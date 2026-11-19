"""fleet-telemetry stack config.json: official MQTT schema + in-place migration."""

from __future__ import annotations

import json
from unittest.mock import patch

from tesla_cli.infra.fleet_telemetry_stack import CONFIG_TEMPLATE, FleetTelemetryStack

LEGACY_MQTT = {"host": "mosquitto", "port": 1884, "topic": "tesla/telemetry/{vin}"}


def _stack(tmp_path, mqtt=None):
    stack = FleetTelemetryStack(stack_dir=tmp_path)
    cfg = json.loads(json.dumps(CONFIG_TEMPLATE))
    cfg["port"] = 4443
    cfg["tls"]["server_cert"] = "/custom/server.crt"
    if mqtt is not None:
        cfg["mqtt"] = mqtt
    stack.config_file.write_text(json.dumps(cfg))
    stack.compose_file.write_text("services: {}\n")
    return stack


def test_template_uses_official_dispatcher_keys():
    mqtt = CONFIG_TEMPLATE["mqtt"]
    assert {"broker", "client_id", "topic_base", "qos"} <= set(mqtt)
    assert not {"host", "port", "topic"} & set(mqtt)
    assert CONFIG_TEMPLATE["records"]["V"] == ["logger", "mqtt"]


def test_migrate_legacy_block_keeps_everything_else(tmp_path):
    stack = _stack(tmp_path, LEGACY_MQTT)
    assert stack.migrate_config() is True
    cfg = json.loads(stack.config_file.read_text())
    assert cfg["mqtt"]["broker"] == "mosquitto:1884"
    assert cfg["mqtt"]["topic_base"] == "tesla/telemetry"
    assert "host" not in cfg["mqtt"]
    assert cfg["tls"]["server_cert"] == "/custom/server.crt"  # untouched
    assert stack.migrate_config() is False  # idempotent


def test_migrate_noop_for_current_or_missing_config(tmp_path):
    stack = _stack(tmp_path)
    before = stack.config_file.read_text()
    assert stack.migrate_config() is False
    assert stack.config_file.read_text() == before
    assert FleetTelemetryStack(stack_dir=tmp_path / "none").migrate_config() is False
    stack.config_file.write_text("{not json")
    assert stack.migrate_config() is False


def test_start_and_restart_migrate_then_restart_container(tmp_path):
    stack = _stack(tmp_path, LEGACY_MQTT)
    calls: list[tuple] = []
    with (
        patch.object(stack, "_docker_compose", side_effect=lambda *a, **k: calls.append(a)),
        patch.object(stack, "_wait_healthy", return_value=True),
    ):
        assert stack.start() is True
        assert calls == [("up", "-d"), ("restart",)]
        calls.clear()
        assert stack.start() is False  # already migrated: no extra restart
        assert calls == [("up", "-d")]
        stack.config_file.write_text(json.dumps({"mqtt": LEGACY_MQTT}))
        calls.clear()
        assert stack.restart() is True
        assert calls == [("restart",)]


def test_cli_restart_reports_migration(tmp_path):
    from tesla_cli.cli.commands import telemetry as tcmd
    from tests.conftest import run_cli

    stack = _stack(tmp_path, LEGACY_MQTT)
    with (
        patch.object(tcmd, "_stack", return_value=stack),
        patch.object(stack, "_docker_compose"),
    ):
        r = run_cli("telemetry", "restart")
    assert r.exit_code == 0, r.output
    assert "pre-5.6" in r.output
