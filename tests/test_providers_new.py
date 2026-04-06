"""Tests for provider implementations — additional coverage."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from tesla_cli.core.providers.base import Capability, ProviderPriority


def _make_cfg(**overrides):
    from tesla_cli.core.config import Config

    cfg = Config()
    for k, v in overrides.items():
        parts = k.split(".")
        obj = cfg
        for part in parts[:-1]:
            obj = getattr(obj, part)
        setattr(obj, parts[-1], v)
    return cfg


# ── MqttProvider ──────────────────────────────────────────────────────────────


class TestMqttProvider:
    def _provider(self, broker="mqtt.local", port=1883):
        from tesla_cli.core.providers.impl.mqtt import MqttProvider

        return MqttProvider(_make_cfg(**{"mqtt.broker": broker, "mqtt.port": port}))

    def test_capabilities(self):
        p = self._provider()
        assert Capability.TELEMETRY_PUSH in p.capabilities

    def test_layer_and_priority(self):
        p = self._provider()
        assert p.layer == 3
        assert p.priority == ProviderPriority.LOW

    def test_name(self):
        p = self._provider()
        assert p.name == "mqtt"

    def test_unavailable_without_broker(self):
        p = self._provider(broker="")
        assert p.is_available() is False

    def test_unavailable_without_paho(self):
        p = self._provider()
        with patch.dict("sys.modules", {"paho": None, "paho.mqtt": None, "paho.mqtt.client": None}):
            assert p.is_available() is False

    def test_available_with_broker_and_paho(self):
        p = self._provider()
        mock_paho = MagicMock()
        with patch.dict(
            "sys.modules",
            {"paho": mock_paho, "paho.mqtt": mock_paho, "paho.mqtt.client": mock_paho},
        ):
            assert p.is_available() is True

    def test_health_check_no_broker(self):
        p = self._provider(broker="")
        result = p.health_check()
        assert result["status"] == "down"
        assert "broker" in result["detail"]

    def test_health_check_no_paho(self):
        p = self._provider()
        with patch.dict("sys.modules", {"paho": None, "paho.mqtt": None, "paho.mqtt.client": None}):
            result = p.health_check()
        assert result["status"] == "down"
        assert "paho" in result["detail"].lower()

    def test_execute_unknown_operation(self):
        p = self._provider()
        result = p.execute("bogus")
        assert not result.ok
        assert "Unknown" in result.error

    def test_execute_push_publishes(self):
        p = self._provider()
        mock_client = MagicMock()
        data = {
            "charge_state": {"battery_level": 80},
            "drive_state": {"speed": 0},
        }
        with patch.object(p, "_make_client", return_value=mock_client):
            result = p.execute("push", data=data, vin="TEST123456")
        assert result.ok
        assert result.provider == "mqtt"
        assert result.data["messages"] >= 1

    def test_execute_send_alias(self):
        p = self._provider()
        mock_client = MagicMock()
        with patch.object(p, "_make_client", return_value=mock_client):
            result = p.execute("send", data={}, vin="VIN123")
        assert result.ok

    def test_fetch_is_write_only(self):
        p = self._provider()
        result = p.fetch("anything")
        assert not result.ok
        assert "write-only" in result.error

    def test_status_row_available(self):
        p = self._provider()
        mock_paho = MagicMock()
        with patch.dict(
            "sys.modules",
            {"paho": mock_paho, "paho.mqtt": mock_paho, "paho.mqtt.client": mock_paho},
        ):
            row = p.status_row()
        assert row["name"] == "mqtt"
        assert "mqtt.local" in row["detail"]

    def test_status_row_unavailable(self):
        p = self._provider(broker="")
        row = p.status_row()
        assert row["available"] is False
        assert "not configured" in row["detail"]

    def test_execute_connection_error(self):
        p = self._provider()
        mock_client = MagicMock()
        mock_client.connect.side_effect = ConnectionRefusedError("refused")
        with patch.object(p, "_make_client", return_value=mock_client):
            result = p.execute("push", data={}, vin="VIN")
        assert not result.ok
        assert "refused" in result.error


# ── AppriseProvider ───────────────────────────────────────────────────────────


class TestAppriseProvider:
    def _provider(self, enabled=True, urls=None):
        from tesla_cli.core.providers.impl.apprise_notify import AppriseProvider

        cfg = _make_cfg()
        cfg.notifications.enabled = enabled
        cfg.notifications.apprise_urls = ["tgram://botid/chatid"] if urls is None else urls
        return AppriseProvider(cfg)

    def test_capabilities(self):
        p = self._provider()
        assert Capability.NOTIFY in p.capabilities

    def test_layer_and_priority(self):
        p = self._provider()
        assert p.layer == 3
        assert p.priority == ProviderPriority.LOW

    def test_name(self):
        p = self._provider()
        assert p.name == "apprise"

    def test_unavailable_when_disabled(self):
        p = self._provider(enabled=False)
        assert p.is_available() is False

    def test_unavailable_without_urls(self):
        p = self._provider(urls=[])
        assert p.is_available() is False

    def test_unavailable_without_package(self):
        p = self._provider()
        with patch.dict("sys.modules", {"apprise": None}):
            assert p.is_available() is False

    def test_health_check_disabled(self):
        p = self._provider(enabled=False)
        result = p.health_check()
        assert result["status"] == "down"
        assert "disabled" in result["detail"]

    def test_health_check_no_urls(self):
        p = self._provider(urls=[])
        result = p.health_check()
        assert result["status"] == "down"
        assert "apprise_urls" in result["detail"]

    def test_health_check_ok(self):
        p = self._provider(urls=["tgram://x/y", "slack://x"])
        mock_apprise = MagicMock()
        with patch.dict("sys.modules", {"apprise": mock_apprise}):
            result = p.health_check()
        assert result["status"] == "ok"
        assert "2" in result["detail"]

    def test_execute_unknown_operation(self):
        p = self._provider()
        result = p.execute("bogus")
        assert not result.ok
        assert "Unknown" in result.error

    def test_execute_push_success(self):
        p = self._provider()
        mock_apprise_module = MagicMock()
        mock_instance = MagicMock()
        mock_instance.notify.return_value = True
        mock_apprise_module.Apprise.return_value = mock_instance
        with patch.dict("sys.modules", {"apprise": mock_apprise_module}):
            result = p.execute("push", title="Alert", body="Battery low")
        assert result.ok
        assert result.provider == "apprise"
        mock_instance.notify.assert_called_once_with(title="Alert", body="Battery low")

    def test_execute_notify_alias(self):
        p = self._provider()
        mock_apprise_module = MagicMock()
        mock_instance = MagicMock()
        mock_instance.notify.return_value = True
        mock_apprise_module.Apprise.return_value = mock_instance
        with patch.dict("sys.modules", {"apprise": mock_apprise_module}):
            result = p.execute("notify", title="T", body="B")
        assert result.ok

    def test_execute_send_alias(self):
        p = self._provider()
        mock_apprise_module = MagicMock()
        mock_instance = MagicMock()
        mock_instance.notify.return_value = True
        mock_apprise_module.Apprise.return_value = mock_instance
        with patch.dict("sys.modules", {"apprise": mock_apprise_module}):
            result = p.execute("send", title="T", body="B")
        assert result.ok

    def test_execute_notify_failure(self):
        p = self._provider()
        mock_apprise_module = MagicMock()
        mock_instance = MagicMock()
        mock_instance.notify.return_value = False
        mock_apprise_module.Apprise.return_value = mock_instance
        with patch.dict("sys.modules", {"apprise": mock_apprise_module}):
            result = p.execute("push", title="T", body="B")
        assert not result.ok
        assert result.error == "Some channels failed"

    def test_execute_uses_message_kwarg(self):
        p = self._provider()
        mock_apprise_module = MagicMock()
        mock_instance = MagicMock()
        mock_instance.notify.return_value = True
        mock_apprise_module.Apprise.return_value = mock_instance
        with patch.dict("sys.modules", {"apprise": mock_apprise_module}):
            result = p.execute("push", title="T", message="via message kwarg")
        assert result.ok
        mock_instance.notify.assert_called_once_with(title="T", body="via message kwarg")

    def test_execute_adds_all_urls(self):
        p = self._provider(urls=["tgram://a/b", "slack://x/y", "mailto://user:pw@example.com"])
        mock_apprise_module = MagicMock()
        mock_instance = MagicMock()
        mock_instance.notify.return_value = True
        mock_apprise_module.Apprise.return_value = mock_instance
        with patch.dict("sys.modules", {"apprise": mock_apprise_module}):
            result = p.execute("push", title="T", body="B")
        assert result.ok
        assert result.data["channels"] == 3
        assert mock_instance.add.call_count == 3

    def test_execute_not_installed(self):
        p = self._provider()
        with patch.dict("sys.modules", {"apprise": None}):
            result = p.execute("push", title="T", body="B")
        assert not result.ok
        assert "not installed" in result.error


# ── AbrpProvider ──────────────────────────────────────────────────────────────


class TestAbrpProvider:
    def _provider(self, token="mytoken", api_key=""):
        from tesla_cli.core.providers.impl.abrp import AbrpProvider

        return AbrpProvider(_make_cfg(**{"abrp.user_token": token, "abrp.api_key": api_key}))

    def test_capabilities(self):
        p = self._provider()
        assert Capability.TELEMETRY_PUSH in p.capabilities

    def test_layer_and_priority(self):
        p = self._provider()
        assert p.layer == 3
        assert p.priority == ProviderPriority.LOW

    def test_name(self):
        p = self._provider()
        assert p.name == "abrp"

    def test_unavailable_without_token(self):
        p = self._provider(token="")
        assert p.is_available() is False

    def test_available_with_token(self):
        p = self._provider()
        assert p.is_available() is True

    def test_health_check_no_token(self):
        p = self._provider(token="")
        result = p.health_check()
        assert result["status"] == "down"

    def test_health_check_with_token(self):
        p = self._provider()
        result = p.health_check()
        assert result["status"] == "ok"
        assert "iternio" in result["detail"]

    def test_execute_unknown_operation(self):
        p = self._provider()
        result = p.execute("bogus", data={})
        assert not result.ok

    def test_execute_push_builds_tlm(self):
        p = self._provider()
        data = {
            "charge_state": {
                "battery_level": 72,
                "charging_state": "Disconnected",
                "charger_power": 0,
            },
            "drive_state": {"speed": 60, "power": 50, "latitude": 37.4, "longitude": -122.0},
            "climate_state": {"inside_temp": 22.0},
        }
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"status": "ok"}'
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            result = p.execute("push", data=data)
        assert result.ok
        tlm = result.data["tlm"]
        assert tlm["soc"] == 72
        assert tlm["lat"] == 37.4
        assert tlm["lon"] == -122.0
        assert tlm["temp"] == 22.0
        assert tlm["is_charging"] == 0

    def test_execute_send_alias(self):
        p = self._provider()
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"status": "ok"}'
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            result = p.execute("send", data={})
        assert result.ok

    def test_execute_charging_state_in_tlm(self):
        p = self._provider()
        data = {
            "charge_state": {
                "battery_level": 50,
                "charging_state": "Charging",
                "charger_power": 11,
            },
            "drive_state": {},
            "climate_state": {},
        }
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"status": "ok"}'
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            result = p.execute("push", data=data)
        assert result.ok
        assert result.data["tlm"]["is_charging"] == 1

    def test_execute_none_values_stripped(self):
        p = self._provider()
        data = {"charge_state": {}, "drive_state": {}, "climate_state": {}}
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"status": "ok"}'
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            result = p.execute("push", data=data)
        assert result.ok
        # lat/lon/temp should not appear if not in data
        assert "lat" not in result.data["tlm"]
        assert "lon" not in result.data["tlm"]
        assert "temp" not in result.data["tlm"]

    def test_execute_network_error(self):
        p = self._provider()
        with patch("urllib.request.urlopen", side_effect=OSError("network error")):
            result = p.execute("push", data={})
        assert not result.ok
        assert "network error" in result.error

    def test_execute_with_api_key(self):
        p = self._provider(token="tok", api_key="apikey123")
        captured_url = {}
        original_request = __import__("urllib.request", fromlist=["Request"]).Request

        def capture_request(url, **kwargs):
            captured_url["url"] = url
            return original_request(url, **kwargs)

        with (
            patch("urllib.request.Request", side_effect=capture_request),
            patch("urllib.request.urlopen") as mock_urlopen,
        ):
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"status": "ok"}'
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            p.execute("push", data={})
        assert "api_key=apikey123" in captured_url.get("url", "")


# ── HomeAssistantProvider ─────────────────────────────────────────────────────


class TestHaProvider:
    def _provider(self, url="http://ha.local:8123", token="ha_token"):
        from tesla_cli.core.providers.impl.ha import HomeAssistantProvider

        return HomeAssistantProvider(
            _make_cfg(**{"home_assistant.url": url, "home_assistant.token": token})
        )

    def test_capabilities(self):
        p = self._provider()
        assert Capability.HOME_SYNC in p.capabilities

    def test_layer_and_priority(self):
        p = self._provider()
        assert p.layer == 3
        assert p.priority == ProviderPriority.LOW

    def test_name(self):
        p = self._provider()
        assert p.name == "home-assistant"

    def test_unavailable_without_url(self):
        p = self._provider(url="")
        assert p.is_available() is False

    def test_unavailable_without_token(self):
        p = self._provider(token="")
        assert p.is_available() is False

    def test_available_with_url_and_token(self):
        p = self._provider()
        assert p.is_available() is True

    def test_health_check_not_configured(self):
        p = self._provider(url="", token="")
        result = p.health_check()
        assert result["status"] == "down"

    def test_execute_unknown_operation(self):
        p = self._provider()
        result = p.execute("bogus")
        assert not result.ok
        assert "Unknown" in result.error

    def test_execute_push_all_sensors(self):
        p = self._provider()
        data = {
            "charge_state": {
                "battery_level": 80,
                "battery_range": 200.0,
                "charging_state": "Complete",
                "charge_limit_soc": 90,
                "charge_energy_added": 12.0,
                "charger_power": 0,
            },
            "drive_state": {
                "speed": 0,
                "shift_state": "P",
                "latitude": 37.4,
                "longitude": -122.0,
                "heading": 90,
            },
            "climate_state": {"inside_temp": 22.0, "outside_temp": 18.0, "is_climate_on": False},
            "vehicle_state": {
                "locked": True,
                "odometer": 15000.0,
                "software_version": "2024.14",
                "is_user_present": False,
            },
        }
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"entity_id":"sensor.tesla_battery_level","state":"80"}'
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            result = p.execute("push", data=data, vin="TESTVINTAIL")
        assert result.ok
        assert result.data["pushed"] == 18
        assert result.data["errors"] == 0

    def test_execute_sync_alias(self):
        p = self._provider()
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b"{}"
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            result = p.execute("sync", data={}, vin="VIN")
        # No sensors matched = ok with 0 pushed
        assert result.ok
        assert result.data["pushed"] == 0

    def test_execute_partial_failure(self):
        p = self._provider()
        data = {"charge_state": {"battery_level": 80}}
        call_count = 0

        def urlopen_side_effect(req, timeout=None):
            nonlocal call_count
            call_count += 1
            raise OSError("HA unreachable")

        with patch("urllib.request.urlopen", side_effect=urlopen_side_effect):
            result = p.execute("push", data=data, vin="VIN")
        assert not result.ok
        assert result.data["errors"] > 0

    def test_headers_include_bearer_token(self):
        p = self._provider(token="mysecrettoken")
        headers = p._headers()
        assert headers["Authorization"] == "Bearer mysecrettoken"
        assert headers["Content-Type"] == "application/json"


# ── BleProvider ───────────────────────────────────────────────────────────────


class TestBleProvider:
    def _provider(self, key_path="/tmp/key.pem"):
        from tesla_cli.core.providers.impl.ble import BleProvider

        return BleProvider(_make_cfg(**{"ble.key_path": key_path}))

    def test_capabilities(self):
        p = self._provider()
        assert Capability.VEHICLE_COMMAND in p.capabilities

    def test_layer_and_priority(self):
        p = self._provider()
        assert p.layer == 0
        assert p.priority == ProviderPriority.CRITICAL

    def test_name(self):
        p = self._provider()
        assert p.name == "ble"

    def test_supported_commands_mapping(self):
        from tesla_cli.core.providers.impl.ble import _BLE_COMMANDS

        assert "lock" in _BLE_COMMANDS
        assert "unlock" in _BLE_COMMANDS
        assert "climate_on" in _BLE_COMMANDS
        assert "climate_off" in _BLE_COMMANDS
        assert "charge_start" in _BLE_COMMANDS
        assert "charge_stop" in _BLE_COMMANDS
        assert "flash_lights" in _BLE_COMMANDS
        assert "honk_horn" in _BLE_COMMANDS
        assert len(_BLE_COMMANDS) >= 8

    def test_unavailable_without_binary(self):
        p = self._provider()
        with patch("tesla_cli.core.providers.impl.ble.shutil.which", return_value=None):
            assert p.is_available() is False

    def test_unavailable_without_key(self):
        p = self._provider(key_path="")
        with patch("tesla_cli.core.providers.impl.ble.shutil.which", return_value="/bin/tc"):
            assert p.is_available() is False

    def test_available_with_binary_and_key(self):
        p = self._provider()
        with patch("tesla_cli.core.providers.impl.ble.shutil.which", return_value="/bin/tc"):
            assert p.is_available() is True

    def test_health_check_no_binary(self):
        p = self._provider()
        with patch("tesla_cli.core.providers.impl.ble.shutil.which", return_value=None):
            result = p.health_check()
        assert result["status"] == "down"
        assert "binary" in result["detail"].lower()

    def test_health_check_no_key(self):
        p = self._provider(key_path="")
        with patch("tesla_cli.core.providers.impl.ble.shutil.which", return_value="/bin/tc"):
            result = p.health_check()
        assert result["status"] == "down"
        assert "key" in result["detail"].lower()

    def test_health_check_ok(self):
        p = self._provider()
        with patch("tesla_cli.core.providers.impl.ble.shutil.which", return_value="/bin/tc"):
            result = p.health_check()
        assert result["status"] == "ok"
        assert "/bin/tc" in result["detail"]

    def test_execute_lock_success(self):
        p = self._provider()
        mock_run = MagicMock(returncode=0, stdout="ok", stderr="")
        with (
            patch("tesla_cli.core.providers.impl.ble.shutil.which", return_value="/bin/tc"),
            patch("tesla_cli.core.providers.impl.ble.subprocess.run", return_value=mock_run),
        ):
            result = p.execute("lock", vin="VIN123456")
        assert result.ok
        assert result.provider == "ble"

    def test_execute_maps_command_name(self):
        p = self._provider()
        captured = {}
        mock_run = MagicMock(returncode=0, stdout="", stderr="")

        def fake_run(args, **kwargs):
            captured["args"] = args
            return mock_run

        with (
            patch("tesla_cli.core.providers.impl.ble.shutil.which", return_value="/bin/tc"),
            patch("tesla_cli.core.providers.impl.ble.subprocess.run", side_effect=fake_run),
        ):
            p.execute("climate_on", vin="VIN123")
        assert "climate-on" in captured["args"]

    def test_execute_unknown_command_passthrough(self):
        p = self._provider()
        captured = {}
        mock_run = MagicMock(returncode=0, stdout="", stderr="")

        def fake_run(args, **kwargs):
            captured["args"] = args
            return mock_run

        with (
            patch("tesla_cli.core.providers.impl.ble.shutil.which", return_value="/bin/tc"),
            patch("tesla_cli.core.providers.impl.ble.subprocess.run", side_effect=fake_run),
        ):
            p.execute("custom-cmd", vin="VIN123")
        assert "custom-cmd" in captured["args"]

    def test_execute_failure(self):
        p = self._provider()
        mock_run = MagicMock(returncode=1, stdout="", stderr="BLE connection failed")
        with (
            patch("tesla_cli.core.providers.impl.ble.shutil.which", return_value="/bin/tc"),
            patch("tesla_cli.core.providers.impl.ble.subprocess.run", return_value=mock_run),
        ):
            result = p.execute("lock", vin="VIN")
        assert not result.ok
        assert "BLE connection failed" in result.error

    def test_execute_timeout(self):
        import subprocess

        p = self._provider()
        with (
            patch("tesla_cli.core.providers.impl.ble.shutil.which", return_value="/bin/tc"),
            patch(
                "tesla_cli.core.providers.impl.ble.subprocess.run",
                side_effect=subprocess.TimeoutExpired("tc", 30),
            ),
        ):
            result = p.execute("lock", vin="VIN")
        assert not result.ok
        assert "timeout" in result.error.lower()

    def test_execute_no_binary(self):
        p = self._provider()
        with patch("tesla_cli.core.providers.impl.ble.shutil.which", return_value=None):
            result = p.execute("lock", vin="VIN")
        assert not result.ok
        assert "not found" in result.error


# ── VehicleApiProvider ────────────────────────────────────────────────────────


class TestVehicleApiProvider:
    def _provider(self, backend="owner"):
        from tesla_cli.core.providers.impl.vehicle_api import VehicleApiProvider

        return VehicleApiProvider(_make_cfg(**{"general.backend": backend}))

    def test_capabilities(self):
        p = self._provider()
        assert Capability.VEHICLE_STATE in p.capabilities
        assert Capability.VEHICLE_COMMAND in p.capabilities
        assert Capability.VEHICLE_LOCATION in p.capabilities

    def test_layer_and_priority(self):
        p = self._provider()
        assert p.layer == 1
        assert p.priority == ProviderPriority.HIGH

    def test_name(self):
        p = self._provider()
        assert p.name == "vehicle-api"

    def test_is_available_owner_with_token(self):
        p = self._provider(backend="owner")
        with patch("keyring.get_password", return_value="tok"):
            assert p.is_available() is True

    def test_is_available_owner_no_token(self):
        p = self._provider(backend="owner")
        with patch("keyring.get_password", return_value=None):
            assert p.is_available() is False

    def test_is_available_tessie_with_token(self):
        p = self._provider(backend="tessie")
        with patch("keyring.get_password", return_value="tessie_tok"):
            assert p.is_available() is True

    def test_is_available_fleet_with_token(self):
        p = self._provider(backend="fleet")
        with patch("keyring.get_password", return_value="fleet_tok"):
            assert p.is_available() is True

    def test_fetch_charge_state(self):
        p = self._provider()
        mock_backend = MagicMock()
        mock_backend.get_charge_state.return_value = {"battery_level": 72}
        with (
            patch("tesla_cli.core.backends.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.core.config.resolve_vin", return_value="VIN123"),
        ):
            result = p.fetch("charge_state", vin="VIN123")
        assert result.ok
        assert result.data["battery_level"] == 72

    def test_fetch_climate_state(self):
        p = self._provider()
        mock_backend = MagicMock()
        mock_backend.get_climate_state.return_value = {"inside_temp": 22.0}
        with (
            patch("tesla_cli.core.backends.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.core.config.resolve_vin", return_value="VIN123"),
        ):
            result = p.fetch("climate_state", vin="VIN123")
        assert result.ok

    def test_fetch_list_vehicles(self):
        p = self._provider()
        mock_backend = MagicMock()
        mock_backend.list_vehicles.return_value = [{"vin": "VIN1"}]
        with (
            patch("tesla_cli.core.backends.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.core.config.resolve_vin", return_value="VIN1"),
        ):
            result = p.fetch("list_vehicles")
        assert result.ok
        assert result.data[0]["vin"] == "VIN1"

    def test_execute_wake(self):
        p = self._provider()
        mock_backend = MagicMock()
        mock_backend.wake_up.return_value = {"state": "online"}
        with (
            patch("tesla_cli.core.backends.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.core.config.resolve_vin", return_value="VIN"),
        ):
            result = p.execute("wake", vin="VIN")
        assert result.ok
        mock_backend.wake_up.assert_called_once_with("VIN")

    def test_fetch_backend_exception(self):
        p = self._provider()
        mock_backend = MagicMock()
        mock_backend.get_vehicle_data.side_effect = RuntimeError("API down")
        with (
            patch("tesla_cli.core.backends.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.core.config.resolve_vin", return_value="VIN"),
        ):
            result = p.fetch("vehicle_data", vin="VIN")
        assert not result.ok
        assert "API down" in result.error


# ── TeslaMateProvider ─────────────────────────────────────────────────────────


class TestTeslaMateProvider:
    def _provider(self, url="postgresql://localhost/tm"):
        from tesla_cli.core.providers.impl.teslaMate import TeslaMateProvider

        return TeslaMateProvider(_make_cfg(**{"teslaMate.database_url": url}))

    def test_capabilities(self):
        p = self._provider()
        assert Capability.HISTORY_TRIPS in p.capabilities
        assert Capability.HISTORY_CHARGES in p.capabilities
        assert Capability.HISTORY_STATS in p.capabilities

    def test_layer_and_priority(self):
        p = self._provider()
        assert p.layer == 2
        assert p.priority == ProviderPriority.MEDIUM

    def test_name(self):
        p = self._provider()
        assert p.name == "teslaMate"

    def test_unavailable_without_url(self):
        p = self._provider(url="")
        assert p.is_available() is False

    def test_available_with_url_unmanaged(self):
        p = self._provider()
        assert p.is_available() is True

    def test_fetch_charges(self):
        p = self._provider()
        mock_backend = MagicMock()
        mock_backend.get_charging_sessions.return_value = [{"id": 1, "kwh": 20}]
        with patch("tesla_cli.core.backends.teslaMate.TeslaMateBacked", return_value=mock_backend):
            result = p.fetch("charges", limit=5)
        assert result.ok
        assert result.data[0]["kwh"] == 20
        mock_backend.get_charging_sessions.assert_called_once_with(limit=5)

    def test_fetch_stats(self):
        p = self._provider()
        mock_backend = MagicMock()
        mock_backend.get_stats.return_value = {"total_km": 10000}
        mock_backend.get_charging_stats.return_value = {"total_kwh": 500}
        with patch("tesla_cli.core.backends.teslaMate.TeslaMateBacked", return_value=mock_backend):
            result = p.fetch("stats")
        assert result.ok
        assert result.data["drives"]["total_km"] == 10000
        assert result.data["charging"]["total_kwh"] == 500

    def test_fetch_efficiency(self):
        p = self._provider()
        mock_backend = MagicMock()
        mock_backend.get_efficiency.return_value = [{"efficiency": 4.5}]
        with patch("tesla_cli.core.backends.teslaMate.TeslaMateBacked", return_value=mock_backend):
            result = p.fetch("efficiency", limit=10)
        assert result.ok
        mock_backend.get_efficiency.assert_called_once_with(limit=10)

    def test_fetch_vampire_drain(self):
        p = self._provider()
        mock_backend = MagicMock()
        mock_backend.get_vampire_drain.return_value = {"drain_kwh": 0.5}
        with patch("tesla_cli.core.backends.teslaMate.TeslaMateBacked", return_value=mock_backend):
            result = p.fetch("vampire", days=7)
        assert result.ok
        mock_backend.get_vampire_drain.assert_called_once_with(days=7)

    def test_fetch_drive_days(self):
        p = self._provider()
        mock_backend = MagicMock()
        mock_backend.get_drive_days.return_value = [{"date": "2024-01-01"}]
        with patch("tesla_cli.core.backends.teslaMate.TeslaMateBacked", return_value=mock_backend):
            result = p.fetch("drive_days", days=90)
        assert result.ok
        mock_backend.get_drive_days.assert_called_once_with(days=90)

    def test_fetch_daily_energy(self):
        p = self._provider()
        mock_backend = MagicMock()
        mock_backend.get_daily_energy.return_value = [{"date": "2024-01-01", "kwh": 5.0}]
        with patch("tesla_cli.core.backends.teslaMate.TeslaMateBacked", return_value=mock_backend):
            result = p.fetch("daily_energy", days=30)
        assert result.ok
        mock_backend.get_daily_energy.assert_called_once_with(days=30)

    def test_fetch_unknown_operation(self):
        p = self._provider()
        mock_backend = MagicMock()
        with patch("tesla_cli.core.backends.teslaMate.TeslaMateBacked", return_value=mock_backend):
            result = p.fetch("nonexistent")
        assert not result.ok
        assert "Unknown" in result.error

    def test_fetch_exception_propagates_as_error(self):
        p = self._provider()
        mock_backend = MagicMock()
        mock_backend.get_trips.side_effect = Exception("DB connection failed")
        with patch("tesla_cli.core.backends.teslaMate.TeslaMateBacked", return_value=mock_backend):
            result = p.fetch("trips")
        assert not result.ok
        assert "DB connection" in result.error

    def test_health_check_no_url(self):
        p = self._provider(url="")
        result = p.health_check()
        assert result["status"] == "down"

    def test_health_check_ok(self):
        p = self._provider()
        mock_backend = MagicMock()
        mock_backend.ping.return_value = True
        with patch("tesla_cli.core.backends.teslaMate.TeslaMateBacked", return_value=mock_backend):
            result = p.health_check()
        assert result["status"] == "ok"

    def test_health_check_db_down(self):
        p = self._provider()
        mock_backend = MagicMock()
        mock_backend.ping.return_value = False
        with patch("tesla_cli.core.backends.teslaMate.TeslaMateBacked", return_value=mock_backend):
            result = p.health_check()
        assert result["status"] == "down"
