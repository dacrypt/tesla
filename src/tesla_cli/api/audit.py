"""API audit trail — logs mutating vehicle commands to JSONL."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request
from starlette.middleware.base import BaseHTTPMiddleware

from tesla_cli.core.events import EVENTS_DIR, _append_jsonl, _read_jsonl

AUDIT_FILE = EVENTS_DIR / "audit.jsonl"

_AUDITED_PREFIXES = ("/api/vehicle", "/api/security", "/api/climate", "/api/charge")
_REDACT_KEYS = {"token", "password", "secret", "code", "api_key", "refresh_token", "access_token"}


def _key_hint(request: Request) -> str:
    key = request.headers.get("X-API-Key") or request.query_params.get("api_key") or ""
    return f"**{key[-4:]}" if len(key) >= 4 else "none"


def _redact(params: dict[str, Any]) -> dict[str, Any]:
    return {k: "***" if k.lower() in _REDACT_KEYS else v for k, v in params.items()}


class AuditMiddleware(BaseHTTPMiddleware):
    """Log mutating API calls on vehicle-control routes."""

    async def dispatch(self, request: Request, call_next):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return await call_next(request)
        if request.url.path.startswith("/api/auth"):
            return await call_next(request)
        if not any(request.url.path.startswith(p) for p in _AUDITED_PREFIXES):
            return await call_next(request)

        # Capture request body for logging
        body: dict = {}
        try:
            raw = await request.body()
            if raw:
                import json

                body = _redact(json.loads(raw))
        except Exception:
            pass

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
