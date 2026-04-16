"""API Key authentication middleware for tesla-cli server.

When `server.api_key` is configured (or TESLA_API_KEY env var is set),
all /api/* requests must include a matching key via:
  - Header:      X-API-Key: <key>
  - Query param: ?api_key=<key>

Requests to / and /static/* are always allowed (web dashboard + assets).
"""

from __future__ import annotations

import os

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Enforce X-API-Key on /api/* paths when a key is configured."""

    def __init__(self, app, api_key: str = "") -> None:
        super().__init__(app)
        # env var takes precedence over config value
        self._key = os.environ.get("TESLA_API_KEY", api_key).strip()

    @property
    def enabled(self) -> bool:
        return bool(self._key)

    async def dispatch(self, request: Request, call_next):
        # Only protect /api/* paths
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        # If no key configured → open access
        if not self.enabled:
            return await call_next(request)

        # Check header first, then query param
        provided = request.headers.get("X-API-Key") or request.query_params.get("api_key") or ""

        import hmac as _hmac

        if not _hmac.compare_digest(provided, self._key):
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key. Provide X-API-Key header."},
            )

        return await call_next(request)
