"""Auth API routes: /api/auth/* — Tesla OAuth from the PWA."""

from __future__ import annotations

import base64
import hashlib
import secrets
import urllib.parse

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from tesla_cli.core.auth.tokens import (
    FLEET_ACCESS_TOKEN,
    FLEET_REFRESH_TOKEN,
    TESSIE_TOKEN,
    has_token,
    set_token,
)
from tesla_cli.core.config import load_config, save_config

router = APIRouter()

# In-memory PKCE verifier store (state → verifier)
_pending_auth: dict[str, str] = {}

AUTH_BASE = "https://auth.tesla.com/oauth2/v3"
AUTHORIZE_URL = f"{AUTH_BASE}/authorize"
TOKEN_URL = f"{AUTH_BASE}/token"
VOID_REDIRECT_URI = "https://auth.tesla.com/void/callback"
FLEET_SCOPES = "openid email offline_access vehicle_device_data vehicle_cmds vehicle_charging_cmds"


# ── Login (generate auth URL) ────────────────────────────────────────────────


@router.get("/login")
def auth_login() -> dict:
    """Generate Tesla OAuth URL for the PWA to open in a popup.

    Returns {auth_url, state} — frontend opens auth_url in popup,
    then sends code + state to POST /api/auth/callback.
    """
    cfg = load_config()
    client_id = cfg.fleet.client_id
    if not client_id:
        raise HTTPException(400, "No Fleet API client_id configured. Run: tesla config auth fleet")

    verifier = secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    state = secrets.token_urlsafe(32)
    _pending_auth[state] = verifier

    params = {
        "client_id": client_id,
        "redirect_uri": VOID_REDIRECT_URI,
        "response_type": "code",
        "scope": FLEET_SCOPES,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    auth_url = f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"
    return {"auth_url": auth_url, "state": state}


# ── Callback (exchange code for tokens) ──────────────────────────────────────


class CallbackRequest(BaseModel):
    code: str
    state: str


@router.post("/callback")
def auth_callback(req: CallbackRequest) -> dict:
    """Exchange authorization code for tokens.

    Called by the PWA after user completes Tesla login and copies
    the void/callback URL containing the code.
    """
    verifier = _pending_auth.pop(req.state, None)
    if not verifier:
        raise HTTPException(400, "Invalid or expired state. Try logging in again.")

    cfg = load_config()
    client_id = cfg.fleet.client_id

    # Exchange code for tokens
    import httpx

    try:
        r = httpx.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": client_id,
                "code": req.code,
                "code_verifier": verifier,
                "redirect_uri": VOID_REDIRECT_URI,
            },
            timeout=30,
        )
        r.raise_for_status()
        token_data = r.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"Token exchange failed: {e.response.status_code}") from e
    except Exception as e:
        raise HTTPException(502, f"Token exchange error: {e}") from e

    # Store tokens in keyring
    set_token(FLEET_ACCESS_TOKEN, token_data["access_token"])
    set_token(FLEET_REFRESH_TOKEN, token_data["refresh_token"])

    # Set backend to fleet if not already
    if cfg.general.backend != "fleet":
        cfg.general.backend = "fleet"
        save_config(cfg)

    # Auto-sync to TeslaMate if running
    _sync_teslamate_tokens()

    return {
        "ok": True,
        "expires_in": token_data.get("expires_in"),
        "backend": "fleet",
    }


# ── Tessie token (paste) ─────────────────────────────────────────────────────


class TessieRequest(BaseModel):
    token: str


@router.post("/tessie")
def auth_tessie(req: TessieRequest) -> dict:
    """Save a Tessie API token."""
    if not req.token or len(req.token) < 10:
        raise HTTPException(400, "Invalid token")
    set_token(TESSIE_TOKEN, req.token)
    cfg = load_config()
    cfg.tessie.configured = True
    cfg.general.backend = "tessie"
    save_config(cfg)
    return {"ok": True, "backend": "tessie"}


# ── Browser login (email + password) ──────────────────────────────────────────


class BrowserLoginRequest(BaseModel):
    email: str
    password: str
    mfa_code: str | None = None


