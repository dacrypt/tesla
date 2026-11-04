"""Which raw vehicle commands the generic ``POST /api/vehicle/command`` may send.

The endpoint forwards a command *name* into the backend URL
(``/api/1/vehicles/{vin}/command/{cmd}``). Without a policy any caller could
send account-altering commands (erase user data, change PIN-to-drive, schedule
a software install) or smuggle path segments into the upstream URL.

The default allowlist covers everyday controls exposed by the dashboard.
Owners who need more can add names via ``server.extra_allowed_commands``.
"""

from __future__ import annotations

import re

DEFAULT_ALLOWED_COMMANDS: frozenset[str] = frozenset(
    {
        # Wake / locks / alerts
        "wake_up",
        "door_lock",
        "door_unlock",
        "honk_horn",
        "flash_lights",
        "remote_start_drive",
        # Trunks / windows / roof / homelink
        "actuate_trunk",
        "window_control",
        "sun_roof_control",
        "trigger_homelink",
        # Charging
        "charge_start",
        "charge_stop",
        "charge_standard",
        "charge_max_range",
        "charge_port_door_open",
        "charge_port_door_close",
        "set_charge_limit",
        "set_charging_amps",
        "set_scheduled_charging",
        "set_scheduled_departure",
        "add_charge_schedule",
        "remove_charge_schedule",
        "add_precondition_schedule",
        "remove_precondition_schedule",
        # Climate
        "auto_conditioning_start",
        "auto_conditioning_stop",
        "set_temps",
        "set_preconditioning_max",
        "set_bioweapon_mode",
        "set_climate_keeper_mode",
        "set_cabin_overheat_protection",
        "set_cop_temp",
        "remote_seat_heater_request",
        "remote_seat_cooler_request",
        "remote_auto_seat_climate_request",
        "remote_steering_wheel_heater_request",
        "remote_steering_wheel_heat_level_request",
        "remote_auto_steering_wheel_heat_climate_request",
        # Security modes
        "set_sentry_mode",
        "set_valet_mode",
        "guest_mode",
        "speed_limit_activate",
        "speed_limit_deactivate",
        "speed_limit_set_limit",
        # Media / navigation
        "media_toggle_playback",
        "media_next_track",
        "media_prev_track",
        "media_next_fav",
        "media_prev_fav",
        "media_volume_down",
        "adjust_volume",
        "share",
        "navigation_request",
        "navigation_gps_request",
        "navigation_sc_request",
        "remote_boombox",
    }
)

# Deliberately excluded (enable explicitly if you really need them):
#   erase_user_data, set_pin_to_drive, reset_pin_to_drive_pin,
#   clear_pin_to_drive_admin, reset_valet_pin, speed_limit_clear_pin,
#   speed_limit_clear_pin_admin, schedule_software_update,
#   cancel_software_update, set_vehicle_name

_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def is_command_allowed(command: str, extra_allowed: list[str] | None = None) -> bool:
    """Return True if *command* may be forwarded to the vehicle backend."""
    if not _NAME_RE.fullmatch(command):
        return False
    return command in DEFAULT_ALLOWED_COMMANDS or command in set(extra_allowed or [])
