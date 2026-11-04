"""Map backend/core exceptions to HTTP responses in one place.

Routes used to copy-paste the same ``except Exception`` block (matching
``"412"``/``"429"`` inside the error text) dozens of times. They now call
:func:`upstream_http_error`, and :func:`register_exception_handlers` covers
typed errors that a route does not catch at all.

Status mapping:

====================================  ======  ============================
Exception                             Status  Meaning for the client
====================================  ======  ============================
VehicleAsleepError                    503     wake the car and retry
RateLimitError / HTTP 429             429     retry later (``Retry-After``)
EndpointDeprecatedError / HTTP 412    412     endpoint gone / pre-delivery
BackendNotSupportedError              501     switch backend
AuthenticationError (Tesla tokens)    424     re-authenticate with Tesla
ConfigurationError                    400     fix configuration
anything else from upstream           502     upstream failure
====================================  ======  ============================

Tesla auth failures deliberately do **not** use 401: the dashboard treats 401
as "your API key for this server is wrong" and shows the sign-in screen.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from tesla_cli.core.exceptions import (
    ApiError,
    AuthenticationError,
    BackendNotSupportedError,
    ConfigurationError,
    EndpointDeprecatedError,
    RateLimitError,
    TeslaCliError,
    VehicleAsleepError,
)

log = logging.getLogger("tesla-cli.api")

ASLEEP_DETAIL = "Vehicle is asleep."
NOT_ACCESSIBLE_DETAIL = "Vehicle not accessible. May be pre-delivery or require Fleet API."
RATE_LIMIT_DETAIL = "Rate limited. Try again in a few seconds."
_MAX_DETAIL = 500


def _status_of(exc: BaseException) -> int | None:
    if isinstance(exc, ApiError):
        return exc.status_code
    # Untyped errors (third-party clients) — last-resort text sniffing,
    # kept in exactly one place.
    text = str(exc)
    for code in (412, 429):
        if f"HTTP {code}" in text or f" {code} " in f" {text} ":
            return code
    return None


def _detail(exc: BaseException) -> str:
    text = str(exc) or exc.__class__.__name__
    return text if len(text) <= _MAX_DETAIL else text[:_MAX_DETAIL] + "…"


def upstream_http_error(exc: BaseException, default_status: int = 502) -> HTTPException:
    """Return the HTTPException a route should raise for *exc*."""
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, VehicleAsleepError):
        return HTTPException(status_code=503, detail=ASLEEP_DETAIL)
    if isinstance(exc, RateLimitError):
        return HTTPException(
            status_code=429, detail=RATE_LIMIT_DETAIL, headers={"Retry-After": "10"}
        )
    if isinstance(exc, EndpointDeprecatedError):
        return HTTPException(status_code=412, detail=_detail(exc) or NOT_ACCESSIBLE_DETAIL)
    if isinstance(exc, BackendNotSupportedError):
        return HTTPException(status_code=501, detail=_detail(exc))
    if isinstance(exc, AuthenticationError):
        return HTTPException(status_code=424, detail=_detail(exc))
    if isinstance(exc, ConfigurationError):
        return HTTPException(status_code=400, detail=_detail(exc))
    status = _status_of(exc)
    if status == 429:
        return HTTPException(
            status_code=429, detail=RATE_LIMIT_DETAIL, headers={"Retry-After": "10"}
        )
    if status == 412:
        return HTTPException(status_code=412, detail=NOT_ACCESSIBLE_DETAIL)
    return HTTPException(status_code=default_status, detail=_detail(exc))


def register_exception_handlers(app: FastAPI) -> None:
    """Translate typed errors that escape a route into proper HTTP responses."""

    @app.exception_handler(TeslaCliError)
    async def _tesla_cli_error(request: Request, exc: TeslaCliError) -> JSONResponse:
        http = upstream_http_error(exc)
        if http.status_code >= 500:
            log.warning("%s %s failed: %s", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=http.status_code,
            content={"detail": http.detail},
            headers=http.headers,
        )
