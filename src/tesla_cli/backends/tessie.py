"""Tessie proxy backend implementation."""

from __future__ import annotations

from typing import Any

import httpx

from tesla_cli.backends.base import VehicleBackend
from tesla_cli.exceptions import ApiError, VehicleAsleepError

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

    def wake_up(self, vin: str) -> bool:
        data = self._post(f"/{vin}/wake")
        return data.get("result", False)

    def command(self, vin: str, command: str, **params: Any) -> dict[str, Any]:
        return self._post(f"/{vin}/command/{command}", **params)
