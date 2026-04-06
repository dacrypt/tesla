"""Tesla Fleet API direct backend."""

from __future__ import annotations

from typing import Any

import httpx

from tesla_cli.core.backends.base import VehicleBackend
from tesla_cli.core.backends.http import HttpBackendMixin

FLEET_API_REGIONS = {
    "na": "https://fleet-api.prd.na.vn.cloud.tesla.com",
    "eu": "https://fleet-api.prd.eu.vn.cloud.tesla.com",
    "cn": "https://fleet-api.prd.cn.vn.cloud.tesla.cn",
}


class FleetBackend(HttpBackendMixin, VehicleBackend):
    """Vehicle backend using Tesla Fleet API directly."""

    _auth_error_message = "Fleet API token expired. Run: tesla config auth fleet"

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

    # ── Vehicle listing & data ──────────────────────────────────────

    def list_vehicles(self) -> list[dict[str, Any]]:
        return self._get("/api/1/vehicles")

    def get_vehicle_data(self, vin: str) -> dict[str, Any]:
        return self._get(
            f"/api/1/vehicles/{vin}/vehicle_data"
            "?endpoints=charge_state;climate_state;drive_state;location_data;"
            "vehicle_config;vehicle_state"
        )

    def get_charge_state(self, vin: str) -> dict[str, Any]:
        data = self._get(f"/api/1/vehicles/{vin}/vehicle_data?endpoints=charge_state")
        return data.get("charge_state", data)

    def get_climate_state(self, vin: str) -> dict[str, Any]:
        data = self._get(f"/api/1/vehicles/{vin}/vehicle_data?endpoints=climate_state")
        return data.get("climate_state", data)

    def get_drive_state(self, vin: str) -> dict[str, Any]:
        data = self._get(f"/api/1/vehicles/{vin}/vehicle_data?endpoints=drive_state;location_data")
        return data.get("drive_state", data)

    def get_vehicle_state(self, vin: str) -> dict[str, Any]:
        data = self._get(f"/api/1/vehicles/{vin}/vehicle_data?endpoints=vehicle_state")
        return data.get("vehicle_state", data)

    def get_vehicle_config(self, vin: str) -> dict[str, Any]:
        data = self._get(f"/api/1/vehicles/{vin}/vehicle_data?endpoints=vehicle_config")
        return data.get("vehicle_config", data)

    def mobile_enabled(self, vin: str) -> bool:
        data = self._get(f"/api/1/vehicles/{vin}/mobile_enabled")
        return bool(data) if not isinstance(data, dict) else data.get("result", False)

    # ── Safety / Telematics ─────────────────────────────────────────

    def get_safety_score(self, vin: str) -> dict[str, Any]:
        """Get Tesla Safety Score / Insurance telematics."""
        return self._get(f"/api/1/vehicles/{vin}/safety_score")

    def get_drive_score(self, vin: str) -> dict[str, Any]:
        """Get per-drive safety scoring breakdown."""
        return self._get(f"/api/1/vehicles/{vin}/drive_score")

    # ── Service ─────────────────────────────────────────────────────

    def get_service_visits(self, vin: str) -> list[dict[str, Any]]:
        """Get service visit history."""
        data = self._get(f"/api/1/vehicles/{vin}/service_data")
        return data if isinstance(data, list) else []

    def get_service_appointments(self) -> dict[str, Any]:
        """Get upcoming service appointments."""
        return self._get("/api/1/dx/service/appointments")

    # ── Location-based schedules ────────────────────────────────────

    def add_charge_schedule(
        self, vin: str, days: str, time: int, lat: float, lon: float, enabled: bool = True
    ) -> dict[str, Any]:
        """Add a location-based charging schedule."""
        return self._post(
            f"/api/1/vehicles/{vin}/command/add_charge_schedule",
            {
                "days_of_week": days,
                "start_time": time,
                "lat": lat,
                "lon": lon,
                "enabled": enabled,
            },
        )

    def remove_charge_schedule(self, vin: str, schedule_id: int) -> dict[str, Any]:
        """Remove a charging schedule by ID."""
        return self._post(
            f"/api/1/vehicles/{vin}/command/remove_charge_schedule", {"id": schedule_id}
        )

    def add_precondition_schedule(
        self, vin: str, days: str, time: int, lat: float, lon: float, enabled: bool = True
    ) -> dict[str, Any]:
        """Add a location-based preconditioning schedule."""
        return self._post(
            f"/api/1/vehicles/{vin}/command/add_precondition_schedule",
            {
                "days_of_week": days,
                "start_time": time,
                "lat": lat,
                "lon": lon,
                "enabled": enabled,
            },
        )

    def remove_precondition_schedule(self, vin: str, schedule_id: int) -> dict[str, Any]:
        """Remove a preconditioning schedule by ID."""
        return self._post(
            f"/api/1/vehicles/{vin}/command/remove_precondition_schedule", {"id": schedule_id}
        )

    # ── Data endpoints (Phase 2) ────────────────────────────────────

    def get_nearby_charging_sites(self, vin: str) -> dict[str, Any]:
        return self._get(f"/api/1/vehicles/{vin}/nearby_charging_sites")

    def get_release_notes(self, vin: str) -> dict[str, Any]:
        return self._get(f"/api/1/vehicles/{vin}/release_notes")

    def get_service_data(self, vin: str) -> dict[str, Any]:
        return self._get(f"/api/1/vehicles/{vin}/service_data")

    def get_recent_alerts(self, vin: str) -> dict[str, Any]:
        return self._get(f"/api/1/vehicles/{vin}/recent_alerts")

    def get_charge_history(self) -> dict[str, Any]:
        return self._post("/api/1/vehicles/charge_history")

    def get_fleet_status(self, vin: str) -> dict[str, Any]:
        return self._get(f"/api/1/vehicles/{vin}/fleet_status")

    # ── Vehicle sharing ─────────────────────────────────────────────

    def get_invitations(self, vin: str) -> list[dict[str, Any]]:
        data = self._get(f"/api/1/vehicles/{vin}/invitations")
        return data if isinstance(data, list) else []

    def create_invitation(self, vin: str) -> dict[str, Any]:
        return self._post(f"/api/1/vehicles/{vin}/invitations")

    def revoke_invitation(self, vin: str, invitation_id: str) -> dict[str, Any]:
        return self._post(f"/api/1/vehicles/{vin}/invitations/{invitation_id}/revoke")

    # ── Wake ────────────────────────────────────────────────────────

    def wake_up(self, vin: str) -> bool:
        data = self._post(f"/api/1/vehicles/{vin}/wake_up")
        return data.get("state") == "online"

    # ── Generic command dispatch ────────────────────────────────────

    def command(self, vin: str, command: str, **params: Any) -> dict[str, Any]:
        return self._post(f"/api/1/vehicles/{vin}/command/{command}", body=params or None)

    # ── Convenience command wrappers ────────────────────────────────
    # These all delegate to command() with the right name/params.

    # Doors
    def door_lock(self, vin: str) -> dict[str, Any]:
        return self.command(vin, "door_lock")

    def door_unlock(self, vin: str) -> dict[str, Any]:
        return self.command(vin, "door_unlock")

    # Charging
    def charge_start(self, vin: str) -> dict[str, Any]:
        return self.command(vin, "charge_start")

    def charge_stop(self, vin: str) -> dict[str, Any]:
        return self.command(vin, "charge_stop")

    def set_charge_limit(self, vin: str, percent: int) -> dict[str, Any]:
        return self.command(vin, "set_charge_limit", percent=percent)

    def set_charging_amps(self, vin: str, charging_amps: int) -> dict[str, Any]:
        return self.command(vin, "set_charging_amps", charging_amps=charging_amps)

    def charge_port_door_open(self, vin: str) -> dict[str, Any]:
        return self.command(vin, "charge_port_door_open")

    def charge_port_door_close(self, vin: str) -> dict[str, Any]:
        return self.command(vin, "charge_port_door_close")

    def set_scheduled_charging(self, vin: str, enable: bool, time_minutes: int) -> dict[str, Any]:
        return self.command(vin, "set_scheduled_charging", enable=enable, time=time_minutes)

    def set_scheduled_departure(
        self,
        vin: str,
        enable: bool,
        departure_time: int,
        preconditioning_enabled: bool = False,
        off_peak_charging_enabled: bool = False,
        end_off_peak_time: int = 0,
    ) -> dict[str, Any]:
        return self.command(
            vin,
            "set_scheduled_departure",
            enable=enable,
            departure_time=departure_time,
            preconditioning_enabled=preconditioning_enabled,
            off_peak_charging_enabled=off_peak_charging_enabled,
            end_off_peak_time=end_off_peak_time,
        )

    # Climate / HVAC
    def auto_conditioning_start(self, vin: str) -> dict[str, Any]:
        return self.command(vin, "auto_conditioning_start")

    def auto_conditioning_stop(self, vin: str) -> dict[str, Any]:
        return self.command(vin, "auto_conditioning_stop")

    def set_temps(self, vin: str, driver_temp: float, passenger_temp: float) -> dict[str, Any]:
        return self.command(
            vin,
            "set_temps",
            driver_temp=driver_temp,
            passenger_temp=passenger_temp,
        )

    def remote_seat_heater_request(self, vin: str, heater: int, level: int) -> dict[str, Any]:
        return self.command(vin, "remote_seat_heater_request", heater=heater, level=level)

    def remote_steering_wheel_heater_request(self, vin: str, on: bool) -> dict[str, Any]:
        return self.command(vin, "remote_steering_wheel_heater_request", on=on)

    def set_preconditioning_max(self, vin: str, on: bool) -> dict[str, Any]:
        return self.command(vin, "set_preconditioning_max", on=on)

    def set_bioweapon_mode(
        self, vin: str, on: bool, manual_override: bool = True
    ) -> dict[str, Any]:
        return self.command(vin, "set_bioweapon_mode", on=on, manual_override=manual_override)

    def set_climate_keeper_mode(self, vin: str, climate_keeper_mode: int) -> dict[str, Any]:
        """Set climate keeper: 0=off, 1=keep, 2=dog, 3=camp."""
        return self.command(vin, "set_climate_keeper_mode", climate_keeper_mode=climate_keeper_mode)

    def set_cabin_overheat_protection(
        self, vin: str, on: bool, fan_only: bool = False
    ) -> dict[str, Any]:
        return self.command(
            vin,
            "set_cop_temp",
            cop_temp=on,
            fan_only=fan_only,
        )

    # Windows
    def window_control(
        self, vin: str, command_action: str, lat: float = 0, lon: float = 0
    ) -> dict[str, Any]:
        """command_action: vent | close"""
        return self.command(vin, "window_control", command=command_action, lat=lat, lon=lon)

    # Trunk / Frunk
    def actuate_trunk(self, vin: str, which_trunk: str = "rear") -> dict[str, Any]:
        return self.command(vin, "actuate_trunk", which_trunk=which_trunk)

    # Horn / Lights
    def honk_horn(self, vin: str) -> dict[str, Any]:
        return self.command(vin, "honk_horn")

    def flash_lights(self, vin: str) -> dict[str, Any]:
        return self.command(vin, "flash_lights")

    # Sentry
    def set_sentry_mode(self, vin: str, on: bool) -> dict[str, Any]:
        return self.command(vin, "set_sentry_mode", on=on)

    # Valet
    def set_valet_mode(self, vin: str, on: bool, password: str = "") -> dict[str, Any]:
        params: dict[str, Any] = {"on": on}
        if password:
            params["password"] = password
        return self.command(vin, "set_valet_mode", **params)

    def reset_valet_pin(self, vin: str) -> dict[str, Any]:
        return self.command(vin, "reset_valet_pin")

    # Speed limit
    def speed_limit_activate(self, vin: str, pin: str) -> dict[str, Any]:
        return self.command(vin, "speed_limit_activate", pin=pin)

    def speed_limit_deactivate(self, vin: str, pin: str) -> dict[str, Any]:
        return self.command(vin, "speed_limit_deactivate", pin=pin)

    def speed_limit_set_limit(self, vin: str, limit_mph: int) -> dict[str, Any]:
        return self.command(vin, "speed_limit_set_limit", limit_mph=limit_mph)

    def speed_limit_clear_pin(self, vin: str, pin: str) -> dict[str, Any]:
        return self.command(vin, "speed_limit_clear_pin", pin=pin)

    # PIN to drive
    def set_pin_to_drive(self, vin: str, on: bool, password: str = "") -> dict[str, Any]:
        params: dict[str, Any] = {"on": on}
        if password:
            params["password"] = password
        return self.command(vin, "set_pin_to_drive", **params)

    # Guest mode
    def guest_mode(self, vin: str, enable: bool) -> dict[str, Any]:
        return self.command(vin, "guest_mode", enable=enable)

    # Remote start
    def remote_start_drive(self, vin: str) -> dict[str, Any]:
        return self.command(vin, "remote_start_drive")

    # Navigation
    def share(
        self,
        vin: str,
        value: str,
        locale: str = "en-US",
        timestamp_ms: int | None = None,
    ) -> dict[str, Any]:
        """Send an address/place to the vehicle nav."""
        import time as _time

        ts = timestamp_ms or int(_time.time() * 1000)
        return self.command(
            vin,
            "share",
            type="share_ext_content_raw",
            value={"android.intent.extra.TEXT": value},
            locale=locale,
            timestamp_ms=str(ts),
        )

    def navigation_sc_request(
        self, vin: str, id: int, order: int, offset: int = 0
    ) -> dict[str, Any]:
        """Navigate to a Supercharger."""
        return self.command(vin, "navigation_sc_request", id=id, order=order, offset=offset)

    def navigation_gps_request(
        self, vin: str, lat: float, lon: float, order: int = 0
    ) -> dict[str, Any]:
        return self.command(vin, "navigation_gps_request", lat=lat, lon=lon, order=order)

    # Media controls
    def media_toggle_playback(self, vin: str) -> dict[str, Any]:
        return self.command(vin, "media_toggle_playback")

    def media_next_track(self, vin: str) -> dict[str, Any]:
        return self.command(vin, "media_next_track")

    def media_prev_track(self, vin: str) -> dict[str, Any]:
        return self.command(vin, "media_prev_track")

    def media_next_fav(self, vin: str) -> dict[str, Any]:
        return self.command(vin, "media_next_fav")

    def media_prev_fav(self, vin: str) -> dict[str, Any]:
        return self.command(vin, "media_prev_fav")

    def media_volume_up(self, vin: str) -> dict[str, Any]:
        return self.command(vin, "media_volume_up")

    def media_volume_down(self, vin: str) -> dict[str, Any]:
        return self.command(vin, "media_volume_down")

    def adjust_volume(self, vin: str, volume: float) -> dict[str, Any]:
        """Set absolute volume (0.0 – 11.0)."""
        return self.command(vin, "adjust_volume", volume=volume)

    # Software updates
    def schedule_software_update(self, vin: str, offset_sec: int = 0) -> dict[str, Any]:
        return self.command(vin, "schedule_software_update", offset_sec=offset_sec)

    def cancel_software_update(self, vin: str) -> dict[str, Any]:
        return self.command(vin, "cancel_software_update")

    # HomeLink
    def trigger_homelink(self, vin: str, lat: float, lon: float) -> dict[str, Any]:
        return self.command(vin, "trigger_homelink", lat=lat, lon=lon)

    # Boombox
    def remote_boombox(self, vin: str) -> dict[str, Any]:
        return self.command(vin, "remote_boombox")

    # Defrost
    def set_preconditioning_max(self, vin: str, on: bool) -> dict[str, Any]:  # noqa: F811 – intentional override
        return self.command(vin, "set_preconditioning_max", on=on)
