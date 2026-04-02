"""Tessie proxy backend implementation."""

from __future__ import annotations

from typing import Any

import httpx

from tesla_cli.core.backends.base import VehicleBackend
from tesla_cli.core.exceptions import ApiError, VehicleAsleepError

TESSIE_API = "https://api.tessie.com"


class TessieBackend(VehicleBackend):
    """Vehicle backend using Tessie as a proxy to Tesla Fleet API."""

    def __init__(self, token: str) -> None:
        self._token = token
        self._client = httpx.Client(
            base_url=TESSIE_API,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )

    def _get(self, path: str) -> dict[str, Any]:
        resp = self._client.get(path)
        if resp.status_code == 408:
            raise VehicleAsleepError("Vehicle is asleep. Run: tesla vehicle wake")
        if resp.status_code != 200:
            raise ApiError(resp.status_code, resp.text)
        return resp.json()

    def _post(self, path: str, **params: Any) -> dict[str, Any]:
        resp = self._client.post(path, json=params if params else None)
        if resp.status_code == 408:
            raise VehicleAsleepError("Vehicle is asleep. Run: tesla vehicle wake")
        if resp.status_code != 200:
            raise ApiError(resp.status_code, resp.text)
        return resp.json()

    def list_vehicles(self) -> list[dict[str, Any]]:
        data = self._get("/api/1/vehicles")
        return data.get("response", data) if isinstance(data, dict) else data

    def get_vehicle_data(self, vin: str) -> dict[str, Any]:
        data = self._get(f"/{vin}/state")
        return data

    def get_charge_state(self, vin: str) -> dict[str, Any]:
        data = self.get_vehicle_data(vin)
        return data.get("charge_state", data)

    def get_climate_state(self, vin: str) -> dict[str, Any]:
        data = self.get_vehicle_data(vin)
        return data.get("climate_state", data)

    def get_drive_state(self, vin: str) -> dict[str, Any]:
        data = self.get_vehicle_data(vin)
        return data.get("drive_state", data)

    def get_vehicle_config(self, vin: str) -> dict[str, Any]:
        data = self.get_vehicle_data(vin)
        return data.get("vehicle_config", data)

    def get_vehicle_state(self, vin: str) -> dict[str, Any]:
        data = self.get_vehicle_data(vin)
        return data.get("vehicle_state", {})

    def get_service_data(self, vin: str) -> dict[str, Any]:
        # Tessie returns service data inside the full state blob
        data = self.get_vehicle_data(vin)
        return data.get("service_data", {})

    def get_nearby_charging_sites(self, vin: str) -> dict[str, Any]:
        return self._get(f"/{vin}/nearby_charging_sites")

    def wake_up(self, vin: str) -> bool:
        data = self._post(f"/{vin}/wake")
        return data.get("result", False)

    def command(self, vin: str, command: str, **params: Any) -> dict[str, Any]:
        return self._post(f"/{vin}/command/{command}", **params)

    # Fleet-only methods — override to give Tessie-specific message
    def get_release_notes(self, vin: str) -> dict[str, Any]:
        from tesla_cli.core.exceptions import BackendNotSupportedError

        raise BackendNotSupportedError("vehicle release-notes", "fleet")

    def get_recent_alerts(self, vin: str) -> dict[str, Any]:
        from tesla_cli.core.exceptions import BackendNotSupportedError

        raise BackendNotSupportedError("vehicle alerts", "fleet")

    def get_charge_history(self) -> dict[str, Any]:
        from tesla_cli.core.exceptions import BackendNotSupportedError

        raise BackendNotSupportedError(
            "charge history", "fleet  (or use `tesla teslaMate charging` if you have TeslaMate)"
        )

    def get_invitations(self, vin: str) -> list[dict[str, Any]]:
        from tesla_cli.core.exceptions import BackendNotSupportedError

        raise BackendNotSupportedError("sharing list", "fleet")

    def create_invitation(self, vin: str) -> dict[str, Any]:
        from tesla_cli.core.exceptions import BackendNotSupportedError

        raise BackendNotSupportedError("sharing invite", "fleet")

    def revoke_invitation(self, vin: str, invitation_id: str) -> dict[str, Any]:
        from tesla_cli.core.exceptions import BackendNotSupportedError

        raise BackendNotSupportedError("sharing revoke", "fleet")
