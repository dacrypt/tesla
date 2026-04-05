"""Teslemetry backend — hosted Fleet Telemetry proxy.

Real-time vehicle streaming without self-hosted infrastructure.
Sign up at https://teslemetry.com for an API key.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from typing import Any

import httpx

from tesla_cli.core.exceptions import ApiError

TESLEMETRY_API = "https://api.teslemetry.com"


class TeslemetryBackend:
    """Query Teslemetry API for real-time vehicle data and SSE streaming."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = httpx.Client(
            base_url=TESLEMETRY_API,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30,
        )

    def _get(self, path: str) -> dict[str, Any]:
        resp = self._client.get(path)
        if resp.status_code != 200:
            raise ApiError(resp.status_code, resp.text)
        return resp.json()

    def get_vehicle_data(self, vin: str) -> dict[str, Any]:
        """Get latest vehicle data snapshot."""
        data = self._get(f"/api/1/vehicles/{vin}/vehicle_data")
        return data.get("response", data)

    def stream(self, vin: str) -> Generator[dict[str, Any], None, None]:
        """Yield real-time telemetry events via SSE.

        Yields dicts of telemetry key-value pairs as they arrive.
        The stream is long-lived; call this inside a loop and handle KeyboardInterrupt.
        """
        url = f"{TESLEMETRY_API}/api/1/vehicles/{vin}/streaming"
        headers = {"Authorization": f"Bearer {self._api_key}"}
        with httpx.stream("GET", url, headers=headers, timeout=None) as resp:
            if resp.status_code != 200:
                resp.read()
                raise ApiError(resp.status_code, resp.text)
            for line in resp.iter_lines():
                if line.startswith("data: "):
                    raw = line[6:].strip()
                    if not raw:
                        continue
                    try:
                        yield json.loads(raw)
                    except json.JSONDecodeError:
                        continue
