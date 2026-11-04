"""Shared HTTP client base for Tesla API backends."""

from __future__ import annotations

import logging
import threading
import time

import httpx

from tesla_cli.core.exceptions import (
    ApiError,
    AuthenticationError,
    EndpointDeprecatedError,
    NetworkError,
    RateLimitError,
    VehicleAsleepError,
)

logger = logging.getLogger(__name__)


class _TokenBucket:
    """Simple token bucket rate limiter."""

    def __init__(self, max_tokens: int = 5, refill_rate: float = 5 / 60) -> None:
        self._max = max_tokens
        self._tokens = float(max_tokens)
        self._rate = refill_rate
        self._last = time.time()
        self._lock = threading.Lock()

    def acquire(self, timeout: float = 30) -> bool:
        deadline = time.time() + timeout
        while True:
            with self._lock:
                now = time.time()
                self._tokens = min(self._max, self._tokens + (now - self._last) * self._rate)
                self._last = now
                if self._tokens >= 1:
                    self._tokens -= 1
                    return True
            if time.time() >= deadline:
                return False
            time.sleep(0.5)


# Shared across all backend instances, split by Tesla's own quota classes
# (Fleet API: ~60 data req/min, ~30 commands/min, 3 wakes/min per vehicle).
# A single 5-per-minute bucket used to be shared by everything, so the 30 s
# dashboard poller starved interactive commands for up to 30 s.
_data_limiter = _TokenBucket(max_tokens=10, refill_rate=45 / 60)
_command_limiter = _TokenBucket(max_tokens=5, refill_rate=25 / 60)
_wake_limiter = _TokenBucket(max_tokens=2, refill_rate=3 / 60)
_tesla_rate_limiter = _data_limiter  # backwards-compatible name


def _limiter_for(method: str, path: str) -> _TokenBucket:
    if path.rstrip("/").endswith("/wake_up"):
        return _wake_limiter
    return _data_limiter if method.upper() == "GET" else _command_limiter


# Errors where the request provably never reached Tesla: safe to retry for
# any method. Read timeouts / dropped connections may mean a command already
# executed, so those are retried for GET only (never re-honk, never toggle a
# trunk twice).
_SAFE_TRANSPORT_ERRORS = (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)
_IDEMPOTENT_TRANSPORT_ERRORS = (httpx.ReadTimeout, httpx.RemoteProtocolError, httpx.ReadError)


def _retryable_transport_error(method: str, exc: Exception) -> bool:
    if isinstance(exc, _SAFE_TRANSPORT_ERRORS):
        return True
    return method.upper() == "GET" and isinstance(exc, _IDEMPOTENT_TRANSPORT_ERRORS)


def send_with_retry(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    max_retries: int = 3,
    base_delay: float = 1.0,
    **kwargs,
) -> httpx.Response:
    """Send a request, retrying transport failures that are safe to repeat.

    Used directly by backends that do their own status handling (Order API);
    :class:`HttpBackendMixin` builds on it.
    """
    for attempt in range(max_retries + 1):
        try:
            return client.request(method, url, **kwargs)
        except httpx.TransportError as exc:
            if attempt >= max_retries or not _retryable_transport_error(method, exc):
                raise NetworkError(f"{type(exc).__name__}: {exc}") from exc
            delay = base_delay * (2**attempt)
            logger.warning(
                "Network error on %s %s (%s), retrying in %.1fs (attempt %d/%d)",
                method,
                url,
                type(exc).__name__,
                delay,
                attempt + 1,
                max_retries,
            )
            time.sleep(delay)
    raise NetworkError("unreachable")  # pragma: no cover


class HttpBackendMixin:
    """Reusable HTTP methods for backends using httpx.

    Subclasses must set ``_client`` (an ``httpx.Client``) before calling any
    request methods.  The mixin handles the standard Tesla Fleet API error
    mapping (401 → AuthenticationError, 408 → VehicleAsleepError) and
    unwraps the ``{"response": ...}`` envelope that Fleet API returns.

    Retries up to ``_max_retries`` times on 429 (rate limit) and 503 (service
    unavailable) responses, using exponential backoff with optional
    ``Retry-After`` header support.
    """

    _client: httpx.Client

    # Subclasses may override this message to give backend-specific guidance.
    _auth_error_message: str = "Token expired. Re-authenticate."
    _max_retries: int = 3
    _base_delay: float = 1.0

    def _request(self, method: str, path: str, **kwargs) -> dict:
        if not _limiter_for(method, path).acquire(timeout=30):
            raise RateLimitError("Local rate limit exceeded")
        for attempt in range(self._max_retries + 1):
            resp = send_with_retry(
                self._client,
                method,
                path,
                max_retries=self._max_retries,
                base_delay=self._base_delay,
                **kwargs,
            )

            if resp.status_code == 401:
                raise AuthenticationError(self._auth_error_message)
            if resp.status_code == 408:
                raise VehicleAsleepError("Vehicle is asleep. Run: tesla vehicle wake")
            if resp.status_code == 412:
                raise EndpointDeprecatedError()

            if resp.status_code in (429, 503) and attempt < self._max_retries:
                delay = self._base_delay * (2**attempt)
                retry_after = resp.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    delay = max(delay, float(retry_after))
                logger.warning(
                    "Rate limited (%d), retrying in %.1fs (attempt %d/%d)",
                    resp.status_code,
                    delay,
                    attempt + 1,
                    self._max_retries,
                )
                time.sleep(delay)
                continue

            if resp.status_code in (429, 503):
                raise RateLimitError(f"Rate limited after {self._max_retries} retries")

            if resp.status_code not in (200, 201):
                raise ApiError(resp.status_code, resp.text)

            data = resp.json()
            return data.get("response", data) if isinstance(data, dict) else data

        raise RateLimitError(f"Rate limited after {self._max_retries} retries")

    def _get(self, path: str, **kwargs) -> dict:
        return self._request("GET", path, **kwargs)

    def _post(self, path: str, body: dict | None = None, **kwargs) -> dict:
        return self._request("POST", path, json=body or {}, **kwargs)
