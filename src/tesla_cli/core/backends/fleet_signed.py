"""Fleet API backend with signed vehicle commands.

Uses tesla-fleet-api library for end-to-end encrypted commands.
Required for 2024.26+ firmware that rejects unsigned commands.

Install: uv pip install 'tesla-cli[fleet]'
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from tesla_cli.core.auth import tokens
from tesla_cli.core.backends.base import VehicleBackend
from tesla_cli.core.config import load_config

log = logging.getLogger(__name__)

# Command name → (method_name, positional_args_from_params, keyword_args_from_params)
# Each entry: (method_name, [param_keys_as_positional], [param_keys_as_keyword])
_COMMAND_MAP: dict[str, tuple[str, list[str], list[str]]] = {
    "door_lock": ("door_lock", [], []),
    "door_unlock": ("door_unlock", [], []),
    "charge_start": ("charge_start", [], []),
    "charge_stop": ("charge_stop", [], []),
    "set_charge_limit": ("set_charge_limit", ["percent"], []),
    "set_charging_amps": ("set_charging_amps", ["charging_amps"], []),
    "charge_port_door_open": ("charge_port_door_open", [], []),
    "charge_port_door_close": ("charge_port_door_close", [], []),
    "flash_lights": ("flash_lights", [], []),
    "honk_horn": ("honk_horn", [], []),
    "actuate_trunk": ("actuate_trunk", [], ["which_trunk"]),
    "remote_start_drive": ("remote_start_drive", [], []),
    "auto_conditioning_start": ("auto_conditioning_start", [], []),
    "auto_conditioning_stop": ("auto_conditioning_stop", [], []),
    "set_temps": ("set_temps", ["driver_temp", "passenger_temp"], []),
    "remote_seat_heater_request": ("remote_seat_heater_request", ["heater", "level"], []),
    "remote_steering_wheel_heater_request": (
        "remote_steering_wheel_heater_request",
        ["on"],
        [],
    ),
    "set_preconditioning_max": ("set_preconditioning_max", ["on"], []),
    "set_bioweapon_mode": ("set_bioweapon_mode", ["on"], ["manual_override"]),
    "set_climate_keeper_mode": ("set_climate_keeper_mode", ["climate_keeper_mode"], []),
    "set_cop_temp": ("set_cabin_overheat_protection", [], ["cop_temp", "fan_only"]),
    "window_control": ("window_control", [], ["command", "lat", "lon"]),
    "set_sentry_mode": ("set_sentry_mode", ["on"], []),
    "set_valet_mode": ("set_valet_mode", ["on"], ["password"]),
    "reset_valet_pin": ("reset_valet_pin", [], []),
    "speed_limit_activate": ("speed_limit_activate", ["pin"], []),
    "speed_limit_deactivate": ("speed_limit_deactivate", ["pin"], []),
    "speed_limit_set_limit": ("speed_limit_set_limit", ["limit_mph"], []),
    "speed_limit_clear_pin": ("speed_limit_clear_pin", ["pin"], []),
    "set_pin_to_drive": ("set_pin_to_drive", ["on"], ["password"]),
    "guest_mode": ("guest_mode", ["enable"], []),
    "schedule_software_update": ("schedule_software_update", [], ["offset_sec"]),
    "cancel_software_update": ("cancel_software_update", [], []),
    "trigger_homelink": ("trigger_homelink", ["lat", "lon"], []),
    "media_toggle_playback": ("media_toggle_playback", [], []),
    "media_next_track": ("media_next_track", [], []),
    "media_prev_track": ("media_prev_track", [], []),
    "media_next_fav": ("media_next_fav", [], []),
    "media_prev_fav": ("media_prev_fav", [], []),
    "media_volume_up": ("media_volume_up", [], []),
    "media_volume_down": ("media_volume_down", [], []),
    "adjust_volume": ("adjust_volume", ["volume"], []),
    "share": ("share", [], ["type", "value", "locale", "timestamp_ms"]),
    "navigation_sc_request": ("navigation_sc_request", ["id", "order"], ["offset"]),
    "navigation_gps_request": ("navigation_gps_request", ["lat", "lon"], ["order"]),
    "remote_boombox": ("remote_boombox", [], []),
}


def _require_fleet_api() -> None:
    """Raise a clear error if tesla-fleet-api is not installed."""
    try:
        import aiohttp  # noqa: F401
        import tesla_fleet_api  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "tesla-fleet-api is required for signed commands. "
            "Install: uv pip install 'tesla-cli[fleet]'"
        ) from exc


class FleetSignedBackend(VehicleBackend):
    """Vehicle backend using Tesla Fleet API with signed (end-to-end encrypted) commands.

    Data endpoints (reads) are delegated to the regular FleetBackend.
    Command endpoints use VehicleSigned for firmware 2024.26+ compatibility.
    """

    def __init__(self) -> None:
        _require_fleet_api()
        self._loop: asyncio.AbstractEventLoop | None = None
        # VIN → VehicleSigned instance (after handshake)
        self._vehicles: dict[str, Any] = {}
        # Lazy-initialised regular backend for data reads
        self._read_backend: Any = None

    # ── Event loop management ────────────────────────────────────────────────

    def _run(self, coro: Any) -> Any:
        """Run an async coroutine synchronously on a dedicated event loop."""
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
        return self._loop.run_until_complete(coro)

    # ── Read backend (unsigned Fleet API for data endpoints) ─────────────────

    @property
    def _reads(self) -> Any:
        """Return the regular FleetBackend used for data reads."""
        if self._read_backend is None:
            from tesla_cli.core.auth.tokens import FLEET_ACCESS_TOKEN, get_token
            from tesla_cli.core.backends.fleet import FleetBackend
            from tesla_cli.core.exceptions import AuthenticationError

            token = get_token(FLEET_ACCESS_TOKEN)
            if not token:
                raise AuthenticationError("No Fleet API token. Run: tesla config auth fleet")
            cfg = load_config()
            self._read_backend = FleetBackend(access_token=token, region=cfg.fleet.region)
        return self._read_backend

    # ── Signed vehicle accessor ──────────────────────────────────────────────

    async def _get_vehicle(self, vin: str) -> Any:
        """Return a VehicleSigned instance for *vin*, performing handshake on first use."""
        import aiohttp
        from tesla_fleet_api import TeslaFleetApi
        from tesla_fleet_api.tesla.vehicle.signed import VehicleSigned

        if vin not in self._vehicles:
            cfg = load_config()
            access_token = tokens.get_token(tokens.FLEET_ACCESS_TOKEN)
            if not access_token:
                from tesla_cli.core.exceptions import AuthenticationError

                raise AuthenticationError("No Fleet API token. Run: tesla config auth fleet")

            session = aiohttp.ClientSession()
            api = TeslaFleetApi(
                access_token=access_token,
                session=session,
                region=cfg.fleet.region,
            )
            vehicle = VehicleSigned(api, vin)
            log.debug("Performing signed handshake for VIN %s", vin)
            await vehicle.handshake()
            log.debug("Handshake complete for VIN %s", vin)
            self._vehicles[vin] = vehicle

        return self._vehicles[vin]

    # ── VehicleBackend — data methods (delegate to unsigned FleetBackend) ────

    def list_vehicles(self) -> list[dict[str, Any]]:
        return self._reads.list_vehicles()

    def get_vehicle_data(self, vin: str) -> dict[str, Any]:
        return self._reads.get_vehicle_data(vin)

    def get_charge_state(self, vin: str) -> dict[str, Any]:
        return self._reads.get_charge_state(vin)

    def get_climate_state(self, vin: str) -> dict[str, Any]:
        return self._reads.get_climate_state(vin)

    def get_drive_state(self, vin: str) -> dict[str, Any]:
        return self._reads.get_drive_state(vin)

    def get_vehicle_state(self, vin: str) -> dict[str, Any]:
        return self._reads.get_vehicle_state(vin)

    def get_vehicle_config(self, vin: str) -> dict[str, Any]:
        return self._reads.get_vehicle_config(vin)

    def mobile_enabled(self, vin: str) -> bool:
        return self._reads.mobile_enabled(vin)

    def get_nearby_charging_sites(self, vin: str) -> dict[str, Any]:
        return self._reads.get_nearby_charging_sites(vin)

    def get_release_notes(self, vin: str) -> dict[str, Any]:
        return self._reads.get_release_notes(vin)

    def get_service_data(self, vin: str) -> dict[str, Any]:
        return self._reads.get_service_data(vin)

    def get_recent_alerts(self, vin: str) -> dict[str, Any]:
        return self._reads.get_recent_alerts(vin)

    def get_charge_history(self) -> dict[str, Any]:
        return self._reads.get_charge_history()

    def get_fleet_status(self, vin: str) -> dict[str, Any]:
        return self._reads.get_fleet_status(vin)

    def get_invitations(self, vin: str) -> list[dict[str, Any]]:
        return self._reads.get_invitations(vin)

    def create_invitation(self, vin: str) -> dict[str, Any]:
        return self._reads.create_invitation(vin)

    def revoke_invitation(self, vin: str, invitation_id: str) -> dict[str, Any]:
        return self._reads.revoke_invitation(vin, invitation_id)

    # ── VehicleBackend — command methods (signed) ────────────────────────────

    def wake_up(self, vin: str) -> bool:
        async def _wake() -> bool:
            vehicle = await self._get_vehicle(vin)
            data = await vehicle.wake_up()
            if isinstance(data, dict):
                return data.get("state") == "online"
            return False

        return self._run(_wake())

    def command(self, vin: str, command: str, **params: Any) -> dict[str, Any]:
        """Dispatch a named command to VehicleSigned, using _COMMAND_MAP for routing."""
        if command not in _COMMAND_MAP:
            # Fall back to unsigned Fleet API for unmapped commands
            log.warning(
                "Command '%s' not in signed command map — falling back to unsigned Fleet API",
                command,
            )
            return self._reads.command(vin, command, **params)

        method_name, positional_keys, keyword_keys = _COMMAND_MAP[command]

        async def _dispatch() -> dict[str, Any]:
            vehicle = await self._get_vehicle(vin)
            method = getattr(vehicle, method_name, None)
            if method is None:
                raise RuntimeError(
                    f"VehicleSigned has no method '{method_name}' for command '{command}'"
                )
            args = [params[k] for k in positional_keys if k in params]
            kwargs = {k: params[k] for k in keyword_keys if k in params}
            result = await method(*args, **kwargs)
            if isinstance(result, dict):
                return result
            return {"result": result}

        return self._run(_dispatch())

    # ── Convenience command wrappers (mirror FleetBackend API) ───────────────

    def door_lock(self, vin: str) -> dict[str, Any]:
        return self.command(vin, "door_lock")

    def door_unlock(self, vin: str) -> dict[str, Any]:
        return self.command(vin, "door_unlock")

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

    def auto_conditioning_start(self, vin: str) -> dict[str, Any]:
        return self.command(vin, "auto_conditioning_start")

    def auto_conditioning_stop(self, vin: str) -> dict[str, Any]:
        return self.command(vin, "auto_conditioning_stop")

    def set_temps(self, vin: str, driver_temp: float, passenger_temp: float) -> dict[str, Any]:
        return self.command(
            vin, "set_temps", driver_temp=driver_temp, passenger_temp=passenger_temp
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
        return self.command(vin, "set_climate_keeper_mode", climate_keeper_mode=climate_keeper_mode)

    def set_cabin_overheat_protection(
        self, vin: str, on: bool, fan_only: bool = False
    ) -> dict[str, Any]:
        return self.command(vin, "set_cop_temp", cop_temp=on, fan_only=fan_only)

    def window_control(
        self, vin: str, command_action: str, lat: float = 0, lon: float = 0
    ) -> dict[str, Any]:
        return self.command(vin, "window_control", command=command_action, lat=lat, lon=lon)

    def actuate_trunk(self, vin: str, which_trunk: str = "rear") -> dict[str, Any]:
        return self.command(vin, "actuate_trunk", which_trunk=which_trunk)

    def honk_horn(self, vin: str) -> dict[str, Any]:
        return self.command(vin, "honk_horn")

    def flash_lights(self, vin: str) -> dict[str, Any]:
        return self.command(vin, "flash_lights")

    def set_sentry_mode(self, vin: str, on: bool) -> dict[str, Any]:
        return self.command(vin, "set_sentry_mode", on=on)

    def set_valet_mode(self, vin: str, on: bool, password: str = "") -> dict[str, Any]:
        params: dict[str, Any] = {"on": on}
        if password:
            params["password"] = password
        return self.command(vin, "set_valet_mode", **params)

    def reset_valet_pin(self, vin: str) -> dict[str, Any]:
        return self.command(vin, "reset_valet_pin")

    def speed_limit_activate(self, vin: str, pin: str) -> dict[str, Any]:
        return self.command(vin, "speed_limit_activate", pin=pin)

    def speed_limit_deactivate(self, vin: str, pin: str) -> dict[str, Any]:
        return self.command(vin, "speed_limit_deactivate", pin=pin)

    def speed_limit_set_limit(self, vin: str, limit_mph: int) -> dict[str, Any]:
        return self.command(vin, "speed_limit_set_limit", limit_mph=limit_mph)

    def speed_limit_clear_pin(self, vin: str, pin: str) -> dict[str, Any]:
        return self.command(vin, "speed_limit_clear_pin", pin=pin)

    def set_pin_to_drive(self, vin: str, on: bool, password: str = "") -> dict[str, Any]:
        params: dict[str, Any] = {"on": on}
        if password:
            params["password"] = password
        return self.command(vin, "set_pin_to_drive", **params)

    def guest_mode(self, vin: str, enable: bool) -> dict[str, Any]:
        return self.command(vin, "guest_mode", enable=enable)

    def remote_start_drive(self, vin: str) -> dict[str, Any]:
        return self.command(vin, "remote_start_drive")

    def share(
        self,
        vin: str,
        value: str,
        locale: str = "en-US",
        timestamp_ms: int | None = None,
    ) -> dict[str, Any]:
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
        return self.command(vin, "navigation_sc_request", id=id, order=order, offset=offset)

    def navigation_gps_request(
        self, vin: str, lat: float, lon: float, order: int = 0
    ) -> dict[str, Any]:
        return self.command(vin, "navigation_gps_request", lat=lat, lon=lon, order=order)

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
        return self.command(vin, "adjust_volume", volume=volume)

    def schedule_software_update(self, vin: str, offset_sec: int = 0) -> dict[str, Any]:
        return self.command(vin, "schedule_software_update", offset_sec=offset_sec)

    def cancel_software_update(self, vin: str) -> dict[str, Any]:
        return self.command(vin, "cancel_software_update")

    def trigger_homelink(self, vin: str, lat: float, lon: float) -> dict[str, Any]:
        return self.command(vin, "trigger_homelink", lat=lat, lon=lon)

    def remote_boombox(self, vin: str) -> dict[str, Any]:
        return self.command(vin, "remote_boombox")

    def set_scheduled_charging(self, vin: str, enable: bool, time_minutes: int) -> dict[str, Any]:
        return self._reads.set_scheduled_charging(vin, enable, time_minutes)

    def set_scheduled_departure(
        self,
        vin: str,
        enable: bool,
        departure_time: int,
        preconditioning_enabled: bool = False,
        off_peak_charging_enabled: bool = False,
        end_off_peak_time: int = 0,
    ) -> dict[str, Any]:
        return self._reads.set_scheduled_departure(
            vin,
            enable,
            departure_time,
            preconditioning_enabled,
            off_peak_charging_enabled,
            end_off_peak_time,
        )
