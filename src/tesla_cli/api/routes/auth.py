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
    get_token,
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
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
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
        r = httpx.post(TOKEN_URL, data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "code": req.code,
            "code_verifier": verifier,
            "redirect_uri": VOID_REDIRECT_URI,
        }, timeout=30)
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


# ── Status ────────────────────────────────────────────────────────────────────

@router.get("/status")
def auth_status() -> dict:
    """Current authentication state."""
    cfg = load_config()
    return {
        "authenticated": has_token(FLEET_ACCESS_TOKEN) or has_token(TESSIE_TOKEN),
        "backend": cfg.general.backend,
        "has_fleet": has_token(FLEET_ACCESS_TOKEN),
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
