"""Dashboard session endpoints: exchange an API key for an HttpOnly cookie.

The browser dashboard cannot keep the API key in JS-readable storage safely,
and ``EventSource`` (SSE) cannot send custom headers. ``POST /api/session``
validates the key once and sets an HttpOnly, SameSite=Strict cookie derived
from it; the auth middleware accepts that cookie on every later request.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from tesla_cli.api.auth import SESSION_COOKIE, resolve_role, session_token

router = APIRouter()

_COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


class SessionLogin(BaseModel):
    key: str


def _keys(request: Request) -> tuple[str, str]:
    return getattr(request.app.state, "auth_keys", ("", ""))


@router.get("")
def session_status(request: Request) -> dict:
    """Whether auth is required and whether this browser is signed in."""
    key, ro_key = _keys(request)
    if not key:
        return {"auth_required": False, "authenticated": True, "role": "control"}
    role = resolve_role(
        key, ro_key, request.headers.get("X-API-Key", ""), request.cookies.get(SESSION_COOKIE, "")
    )
    return {"auth_required": True, "authenticated": role is not None, "role": role}


@router.post("")
def session_login(body: SessionLogin, request: Request, response: Response) -> dict:
    """Validate an API key and set the session cookie."""
    key, ro_key = _keys(request)
    if not key:
        return {"auth_required": False, "authenticated": True, "role": "control"}
    role = resolve_role(key, ro_key, body.key.strip())
    if role is None:
        raise HTTPException(status_code=401, detail="Invalid API key.")
    matched = key if role == "control" else ro_key
    response.set_cookie(
        SESSION_COOKIE,
        session_token(matched),
        max_age=_COOKIE_MAX_AGE,
        httponly=True,
        samesite="strict",
        secure=request.url.scheme == "https",
        path="/",
    )
    return {"auth_required": True, "authenticated": True, "role": role}


@router.delete("")
def session_logout(response: Response) -> dict:
    """Clear the session cookie."""
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}
