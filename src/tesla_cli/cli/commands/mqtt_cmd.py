"""MQTT commands: tesla mqtt setup|status|test|publish.

Configure and manage the MQTT telemetry integration. Publishes vehicle
state snapshots to a local or remote MQTT broker.

Requires paho-mqtt: pip install 'tesla-cli[mqtt]'
"""

from __future__ import annotations

import typer

from tesla_cli.cli.output import console, is_json_mode
from tesla_cli.core.config import load_config, save_config

mqtt_app = typer.Typer(
    name="mqtt",
    help="MQTT broker integration — publish vehicle state as telemetry.",
)

VinOption = typer.Option(None, "--vin", "-v", help="VIN or alias")


# ── HA discovery sensor definitions ──────────────────────────────────────────

_HA_SENSORS: list[tuple[str, str, str, str | None, str | None]] = [
    # (slug, friendly_name, state_topic_suffix, unit, device_class)
    ("battery_level", "Battery Level", "charge_state", "%", "battery"),
    ("battery_range", "Battery Range", "charge_state", "mi", "distance"),
    ("charging_state", "Charging State", "charge_state", None, None),
    ("charge_limit", "Charge Limit", "charge_state", "%", None),
    ("energy_added", "Energy Added", "charge_state", "kWh", "energy"),
    ("charger_power", "Charger Power", "charge_state", "kW", "power"),
    ("speed", "Speed", "drive_state", "mph", "speed"),
    ("latitude", "Latitude", "drive_state", "°", None),
    ("longitude", "Longitude", "drive_state", "°", None),
    ("inside_temp", "Cabin Temperature", "climate_state", "°C", "temperature"),
    ("outside_temp", "Outside Temperature", "climate_state", "°C", "temperature"),
    ("climate_on", "Climate On", "climate_state", None, None),
    ("locked", "Locked", "vehicle_state", None, None),
    ("odometer", "Odometer", "vehicle_state", "mi", "distance"),
    ("sw_version", "Software Version", "vehicle_state", None, None),
]

# Field extraction: slug → (state_section, state_key)
_SLUG_TO_KEY: dict[str, tuple[str, str]] = {
    "battery_level": ("charge_state", "battery_level"),
    "battery_range": ("charge_state", "battery_range"),
    "charging_state": ("charge_state", "charging_state"),
    "charge_limit": ("charge_state", "charge_limit_soc"),
    "energy_added": ("charge_state", "charge_energy_added"),
    "charger_power": ("charge_state", "charger_power"),
    "speed": ("drive_state", "speed"),
    "latitude": ("drive_state", "latitude"),
    "longitude": ("drive_state", "longitude"),
    "inside_temp": ("climate_state", "inside_temp"),
    "outside_temp": ("climate_state", "outside_temp"),
    "climate_on": ("climate_state", "is_climate_on"),
    "locked": ("vehicle_state", "locked"),
    "odometer": ("vehicle_state", "odometer"),
    "sw_version": ("vehicle_state", "software_version"),
}


# ── Helpers ───────────────────────────────────────────────────────────────────


def _require_paho() -> bool:
    try:
        import paho.mqtt.client  # noqa: F401

        return True
    except ImportError:
        console.print(
            "[red]paho-mqtt not installed.[/red]\n\n"
            "Install with:\n"
            "  [bold]pip install 'tesla-cli[mqtt]'[/bold]\n"
            "  or\n"
            "  [bold]uv pip install paho-mqtt[/bold]"
        )
        return False


def _make_client(cfg, client_id: str = "tesla-cli"):
    """Build and return a connected paho MQTT client."""
    import paho.mqtt.client as mqtt

    client = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv311)
    if cfg.mqtt.username:
        client.username_pw_set(cfg.mqtt.username, cfg.mqtt.password or "")
    if cfg.mqtt.tls:
        client.tls_set()
    return client


def _publish_ha_discovery(client, cfg, vin: str) -> int:
    """Publish Home Assistant MQTT discovery configs for all sensors.

    Returns the number of discovery messages published.
    """
    import json as _json

    prefix = (cfg.mqtt.topic_prefix or "tesla").rstrip("/")
    device_info = {
        "identifiers": [f"tesla_{vin}"],
        "name": f"Tesla {vin[-6:]}",
        "manufacturer": "Tesla",
        "model": "Vehicle",
        "sw_version": vin,
    }

    published = 0
    for slug, friendly_name, state_section, unit, device_class in _HA_SENSORS:
        unique_id = f"tesla_{vin}_{slug}"
        state_topic = f"{prefix}/{vin}/{state_section}"
        # value_template extracts the specific key from the JSON state blob
        _, state_key = _SLUG_TO_KEY.get(slug, ("", slug))
        value_tpl = f"{{{{ value_json.{state_key} }}}}"

        config: dict = {
            "unique_id": unique_id,
            "name": f"Tesla {friendly_name}",
            "state_topic": state_topic,
            "value_template": value_tpl,
            "device": device_info,
        }
        if unit:
            config["unit_of_measurement"] = unit
        if device_class:
            config["device_class"] = device_class

        discovery_topic = f"homeassistant/sensor/{unique_id}/config"
        client.publish(
            discovery_topic,
            _json.dumps(config),
            qos=cfg.mqtt.qos,
            retain=True,  # discovery configs should be retained
        )
        published += 1

    return published


