"""Feature health probes — classify each feature as ok / missing-scope / external-blocker / not-configured.

This module is OFFLINE-SAFE: it only inspects the local token payload and the
user's config. It does NOT make HTTP calls to Tesla and does NOT wake the car.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FeatureSpec:
    name: str  # stable id, e.g. "flash_lights"
    tier: str  # "T0" | "T2" | "T3" | "T4"
    backend: str  # "fleet" | "fleet-signed" | "external"
    required_scope: str | None  # e.g. "vehicle_cmds", or None
    required_config: str | None  # e.g. "teslaMate.database_url"
    description: str  # one-line human text


# ── Seed list (22 entries, see plan §3.1) ─────────────────────────────────────

FEATURES: list[FeatureSpec] = [
    FeatureSpec("vehicle_list", "T0", "fleet", None, None, "List vehicles on the account"),
    FeatureSpec(
        "vehicle_data", "T0", "fleet", "vehicle_device_data", None, "Full vehicle state snapshot"
    ),
    FeatureSpec(
        "vehicle_location",
        "T3",
        "fleet",
        "vehicle_location",
        None,
        "Live GPS location + heading",
    ),
    FeatureSpec(
        "charge_history",
        "T0",
        "fleet",
        "vehicle_charging_cmds",
        None,
        "Historical charge session list",
    ),
    FeatureSpec(
        "charge_invoices",
        "T0",
        "fleet",
        "vehicle_charging_cmds",
        None,
        "Supercharger invoice PDFs",
    ),
    FeatureSpec("flash_lights", "T2", "fleet-signed", "vehicle_cmds", None, "Flash headlights"),
    FeatureSpec("honk_horn", "T2", "fleet-signed", "vehicle_cmds", None, "Honk the horn"),
    FeatureSpec("door_lock", "T2", "fleet-signed", "vehicle_cmds", None, "Lock the doors"),
    FeatureSpec("door_unlock", "T2", "fleet-signed", "vehicle_cmds", None, "Unlock the doors"),
    FeatureSpec("sentry_mode", "T2", "fleet-signed", "vehicle_cmds", None, "Toggle Sentry Mode"),
    FeatureSpec(
        "actuate_trunk", "T2", "fleet-signed", "vehicle_cmds", None, "Open front/rear trunk"
    ),
    FeatureSpec("window_control", "T2", "fleet-signed", "vehicle_cmds", None, "Vent/close windows"),
    FeatureSpec(
        "climate_start", "T2", "fleet-signed", "vehicle_cmds", None, "Start preconditioning"
    ),
    FeatureSpec(
        "charge_start",
        "T2",
        "fleet-signed",
        "vehicle_charging_cmds",
        None,
        "Start charging session",
    ),
    FeatureSpec(
        "charge_stop",
        "T2",
        "fleet-signed",
        "vehicle_charging_cmds",
        None,
        "Stop charging session",
    ),
    FeatureSpec(
        "set_charge_limit",
        "T2",
        "fleet-signed",
        "vehicle_charging_cmds",
        None,
        "Set target SoC",
    ),
    FeatureSpec("safety_score", "T3", "fleet", "user_data", None, "Tesla safety score"),
    FeatureSpec(
        "energy_status",
        "T3",
        "fleet",
        "energy_device_data",
        None,
        "Powerwall/Solar energy site status",
    ),
    FeatureSpec(
        "teslamate", "T4", "external", None, "teslaMate.database_url", "TeslaMate analytics DB"
    ),
    FeatureSpec("mqtt", "T4", "external", None, "mqtt.broker", "MQTT telemetry publisher"),
    FeatureSpec(
        "home_assistant",
        "T4",
        "external",
        None,
        "home_assistant.url",
        "Home Assistant integration",
    ),
    FeatureSpec("abrp", "T4", "external", None, "abrp.user_token", "A Better Route Planner"),
]


# ── Setup commands for T4 external integrations ──────────────────────────────

_T4_SETUP_COMMANDS: dict[str, str] = {
    "teslamate": "make teslaMate-up",
    "mqtt": "tesla mqtt setup",
    "home_assistant": "tesla ha setup",
    "abrp": "tesla abrp setup",
}


# ── Helpers ───────────────────────────────────────────────────────────────────


def _decode_token_scopes(token: str | None) -> list[str]:
    """Extract the `scp` claim from a JWT access token. Returns [] on any error."""
    if not token:
        return []
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return []
        payload_b64 = parts[1]
        # Pad for urlsafe_b64decode
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload_bytes = base64.urlsafe_b64decode(padded)
        payload = json.loads(payload_bytes)
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return []
    scp = payload.get("scp")
    if isinstance(scp, list):
        return [str(s) for s in scp]
    if isinstance(scp, str):
        return scp.split()
    return []


def _get_config_attr(cfg: Any, dotted_path: str) -> Any:
    """Resolve a dotted path like 'teslaMate.database_url' on the config object."""
    cur: Any = cfg
    for part in dotted_path.split("."):
        cur = getattr(cur, part, None)
        if cur is None:
            return None
    return cur


# ── Probe ─────────────────────────────────────────────────────────────────────


def _load_scopes_safe() -> list[str]:
    """Read the Fleet access token's scopes. Return [] on any failure.

    Swallows keyring errors (e.g. `NoKeyringError` on CI where no backend
    exists) and config-load errors so `tesla doctor` / `/api/doctor` stays
    usable in fresh/minimal environments.
    """
    try:
        from tesla_cli.core.auth.tokens import FLEET_ACCESS_TOKEN, get_token

        return _decode_token_scopes(get_token(FLEET_ACCESS_TOKEN))
    except Exception:
        return []


def probe(feature: FeatureSpec, *, cfg: Any = None, token_scopes: list[str] | None = None) -> dict:
    """Classify one feature's availability — pure function, no I/O.

    If `cfg` or `token_scopes` are not supplied, load them from the user's
    config / keyring. This makes the function convenient for ad-hoc calls
    while still allowing tests to inject fully mocked inputs.
    """
    if cfg is None:
        from tesla_cli.core.config import load_config

        try:
            cfg = load_config()
        except Exception:
            # Fresh env / corrupt config: treat as "nothing configured" so T4
            # rows report `not-configured` instead of blowing up the probe.
            from tesla_cli.core.config import Config

            cfg = Config()
    if token_scopes is None:
        token_scopes = _load_scopes_safe()

    name = feature.name
    tier = feature.tier
    status = "ok"
    remediation: str | None = None

    if tier == "T0":
        if feature.required_scope and feature.required_scope not in token_scopes:
            status = "missing-scope"
            remediation = (
                f"Add scope '{feature.required_scope}' in developer.tesla.com "
                "and re-auth: tesla config auth fleet"
            )
    elif tier == "T2":
        current_backend = getattr(cfg.general, "backend", "")
        if current_backend != "fleet-signed":
            status = "external-blocker"
            remediation = "Run: tesla config auth fleet-signed (then pair in Tesla app)"
    elif tier == "T3":
        if feature.required_scope and feature.required_scope not in token_scopes:
            status = "missing-scope"
            remediation = (
                f"Scope '{feature.required_scope}' missing — add in developer.tesla.com; "
                "may take up to 24h to propagate"
            )
    elif tier == "T4":
        configured = False
        if feature.required_config:
            val = _get_config_attr(cfg, feature.required_config)
            configured = bool(val)
        if not configured:
            status = "not-configured"
            setup = _T4_SETUP_COMMANDS.get(name, f"tesla {name} setup")
            remediation = f"Run: {setup}"

    result: dict = {
        "name": name,
        "tier": tier,
        "status": status,
    }
    if remediation:
        result["remediation"] = remediation
    return result


def probe_all(*, cfg: Any = None, token_scopes: list[str] | None = None) -> list[dict]:
    """Probe every feature in FEATURES. Returns a JSON-serializable list."""
    if cfg is None:
        from tesla_cli.core.config import load_config

        try:
            cfg = load_config()
        except Exception:
            from tesla_cli.core.config import Config

            cfg = Config()
    if token_scopes is None:
        token_scopes = _load_scopes_safe()
    return [probe(f, cfg=cfg, token_scopes=token_scopes) for f in FEATURES]
