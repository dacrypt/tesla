"""Tesla Energy (Powerwall/Solar) backend via Fleet API."""

from __future__ import annotations

from typing import Any

import httpx

from tesla_cli.core.backends.fleet import FLEET_API_REGIONS
from tesla_cli.core.exceptions import ApiError, AuthenticationError


class EnergyBackend:
    """Query and control Tesla energy products (Powerwall, Solar)."""

    def __init__(self, access_token: str, region: str = "na") -> None:
        base_url = FLEET_API_REGIONS.get(region, FLEET_API_REGIONS["na"])
        self._client = httpx.Client(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )

    def _get(self, path: str, **params: Any) -> dict[str, Any]:
        resp = self._client.get(path, params=params or None)
        if resp.status_code == 401:
            raise AuthenticationError("Fleet API token expired. Run: tesla config auth fleet")
        if resp.status_code != 200:
            raise ApiError(resp.status_code, resp.text)
        data = resp.json()
        return data.get("response", data) if isinstance(data, dict) else data

    def _post(self, path: str, body: dict | None = None) -> dict[str, Any]:
        resp = self._client.post(path, json=body or {})
        if resp.status_code == 401:
            raise AuthenticationError("Fleet API token expired. Run: tesla config auth fleet")
        if resp.status_code != 200:
            raise ApiError(resp.status_code, resp.text)
        data = resp.json()
        return data.get("response", data) if isinstance(data, dict) else data

    # ── Site discovery ──────────────────────────────────────────────

    def list_energy_sites(self) -> list[dict[str, Any]]:
        """Return all energy sites from /api/1/products (items with energy_site_id)."""
        data = self._get("/api/1/products")
        products = data if isinstance(data, list) else data.get("response", [])
        return [p for p in products if "energy_site_id" in p]

    # ── Site data ───────────────────────────────────────────────────

    def get_site_info(self, site_id: int) -> dict[str, Any]:
        """GET /api/1/energy_sites/{id}/site_info — site config, assets, features."""
        return self._get(f"/api/1/energy_sites/{site_id}/site_info")

    def live_status(self, site_id: int) -> dict[str, Any]:
        """GET /api/1/energy_sites/{id}/live_status — real-time power/battery/grid."""
        return self._get(f"/api/1/energy_sites/{site_id}/live_status")

    def energy_history(
        self,
        site_id: int,
        period: str = "day",
        start: str = "",
        end: str = "",
    ) -> dict[str, Any]:
        """GET /api/1/energy_sites/{id}/calendar_history?kind=energy."""
        params: dict[str, Any] = {"kind": "energy", "period": period}
        if start:
            params["start_date"] = start
        if end:
            params["end_date"] = end
        return self._get(f"/api/1/energy_sites/{site_id}/calendar_history", **params)

    def backup_history(
        self,
        site_id: int,
        period: str = "day",
    ) -> dict[str, Any]:
        """GET /api/1/energy_sites/{id}/calendar_history?kind=backup."""
        return self._get(
            f"/api/1/energy_sites/{site_id}/calendar_history",
            kind="backup",
            period=period,
        )

    # ── Site control ────────────────────────────────────────────────

    def set_backup_reserve(self, site_id: int, percent: int) -> dict[str, Any]:
        """POST /api/1/energy_sites/{id}/backup — set backup reserve %."""
        return self._post(f"/api/1/energy_sites/{site_id}/backup", {"backup_reserve_percent": percent})

    def set_operation_mode(self, site_id: int, mode: str) -> dict[str, Any]:
        """POST /api/1/energy_sites/{id}/operation — set mode.

        Modes: self_consumption | autonomous | backup
        """
        return self._post(f"/api/1/energy_sites/{site_id}/operation", {"default_real_mode": mode})

    def set_storm_mode(self, site_id: int, enabled: bool) -> dict[str, Any]:
        """POST /api/1/energy_sites/{id}/storm_mode — toggle storm watch."""
        return self._post(
            f"/api/1/energy_sites/{site_id}/storm_mode", {"enabled": enabled}
        )


def load_energy_backend() -> EnergyBackend:
    """Construct an EnergyBackend from config + keyring tokens.

    Raises ConfigurationError if Fleet auth tokens are not present.
    """
    from tesla_cli.core.auth.tokens import FLEET_ACCESS_TOKEN, get_token
    from tesla_cli.core.config import load_config
    from tesla_cli.core.exceptions import ConfigurationError

    cfg = load_config()
    access_token = get_token(FLEET_ACCESS_TOKEN)
    if not access_token:
        raise ConfigurationError(
            "Fleet API access token not found.\n"
            "Run: tesla config auth fleet"
        )
    return EnergyBackend(access_token, region=cfg.fleet.region)
