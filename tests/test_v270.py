"""Tests for v2.7.0: MQTT provider, systemd/launchd service files, dashboard TeslaMate."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from tesla_cli.cli.app import app as cli_app
from tests.conftest import MOCK_VIN

_runner = CliRunner()


def _make_cfg(**overrides):
    from tesla_cli.core.config import Config

    cfg = Config()
    cfg.general.default_vin = MOCK_VIN
    for k, v in overrides.items():
        parts = k.split(".")
        obj = cfg
        for part in parts[:-1]:
            obj = getattr(obj, part)
        setattr(obj, parts[-1], v)
    return cfg


# ── Tests: MqttConfig ────────────────────────────────────────────────────────


class TestMqttConfig:
    def test_defaults(self):
        from tesla_cli.core.config import MqttConfig

        mc = MqttConfig()
        assert mc.broker == ""
        assert mc.port == 1883
        assert mc.topic_prefix == "tesla"
        assert mc.qos == 0
        assert mc.retain is False
        assert mc.tls is False

    def test_config_has_mqtt_field(self):
        from tesla_cli.core.config import Config

        cfg = Config()
        assert hasattr(cfg, "mqtt")
        assert cfg.mqtt.broker == ""

    def test_custom_values(self):
        from tesla_cli.core.config import MqttConfig

        mc = MqttConfig(broker="mqtt.example.com", port=8883, tls=True, username="user")
        assert mc.broker == "mqtt.example.com"
        assert mc.port == 8883
        assert mc.tls is True
        assert mc.username == "user"


# ── Tests: MqttProvider ──────────────────────────────────────────────────────


class TestMqttProvider:
    def _provider(self, broker="mqtt.example.com", **kwargs):
        from tesla_cli.core.providers.impl.mqtt import MqttProvider

        cfg = _make_cfg(**{"mqtt.broker": broker}, **{f"mqtt.{k}": v for k, v in kwargs.items()})
        return MqttProvider(cfg)

    def test_capabilities(self):
        from tesla_cli.core.providers.base import Capability
        from tesla_cli.core.providers.impl.mqtt import MqttProvider

        assert Capability.TELEMETRY_PUSH in MqttProvider.capabilities

    def test_layer_and_priority(self):
        from tesla_cli.core.providers.base import ProviderPriority
        from tesla_cli.core.providers.impl.mqtt import MqttProvider

        assert MqttProvider.layer == 3
        assert MqttProvider.priority == ProviderPriority.LOW

    def test_not_available_without_broker(self):
        p = self._provider(broker="")
        assert p.is_available() is False

    def test_not_available_without_paho(self):
        p = self._provider()
        with patch.dict(sys.modules, {"paho": None, "paho.mqtt": None, "paho.mqtt.client": None}):
            assert p.is_available() is False

    def test_available_with_broker_and_paho(self):
        p = self._provider()
        mock_paho = MagicMock()
        with patch.dict(
            sys.modules, {"paho": mock_paho, "paho.mqtt": mock_paho, "paho.mqtt.client": mock_paho}
        ):
            assert p.is_available() is True

    def test_health_check_no_broker(self):
        p = self._provider(broker="")
        result = p.health_check()
        assert result["status"] == "down"
        assert "not configured" in result["detail"]

    def test_health_check_no_paho(self):
        p = self._provider()
        with patch.dict(sys.modules, {"paho": None, "paho.mqtt": None, "paho.mqtt.client": None}):
            result = p.health_check()
        assert result["status"] == "down"
        assert "paho-mqtt" in result["detail"]

    def test_execute_unknown_operation(self):
        p = self._provider()
        result = p.execute("subscribe")
        assert not result.ok
        assert "Unknown" in result.error

    def test_execute_push_success(self):
        p = self._provider()
        mock_client = MagicMock()
        with patch.object(p, "_make_client", return_value=mock_client):
            result = p.execute(
                "push",
                data={
                    "charge_state": {"battery_level": 80},
                    "drive_state": {"latitude": 1.0},
                },
                vin=MOCK_VIN,
            )

        assert result.ok
        assert result.provider == "mqtt"
        assert result.data["messages"] > 0

    def test_execute_push_connection_error(self):
        """Connection failures return ok=False."""
        p = self._provider()
        bad_client = MagicMock()
        bad_client.connect.side_effect = ConnectionRefusedError("refused")
        with patch.object(p, "_make_client", return_value=bad_client):
            result = p.execute("push", data={}, vin=MOCK_VIN)
        assert not result.ok
        assert result.error != ""

    def test_topic_structure(self):
        """Published topics should follow tesla/<vin>/<key> pattern."""
        p = self._provider()
        published_topics = []
        mock_client = MagicMock()
        mock_client.publish.side_effect = lambda topic, *a, **kw: published_topics.append(topic)
        with patch.object(p, "_make_client", return_value=mock_client):
            p.execute("push", data={"charge_state": {"batt": 80}}, vin=MOCK_VIN)

        assert any(f"tesla/{MOCK_VIN}/charge_state" in t for t in published_topics)
        assert any(f"tesla/{MOCK_VIN}/state" in t for t in published_topics)

    def test_fetch_returns_error(self):
        p = self._provider()
        result = p.fetch("anything")
        assert not result.ok
        assert "write-only" in result.error

    def test_status_row_unavailable(self):
        p = self._provider(broker="")
        row = p.status_row()
        assert row["available"] is False
        assert row["name"] == "mqtt"

    def test_status_row_available(self):
        p = self._provider()
        mock_paho = MagicMock()
        with patch.dict(
            sys.modules,
            {
                "paho": mock_paho,
                "paho.mqtt": mock_paho,
                "paho.mqtt.client": mock_paho,
            },
        ):
            row = p.status_row()
        assert row["available"] is True
        assert "mqtt.example.com" in row["detail"]

    def test_loader_includes_mqtt(self):
        from tesla_cli.core.providers.loader import build_registry

        with patch("tesla_cli.core.auth.tokens.get_token", return_value=None):
            reg = build_registry(_make_cfg())
        names = {p.name for p in reg.all()}
        assert "mqtt" in names


# ── Tests: install-service CLI ────────────────────────────────────────────────


class TestInstallService:
    def test_print_systemd(self):
        result = _runner.invoke(
            cli_app, ["serve", "install-service", "--platform", "systemd", "--print"]
        )
        assert result.exit_code == 0
        assert "[Unit]" in result.output
        assert "ExecStart" in result.output
        assert "tesla-cli" in result.output.lower() or "tesla" in result.output.lower()

    def test_print_launchd(self):
        result = _runner.invoke(
            cli_app, ["serve", "install-service", "--platform", "launchd", "--print"]
        )
        assert result.exit_code == 0
        assert "com.tesla-cli.server" in result.output
        assert "ProgramArguments" in result.output

    def test_install_systemd(self, tmp_path):
        with patch("tesla_cli.cli.commands.serve.Path.home", return_value=tmp_path):
            result = _runner.invoke(
                cli_app,
                ["serve", "install-service", "--platform", "systemd"],
            )
        assert result.exit_code == 0
        assert "✓" in result.output or "Systemd" in result.output

    def test_install_launchd(self, tmp_path):
        with patch("tesla_cli.cli.commands.serve.Path.home", return_value=tmp_path):
            result = _runner.invoke(
                cli_app,
                ["serve", "install-service", "--platform", "launchd"],
            )
        assert result.exit_code == 0
        assert "✓" in result.output or "LaunchAgent" in result.output

    def test_unknown_platform_exits_1(self):
        result = _runner.invoke(cli_app, ["serve", "install-service", "--platform", "windows"])
        assert result.exit_code != 0
        assert "unknown" in result.output.lower() or "unsupported" in result.output.lower()

    def test_systemd_content(self):
        from tesla_cli.cli.commands.serve import _systemd_unit

        content = _systemd_unit("/usr/local/bin/tesla", 8080, "127.0.0.1")
        assert "[Unit]" in content
        assert "[Service]" in content
        assert "[Install]" in content
        assert "8080" in content
        assert "127.0.0.1" in content
        assert "Restart=on-failure" in content

    def test_launchd_content(self):
        from tesla_cli.cli.commands.serve import _launchd_plist

        content = _launchd_plist("/usr/local/bin/tesla", 9090, "0.0.0.0")
        assert "com.tesla-cli.server" in content
        assert "9090" in content
        assert "0.0.0.0" in content
        assert "RunAtLoad" in content
        assert "KeepAlive" in content
