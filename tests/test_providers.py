"""Tests for the Provider architecture (base, registry, loader, implementations)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from tesla_cli.app import app as cli_app
from tesla_cli.providers.base import Capability, Provider, ProviderPriority, ProviderResult
from tesla_cli.providers.registry import CapabilityNotAvailableError, ProviderRegistry
from tests.conftest import MOCK_VIN

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_cfg(**overrides):
    from tesla_cli.config import Config
    cfg = Config()
    cfg.general.default_vin = MOCK_VIN
    cfg.general.backend = "owner"
    for k, v in overrides.items():
        parts = k.split(".")
        obj = cfg
        for part in parts[:-1]:
            obj = getattr(obj, part)
        setattr(obj, parts[-1], v)
    return cfg


class _FakeProvider(Provider):
    """Minimal concrete provider for unit testing."""
    name        = "fake"
    description = "Test provider"
    layer       = 1
    priority    = ProviderPriority.HIGH
    capabilities = frozenset({Capability.VEHICLE_STATE})

    def __init__(self, available=True, fetch_data=None, execute_data=None):
        self._available    = available
        self._fetch_data   = fetch_data or {"battery_level": 72}
        self._execute_data = execute_data or {"result": True}

    def is_available(self) -> bool:
        return self._available

    def health_check(self) -> dict:
        return {"status": "ok" if self._available else "down", "latency_ms": 1.0, "detail": "test"}

    def fetch(self, operation: str, **kwargs) -> ProviderResult:
        return ProviderResult(ok=True, data=self._fetch_data, provider=self.name, latency_ms=1.0)

    def execute(self, operation: str, **kwargs) -> ProviderResult:
        return ProviderResult(ok=True, data=self._execute_data, provider=self.name, latency_ms=1.0)


# ── Capability ────────────────────────────────────────────────────────────────

class TestCapability:
    def test_all_returns_strings(self):
        caps = Capability.all()
        assert isinstance(caps, list)
        assert len(caps) > 5
        for c in caps:
            assert isinstance(c, str)
            assert "." in c

    def test_known_capabilities_present(self):
        caps = set(Capability.all())
        assert Capability.VEHICLE_STATE    in caps
        assert Capability.VEHICLE_COMMAND  in caps
        assert Capability.HISTORY_TRIPS    in caps
        assert Capability.TELEMETRY_PUSH   in caps
        assert Capability.NOTIFY           in caps
        assert Capability.HOME_SYNC        in caps


# ── ProviderResult ────────────────────────────────────────────────────────────

class TestProviderResult:
    def test_ok_result(self):
        r = ProviderResult(ok=True, data={"x": 1}, provider="test", latency_ms=5.0)
        assert r.ok
        assert r.data == {"x": 1}
        assert r.provider == "test"
        assert r.error is None

    def test_error_result(self):
        r = ProviderResult(ok=False, provider="test", error="connection refused")
        assert not r.ok
        assert r.error == "connection refused"

    def test_to_dict(self):
        r = ProviderResult(ok=True, data=42, provider="p", latency_ms=3.7)
        d = r.to_dict()
        assert d["ok"] is True
        assert d["provider"] == "p"
        assert d["latency_ms"] == 3.7
        assert d["data"] == 42


# ── ProviderRegistry ──────────────────────────────────────────────────────────

class TestProviderRegistry:
    def _registry(self):
        return ProviderRegistry()

    def test_register_and_get(self):
        reg = self._registry()
        p   = _FakeProvider()
        reg.register(p)
        got = reg.get(Capability.VEHICLE_STATE)
        assert got is p

    def test_priority_ordering(self):
        reg = self._registry()
        low = _FakeProvider()
        low.name = "low"
        low.priority = ProviderPriority.LOW
        high = _FakeProvider()
        high.name = "high"
        high.priority = ProviderPriority.HIGH
        reg.register(low)
        reg.register(high)
        # High priority should be first
        ordered = reg.for_capability(Capability.VEHICLE_STATE)
        assert ordered[0].name == "high"

    def test_unavailable_provider_skipped(self):
        reg = self._registry()
        unavail = _FakeProvider(available=False)
        unavail.name = "unavail"
        avail = _FakeProvider(available=True)
        avail.name = "avail"
        avail.priority = ProviderPriority.LOW  # lower priority but available
        unavail.priority = ProviderPriority.HIGH
        reg.register(unavail)
        reg.register(avail)
        got = reg.get(Capability.VEHICLE_STATE)
        assert got.name == "avail"

    def test_no_provider_raises(self):
        reg = self._registry()
        with pytest.raises(CapabilityNotAvailableError):
            reg.get(Capability.VEHICLE_STATE)

    def test_no_available_raises_with_message(self):
        reg = self._registry()
        p = _FakeProvider(available=False)
        reg.register(p)
        with pytest.raises(CapabilityNotAvailableError) as exc_info:
            reg.get(Capability.VEHICLE_STATE)
        assert "configured" in str(exc_info.value)

    def test_has_capability_true(self):
        reg = self._registry()
        reg.register(_FakeProvider())
        assert reg.has(Capability.VEHICLE_STATE) is True

    def test_has_capability_false(self):
        reg = self._registry()
        assert reg.has(Capability.VEHICLE_STATE) is False

    def test_fetch_delegates(self):
        reg = self._registry()
        reg.register(_FakeProvider(fetch_data={"battery_level": 90}))
        result = reg.fetch(Capability.VEHICLE_STATE, "vehicle_data")
        assert result.ok
        assert result.data["battery_level"] == 90

    def test_fetch_with_fallback_first_ok(self):
        reg = self._registry()
        p1 = _FakeProvider()
        p1.name = "p1"
        p1.priority = ProviderPriority.HIGH
        reg.register(p1)
        result = reg.fetch_with_fallback(Capability.VEHICLE_STATE, "vehicle_data")
        assert result.ok
        assert result.provider == "p1"

    def test_fetch_with_fallback_falls_through(self):
        """First provider fails → falls back to second."""
        reg = self._registry()
        fail = _FakeProvider()
        fail.name = "fail"
        fail.priority = ProviderPriority.HIGH
        fail.fetch = lambda op, **kw: ProviderResult(ok=False, provider="fail", error="down")
        ok = _FakeProvider(fetch_data={"batt": 55})
        ok.name = "ok"
        ok.priority = ProviderPriority.LOW
        reg.register(fail)
        reg.register(ok)
        result = reg.fetch_with_fallback(Capability.VEHICLE_STATE, "vehicle_data")
        assert result.ok
        assert result.provider == "ok"

    def test_fanout_calls_all(self):
        """Fan-out hits every provider with the capability."""
        class NotifyProvider(_FakeProvider):
            capabilities = frozenset({Capability.NOTIFY})
            def execute(self, op, **kw):
                self.called = True
                return ProviderResult(ok=True, provider=self.name)

        reg = self._registry()
        n1 = NotifyProvider()
        n1.name = "n1"
        n1.called = False
        n2 = NotifyProvider()
        n2.name = "n2"
        n2.called = False
        reg.register(n1)
        reg.register(n2)

        results = reg.fanout(Capability.NOTIFY, "push", title="T", body="B")
        assert len(results) == 2
        assert n1.called
        assert n2.called

    def test_fanout_empty_returns_empty(self):
        reg = self._registry()
        results = reg.fanout(Capability.NOTIFY, "push")
        assert results == []

    def test_unregister(self):
        reg = self._registry()
        p   = _FakeProvider()
        reg.register(p)
        assert reg.has(Capability.VEHICLE_STATE)
        reg.unregister("fake")
        assert not reg.has(Capability.VEHICLE_STATE)

    def test_status_returns_rows(self):
        reg = self._registry()
        reg.register(_FakeProvider())
        rows = reg.status()
        assert len(rows) == 1
        assert rows[0]["name"] == "fake"
        assert rows[0]["available"] is True

    def test_capability_map(self):
        reg = self._registry()
        reg.register(_FakeProvider())
        cmap = reg.capability_map()
        assert Capability.VEHICLE_STATE in cmap
        assert "fake" in cmap[Capability.VEHICLE_STATE]

    def test_for_capability_available_only(self):
        reg = self._registry()
        avail = _FakeProvider(available=True)
        avail.name = "avail"
        unavail = _FakeProvider(available=False)
        unavail.name = "unavail"
        reg.register(avail)
        reg.register(unavail)
        all_p = reg.for_capability(Capability.VEHICLE_STATE, available_only=False)
        avail_only = reg.for_capability(Capability.VEHICLE_STATE, available_only=True)
        assert len(all_p)      == 2
        assert len(avail_only) == 1


# ── Provider implementations ──────────────────────────────────────────────────

class TestVehicleApiProvider:
    def _provider(self, **cfg_overrides):
        from tesla_cli.providers.impl.vehicle_api import VehicleApiProvider
        return VehicleApiProvider(_make_cfg(**cfg_overrides))

    def test_capabilities(self):
        p = self._provider()
        assert Capability.VEHICLE_STATE   in p.capabilities
        assert Capability.VEHICLE_COMMAND in p.capabilities
        assert Capability.VEHICLE_LOCATION in p.capabilities

    def test_layer_and_priority(self):
        p = self._provider()
        assert p.layer    == 1
        assert p.priority == ProviderPriority.HIGH

    def test_is_available_with_token(self):
        p = self._provider()
        with patch("keyring.get_password", return_value="tok123"):
            assert p.is_available() is True

    def test_is_available_without_token(self):
        p = self._provider()
        with patch("keyring.get_password", return_value=None):
            assert p.is_available() is False

    def test_fetch_vehicle_data(self):
        p = self._provider()
        mock_backend = MagicMock()
        mock_backend.get_vehicle_data.return_value = {"battery_level": 72}
        with patch("tesla_cli.backends.get_vehicle_backend", return_value=mock_backend), \
             patch("tesla_cli.config.resolve_vin", return_value=MOCK_VIN):
            result = p.fetch("vehicle_data", vin=MOCK_VIN)
        assert result.ok
        assert result.data["battery_level"] == 72
        assert result.provider == "vehicle-api"

    def test_fetch_unknown_operation(self):
        p = self._provider()
        mock_backend = MagicMock()
        with patch("tesla_cli.backends.get_vehicle_backend", return_value=mock_backend), \
             patch("tesla_cli.config.resolve_vin", return_value=MOCK_VIN):
            result = p.fetch("nonexistent_op", vin=MOCK_VIN)
        assert not result.ok
        assert "Unknown" in result.error

    def test_execute_command(self):
        p = self._provider()
        mock_backend = MagicMock()
        mock_backend.command.return_value = {"result": True}
        with patch("tesla_cli.backends.get_vehicle_backend", return_value=mock_backend), \
             patch("tesla_cli.config.resolve_vin", return_value=MOCK_VIN):
            result = p.execute("lock", vin=MOCK_VIN)
        assert result.ok
        mock_backend.command.assert_called_once_with(MOCK_VIN, "lock")


class TestBleProvider:
    def _provider(self, key_path="", binary="/usr/bin/tesla-control"):
        from tesla_cli.providers.impl.ble import BleProvider
        return BleProvider(_make_cfg(**{"ble.key_path": key_path}))

    def test_capabilities(self):
        p = self._provider()
        assert Capability.VEHICLE_COMMAND in p.capabilities

    def test_layer_priority(self):
        p = self._provider()
        assert p.layer    == 0
        assert p.priority == ProviderPriority.CRITICAL

    def test_unavailable_without_binary(self):
        p = self._provider(key_path="/tmp/key.pem")
        with patch("tesla_cli.providers.impl.ble.shutil.which", return_value=None):
            assert p.is_available() is False

    def test_unavailable_without_key(self):
        p = self._provider(key_path="")
        with patch("tesla_cli.providers.impl.ble.shutil.which", return_value="/bin/tc"):
            assert p.is_available() is False

    def test_available_with_both(self):
        p = self._provider(key_path="/tmp/key.pem")
        with patch("tesla_cli.providers.impl.ble.shutil.which", return_value="/bin/tc"):
            assert p.is_available() is True

    def test_execute_lock(self):
        p = self._provider(key_path="/tmp/key.pem")
        mock_run = MagicMock()
        mock_run.returncode = 0
        mock_run.stdout = "ok"
        mock_run.stderr = ""
        with patch("tesla_cli.providers.impl.ble.shutil.which", return_value="/bin/tc"), \
             patch("tesla_cli.providers.impl.ble.subprocess.run", return_value=mock_run):
            result = p.execute("lock", vin=MOCK_VIN)
        assert result.ok
        assert result.provider == "ble"

    def test_execute_failure(self):
        p = self._provider(key_path="/tmp/key.pem")
        mock_run = MagicMock()
        mock_run.returncode = 1
        mock_run.stdout = ""
        mock_run.stderr = "BLE error"
        with patch("tesla_cli.providers.impl.ble.shutil.which", return_value="/bin/tc"), \
             patch("tesla_cli.providers.impl.ble.subprocess.run", return_value=mock_run):
            result = p.execute("lock", vin=MOCK_VIN)
        assert not result.ok
        assert "BLE error" in result.error


class TestTeslaMateProvider:
    def _provider(self, url="postgresql://localhost/tm"):
        from tesla_cli.providers.impl.teslaMate import TeslaMateProvider
        return TeslaMateProvider(_make_cfg(**{"teslaMate.database_url": url}))

    def test_capabilities(self):
        p = self._provider()
        assert Capability.HISTORY_TRIPS   in p.capabilities
        assert Capability.HISTORY_CHARGES in p.capabilities
        assert Capability.HISTORY_STATS   in p.capabilities

    def test_layer_priority(self):
        p = self._provider()
        assert p.layer    == 2
        assert p.priority == ProviderPriority.MEDIUM

    def test_unavailable_without_url(self):
        p = self._provider(url="")
        assert p.is_available() is False

    def test_available_with_url(self):
        p = self._provider()
        assert p.is_available() is True

    def test_fetch_trips(self):
        p = self._provider()
        mock_backend = MagicMock()
        mock_backend.get_trips.return_value = [{"id": 1, "km": 42}]
        with patch("tesla_cli.backends.teslaMate.TeslaMateBacked", return_value=mock_backend):
            result = p.fetch("trips", limit=10)
        assert result.ok
        assert result.data[0]["km"] == 42

    def test_fetch_unknown_operation(self):
        p = self._provider()
        mock_backend = MagicMock()
        with patch("tesla_cli.backends.teslaMate.TeslaMateBacked", return_value=mock_backend):
            result = p.fetch("nonexistent")
        assert not result.ok


class TestAbrpProvider:
    def _provider(self, token="mytoken"):
        from tesla_cli.providers.impl.abrp import AbrpProvider
        return AbrpProvider(_make_cfg(**{"abrp.user_token": token}))

    def test_capabilities(self):
        p = self._provider()
        assert Capability.TELEMETRY_PUSH in p.capabilities

    def test_layer_priority(self):
        p = self._provider()
        assert p.layer    == 3
        assert p.priority == ProviderPriority.LOW

    def test_unavailable_without_token(self):
        p = self._provider(token="")
        assert p.is_available() is False

    def test_execute_push(self):
        p = self._provider()
        data = {
            "charge_state": {"battery_level": 72, "charging_state": "Disconnected", "charger_power": 0},
            "drive_state":  {"speed": 0, "power": 0, "latitude": 37.4, "longitude": -122.0},
            "climate_state": {"inside_temp": 22.0},
        }
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"status": "ok"}'
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__  = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            result = p.execute("push", data=data, vin=MOCK_VIN)
        assert result.ok
        assert result.data["tlm"]["soc"] == 72

    def test_execute_unknown_operation(self):
        p = self._provider()
        result = p.execute("bogus", data={})
        assert not result.ok


class TestHomeAssistantProvider:
    def _provider(self, url="http://ha.local:8123", token="ha_token"):
        from tesla_cli.providers.impl.ha import HomeAssistantProvider
        return HomeAssistantProvider(_make_cfg(**{
            "home_assistant.url": url,
            "home_assistant.token": token,
        }))

    def test_capabilities(self):
        p = self._provider()
        assert Capability.HOME_SYNC in p.capabilities

    def test_unavailable_without_config(self):
        p = self._provider(url="", token="")
        assert p.is_available() is False

    def test_execute_push_success(self):
        p = self._provider()
        data = {
            "charge_state":  {"battery_level": 80, "battery_range": 200.0,
                               "charging_state": "Complete", "charge_limit_soc": 90,
                               "charge_energy_added": 12.0, "charger_power": 0},
            "drive_state":   {"speed": 0, "shift_state": "P", "latitude": 37.4,
                               "longitude": -122.0, "heading": 90},
            "climate_state": {"inside_temp": 22.0, "outside_temp": 18.0, "is_climate_on": False},
            "vehicle_state": {"locked": True, "odometer": 15000.0,
                               "software_version": "2024.14", "is_user_present": False},
        }
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"entity_id":"sensor.tesla_battery_level","state":"80"}'
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__  = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            result = p.execute("push", data=data, vin=MOCK_VIN)
        assert result.ok
        assert result.data["pushed"] > 0


class TestAppriseProvider:
    def _provider(self, enabled=True, urls=None):
        from tesla_cli.providers.impl.apprise_notify import AppriseProvider
        cfg = _make_cfg()
        cfg.notifications.enabled = enabled
        cfg.notifications.apprise_urls = urls or ["tgram://botid/chatid"]
        return AppriseProvider(cfg)

    def test_capabilities(self):
        p = self._provider()
        assert Capability.NOTIFY in p.capabilities

    def test_unavailable_when_disabled(self):
        p = self._provider(enabled=False)
        try:
            import apprise  # noqa: F401
            assert p.is_available() is False
        except ImportError:
            pytest.skip("apprise not installed")

    def test_unavailable_without_apprise_installed(self):
        p = self._provider()
        with patch.dict("sys.modules", {"apprise": None}):
            assert p.is_available() is False

    def test_execute_push(self):
        p = self._provider()
        mock_apprise = MagicMock()
        mock_apprise_instance = MagicMock()
        mock_apprise_instance.notify.return_value = True
        mock_apprise.Apprise.return_value = mock_apprise_instance
        with patch.dict("sys.modules", {"apprise": mock_apprise}):
            result = p.execute("push", title="Test", body="Hello")
        assert result.ok


# ── Registry loader ───────────────────────────────────────────────────────────

class TestLoader:
    def test_build_registry_returns_registry(self):
        from tesla_cli.providers.loader import build_registry
        from tesla_cli.providers.registry import ProviderRegistry
        cfg = _make_cfg()
        with patch("tesla_cli.auth.tokens.get_token", return_value=None):
            reg = build_registry(cfg)
        assert isinstance(reg, ProviderRegistry)

    def test_all_provider_types_registered(self):
        from tesla_cli.providers.loader import build_registry
        cfg = _make_cfg()
        with patch("tesla_cli.auth.tokens.get_token", return_value=None):
            reg = build_registry(cfg)
        names = {p.name for p in reg.all()}
        assert "vehicle-api"     in names
        assert "ble"             in names
        assert "teslaMate"       in names
        assert "abrp"            in names
        assert "home-assistant"  in names
        assert "apprise"         in names
        assert "mqtt"            in names

    def test_seven_providers_registered(self):
        from tesla_cli.providers.loader import build_registry
        cfg = _make_cfg()
        with patch("tesla_cli.auth.tokens.get_token", return_value=None):
            reg = build_registry(cfg)
        assert len(reg.all()) == 7


# ── CLI commands ──────────────────────────────────────────────────────────────

_runner = CliRunner()


def _cli(*args):
    return _runner.invoke(cli_app, list(args))


def _mock_registry():
    from tesla_cli.providers.impl.vehicle_api import VehicleApiProvider
    cfg = _make_cfg()
    reg = ProviderRegistry()
    p = VehicleApiProvider(cfg)
    with patch.object(p, "is_available", return_value=True):
        reg.register(p)
    return reg


class TestProvidersCommand:
    def test_providers_status(self):
        with patch("tesla_cli.providers.get_registry") as mock_reg:
            mock_reg.return_value.status.return_value = [
                {"name": "vehicle-api", "layer": "L1", "priority": 80,
                 "available": True, "capabilities": ["vehicle.state"], "description": "test"}
            ]
            mock_reg.return_value.all.return_value = []
            mock_reg.return_value.get.side_effect = CapabilityNotAvailableError("x")
            mock_reg.return_value.for_capability.return_value = []
            result = _cli("providers", "status")
        assert result.exit_code == 0
        assert "vehicle-api" in result.output

    def test_providers_status_json(self):
        rows = [{"name": "ble", "layer": "L0", "priority": 100,
                 "available": False, "capabilities": ["vehicle.command"], "description": "BLE"}]
        with patch("tesla_cli.providers.get_registry") as mock_reg:
            mock_reg.return_value.status.return_value = rows
            result = _cli("-j", "providers", "status")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["name"] == "ble"

    def test_providers_test(self):
        with patch("tesla_cli.providers.get_registry") as mock_reg:
            mock_reg.return_value.all.return_value = []
            result = _cli("providers", "test")
        assert result.exit_code == 0

    def test_providers_capabilities(self):
        with patch("tesla_cli.providers.get_registry") as mock_reg:
            mock_reg.return_value.for_capability.return_value = []
            result = _cli("providers", "capabilities")
        assert result.exit_code == 0

    def test_providers_in_help(self):
        result = _cli("providers", "--help")
        assert result.exit_code == 0
        assert "status" in result.output
        assert "test" in result.output
        assert "capabilities" in result.output