# ── Commands ──────────────────────────────────────────────────────────────────


@mqtt_app.command("setup")
def mqtt_setup(
    broker: str = typer.Argument(..., help="MQTT broker hostname or IP (e.g. localhost)"),
    port: int = typer.Option(1883, "--port", "-p", help="Broker port (default 1883)"),
    username: str = typer.Option("", "--username", "-u", help="Broker username"),
    password: str = typer.Option("", "--password", help="Broker password"),
    topic_prefix: str = typer.Option("tesla", "--prefix", help="Topic prefix (default: tesla)"),
    tls: bool = typer.Option(False, "--tls", help="Enable TLS/SSL (port 8883 typical)"),
) -> None:
    """Configure MQTT broker connection.

    \b
    tesla mqtt setup localhost
    tesla mqtt setup mqtt.example.com --port 1883 --username user --password pass
    tesla mqtt setup broker.local --tls --port 8883
    """
    cfg = load_config()
    cfg.mqtt.broker = broker
    cfg.mqtt.port = port
    cfg.mqtt.username = username
    cfg.mqtt.password = password
    cfg.mqtt.topic_prefix = topic_prefix
    cfg.mqtt.tls = tls
    save_config(cfg)

    from tesla_cli.cli.output import render_success

    render_success(
        f"MQTT configured: [bold]{broker}:{port}[/bold]  "
        f"prefix=[bold]{topic_prefix}[/bold]\n"
        "Test with: [bold]tesla mqtt test[/bold]"
    )


@mqtt_app.command("status")
def mqtt_status() -> None:
    """Show MQTT configuration and broker connectivity.

    \b
    tesla mqtt status
    tesla -j mqtt status
    """
    import json as _json

    cfg = load_config()
    mc = cfg.mqtt
    configured = bool(mc.broker)

    if is_json_mode():
        console.print(
            _json.dumps(
                {
                    "configured": configured,
                    "broker": mc.broker,
                    "port": mc.port,
                    "topic_prefix": mc.topic_prefix,
                    "username_set": bool(mc.username),
                    "tls": mc.tls,
                    "qos": mc.qos,
                    "retain": mc.retain,
                }
            )
        )
        return

    from rich.table import Table

    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_column("k", style="dim", width=18)
    t.add_column("v")
    t.add_row("Broker", mc.broker or "[dim]not set[/dim]")
    t.add_row("Port", str(mc.port))
    t.add_row("Topic prefix", mc.topic_prefix or "tesla")
    t.add_row("Username", mc.username or "[dim]none[/dim]")
    t.add_row("TLS", "[green]yes[/green]" if mc.tls else "[dim]no[/dim]")
    t.add_row("QoS", str(mc.qos))
    t.add_row("Retain", "[green]yes[/green]" if mc.retain else "[dim]no[/dim]")

    if configured:
        if not _require_paho():
            console.print(t)
            return
        try:
            client = _make_client(cfg, "tesla-cli-status-check")
            client.connect(mc.broker, mc.port, keepalive=5)
            client.disconnect()
            t.add_row("Connectivity", "[green]✓ OK[/green]")
        except Exception as exc:  # noqa: BLE001
            t.add_row("Connectivity", f"[red]✗ {exc}[/red]")

    console.print(t)

    if not configured:
        console.print(
            "\n[yellow]Not configured.[/yellow]\nRun: [bold]tesla mqtt setup <BROKER>[/bold]"
        )


@mqtt_app.command("test")
def mqtt_test() -> None:
    """Send a test message to the MQTT broker to verify connectivity.

    \b
    tesla mqtt test
    """
    import json as _json
    import time

    cfg = load_config()
    if not cfg.mqtt.broker:
        console.print(
            "[red]MQTT not configured.[/red]\nRun: [bold]tesla mqtt setup <BROKER>[/bold]"
        )
        raise typer.Exit(1)

    if not _require_paho():
        raise typer.Exit(1)

    prefix = (cfg.mqtt.topic_prefix or "tesla").rstrip("/")
    topic = f"{prefix}/test"

    try:
        client = _make_client(cfg, "tesla-cli-test")
        t0 = time.monotonic()
        client.connect(cfg.mqtt.broker, cfg.mqtt.port, keepalive=5)
        payload = _json.dumps({"source": "tesla-cli", "ts": int(time.time()), "msg": "test"})
        client.publish(topic, payload, qos=cfg.mqtt.qos)
        client.loop(timeout=0.5)
        client.disconnect()
        ms = round((time.monotonic() - t0) * 1000, 1)

        if is_json_mode():
            console.print(_json.dumps({"ok": True, "topic": topic, "latency_ms": ms}))
        else:
            console.print(f"[green]✓[/green] Message published to [bold]{topic}[/bold]  ({ms} ms)")

    except Exception as exc:  # noqa: BLE001
        if is_json_mode():
            console.print(_json.dumps({"ok": False, "error": str(exc)}))
        else:
            console.print(f"[red]✗ MQTT test failed:[/red] {exc}")
        raise typer.Exit(1)


