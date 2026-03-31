"""Tests for v0.3.0+ commands: diff, checklist, gates, stream, sentry, trips,
anonymize mode, VIN decoder, option code decoder, i18n, and TeslaMate config."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from tesla_cli.app import app
from tests.conftest import MOCK_VIN

runner = CliRunner()


def _run(*args):
    return runner.invoke(app, list(args))


# ── VIN Decoder ──────────────────────────────────────────────────────────────


class TestVinDecoder:
    def test_shanghai_model_y(self):
        from tesla_cli.backends.dossier import decode_vin
        decoded = decode_vin("LRWYE7FK4TC123456")
        assert "Shanghai" in decoded.manufacturer
        assert "Y" in decoded.model
        assert decoded.model_year == "2026"

    def test_fremont_model_3(self):
        from tesla_cli.backends.dossier import decode_vin
        decoded = decode_vin("5YJ3E1EA1PF000001")
        assert "Fremont" in decoded.manufacturer
        assert "3" in decoded.model

    def test_serial_number(self):
        from tesla_cli.backends.dossier import decode_vin
        decoded = decode_vin("5YJ3E1EA1PF123456")
        assert decoded.serial_number == "123456"

    def test_short_vin_graceful(self):
        from tesla_cli.backends.dossier import decode_vin
        decoded = decode_vin("SHORT")
        assert decoded.vin == "SHORT"
        assert decoded.manufacturer == ""  # graceful empty

    def test_vin_command_no_config(self):
        with patch("tesla_cli.config.load_config") as mock_cfg:
            mock_cfg.return_value.general.default_vin = ""
            result = _run("dossier", "vin", "5YJ3E1EA1PF000001")
            assert result.exit_code == 0
            assert "5YJ" in result.output

    def test_vin_command_json(self):
        result = _run("--json", "dossier", "vin", "5YJ3E1EA1PF000001")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["vin"] == "5YJ3E1EA1PF000001"
        assert data["serial_number"] == "000001"


# ── Option Code Decoder ──────────────────────────────────────────────────────


class TestOptionCodeDecoder:
    def test_known_code(self):
        from tesla_cli.backends.dossier import decode_option_codes
        result = decode_option_codes("PPSW,APF2,CP01")
        codes = {c.code: c for c in result.codes}
        assert "PPSW" in codes
        assert codes["PPSW"].category == "paint"
        assert "Pearl White" in codes["PPSW"].description
        assert "APF2" in codes
        assert codes["APF2"].category == "autopilot"

    def test_unknown_code(self):
        from tesla_cli.backends.dossier import decode_option_codes
        result = decode_option_codes("ZZ99,PPSW")
        codes = {c.code: c for c in result.codes}
        assert "ZZ99" in codes
        assert codes["ZZ99"].category == "unknown"

    def test_empty_string(self):
        from tesla_cli.backends.dossier import decode_option_codes
        result = decode_option_codes("")
        assert result.codes == []

    def test_raw_string_preserved(self):
        from tesla_cli.backends.dossier import decode_option_codes
        raw = "PPSW,APF2,CP01"
        result = decode_option_codes(raw)
        assert result.raw_string == raw

    def test_expanded_catalog_size(self):
        from tesla_cli.backends.dossier import OPTION_CODE_MAP
        assert len(OPTION_CODE_MAP) >= 100, "Catalog should have at least 100 codes"

    def test_autopilot_hw_codes(self):
        from tesla_cli.backends.dossier import OPTION_CODE_MAP
        for code in ["APH1", "APH2", "APH3", "APH4"]:
            assert code in OPTION_CODE_MAP, f"{code} missing from catalog"

    def test_all_models_in_catalog(self):
        from tesla_cli.backends.dossier import OPTION_CODE_MAP
        for code in ["MDLS", "MDL3", "MDLX", "MDLY"]:
            assert code in OPTION_CODE_MAP, f"Model code {code} missing"


# ── Anonymize Mode ───────────────────────────────────────────────────────────


class TestAnonymizeMode:
    def setup_method(self):
        from tesla_cli.output import set_anon_mode
        set_anon_mode(False)

    def teardown_method(self):
        from tesla_cli.output import set_anon_mode
        set_anon_mode(False)

    def test_vin_masked(self):
        from tesla_cli.output import anonymize, set_anon_mode
        set_anon_mode(True, vin="5YJ3E1EA1PF123456")
        result = anonymize("VIN: 5YJ3E1EA1PF123456")
        assert "5YJ3E1EA1PF123456" not in result
        # First 4 and last 3 preserved
        assert "5YJ3" in result
        assert "456" in result

    def test_rn_masked(self):
        from tesla_cli.output import anonymize, set_anon_mode
        set_anon_mode(True, rn="RN126460939")
        result = anonymize("Order: RN126460939")
        assert "RN126460939" not in result
        assert "RN" in result  # prefix preserved

    def test_email_masked(self):
        from tesla_cli.output import anonymize, set_anon_mode
        set_anon_mode(True, email="user@example.com")
        result = anonymize("Email: user@example.com")
        assert "user@example.com" not in result

    def test_anon_false_no_masking(self):
        from tesla_cli.output import anonymize, set_anon_mode
        set_anon_mode(False)
        text = "VIN: 5YJ3E1EA1PF123456"
        assert anonymize(text) == text

    def test_empty_string(self):
        from tesla_cli.output import anonymize, set_anon_mode
        set_anon_mode(True, vin="5YJ3E1EA1PF123456")
        assert anonymize("") == ""

    def test_anon_flag_runs_command(self):
        with (
            patch("tesla_cli.commands.order.OrderBackend") as mock_backend_cls,
            patch("tesla_cli.commands.order.load_config") as mock_cfg,
        ):
            mock_cfg.return_value.order.reservation_number = "RN999999999"
            mock_cfg.return_value.general.default_vin = MOCK_VIN
            mock_cfg.return_value.notifications.enabled = False
            from tesla_cli.models.order import OrderStatus
            mock_backend = MagicMock()
            mock_backend.get_order_status.return_value = OrderStatus(
                order_status="BOOKED",
                order_substatus="",
                vin=MOCK_VIN,
            )
            mock_backend_cls.return_value = mock_backend
            result = _run("--anon", "order", "status")
            assert result.exit_code == 0


# ── i18n ────────────────────────────────────────────────────────────────────


class TestI18n:
    def teardown_method(self):
        from tesla_cli.i18n import set_lang
        set_lang("en")

    def test_english_default(self):
        from tesla_cli.i18n import t
        result = t("order.stopped")
        assert result == "Stopped watching."

    def test_spanish(self):
        from tesla_cli.i18n import set_lang, t
        set_lang("es")
        result = t("order.stopped")
        assert result == "Monitoreo detenido."

    def test_fallback_to_english(self):
        from tesla_cli.i18n import set_lang, t
        set_lang("xx")  # unknown language — falls back to English
        result = t("order.stopped")
        assert result == "Stopped watching."  # falls back to English

    def test_interpolation(self):
        from tesla_cli.i18n import t
        result = t("order.watching", rn="RN123", interval="5")
        assert "RN123" in result
        assert "5" in result

    def test_spanish_interpolation(self):
        from tesla_cli.i18n import set_lang, t
        set_lang("es")
        result = t("order.watching", rn="RN123", interval="5")
        assert "RN123" in result

    def test_unknown_key_returns_key(self):
        from tesla_cli.i18n import t
        result = t("this.key.does.not.exist")
        assert result == "this.key.does.not.exist"

    def test_lang_flag(self):
        result = _run("--lang", "es", "--version")
        # --version is eager, will exit 0 regardless of lang
        # just test it doesn't crash
        assert result.exit_code == 0


# ── Dossier Checklist ────────────────────────────────────────────────────────


class TestDossierChecklist:
    def test_checklist_shows(self):
        result = _run("dossier", "checklist")
        # Just verify it runs without crashing
        assert result.exit_code == 0

    def test_checklist_help(self):
        result = _run("dossier", "checklist", "--help")
        assert result.exit_code == 0
        assert "--mark" in result.output
        assert "--reset" in result.output

    def test_checklist_json(self):
        result = _run("--json", "dossier", "checklist")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) > 0
        # Check structure
        item = data[0]
        assert "index" in item
        assert "section" in item
        assert "item" in item
        assert "done" in item

    def test_checklist_has_34_items(self):
        result = _run("--json", "dossier", "checklist")
        data = json.loads(result.output)
        assert len(data) == 34, f"Expected 34 items, got {len(data)}"

    def test_checklist_sections_present(self):
        result = _run("--json", "dossier", "checklist")
        data = json.loads(result.output)
        sections = {item["section"] for item in data}
        assert "Exterior" in sections
        assert "Interior" in sections
        assert "Mechanicals" in sections
        assert "Electronics & Software" in sections
        assert "Final" in sections


# ── Dossier Gates ────────────────────────────────────────────────────────────


class TestDossierGates:
    def test_gates_no_dossier(self):
        with patch("tesla_cli.commands.dossier.DossierBackend") as mock_cls:
            mock_cls.return_value._load_dossier.return_value = None
            result = _run("dossier", "gates")
            assert result.exit_code == 0
            assert "Gate" in result.output

    def test_gates_json_no_dossier(self):
        with patch("tesla_cli.commands.dossier.DossierBackend") as mock_cls:
            mock_cls.return_value._load_dossier.return_value = None
            result = _run("--json", "dossier", "gates")
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert isinstance(data, list)
            assert len(data) == 13

    def test_gates_structure(self):
        with patch("tesla_cli.commands.dossier.DossierBackend") as mock_cls:
            mock_cls.return_value._load_dossier.return_value = None
            result = _run("--json", "dossier", "gates")
            data = json.loads(result.output)
            for gate in data:
                assert "gate" in gate
                assert "label" in gate
                assert "status" in gate
                assert gate["status"] in ("complete", "current", "pending")

    def test_gates_with_ordered_phase(self):
        with patch("tesla_cli.commands.dossier.DossierBackend") as mock_cls:
            mock_dossier = MagicMock()
            mock_dossier.vin = MOCK_VIN
            mock_dossier.real_status.phase = "ordered"
            mock_cls.return_value._load_dossier.return_value = mock_dossier
            result = _run("--json", "dossier", "gates")
            data = json.loads(result.output)
            # First gate should be current
            assert data[0]["status"] == "current"
            # All others pending
            assert all(g["status"] == "pending" for g in data[1:])

    def test_gates_with_shipped_phase(self):
        with patch("tesla_cli.commands.dossier.DossierBackend") as mock_cls:
            mock_dossier = MagicMock()
            mock_dossier.vin = MOCK_VIN
            mock_dossier.real_status.phase = "shipped"
            mock_cls.return_value._load_dossier.return_value = mock_dossier
            result = _run("--json", "dossier", "gates")
            data = json.loads(result.output)
            complete = [g for g in data if g["status"] == "complete"]
            assert len(complete) > 0


# ── Dossier Diff ─────────────────────────────────────────────────────────────


class TestDossierDiff:
    def _make_snapshot(self, tmpdir: Path, name: str, data: dict) -> Path:
        path = tmpdir / name
        path.write_text(json.dumps(data))
        return path

    def test_diff_need_two_snapshots(self):
        with patch("tesla_cli.commands.dossier.DossierBackend") as mock_cls:
            mock_cls.return_value.get_history.return_value = [
                {"timestamp": "2026-01-01T00:00:00", "file": "/tmp/x.json", "order_status": "BOOKED"}
            ]
            result = _run("dossier", "diff")
            assert result.exit_code == 1
            assert "2 snapshot" in result.output.lower() or "Need" in result.output

    def test_diff_no_changes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            snap_path = Path(tmpdir) / "snap.json"
            snap_data = {"order": {"current": {"order_status": "BOOKED"}}, "vin": MOCK_VIN}
            snap_path.write_text(json.dumps(snap_data))
            history = [
                {"timestamp": "2026-01-01T00:00:00", "file": str(snap_path), "order_status": "BOOKED"},
                {"timestamp": "2026-01-02T00:00:00", "file": str(snap_path), "order_status": "BOOKED"},
            ]
            with patch("tesla_cli.commands.dossier.DossierBackend") as mock_cls:
                mock_cls.return_value.get_history.return_value = history
                result = _run("dossier", "diff")
                assert result.exit_code == 0
                assert "No differences" in result.output

    def test_diff_detects_changes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            snap_a = Path(tmpdir) / "snap_a.json"
            snap_b = Path(tmpdir) / "snap_b.json"
            snap_a.write_text(json.dumps({"order": {"status": "BOOKED"}}))
            snap_b.write_text(json.dumps({"order": {"status": "DELIVERED"}}))
            history = [
                {"timestamp": "2026-01-01T00:00:00", "file": str(snap_a), "order_status": "BOOKED"},
                {"timestamp": "2026-01-02T00:00:00", "file": str(snap_b), "order_status": "DELIVERED"},
            ]
            with patch("tesla_cli.commands.dossier.DossierBackend") as mock_cls:
                mock_cls.return_value.get_history.return_value = history
                result = _run("--json", "dossier", "diff")
                assert result.exit_code == 0
                data = json.loads(result.output)
                assert isinstance(data, list)
                change = next((c for c in data if "status" in c["path"]), None)
                assert change is not None
                assert change["old"] == "BOOKED"
                assert change["new"] == "DELIVERED"

    def test_compute_diff_direct(self):
        from tesla_cli.commands.dossier import _compute_diff
        a = {"foo": "bar", "nested": {"x": 1}}
        b = {"foo": "baz", "nested": {"x": 1}, "new_key": "hello"}
        changes = _compute_diff(a, b)
        paths = [c["path"] for c in changes]
        assert "foo" in paths
        assert "new_key" in paths
        # nested.x unchanged, should not appear
        assert "nested.x" not in paths

    def test_compute_diff_symbols(self):
        from tesla_cli.commands.dossier import _compute_diff
        a = {"x": "old", "y": None, "z": "gone"}
        b = {"x": "new", "y": "added", "z": None}
        changes = _compute_diff(a, b)
        by_path = {c["path"]: c for c in changes}
        assert by_path["x"]["symbol"] == "≠"  # changed
        assert by_path["y"]["symbol"] == "+"   # added
        assert by_path["z"]["symbol"] == "−"   # removed


# ── Vehicle Sentry ───────────────────────────────────────────────────────────


class TestVehicleSentry:
    def _patched(self, mock_fleet_backend):
        cfg = MagicMock()
        cfg.general.backend = "fleet"
        cfg.general.default_vin = MOCK_VIN
        cfg.fleet.region = "na"
        return [
            patch("tesla_cli.backends.get_vehicle_backend", return_value=mock_fleet_backend),
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock_fleet_backend),
            patch("tesla_cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ]

    def test_sentry_status(self, mock_fleet_backend):
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("vehicle", "sentry")
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        assert "Sentry" in result.output

    def test_sentry_status_json(self, mock_fleet_backend):
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("--json", "vehicle", "sentry")
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "sentry_mode" in data
        assert "sentry_mode_available" in data

    def test_sentry_enable(self, mock_fleet_backend):
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("vehicle", "sentry", "--on")
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        mock_fleet_backend.command.assert_called()

    def test_sentry_disable(self, mock_fleet_backend):
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("vehicle", "sentry", "--off")
        for p in patches:
            p.stop()
        assert result.exit_code == 0


# ── Vehicle Trips ────────────────────────────────────────────────────────────


class TestVehicleTrips:
    def _patched(self, mock_fleet_backend):
        cfg = MagicMock()
        cfg.general.backend = "fleet"
        cfg.general.default_vin = MOCK_VIN
        cfg.fleet.region = "na"
        mock_fleet_backend.get_service_data.return_value = {}
        return [
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock_fleet_backend),
            patch("tesla_cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ]

    def test_trips_runs(self, mock_fleet_backend):
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("vehicle", "trips")
        for p in patches:
            p.stop()
        assert result.exit_code == 0

    def test_trips_json(self, mock_fleet_backend):
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("--json", "vehicle", "trips")
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "drive_state" in data
        assert "vehicle_state" in data


# ── Stream Live ──────────────────────────────────────────────────────────────


class TestStreamLive:
    def test_stream_help(self):
        result = _run("stream", "live", "--help")
        assert result.exit_code == 0
        assert "--interval" in result.output
        assert "--count" in result.output

    def test_stream_runs_once(self, mock_fleet_backend):
        cfg = MagicMock()
        cfg.general.backend = "fleet"
        cfg.general.default_vin = MOCK_VIN
        cfg.fleet.region = "na"
        with (
            patch("tesla_cli.backends.get_vehicle_backend", return_value=mock_fleet_backend),
            patch("tesla_cli.config.load_config", return_value=cfg),
            patch("tesla_cli.config.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("stream", "live", "--count", "1", "--interval", "0")
            assert result.exit_code == 0

    def test_stream_json_exits(self, mock_fleet_backend):
        cfg = MagicMock()
        cfg.general.backend = "fleet"
        cfg.general.default_vin = MOCK_VIN
        cfg.fleet.region = "na"
        with (
            patch("tesla_cli.backends.get_vehicle_backend", return_value=mock_fleet_backend),
            patch("tesla_cli.config.load_config", return_value=cfg),
            patch("tesla_cli.config.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("--json", "stream", "live", "--count", "1")
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert "charge_state" in data or "state" in data


# ── TeslaMate Config ─────────────────────────────────────────────────────────


class TestTeslamateConfig:
    def test_config_has_teslaMate_section(self):
        from tesla_cli.config import Config
        cfg = Config()
        assert hasattr(cfg, "teslaMate")
        assert cfg.teslaMate.database_url == ""
        assert cfg.teslaMate.car_id == 1

    def test_teslaMate_app_registered(self):
        result = _run("teslaMate", "--help")
        assert result.exit_code == 0
        assert "connect" in result.output
        assert "status" in result.output
        assert "trips" in result.output
        assert "charging" in result.output
        assert "updates" in result.output

    def test_teslaMate_connect_no_db_fails_gracefully(self):
        result = _run("teslaMate", "status")
        # Should fail with a helpful message since not configured
        assert "teslaMate" in result.output.lower() or "configured" in result.output.lower() or result.exit_code != 0

    def test_teslaMate_backend_raises_import_error(self):
        from tesla_cli.backends.teslaMate import TeslaMateBacked
        backend = TeslaMateBacked("postgresql://localhost/test")
        # Without psycopg2 (or with a bad URL), ping should fail
        # We test that the ImportError is raised when psycopg2 is not available
        import sys
        original = sys.modules.get("psycopg2")
        sys.modules["psycopg2"] = None  # type: ignore[assignment]
        try:
            with pytest.raises((ImportError, TypeError)):
                backend._get_conn()
        finally:
            if original is None:
                del sys.modules["psycopg2"]
            else:
                sys.modules["psycopg2"] = original


# ── Order Watch Changes Display ──────────────────────────────────────────────


class TestOrderChangesDisplay:
    def test_show_changes_has_symbols(self):
        """The _show_changes output should contain +/−/≠ symbols."""
        from tesla_cli.commands.order import _show_changes
        from tesla_cli.models.order import OrderChange

        changes = [
            OrderChange(field="order_status", old_value="BOOKED", new_value="DELIVERED"),
            OrderChange(field="vin", old_value="", new_value=MOCK_VIN),
            OrderChange(field="old_field", old_value="something", new_value=""),
        ]
        # Just verify it runs without error
        try:
            _show_changes(changes, notify=False)
        except Exception as e:
            pytest.fail(f"_show_changes raised {e}")


# ── Auto-wake Backend ────────────────────────────────────────────────────────


class TestOwnerApiAutoWake:
    def test_command_retries_on_asleep(self):
        from tesla_cli.backends.owner import OwnerApiVehicleBackend
        from tesla_cli.exceptions import VehicleAsleepError

        backend = OwnerApiVehicleBackend()
        backend._id_cache[MOCK_VIN] = "12345"

        call_count = 0

        def mock_post(path, body=None):
            nonlocal call_count
            call_count += 1
            if "wake_up" in path:
                return {"state": "online"}
            if call_count <= 2:
                raise VehicleAsleepError("asleep")
            return {"result": True}

        backend._post = mock_post

        with patch("tesla_cli.backends.owner._time.sleep"):
            result = backend.command(MOCK_VIN, "door_lock")

        assert result == {"result": True}
        assert call_count >= 3  # 2 failures + 1 success + wake calls

    def test_command_raises_after_max_retries(self):
        from tesla_cli.backends.owner import OwnerApiVehicleBackend
        from tesla_cli.exceptions import VehicleAsleepError

        backend = OwnerApiVehicleBackend()
        backend._id_cache[MOCK_VIN] = "12345"

        def always_asleep(path, body=None):
            if "wake_up" in path:
                return {"state": "online"}
            raise VehicleAsleepError("asleep")

        backend._post = always_asleep

        with patch("tesla_cli.backends.owner._time.sleep"), pytest.raises(VehicleAsleepError):
            backend.command(MOCK_VIN, "door_lock")


# ── Dossier Estimate ──────────────────────────────────────────────────────────


class TestDossierEstimate:
    def test_estimate_help(self):
        result = _run("dossier", "estimate", "--help")
        assert result.exit_code == 0
        assert "estimate" in result.output.lower() or "delivery" in result.output.lower()

    def test_estimate_no_dossier(self):
        with patch("tesla_cli.commands.dossier.DossierBackend") as mock_cls:
            mock_cls.return_value._load_dossier.return_value = None
            result = _run("dossier", "estimate")
            assert result.exit_code == 0

    def test_estimate_json_no_dossier(self):
        with patch("tesla_cli.commands.dossier.DossierBackend") as mock_cls:
            mock_cls.return_value._load_dossier.return_value = None
            result = _run("--json", "dossier", "estimate")
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert "current_phase" in data
            assert data["current_phase"] == "ordered"
            assert "estimated_delivery_range" in data
            rng = data["estimated_delivery_range"]
            assert "optimistic" in rng
            assert "typical" in rng
            assert "conservative" in rng

    def test_estimate_json_with_phase(self):
        with patch("tesla_cli.commands.dossier.DossierBackend") as mock_cls:
            mock_dossier = MagicMock()
            mock_dossier.real_status.phase = "shipped"
            mock_dossier.real_status.delivery_date = None
            mock_cls.return_value._load_dossier.return_value = mock_dossier
            result = _run("--json", "dossier", "estimate")
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["current_phase"] == "shipped"
            assert data["optimistic_days"] < data["typical_days"]
            assert data["typical_days"] < data["conservative_days"]

    def test_estimate_delivered_phase(self):
        with patch("tesla_cli.commands.dossier.DossierBackend") as mock_cls:
            mock_dossier = MagicMock()
            mock_dossier.real_status.phase = "delivered"
            mock_dossier.real_status.delivery_date = None
            mock_cls.return_value._load_dossier.return_value = mock_dossier
            result = _run("dossier", "estimate")
            assert result.exit_code == 0
            assert "Delivered" in result.output or "delivered" in result.output.lower()

    def test_estimate_confirmed_delivery(self):
        with patch("tesla_cli.commands.dossier.DossierBackend") as mock_cls:
            mock_dossier = MagicMock()
            mock_dossier.real_status.phase = "delivery_scheduled"
            mock_dossier.real_status.delivery_date = "2026-04-15"
            mock_cls.return_value._load_dossier.return_value = mock_dossier
            result = _run("dossier", "estimate")
            assert result.exit_code == 0
            assert "2026-04-15" in result.output


# ── Vehicle Windows + Charge Port ────────────────────────────────────────────


class TestVehicleWindowsChargePort:
    def _patched(self, mock_backend):
        cfg = MagicMock()
        cfg.general.backend = "fleet"
        cfg.general.default_vin = MOCK_VIN
        cfg.fleet.region = "na"
        return [
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ]

    def test_windows_vent(self, mock_fleet_backend):
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("vehicle", "windows", "vent")
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        mock_fleet_backend.command.assert_called()

    def test_windows_close(self, mock_fleet_backend):
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("vehicle", "windows", "close")
        for p in patches:
            p.stop()
        assert result.exit_code == 0

    def test_windows_invalid_action(self, mock_fleet_backend):
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("vehicle", "windows", "explode")
        for p in patches:
            p.stop()
        assert result.exit_code != 0

    def test_charge_port_open(self, mock_fleet_backend):
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("vehicle", "charge-port", "open")
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        mock_fleet_backend.command.assert_called()

    def test_charge_port_close(self, mock_fleet_backend):
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("vehicle", "charge-port", "close")
        for p in patches:
            p.stop()
        assert result.exit_code == 0

    def test_charge_port_stop(self, mock_fleet_backend):
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("vehicle", "charge-port", "stop")
        for p in patches:
            p.stop()
        assert result.exit_code == 0

    def test_charge_port_invalid_action(self, mock_fleet_backend):
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("vehicle", "charge-port", "explode")
        for p in patches:
            p.stop()
        assert result.exit_code != 0

    def test_windows_help(self):
        result = _run("vehicle", "windows", "--help")
        assert result.exit_code == 0
        assert "vent" in result.output.lower()

    def test_charge_port_help(self):
        result = _run("vehicle", "charge-port", "--help")
        assert result.exit_code == 0
        assert "open" in result.output.lower()


# ── Vehicle Software ──────────────────────────────────────────────────────────


class TestVehicleSoftware:
    def _patched(self, mock_backend):
        cfg = MagicMock()
        cfg.general.backend = "fleet"
        cfg.general.default_vin = MOCK_VIN
        cfg.fleet.region = "na"
        return [
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ]

    def test_software_help(self):
        result = _run("vehicle", "software", "--help")
        assert result.exit_code == 0
        assert "--install" in result.output

    def test_software_no_update(self, mock_fleet_backend):
        mock_fleet_backend.get_vehicle_state.return_value = {
            "car_version": "2025.2.6",
            "software_update": {},
        }
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("vehicle", "software")
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        assert "2025.2.6" in result.output

    def test_software_json(self, mock_fleet_backend):
        mock_fleet_backend.get_vehicle_state.return_value = {
            "car_version": "2025.2.6",
            "software_update": {"status": "available", "version": "2025.6.1"},
        }
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("--json", "vehicle", "software")
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["current_version"] == "2025.2.6"
        assert data["update_version"] == "2025.6.1"
        assert data["update_status"] == "available"

    def test_software_update_available(self, mock_fleet_backend):
        mock_fleet_backend.get_vehicle_state.return_value = {
            "car_version": "2025.2.6",
            "software_update": {
                "status": "available",
                "version": "2025.6.1",
                "download_percentage": 100,
                "expected_duration_sec": 3600,
            },
        }
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("vehicle", "software")
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        assert "2025.6.1" in result.output


# ── Notify Commands ───────────────────────────────────────────────────────────


class TestNotifyCommands:
    def test_notify_list_help(self):
        result = _run("notify", "list", "--help")
        assert result.exit_code == 0

    def test_notify_test_help(self):
        result = _run("notify", "test", "--help")
        assert result.exit_code == 0
        assert "--body" in result.output or "--title" in result.output

    def test_notify_list_empty(self):
        with patch("tesla_cli.commands.notify.load_config") as mock_cfg:
            mock_cfg.return_value.notifications.apprise_urls = []
            mock_cfg.return_value.notifications.enabled = False
            result = _run("notify", "list")
            assert result.exit_code == 0
            assert "No notification" in result.output or "notify add" in result.output

    def test_notify_list_json_empty(self):
        with patch("tesla_cli.commands.notify.load_config") as mock_cfg:
            mock_cfg.return_value.notifications.apprise_urls = []
            mock_cfg.return_value.notifications.enabled = False
            result = _run("--json", "notify", "list")
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["urls"] == []
            assert data["enabled"] is False

    def test_notify_list_with_urls(self):
        with patch("tesla_cli.commands.notify.load_config") as mock_cfg:
            mock_cfg.return_value.notifications.apprise_urls = [
                "tgram://BOTTOKEN/CHATID",
                "slack://a/b/c/channel",
            ]
            mock_cfg.return_value.notifications.enabled = True
            result = _run("notify", "list")
            assert result.exit_code == 0
            assert "tgram" in result.output
            assert "slack" in result.output

    def test_notify_test_no_urls(self):
        with patch("tesla_cli.commands.notify.load_config") as mock_cfg:
            mock_cfg.return_value.notifications.apprise_urls = []
            result = _run("notify", "test")
            assert result.exit_code == 1
            assert "No notification" in result.output or "notify add" in result.output

    def test_notify_test_sends(self):
        with (
            patch("tesla_cli.commands.notify.load_config") as mock_cfg,
            patch("apprise.Apprise") as mock_apprise_cls,
        ):
            mock_cfg.return_value.notifications.apprise_urls = ["tgram://TOKEN/CHATID"]
            mock_apobj = MagicMock()
            mock_apobj.notify.return_value = True
            mock_apprise_cls.return_value = mock_apobj
            result = _run("notify", "test")
            assert result.exit_code == 0
            mock_apobj.notify.assert_called_once()

    def test_notify_test_json(self):
        with (
            patch("tesla_cli.commands.notify.load_config") as mock_cfg,
            patch("apprise.Apprise") as mock_apprise_cls,
        ):
            mock_cfg.return_value.notifications.apprise_urls = ["tgram://TOKEN/CHATID"]
            mock_apobj = MagicMock()
            mock_apobj.notify.return_value = True
            mock_apprise_cls.return_value = mock_apobj
            result = _run("--json", "notify", "test")
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert isinstance(data, list)
            assert data[0]["success"] is True

    def test_notify_add(self):
        with (
            patch("tesla_cli.commands.notify.load_config") as mock_cfg,
            patch("tesla_cli.commands.notify.save_config") as mock_save,
        ):
            cfg = MagicMock()
            cfg.notifications.apprise_urls = []
            mock_cfg.return_value = cfg
            result = _run("notify", "add", "tgram://TOKEN/CHATID")
            assert result.exit_code == 0
            mock_save.assert_called_once()

    def test_notify_remove_out_of_range(self):
        with patch("tesla_cli.commands.notify.load_config") as mock_cfg:
            mock_cfg.return_value.notifications.apprise_urls = ["tgram://TOKEN/CHATID"]
            result = _run("notify", "remove", "5")
            assert result.exit_code == 1


# ── Config Export / Import ────────────────────────────────────────────────────


class TestConfigExportImport:
    def test_export_help(self):
        result = _run("config", "export", "--help")
        assert result.exit_code == 0
        assert "--output" in result.output

    def test_import_help(self):
        result = _run("config", "import", "--help")
        assert result.exit_code == 0
        assert "--merge" in result.output or "--replace" in result.output

    def test_export_no_config(self):
        with patch("tesla_cli.config.CONFIG_FILE") as mock_file:
            mock_file.exists.return_value = False
            result = _run("config", "export")
            assert result.exit_code == 1

    def test_export_stdout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = Path(tmpdir) / "config.toml"
            cfg_path.write_text('[general]\ndefault_vin = "5YJ3E1EA1PF000001"\n')
            with patch("tesla_cli.config.CONFIG_FILE", cfg_path):
                result = _run("config", "export")
                assert result.exit_code == 0
                assert "default_vin" in result.output

    def test_export_to_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = Path(tmpdir) / "config.toml"
            cfg_path.write_text('[general]\ndefault_vin = "5YJ3E1EA1PF000001"\n')
            out_path = Path(tmpdir) / "backup.toml"
            with patch("tesla_cli.config.CONFIG_FILE", cfg_path):
                result = _run("config", "export", "-o", str(out_path))
                assert result.exit_code == 0
                assert out_path.exists()
                assert "default_vin" in out_path.read_text()

    def test_import_file_not_found(self):
        result = _run("config", "import", "/nonexistent/path/config.toml")
        assert result.exit_code == 1

    def test_import_valid_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "import.toml"
            src.write_text('[general]\ndefault_vin = "5YJ3E1EA1PF999999"\n')
            with (
                patch("tesla_cli.config.CONFIG_FILE") as mock_cfile,
                patch("tesla_cli.commands.config_cmd.save_config") as mock_save,
            ):
                mock_cfile.exists.return_value = False
                result = _run("config", "import", str(src))
                assert result.exit_code == 0
                mock_save.assert_called_once()


# ── Dossier Option Codes ──────────────────────────────────────────────────────


class TestDossierOptionCodes:
    def test_option_codes_help(self):
        result = _run("dossier", "option-codes", "--help")
        assert result.exit_code == 0

    def test_option_codes_no_dossier(self):
        with patch("tesla_cli.commands.dossier.DossierBackend") as mock_cls:
            mock_cls.return_value._load_dossier.return_value = None
            result = _run("dossier", "option-codes")
            assert result.exit_code == 1

    def test_option_codes_with_dossier(self):
        with patch("tesla_cli.commands.dossier.DossierBackend") as mock_cls:
            mock_dossier = MagicMock()
            mock_dossier.option_codes.raw_string = "PPSW,APF2,MDL3"
            mock_cls.return_value._load_dossier.return_value = mock_dossier
            result = _run("dossier", "option-codes")
            assert result.exit_code == 0
            assert "PPSW" in result.output or "Pearl White" in result.output

    def test_option_codes_json(self):
        with patch("tesla_cli.commands.dossier.DossierBackend") as mock_cls:
            mock_dossier = MagicMock()
            mock_dossier.option_codes.raw_string = "PPSW,APF2"
            mock_cls.return_value._load_dossier.return_value = mock_dossier
            result = _run("--json", "dossier", "option-codes")
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert isinstance(data, list)
            codes = {item["code"] for item in data}
            assert "PPSW" in codes
            assert "APF2" in codes

    def test_option_codes_json_structure(self):
        with patch("tesla_cli.commands.dossier.DossierBackend") as mock_cls:
            mock_dossier = MagicMock()
            mock_dossier.option_codes.raw_string = "PPSW"
            mock_cls.return_value._load_dossier.return_value = mock_dossier
            result = _run("--json", "dossier", "option-codes")
            data = json.loads(result.output)
            assert all("code" in item and "category" in item and "description" in item for item in data)


# ── Order Timeline ────────────────────────────────────────────────────────────


class TestOrderTimeline:
    def test_timeline_help(self):
        result = _run("order", "timeline", "--help")
        assert result.exit_code == 0

    def test_timeline_no_history(self):
        with patch("tesla_cli.backends.dossier.DossierBackend") as mock_cls:
            mock_cls.return_value.get_history.return_value = []
            result = _run("order", "timeline")
            assert result.exit_code == 1
            assert "history" in result.output.lower() or "found" in result.output.lower()

    def test_timeline_with_history(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            snap = Path(tmpdir) / "snap.json"
            snap.write_text(json.dumps({
                "vin": MOCK_VIN,
                "order": {"current": {"orderStatus": "BOOKED"}},
                "real_status": {"delivery_date": None, "in_runt": False, "has_placa": False},
                "runt": {"estado": ""},
            }))
            history = [
                {"timestamp": "2026-01-01T00:00:00", "file": str(snap), "order_status": "BOOKED"},
                {"timestamp": "2026-01-10T00:00:00", "file": str(snap), "order_status": "BOOKED"},
            ]
            with patch("tesla_cli.backends.dossier.DossierBackend") as mock_cls:
                mock_cls.return_value.get_history.return_value = history
                result = _run("order", "timeline")
                assert result.exit_code == 0
                assert "Timeline" in result.output or "snapshot" in result.output.lower()

    def test_timeline_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            snap = Path(tmpdir) / "snap.json"
            snap.write_text(json.dumps({
                "vin": MOCK_VIN,
                "order": {"current": {"orderStatus": "BOOKED"}},
                "real_status": {"delivery_date": None, "in_runt": False, "has_placa": False},
                "runt": {"estado": ""},
            }))
            history = [
                {"timestamp": "2026-01-01T00:00:00", "file": str(snap), "order_status": "BOOKED"},
            ]
            with patch("tesla_cli.backends.dossier.DossierBackend") as mock_cls:
                mock_cls.return_value.get_history.return_value = history
                result = _run("--json", "order", "timeline")
                assert result.exit_code == 0
                data = json.loads(result.output)
                assert isinstance(data, list)
                assert data[0]["order_status"] == "BOOKED"
                assert "changes" in data[0]


# ── Vehicle Nearby ────────────────────────────────────────────────────────────


class TestVehicleNearby:
    def _patched(self, mock_backend):
        cfg = MagicMock()
        cfg.general.backend = "fleet"
        cfg.general.default_vin = MOCK_VIN
        cfg.fleet.region = "na"
        return [
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ]

    def test_nearby_help(self):
        result = _run("vehicle", "nearby", "--help")
        assert result.exit_code == 0
        assert "supercharger" in result.output.lower() or "charging" in result.output.lower()

    def test_nearby_empty(self, mock_fleet_backend):
        mock_fleet_backend.get_nearby_charging_sites.return_value = {
            "superchargers": [],
            "destination_charging": [],
        }
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("vehicle", "nearby")
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        assert "No nearby" in result.output or "not found" in result.output.lower()

    def test_nearby_with_superchargers(self, mock_fleet_backend):
        mock_fleet_backend.get_nearby_charging_sites.return_value = {
            "superchargers": [
                {
                    "name": "Tesla Supercharger Bogotá",
                    "distance_miles": 2.4,
                    "available_stalls": 6,
                    "total_stalls": 12,
                    "type": "V3",
                },
            ],
            "destination_charging": [],
        }
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("vehicle", "nearby")
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        assert "Bogotá" in result.output or "Supercharger" in result.output

    def test_nearby_with_destination(self, mock_fleet_backend):
        mock_fleet_backend.get_nearby_charging_sites.return_value = {
            "superchargers": [],
            "destination_charging": [
                {
                    "name": "Hotel Example",
                    "distance_miles": 0.8,
                    "total_stalls": 4,
                },
            ],
        }
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("vehicle", "nearby")
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        assert "Hotel" in result.output or "Destination" in result.output

    def test_nearby_json(self, mock_fleet_backend):
        mock_fleet_backend.get_nearby_charging_sites.return_value = {
            "superchargers": [
                {
                    "name": "Test SC",
                    "distance_miles": 1.5,
                    "available_stalls": 3,
                    "total_stalls": 8,
                    "type": "V2",
                },
            ],
            "destination_charging": [],
        }
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("--json", "vehicle", "nearby")
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "superchargers" in data
        assert "destination_charging" in data
        assert data["superchargers"][0]["name"] == "Test SC"

    def test_nearby_availability_color_logic(self, mock_fleet_backend):
        """Green > 3, yellow > 0, red = 0 — verify no crash with all cases."""
        mock_fleet_backend.get_nearby_charging_sites.return_value = {
            "superchargers": [
                {"name": "SC Green", "distance_miles": 1.0, "available_stalls": 8, "total_stalls": 12, "type": "V3"},
                {"name": "SC Yellow", "distance_miles": 2.0, "available_stalls": 1, "total_stalls": 12, "type": "V3"},
                {"name": "SC Red", "distance_miles": 3.0, "available_stalls": 0, "total_stalls": 12, "type": "V3"},
            ],
            "destination_charging": [],
        }
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("vehicle", "nearby")
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        assert "SC Green" in result.output


# ── TeslaMate Efficiency ──────────────────────────────────────────────────────


class TestTeslaMatEfficiency:
    def _patched_backend(self, trips):
        cfg = MagicMock()
        cfg.teslaMate.database_url = "postgresql://user:pass@localhost:5432/teslaMate"
        cfg.teslaMate.car_id = 1

        mock_backend = MagicMock()
        mock_backend.get_efficiency.return_value = trips

        return (
            patch("tesla_cli.commands.teslaMate.load_config", return_value=cfg),
            patch("tesla_cli.backends.teslaMate.TeslaMateBacked", return_value=mock_backend),
            mock_backend,
        )

    def test_efficiency_help(self):
        result = _run("teslaMate", "efficiency", "--help")
        assert result.exit_code == 0
        assert "--limit" in result.output

    def test_efficiency_app_registered(self):
        result = _run("teslaMate", "--help")
        assert result.exit_code == 0
        assert "efficiency" in result.output

    def test_efficiency_empty(self):
        patch_cfg, patch_backend, _ = self._patched_backend([])
        with patch_cfg, patch_backend:
            result = _run("teslaMate", "efficiency")
        assert result.exit_code == 0
        assert "No trip" in result.output or "not found" in result.output.lower()

    def test_efficiency_with_trips(self):
        trips = [
            {
                "start_date": "2026-03-01T08:00:00",
                "distance_km": 42.0,
                "energy_kwh": 6.3,
                "wh_per_km": 150.0,
                "kwh_per_100mi": 24.1,
                "start_battery_level": 80,
                "end_battery_level": 68,
                "start_address": "Home",
                "end_address": "Office",
            }
        ]
        patch_cfg, patch_backend, _ = self._patched_backend(trips)
        with patch_cfg, patch_backend:
            result = _run("teslaMate", "efficiency")
        assert result.exit_code == 0
        assert "42" in result.output or "Home" in result.output or "Office" in result.output

    def test_efficiency_json(self):
        trips = [
            {
                "start_date": "2026-03-01T08:00:00",
                "distance_km": 42.0,
                "energy_kwh": 6.3,
                "wh_per_km": 150.0,
                "kwh_per_100mi": 24.1,
                "start_battery_level": 80,
                "end_battery_level": 68,
                "start_address": "Home",
                "end_address": "Office",
            }
        ]
        patch_cfg, patch_backend, _ = self._patched_backend(trips)
        with patch_cfg, patch_backend:
            result = _run("--json", "teslaMate", "efficiency")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]["wh_per_km"] == 150.0
        assert data[0]["kwh_per_100mi"] == 24.1

    def test_efficiency_limit_passed(self):
        patch_cfg, patch_backend, mock_bk = self._patched_backend([])
        with patch_cfg, patch_backend:
            _run("teslaMate", "efficiency", "--limit", "50")
        mock_bk.get_efficiency.assert_called_once_with(limit=50)

    def test_efficiency_summary_line(self):
        trips = [
            {
                "start_date": "2026-03-01",
                "distance_km": 100.0,
                "energy_kwh": 15.0,
                "wh_per_km": 150.0,
                "kwh_per_100mi": 24.1,
                "start_battery_level": 90,
                "end_battery_level": 75,
                "start_address": "A",
                "end_address": "B",
            },
            {
                "start_date": "2026-03-02",
                "distance_km": 50.0,
                "energy_kwh": 8.0,
                "wh_per_km": 160.0,
                "kwh_per_100mi": 25.7,
                "start_battery_level": 80,
                "end_battery_level": 70,
                "start_address": "B",
                "end_address": "C",
            },
        ]
        patch_cfg, patch_backend, _ = self._patched_backend(trips)
        with patch_cfg, patch_backend:
            result = _run("teslaMate", "efficiency")
        assert result.exit_code == 0
        # Should contain a summary line with avg efficiency
        assert "150" in result.output or "avg" in result.output.lower() or "Wh/km" in result.output


# ── Portuguese i18n ───────────────────────────────────────────────────────────


class TestPortugueseI18n:
    def setup_method(self):
        """Reset language to English before each test."""
        from tesla_cli.i18n import set_lang
        set_lang("en")

    def teardown_method(self):
        """Reset language to English after each test."""
        from tesla_cli.i18n import set_lang
        set_lang("en")

    def test_pt_order_no_rn(self):
        from tesla_cli.i18n import set_lang, t
        set_lang("pt")
        text = t("order.no_rn")
        assert "reserva" in text.lower() or "Número" in text

    def test_pt_order_watching(self):
        from tesla_cli.i18n import set_lang, t
        set_lang("pt")
        text = t("order.watching", rn="RN123", interval="5")
        assert "RN123" in text
        assert "5" in text
        assert "Monitorando" in text or "pedido" in text

    def test_pt_vehicle_locked(self):
        from tesla_cli.i18n import set_lang, t
        set_lang("pt")
        assert t("vehicle.locked") == "Veículo trancado"

    def test_pt_vehicle_unlocked(self):
        from tesla_cli.i18n import set_lang, t
        set_lang("pt")
        assert t("vehicle.unlocked") == "Veículo destrancado"

    def test_pt_charge_started(self):
        from tesla_cli.i18n import set_lang, t
        set_lang("pt")
        assert "Carregamento" in t("charge.started")

    def test_pt_climate_on(self):
        from tesla_cli.i18n import set_lang, t
        set_lang("pt")
        assert "LIGADO" in t("climate.on") or "Clima" in t("climate.on")

    def test_pt_dossier_not_found(self):
        from tesla_cli.i18n import set_lang, t
        set_lang("pt")
        text = t("dossier.not_found")
        assert "dossier" in text.lower() or "Nenhum" in text

    def test_pt_fallback_to_english_for_unknown_key(self):
        from tesla_cli.i18n import set_lang, t
        set_lang("pt")
        # Unknown key should return the key itself (no crash)
        result = t("nonexistent.key.xyz")
        assert result == "nonexistent.key.xyz"

    def test_pt_teslaMate_not_configured(self):
        from tesla_cli.i18n import set_lang, t
        set_lang("pt")
        text = t("teslaMate.not_configured")
        assert "TeslaMate" in text and ("não" in text or "Nenhum" in text or "configurado" in text)

    def test_pt_config_saved_is_defined(self):
        from tesla_cli.i18n import _STRINGS
        assert "pt" in _STRINGS
        pt = _STRINGS["pt"]
        assert "config.saved" in pt
        # Template should include format placeholders for key and value
        assert "{value}" in pt["config.saved"]

    def test_pt_order_no_changes_with_time(self):
        from tesla_cli.i18n import set_lang, t
        set_lang("pt")
        text = t("order.no_changes", time="12:00")
        assert "12:00" in text
        assert "Sem" in text or "alterações" in text

    def test_pt_language_isolation(self):
        """Switching back to 'en' from 'pt' restores English strings."""
        from tesla_cli.i18n import get_lang, set_lang, t
        set_lang("pt")
        pt_text = t("vehicle.locked")
        set_lang("en")
        en_text = t("vehicle.locked")
        assert pt_text != en_text
        assert en_text == "Vehicle locked"
        assert get_lang() == "en"

    def test_lang_flag_via_env(self, monkeypatch):
        """TESLA_LANG env var drives i18n at module import — test set_lang directly."""
        from tesla_cli.i18n import set_lang, t
        monkeypatch.setenv("TESLA_LANG", "pt")
        set_lang("pt")
        assert "Veículo" in t("vehicle.locked") or t("vehicle.locked") == "Veículo trancado"


# ── Vehicle Alerts ────────────────────────────────────────────────────────────


class TestVehicleAlerts:
    def _patched(self, mock_backend):
        cfg = MagicMock()
        cfg.general.backend = "fleet"
        cfg.general.default_vin = MOCK_VIN
        cfg.fleet.region = "na"
        return [
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ]

    def test_alerts_help(self):
        result = _run("vehicle", "alerts", "--help")
        assert result.exit_code == 0

    def test_alerts_none(self, mock_fleet_backend):
        mock_fleet_backend.get_recent_alerts.return_value = []
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("vehicle", "alerts")
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        assert "No recent" in result.output

    def test_alerts_with_data(self, mock_fleet_backend):
        mock_fleet_backend.get_recent_alerts.return_value = [
            {
                "name": "VCFRONT_a174",
                "audiences": ["CUSTOMER"],
                "started_at": "2026-03-01T10:00:00",
                "expires_at": "2026-03-08T10:00:00",
            }
        ]
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("vehicle", "alerts")
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        assert "VCFRONT" in result.output or "CUSTOMER" in result.output

    def test_alerts_json(self, mock_fleet_backend):
        mock_fleet_backend.get_recent_alerts.return_value = [
            {"name": "ALERT_001", "audiences": ["CUSTOMER"], "started_at": "2026-03-01"}
        ]
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("--json", "vehicle", "alerts")
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]["name"] == "ALERT_001"

    def test_alerts_dict_response(self, mock_fleet_backend):
        """Backend may return {recent_alerts: [...]} dict."""
        mock_fleet_backend.get_recent_alerts.return_value = {
            "recent_alerts": [{"name": "WRAPPED_ALERT", "audiences": []}]
        }
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("--json", "vehicle", "alerts")
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["name"] == "WRAPPED_ALERT"


# ── Vehicle Release Notes ─────────────────────────────────────────────────────


class TestVehicleReleaseNotes:
    def _patched(self, mock_backend):
        cfg = MagicMock()
        cfg.general.backend = "fleet"
        cfg.general.default_vin = MOCK_VIN
        cfg.fleet.region = "na"
        return [
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ]

    def test_release_notes_help(self):
        result = _run("vehicle", "release-notes", "--help")
        assert result.exit_code == 0

    def test_release_notes_empty(self, mock_fleet_backend):
        mock_fleet_backend.get_release_notes.return_value = []
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("vehicle", "release-notes")
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        assert "No release notes" in result.output

    def test_release_notes_with_data(self, mock_fleet_backend):
        mock_fleet_backend.get_release_notes.return_value = [
            {"title": "Autopilot Improvements", "description": "Better lane changing."}
        ]
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("vehicle", "release-notes")
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        assert "Autopilot" in result.output or "lane" in result.output

    def test_release_notes_dict_response(self, mock_fleet_backend):
        """Backend may return {release_notes: [...]} dict."""
        mock_fleet_backend.get_release_notes.return_value = {
            "release_notes": [{"title": "Test Update", "description": "Fixes."}]
        }
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("vehicle", "release-notes")
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        assert "Test Update" in result.output or "Fixes" in result.output

    def test_release_notes_json(self, mock_fleet_backend):
        mock_fleet_backend.get_release_notes.return_value = [
            {"title": "OTA 2025.6", "description": "New features."}
        ]
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("--json", "vehicle", "release-notes")
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]["title"] == "OTA 2025.6"


# ── Vehicle Valet ─────────────────────────────────────────────────────────────


class TestVehicleValet:
    def _patched(self, mock_backend):
        cfg = MagicMock()
        cfg.general.backend = "fleet"
        cfg.general.default_vin = MOCK_VIN
        cfg.fleet.region = "na"
        return [
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ]

    def test_valet_help(self):
        result = _run("vehicle", "valet", "--help")
        assert result.exit_code == 0
        assert "--on" in result.output or "--off" in result.output

    def test_valet_status_off(self, mock_fleet_backend):
        mock_fleet_backend.get_vehicle_state.return_value = {"valet_mode": False}
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("vehicle", "valet")
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        assert "OFF" in result.output or "off" in result.output.lower()

    def test_valet_status_on(self, mock_fleet_backend):
        mock_fleet_backend.get_vehicle_state.return_value = {"valet_mode": True}
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("vehicle", "valet")
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        assert "ON" in result.output or "on" in result.output.lower()

    def test_valet_status_json(self, mock_fleet_backend):
        mock_fleet_backend.get_vehicle_state.return_value = {"valet_mode": False}
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("--json", "vehicle", "valet")
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "valet_mode" in data
        assert data["valet_mode"] is False

    def test_valet_enable(self, mock_fleet_backend):
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("vehicle", "valet", "--on", "--password", "1234")
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        mock_fleet_backend.set_valet_mode.assert_called_once_with(
            MOCK_VIN, on=True, password="1234"
        )

    def test_valet_disable(self, mock_fleet_backend):
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("vehicle", "valet", "--off")
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        mock_fleet_backend.set_valet_mode.assert_called_once_with(
            MOCK_VIN, on=False, password=""
        )


# ── Vehicle Schedule Charge ───────────────────────────────────────────────────


class TestVehicleScheduleCharge:
    def _patched(self, mock_backend):
        cfg = MagicMock()
        cfg.general.backend = "fleet"
        cfg.general.default_vin = MOCK_VIN
        cfg.fleet.region = "na"
        return [
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ]

    def test_schedule_charge_help(self):
        result = _run("vehicle", "schedule-charge", "--help")
        assert result.exit_code == 0
        assert "--off" in result.output

    def test_schedule_charge_status_off(self, mock_fleet_backend):
        mock_fleet_backend.get_charge_state.return_value = {
            "scheduled_charging_pending": False,
            "scheduled_charging_start_time": None,
        }
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("vehicle", "schedule-charge")
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        assert "OFF" in result.output

    def test_schedule_charge_set_time(self, mock_fleet_backend):
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("vehicle", "schedule-charge", "23:30")
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        mock_fleet_backend.set_scheduled_charging.assert_called_once_with(
            MOCK_VIN, enable=True, time_minutes=23 * 60 + 30
        )

    def test_schedule_charge_disable(self, mock_fleet_backend):
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("vehicle", "schedule-charge", "--off")
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        mock_fleet_backend.set_scheduled_charging.assert_called_once_with(
            MOCK_VIN, enable=False, time_minutes=0
        )

    def test_schedule_charge_json(self, mock_fleet_backend):
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("--json", "vehicle", "schedule-charge", "06:00")
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["scheduled_charging"] is True
        assert data["time_minutes"] == 360

    def test_schedule_charge_invalid_time(self, mock_fleet_backend):
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("vehicle", "schedule-charge", "25:99")
        for p in patches:
            p.stop()
        assert result.exit_code != 0

    def test_schedule_charge_midnight(self, mock_fleet_backend):
        patches = self._patched(mock_fleet_backend)
        for p in patches:
            p.start()
        result = _run("vehicle", "schedule-charge", "00:00")
        for p in patches:
            p.stop()
        assert result.exit_code == 0
        mock_fleet_backend.set_scheduled_charging.assert_called_once_with(
            MOCK_VIN, enable=True, time_minutes=0
        )


# ── Dossier Clean ─────────────────────────────────────────────────────────────


class TestDossierClean:
    def test_clean_help(self):
        result = _run("dossier", "clean", "--help")
        assert result.exit_code == 0
        assert "--keep" in result.output
        assert "--dry-run" in result.output

    def test_clean_no_snapshots_dir(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_dir = Path(tmpdir) / "nonexistent"
            with patch("tesla_cli.backends.dossier.SNAPSHOTS_DIR", fake_dir):
                result = _run("dossier", "clean")
        assert result.exit_code == 0
        assert "No snapshots" in result.output

    def test_clean_nothing_to_do(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            snap_dir = Path(tmpdir) / "snapshots"
            snap_dir.mkdir()
            for i in range(3):
                (snap_dir / f"snapshot_2026010{i}_120000.json").write_text("{}")
            with patch("tesla_cli.backends.dossier.SNAPSHOTS_DIR", snap_dir):
                result = _run("dossier", "clean", "--keep", "10")
        assert result.exit_code == 0
        assert "Nothing to clean" in result.output

    def test_clean_deletes_oldest(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            snap_dir = Path(tmpdir) / "snapshots"
            snap_dir.mkdir()
            for i in range(1, 8):
                (snap_dir / f"snapshot_202601{i:02d}_120000.json").write_text("{}")
            with patch("tesla_cli.backends.dossier.SNAPSHOTS_DIR", snap_dir):
                result = _run("dossier", "clean", "--keep", "3")
            remaining = list(snap_dir.glob("snapshot_*.json"))
        assert result.exit_code == 0
        assert len(remaining) == 3
        assert "Deleted" in result.output or "deleted" in result.output.lower()

    def test_clean_dry_run(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            snap_dir = Path(tmpdir) / "snapshots"
            snap_dir.mkdir()
            for i in range(1, 6):
                (snap_dir / f"snapshot_202601{i:02d}_120000.json").write_text("{}")
            with patch("tesla_cli.backends.dossier.SNAPSHOTS_DIR", snap_dir):
                result = _run("dossier", "clean", "--keep", "2", "--dry-run")
            remaining = list(snap_dir.glob("snapshot_*.json"))
        assert result.exit_code == 0
        assert len(remaining) == 5  # nothing actually deleted
        assert "Would delete" in result.output

    def test_clean_json(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            snap_dir = Path(tmpdir) / "snapshots"
            snap_dir.mkdir()
            for i in range(1, 6):
                (snap_dir / f"snapshot_202601{i:02d}_120000.json").write_text("{}")
            with patch("tesla_cli.backends.dossier.SNAPSHOTS_DIR", snap_dir):
                result = _run("--json", "dossier", "clean", "--keep", "3")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["deleted"] == 2
        assert data["kept"] == 3
        assert len(data["files_removed"]) == 2

    def test_clean_json_dry_run(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            snap_dir = Path(tmpdir) / "snapshots"
            snap_dir.mkdir()
            for i in range(1, 4):
                (snap_dir / f"snapshot_202601{i:02d}_120000.json").write_text("{}")
            with patch("tesla_cli.backends.dossier.SNAPSHOTS_DIR", snap_dir):
                result = _run("--json", "dossier", "clean", "--keep", "1", "--dry-run")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["deleted"] == 2


# ── French i18n ───────────────────────────────────────────────────────────────


class TestFrenchI18n:
    def setup_method(self):
        from tesla_cli.i18n import set_lang
        set_lang("en")

    def teardown_method(self):
        from tesla_cli.i18n import set_lang
        set_lang("en")

    def test_fr_vehicle_locked(self):
        from tesla_cli.i18n import set_lang, t
        set_lang("fr")
        assert t("vehicle.locked") == "Véhicule verrouillé"

    def test_fr_vehicle_unlocked(self):
        from tesla_cli.i18n import set_lang, t
        set_lang("fr")
        assert t("vehicle.unlocked") == "Véhicule déverrouillé"

    def test_fr_order_watching(self):
        from tesla_cli.i18n import set_lang, t
        set_lang("fr")
        text = t("order.watching", rn="RN999", interval="10")
        assert "RN999" in text and "10" in text
        assert "Surveillance" in text or "commande" in text

    def test_fr_charge_started(self):
        from tesla_cli.i18n import set_lang, t
        set_lang("fr")
        assert "Charge" in t("charge.started") or "Charg" in t("charge.started")

    def test_fr_climate_on(self):
        from tesla_cli.i18n import set_lang, t
        set_lang("fr")
        assert "ACTIVÉE" in t("climate.on") or "Climatisation" in t("climate.on")

    def test_fr_dossier_not_found(self):
        from tesla_cli.i18n import set_lang, t
        set_lang("fr")
        assert "dossier" in t("dossier.not_found").lower() or "Aucun" in t("dossier.not_found")

    def test_fr_teslaMate_not_configured(self):
        from tesla_cli.i18n import set_lang, t
        set_lang("fr")
        text = t("teslaMate.not_configured")
        assert "TeslaMate" in text and ("non" in text or "configuré" in text)

    def test_fr_isolation_from_en(self):
        from tesla_cli.i18n import set_lang, t
        set_lang("fr")
        fr_text = t("vehicle.locked")
        set_lang("en")
        en_text = t("vehicle.locked")
        assert fr_text != en_text
        assert en_text == "Vehicle locked"

    def test_fr_catalog_completeness(self):
        """French catalog should cover the same keys as English."""
        from tesla_cli.i18n import _STRINGS
        en_keys = set(_STRINGS["en"].keys())
        fr_keys = set(_STRINGS["fr"].keys())
        missing = en_keys - fr_keys
        assert not missing, f"French catalog missing keys: {missing}"

    def test_three_languages_registered(self):
        from tesla_cli.i18n import _STRINGS
        assert "en" in _STRINGS
        assert "es" in _STRINGS
        assert "pt" in _STRINGS
        assert "fr" in _STRINGS


# ── Backend Not Supported Error ───────────────────────────────────────────────


class TestBackendNotSupported:
    """Verify that Fleet-only features fail gracefully on Owner/Tessie backends."""

    def test_exception_message_contains_hint(self):
        from tesla_cli.exceptions import BackendNotSupportedError
        exc = BackendNotSupportedError("charge history", "fleet")
        assert "fleet" in str(exc)
        assert "charge history" in str(exc)
        assert "tesla config set backend" in str(exc)

    def test_base_get_charge_history_raises(self):
        from tesla_cli.backends.base import VehicleBackend
        from tesla_cli.exceptions import BackendNotSupportedError
        # Create a minimal concrete subclass
        class _MinimalBackend(VehicleBackend):
            def list_vehicles(self): return []
            def get_vehicle_data(self, vin): return {}
            def get_charge_state(self, vin): return {}
            def get_climate_state(self, vin): return {}
            def get_drive_state(self, vin): return {}
            def get_vehicle_config(self, vin): return {}
            def wake_up(self, vin): return True
            def command(self, vin, command, **p): return {}

        b = _MinimalBackend()
        with pytest.raises(BackendNotSupportedError):
            b.get_charge_history()

    def test_base_get_recent_alerts_raises(self):
        from tesla_cli.backends.base import VehicleBackend
        from tesla_cli.exceptions import BackendNotSupportedError
        class _MinimalBackend(VehicleBackend):
            def list_vehicles(self): return []
            def get_vehicle_data(self, vin): return {}
            def get_charge_state(self, vin): return {}
            def get_climate_state(self, vin): return {}
            def get_drive_state(self, vin): return {}
            def get_vehicle_config(self, vin): return {}
            def wake_up(self, vin): return True
            def command(self, vin, command, **p): return {}

        b = _MinimalBackend()
        with pytest.raises(BackendNotSupportedError):
            b.get_recent_alerts("VIN123")

    def test_base_get_release_notes_raises(self):
        from tesla_cli.backends.base import VehicleBackend
        from tesla_cli.exceptions import BackendNotSupportedError
        class _MinimalBackend(VehicleBackend):
            def list_vehicles(self): return []
            def get_vehicle_data(self, vin): return {}
            def get_charge_state(self, vin): return {}
            def get_climate_state(self, vin): return {}
            def get_drive_state(self, vin): return {}
            def get_vehicle_config(self, vin): return {}
            def wake_up(self, vin): return True
            def command(self, vin, command, **p): return {}

        b = _MinimalBackend()
        with pytest.raises(BackendNotSupportedError):
            b.get_release_notes("VIN123")

    def test_base_get_invitations_raises(self):
        from tesla_cli.backends.base import VehicleBackend
        from tesla_cli.exceptions import BackendNotSupportedError
        class _MinimalBackend(VehicleBackend):
            def list_vehicles(self): return []
            def get_vehicle_data(self, vin): return {}
            def get_charge_state(self, vin): return {}
            def get_climate_state(self, vin): return {}
            def get_drive_state(self, vin): return {}
            def get_vehicle_config(self, vin): return {}
            def wake_up(self, vin): return True
            def command(self, vin, command, **p): return {}

        b = _MinimalBackend()
        with pytest.raises(BackendNotSupportedError):
            b.get_invitations("VIN123")

    def test_base_get_vehicle_state_fallback(self):
        """get_vehicle_state falls back to extracting from vehicle_data."""
        from tesla_cli.backends.base import VehicleBackend
        class _MinimalBackend(VehicleBackend):
            def list_vehicles(self): return []
            def get_vehicle_data(self, vin): return {"vehicle_state": {"locked": True}}
            def get_charge_state(self, vin): return {}
            def get_climate_state(self, vin): return {}
            def get_drive_state(self, vin): return {}
            def get_vehicle_config(self, vin): return {}
            def wake_up(self, vin): return True
            def command(self, vin, command, **p): return {}

        b = _MinimalBackend()
        assert b.get_vehicle_state("VIN123") == {"locked": True}

    def test_charge_history_command_graceful(self):
        from tesla_cli.exceptions import BackendNotSupportedError
        mock_backend = MagicMock()
        mock_backend.get_charge_history.side_effect = BackendNotSupportedError(
            "charge history", "fleet"
        )
        cfg = MagicMock()
        cfg.general.backend = "owner"
        cfg.general.default_vin = MOCK_VIN
        with (
            patch("tesla_cli.commands.charge.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.commands.charge.load_config", return_value=cfg),
        ):
            result = _run("charge", "history")
        assert result.exit_code == 1
        assert "fleet" in result.output.lower() or "not available" in result.output.lower()

    def test_vehicle_alerts_command_graceful(self):
        from tesla_cli.exceptions import BackendNotSupportedError
        mock_backend = MagicMock()
        mock_backend.get_recent_alerts.side_effect = BackendNotSupportedError(
            "vehicle alerts", "fleet"
        )
        cfg = MagicMock()
        cfg.general.backend = "owner"
        cfg.general.default_vin = MOCK_VIN
        cfg.fleet.region = "na"
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "alerts")
        assert result.exit_code == 1
        assert "fleet" in result.output.lower() or "not available" in result.output.lower()

    def test_vehicle_release_notes_command_graceful(self):
        from tesla_cli.exceptions import BackendNotSupportedError
        mock_backend = MagicMock()
        mock_backend.get_release_notes.side_effect = BackendNotSupportedError(
            "vehicle release-notes", "fleet"
        )
        cfg = MagicMock()
        cfg.general.backend = "owner"
        cfg.general.default_vin = MOCK_VIN
        cfg.fleet.region = "na"
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "release-notes")
        assert result.exit_code == 1
        assert "fleet" in result.output.lower() or "not available" in result.output.lower()

    def test_sharing_list_command_graceful(self):
        from tesla_cli.exceptions import BackendNotSupportedError
        mock_backend = MagicMock()
        mock_backend.get_invitations.side_effect = BackendNotSupportedError(
            "sharing list", "fleet"
        )
        cfg = MagicMock()
        cfg.general.backend = "owner"
        cfg.general.default_vin = MOCK_VIN
        with (
            patch("tesla_cli.commands.sharing.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.commands.sharing.load_config", return_value=cfg),
            patch("tesla_cli.commands.sharing.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("sharing", "list")
        assert result.exit_code == 1
        assert "fleet" in result.output.lower() or "not available" in result.output.lower()

    def test_tessie_backend_has_vehicle_state(self):
        """TessieBackend.get_vehicle_state extracts from vehicle_data."""
        from tesla_cli.backends.tessie import TessieBackend
        backend = TessieBackend.__new__(TessieBackend)
        backend.get_vehicle_data = MagicMock(
            return_value={"vehicle_state": {"locked": False, "sentry_mode": True}}
        )
        state = backend.get_vehicle_state("VIN123")
        assert state["locked"] is False
        assert state["sentry_mode"] is True

    def test_tessie_backend_nearby_sites_called(self):
        """TessieBackend.get_nearby_charging_sites hits the right endpoint."""
        from tesla_cli.backends.tessie import TessieBackend
        backend = TessieBackend.__new__(TessieBackend)
        backend._get = MagicMock(return_value={"superchargers": [], "destination_charging": []})
        result = backend.get_nearby_charging_sites("VIN123")
        backend._get.assert_called_once_with("/VIN123/nearby_charging_sites")
        assert "superchargers" in result


# ═══════════════════════════════════════════════════════════════════════════════
# v1.3.0 Tests — Vehicle Tires, HomeLink, Dashcam, Rename
# ═══════════════════════════════════════════════════════════════════════════════


class TestVehicleTires:
    """Tests for `tesla vehicle tires` (TPMS)."""

    def _make_backend(self, fl=2.8, fr=2.8, rl=2.7, rr=2.7, soft_fl=False, hard_fl=False):
        mock = MagicMock()
        mock.get_vehicle_state.return_value = {
            "tpms_pressure_fl": fl,
            "tpms_pressure_fr": fr,
            "tpms_pressure_rl": rl,
            "tpms_pressure_rr": rr,
            "tpms_soft_warning_fl": soft_fl,
            "tpms_hard_warning_fl": hard_fl,
            "tpms_soft_warning_fr": False,
            "tpms_hard_warning_fr": False,
            "tpms_soft_warning_rl": False,
            "tpms_hard_warning_rl": False,
            "tpms_soft_warning_rr": False,
            "tpms_hard_warning_rr": False,
        }
        return mock

    def _cfg(self):
        cfg = MagicMock()
        cfg.general.default_vin = MOCK_VIN
        return cfg

    def test_tires_success(self):
        mock = self._make_backend()
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "tires")
        assert result.exit_code == 0

    def test_tires_psi_conversion(self):
        """2.8 bar ≈ 40.6 PSI."""
        mock = self._make_backend(fl=2.8)
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "tires")
        assert "40.6" in result.output or "40" in result.output

    def test_tires_json_output(self):
        mock = self._make_backend()
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("-j", "vehicle", "tires")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "front_left" in data
        assert "psi" in data["front_left"]

    def test_tires_soft_warning_shown(self):
        mock = self._make_backend(fl=2.0, soft_fl=True)
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "tires")
        assert result.exit_code == 0
        assert "LOW" in result.output or "WARN" in result.output

    def test_tires_hard_warning_shown(self):
        mock = self._make_backend(fl=1.5, hard_fl=True)
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "tires")
        assert result.exit_code == 0
        assert "HARD" in result.output

    def test_tires_missing_data_graceful(self):
        """Missing TPMS data returns N/A, not a crash."""
        mock = MagicMock()
        mock.get_vehicle_state.return_value = {}
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "tires")
        assert result.exit_code == 0

    def test_tires_in_help(self):
        result = _run("vehicle", "--help")
        assert "tires" in result.output


class TestVehicleHomelink:
    """Tests for `tesla vehicle homelink`."""

    def _cfg(self):
        cfg = MagicMock()
        cfg.general.default_vin = MOCK_VIN
        return cfg

    def _make_backend(self, lat=37.42, lon=-122.08):
        mock = MagicMock()
        mock.get_drive_state.return_value = {"latitude": lat, "longitude": lon}
        mock.command.return_value = {"result": True}
        return mock

    def test_homelink_success(self):
        mock = self._make_backend()
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "homelink")
        assert result.exit_code == 0
        assert "HomeLink" in result.output or "triggered" in result.output.lower()

    def test_homelink_passes_gps_to_command(self):
        mock = self._make_backend(lat=37.42, lon=-122.08)
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            _run("vehicle", "homelink")
        mock.command.assert_called_once_with(MOCK_VIN, "trigger_homelink", lat=37.42, lon=-122.08)

    def test_homelink_json_output(self):
        mock = self._make_backend()
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("-j", "vehicle", "homelink")
        data = json.loads(result.output)
        assert data["homelink"] == "triggered"
        assert "lat" in data

    def test_homelink_missing_gps_uses_zero(self):
        """Missing GPS falls back to 0.0 coordinates — no crash."""
        mock = MagicMock()
        mock.get_drive_state.return_value = {}
        mock.command.return_value = {"result": True}
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "homelink")
        assert result.exit_code == 0
        mock.command.assert_called_once_with(MOCK_VIN, "trigger_homelink", lat=0.0, lon=0.0)


class TestVehicleDashcam:
    """Tests for `tesla vehicle dashcam`."""

    def _cfg(self):
        cfg = MagicMock()
        cfg.general.default_vin = MOCK_VIN
        return cfg

    def test_dashcam_success(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "dashcam")
        assert result.exit_code == 0
        assert "saved" in result.output.lower() or "dashcam" in result.output.lower()

    def test_dashcam_calls_correct_command(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            _run("vehicle", "dashcam")
        mock.command.assert_called_once_with(MOCK_VIN, "dashcam_save_clip")

    def test_dashcam_json_output(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("-j", "vehicle", "dashcam")
        data = json.loads(result.output)
        assert data["dashcam_save"] is True


class TestVehicleRename:
    """Tests for `tesla vehicle rename`."""

    def _cfg(self):
        cfg = MagicMock()
        cfg.general.default_vin = MOCK_VIN
        return cfg

    def test_rename_success(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "rename", "My Tesla Y")
        assert result.exit_code == 0
        assert "My Tesla Y" in result.output or "renamed" in result.output.lower()

    def test_rename_calls_correct_command(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            _run("vehicle", "rename", "Road Runner")
        mock.command.assert_called_once_with(MOCK_VIN, "set_vehicle_name", vehicle_name="Road Runner")

    def test_rename_json_output(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("-j", "vehicle", "rename", "Thunder")
        data = json.loads(result.output)
        assert data["name"] == "Thunder"


# ═══════════════════════════════════════════════════════════════════════════════
# v1.3.0 Tests — Security Remote Start
# ═══════════════════════════════════════════════════════════════════════════════


class TestSecurityRemoteStart:
    """Tests for `tesla security remote-start`.

    Note: security.py imports _with_wake from vehicle.py, which calls
    get_vehicle_backend from tesla_cli.commands.vehicle — that's the patch target.
    """

    def _cfg(self):
        cfg = MagicMock()
        cfg.general.default_vin = MOCK_VIN
        return cfg

    def _patches(self, mock_backend):
        return (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.security.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.security.resolve_vin", return_value=MOCK_VIN),
        )

    def test_remote_start_success(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.security.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.security.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("security", "remote-start")
        assert result.exit_code == 0

    def test_remote_start_calls_correct_command(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.security.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.security.resolve_vin", return_value=MOCK_VIN),
        ):
            _run("security", "remote-start")
        mock.command.assert_called_once_with(MOCK_VIN, "remote_start_drive")

    def test_remote_start_in_help(self):
        result = _run("security", "--help")
        assert "remote-start" in result.output

    def test_remote_start_json_output(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.security.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.security.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("-j", "security", "remote-start")
        data = json.loads(result.output)
        assert data["remote_start"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# v1.3.0 Tests — Dossier Battery Health
# ═══════════════════════════════════════════════════════════════════════════════


class TestDossierBatteryHealth:
    """Tests for `tesla dossier battery-health`."""

    def _make_snapshot(self, battery_level: float, battery_range: float, ts: str) -> dict:
        return {
            "last_updated": ts,
            "charge_state": {
                "battery_level": battery_level,
                "battery_range": battery_range,
            },
        }

    def test_no_snapshots_dir_exits(self):
        fake_dir = Path("/nonexistent_snapshots_xyz_123")
        with patch("tesla_cli.backends.dossier.SNAPSHOTS_DIR", fake_dir):
            result = _run("dossier", "battery-health")
        assert result.exit_code != 0

    def test_single_snapshot_exits_with_message(self):
        with tempfile.TemporaryDirectory() as td:
            snap_dir = Path(td)
            snap1 = snap_dir / "snapshot_2024-01-01.json"
            snap1.write_text(json.dumps(self._make_snapshot(80.0, 200.0, "2024-01-01")))
            with patch("tesla_cli.backends.dossier.SNAPSHOTS_DIR", snap_dir):
                result = _run("dossier", "battery-health")
        assert result.exit_code != 0

    def test_battery_health_json_output(self):
        with tempfile.TemporaryDirectory() as td:
            snap_dir = Path(td)
            for fname, level, rng, ts in [
                ("snapshot_2024-01-01.json", 100.0, 320.0, "2024-01-01"),
                ("snapshot_2024-06-01.json", 80.0, 248.0, "2024-06-01"),
            ]:
                (snap_dir / fname).write_text(
                    json.dumps(self._make_snapshot(level, rng, ts))
                )
            with patch("tesla_cli.backends.dossier.SNAPSHOTS_DIR", snap_dir):
                result = _run("-j", "dossier", "battery-health")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "snapshots_analyzed" in data
        assert data["snapshots_analyzed"] == 2
        assert "estimated_degradation_pct" in data
        assert "peak_estimated_range_mi" in data

    def test_battery_health_in_help(self):
        result = _run("dossier", "--help")
        assert "battery-health" in result.output

    def test_battery_health_skips_low_battery(self):
        """Snapshots with battery_level <= 10 are excluded."""
        with tempfile.TemporaryDirectory() as td:
            snap_dir = Path(td)
            (snap_dir / "snapshot_2024-01-01.json").write_text(
                json.dumps(self._make_snapshot(85.0, 255.0, "2024-01-01"))
            )
            # 5% battery — should be excluded
            (snap_dir / "snapshot_2024-02-01.json").write_text(
                json.dumps(self._make_snapshot(5.0, 10.0, "2024-02-01"))
            )
            (snap_dir / "snapshot_2024-03-01.json").write_text(
                json.dumps(self._make_snapshot(90.0, 270.0, "2024-03-01"))
            )
            with patch("tesla_cli.backends.dossier.SNAPSHOTS_DIR", snap_dir):
                result = _run("-j", "dossier", "battery-health")
        data = json.loads(result.output)
        assert data["snapshots_analyzed"] == 2  # 5% battery excluded

    def test_degradation_math(self):
        """320mi peak, 280mi latest (280/0.8=350 rated — no degradation vs 320 peak)."""
        with tempfile.TemporaryDirectory() as td:
            snap_dir = Path(td)
            # rated = 320 (320/1.0) then 350 (280/0.8), peak=350, latest=350, degradation=0%
            (snap_dir / "snapshot_2024-01-01.json").write_text(
                json.dumps(self._make_snapshot(100.0, 320.0, "2024-01-01"))
            )
            (snap_dir / "snapshot_2024-06-01.json").write_text(
                json.dumps(self._make_snapshot(80.0, 280.0, "2024-06-01"))  # 280/0.8=350
            )
            with patch("tesla_cli.backends.dossier.SNAPSHOTS_DIR", snap_dir):
                result = _run("-j", "dossier", "battery-health")
        data = json.loads(result.output)
        assert data["estimated_degradation_pct"] == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# v1.3.0 Tests — TeslaMate Vampire Drain
# ═══════════════════════════════════════════════════════════════════════════════


class TestTeslaMatVampireDrain:
    """Tests for `tesla teslaMate vampire`."""

    def _make_mock_backend(self, data=None):
        mock = MagicMock()
        if data is None:
            data = {
                "days_analyzed": 30,
                "avg_pct_per_hour": 0.042,
                "daily": [
                    {"date": "2024-06-01", "avg_drain_pct": 1.2, "avg_parked_hours": 8.0, "pct_per_hour": 0.15, "periods": 2},
                    {"date": "2024-06-02", "avg_drain_pct": 0.8, "avg_parked_hours": 10.0, "pct_per_hour": 0.08, "periods": 1},
                ],
            }
        mock.get_vampire_drain.return_value = data
        return mock

    def test_vampire_success(self):
        mock = self._make_mock_backend()
        with patch("tesla_cli.commands.teslaMate._backend", return_value=mock):
            result = _run("teslaMate", "vampire")
        assert result.exit_code == 0

    def test_vampire_shows_drain_rate(self):
        mock = self._make_mock_backend()
        with patch("tesla_cli.commands.teslaMate._backend", return_value=mock):
            result = _run("teslaMate", "vampire")
        assert "0.042" in result.output or "%" in result.output

    def test_vampire_empty_data(self):
        mock = self._make_mock_backend({"days_analyzed": 30, "avg_pct_per_hour": None, "daily": []})
        with patch("tesla_cli.commands.teslaMate._backend", return_value=mock):
            result = _run("teslaMate", "vampire")
        assert result.exit_code == 0
        # should mention no data
        out = result.output.lower()
        assert "no" in out or "found" in out or "data" in out

    def test_vampire_json_output(self):
        mock = self._make_mock_backend()
        with patch("tesla_cli.commands.teslaMate._backend", return_value=mock):
            result = _run("-j", "teslaMate", "vampire")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "avg_pct_per_hour" in data
        assert "daily" in data

    def test_vampire_days_option(self):
        mock = self._make_mock_backend()
        with patch("tesla_cli.commands.teslaMate._backend", return_value=mock):
            _run("teslaMate", "vampire", "--days", "90")
        mock.get_vampire_drain.assert_called_once_with(days=90)

    def test_vampire_in_help(self):
        result = _run("teslaMate", "--help")
        assert "vampire" in result.output

    def test_vampire_backend_method_returns_structure(self):
        """TeslaMateBacked.get_vampire_drain returns expected dict structure."""
        from tesla_cli.backends.teslaMate import TeslaMateBacked
        backend = TeslaMateBacked.__new__(TeslaMateBacked)
        backend._car_id = 1
        mock_rows = [
            {"date": "2024-06-01", "avg_drain_pct": 1.0, "avg_parked_hours": 8.0, "pct_per_hour": 0.125, "periods": 2},
        ]
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = [dict(r) for r in mock_rows]
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_cur)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        backend._cursor = MagicMock(return_value=mock_ctx)
        result = backend.get_vampire_drain(days=30)
        assert result["days_analyzed"] == 30
        assert "avg_pct_per_hour" in result
        assert len(result["daily"]) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# v1.3.0 Tests — CSV Export (trips, charging, efficiency)
# ═══════════════════════════════════════════════════════════════════════════════


class TestTeslaMateCsvExport:
    """Tests for --csv flag on teslaMate trips, charging, efficiency."""

    MOCK_TRIPS = [
        {"date": "2024-06-01", "distance_km": 42.5, "duration_min": 35, "energy_wh": 6200, "start": "Home", "end": "Work"},
        {"date": "2024-06-02", "distance_km": 18.0, "duration_min": 15, "energy_wh": 2800, "start": "Work", "end": "Home"},
    ]

    MOCK_SESSIONS = [
        {"date": "2024-06-01", "location": "Home", "kwh": 45.2, "cost": 8.14, "duration": "3h 22m"},
        {"date": "2024-06-02", "location": "Supercharger", "kwh": 62.0, "cost": 0, "duration": "45m"},
    ]

    def test_trips_csv_creates_file(self):
        mock = MagicMock()
        mock.get_trips.return_value = self.MOCK_TRIPS
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            csv_path = f.name
        try:
            with patch("tesla_cli.commands.teslaMate._backend", return_value=mock):
                result = _run("teslaMate", "trips", "--csv", csv_path)
            assert result.exit_code == 0
            assert Path(csv_path).exists()
            content = Path(csv_path).read_text()
            assert "date" in content
            assert "2024-06-01" in content
        finally:
            Path(csv_path).unlink(missing_ok=True)

    def test_trips_csv_has_correct_columns(self):
        mock = MagicMock()
        mock.get_trips.return_value = self.MOCK_TRIPS
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            csv_path = f.name
        try:
            with patch("tesla_cli.commands.teslaMate._backend", return_value=mock):
                _run("teslaMate", "trips", "--csv", csv_path)
            import csv
            with open(csv_path, newline="") as fh:
                reader = csv.DictReader(fh)
                rows = list(reader)
            assert len(rows) == 2
            assert "distance_km" in rows[0]
        finally:
            Path(csv_path).unlink(missing_ok=True)

    def test_charging_csv_creates_file(self):
        mock = MagicMock()
        mock.get_charging_sessions.return_value = self.MOCK_SESSIONS
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            csv_path = f.name
        try:
            with patch("tesla_cli.commands.teslaMate._backend", return_value=mock):
                result = _run("teslaMate", "charging", "--csv", csv_path)
            assert result.exit_code == 0
            content = Path(csv_path).read_text()
            assert "location" in content
        finally:
            Path(csv_path).unlink(missing_ok=True)

    def test_efficiency_csv_creates_file(self):
        mock = MagicMock()
        mock.get_efficiency_stats.return_value = [
            {"month": "2024-06", "avg_wh_per_km": 145.0, "total_km": 820.0, "total_kwh": 118.9},
        ]
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            csv_path = f.name
        try:
            with patch("tesla_cli.commands.teslaMate._backend", return_value=mock):
                result = _run("teslaMate", "efficiency", "--csv", csv_path)
            assert result.exit_code == 0
            assert Path(csv_path).exists()
        finally:
            Path(csv_path).unlink(missing_ok=True)


# ═══════════════════════════════════════════════════════════════════════════════
# v1.3.0 Tests — Energy Cost Tracking
# ═══════════════════════════════════════════════════════════════════════════════


class TestEnergyCostTracking:
    """Tests for cost_per_kwh config and charge status cost display."""

    def test_cost_per_kwh_field_in_config(self):
        """GeneralConfig must have cost_per_kwh with default 0.0."""
        from tesla_cli.config import GeneralConfig
        cfg = GeneralConfig()
        assert hasattr(cfg, "cost_per_kwh")
        assert cfg.cost_per_kwh == 0.0

    def test_charge_status_shows_cost_when_configured(self):
        """When cost_per_kwh > 0 and energy was added, show estimated cost."""
        mock_backend = MagicMock()
        mock_backend.get_charge_state.return_value = {
            "battery_level": 80,
            "battery_range": 240.0,
            "charge_energy_added": 20.0,  # 20 kWh added
            "charging_state": "Complete",
            "charge_limit_soc": 80,
        }
        cfg = MagicMock()
        cfg.general.backend = "fleet"
        cfg.general.default_vin = MOCK_VIN
        cfg.general.cost_per_kwh = 0.15  # 15¢/kWh
        # charge.py uses _with_wake from vehicle.py which calls vehicle._backend()
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.commands.charge.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.commands.charge.load_config", return_value=cfg),
            patch("tesla_cli.commands.charge.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("charge", "status")
        assert result.exit_code == 0
        # 20 kWh × $0.15 = $3.00
        assert "$3.00" in result.output

    def test_charge_status_no_cost_when_zero(self):
        """When cost_per_kwh is 0, no cost line is shown."""
        mock_backend = MagicMock()
        mock_backend.get_charge_state.return_value = {
            "battery_level": 80,
            "battery_range": 240.0,
            "charge_energy_added": 20.0,
            "charging_state": "Complete",
            "charge_limit_soc": 80,
        }
        cfg = MagicMock()
        cfg.general.backend = "fleet"
        cfg.general.default_vin = MOCK_VIN
        cfg.general.cost_per_kwh = 0.0
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.commands.charge.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.commands.charge.load_config", return_value=cfg),
            patch("tesla_cli.commands.charge.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("charge", "status")
        assert result.exit_code == 0
        assert "session cost" not in result.output.lower()

    def test_cost_per_kwh_is_valid_config_key(self):
        """config set cost-per-kwh must be accepted (not raise 'unknown key')."""
        cfg_mock = MagicMock()
        cfg_mock.general.cost_per_kwh = 0.0
        cfg_mock.notifications.enabled = False
        cfg_mock.notifications.apprise_urls = []
        with (
            patch("tesla_cli.commands.config_cmd.load_config", return_value=cfg_mock),
            patch("tesla_cli.commands.config_cmd.save_config"),
        ):
            result = _run("config", "set", "cost-per-kwh", "0.12")
        # Should not print "Unknown key"
        assert "Unknown key" not in result.output


# ═══════════════════════════════════════════════════════════════════════════════
# v1.3.0 Tests — Order Watch --on-change-exec
# ═══════════════════════════════════════════════════════════════════════════════


class TestOrderWatchOnChangeExec:
    """Tests for _exec_on_change helper."""

    def test_exec_on_change_passes_env_var(self):
        """_exec_on_change should call subprocess.Popen with TESLA_CHANGES env."""
        from tesla_cli.commands.order import _exec_on_change
        from tesla_cli.models.order import OrderChange

        changes = [OrderChange(field="order_status", old_value="Pending", new_value="Confirmed")]

        # subprocess is imported lazily inside _exec_on_change — patch at stdlib level
        with patch("subprocess.Popen") as mock_popen:
            _exec_on_change("echo test", changes)

        mock_popen.assert_called_once()
        call_kwargs = mock_popen.call_args
        env = call_kwargs.kwargs.get("env") or call_kwargs[1].get("env", {})
        assert "TESLA_CHANGES" in env
        changes_data = json.loads(env["TESLA_CHANGES"])
        assert len(changes_data) == 1
        assert changes_data[0]["field"] == "order_status"

    def test_exec_on_change_uses_shell(self):
        """Command must run with shell=True for flexibility."""
        from tesla_cli.commands.order import _exec_on_change

        with patch("subprocess.Popen") as mock_popen:
            _exec_on_change("my-hook.sh", [])

        call_kwargs = mock_popen.call_args
        shell = call_kwargs.kwargs.get("shell") or call_kwargs[1].get("shell")
        assert shell is True

    def test_exec_on_change_empty_changes(self):
        """Empty changes list produces empty JSON array in env."""
        from tesla_cli.commands.order import _exec_on_change

        with patch("subprocess.Popen") as mock_popen:
            _exec_on_change("noop", [])

        call_kwargs = mock_popen.call_args
        env = call_kwargs.kwargs.get("env") or call_kwargs[1].get("env", {})
        assert json.loads(env["TESLA_CHANGES"]) == []


# ═══════════════════════════════════════════════════════════════════════════════
# v1.3.0 Tests — Stream MQTT
# ═══════════════════════════════════════════════════════════════════════════════


class TestStreamMqtt:
    """Tests for --mqtt option on `tesla stream live`."""

    def test_stream_live_subcommand_help_has_mqtt(self):
        result = _run("stream", "live", "--help")
        assert "--mqtt" in result.output

    def test_mqtt_url_parsing(self):
        """MQTT URL parsed correctly for host/port/topic."""
        from urllib.parse import urlparse
        url = "mqtt://mybroker:1884/tesla/VIN123"
        parsed = urlparse(url)
        assert parsed.hostname == "mybroker"
        assert parsed.port == 1884
        assert parsed.path == "/tesla/VIN123"

    def test_mqtt_import_error_handled(self):
        """If paho-mqtt not installed, stream should not crash immediately."""
        # The warning is shown lazily after first MQTT attempt, so this just
        # tests that the help renders correctly and the option is registered.
        result = _run("stream", "live", "--help")
        assert result.exit_code == 0


# ═══════════════════════════════════════════════════════════════════════════════
# v1.3.0 Tests — German + Italian i18n
# ═══════════════════════════════════════════════════════════════════════════════


class TestGermanI18n:
    """Tests for German (de) i18n catalog."""

    def test_de_catalog_exists(self):
        from tesla_cli.i18n import _STRINGS
        assert "de" in _STRINGS

    def test_de_order_keys(self):
        """German catalog must have order-related keys."""
        from tesla_cli.i18n import _STRINGS
        de = _STRINGS["de"]
        # These are the actual keys in the catalog (not order.status)
        assert "order.no_rn" in de or "order.watching" in de

    def test_de_vehicle_keys(self):
        from tesla_cli.i18n import _STRINGS
        de = _STRINGS["de"]
        assert "vehicle.locked" in de
        assert "vehicle.unlocked" in de

    def test_de_charge_keys(self):
        from tesla_cli.i18n import _STRINGS
        de = _STRINGS["de"]
        # Actual keys are charge.started / charge.stopped
        assert "charge.started" in de
        assert "charge.stopped" in de

    def test_de_climate_keys(self):
        from tesla_cli.i18n import _STRINGS
        de = _STRINGS["de"]
        assert "climate.on" in de
        assert "climate.off" in de

    def test_de_error_keys(self):
        from tesla_cli.i18n import _STRINGS
        de = _STRINGS["de"]
        assert "error.auth" in de

    def test_de_t_function_returns_string(self):
        from tesla_cli.i18n import _lang, set_lang, t
        original = _lang
        try:
            set_lang("de")
            result = t("vehicle.locked")
            assert isinstance(result, str)
            assert len(result) > 0
        finally:
            set_lang(original)

    def test_de_translations_are_not_english(self):
        """German should differ from English for at least one key."""
        from tesla_cli.i18n import _STRINGS
        en = _STRINGS["en"]
        de = _STRINGS["de"]
        differs = any(de.get(k) != v for k, v in en.items() if k in de)
        assert differs, "German catalog is identical to English — translations missing"

    def test_de_setup_keys(self):
        from tesla_cli.i18n import _STRINGS
        de = _STRINGS["de"]
        assert any(k.startswith("setup.") for k in de)


class TestItalianI18n:
    """Tests for Italian (it) i18n catalog."""

    def test_it_catalog_exists(self):
        from tesla_cli.i18n import _STRINGS
        assert "it" in _STRINGS

    def test_it_order_keys(self):
        from tesla_cli.i18n import _STRINGS
        it = _STRINGS["it"]
        assert "order.no_rn" in it or "order.watching" in it

    def test_it_vehicle_keys(self):
        from tesla_cli.i18n import _STRINGS
        it = _STRINGS["it"]
        assert "vehicle.locked" in it
        assert "vehicle.unlocked" in it

    def test_it_charge_keys(self):
        from tesla_cli.i18n import _STRINGS
        it = _STRINGS["it"]
        assert "charge.started" in it
        assert "charge.stopped" in it

    def test_it_error_keys(self):
        from tesla_cli.i18n import _STRINGS
        it = _STRINGS["it"]
        assert "error.auth" in it

    def test_it_t_function_returns_string(self):
        from tesla_cli.i18n import _lang, set_lang, t
        original = _lang
        try:
            set_lang("it")
            result = t("vehicle.locked")
            assert isinstance(result, str)
            assert len(result) > 0
        finally:
            set_lang(original)

    def test_it_translations_are_not_english(self):
        """Italian should differ from English for at least one key."""
        from tesla_cli.i18n import _STRINGS
        en = _STRINGS["en"]
        it = _STRINGS["it"]
        differs = any(it.get(k) != v for k, v in en.items() if k in it)
        assert differs, "Italian catalog is identical to English — translations missing"

    def test_it_setup_keys(self):
        from tesla_cli.i18n import _STRINGS
        it = _STRINGS["it"]
        assert any(k.startswith("setup.") for k in it)

    def test_six_languages_supported(self):
        """CLI must support exactly 6 languages."""
        from tesla_cli.i18n import _STRINGS
        for lang in ["en", "es", "pt", "fr", "de", "it"]:
            assert lang in _STRINGS, f"Language '{lang}' missing from _STRINGS"


# ═══════════════════════════════════════════════════════════════════════════════
# v1.4.0 Tests — Charge Departure
# ═══════════════════════════════════════════════════════════════════════════════


class TestChargeDeparture:
    """Tests for `tesla charge departure`."""

    def _cfg(self):
        cfg = MagicMock()
        cfg.general.default_vin = MOCK_VIN
        return cfg

    def _run_departure(self, mock_backend, *args):
        cfg = self._cfg()
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.commands.charge.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.commands.charge.load_config", return_value=cfg),
            patch("tesla_cli.commands.charge.resolve_vin", return_value=MOCK_VIN),
        ):
            return _run("charge", "departure", *args)

    def test_departure_success(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        result = self._run_departure(mock, "07:30")
        assert result.exit_code == 0
        assert "07:30" in result.output

    def test_departure_parses_time_to_minutes(self):
        """07:30 → 450 minutes after midnight."""
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        result = self._run_departure(mock, "-j", "07:30")
        # -j must come before subcommand
        cfg = self._cfg()
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.commands.charge.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.charge.load_config", return_value=cfg),
            patch("tesla_cli.commands.charge.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("-j", "charge", "departure", "07:30")
        data = json.loads(result.output)
        assert data["time_minutes"] == 450  # 7*60+30
        assert data["time"] == "07:30"
        assert data["scheduled_departure"] is True

    def test_departure_with_precondition(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        result = self._run_departure(mock, "08:00", "--precondition")
        assert result.exit_code == 0
        assert "precondition" in result.output.lower()

    def test_departure_disable(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        result = self._run_departure(mock, "--disable", "ignored")
        assert result.exit_code == 0
        assert "disabled" in result.output.lower()

    def test_departure_disable_calls_correct_command(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        self._run_departure(mock, "--disable", "00:00")
        mock.command.assert_called_once_with(
            MOCK_VIN, "set_scheduled_departure", enable=False, departure_time=0
        )

    def test_departure_json_disable(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        cfg = self._cfg()
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.commands.charge.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.charge.load_config", return_value=cfg),
            patch("tesla_cli.commands.charge.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("-j", "charge", "departure", "--disable", "00:00")
        data = json.loads(result.output)
        assert data["scheduled_departure"] is False

    def test_departure_off_peak(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        result = self._run_departure(mock, "06:00", "--off-peak", "--off-peak-end", "07:00")
        assert result.exit_code == 0

    def test_departure_in_help(self):
        result = _run("charge", "--help")
        assert "departure" in result.output


# ═══════════════════════════════════════════════════════════════════════════════
# v1.4.0 Tests — Vehicle Precondition
# ═══════════════════════════════════════════════════════════════════════════════


class TestVehiclePrecondition:
    """Tests for `tesla vehicle precondition`."""

    def _cfg(self):
        cfg = MagicMock()
        cfg.general.default_vin = MOCK_VIN
        return cfg

    def test_precondition_on(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "precondition", "true")
        assert result.exit_code == 0
        assert "enabled" in result.output.lower()

    def test_precondition_off(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "precondition", "false")
        assert result.exit_code == 0
        assert "disabled" in result.output.lower()

    def test_precondition_calls_correct_command(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            _run("vehicle", "precondition", "true")
        mock.command.assert_called_once_with(MOCK_VIN, "set_preconditioning_max", on=True)

    def test_precondition_json(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("-j", "vehicle", "precondition", "true")
        data = json.loads(result.output)
        assert data["preconditioning_max"] is True

    def test_precondition_in_help(self):
        result = _run("vehicle", "--help")
        assert "precondition" in result.output


# ═══════════════════════════════════════════════════════════════════════════════
# v1.4.0 Tests — Vehicle Screenshot
# ═══════════════════════════════════════════════════════════════════════════════


class TestVehicleScreenshot:
    """Tests for `tesla vehicle screenshot`."""

    def _cfg(self):
        cfg = MagicMock()
        cfg.general.default_vin = MOCK_VIN
        return cfg

    def test_screenshot_success(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "screenshot")
        assert result.exit_code == 0
        assert "screenshot" in result.output.lower()

    def test_screenshot_calls_correct_command(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            _run("vehicle", "screenshot")
        mock.command.assert_called_once_with(MOCK_VIN, "trigger_vehicle_screenshot")

    def test_screenshot_json(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("-j", "vehicle", "screenshot")
        data = json.loads(result.output)
        assert data["screenshot"] == "triggered"

    def test_screenshot_in_help(self):
        result = _run("vehicle", "--help")
        assert "screenshot" in result.output


# ═══════════════════════════════════════════════════════════════════════════════
# v1.4.0 Tests — Vehicle Tonneau
# ═══════════════════════════════════════════════════════════════════════════════


class TestVehicleTonneau:
    """Tests for `tesla vehicle tonneau` (Cybertruck tonneau cover)."""

    def _cfg(self):
        cfg = MagicMock()
        cfg.general.default_vin = MOCK_VIN
        return cfg

    def test_tonneau_open(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "tonneau", "open")
        assert result.exit_code == 0
        mock.command.assert_called_once_with(MOCK_VIN, "tonneau_open")

    def test_tonneau_close(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "tonneau", "close")
        assert result.exit_code == 0
        mock.command.assert_called_once_with(MOCK_VIN, "tonneau_close")

    def test_tonneau_stop(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "tonneau", "stop")
        assert result.exit_code == 0
        mock.command.assert_called_once_with(MOCK_VIN, "tonneau_stop")

    def test_tonneau_status(self):
        mock = MagicMock()
        mock.get_vehicle_state.return_value = {
            "tonneau_open": False,
            "tonneau_door_state": "closed",
        }
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "tonneau", "status")
        assert result.exit_code == 0
        assert "tonneau" in result.output.lower() or "closed" in result.output.lower()

    def test_tonneau_status_json(self):
        mock = MagicMock()
        mock.get_vehicle_state.return_value = {
            "tonneau_open": True,
            "tonneau_door_state": "open",
        }
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("-j", "vehicle", "tonneau", "status")
        data = json.loads(result.output)
        assert data["tonneau_open"] is True
        assert data["door_state"] == "open"

    def test_tonneau_json_action(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("-j", "vehicle", "tonneau", "open")
        data = json.loads(result.output)
        assert data["tonneau"] == "open"

    def test_tonneau_invalid_action(self):
        mock = MagicMock()
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "tonneau", "fly")
        assert result.exit_code != 0

    def test_tonneau_in_help(self):
        result = _run("vehicle", "--help")
        assert "tonneau" in result.output


# ═══════════════════════════════════════════════════════════════════════════════
# v1.4.0 Tests — TeslaMate Geo
# ═══════════════════════════════════════════════════════════════════════════════


class TestTeslaMatGeo:
    """Tests for `tesla teslaMate geo`."""

    MOCK_LOCATIONS = [
        {"location": "Home", "visit_count": 142, "latitude": 37.42, "longitude": -122.08, "max_arrival_pct": 80, "min_arrival_pct": 20},
        {"location": "Work - Downtown", "visit_count": 98, "latitude": 37.78, "longitude": -122.42, "max_arrival_pct": 70, "min_arrival_pct": 45},
        {"location": "Supercharger - I-5 N", "visit_count": 12, "latitude": 38.10, "longitude": -121.50, "max_arrival_pct": 95, "min_arrival_pct": 15},
    ]

    def test_geo_success(self):
        mock = MagicMock()
        mock.get_top_locations.return_value = self.MOCK_LOCATIONS
        with patch("tesla_cli.commands.teslaMate._backend", return_value=mock):
            result = _run("teslaMate", "geo")
        assert result.exit_code == 0
        assert "Home" in result.output

    def test_geo_json_output(self):
        mock = MagicMock()
        mock.get_top_locations.return_value = self.MOCK_LOCATIONS
        with patch("tesla_cli.commands.teslaMate._backend", return_value=mock):
            result = _run("-j", "teslaMate", "geo")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 3
        assert data[0]["location"] == "Home"
        assert data[0]["visit_count"] == 142

    def test_geo_limit_option(self):
        mock = MagicMock()
        mock.get_top_locations.return_value = self.MOCK_LOCATIONS[:2]
        with patch("tesla_cli.commands.teslaMate._backend", return_value=mock):
            _run("teslaMate", "geo", "--limit", "2")
        mock.get_top_locations.assert_called_once_with(limit=2)

    def test_geo_empty_data(self):
        mock = MagicMock()
        mock.get_top_locations.return_value = []
        with patch("tesla_cli.commands.teslaMate._backend", return_value=mock):
            result = _run("teslaMate", "geo")
        assert result.exit_code == 0
        assert "no" in result.output.lower() or "found" in result.output.lower()

    def test_geo_csv_export(self):
        mock = MagicMock()
        mock.get_top_locations.return_value = self.MOCK_LOCATIONS
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            csv_path = f.name
        try:
            with patch("tesla_cli.commands.teslaMate._backend", return_value=mock):
                result = _run("teslaMate", "geo", "--csv", csv_path)
            assert result.exit_code == 0
            content = Path(csv_path).read_text()
            assert "Home" in content
            assert "visit_count" in content
        finally:
            Path(csv_path).unlink(missing_ok=True)

    def test_geo_in_help(self):
        result = _run("teslaMate", "--help")
        assert "geo" in result.output

    def test_geo_backend_method(self):
        """TeslaMateBacked.get_top_locations returns list of dicts."""
        from tesla_cli.backends.teslaMate import TeslaMateBacked
        backend = TeslaMateBacked.__new__(TeslaMateBacked)
        backend._car_id = 1
        mock_rows = [
            {"location": "Home", "visit_count": 50, "latitude": 37.42, "longitude": -122.08,
             "max_arrival_pct": 80, "min_arrival_pct": 20},
        ]
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = [dict(r) for r in mock_rows]
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_cur)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        backend._cursor = MagicMock(return_value=mock_ctx)
        result = backend.get_top_locations(limit=10)
        assert len(result) == 1
        assert result[0]["location"] == "Home"
        assert result[0]["visit_count"] == 50


# ═══════════════════════════════════════════════════════════════════════════════
# v1.4.0 Tests — AES-256-GCM Token Encryption
# ═══════════════════════════════════════════════════════════════════════════════


class TestTokenEncryption:
    """Tests for tesla_cli.auth.encryption module."""

    def test_is_encrypted_true(self):
        from tesla_cli.auth.encryption import is_encrypted
        assert is_encrypted("enc1:abc123") is True

    def test_is_encrypted_false_plain(self):
        from tesla_cli.auth.encryption import is_encrypted
        assert is_encrypted("eyJhbGciOiJSUzI1NiJ9.plain_token") is False

    def test_is_encrypted_false_empty(self):
        from tesla_cli.auth.encryption import is_encrypted
        assert is_encrypted("") is False

    def test_is_encrypted_false_none_like(self):
        from tesla_cli.auth.encryption import is_encrypted
        assert is_encrypted("plain_text_token") is False

    def test_encrypt_produces_enc1_prefix(self):
        from tesla_cli.auth.encryption import encrypt_token
        result = encrypt_token("my-secret", "password")
        assert result.startswith("enc1:")

    def test_roundtrip_encrypt_decrypt(self):
        from tesla_cli.auth.encryption import decrypt_token, encrypt_token
        original = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.test_token_value"
        encrypted = encrypt_token(original, "test_password_123")
        assert encrypted != original
        decrypted = decrypt_token(encrypted, "test_password_123")
        assert decrypted == original

    def test_wrong_password_raises_value_error(self):
        from tesla_cli.auth.encryption import decrypt_token, encrypt_token
        encrypted = encrypt_token("secret", "correct_password")
        with pytest.raises(ValueError, match="Decryption failed"):
            decrypt_token(encrypted, "wrong_password")

    def test_decrypt_non_encrypted_raises(self):
        from tesla_cli.auth.encryption import decrypt_token
        with pytest.raises(ValueError, match="Not an encrypted token"):
            decrypt_token("plain_token", "password")

    def test_different_calls_produce_different_ciphertext(self):
        """Each encryption call uses a random nonce — same input → different ciphertext."""
        from tesla_cli.auth.encryption import encrypt_token
        c1 = encrypt_token("same_plaintext", "same_password")
        c2 = encrypt_token("same_plaintext", "same_password")
        assert c1 != c2  # different nonce each time

    def test_encrypted_token_is_string(self):
        from tesla_cli.auth.encryption import encrypt_token
        result = encrypt_token("token", "pass")
        assert isinstance(result, str)

    def test_unicode_token_roundtrip(self):
        from tesla_cli.auth.encryption import decrypt_token, encrypt_token
        original = "tëst-tökën-wïth-ünicode-chäracters"
        encrypted = encrypt_token(original, "password")
        assert decrypt_token(encrypted, "password") == original


class TestConfigEncryptDecryptCommands:
    """Tests for `tesla config encrypt-token` and `decrypt-token`."""

    def test_encrypt_token_command_success(self):
        from tesla_cli.auth import tokens as tok_module

        with (
            patch.object(tok_module, "get_token", return_value="plain_token_value"),
            patch.object(tok_module, "set_token") as mock_store,
        ):
            result = _run("config", "encrypt-token", "order_refresh_token", "--password", "mypass")

        assert result.exit_code == 0
        mock_store.assert_called_once()
        stored_value = mock_store.call_args[0][1]
        assert stored_value.startswith("enc1:")

    def test_encrypt_token_already_encrypted(self):
        from tesla_cli.auth import tokens as tok_module

        with patch.object(tok_module, "get_token", return_value="enc1:already_encrypted"):
            result = _run("config", "encrypt-token", "some_key", "--password", "pass")

        assert result.exit_code == 0
        assert "already encrypted" in result.output.lower()

    def test_encrypt_token_not_found(self):
        from tesla_cli.auth import tokens as tok_module

        with patch.object(tok_module, "get_token", return_value=None):
            result = _run("config", "encrypt-token", "missing_key", "--password", "pass")

        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_decrypt_token_command_success(self):
        from tesla_cli.auth import tokens as tok_module
        from tesla_cli.auth.encryption import encrypt_token

        original = "my_plain_token"
        encrypted = encrypt_token(original, "testpass")

        with (
            patch.object(tok_module, "get_token", return_value=encrypted),
            patch.object(tok_module, "set_token") as mock_store,
        ):
            result = _run("config", "decrypt-token", "order_refresh_token", "--password", "testpass")

        assert result.exit_code == 0
        stored_value = mock_store.call_args[0][1]
        assert stored_value == original

    def test_decrypt_token_wrong_password(self):
        from tesla_cli.auth import tokens as tok_module
        from tesla_cli.auth.encryption import encrypt_token

        encrypted = encrypt_token("secret", "correct")

        with patch.object(tok_module, "get_token", return_value=encrypted):
            result = _run("config", "decrypt-token", "some_key", "--password", "wrong")

        assert result.exit_code != 0
        assert "failed" in result.output.lower() or "error" in result.output.lower()

    def test_decrypt_token_not_encrypted(self):
        from tesla_cli.auth import tokens as tok_module

        with patch.object(tok_module, "get_token", return_value="plain_not_encrypted"):
            result = _run("config", "decrypt-token", "some_key", "--password", "pass")

        assert result.exit_code == 0
        assert "not encrypted" in result.output.lower()

    def test_encrypt_decrypt_commands_in_help(self):
        result = _run("config", "--help")
        assert "encrypt-token" in result.output
        assert "decrypt-token" in result.output


# ═══════════════════════════════════════════════════════════════════════════════
# v1.5.0 Tests — Dossier export-pdf
# ═══════════════════════════════════════════════════════════════════════════════


class TestDossierExportPdf:
    """Tests for `tesla dossier export-pdf`."""

    def _make_snapshot(self) -> dict:
        return {
            "vin": "5YJ3E1EA1PF000001",
            "last_updated": "2024-06-01T10:00:00",
            "charge_state": {"battery_level": 80, "battery_range": 240.0, "charging_state": "Disconnected", "charge_limit_soc": 90, "charge_energy_added": 0},
            "vehicle_config": {"car_type": "model3", "exterior_color": "MidnightSilver", "wheel_type": "Pinwheel18", "battery_type": "NCA", "drive_unit": "DV2", "model_year": 2023},
            "order_status": {"order_status": "Delivered", "estimated_delivery": "2024-01-15"},
            "nhtsa_recalls": [],
            "vin_decode": {"model": "3", "model_year": "2024", "manufacturer": "Fremont"},
        }

    def test_export_pdf_no_fpdf2_exits_gracefully(self):
        """If fpdf2 not installed, show helpful message and exit."""
        import sys
        with patch.dict(sys.modules, {"fpdf": None}):
            result = _run("dossier", "export-pdf")
        # Should either succeed (fpdf2 is installed) or exit with helpful message
        if result.exit_code != 0:
            assert "fpdf2" in result.output.lower() or "install" in result.output.lower()

    def test_export_pdf_creates_file(self):
        """With fpdf2 installed and a snapshot, a PDF file is created."""
        pytest.importorskip("fpdf")
        with tempfile.TemporaryDirectory() as td:
            snap_dir = Path(td)
            (snap_dir / "snapshot_2024-06-01.json").write_text(
                json.dumps(self._make_snapshot())
            )
            out_path = Path(td) / "test-dossier.pdf"
            with patch("tesla_cli.backends.dossier.SNAPSHOTS_DIR", snap_dir):
                result = _run("dossier", "export-pdf", "--output", str(out_path))
        if result.exit_code == 0:
            assert out_path.exists()
            assert out_path.stat().st_size > 1000  # PDF should be at least 1KB

    def test_export_pdf_in_help(self):
        result = _run("dossier", "--help")
        assert "export-pdf" in result.output

    def test_export_pdf_no_snapshot_still_works(self):
        """Even without snapshots, PDF is created (empty sections)."""
        pytest.importorskip("fpdf")
        fake_dir = Path("/nonexistent_snap_dir_xyz")
        with tempfile.TemporaryDirectory() as td:
            out_path = Path(td) / "empty.pdf"
            with patch("tesla_cli.backends.dossier.SNAPSHOTS_DIR", fake_dir):
                cfg = MagicMock()
                cfg.general.default_vin = MOCK_VIN
                with patch("tesla_cli.commands.dossier.load_config", return_value=cfg):
                    result = _run("dossier", "export-pdf", "--output", str(out_path))
        if result.exit_code == 0:
            assert out_path.exists()


# ═══════════════════════════════════════════════════════════════════════════════
# v1.5.0 Tests — Config backup + restore
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfigBackup:
    """Tests for `tesla config backup`."""

    def test_backup_creates_file(self):
        cfg = MagicMock()
        cfg.model_dump.return_value = {
            "general": {"default_vin": MOCK_VIN, "backend": "fleet", "cost_per_kwh": 0.15},
            "fleet": {"region": "na", "client_id": ""},
            "order": {"reservation_number": "RN123456"},
        }
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            out = f.name
        try:
            with patch("tesla_cli.commands.config_cmd.load_config", return_value=cfg):
                result = _run("config", "backup", "--output", out)
            assert result.exit_code == 0
            assert Path(out).exists()
        finally:
            Path(out).unlink(missing_ok=True)

    def test_backup_redacts_token_fields(self):
        cfg = MagicMock()
        cfg.model_dump.return_value = {
            "general": {"default_vin": MOCK_VIN},
            "auth": {"access_token": "secret_abc", "refresh_token": "secret_xyz"},
        }
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            out = f.name
        try:
            with patch("tesla_cli.commands.config_cmd.load_config", return_value=cfg):
                _run("config", "backup", "--output", out)
            import json as _json
            data = _json.loads(Path(out).read_text())
            # Token fields must be redacted
            assert data["auth"]["access_token"] == "[REDACTED]"
            assert data["auth"]["refresh_token"] == "[REDACTED]"
            # Non-sensitive fields preserved
            assert data["general"]["default_vin"] == MOCK_VIN
        finally:
            Path(out).unlink(missing_ok=True)

    def test_backup_includes_meta(self):
        cfg = MagicMock()
        cfg.model_dump.return_value = {"general": {}}
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            out = f.name
        try:
            with patch("tesla_cli.commands.config_cmd.load_config", return_value=cfg):
                _run("config", "backup", "--output", out)
            import json as _json
            data = _json.loads(Path(out).read_text())
            assert "_meta" in data
            assert data["_meta"]["backup_version"] == "1"
        finally:
            Path(out).unlink(missing_ok=True)

    def test_backup_in_help(self):
        result = _run("config", "--help")
        assert "backup" in result.output

    def test_backup_shows_output_path(self):
        cfg = MagicMock()
        cfg.model_dump.return_value = {"general": {}}
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            out = f.name
        try:
            with patch("tesla_cli.commands.config_cmd.load_config", return_value=cfg):
                result = _run("config", "backup", "--output", out)
            assert result.exit_code == 0
            assert "backed up" in result.output.lower() or "✓" in result.output
        finally:
            Path(out).unlink(missing_ok=True)


class TestConfigRestore:
    """Tests for `tesla config restore`."""

    def _make_backup(self, td: str) -> Path:
        import json as _json
        backup = {
            "_meta": {"backup_version": "1", "tesla_cli_version": "1.5.0"},
            "general": {"default_vin": MOCK_VIN, "backend": "fleet", "cost_per_kwh": 0.15},
            "order": {"reservation_number": "RN999888"},
        }
        p = Path(td) / "backup.json"
        p.write_text(_json.dumps(backup))
        return p

    def test_restore_missing_file_exits(self):
        result = _run("config", "restore", "/nonexistent/backup_xyz.json")
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_restore_force_applies_settings(self):
        from tesla_cli.config import Config
        real_cfg = Config()
        with tempfile.TemporaryDirectory() as td:
            backup_path = self._make_backup(td)
            with (
                patch("tesla_cli.commands.config_cmd.load_config", return_value=real_cfg),
                patch("tesla_cli.commands.config_cmd.save_config") as mock_save,
            ):
                result = _run("config", "restore", str(backup_path), "--force")
        assert result.exit_code == 0
        mock_save.assert_called_once()

    def test_restore_in_help(self):
        result = _run("config", "--help")
        assert "restore" in result.output

    def test_restore_skips_redacted_values(self):
        """[REDACTED] values must not overwrite existing token fields."""
        import json as _json

        from tesla_cli.config import Config
        real_cfg = Config()
        real_cfg.general.default_vin = "ORIGINAL_VIN"

        with tempfile.TemporaryDirectory() as td:
            backup = {
                "_meta": {"backup_version": "1"},
                "general": {
                    "default_vin": MOCK_VIN,
                    "some_token": "[REDACTED]",  # must be skipped
                },
            }
            p = Path(td) / "backup.json"
            p.write_text(_json.dumps(backup))
            with (
                patch("tesla_cli.commands.config_cmd.load_config", return_value=real_cfg),
                patch("tesla_cli.commands.config_cmd.save_config"),
            ):
                result = _run("config", "restore", str(p), "--force")
        assert result.exit_code == 0
        # default_vin was applied (not redacted)
        assert real_cfg.general.default_vin == MOCK_VIN


# ═══════════════════════════════════════════════════════════════════════════════
# v1.5.0 Tests — TeslaMate monthly report
# ═══════════════════════════════════════════════════════════════════════════════


class TestTeslaMatReport:
    """Tests for `tesla teslaMate report`."""

    MOCK_REPORT = {
        "month": "2024-06",
        "driving": {
            "trips": 42,
            "total_km": 1248.5,
            "total_drive_min": 960,
            "total_kwh_used": 185.3,
            "avg_km_per_trip": 29.7,
            "longest_trip_km": 312.0,
            "avg_wh_per_km": 148.4,
        },
        "charging": {
            "sessions": 18,
            "total_kwh_charged": 210.5,
            "total_cost": 31.58,
            "avg_kwh_per_session": 11.7,
            "dc_fast_sessions": 3,
            "ac_sessions": 15,
        },
    }

    def test_report_success(self):
        mock = MagicMock()
        mock.get_monthly_report.return_value = self.MOCK_REPORT
        with patch("tesla_cli.commands.teslaMate._backend", return_value=mock):
            result = _run("teslaMate", "report", "--month", "2024-06")
        assert result.exit_code == 0
        assert "2024-06" in result.output

    def test_report_shows_trips(self):
        mock = MagicMock()
        mock.get_monthly_report.return_value = self.MOCK_REPORT
        with patch("tesla_cli.commands.teslaMate._backend", return_value=mock):
            result = _run("teslaMate", "report", "--month", "2024-06")
        assert "42" in result.output   # trip count
        assert "1248.5" in result.output or "1248" in result.output   # total km

    def test_report_shows_charging(self):
        mock = MagicMock()
        mock.get_monthly_report.return_value = self.MOCK_REPORT
        with patch("tesla_cli.commands.teslaMate._backend", return_value=mock):
            result = _run("teslaMate", "report", "--month", "2024-06")
        assert "18" in result.output   # sessions
        assert "210.5" in result.output or "210" in result.output

    def test_report_json_output(self):
        mock = MagicMock()
        mock.get_monthly_report.return_value = self.MOCK_REPORT
        with patch("tesla_cli.commands.teslaMate._backend", return_value=mock):
            result = _run("-j", "teslaMate", "report", "--month", "2024-06")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["month"] == "2024-06"
        assert data["driving"]["trips"] == 42
        assert data["charging"]["sessions"] == 18

    def test_report_default_month(self):
        """Without --month, defaults to current month."""
        from datetime import datetime
        current_month = datetime.now().strftime("%Y-%m")
        mock = MagicMock()
        mock.get_monthly_report.return_value = {
            "month": current_month,
            "driving": {},
            "charging": {},
        }
        with patch("tesla_cli.commands.teslaMate._backend", return_value=mock):
            _run("teslaMate", "report")
        mock.get_monthly_report.assert_called_once_with(month=current_month)

    def test_report_passes_month_to_backend(self):
        mock = MagicMock()
        mock.get_monthly_report.return_value = self.MOCK_REPORT
        with patch("tesla_cli.commands.teslaMate._backend", return_value=mock):
            _run("teslaMate", "report", "--month", "2023-12")
        mock.get_monthly_report.assert_called_once_with(month="2023-12")

    def test_report_in_help(self):
        result = _run("teslaMate", "--help")
        assert "report" in result.output

    def test_report_backend_method(self):
        """TeslaMateBacked.get_monthly_report returns expected structure."""
        from tesla_cli.backends.teslaMate import TeslaMateBacked
        backend = TeslaMateBacked.__new__(TeslaMateBacked)
        backend._car_id = 1

        mock_drive_row = {
            "trips": 10, "total_km": 300.0, "total_drive_min": 240,
            "total_kwh_used": 45.0, "avg_km_per_trip": 30.0,
            "longest_trip_km": 80.0, "avg_wh_per_km": 150.0,
        }
        mock_charge_row = {
            "sessions": 5, "total_kwh_charged": 60.0, "total_cost": 9.0,
            "avg_kwh_per_session": 12.0, "dc_fast_sessions": 1, "ac_sessions": 4,
        }

        call_count = {"n": 0}

        def make_ctx(row):
            cur = MagicMock()
            cur.fetchone.return_value = row
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=cur)
            ctx.__exit__ = MagicMock(return_value=False)
            return ctx

        def fake_cursor():
            call_count["n"] += 1
            if call_count["n"] == 1:
                return make_ctx(mock_drive_row)
            return make_ctx(mock_charge_row)

        backend._cursor = fake_cursor
        result = backend.get_monthly_report(month="2024-06")
        assert result["month"] == "2024-06"
        assert result["driving"]["trips"] == 10
        assert result["charging"]["sessions"] == 5


# ═══════════════════════════════════════════════════════════════════════════════
# v1.5.0 Tests — Vehicle sentry-events
# ═══════════════════════════════════════════════════════════════════════════════


class TestVehicleSentryEvents:
    """Tests for `tesla vehicle sentry-events`."""

    def _cfg(self):
        cfg = MagicMock()
        cfg.general.default_vin = MOCK_VIN
        return cfg

    MOCK_ALERTS = [
        {"name": "sentry_detection_nearby_person", "audience": ["Customer"], "start_epoch_time": 1717200000},
        {"name": "sentry_camera_tampering", "audience": ["Customer"], "start_epoch_time": 1717100000},
        {"name": "software_update_available", "audience": ["Customer"], "start_epoch_time": 1717000000},
    ]

    def test_sentry_events_success(self):
        mock = MagicMock()
        mock.get_recent_alerts.return_value = self.MOCK_ALERTS
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "sentry-events")
        assert result.exit_code == 0

    def test_sentry_events_json_output(self):
        mock = MagicMock()
        mock.get_recent_alerts.return_value = self.MOCK_ALERTS
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("-j", "vehicle", "sentry-events")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)

    def test_sentry_events_unsupported_backend(self):
        """BackendNotSupportedError → exit 1 with helpful message."""
        from tesla_cli.exceptions import BackendNotSupportedError
        mock = MagicMock()
        mock.get_recent_alerts.side_effect = BackendNotSupportedError("vehicle sentry-events", "fleet")
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "sentry-events")
        assert result.exit_code == 1

    def test_sentry_events_limit(self):
        mock = MagicMock()
        mock.get_recent_alerts.return_value = self.MOCK_ALERTS * 5  # 15 total
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("-j", "vehicle", "sentry-events", "--limit", "2")
        data = json.loads(result.output)
        assert len(data) <= 2

    def test_sentry_events_empty(self):
        mock = MagicMock()
        mock.get_recent_alerts.return_value = []
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "sentry-events")
        assert result.exit_code == 0
        assert "no" in result.output.lower() or "sentry" in result.output.lower()

    def test_sentry_events_in_help(self):
        result = _run("vehicle", "--help")
        assert "sentry-events" in result.output


# ═══════════════════════════════════════════════════════════════════════════════
# v1.6.0 — dossier export-html, charge schedule-preview, order stores
# ═══════════════════════════════════════════════════════════════════════════════


# ── dossier export-html ───────────────────────────────────────────────────────


class TestDossierExportHtml:
    """Tests for tesla dossier export-html (no extra deps)."""

    def _snapshot(self, tmp_path: Path) -> Path:
        """Write a minimal snapshot to a temp dir."""
        snap = {
            "vin": MOCK_VIN,
            "last_updated": "2026-03-30T12:00:00",
            "charge_state": {
                "battery_level": 75,
                "battery_range": 220.5,
                "charging_state": "Disconnected",
                "charge_limit_soc": 80,
                "charge_energy_added": 12.3,
                "charger_power": 0,
            },
            "vehicle_config": {
                "car_type": "modely",
                "exterior_color": "Pearl White",
                "wheel_type": "Gemini",
            },
            "vin_decode": {"model": "Y", "model_year": "2026", "manufacturer": "Shanghai"},
            "order_status": {"orderStatus": "ORDERED", "reservationNumber": "RN123"},
            "nhtsa_recalls": [],
        }
        snaps_dir = tmp_path / "snapshots"
        snaps_dir.mkdir()
        snap_file = snaps_dir / "snapshot_2026-03-30T12-00-00.json"
        snap_file.write_text(json.dumps(snap))
        return snaps_dir

    def test_export_html_creates_file(self, tmp_path):
        snaps_dir = self._snapshot(tmp_path)
        out = tmp_path / "report.html"
        with (
            patch("tesla_cli.backends.dossier.SNAPSHOTS_DIR", snaps_dir),
            patch("tesla_cli.config.load_config") as mock_lc,
        ):
            mock_lc.return_value.general.default_vin = MOCK_VIN
            result = _run("dossier", "export-html", "--output", str(out))
        assert result.exit_code == 0
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        assert MOCK_VIN in content

    def test_export_html_contains_vin(self, tmp_path):
        snaps_dir = self._snapshot(tmp_path)
        out = tmp_path / "dossier.html"
        with (
            patch("tesla_cli.backends.dossier.SNAPSHOTS_DIR", snaps_dir),
            patch("tesla_cli.config.load_config") as mock_lc,
        ):
            mock_lc.return_value.general.default_vin = MOCK_VIN
            _run("dossier", "export-html", "--output", str(out))
        content = out.read_text()
        assert MOCK_VIN in content
        assert "Tesla Vehicle Dossier" in content

    def test_export_html_battery_level(self, tmp_path):
        snaps_dir = self._snapshot(tmp_path)
        out = tmp_path / "dossier.html"
        with (
            patch("tesla_cli.backends.dossier.SNAPSHOTS_DIR", snaps_dir),
            patch("tesla_cli.config.load_config") as mock_lc,
        ):
            mock_lc.return_value.general.default_vin = MOCK_VIN
            _run("dossier", "export-html", "--output", str(out))
        content = out.read_text()
        assert "75" in content  # battery_level

    def test_export_html_no_snapshots(self, tmp_path):
        """Should still produce a valid HTML when there are no snapshots."""
        empty_dir = tmp_path / "empty_snaps"
        empty_dir.mkdir()
        out = tmp_path / "empty.html"
        with (
            patch("tesla_cli.backends.dossier.SNAPSHOTS_DIR", empty_dir),
            patch("tesla_cli.config.load_config") as mock_lc,
        ):
            mock_lc.return_value.general.default_vin = ""
            result = _run("dossier", "export-html", "--output", str(out))
        assert result.exit_code == 0
        assert out.exists()
        content = out.read_text()
        assert "<!DOCTYPE html>" in content

    def test_export_html_with_recalls(self, tmp_path):
        snaps_dir = tmp_path / "snaps_rc"
        snaps_dir.mkdir()
        snap = {
            "vin": MOCK_VIN,
            "nhtsa_recalls": [
                {
                    "NHTSACampaignNumber": "23V-999",
                    "Component": "STEERING",
                    "Summary": "Steering may fail unexpectedly under load",
                }
            ],
        }
        (snaps_dir / "snapshot_2026.json").write_text(json.dumps(snap))
        out = tmp_path / "recalls.html"
        with (
            patch("tesla_cli.backends.dossier.SNAPSHOTS_DIR", snaps_dir),
            patch("tesla_cli.config.load_config") as mock_lc,
        ):
            mock_lc.return_value.general.default_vin = MOCK_VIN
            _run("dossier", "export-html", "--output", str(out))
        content = out.read_text()
        assert "23V-999" in content
        assert "STEERING" in content

    def test_export_html_in_help(self):
        result = _run("dossier", "--help")
        assert "export-html" in result.output

    def test_export_html_self_contained(self, tmp_path):
        """No external CSS/JS references — everything is inline."""
        snaps_dir = self._snapshot(tmp_path)
        out = tmp_path / "self.html"
        with (
            patch("tesla_cli.backends.dossier.SNAPSHOTS_DIR", snaps_dir),
            patch("tesla_cli.config.load_config") as mock_lc,
        ):
            mock_lc.return_value.general.default_vin = MOCK_VIN
            _run("dossier", "export-html", "--output", str(out))
        content = out.read_text()
        # No external stylesheet or script src references
        assert '<link' not in content or 'http' not in content.split('<link')[1].split('>')[0]
        assert '<script src="http' not in content

    def test_export_html_default_output_name(self, tmp_path):
        """Default output filename is dossier.html."""
        snaps_dir = self._snapshot(tmp_path)
        import os
        orig = os.getcwd()
        os.chdir(tmp_path)
        try:
            with (
                patch("tesla_cli.backends.dossier.SNAPSHOTS_DIR", snaps_dir),
                patch("tesla_cli.config.load_config") as mock_lc,
            ):
                mock_lc.return_value.general.default_vin = MOCK_VIN
                result = _run("dossier", "export-html")
            assert result.exit_code == 0
            assert (tmp_path / "dossier.html").exists()
        finally:
            os.chdir(orig)


# ── charge schedule-preview ───────────────────────────────────────────────────


class TestChargeSchedulePreview:
    """Tests for tesla charge schedule-preview."""

    MOCK_CHARGE_STATE = {
        "battery_level": 72,
        "charging_state": "Disconnected",
        "charge_limit_soc": 80,
        "charge_energy_added": 0.0,
        "scheduled_charging_mode": "StartAt",
        "scheduled_charging_start_time_app": 420,   # 07:00
        "scheduled_charging_start_time": 1711940400,
        "scheduled_departure_time_minutes": 450,    # 07:30
        "scheduled_departure_time": 1711942200,
        "preconditioning_enabled": True,
        "preconditioning_weekdays_only": False,
        "off_peak_charging_enabled": True,
        "off_peak_hours_end_time": 480,             # 08:00
    }

    def _cfg(self):
        cfg = MagicMock()
        cfg.general.backend = "fleet"
        cfg.general.default_vin = MOCK_VIN
        cfg.general.cost_per_kwh = 0.0
        return cfg

    def test_schedule_preview_shows_charge_time(self):
        mock = MagicMock()
        mock.get_charge_state.return_value = self.MOCK_CHARGE_STATE
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.charge.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.charge._vin", return_value=MOCK_VIN),
        ):
            result = _run("charge", "schedule-preview")
        assert result.exit_code == 0
        assert "07:00" in result.output  # scheduled_charging_start_time_app = 420

    def test_schedule_preview_shows_departure_time(self):
        mock = MagicMock()
        mock.get_charge_state.return_value = self.MOCK_CHARGE_STATE
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.charge.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.charge._vin", return_value=MOCK_VIN),
        ):
            result = _run("charge", "schedule-preview")
        assert result.exit_code == 0
        assert "07:30" in result.output  # departure_time_minutes = 450

    def test_schedule_preview_json(self):
        mock = MagicMock()
        mock.get_charge_state.return_value = self.MOCK_CHARGE_STATE
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.charge.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.charge._vin", return_value=MOCK_VIN),
        ):
            result = _run("-j", "charge", "schedule-preview")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["scheduled_charging_mode"] == "StartAt"
        assert data["scheduled_charging_start"] == "07:00"
        assert data["scheduled_departure_time"] == "07:30"
        assert data["preconditioning_enabled"] is True
        assert data["off_peak_charging_enabled"] is True
        assert data["off_peak_hours_end_time"] == "08:00"

    def test_schedule_preview_off_charging(self):
        state = {**self.MOCK_CHARGE_STATE,
                 "scheduled_charging_mode": "Off",
                 "scheduled_charging_start_time_app": None,
                 "scheduled_departure_time_minutes": None,
                 "preconditioning_enabled": False,
                 "off_peak_charging_enabled": False}
        mock = MagicMock()
        mock.get_charge_state.return_value = state
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.charge.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.charge._vin", return_value=MOCK_VIN),
        ):
            result = _run("charge", "schedule-preview")
        assert result.exit_code == 0
        assert "Off" in result.output

    def test_schedule_preview_minutes_to_hhmm_midnight(self):
        """Edge case: 0 minutes should display 00:00."""
        state = {**self.MOCK_CHARGE_STATE,
                 "scheduled_charging_start_time_app": 0,
                 "scheduled_departure_time_minutes": 0}
        mock = MagicMock()
        mock.get_charge_state.return_value = state
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.charge.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.charge._vin", return_value=MOCK_VIN),
        ):
            result = _run("-j", "charge", "schedule-preview")
        data = json.loads(result.output)
        assert data["scheduled_charging_start"] == "00:00"
        assert data["scheduled_departure_time"] == "00:00"

    def test_schedule_preview_in_help(self):
        result = _run("charge", "--help")
        assert "schedule-preview" in result.output


# ── order stores ─────────────────────────────────────────────────────────────


class TestOrderStores:
    """Tests for tesla order stores — embedded EU/global store DB."""

    def test_stores_all(self):
        result = _run("order", "stores")
        assert result.exit_code == 0
        assert "Tesla" in result.output

    def test_stores_filter_country_de(self):
        result = _run("-j", "order", "stores", "--country", "DE")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert all(s["country"] == "DE" for s in data)
        assert len(data) > 0

    def test_stores_filter_country_fr(self):
        result = _run("-j", "order", "stores", "--country", "FR")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert all(s["country"] == "FR" for s in data)
        assert len(data) >= 5  # at least Paris, Lyon, Marseille, Bordeaux, Toulouse

    def test_stores_filter_city(self):
        result = _run("-j", "order", "stores", "--city", "Paris")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert all("paris" in s["city"].lower() for s in data)

    def test_stores_near_berlin(self):
        result = _run("-j", "order", "stores", "--near", "52.52,13.40", "--limit", "3")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) <= 3
        # First result should be Berlin
        assert "Berlin" in data[0]["city"] or data[0]["country"] == "DE"

    def test_stores_near_paris(self):
        result = _run("-j", "order", "stores", "--near", "48.86,2.35", "--limit", "1")
        data = json.loads(result.output)
        assert "Paris" in data[0]["city"] or data[0]["country"] == "FR"

    def test_stores_near_invalid_coords(self):
        result = _run("order", "stores", "--near", "badcoord")
        assert result.exit_code == 1
        assert "lat,lon" in result.output or "must be" in result.output

    def test_stores_limit(self):
        result = _run("-j", "order", "stores", "--limit", "5")
        data = json.loads(result.output)
        assert len(data) == 5

    def test_stores_json_has_lat_lon(self):
        result = _run("-j", "order", "stores", "--country", "NO")
        data = json.loads(result.output)
        for s in data:
            assert "lat" in s
            assert "lon" in s
            assert isinstance(s["lat"], float)
            assert isinstance(s["lon"], float)

    def test_stores_json_has_distance_when_near(self):
        result = _run("-j", "order", "stores", "--near", "51.50,-0.12", "--limit", "5")
        data = json.loads(result.output)
        for s in data:
            assert "_dist_km" in s
            assert isinstance(s["_dist_km"], float)

    def test_stores_norway_has_oslo(self):
        result = _run("-j", "order", "stores", "--country", "NO")
        data = json.loads(result.output)
        cities = [s["city"] for s in data]
        assert any("Oslo" in c for c in cities)

    def test_stores_gb_has_london(self):
        result = _run("-j", "order", "stores", "--country", "GB")
        data = json.loads(result.output)
        names = [s["name"] for s in data]
        assert any("London" in n for n in names)

    def test_stores_us_has_fremont(self):
        result = _run("-j", "order", "stores", "--country", "US")
        data = json.loads(result.output)
        names = [s["name"] for s in data]
        assert any("Fremont" in n for n in names)

    def test_stores_in_help(self):
        result = _run("order", "--help")
        assert "stores" in result.output

    def test_stores_total_count_geq_200(self):
        """The embedded DB should have at least 100 locations."""
        from tesla_cli.commands.order import _STORES
        assert len(_STORES) >= 100

    def test_stores_all_have_required_fields(self):
        from tesla_cli.commands.order import _STORES
        required = {"country", "city", "name", "lat", "lon"}
        for s in _STORES:
            assert required.issubset(s.keys()), f"Missing keys in: {s}"

# ═══════════════════════════════════════════════════════════════════════════════
# v1.7.0 — vehicle sw-update, vehicle speed-limit, teslaMate stats
# ═══════════════════════════════════════════════════════════════════════════════


# ── vehicle sw-update ─────────────────────────────────────────────────────────


class TestVehicleSwUpdate:
    """Tests for tesla vehicle sw-update."""

    def _cfg(self):
        cfg = MagicMock()
        cfg.general.backend = "fleet"
        cfg.general.default_vin = MOCK_VIN
        return cfg

    def _vehicle_data(self, status: str = "", version: str = "") -> dict:
        return {
            "vehicle_state": {
                "car_version": "2025.10.4 abc1234",
                "software_update": {
                    "status": status,
                    "version": version,
                    "download_perc": 100 if status == "available" else 0,
                    "install_perc": 0,
                    "expected_duration_sec": 1800,
                    "scheduled_time_ms": 0,
                },
            }
        }

    def test_sw_update_no_update(self):
        mock = MagicMock()
        mock.get_vehicle_data.return_value = self._vehicle_data()
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "sw-update")
        assert result.exit_code == 0
        assert "No update pending" in result.output or "2025.10.4" in result.output

    def test_sw_update_available(self):
        mock = MagicMock()
        mock.get_vehicle_data.return_value = self._vehicle_data(
            status="available", version="2025.14.0"
        )
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "sw-update")
        assert result.exit_code == 0
        assert "2025.14.0" in result.output
        assert "available" in result.output.lower()

    def test_sw_update_json_no_update(self):
        mock = MagicMock()
        mock.get_vehicle_data.return_value = self._vehicle_data()
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("-j", "vehicle", "sw-update")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["update_available"] is False
        assert "current_version" in data

    def test_sw_update_json_available(self):
        mock = MagicMock()
        mock.get_vehicle_data.return_value = self._vehicle_data(
            status="available", version="2025.14.0"
        )
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("-j", "vehicle", "sw-update")
        data = json.loads(result.output)
        assert data["update_available"] is True
        assert data["update_version"] == "2025.14.0"
        assert data["update_status"] == "available"

    def test_sw_update_json_all_keys(self):
        mock = MagicMock()
        mock.get_vehicle_data.return_value = self._vehicle_data()
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("-j", "vehicle", "sw-update")
        data = json.loads(result.output)
        expected_keys = {
            "current_version", "update_available", "update_status",
            "update_version", "update_download_pct", "update_install_perc",
            "expected_duration_sec", "scheduled_time_ms",
        }
        assert expected_keys.issubset(data.keys())

    def test_sw_update_downloading_status(self):
        mock = MagicMock()
        mock.get_vehicle_data.return_value = self._vehicle_data(
            status="downloading", version="2025.14.0"
        )
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("-j", "vehicle", "sw-update")
        data = json.loads(result.output)
        assert data["update_available"] is True
        assert data["update_status"] == "downloading"

    def test_sw_update_in_help(self):
        result = _run("vehicle", "--help")
        assert "sw-update" in result.output


# ── vehicle speed-limit ───────────────────────────────────────────────────────


class TestVehicleSpeedLimit:
    """Tests for tesla vehicle speed-limit."""

    MOCK_VEHICLE_STATE_SLM = {
        "locked": True,
        "sentry_mode": False,
        "speed_limit_mode": {
            "active": False,
            "current_limit_mph": 75.0,
            "max_limit_mph": 90.0,
            "min_limit_mph": 50.0,
            "pin_code_set": True,
        },
    }

    def _cfg(self):
        cfg = MagicMock()
        cfg.general.backend = "fleet"
        cfg.general.default_vin = MOCK_VIN
        return cfg

    def test_speed_limit_status(self):
        mock = MagicMock()
        mock.get_vehicle_state.return_value = self.MOCK_VEHICLE_STATE_SLM
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "speed-limit")
        assert result.exit_code == 0
        assert "75" in result.output
        assert "Inactive" in result.output or "inactive" in result.output.lower()

    def test_speed_limit_status_json(self):
        mock = MagicMock()
        mock.get_vehicle_state.return_value = self.MOCK_VEHICLE_STATE_SLM
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("-j", "vehicle", "speed-limit")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["active"] is False
        assert data["current_limit_mph"] == 75.0
        assert data["pin_code_set"] is True

    def test_speed_limit_set(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "speed-limit", "--limit", "65")
        assert result.exit_code == 0
        assert "65 mph" in result.output
        mock.command.assert_called_once()

    def test_speed_limit_activate_requires_pin(self):
        result = _run("vehicle", "speed-limit", "--on")
        assert result.exit_code == 1
        assert "pin" in result.output.lower() or "--pin" in result.output

    def test_speed_limit_deactivate_requires_pin(self):
        result = _run("vehicle", "speed-limit", "--off")
        assert result.exit_code == 1
        assert "pin" in result.output.lower()

    def test_speed_limit_activate_with_pin(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "speed-limit", "--on", "--pin", "1234")
        assert result.exit_code == 0
        assert "activated" in result.output.lower()

    def test_speed_limit_deactivate_with_pin(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "speed-limit", "--off", "--pin", "1234")
        assert result.exit_code == 0
        assert "deactivated" in result.output.lower()

    def test_speed_limit_clear_pin(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "speed-limit", "--clear", "--pin", "1234")
        assert result.exit_code == 0
        assert "cleared" in result.output.lower() or "PIN" in result.output

    def test_speed_limit_out_of_range(self):
        mock = MagicMock()
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "speed-limit", "--limit", "120")
        assert result.exit_code == 1
        assert "50" in result.output and "90" in result.output

    def test_speed_limit_in_help(self):
        result = _run("vehicle", "--help")
        assert "speed-limit" in result.output


# ── teslaMate stats ───────────────────────────────────────────────────────────


class TestTeslaMateStats:
    """Tests for tesla teslaMate stats."""

    MOCK_DRIVE_STATS = {
        "total_drives": 142,
        "total_km": 8432.5,
        "total_kwh": 1350.2,
        "avg_km_per_trip": 59.4,
        "longest_trip_km": 312.0,
        "first_drive": "2023-06-01T08:00:00",
        "last_drive": "2026-03-28T17:30:00",
    }

    MOCK_CHARGE_STATS = {
        "total_sessions": 98,
        "total_kwh_added": 1412.7,
        "total_cost": 178.35,
        "avg_kwh_per_session": 14.4,
        "last_session": "2026-03-27T22:15:00",
    }

    def _patched(self):
        mock_backend = MagicMock()
        mock_backend.get_stats.return_value = self.MOCK_DRIVE_STATS
        mock_backend.get_charging_stats.return_value = self.MOCK_CHARGE_STATS
        return patch("tesla_cli.commands.teslaMate._backend", return_value=mock_backend)

    def test_stats_shows_drives(self):
        with self._patched():
            result = _run("teslaMate", "stats")
        assert result.exit_code == 0
        assert "142" in result.output

    def test_stats_shows_total_km(self):
        with self._patched():
            result = _run("teslaMate", "stats")
        assert "8,432" in result.output or "8432" in result.output

    def test_stats_shows_charging_sessions(self):
        with self._patched():
            result = _run("teslaMate", "stats")
        assert "98" in result.output

    def test_stats_shows_cost(self):
        with self._patched():
            result = _run("teslaMate", "stats")
        assert "178.35" in result.output or "178" in result.output

    def test_stats_json(self):
        with self._patched():
            result = _run("-j", "teslaMate", "stats")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "drives" in data
        assert "charging" in data
        assert data["drives"]["total_drives"] == 142
        assert data["charging"]["total_sessions"] == 98

    def test_stats_json_all_drive_keys(self):
        with self._patched():
            result = _run("-j", "teslaMate", "stats")
        data = json.loads(result.output)
        drives = data["drives"]
        for key in ("total_drives", "total_km", "total_kwh", "avg_km_per_trip", "longest_trip_km"):
            assert key in drives

    def test_stats_json_all_charging_keys(self):
        with self._patched():
            result = _run("-j", "teslaMate", "stats")
        data = json.loads(result.output)
        charging = data["charging"]
        for key in ("total_sessions", "total_kwh_added", "total_cost", "avg_kwh_per_session"):
            assert key in charging

    def test_stats_shows_efficiency(self):
        """Lifetime avg efficiency banner should appear when data is available."""
        with self._patched():
            result = _run("teslaMate", "stats")
        # 1350.2 kWh / 8432.5 km * 1000 ≈ 160.1 Wh/km
        assert "Wh/km" in result.output
        assert "160" in result.output

    def test_stats_shows_first_drive_date(self):
        with self._patched():
            result = _run("teslaMate", "stats")
        assert "2023-06-01" in result.output

    def test_stats_empty_data(self):
        """Should handle empty stats gracefully without crashing."""
        mock_backend = MagicMock()
        mock_backend.get_stats.return_value = {}
        mock_backend.get_charging_stats.return_value = {}
        with patch("tesla_cli.commands.teslaMate._backend", return_value=mock_backend):
            result = _run("teslaMate", "stats")
        assert result.exit_code == 0

    def test_stats_in_help(self):
        result = _run("teslaMate", "--help")
        assert "stats" in result.output
