"""Self-hosted Fleet Telemetry backend.

Manages Tesla's fleet-telemetry server via Docker and configures
vehicle telemetry streaming via Fleet API.

No third-party services — vehicles stream directly to your server.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from tesla_cli.core.backends.fleet import FLEET_API_REGIONS
from tesla_cli.core.exceptions import ApiError


class FleetTelemetryBackend:
    """Self-hosted fleet telemetry management.

    Wraps the Fleet API telemetry config endpoints:
      POST   /api/1/vehicles/fleet_telemetry_config
      GET    /api/1/vehicles/{vin}/fleet_telemetry_config
      DELETE /api/1/vehicles/{vin}/fleet_telemetry_config
    """

    def __init__(self, access_token: str, region: str = "na") -> None:
        base_url = FLEET_API_REGIONS.get(region, FLEET_API_REGIONS["na"])
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )

    def configure_streaming(
        self,
        vin: str,
        hostname: str,
        port: int,
        ca_cert: str,
        fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Configure which telemetry fields a vehicle should stream.

        POST /api/1/vehicles/fleet_telemetry_config

        Args:
            vin: Vehicle VIN.
            hostname: FQDN of the fleet-telemetry server.
            port: Port the fleet-telemetry server listens on.
            ca_cert: PEM-encoded CA certificate string.
            fields: Dict of field names to stream config.
                    Defaults to a standard set of telemetry fields.

        Returns:
            API response dict.
        """
        if fields is None:
            fields = _default_fields()

        config = {
            "vins": [vin],
            "config": {
                "hostname": hostname,
                "port": port,
                "ca": ca_cert,
                "fields": fields,
                "alert_types": ["service"],
            },
        }
        resp = self._client.post("/api/1/vehicles/fleet_telemetry_config", json=config)
        if resp.status_code not in (200, 201):
            raise ApiError(resp.status_code, resp.text)
        return resp.json()

    def get_streaming_config(self, vin: str) -> dict[str, Any]:
        """Get current fleet telemetry config for a vehicle.

        GET /api/1/vehicles/{vin}/fleet_telemetry_config
        """
        resp = self._client.get(f"/api/1/vehicles/{vin}/fleet_telemetry_config")
        if resp.status_code != 200:
            raise ApiError(resp.status_code, resp.text)
        return resp.json()

    def delete_streaming_config(self, vin: str) -> dict[str, Any]:
        """Stop streaming for a vehicle.

        DELETE /api/1/vehicles/{vin}/fleet_telemetry_config
        """
        resp = self._client.delete(f"/api/1/vehicles/{vin}/fleet_telemetry_config")
        if resp.status_code not in (200, 204):
            raise ApiError(resp.status_code, resp.text)
        return resp.json() if resp.content else {}


def _default_fields() -> dict[str, Any]:
    """Return a default set of telemetry fields to stream."""
    field_names = [
        "BatteryLevel",
        "ChargeState",
        "ChargerPower",
        "VehicleSpeed",
        "Odometer",
        "Locked",
        "SentryMode",
        "Location",
        "InsideTemp",
        "OutsideTemp",
        "DCChargingEnergyIn",
        "ACChargingEnergyIn",
    ]
    return {name: {"interval_seconds": 10} for name in field_names}


def load_fleet_telemetry_backend() -> FleetTelemetryBackend:
    """Construct a FleetTelemetryBackend from config + keyring tokens.

    Raises ConfigurationError if Fleet auth tokens are not present.
    """
    from tesla_cli.core.auth.tokens import FLEET_ACCESS_TOKEN, get_token
    from tesla_cli.core.config import load_config
    from tesla_cli.core.exceptions import ConfigurationError

    cfg = load_config()
    access_token = get_token(FLEET_ACCESS_TOKEN)
    if not access_token:
        raise ConfigurationError("Fleet API access token not found.\nRun: tesla config auth fleet")
    return FleetTelemetryBackend(access_token, region=cfg.fleet.region)


def read_ca_cert(ca_cert_path: str) -> str:
    """Read CA certificate PEM from file path.

    Raises ConfigurationError if path is empty or file not found.
    """
    from tesla_cli.core.exceptions import ConfigurationError

    if not ca_cert_path:
        raise ConfigurationError(
            "CA certificate path not configured.\nRun: tesla telemetry install"
        )
    path = Path(ca_cert_path)
    if not path.exists():
        raise ConfigurationError(
            f"CA certificate not found: {ca_cert_path}\nRun: tesla telemetry install"
        )
    return path.read_text()
