"""Configuration validation shared by `tesla config validate` and the REST API."""

from __future__ import annotations

from tesla_cli.core.config import Config


def run_config_checks(cfg: Config) -> list[dict]:
    """Run all config validation checks and return list of {field, status, message}."""
    import string

    checks: list[dict] = []

    def _ok(field: str, msg: str) -> None:
        checks.append({"field": field, "status": "ok", "message": msg})

    def _warn(field: str, msg: str) -> None:
        checks.append({"field": field, "status": "warn", "message": msg})

    def _err(field: str, msg: str) -> None:
        checks.append({"field": field, "status": "error", "message": msg})

    valid_backends = {"fleet", "fleet-signed", "tessie", "owner"}
    if cfg.general.default_vin:
        _ok("general.default_vin", f"Set: {cfg.general.default_vin}")
    else:
        _warn("general.default_vin", "Not set — most vehicle commands will fail")

    if cfg.general.backend in valid_backends:
        _ok("general.backend", f"Valid: {cfg.general.backend}")
    else:
        _err(
            "general.backend",
            f"Unknown backend '{cfg.general.backend}' — must be one of: {', '.join(sorted(valid_backends))}",
        )

    if 0.0 <= cfg.general.cost_per_kwh <= 5.0:
        _ok("general.cost_per_kwh", str(cfg.general.cost_per_kwh))
    else:
        _warn(
            "general.cost_per_kwh", f"Unusual value {cfg.general.cost_per_kwh} — expected 0.0–5.0"
        )

    if cfg.mqtt.broker:
        if not 1 <= cfg.mqtt.port <= 65535:
            _err("mqtt.port", f"Port {cfg.mqtt.port} out of range (1–65535)")
        else:
            _ok("mqtt.port", str(cfg.mqtt.port))
        if cfg.mqtt.qos not in (0, 1, 2):
            _err("mqtt.qos", f"QoS {cfg.mqtt.qos} invalid — must be 0, 1, or 2")
        else:
            _ok("mqtt.qos", str(cfg.mqtt.qos))
    else:
        _ok("mqtt", "Not configured (optional)")

    if cfg.home_assistant.url:
        if cfg.home_assistant.url.startswith(("http://", "https://")):
            _ok("home_assistant.url", cfg.home_assistant.url)
        else:
            _err("home_assistant.url", "Must start with http:// or https://")

    if cfg.teslaMate.database_url:
        if cfg.teslaMate.database_url.startswith("postgresql"):
            _ok("teslaMate.database_url", "Valid PostgreSQL URL")
        else:
            _err("teslaMate.database_url", "Must be a postgresql:// URL")
        if cfg.teslaMate.car_id < 1:
            _err("teslaMate.car_id", f"car_id {cfg.teslaMate.car_id} must be ≥ 1")
        else:
            _ok("teslaMate.car_id", str(cfg.teslaMate.car_id))

    if cfg.server.api_key and len(cfg.server.api_key) < 8:
        _warn("server.api_key", "API key < 8 chars — consider a longer key")

    tmpl = cfg.notifications.message_template
    known = {"{event}", "{vehicle}", "{detail}", "{ts}"}
    try:
        used = {f"{{{f}}}" for _, f, _, _ in string.Formatter().parse(tmpl) if f}
        unknown_keys = used - known
        if unknown_keys:
            _warn(
                "notifications.message_template",
                f"Unknown placeholder(s): {', '.join(sorted(unknown_keys))}",
            )
        else:
            _ok("notifications.message_template", tmpl[:60])
    except Exception:
        _warn("notifications.message_template", "Could not parse template")

    return checks
