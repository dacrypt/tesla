"""Shared HTTP client base for Tesla API backends."""

from __future__ import annotations

import logging
import time

import httpx

from tesla_cli.core.exceptions import (
    ApiError,
    AuthenticationError,
    EndpointDeprecatedError,
    RateLimitError,
    VehicleAsleepError,
)

logger = logging.getLogger(__name__)


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
        for attempt in range(self._max_retries + 1):
            resp = self._client.request(method, path, **kwargs)

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

    def _get(self, path: str) -> dict:
        return self._request("GET", path)

    def _post(self, path: str, body: dict | None = None) -> dict:
        return self._request("POST", path, json=body or {})
