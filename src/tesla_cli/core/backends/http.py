"""Shared HTTP client base for Tesla API backends."""

from __future__ import annotations

import httpx

from tesla_cli.core.exceptions import ApiError, AuthenticationError, VehicleAsleepError


class HttpBackendMixin:
    """Reusable HTTP methods for backends using httpx.

    Subclasses must set ``_client`` (an ``httpx.Client``) before calling any
    request methods.  The mixin handles the standard Tesla Fleet API error
    mapping (401 → AuthenticationError, 408 → VehicleAsleepError) and
    unwraps the ``{"response": ...}`` envelope that Fleet API returns.
    """

    _client: httpx.Client

    # Subclasses may override this message to give backend-specific guidance.
    _auth_error_message: str = "Token expired. Re-authenticate."

    def _request(self, method: str, path: str, **kwargs) -> dict:
        resp = self._client.request(method, path, **kwargs)
        if resp.status_code == 401:
            raise AuthenticationError(self._auth_error_message)
        if resp.status_code == 408:
            raise VehicleAsleepError("Vehicle is asleep. Run: tesla vehicle wake")
        if resp.status_code not in (200, 201):
            raise ApiError(resp.status_code, resp.text)
        data = resp.json()
        return data.get("response", data) if isinstance(data, dict) else data

    def _get(self, path: str) -> dict:
        return self._request("GET", path)

    def _post(self, path: str, body: dict | None = None) -> dict:
        return self._request("POST", path, json=body or {})
