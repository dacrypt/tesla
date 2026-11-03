"""Authentication + request-hardening middleware for the tesla-cli server.

Threat model (self-hosted): the server runs on a home machine / NAS / Pi and
may be reachable from the LAN, a VPN (Tailscale) or a reverse proxy. Anything
on that network, *and any web page open in the owner's browser*, can try to
talk to it. This middleware enforces:

1. **API key auth** on every ``/api/*`` path when a key is configured.
   Credentials are accepted via the ``X-API-Key`` header or the HttpOnly
   session cookie issued by ``POST /api/session`` (used by the dashboard and
   by ``EventSource``, which cannot set headers). Query-string keys are no
   longer accepted — they leak into proxy logs and browser history.

2. **Roles**: ``server.api_key`` grants full control; ``server.read_only_key``
   (optional) grants only safe methods (GET/HEAD/OPTIONS). Handy for a family
   wall dashboard or a Home Assistant integration that only reads.

3. **CSRF**: state-changing requests (POST/PUT/PATCH/DELETE) carrying a
   cross-site ``Origin`` or ``Sec-Fetch-Site: cross-site`` are rejected, even
   with no key configured. A malicious page can no longer fire
   ``POST /api/security/unlock`` at ``localhost:8080``.

4. **DNS rebinding**: when no key is configured (localhost-only mode) the
   ``Host`` header must be a loopback name or listed in
   ``server.allowed_hosts``.

Always-public paths: ``/api/health`` (Docker HEALTHCHECK; the ``?deep=`` variant
requires auth) and ``/api/session`` (login/logout/status).
"""

from __future__ import annotations

import hashlib
import hmac
import os
from urllib.parse import urlsplit

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

SESSION_COOKIE = "tesla_cli_session"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_LOOPBACK_HOSTS: set[str] = {"localhost", "127.0.0.1", "::1"}
_PUBLIC_PATHS = frozenset({"/api/session"})

ROLE_CONTROL = "control"
ROLE_READ = "read"


def session_token(key: str) -> str:
    """Derive the cookie value for *key* (the raw key never lands in a cookie)."""
    return hmac.new(key.encode(), b"tesla-cli-session-v1", hashlib.sha256).hexdigest()


def effective_keys(api_key: str = "", read_only_key: str = "") -> tuple[str, str]:
    """Return (control_key, read_only_key); env vars override config values."""
    return (
        os.environ.get("TESLA_API_KEY", api_key).strip(),
        os.environ.get("TESLA_READ_ONLY_KEY", read_only_key).strip(),
    )


def resolve_role(key: str, ro_key: str, provided: str = "", cookie: str = "") -> str | None:
    """Map a provided key and/or session cookie to a role (None = unauthenticated).

    Every candidate is compared so timing does not reveal which key matched.
    """
    role: str | None = None
    candidates = [(key, ROLE_CONTROL)]
    if ro_key:
        candidates.append((ro_key, ROLE_READ))
    for cand, cand_role in candidates:
        if not cand:
            continue
        hit = False
        if provided:
            hit |= hmac.compare_digest(provided.encode(), cand.encode())
        if cookie:
            hit |= hmac.compare_digest(cookie.encode(), session_token(cand).encode())
        if hit and role is None:
            role = cand_role
    return role


def _host_only(value: str) -> str:
    """Strip port (and IPv6 brackets) from a Host/netloc value; lower-case it."""
    value = value.strip().lower()
    if value.startswith("["):
        return value[1:].split("]", 1)[0]
    if value.count(":") == 1:
        return value.rsplit(":", 1)[0]
    return value


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Enforce auth, roles, CSRF and Host checks on /api/* paths."""

    def __init__(
        self,
        app,
        api_key: str = "",
        read_only_key: str = "",
        allowed_hosts: list[str] | None = None,
        allowed_origins: list[str] | None = None,
    ) -> None:
        super().__init__(app)
        self._key, self._ro_key = effective_keys(api_key, read_only_key)
        self._allowed_hosts = {h.strip().lower() for h in (allowed_hosts or []) if h.strip()}
        self._allowed_origins = {o.rstrip("/").lower() for o in (allowed_origins or [])}

    @property
    def enabled(self) -> bool:
        return bool(self._key)

    # ── credential resolution ────────────────────────────────────────────────

    def role_for(self, request: Request) -> str | None:
        """Return the role granted by the request's credentials, or None."""
        if not self.enabled:
            return ROLE_CONTROL
        provided = request.headers.get("X-API-Key", "")
        cookie = request.cookies.get(SESSION_COOKIE, "")
        return self.role_for_credentials(provided, cookie)

    def role_for_credentials(self, provided: str = "", cookie: str = "") -> str | None:
        return resolve_role(self._key, self._ro_key, provided, cookie)

    # ── request checks ───────────────────────────────────────────────────────

    def _host_allowed(self, request: Request) -> bool:
        if "*" in self._allowed_hosts:
            return True
        host = _host_only(request.headers.get("host", ""))
        return host in _LOOPBACK_HOSTS or host in self._allowed_hosts

    def _is_cross_site(self, request: Request) -> bool:
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/").lower() in self._allowed_origins:
            return False
        if request.headers.get("sec-fetch-site", "").lower() == "cross-site":
            return True
        if not origin:
            return False  # non-browser client (curl, HA, scripts)
        if origin.lower() == "null":
            return True
        origin_host = urlsplit(origin).netloc.lower()
        return origin_host != request.headers.get("host", "").lower()

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith("/api/"):
            return await call_next(request)

        method = request.method.upper()

        if method not in SAFE_METHODS and self._is_cross_site(request):
            return JSONResponse(
                status_code=403,
                content={"detail": "Cross-site request blocked."},
            )

        if not self.enabled and not self._host_allowed(request):
            return JSONResponse(
                status_code=403,
                content={
                    "detail": (
                        "Host not allowed. Configure server.api_key to expose the API "
                        "beyond localhost, or add this host to server.allowed_hosts."
                    )
                },
            )

        if path in _PUBLIC_PATHS or (path == "/api/health" and "deep" not in request.query_params):
            return await call_next(request)

        role = self.role_for(request)
        if role is None:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key. Provide X-API-Key header."},
            )
        if role == ROLE_READ and method not in SAFE_METHODS:
            return JSONResponse(
                status_code=403,
                content={"detail": "Read-only key cannot perform this action."},
            )

        request.state.auth_role = role
        return await call_next(request)
