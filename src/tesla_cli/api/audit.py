"""API audit trail — logs mutating vehicle commands to JSONL."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request
from starlette.middleware.base import BaseHTTPMiddleware

from tesla_cli.core.events import EVENTS_DIR, _append_jsonl, _read_jsonl

AUDIT_FILE = EVENTS_DIR / "audit.jsonl"

# Every state-changing /api call is audited except sign-in flows (which carry
# credentials and are not vehicle/config actions).
_UNAUDITED_PREFIXES = ("/api/auth", "/api/session")
_REDACT_KEYS = {
    "token",
    "password",
    "secret",
    "code",
    "key",
    "api_key",
    "refresh_token",
    "access_token",
    "pin",
    "url",
    "webhook_url",
    "urls",
}


def _key_hint(request: Request) -> str:
    key = request.headers.get("X-API-Key") or ""
    if len(key) >= 4:
        return f"**{key[-4:]}"
    return "session" if request.cookies.get("tesla_cli_session") else "none"


def _redact(params: Any) -> Any:
    if isinstance(params, dict):
        return {
            k: "***" if str(k).lower() in _REDACT_KEYS else _redact(v) for k, v in params.items()
        }
    if isinstance(params, list):
        return [_redact(v) for v in params]
    return params


class AuditMiddleware(BaseHTTPMiddleware):
    """Log every mutating /api call (vehicle commands, config, automations, …)."""

    async def dispatch(self, request: Request, call_next):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return await call_next(request)
        path = request.url.path
        if not path.startswith("/api/") or path.startswith(_UNAUDITED_PREFIXES):
            return await call_next(request)

        # Capture request body for logging
        body: dict = {}
        try:
            raw = await request.body()
            if raw:
                import json

                body = _redact(json.loads(raw))
        except Exception:
            logging.getLogger(__name__).debug("Ignored error", exc_info=True)

        t0 = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - t0) * 1000)

        entry = {
            "ts": datetime.now(UTC).isoformat(),
            "method": request.method,
            "path": request.url.path,
            "api_key_hint": _key_hint(request),
            "params": body,
            "status": response.status_code,
            "ok": 200 <= response.status_code < 400,
            "duration_ms": duration_ms,
        }
        _append_jsonl(AUDIT_FILE, entry)

        return response


# ── Query endpoint ───────────────────────────────────────────────────────────

audit_router = APIRouter()


@audit_router.get("")
def list_audit(limit: int = 50) -> list:
    """Recent audit log entries (newest first)."""
    limit = min(limit, 500)
    entries = _read_jsonl(AUDIT_FILE, limit)
    return list(reversed(entries))
