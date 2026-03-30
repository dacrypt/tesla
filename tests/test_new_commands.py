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
        set_lang("fr")  # French not implemented yet
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
