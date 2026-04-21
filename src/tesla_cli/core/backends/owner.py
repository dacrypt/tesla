"""Owner API vehicle backend.

Uses the same Tesla Owner API token obtained for order tracking
(owner-api.teslamotors.com) to control the vehicle — no third-party
service or developer app registration required.

This is the same API used by:
- The official Tesla mobile app (older flow)
- TeslaPy, TeslaMate, and other community projects

Note: Tesla officially deprecated this in favour of the Fleet API, but
it continues to work for community use. Endpoints are well-documented
by the community (see references/TeslaPy/teslapy/endpoints.json).
"""

from __future__ import annotations

import logging
import time as _time
from typing import Any

import httpx
import jwt

from tesla_cli import __version__
from tesla_cli.core.auth import tokens
from tesla_cli.core.auth.oauth import refresh_access_token
from tesla_cli.core.backends.base import VehicleBackend
from tesla_cli.core.exceptions import (
    ApiError,
    AuthenticationError,
    EndpointDeprecatedError,
    VehicleAsleepError,
)

logger = logging.getLogger(__name__)

OWNER_API_BASE = "https://owner-api.teslamotors.com"


class OwnerApiVehicleBackend(VehicleBackend):
    """Vehicle backend using the Tesla Owner API with the order-tracking token.

    No extra setup needed — uses the same credentials as `tesla config auth order`.
    """

    def __init__(self) -> None:
        self._client = httpx.Client(base_url=OWNER_API_BASE, timeout=30)
        self._id_cache: dict[str, str] = {}  # VIN → numeric vehicle id_s

    # ── Auth ────────────────────────────────────────────────────────────────

    def _get_access_token(self) -> str:
        """Return a valid access token, refreshing automatically if expired."""
        access = tokens.get_token(tokens.ORDER_ACCESS_TOKEN)
        refresh = tokens.get_token(tokens.ORDER_REFRESH_TOKEN)

        if not refresh:
            raise AuthenticationError("Not authenticated. Run: tesla config auth order")

        if access:
            try:
                payload = jwt.decode(access, options={"verify_signature": False})
                if payload.get("exp", 0) > _time.time() + 60:
                    return access
            except jwt.DecodeError:
                pass

        token_data = refresh_access_token(refresh)
        new_access = token_data["access_token"]
        tokens.set_token(tokens.ORDER_ACCESS_TOKEN, new_access)
        if "refresh_token" in token_data:
            tokens.set_token(tokens.ORDER_REFRESH_TOKEN, token_data["refresh_token"])
        return new_access

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json",
            "User-Agent": f"tesla-cli/{__version__}",
        }

    # ── VIN → vehicle_id resolution ─────────────────────────────────────────

    def _resolve_id(self, vin: str) -> str:
        """Resolve a VIN to the numeric vehicle id_s used by the Owner API.

        Results are cached in-memory for the lifetime of this backend instance.
        """
        if vin in self._id_cache:
            return self._id_cache[vin]

        resp = self._client.get("/api/1/vehicles", headers=self._headers())
        if resp.status_code == 401:
            raise AuthenticationError("Token expired. Run: tesla config auth order")
        if resp.status_code == 412:
            raise EndpointDeprecatedError()
        if resp.status_code != 200:
            raise ApiError(resp.status_code, f"Failed to list vehicles: {resp.text}")

        data = resp.json()
        vehicles = data.get("response", data) if isinstance(data, dict) else data

        for v in vehicles if isinstance(vehicles, list) else []:
            v_vin = v.get("vin", "")
            v_id = str(v.get("id_s") or v.get("id", ""))
            if v_vin:
                self._id_cache[v_vin] = v_id

        if vin not in self._id_cache:
            raise ApiError(404, f"Vehicle {vin} not found on this account")

        return self._id_cache[vin]

    # ── HTTP helpers ─────────────────────────────────────────────────────────

    def _get(self, path: str) -> dict[str, Any]:
        resp = self._client.get(path, headers=self._headers())
        if resp.status_code == 401:
            raise AuthenticationError("Token expired. Run: tesla config auth order")
        if resp.status_code == 408:
            raise VehicleAsleepError("Vehicle is asleep. Run: tesla vehicle wake")
        if resp.status_code == 412:
            raise EndpointDeprecatedError()
        if resp.status_code != 200:
            raise ApiError(resp.status_code, resp.text)
        data = resp.json()
        return data.get("response", data) if isinstance(data, dict) else data

    def _post(self, path: str, body: dict | None = None) -> dict[str, Any]:
        resp = self._client.post(path, json=body or {}, headers=self._headers())
        if resp.status_code == 401:
            raise AuthenticationError("Token expired. Run: tesla config auth order")
        if resp.status_code == 408:
            raise VehicleAsleepError("Vehicle is asleep. Run: tesla vehicle wake")
        if resp.status_code == 412:
            raise EndpointDeprecatedError()
        if resp.status_code != 200:
            raise ApiError(resp.status_code, resp.text)
        data = resp.json()
        return data.get("response", data) if isinstance(data, dict) else data

    # ── VehicleBackend interface ─────────────────────────────────────────────

    def list_vehicles(self) -> list[dict[str, Any]]:
        data = self._get("/api/1/vehicles")
        return data if isinstance(data, list) else []

    def get_vehicle_data(self, vin: str) -> dict[str, Any]:
        vid = self._resolve_id(vin)
        return self._get(f"/api/1/vehicles/{vid}/vehicle_data")

    def get_charge_state(self, vin: str) -> dict[str, Any]:
        data = self.get_vehicle_data(vin)
        return data.get("charge_state", data)

    def get_climate_state(self, vin: str) -> dict[str, Any]:
        data = self.get_vehicle_data(vin)
        return data.get("climate_state", data)

    def get_drive_state(self, vin: str) -> dict[str, Any]:
        data = self.get_vehicle_data(vin)
        return data.get("drive_state", data)

    def get_vehicle_state(self, vin: str) -> dict[str, Any]:
        data = self.get_vehicle_data(vin)
        return data.get("vehicle_state", data)

    def get_vehicle_config(self, vin: str) -> dict[str, Any]:
        data = self.get_vehicle_data(vin)
        return data.get("vehicle_config", data)

    def mobile_enabled(self, vin: str) -> bool:
        vid = self._resolve_id(vin)
        data = self._get(f"/api/1/vehicles/{vid}/mobile_enabled")
        return bool(data) if not isinstance(data, dict) else data.get("result", False)

    def get_nearby_charging_sites(self, vin: str) -> dict[str, Any]:
        vid = self._resolve_id(vin)
        return self._get(f"/api/1/vehicles/{vid}/nearby_charging_sites")

    def get_service_data(self, vin: str) -> dict[str, Any]:
        vid = self._resolve_id(vin)
        return self._get(f"/api/1/vehicles/{vid}/service_data")

    def wake_up(self, vin: str) -> bool:
        vid = self._resolve_id(vin)
        data = self._post(f"/api/1/vehicles/{vid}/wake_up")
        return data.get("state") == "online"

    def command(self, vin: str, cmd: str, **params: Any) -> dict[str, Any]:
        """Send a command to the vehicle via the Owner API.

        If the vehicle is asleep, wakes it up automatically and retries (up to
        3 attempts with 8-second back-off between retries).
        """
        vid = self._resolve_id(vin)
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                return self._post(
                    f"/api/1/vehicles/{vid}/command/{cmd}",
                    body=params or None,
                )
            except VehicleAsleepError:
                if attempt == max_attempts - 1:
                    raise
                logger.info(
                    "Vehicle asleep (attempt %d/%d) — waking up…", attempt + 1, max_attempts
                )
                self._post(f"/api/1/vehicles/{vid}/wake_up")
                _time.sleep(8)
        # Should never reach here
        raise VehicleAsleepError("Vehicle did not wake up in time")