@mqtt_app.command("publish")
def mqtt_publish(
    vin: str | None = VinOption,
    ha_discovery: bool = typer.Option(
        False,
        "--ha-discovery",
        help="Also publish Home Assistant MQTT discovery configs",
    ),
) -> None:
    """Publish current vehicle state to the MQTT broker (one-shot).

    \b
    tesla mqtt publish
    tesla mqtt publish --ha-discovery   # also register HA sensors
    tesla -j mqtt publish
    """
    import json as _json

    cfg = load_config()
    if not cfg.mqtt.broker:
        console.print(
            "[red]MQTT not configured.[/red]\nRun: [bold]tesla mqtt setup <BROKER>[/bold]"
        )
        raise typer.Exit(1)

    if not _require_paho():
        raise typer.Exit(1)

    from tesla_cli.cli.commands.vehicle import _with_wake
    from tesla_cli.core.config import resolve_vin

    v = resolve_vin(cfg, vin)
    data = _with_wake(lambda b, vv: b.get_vehicle_data(vv), v)

    from tesla_cli.core.providers.impl.mqtt import MqttProvider

    provider = MqttProvider(cfg)
    result = provider.execute("push", data=data, vin=v)

    discovery_count = 0
    if ha_discovery and result.ok:
        try:
            client = _make_client(cfg, f"tesla-cli-ha-{v[-6:]}")
            client.connect(cfg.mqtt.broker, cfg.mqtt.port, keepalive=10)
            discovery_count = _publish_ha_discovery(client, cfg, v)
            client.loop(timeout=1.0)
            client.disconnect()
        except Exception as exc:  # noqa: BLE001
            console.print(f"[yellow]⚠ HA discovery publish failed: {exc}[/yellow]")

    if is_json_mode():
        console.print(
            _json.dumps(
                {
                    "ok": result.ok,
                    "messages": result.data.get("messages") if result.data else 0,
                    "ha_discovery": discovery_count,
                    "latency_ms": result.latency_ms,
                    "error": result.error,
                }
            )
        )
        return

    if result.ok:
        msgs = result.data.get("messages", 0) if result.data else 0
        line = f"[green]✓[/green] Published {msgs} messages to [bold]{cfg.mqtt.broker}[/bold]  ({result.latency_ms:.0f} ms)"
        if discovery_count:
            line += f"\n  [dim]+{discovery_count} HA discovery configs published[/dim]"
        console.print(line)
    else:
        console.print(f"[red]✗ MQTT publish failed:[/red] {result.error}")
        raise typer.Exit(1)


@mqtt_app.command("ha-discovery")
def mqtt_ha_discovery(vin: str | None = VinOption) -> None:
    """Publish Home Assistant MQTT discovery configuration for all sensors.

    This registers tesla sensors in Home Assistant automatically when MQTT
    discovery is enabled in HA. Run once — configs are retained on the broker.

    \b
    tesla mqtt ha-discovery
    """
    import json as _json

    cfg = load_config()
    if not cfg.mqtt.broker:
        console.print(
            "[red]MQTT not configured.[/red]\nRun: [bold]tesla mqtt setup <BROKER>[/bold]"
        )
        raise typer.Exit(1)

    if not _require_paho():
        raise typer.Exit(1)

    from tesla_cli.core.config import resolve_vin

    v = resolve_vin(cfg, vin)

    try:
        client = _make_client(cfg, f"tesla-cli-ha-{v[-6:]}")
        client.connect(cfg.mqtt.broker, cfg.mqtt.port, keepalive=10)
        count = _publish_ha_discovery(client, cfg, v)
        client.loop(timeout=1.0)
        client.disconnect()

        if is_json_mode():
            console.print(_json.dumps({"ok": True, "sensors": count, "vin": v}))
        else:
            console.print(
                f"[green]✓[/green] Published [bold]{count}[/bold] HA discovery configs "
                f"for VIN [bold]{v[-6:]}[/bold]\n"
                f"  Topics: [dim]homeassistant/sensor/tesla_{v}_<slug>/config[/dim]\n"
                f"  Home Assistant will auto-create sensors if MQTT discovery is enabled."
            )
    except Exception as exc:  # noqa: BLE001
        if is_json_mode():
            console.print(_json.dumps({"ok": False, "error": str(exc)}))
        else:
            console.print(f"[red]✗ HA discovery failed:[/red] {exc}")
        raise typer.Exit(1)
