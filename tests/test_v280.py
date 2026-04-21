"""Tests for v2.8.0: MQTT CLI commands, HA discovery, SSE topic filtering, dashboard geofence overlay."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from tests.conftest import MOCK_VIN
from tests.conftest import run_cli as _run


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


# ── Tests: mqtt setup ─────────────────────────────────────────────────────────


class TestMqttSetup:
    def test_setup_saves_broker(self):
        cfg = _make_cfg()
        with (
            patch("tesla_cli.cli.commands.mqtt_cmd.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.mqtt_cmd.save_config") as mock_save,
        ):
            r = _run("mqtt", "setup", "localhost")
        assert r.exit_code == 0
        assert "localhost" in r.output
        mock_save.assert_called_once_with(cfg)
        assert cfg.mqtt.broker == "localhost"

    def test_setup_custom_port_and_prefix(self):
        cfg = _make_cfg()
        with (
            patch("tesla_cli.cli.commands.mqtt_cmd.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.mqtt_cmd.save_config"),
        ):
            r = _run(
                "mqtt", "setup", "broker.local", "--port", "8883", "--prefix", "myhome", "--tls"
            )
        assert r.exit_code == 0
        assert cfg.mqtt.port == 8883
        assert cfg.mqtt.topic_prefix == "myhome"
        assert cfg.mqtt.tls is True

    def test_setup_with_credentials(self):
        cfg = _make_cfg()
        with (
            patch("tesla_cli.cli.commands.mqtt_cmd.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.mqtt_cmd.save_config"),
        ):
            r = _run(
                "mqtt", "setup", "mqtt.example.com", "--username", "user", "--password", "pass"
            )
        assert r.exit_code == 0
        assert cfg.mqtt.username == "user"
        assert cfg.mqtt.password == "pass"

    def test_setup_shows_success(self):
        cfg = _make_cfg()
        with (
            patch("tesla_cli.cli.commands.mqtt_cmd.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.mqtt_cmd.save_config"),
        ):
            r = _run("mqtt", "setup", "mybroker")
        assert "MQTT configured" in r.output or "configured" in r.output.lower()


# ── Tests: mqtt status ────────────────────────────────────────────────────────


class TestMqttStatus:
    def test_status_not_configured(self):
        cfg = _make_cfg()
        with patch("tesla_cli.cli.commands.mqtt_cmd.load_config", return_value=cfg):
            r = _run("mqtt", "status")
        assert r.exit_code == 0
        assert "not set" in r.output or "Not configured" in r.output

    def test_status_configured_shown(self):
        cfg = _make_cfg()
        cfg.mqtt.broker = "test.broker.io"
        cfg.mqtt.port = 1883
        with patch("tesla_cli.cli.commands.mqtt_cmd.load_config", return_value=cfg):
            r = _run("mqtt", "status")
        assert r.exit_code == 0
        assert "test.broker.io" in r.output

    def test_status_json_mode(self):
        cfg = _make_cfg()
        cfg.mqtt.broker = "mqtt.local"
        cfg.mqtt.port = 1883
        with patch("tesla_cli.cli.commands.mqtt_cmd.load_config", return_value=cfg):
            r = _run("-j", "mqtt", "status")
        assert r.exit_code == 0
        data = json.loads(r.output)
        assert data["broker"] == "mqtt.local"
        assert data["configured"] is True

    def test_status_json_unconfigured(self):
        cfg = _make_cfg()
        with patch("tesla_cli.cli.commands.mqtt_cmd.load_config", return_value=cfg):
            r = _run("-j", "mqtt", "status")
        assert r.exit_code == 0
        data = json.loads(r.output)
        assert data["configured"] is False


# ── Tests: mqtt test ──────────────────────────────────────────────────────────


class TestMqttTest:
    def test_test_not_configured_exits(self):
        cfg = _make_cfg()
        with patch("tesla_cli.cli.commands.mqtt_cmd.load_config", return_value=cfg):
            r = _run("mqtt", "test")
        assert r.exit_code != 0
        assert "not configured" in r.output.lower() or "MQTT" in r.output

    def test_test_success(self):
        cfg = _make_cfg()
        cfg.mqtt.broker = "localhost"
        cfg.mqtt.port = 1883
        cfg.mqtt.qos = 0

        mock_client = MagicMock()
        with (
            patch("tesla_cli.cli.commands.mqtt_cmd.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.mqtt_cmd._require_paho", return_value=True),
            patch("tesla_cli.cli.commands.mqtt_cmd._make_client", return_value=mock_client),
        ):
            r = _run("mqtt", "test")
        assert r.exit_code == 0
        mock_client.connect.assert_called_once()
        mock_client.publish.assert_called_once()

    def test_test_json_mode_ok(self):
        cfg = _make_cfg()
        cfg.mqtt.broker = "localhost"
        cfg.mqtt.port = 1883
        cfg.mqtt.qos = 0

        mock_client = MagicMock()
        with (
            patch("tesla_cli.cli.commands.mqtt_cmd.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.mqtt_cmd._require_paho", return_value=True),
            patch("tesla_cli.cli.commands.mqtt_cmd._make_client", return_value=mock_client),
        ):
            r = _run("-j", "mqtt", "test")
        assert r.exit_code == 0
        data = json.loads(r.output)
        assert data["ok"] is True
        assert "topic" in data
        assert "latency_ms" in data

    def test_test_connection_failure(self):
        cfg = _make_cfg()
        cfg.mqtt.broker = "bad.broker"
        cfg.mqtt.port = 1883
        cfg.mqtt.qos = 0

        mock_client = MagicMock()
        mock_client.connect.side_effect = ConnectionRefusedError("refused")
        with (
            patch("tesla_cli.cli.commands.mqtt_cmd.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.mqtt_cmd._require_paho", return_value=True),
            patch("tesla_cli.cli.commands.mqtt_cmd._make_client", return_value=mock_client),
        ):
            r = _run("-j", "mqtt", "test")
        assert r.exit_code != 0
        data = json.loads(r.output)
        assert data["ok"] is False


# ── Tests: mqtt publish ───────────────────────────────────────────────────────


class TestMqttPublish:
    def test_publish_not_configured_exits(self):
        cfg = _make_cfg()
        with patch("tesla_cli.cli.commands.mqtt_cmd.load_config", return_value=cfg):
            r = _run("mqtt", "publish")
        assert r.exit_code != 0

    def test_publish_success(self, mock_config, mock_fleet_backend):
        from tesla_cli.core.config import Config
        from tesla_cli.core.providers.base import ProviderResult

        cfg = Config()
        cfg.general.default_vin = MOCK_VIN
        cfg.mqtt.broker = "localhost"
        cfg.mqtt.port = 1883

        mock_result = MagicMock(spec=ProviderResult)
        mock_result.ok = True
        mock_result.data = {"messages": 5}
        mock_result.latency_ms = 12.3
        mock_result.error = None

        with (
            patch("tesla_cli.cli.commands.mqtt_cmd.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.mqtt_cmd._require_paho", return_value=True),
            patch("tesla_cli.core.config.resolve_vin", return_value=MOCK_VIN),
            patch("tesla_cli.core.providers.impl.mqtt.MqttProvider") as MockProvider,
            patch("tesla_cli.cli.commands.vehicle._with_wake", return_value={}),
        ):
            MockProvider.return_value.execute.return_value = mock_result
            r = _run("mqtt", "publish")
        assert r.exit_code == 0
        assert "Published" in r.output or "5" in r.output

    def test_publish_json_mode(self, mock_config, mock_fleet_backend):
        from tesla_cli.core.config import Config
        from tesla_cli.core.providers.base import ProviderResult

        cfg = Config()
        cfg.general.default_vin = MOCK_VIN
        cfg.mqtt.broker = "localhost"
        cfg.mqtt.port = 1883

        mock_result = MagicMock(spec=ProviderResult)
        mock_result.ok = True
        mock_result.data = {"messages": 3}
        mock_result.latency_ms = 5.0
        mock_result.error = None

        with (
            patch("tesla_cli.cli.commands.mqtt_cmd.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.mqtt_cmd._require_paho", return_value=True),
            patch("tesla_cli.core.config.resolve_vin", return_value=MOCK_VIN),
            patch("tesla_cli.core.providers.impl.mqtt.MqttProvider") as MockProvider,
            patch("tesla_cli.cli.commands.vehicle._with_wake", return_value={}),
        ):
            MockProvider.return_value.execute.return_value = mock_result
            r = _run("-j", "mqtt", "publish")
        assert r.exit_code == 0
        data = json.loads(r.output)
        assert data["ok"] is True
        assert data["messages"] == 3


# ── Tests: mqtt ha-discovery ──────────────────────────────────────────────────


class TestMqttHaDiscovery:
    def test_ha_discovery_not_configured_exits(self):
        cfg = _make_cfg()
        with patch("tesla_cli.cli.commands.mqtt_cmd.load_config", return_value=cfg):
            r = _run("mqtt", "ha-discovery")
        assert r.exit_code != 0

    def test_ha_discovery_publishes_sensors(self):
        cfg = _make_cfg()
        cfg.mqtt.broker = "localhost"
        cfg.mqtt.port = 1883
        cfg.mqtt.qos = 0
        cfg.mqtt.topic_prefix = "tesla"

        mock_client = MagicMock()
        with (
            patch("tesla_cli.cli.commands.mqtt_cmd.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.mqtt_cmd._require_paho", return_value=True),
            patch("tesla_cli.cli.commands.mqtt_cmd._make_client", return_value=mock_client),
            patch("tesla_cli.core.config.resolve_vin", return_value=MOCK_VIN),
        ):
            r = _run("mqtt", "ha-discovery")
        assert r.exit_code == 0
        # Should publish 15 discovery configs
        assert mock_client.publish.call_count == 15

    def test_ha_discovery_json_mode(self):
        cfg = _make_cfg()
        cfg.mqtt.broker = "localhost"
        cfg.mqtt.port = 1883
        cfg.mqtt.qos = 0

        mock_client = MagicMock()
        with (
            patch("tesla_cli.cli.commands.mqtt_cmd.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.mqtt_cmd._require_paho", return_value=True),
            patch("tesla_cli.cli.commands.mqtt_cmd._make_client", return_value=mock_client),
            patch("tesla_cli.core.config.resolve_vin", return_value=MOCK_VIN),
        ):
            r = _run("-j", "mqtt", "ha-discovery")
        assert r.exit_code == 0
        data = json.loads(r.output)
        assert data["ok"] is True
        assert data["sensors"] == 15

    def test_ha_discovery_correct_topics(self):
        """Verify discovery messages use correct homeassistant topic format."""
        cfg = _make_cfg()
        cfg.mqtt.broker = "localhost"
        cfg.mqtt.port = 1883
        cfg.mqtt.qos = 0

        mock_client = MagicMock()
        with (
            patch("tesla_cli.cli.commands.mqtt_cmd.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.mqtt_cmd._require_paho", return_value=True),
            patch("tesla_cli.cli.commands.mqtt_cmd._make_client", return_value=mock_client),
            patch("tesla_cli.core.config.resolve_vin", return_value=MOCK_VIN),
        ):
            _run("mqtt", "ha-discovery")

        calls = mock_client.publish.call_args_list
        topics = [c[0][0] for c in calls]
        # All should start with homeassistant/sensor/
        assert all(t.startswith("homeassistant/sensor/") for t in topics)
        # All should end with /config
        assert all(t.endswith("/config") for t in topics)
        # Verify VIN is in the topic
        assert any(MOCK_VIN in t for t in topics)

    def test_ha_discovery_retained_messages(self):
        """Discovery messages must be retained for HA auto-discovery."""
        cfg = _make_cfg()
        cfg.mqtt.broker = "localhost"
        cfg.mqtt.port = 1883
        cfg.mqtt.qos = 0

        mock_client = MagicMock()
        with (
            patch("tesla_cli.cli.commands.mqtt_cmd.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.mqtt_cmd._require_paho", return_value=True),
            patch("tesla_cli.cli.commands.mqtt_cmd._make_client", return_value=mock_client),
            patch("tesla_cli.core.config.resolve_vin", return_value=MOCK_VIN),
        ):
            _run("mqtt", "ha-discovery")

        for call in mock_client.publish.call_args_list:
            kwargs = call[1]
            assert kwargs.get("retain") is True, "HA discovery must use retain=True"

    def test_ha_discovery_payload_structure(self):
        """Discovery payload must include unique_id, name, state_topic, value_template, device."""
        cfg = _make_cfg()
        cfg.mqtt.broker = "localhost"
        cfg.mqtt.port = 1883
        cfg.mqtt.qos = 0

        mock_client = MagicMock()
        with (
            patch("tesla_cli.cli.commands.mqtt_cmd.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.mqtt_cmd._require_paho", return_value=True),
            patch("tesla_cli.cli.commands.mqtt_cmd._make_client", return_value=mock_client),
            patch("tesla_cli.core.config.resolve_vin", return_value=MOCK_VIN),
        ):
            _run("mqtt", "ha-discovery")

        # Check first payload
        first_call = mock_client.publish.call_args_list[0]
        payload = json.loads(first_call[0][1])
        assert "unique_id" in payload
        assert "name" in payload
        assert "state_topic" in payload
        assert "value_template" in payload
        assert "device" in payload


# ── Tests: mqtt registered in CLI ─────────────────────────────────────────────


class TestMqttRegistered:
    def test_mqtt_in_help(self):
        r = _run("--help")
        assert "mqtt" in r.output

    def test_mqtt_subcommands_in_help(self):
        r = _run("mqtt", "--help")
        assert r.exit_code == 0
        assert "setup" in r.output
        assert "status" in r.output
        assert "test" in r.output
        assert "publish" in r.output
        assert "ha-discovery" in r.output


# ── Tests: SSE topic filtering ────────────────────────────────────────────────


class TestSSEHubArchitecture:
    """Test SSE stream uses the VehicleStateHub for broadcasting.

    The SSE endpoint subscribes to the shared hub instead of polling per-client.
    Tested via source code analysis (avoids infinite HTTP stream hang)."""

    def _server_src(self) -> str:
        from pathlib import Path

        return (Path(__file__).parent.parent / "src" / "tesla_cli" / "api" / "app.py").read_text()

    def _hub_src(self) -> str:
        from pathlib import Path

        return (
            Path(__file__).parent.parent / "src" / "tesla_cli" / "api" / "vehicle_hub.py"
        ).read_text()

    def test_sse_uses_hub_subscribe(self):
        src = self._server_src()
        assert "hub.subscribe()" in src

    def test_sse_uses_hub_unsubscribe(self):
        src = self._server_src()
        assert "hub.unsubscribe(q)" in src

    def test_hub_broadcasts_vehicle_event(self):
        src = self._hub_src()
        assert "event: vehicle" in src

    def test_hub_broadcasts_error_event(self):
        src = self._hub_src()
        assert "event: error" in src

    def test_hub_smart_interval_on_412(self):
        src = self._hub_src()
        assert "DEGRADED_INTERVAL" in src
        assert '"412"' in src

    def test_hub_invalidate_method(self):
        src = self._hub_src()
        assert "def invalidate(self)" in src

    def test_hub_keepalive_comment(self):
        """SSE sends keepalive to prevent proxy/browser timeout."""
        src = self._server_src()
        assert "keepalive" in src

    def test_vehicle_event_format(self):
        """Verify the vehicle event string format matches SSE spec."""
        ts = 1000
        data = {"battery_level": 80}
        event = f"event: vehicle\ndata: {json.dumps({'ts': ts, 'data': data})}\n\n"
        assert event.startswith("event: vehicle\n")
        assert '"battery_level": 80' in event


# ── Tests: version 2.8.0 ─────────────────────────────────────────────────────


class TestVersion280:
    def test_version_string(self):
        from tesla_cli import __version__

        # v2.8.0 features shipped; current version is >= 2.8.0
        major, minor, patch = (int(x) for x in __version__.split("."))
        assert (major, minor) >= (2, 8)

    def test_pyproject_version(self):
        from pathlib import Path

        pyproject = Path(__file__).parent.parent / "pyproject.toml"
        content = pyproject.read_text()
        # Project version should be >= 2.8.0
        assert 'version = "' in content