@router.post("/browser-login")
def auth_browser_login(req: BrowserLoginRequest) -> dict:
    """Login with Tesla email + password via headless browser.

    Automates the full OAuth flow in a headless browser (patchright),
    capturing both Owner API and Fleet API tokens. Runs as subprocess
    to avoid Playwright/uvicorn conflicts.

    Returns {ok, has_order, has_fleet} on success.
    If MFA is required, returns {ok: false, mfa_required: true}.
    """
    import json as _json
    import subprocess
    import sys

    cfg = load_config()
    fleet_client_id = cfg.fleet.client_id or ""

    # Run in subprocess (Playwright doesn't work in uvicorn)
    script = f"""
import json
from tesla_cli.core.auth.browser_login import full_login
try:
    result = full_login(
        email={repr(req.email)},
        password={repr(req.password)},
        mfa_code={repr(req.mfa_code)},
        fleet_client_id={repr(fleet_client_id)},
    )
    print(json.dumps({{
        "ok": True,
        "order": result.get("order"),
        "fleet": result.get("fleet"),
    }}))
except Exception as e:
    msg = str(e)
    print(json.dumps({{
        "ok": False,
        "mfa_required": "MFA_REQUIRED" in msg,
        "error": msg if "MFA_REQUIRED" not in msg else "MFA code required",
    }}))
"""

    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.stdout.strip():
            data = _json.loads(result.stdout.strip())
        else:
            raise HTTPException(
                502, f"Login failed: {result.stderr[:200] if result.stderr else 'no output'}"
            )
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "Login timed out")
    except _json.JSONDecodeError:
        raise HTTPException(
            502, f"Login error: {result.stdout[:100] if result.stdout else result.stderr[:100]}"
        )

    if not data.get("ok"):
        if data.get("mfa_required"):
            return {"ok": False, "mfa_required": True, "error": "Enter your MFA code"}
        raise HTTPException(401, data.get("error", "Login failed"))

    # Store tokens
    if data.get("order"):
        from tesla_cli.core.auth.tokens import ORDER_ACCESS_TOKEN, ORDER_REFRESH_TOKEN

        set_token(ORDER_ACCESS_TOKEN, data["order"]["access_token"])
        set_token(ORDER_REFRESH_TOKEN, data["order"]["refresh_token"])

    if data.get("fleet"):
        set_token(FLEET_ACCESS_TOKEN, data["fleet"]["access_token"])
        set_token(FLEET_REFRESH_TOKEN, data["fleet"]["refresh_token"])

    # Set backend to fleet if we got fleet tokens
    if data.get("fleet"):
        cfg = load_config()
        cfg.general.backend = "fleet"
        save_config(cfg)

    # Auto-discover VIN and reservation from order API
    if data.get("order"):
        try:
            from tesla_cli.core.backends.order import OrderBackend

            backend = OrderBackend()
            orders = backend.get_orders()
            order_list = orders if isinstance(orders, list) else [orders]
            if order_list:
                first = order_list[0]
                cfg = load_config()
                rn = first.get("referenceNumber", "")
                vin = first.get("vin", "")
                if rn and not cfg.order.reservation_number:
                    cfg.order.reservation_number = rn
                if vin and not cfg.general.default_vin:
                    cfg.general.default_vin = vin
                save_config(cfg)
        except Exception:
            pass

    # Auto-sync to TeslaMate
    _sync_teslamate_tokens()

    return {
        "ok": True,
        "has_order": bool(data.get("order")),
        "has_fleet": bool(data.get("fleet")),
    }


# ── Portal scrape (full order data) ───────────────────────────────────────────


class PortalScrapeRequest(BaseModel):
    email: str
    password: str
    mfa_code: str | None = None


@router.post("/portal-scrape")
def auth_portal_scrape(req: PortalScrapeRequest) -> dict:
    """Scrape Tesla ownership portal for full order/delivery/registration data.

    Automates login to tesla.com/teslaaccount via headless browser,
    extracts window.Tesla.App.* data including documents, registration,
    financing, delivery details — everything the mobile app shows.

    If MFA required, returns {ok: false, mfa_required: true}.
    """
    import json as _json
    import subprocess
    import sys

    cfg = load_config()
    rn = cfg.order.reservation_number or ""

    script = f"""
import json
from tesla_cli.core.auth.portal_scrape import scrape_portal
try:
    data = scrape_portal(
        email={repr(req.email)},
        password={repr(req.password)},
        mfa_code={repr(req.mfa_code)},
        reservation_number={repr(rn)},
    )
    # Save to sources cache
    from tesla_cli.core.sources import _save_cache
    from pathlib import Path
    _save_cache("tesla.portal", data)
    print(json.dumps({{"ok": True, "keys": list(data.keys()), "sections": len(data)}}))
except Exception as e:
    msg = str(e)
    print(json.dumps({{
        "ok": False,
        "mfa_required": "MFA_REQUIRED" in msg,
        "error": msg if "MFA_REQUIRED" not in msg else "MFA code required",
    }}))
"""

    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.stdout.strip():
            data = _json.loads(result.stdout.strip())
        else:
            raise HTTPException(502, f"Portal scrape failed: {result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "Portal scrape timed out")
    except _json.JSONDecodeError:
        raise HTTPException(502, f"Portal error: {result.stdout[:100]}")

    if not data.get("ok"):
        if data.get("mfa_required"):
            return {"ok": False, "mfa_required": True}
        raise HTTPException(502, data.get("error", "Scrape failed"))

    return data


# ── Status ────────────────────────────────────────────────────────────────────


@router.get("/status")
def auth_status() -> dict:
    """Current authentication state."""
    from tesla_cli.core.auth.tokens import ORDER_ACCESS_TOKEN

    cfg = load_config()
    return {
        "authenticated": has_token(FLEET_ACCESS_TOKEN)
        or has_token(TESSIE_TOKEN)
        or has_token(ORDER_ACCESS_TOKEN),
        "backend": cfg.general.backend,
        "has_fleet": has_token(FLEET_ACCESS_TOKEN),
        "has_order": has_token(ORDER_ACCESS_TOKEN),
        "has_tessie": has_token(TESSIE_TOKEN),
        "fleet_client_id": cfg.fleet.client_id or None,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────


def _sync_teslamate_tokens() -> None:
    """Best-effort sync tokens to TeslaMate if managed stack is running."""
    try:
        from pathlib import Path

        cfg = load_config()
        if not cfg.teslaMate.managed:
            return
        from tesla_cli.infra.teslamate_stack import TeslaMateStack

        stack = TeslaMateStack(Path(cfg.teslaMate.stack_dir) if cfg.teslaMate.stack_dir else None)
        if stack.is_running():
            stack.sync_tokens_from_keyring()
    except Exception:
        pass
