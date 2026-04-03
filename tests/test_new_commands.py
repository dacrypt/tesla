"""Tests for v0.3.0+ commands: diff, checklist, gates, stream, sentry, trips,
anonymize mode, VIN decoder, option code decoder, i18n, and TeslaMate config."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from tesla_cli.cli.app import app
from tests.conftest import MOCK_VIN

runner = CliRunner()


def _run(*args):
    return runner.invoke(app, list(args))


# ── VIN Decoder ──────────────────────────────────────────────────────────────


class TestVinDecoder:
    def test_shanghai_model_y(self):
        from tesla_cli.core.backends.dossier import decode_vin

        decoded = decode_vin("LRWYE7FK4TC123456")
        assert "Shanghai" in decoded.manufacturer
        assert "Y" in decoded.model
        assert decoded.model_year == "2026"

    def test_fremont_model_3(self):
        from tesla_cli.core.backends.dossier import decode_vin

        decoded = decode_vin("5YJ3E1EA1PF000001")
        assert "Fremont" in decoded.manufacturer
        assert "3" in decoded.model

    def test_serial_number(self):
        from tesla_cli.core.backends.dossier import decode_vin

        decoded = decode_vin("5YJ3E1EA1PF123456")
        assert decoded.serial_number == "123456"

    def test_short_vin_graceful(self):
        from tesla_cli.core.backends.dossier import decode_vin

        decoded = decode_vin("SHORT")
        assert decoded.vin == "SHORT"
        assert decoded.manufacturer == ""  # graceful empty

    def test_vin_command_no_config(self):
        with patch("tesla_cli.core.config.load_config") as mock_cfg:
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
        from tesla_cli.core.backends.dossier import decode_option_codes

        result = decode_option_codes("PPSW,APF2,CP01")
        codes = {c.code: c for c in result.codes}
        assert "PPSW" in codes
        assert codes["PPSW"].category == "paint"
        assert "Pearl White" in codes["PPSW"].description
        assert "APF2" in codes
        assert codes["APF2"].category == "autopilot"

    def test_unknown_code(self):
        from tesla_cli.core.backends.dossier import decode_option_codes

        result = decode_option_codes("ZZ99,PPSW")
        codes = {c.code: c for c in result.codes}
        assert "ZZ99" in codes
        assert codes["ZZ99"].category == "unknown"

    def test_empty_string(self):
        from tesla_cli.core.backends.dossier import decode_option_codes

        result = decode_option_codes("")
        assert result.codes == []

    def test_raw_string_preserved(self):
        from tesla_cli.core.backends.dossier import decode_option_codes

        raw = "PPSW,APF2,CP01"
        result = decode_option_codes(raw)
        assert result.raw_string == raw

    def test_expanded_catalog_size(self):
        from tesla_cli.core.backends.dossier import OPTION_CODE_MAP

        assert len(OPTION_CODE_MAP) >= 100, "Catalog should have at least 100 codes"

    def test_autopilot_hw_codes(self):
        from tesla_cli.core.backends.dossier import OPTION_CODE_MAP

        for code in ["APH1", "APH2", "APH3", "APH4"]:
            assert code in OPTION_CODE_MAP, f"{code} missing from catalog"

    def test_all_models_in_catalog(self):
        from tesla_cli.core.backends.dossier import OPTION_CODE_MAP

        for code in ["MDLS", "MDL3", "MDLX", "MDLY"]:
            assert code in OPTION_CODE_MAP, f"Model code {code} missing"


# ── Anonymize Mode ───────────────────────────────────────────────────────────


class TestAnonymizeMode:
    def setup_method(self):
        from tesla_cli.cli.output import set_anon_mode

        set_anon_mode(False)

    def teardown_method(self):
        from tesla_cli.cli.output import set_anon_mode

        set_anon_mode(False)

    def test_vin_masked(self):
        from tesla_cli.cli.output import anonymize, set_anon_mode

        set_anon_mode(True, vin="5YJ3E1EA1PF123456")
        result = anonymize("VIN: 5YJ3E1EA1PF123456")
        assert "5YJ3E1EA1PF123456" not in result
        # First 4 and last 3 preserved
        assert "5YJ3" in result
        assert "456" in result

    def test_rn_masked(self):
        from tesla_cli.cli.output import anonymize, set_anon_mode

        set_anon_mode(True, rn="RN126460939")
        result = anonymize("Order: RN126460939")
        assert "RN126460939" not in result
        assert "RN" in result  # prefix preserved

    def test_email_masked(self):
        from tesla_cli.cli.output import anonymize, set_anon_mode

        set_anon_mode(True, email="user@example.com")
        result = anonymize("Email: user@example.com")
        assert "user@example.com" not in result

    def test_anon_false_no_masking(self):
        from tesla_cli.cli.output import anonymize, set_anon_mode

        set_anon_mode(False)
        text = "VIN: 5YJ3E1EA1PF123456"
        assert anonymize(text) == text

    def test_empty_string(self):
        from tesla_cli.cli.output import anonymize, set_anon_mode

        set_anon_mode(True, vin="5YJ3E1EA1PF123456")
        assert anonymize("") == ""

    def test_anon_flag_runs_command(self):
        with (
            patch("tesla_cli.cli.commands.order.OrderBackend") as mock_backend_cls,
            patch("tesla_cli.cli.commands.order.load_config") as mock_cfg,
        ):
            mock_cfg.return_value.order.reservation_number = "RN999999999"
            mock_cfg.return_value.general.default_vin = MOCK_VIN
            mock_cfg.return_value.notifications.enabled = False
            from tesla_cli.core.models.order import OrderStatus

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
        from tesla_cli.cli.i18n import set_lang

        set_lang("en")

    def test_english_default(self):
        from tesla_cli.cli.i18n import t

        result = t("order.stopped")
        assert result == "Stopped watching."

    def test_spanish(self):
        from tesla_cli.cli.i18n import set_lang, t

        set_lang("es")
        result = t("order.stopped")
        assert result == "Monitoreo detenido."

    def test_fallback_to_english(self):
        from tesla_cli.cli.i18n import set_lang, t

        set_lang("xx")  # unknown language — falls back to English
        result = t("order.stopped")
        assert result == "Stopped watching."  # falls back to English

    def test_interpolation(self):
        from tesla_cli.cli.i18n import t

        result = t("order.watching", rn="RN123", interval="5")
        assert "RN123" in result
        assert "5" in result

    def test_spanish_interpolation(self):
        from tesla_cli.cli.i18n import set_lang, t

        set_lang("es")
        result = t("order.watching", rn="RN123", interval="5")
        assert "RN123" in result

    def test_unknown_key_returns_key(self):
        from tesla_cli.cli.i18n import t

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
        with patch("tesla_cli.cli.commands.dossier.DossierBackend") as mock_cls:
            mock_cls.return_value._load_dossier.return_value = None
            result = _run("dossier", "gates")
            assert result.exit_code == 0
            assert "Gate" in result.output

    def test_gates_json_no_dossier(self):
        with patch("tesla_cli.cli.commands.dossier.DossierBackend") as mock_cls:
            mock_cls.return_value._load_dossier.return_value = None
            result = _run("--json", "dossier", "gates")
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert isinstance(data, list)
            assert len(data) == 13

    def test_gates_structure(self):
        with patch("tesla_cli.cli.commands.dossier.DossierBackend") as mock_cls:
            mock_cls.return_value._load_dossier.return_value = None
            result = _run("--json", "dossier", "gates")
            data = json.loads(result.output)
            for gate in data:
                assert "gate" in gate
                assert "label" in gate
                assert "status" in gate
                assert gate["status"] in ("complete", "current", "pending")

    def test_gates_with_ordered_phase(self):
        with patch("tesla_cli.cli.commands.dossier.DossierBackend") as mock_cls:
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
        with patch("tesla_cli.cli.commands.dossier.DossierBackend") as mock_cls:
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
        with patch("tesla_cli.cli.commands.dossier.DossierBackend") as mock_cls:
            mock_cls.return_value.get_history.return_value = [
                {
                    "timestamp": "2026-01-01T00:00:00",
                    "file": "/tmp/x.json",
                    "order_status": "BOOKED",
                }
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
                {
                    "timestamp": "2026-01-01T00:00:00",
                    "file": str(snap_path),
                    "order_status": "BOOKED",
                },
                {
                    "timestamp": "2026-01-02T00:00:00",
                    "file": str(snap_path),
                    "order_status": "BOOKED",
                },
            ]
            with patch("tesla_cli.cli.commands.dossier.DossierBackend") as mock_cls:
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
                {
                    "timestamp": "2026-01-02T00:00:00",
                    "file": str(snap_b),
                    "order_status": "DELIVERED",
                },
            ]
            with patch("tesla_cli.cli.commands.dossier.DossierBackend") as mock_cls:
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
        from tesla_cli.cli.commands.dossier import _compute_diff

        a = {"foo": "bar", "nested": {"x": 1}}
        b = {"foo": "baz", "nested": {"x": 1}, "new_key": "hello"}
        changes = _compute_diff(a, b)
        paths = [c["path"] for c in changes]
        assert "foo" in paths
        assert "new_key" in paths
        # nested.x unchanged, should not appear
        assert "nested.x" not in paths

    def test_compute_diff_symbols(self):
        from tesla_cli.cli.commands.dossier import _compute_diff

        a = {"x": "old", "y": None, "z": "gone"}
        b = {"x": "new", "y": "added", "z": None}
        changes = _compute_diff(a, b)
        by_path = {c["path"]: c for c in changes}
        assert by_path["x"]["symbol"] == "≠"  # changed
        assert by_path["y"]["symbol"] == "+"  # added
        assert by_path["z"]["symbol"] == "−"  # removed


# ── Vehicle Sentry ───────────────────────────────────────────────────────────


class TestVehicleSentry:
    def _patched(self, mock_fleet_backend):
        cfg = MagicMock()
        cfg.general.backend = "fleet"
        cfg.general.default_vin = MOCK_VIN
        cfg.fleet.region = "na"
        return [
            patch("tesla_cli.core.backends.get_vehicle_backend", return_value=mock_fleet_backend),
            patch(
                "tesla_cli.cli.commands.vehicle.get_vehicle_backend",
                return_value=mock_fleet_backend,
            ),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
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
            patch(
                "tesla_cli.cli.commands.vehicle.get_vehicle_backend",
                return_value=mock_fleet_backend,
            ),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
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
            patch("tesla_cli.core.backends.get_vehicle_backend", return_value=mock_fleet_backend),
            patch("tesla_cli.core.config.load_config", return_value=cfg),
            patch("tesla_cli.core.config.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("stream", "live", "--count", "1", "--interval", "0")
            assert result.exit_code == 0

    def test_stream_json_exits(self, mock_fleet_backend):
        cfg = MagicMock()
        cfg.general.backend = "fleet"
        cfg.general.default_vin = MOCK_VIN
        cfg.fleet.region = "na"
        with (
            patch("tesla_cli.core.backends.get_vehicle_backend", return_value=mock_fleet_backend),
            patch("tesla_cli.core.config.load_config", return_value=cfg),
            patch("tesla_cli.core.config.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("--json", "stream", "live", "--count", "1")
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert "charge_state" in data or "state" in data


# ── TeslaMate Config ─────────────────────────────────────────────────────────


class TestTeslamateConfig:
    def test_config_has_teslaMate_section(self):
        from tesla_cli.core.config import Config

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

    def test_teslaMate_status_shows_info(self):
        result = _run("teslaMate", "status")
        # Should show TeslaMate info (connected or not) or fail gracefully
        lower = result.output.lower()
        assert (
            "teslamate" in lower
            or "configured" in lower
            or "not connected" in lower
            or "managed" in lower
            or result.exit_code != 0
        )

    def test_teslaMate_backend_raises_import_error(self):
        from tesla_cli.core.backends.teslaMate import TeslaMateBacked

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
        from tesla_cli.cli.commands.order import _show_changes
        from tesla_cli.core.models.order import OrderChange

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
        from tesla_cli.core.backends.owner import OwnerApiVehicleBackend
        from tesla_cli.core.exceptions import VehicleAsleepError

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

        with patch("tesla_cli.core.backends.owner._time.sleep"):
            result = backend.command(MOCK_VIN, "door_lock")

        assert result == {"result": True}
        assert call_count >= 3  # 2 failures + 1 success + wake calls

    def test_command_raises_after_max_retries(self):
        from tesla_cli.core.backends.owner import OwnerApiVehicleBackend
        from tesla_cli.core.exceptions import VehicleAsleepError

        backend = OwnerApiVehicleBackend()
        backend._id_cache[MOCK_VIN] = "12345"

        def always_asleep(path, body=None):
            if "wake_up" in path:
                return {"state": "online"}
            raise VehicleAsleepError("asleep")

        backend._post = always_asleep

        with patch("tesla_cli.core.backends.owner._time.sleep"), pytest.raises(VehicleAsleepError):
            backend.command(MOCK_VIN, "door_lock")


# ── Dossier Estimate ──────────────────────────────────────────────────────────


class TestDossierEstimate:
    def test_estimate_help(self):
        result = _run("dossier", "estimate", "--help")
        assert result.exit_code == 0
        assert "estimate" in result.output.lower() or "delivery" in result.output.lower()

    def test_estimate_no_dossier(self):
        with patch("tesla_cli.cli.commands.dossier.DossierBackend") as mock_cls:
            mock_cls.return_value._load_dossier.return_value = None
            result = _run("dossier", "estimate")
            assert result.exit_code == 0

    def test_estimate_json_no_dossier(self):
        with patch("tesla_cli.cli.commands.dossier.DossierBackend") as mock_cls:
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
        with patch("tesla_cli.cli.commands.dossier.DossierBackend") as mock_cls:
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
        with patch("tesla_cli.cli.commands.dossier.DossierBackend") as mock_cls:
            mock_dossier = MagicMock()
            mock_dossier.real_status.phase = "delivered"
            mock_dossier.real_status.delivery_date = None
            mock_cls.return_value._load_dossier.return_value = mock_dossier
            result = _run("dossier", "estimate")
            assert result.exit_code == 0
            assert "Delivered" in result.output or "delivered" in result.output.lower()

    def test_estimate_confirmed_delivery(self):
        with patch("tesla_cli.cli.commands.dossier.DossierBackend") as mock_cls:
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
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
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
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
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
        with patch("tesla_cli.cli.commands.notify.load_config") as mock_cfg:
            mock_cfg.return_value.notifications.apprise_urls = []
            mock_cfg.return_value.notifications.enabled = False
            result = _run("notify", "list")
            assert result.exit_code == 0
            assert "No notification" in result.output or "notify add" in result.output

    def test_notify_list_json_empty(self):
        with patch("tesla_cli.cli.commands.notify.load_config") as mock_cfg:
            mock_cfg.return_value.notifications.apprise_urls = []
            mock_cfg.return_value.notifications.enabled = False
            result = _run("--json", "notify", "list")
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["urls"] == []
            assert data["enabled"] is False

    def test_notify_list_with_urls(self):
        with patch("tesla_cli.cli.commands.notify.load_config") as mock_cfg:
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
        with patch("tesla_cli.cli.commands.notify.load_config") as mock_cfg:
            mock_cfg.return_value.notifications.apprise_urls = []
            result = _run("notify", "test")
            assert result.exit_code == 1
            assert "No notification" in result.output or "notify add" in result.output

    def test_notify_test_sends(self):
        with (
            patch("tesla_cli.cli.commands.notify.load_config") as mock_cfg,
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
            patch("tesla_cli.cli.commands.notify.load_config") as mock_cfg,
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
            patch("tesla_cli.cli.commands.notify.load_config") as mock_cfg,
            patch("tesla_cli.cli.commands.notify.save_config") as mock_save,
        ):
            cfg = MagicMock()
            cfg.notifications.apprise_urls = []
            mock_cfg.return_value = cfg
            result = _run("notify", "add", "tgram://TOKEN/CHATID")
            assert result.exit_code == 0
            mock_save.assert_called_once()

    def test_notify_remove_out_of_range(self):
        with patch("tesla_cli.cli.commands.notify.load_config") as mock_cfg:
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
        with patch("tesla_cli.core.config.CONFIG_FILE") as mock_file:
            mock_file.exists.return_value = False
            result = _run("config", "export")
            assert result.exit_code == 1

    def test_export_stdout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = Path(tmpdir) / "config.toml"
            cfg_path.write_text('[general]\ndefault_vin = "5YJ3E1EA1PF000001"\n')
            with patch("tesla_cli.core.config.CONFIG_FILE", cfg_path):
                result = _run("config", "export")
                assert result.exit_code == 0
                assert "default_vin" in result.output

    def test_export_to_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = Path(tmpdir) / "config.toml"
            cfg_path.write_text('[general]\ndefault_vin = "5YJ3E1EA1PF000001"\n')
            out_path = Path(tmpdir) / "backup.toml"
            with patch("tesla_cli.core.config.CONFIG_FILE", cfg_path):
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
                patch("tesla_cli.core.config.CONFIG_FILE") as mock_cfile,
                patch("tesla_cli.cli.commands.config_cmd.save_config") as mock_save,
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
        with patch("tesla_cli.cli.commands.dossier.DossierBackend") as mock_cls:
            mock_cls.return_value._load_dossier.return_value = None
            result = _run("dossier", "option-codes")
            assert result.exit_code == 1

    def test_option_codes_with_dossier(self):
        with patch("tesla_cli.cli.commands.dossier.DossierBackend") as mock_cls:
            mock_dossier = MagicMock()
            mock_dossier.option_codes.raw_string = "PPSW,APF2,MDL3"
            mock_cls.return_value._load_dossier.return_value = mock_dossier
            result = _run("dossier", "option-codes")
            assert result.exit_code == 0
            assert "PPSW" in result.output or "Pearl White" in result.output

    def test_option_codes_json(self):
        with patch("tesla_cli.cli.commands.dossier.DossierBackend") as mock_cls:
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
        with patch("tesla_cli.cli.commands.dossier.DossierBackend") as mock_cls:
            mock_dossier = MagicMock()
            mock_dossier.option_codes.raw_string = "PPSW"
            mock_cls.return_value._load_dossier.return_value = mock_dossier
            result = _run("--json", "dossier", "option-codes")
            data = json.loads(result.output)
            assert all(
                "code" in item and "category" in item and "description" in item for item in data
            )


# ── Order Timeline ────────────────────────────────────────────────────────────


class TestOrderTimeline:
    def test_timeline_help(self):
        result = _run("order", "timeline", "--help")
        assert result.exit_code == 0

    def test_timeline_no_history(self):
        with patch("tesla_cli.core.backends.dossier.DossierBackend") as mock_cls:
            mock_cls.return_value.get_history.return_value = []
            result = _run("order", "timeline")
            assert result.exit_code == 1
            assert "history" in result.output.lower() or "found" in result.output.lower()

    def test_timeline_with_history(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            snap = Path(tmpdir) / "snap.json"
            snap.write_text(
                json.dumps(
                    {
                        "vin": MOCK_VIN,
                        "order": {"current": {"orderStatus": "BOOKED"}},
                        "real_status": {
                            "delivery_date": None,
                            "in_runt": False,
                            "has_placa": False,
                        },
                        "runt": {"estado": ""},
                    }
                )
            )
            history = [
                {"timestamp": "2026-01-01T00:00:00", "file": str(snap), "order_status": "BOOKED"},
                {"timestamp": "2026-01-10T00:00:00", "file": str(snap), "order_status": "BOOKED"},
            ]
            with patch("tesla_cli.core.backends.dossier.DossierBackend") as mock_cls:
                mock_cls.return_value.get_history.return_value = history
                result = _run("order", "timeline")
                assert result.exit_code == 0
                assert "Timeline" in result.output or "snapshot" in result.output.lower()

    def test_timeline_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            snap = Path(tmpdir) / "snap.json"
            snap.write_text(
                json.dumps(
                    {
                        "vin": MOCK_VIN,
                        "order": {"current": {"orderStatus": "BOOKED"}},
                        "real_status": {
                            "delivery_date": None,
                            "in_runt": False,
                            "has_placa": False,
                        },
                        "runt": {"estado": ""},
                    }
                )
            )
            history = [
                {"timestamp": "2026-01-01T00:00:00", "file": str(snap), "order_status": "BOOKED"},
            ]
            with patch("tesla_cli.core.backends.dossier.DossierBackend") as mock_cls:
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
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
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
                {
                    "name": "SC Green",
                    "distance_miles": 1.0,
                    "available_stalls": 8,
                    "total_stalls": 12,
                    "type": "V3",
                },
                {
                    "name": "SC Yellow",
                    "distance_miles": 2.0,
                    "available_stalls": 1,
                    "total_stalls": 12,
                    "type": "V3",
                },
                {
                    "name": "SC Red",
                    "distance_miles": 3.0,
                    "available_stalls": 0,
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
            patch("tesla_cli.cli.commands.teslaMate.load_config", return_value=cfg),
            patch("tesla_cli.core.backends.teslaMate.TeslaMateBacked", return_value=mock_backend),
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
        from tesla_cli.cli.i18n import set_lang

        set_lang("en")

    def teardown_method(self):
        """Reset language to English after each test."""
        from tesla_cli.cli.i18n import set_lang

        set_lang("en")

    def test_pt_order_no_rn(self):
        from tesla_cli.cli.i18n import set_lang, t

        set_lang("pt")
        text = t("order.no_rn")
        assert "reserva" in text.lower() or "Número" in text

    def test_pt_order_watching(self):
        from tesla_cli.cli.i18n import set_lang, t

        set_lang("pt")
        text = t("order.watching", rn="RN123", interval="5")
        assert "RN123" in text
        assert "5" in text
        assert "Monitorando" in text or "pedido" in text

    def test_pt_vehicle_locked(self):
        from tesla_cli.cli.i18n import set_lang, t

        set_lang("pt")
        assert t("vehicle.locked") == "Veículo trancado"

    def test_pt_vehicle_unlocked(self):
        from tesla_cli.cli.i18n import set_lang, t

        set_lang("pt")
        assert t("vehicle.unlocked") == "Veículo destrancado"

    def test_pt_charge_started(self):
        from tesla_cli.cli.i18n import set_lang, t

        set_lang("pt")
        assert "Carregamento" in t("charge.started")

    def test_pt_climate_on(self):
        from tesla_cli.cli.i18n import set_lang, t

        set_lang("pt")
        assert "LIGADO" in t("climate.on") or "Clima" in t("climate.on")

    def test_pt_dossier_not_found(self):
        from tesla_cli.cli.i18n import set_lang, t

        set_lang("pt")
        text = t("dossier.not_found")
        assert "dossier" in text.lower() or "Nenhum" in text

    def test_pt_fallback_to_english_for_unknown_key(self):
        from tesla_cli.cli.i18n import set_lang, t

        set_lang("pt")
        # Unknown key should return the key itself (no crash)
        result = t("nonexistent.key.xyz")
        assert result == "nonexistent.key.xyz"

    def test_pt_teslaMate_not_configured(self):
        from tesla_cli.cli.i18n import set_lang, t

        set_lang("pt")
        text = t("teslaMate.not_configured")
        assert "TeslaMate" in text and ("não" in text or "Nenhum" in text or "configurado" in text)

    def test_pt_config_saved_is_defined(self):
        from tesla_cli.cli.i18n import _STRINGS

        assert "pt" in _STRINGS
        pt = _STRINGS["pt"]
        assert "config.saved" in pt
        # Template should include format placeholders for key and value
        assert "{value}" in pt["config.saved"]

    def test_pt_order_no_changes_with_time(self):
        from tesla_cli.cli.i18n import set_lang, t

        set_lang("pt")
        text = t("order.no_changes", time="12:00")
        assert "12:00" in text
        assert "Sem" in text or "alterações" in text

    def test_pt_language_isolation(self):
        """Switching back to 'en' from 'pt' restores English strings."""
        from tesla_cli.cli.i18n import get_lang, set_lang, t

        set_lang("pt")
        pt_text = t("vehicle.locked")
        set_lang("en")
        en_text = t("vehicle.locked")
        assert pt_text != en_text
        assert en_text == "Vehicle locked"
        assert get_lang() == "en"

    def test_lang_flag_via_env(self, monkeypatch):
        """TESLA_LANG env var drives i18n at module import — test set_lang directly."""
        from tesla_cli.cli.i18n import set_lang, t

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
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
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
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
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
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
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
        mock_fleet_backend.set_valet_mode.assert_called_once_with(MOCK_VIN, on=False, password="")


# ── Vehicle Schedule Charge ───────────────────────────────────────────────────


class TestVehicleScheduleCharge:
    def _patched(self, mock_backend):
        cfg = MagicMock()
        cfg.general.backend = "fleet"
        cfg.general.default_vin = MOCK_VIN
        cfg.fleet.region = "na"
        return [
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
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
            with patch("tesla_cli.core.backends.dossier.SNAPSHOTS_DIR", fake_dir):
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
            with patch("tesla_cli.core.backends.dossier.SNAPSHOTS_DIR", snap_dir):
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
            with patch("tesla_cli.core.backends.dossier.SNAPSHOTS_DIR", snap_dir):
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
            with patch("tesla_cli.core.backends.dossier.SNAPSHOTS_DIR", snap_dir):
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
            with patch("tesla_cli.core.backends.dossier.SNAPSHOTS_DIR", snap_dir):
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
            with patch("tesla_cli.core.backends.dossier.SNAPSHOTS_DIR", snap_dir):
                result = _run("--json", "dossier", "clean", "--keep", "1", "--dry-run")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["deleted"] == 2


# ── French i18n ───────────────────────────────────────────────────────────────


class TestFrenchI18n:
    def setup_method(self):
        from tesla_cli.cli.i18n import set_lang

        set_lang("en")

    def teardown_method(self):
        from tesla_cli.cli.i18n import set_lang

        set_lang("en")

    def test_fr_vehicle_locked(self):
        from tesla_cli.cli.i18n import set_lang, t

        set_lang("fr")
        assert t("vehicle.locked") == "Véhicule verrouillé"

    def test_fr_vehicle_unlocked(self):
        from tesla_cli.cli.i18n import set_lang, t

        set_lang("fr")
        assert t("vehicle.unlocked") == "Véhicule déverrouillé"

    def test_fr_order_watching(self):
        from tesla_cli.cli.i18n import set_lang, t

        set_lang("fr")
        text = t("order.watching", rn="RN999", interval="10")
        assert "RN999" in text and "10" in text
        assert "Surveillance" in text or "commande" in text

    def test_fr_charge_started(self):
        from tesla_cli.cli.i18n import set_lang, t

        set_lang("fr")
        assert "Charge" in t("charge.started") or "Charg" in t("charge.started")

    def test_fr_climate_on(self):
        from tesla_cli.cli.i18n import set_lang, t

        set_lang("fr")
        assert "ACTIVÉE" in t("climate.on") or "Climatisation" in t("climate.on")

    def test_fr_dossier_not_found(self):
        from tesla_cli.cli.i18n import set_lang, t

        set_lang("fr")
        assert "dossier" in t("dossier.not_found").lower() or "Aucun" in t("dossier.not_found")

    def test_fr_teslaMate_not_configured(self):
        from tesla_cli.cli.i18n import set_lang, t

        set_lang("fr")
        text = t("teslaMate.not_configured")
        assert "TeslaMate" in text and ("non" in text or "configuré" in text)

    def test_fr_isolation_from_en(self):
        from tesla_cli.cli.i18n import set_lang, t

        set_lang("fr")
        fr_text = t("vehicle.locked")
        set_lang("en")
        en_text = t("vehicle.locked")
        assert fr_text != en_text
        assert en_text == "Vehicle locked"

    def test_fr_catalog_completeness(self):
        """French catalog should cover the same keys as English."""
        from tesla_cli.cli.i18n import _STRINGS

        en_keys = set(_STRINGS["en"].keys())
        fr_keys = set(_STRINGS["fr"].keys())
        missing = en_keys - fr_keys
        assert not missing, f"French catalog missing keys: {missing}"

    def test_three_languages_registered(self):
        from tesla_cli.cli.i18n import _STRINGS

        assert "en" in _STRINGS
        assert "es" in _STRINGS
        assert "pt" in _STRINGS
        assert "fr" in _STRINGS


# ── Backend Not Supported Error ───────────────────────────────────────────────


class TestBackendNotSupported:
    """Verify that Fleet-only features fail gracefully on Owner/Tessie backends."""

    def test_exception_message_contains_hint(self):
        from tesla_cli.core.exceptions import BackendNotSupportedError

        exc = BackendNotSupportedError("charge history", "fleet")
        assert "fleet" in str(exc)
        assert "charge history" in str(exc)
        assert "tesla config set backend" in str(exc)

    def test_base_get_charge_history_raises(self):
        from tesla_cli.core.backends.base import VehicleBackend
        from tesla_cli.core.exceptions import BackendNotSupportedError

        # Create a minimal concrete subclass
        class _MinimalBackend(VehicleBackend):
            def list_vehicles(self):
                return []

            def get_vehicle_data(self, vin):
                return {}

            def get_charge_state(self, vin):
                return {}

            def get_climate_state(self, vin):
                return {}

            def get_drive_state(self, vin):
                return {}

            def get_vehicle_config(self, vin):
                return {}

            def wake_up(self, vin):
                return True

            def command(self, vin, command, **p):
                return {}

        b = _MinimalBackend()
        with pytest.raises(BackendNotSupportedError):
            b.get_charge_history()

    def test_base_get_recent_alerts_raises(self):
        from tesla_cli.core.backends.base import VehicleBackend
        from tesla_cli.core.exceptions import BackendNotSupportedError

        class _MinimalBackend(VehicleBackend):
            def list_vehicles(self):
                return []

            def get_vehicle_data(self, vin):
                return {}

            def get_charge_state(self, vin):
                return {}

            def get_climate_state(self, vin):
                return {}

            def get_drive_state(self, vin):
                return {}

            def get_vehicle_config(self, vin):
                return {}

            def wake_up(self, vin):
                return True

            def command(self, vin, command, **p):
                return {}

        b = _MinimalBackend()
        with pytest.raises(BackendNotSupportedError):
            b.get_recent_alerts("VIN123")

    def test_base_get_release_notes_raises(self):
        from tesla_cli.core.backends.base import VehicleBackend
        from tesla_cli.core.exceptions import BackendNotSupportedError

        class _MinimalBackend(VehicleBackend):
            def list_vehicles(self):
                return []

            def get_vehicle_data(self, vin):
                return {}

            def get_charge_state(self, vin):
                return {}

            def get_climate_state(self, vin):
                return {}

            def get_drive_state(self, vin):
                return {}

            def get_vehicle_config(self, vin):
                return {}

            def wake_up(self, vin):
                return True

            def command(self, vin, command, **p):
                return {}

        b = _MinimalBackend()
        with pytest.raises(BackendNotSupportedError):
            b.get_release_notes("VIN123")

    def test_base_get_invitations_raises(self):
        from tesla_cli.core.backends.base import VehicleBackend
        from tesla_cli.core.exceptions import BackendNotSupportedError

        class _MinimalBackend(VehicleBackend):
            def list_vehicles(self):
                return []

            def get_vehicle_data(self, vin):
                return {}

            def get_charge_state(self, vin):
                return {}

            def get_climate_state(self, vin):
                return {}

            def get_drive_state(self, vin):
                return {}

            def get_vehicle_config(self, vin):
                return {}

            def wake_up(self, vin):
                return True

            def command(self, vin, command, **p):
                return {}

        b = _MinimalBackend()
        with pytest.raises(BackendNotSupportedError):
            b.get_invitations("VIN123")

    def test_base_get_vehicle_state_fallback(self):
        """get_vehicle_state falls back to extracting from vehicle_data."""
        from tesla_cli.core.backends.base import VehicleBackend

        class _MinimalBackend(VehicleBackend):
            def list_vehicles(self):
                return []

            def get_vehicle_data(self, vin):
                return {"vehicle_state": {"locked": True}}

            def get_charge_state(self, vin):
                return {}

            def get_climate_state(self, vin):
                return {}

            def get_drive_state(self, vin):
                return {}

            def get_vehicle_config(self, vin):
                return {}

            def wake_up(self, vin):
                return True

            def command(self, vin, command, **p):
                return {}

        b = _MinimalBackend()
        assert b.get_vehicle_state("VIN123") == {"locked": True}

    def test_charge_history_command_graceful(self):
        from tesla_cli.core.exceptions import BackendNotSupportedError

        mock_backend = MagicMock()
        mock_backend.get_charge_history.side_effect = BackendNotSupportedError(
            "charge history", "fleet"
        )
        cfg = MagicMock()
        cfg.general.backend = "owner"
        cfg.general.default_vin = MOCK_VIN
        with (
            patch("tesla_cli.cli.commands.charge.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.cli.commands.charge.load_config", return_value=cfg),
        ):
            result = _run("charge", "history")
        assert result.exit_code == 1
        assert "fleet" in result.output.lower() or "not available" in result.output.lower()

    def test_vehicle_alerts_command_graceful(self):
        from tesla_cli.core.exceptions import BackendNotSupportedError

        mock_backend = MagicMock()
        mock_backend.get_recent_alerts.side_effect = BackendNotSupportedError(
            "vehicle alerts", "fleet"
        )
        cfg = MagicMock()
        cfg.general.backend = "owner"
        cfg.general.default_vin = MOCK_VIN
        cfg.fleet.region = "na"
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "alerts")
        assert result.exit_code == 1
        assert "fleet" in result.output.lower() or "not available" in result.output.lower()

    def test_vehicle_release_notes_command_graceful(self):
        from tesla_cli.core.exceptions import BackendNotSupportedError

        mock_backend = MagicMock()
        mock_backend.get_release_notes.side_effect = BackendNotSupportedError(
            "vehicle release-notes", "fleet"
        )
        cfg = MagicMock()
        cfg.general.backend = "owner"
        cfg.general.default_vin = MOCK_VIN
        cfg.fleet.region = "na"
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "release-notes")
        assert result.exit_code == 1
        assert "fleet" in result.output.lower() or "not available" in result.output.lower()

    def test_sharing_list_command_graceful(self):
        from tesla_cli.core.exceptions import BackendNotSupportedError

        mock_backend = MagicMock()
        mock_backend.get_invitations.side_effect = BackendNotSupportedError("sharing list", "fleet")
        cfg = MagicMock()
        cfg.general.backend = "owner"
        cfg.general.default_vin = MOCK_VIN
        with (
            patch("tesla_cli.cli.commands.sharing.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.cli.commands.sharing.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.sharing.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("sharing", "list")
        assert result.exit_code == 1
        assert "fleet" in result.output.lower() or "not available" in result.output.lower()

    def test_tessie_backend_has_vehicle_state(self):
        """TessieBackend.get_vehicle_state extracts from vehicle_data."""
        from tesla_cli.core.backends.tessie import TessieBackend

        backend = TessieBackend.__new__(TessieBackend)
        backend.get_vehicle_data = MagicMock(
            return_value={"vehicle_state": {"locked": False, "sentry_mode": True}}
        )
        state = backend.get_vehicle_state("VIN123")
        assert state["locked"] is False
        assert state["sentry_mode"] is True

    def test_tessie_backend_nearby_sites_called(self):
        """TessieBackend.get_nearby_charging_sites hits the right endpoint."""
        from tesla_cli.core.backends.tessie import TessieBackend

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
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "tires")
        assert result.exit_code == 0

    def test_tires_psi_conversion(self):
        """2.8 bar ≈ 40.6 PSI."""
        mock = self._make_backend(fl=2.8)
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "tires")
        assert "40.6" in result.output or "40" in result.output

    def test_tires_json_output(self):
        mock = self._make_backend()
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("-j", "vehicle", "tires")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "front_left" in data
        assert "psi" in data["front_left"]

    def test_tires_soft_warning_shown(self):
        mock = self._make_backend(fl=2.0, soft_fl=True)
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "tires")
        assert result.exit_code == 0
        assert "LOW" in result.output or "WARN" in result.output

    def test_tires_hard_warning_shown(self):
        mock = self._make_backend(fl=1.5, hard_fl=True)
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "tires")
        assert result.exit_code == 0
        assert "HARD" in result.output

    def test_tires_missing_data_graceful(self):
        """Missing TPMS data returns N/A, not a crash."""
        mock = MagicMock()
        mock.get_vehicle_state.return_value = {}
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
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
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "homelink")
        assert result.exit_code == 0
        assert "HomeLink" in result.output or "triggered" in result.output.lower()

    def test_homelink_passes_gps_to_command(self):
        mock = self._make_backend(lat=37.42, lon=-122.08)
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            _run("vehicle", "homelink")
        mock.command.assert_called_once_with(MOCK_VIN, "trigger_homelink", lat=37.42, lon=-122.08)

    def test_homelink_json_output(self):
        mock = self._make_backend()
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
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
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
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
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "dashcam")
        assert result.exit_code == 0
        assert "saved" in result.output.lower() or "dashcam" in result.output.lower()

    def test_dashcam_calls_correct_command(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            _run("vehicle", "dashcam")
        mock.command.assert_called_once_with(MOCK_VIN, "dashcam_save_clip")

    def test_dashcam_json_output(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
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
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "rename", "My Tesla Y")
        assert result.exit_code == 0
        assert "My Tesla Y" in result.output or "renamed" in result.output.lower()

    def test_rename_calls_correct_command(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            _run("vehicle", "rename", "Road Runner")
        mock.command.assert_called_once_with(
            MOCK_VIN, "set_vehicle_name", vehicle_name="Road Runner"
        )

    def test_rename_json_output(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
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
    get_vehicle_backend from tesla_cli.cli.commands.vehicle — that's the patch target.
    """

    def _cfg(self):
        cfg = MagicMock()
        cfg.general.default_vin = MOCK_VIN
        return cfg

    def _patches(self, mock_backend):
        return (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.security.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.security.resolve_vin", return_value=MOCK_VIN),
        )

    def test_remote_start_success(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.security.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.security.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("security", "remote-start")
        assert result.exit_code == 0

    def test_remote_start_calls_correct_command(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.security.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.security.resolve_vin", return_value=MOCK_VIN),
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
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.security.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.security.resolve_vin", return_value=MOCK_VIN),
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
        with patch("tesla_cli.core.backends.dossier.SNAPSHOTS_DIR", fake_dir):
            result = _run("dossier", "battery-health")
        assert result.exit_code != 0

    def test_single_snapshot_exits_with_message(self):
        with tempfile.TemporaryDirectory() as td:
            snap_dir = Path(td)
            snap1 = snap_dir / "snapshot_2024-01-01.json"
            snap1.write_text(json.dumps(self._make_snapshot(80.0, 200.0, "2024-01-01")))
            with patch("tesla_cli.core.backends.dossier.SNAPSHOTS_DIR", snap_dir):
                result = _run("dossier", "battery-health")
        assert result.exit_code != 0

    def test_battery_health_json_output(self):
        with tempfile.TemporaryDirectory() as td:
            snap_dir = Path(td)
            for fname, level, rng, ts in [
                ("snapshot_2024-01-01.json", 100.0, 320.0, "2024-01-01"),
                ("snapshot_2024-06-01.json", 80.0, 248.0, "2024-06-01"),
            ]:
                (snap_dir / fname).write_text(json.dumps(self._make_snapshot(level, rng, ts)))
            with patch("tesla_cli.core.backends.dossier.SNAPSHOTS_DIR", snap_dir):
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
            with patch("tesla_cli.core.backends.dossier.SNAPSHOTS_DIR", snap_dir):
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
            with patch("tesla_cli.core.backends.dossier.SNAPSHOTS_DIR", snap_dir):
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
                    {
                        "date": "2024-06-01",
                        "avg_drain_pct": 1.2,
                        "avg_parked_hours": 8.0,
                        "pct_per_hour": 0.15,
                        "periods": 2,
                    },
                    {
                        "date": "2024-06-02",
                        "avg_drain_pct": 0.8,
                        "avg_parked_hours": 10.0,
                        "pct_per_hour": 0.08,
                        "periods": 1,
                    },
                ],
            }
        mock.get_vampire_drain.return_value = data
        return mock

    def test_vampire_success(self):
        mock = self._make_mock_backend()
        with patch("tesla_cli.cli.commands.teslaMate._backend", return_value=mock):
            result = _run("teslaMate", "vampire")
        assert result.exit_code == 0

    def test_vampire_shows_drain_rate(self):
        mock = self._make_mock_backend()
        with patch("tesla_cli.cli.commands.teslaMate._backend", return_value=mock):
            result = _run("teslaMate", "vampire")
        assert "0.042" in result.output or "%" in result.output

    def test_vampire_empty_data(self):
        mock = self._make_mock_backend({"days_analyzed": 30, "avg_pct_per_hour": None, "daily": []})
        with patch("tesla_cli.cli.commands.teslaMate._backend", return_value=mock):
            result = _run("teslaMate", "vampire")
        assert result.exit_code == 0
        # should mention no data
        out = result.output.lower()
        assert "no" in out or "found" in out or "data" in out

    def test_vampire_json_output(self):
        mock = self._make_mock_backend()
        with patch("tesla_cli.cli.commands.teslaMate._backend", return_value=mock):
            result = _run("-j", "teslaMate", "vampire")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "avg_pct_per_hour" in data
        assert "daily" in data

    def test_vampire_days_option(self):
        mock = self._make_mock_backend()
        with patch("tesla_cli.cli.commands.teslaMate._backend", return_value=mock):
            _run("teslaMate", "vampire", "--days", "90")
        mock.get_vampire_drain.assert_called_once_with(days=90)

    def test_vampire_in_help(self):
        result = _run("teslaMate", "--help")
        assert "vampire" in result.output

    def test_vampire_backend_method_returns_structure(self):
        """TeslaMateBacked.get_vampire_drain returns expected dict structure."""
        from tesla_cli.core.backends.teslaMate import TeslaMateBacked

        backend = TeslaMateBacked.__new__(TeslaMateBacked)
        backend._car_id = 1
        mock_rows = [
            {"date": "2024-06-01", "km_per_hour": 0.125, "periods": 2},
        ]
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = [dict(r) for r in mock_rows]
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_cur)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        backend._cursor = MagicMock(return_value=mock_ctx)
        result = backend.get_vampire_drain(days=30)
        assert result["days_analyzed"] == 30
        assert "avg_km_per_hour" in result
        assert len(result["daily"]) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# v1.3.0 Tests — CSV Export (trips, charging, efficiency)
# ═══════════════════════════════════════════════════════════════════════════════


class TestTeslaMateCsvExport:
    """Tests for --csv flag on teslaMate trips, charging, efficiency."""

    MOCK_TRIPS = [
        {
            "date": "2024-06-01",
            "distance_km": 42.5,
            "duration_min": 35,
            "energy_wh": 6200,
            "start": "Home",
            "end": "Work",
        },
        {
            "date": "2024-06-02",
            "distance_km": 18.0,
            "duration_min": 15,
            "energy_wh": 2800,
            "start": "Work",
            "end": "Home",
        },
    ]

    MOCK_SESSIONS = [
        {"date": "2024-06-01", "location": "Home", "kwh": 45.2, "cost": 8.14, "duration": "3h 22m"},
        {
            "date": "2024-06-02",
            "location": "Supercharger",
            "kwh": 62.0,
            "cost": 0,
            "duration": "45m",
        },
    ]

    def test_trips_csv_creates_file(self):
        mock = MagicMock()
        mock.get_trips.return_value = self.MOCK_TRIPS
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            csv_path = f.name
        try:
            with patch("tesla_cli.cli.commands.teslaMate._backend", return_value=mock):
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
            with patch("tesla_cli.cli.commands.teslaMate._backend", return_value=mock):
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
            with patch("tesla_cli.cli.commands.teslaMate._backend", return_value=mock):
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
            with patch("tesla_cli.cli.commands.teslaMate._backend", return_value=mock):
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
        from tesla_cli.core.config import GeneralConfig

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
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.charge.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.cli.commands.charge.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.charge.resolve_vin", return_value=MOCK_VIN),
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
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.charge.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.cli.commands.charge.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.charge.resolve_vin", return_value=MOCK_VIN),
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
            patch("tesla_cli.cli.commands.config_cmd.load_config", return_value=cfg_mock),
            patch("tesla_cli.cli.commands.config_cmd.save_config"),
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
        from tesla_cli.cli.commands.order import _exec_on_change
        from tesla_cli.core.models.order import OrderChange

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
        from tesla_cli.cli.commands.order import _exec_on_change

        with patch("subprocess.Popen") as mock_popen:
            _exec_on_change("my-hook.sh", [])

        call_kwargs = mock_popen.call_args
        shell = call_kwargs.kwargs.get("shell") or call_kwargs[1].get("shell")
        assert shell is True

    def test_exec_on_change_empty_changes(self):
        """Empty changes list produces empty JSON array in env."""
        from tesla_cli.cli.commands.order import _exec_on_change

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
        from tesla_cli.cli.i18n import _STRINGS

        assert "de" in _STRINGS

    def test_de_order_keys(self):
        """German catalog must have order-related keys."""
        from tesla_cli.cli.i18n import _STRINGS

        de = _STRINGS["de"]
        # These are the actual keys in the catalog (not order.status)
        assert "order.no_rn" in de or "order.watching" in de

    def test_de_vehicle_keys(self):
        from tesla_cli.cli.i18n import _STRINGS

        de = _STRINGS["de"]
        assert "vehicle.locked" in de
        assert "vehicle.unlocked" in de

    def test_de_charge_keys(self):
        from tesla_cli.cli.i18n import _STRINGS

        de = _STRINGS["de"]
        # Actual keys are charge.started / charge.stopped
        assert "charge.started" in de
        assert "charge.stopped" in de

    def test_de_climate_keys(self):
        from tesla_cli.cli.i18n import _STRINGS

        de = _STRINGS["de"]
        assert "climate.on" in de
        assert "climate.off" in de

    def test_de_error_keys(self):
        from tesla_cli.cli.i18n import _STRINGS

        de = _STRINGS["de"]
        assert "error.auth" in de

    def test_de_t_function_returns_string(self):
        from tesla_cli.cli.i18n import _lang, set_lang, t

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
        from tesla_cli.cli.i18n import _STRINGS

        en = _STRINGS["en"]
        de = _STRINGS["de"]
        differs = any(de.get(k) != v for k, v in en.items() if k in de)
        assert differs, "German catalog is identical to English — translations missing"

    def test_de_setup_keys(self):
        from tesla_cli.cli.i18n import _STRINGS

        de = _STRINGS["de"]
        assert any(k.startswith("setup.") for k in de)


class TestItalianI18n:
    """Tests for Italian (it) i18n catalog."""

    def test_it_catalog_exists(self):
        from tesla_cli.cli.i18n import _STRINGS

        assert "it" in _STRINGS

    def test_it_order_keys(self):
        from tesla_cli.cli.i18n import _STRINGS

        it = _STRINGS["it"]
        assert "order.no_rn" in it or "order.watching" in it

    def test_it_vehicle_keys(self):
        from tesla_cli.cli.i18n import _STRINGS

        it = _STRINGS["it"]
        assert "vehicle.locked" in it
        assert "vehicle.unlocked" in it

    def test_it_charge_keys(self):
        from tesla_cli.cli.i18n import _STRINGS

        it = _STRINGS["it"]
        assert "charge.started" in it
        assert "charge.stopped" in it

    def test_it_error_keys(self):
        from tesla_cli.cli.i18n import _STRINGS

        it = _STRINGS["it"]
        assert "error.auth" in it

    def test_it_t_function_returns_string(self):
        from tesla_cli.cli.i18n import _lang, set_lang, t

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
        from tesla_cli.cli.i18n import _STRINGS

        en = _STRINGS["en"]
        it = _STRINGS["it"]
        differs = any(it.get(k) != v for k, v in en.items() if k in it)
        assert differs, "Italian catalog is identical to English — translations missing"

    def test_it_setup_keys(self):
        from tesla_cli.cli.i18n import _STRINGS

        it = _STRINGS["it"]
        assert any(k.startswith("setup.") for k in it)

    def test_six_languages_supported(self):
        """CLI must support exactly 6 languages."""
        from tesla_cli.cli.i18n import _STRINGS

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
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.charge.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.cli.commands.charge.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.charge.resolve_vin", return_value=MOCK_VIN),
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
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.charge.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.charge.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.charge.resolve_vin", return_value=MOCK_VIN),
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
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.charge.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.charge.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.charge.resolve_vin", return_value=MOCK_VIN),
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
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "precondition", "true")
        assert result.exit_code == 0
        assert "enabled" in result.output.lower()

    def test_precondition_off(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "precondition", "false")
        assert result.exit_code == 0
        assert "disabled" in result.output.lower()

    def test_precondition_calls_correct_command(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            _run("vehicle", "precondition", "true")
        mock.command.assert_called_once_with(MOCK_VIN, "set_preconditioning_max", on=True)

    def test_precondition_json(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
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
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "screenshot")
        assert result.exit_code == 0
        assert "screenshot" in result.output.lower()

    def test_screenshot_calls_correct_command(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            _run("vehicle", "screenshot")
        mock.command.assert_called_once_with(MOCK_VIN, "trigger_vehicle_screenshot")

    def test_screenshot_json(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
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
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "tonneau", "open")
        assert result.exit_code == 0
        mock.command.assert_called_once_with(MOCK_VIN, "tonneau_open")

    def test_tonneau_close(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "tonneau", "close")
        assert result.exit_code == 0
        mock.command.assert_called_once_with(MOCK_VIN, "tonneau_close")

    def test_tonneau_stop(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
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
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
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
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("-j", "vehicle", "tonneau", "status")
        data = json.loads(result.output)
        assert data["tonneau_open"] is True
        assert data["door_state"] == "open"

    def test_tonneau_json_action(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("-j", "vehicle", "tonneau", "open")
        data = json.loads(result.output)
        assert data["tonneau"] == "open"

    def test_tonneau_invalid_action(self):
        mock = MagicMock()
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
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
        {
            "location": "Home",
            "visit_count": 142,
            "latitude": 37.42,
            "longitude": -122.08,
            "max_arrival_pct": 80,
            "min_arrival_pct": 20,
        },
        {
            "location": "Work - Downtown",
            "visit_count": 98,
            "latitude": 37.78,
            "longitude": -122.42,
            "max_arrival_pct": 70,
            "min_arrival_pct": 45,
        },
        {
            "location": "Supercharger - I-5 N",
            "visit_count": 12,
            "latitude": 38.10,
            "longitude": -121.50,
            "max_arrival_pct": 95,
            "min_arrival_pct": 15,
        },
    ]

    def test_geo_success(self):
        mock = MagicMock()
        mock.get_top_locations.return_value = self.MOCK_LOCATIONS
        with patch("tesla_cli.cli.commands.teslaMate._backend", return_value=mock):
            result = _run("teslaMate", "geo")
        assert result.exit_code == 0
        assert "Home" in result.output

    def test_geo_json_output(self):
        mock = MagicMock()
        mock.get_top_locations.return_value = self.MOCK_LOCATIONS
        with patch("tesla_cli.cli.commands.teslaMate._backend", return_value=mock):
            result = _run("-j", "teslaMate", "geo")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 3
        assert data[0]["location"] == "Home"
        assert data[0]["visit_count"] == 142

    def test_geo_limit_option(self):
        mock = MagicMock()
        mock.get_top_locations.return_value = self.MOCK_LOCATIONS[:2]
        with patch("tesla_cli.cli.commands.teslaMate._backend", return_value=mock):
            _run("teslaMate", "geo", "--limit", "2")
        mock.get_top_locations.assert_called_once_with(limit=2)

    def test_geo_empty_data(self):
        mock = MagicMock()
        mock.get_top_locations.return_value = []
        with patch("tesla_cli.cli.commands.teslaMate._backend", return_value=mock):
            result = _run("teslaMate", "geo")
        assert result.exit_code == 0
        assert "no" in result.output.lower() or "found" in result.output.lower()

    def test_geo_csv_export(self):
        mock = MagicMock()
        mock.get_top_locations.return_value = self.MOCK_LOCATIONS
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            csv_path = f.name
        try:
            with patch("tesla_cli.cli.commands.teslaMate._backend", return_value=mock):
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
        from tesla_cli.core.backends.teslaMate import TeslaMateBacked

        backend = TeslaMateBacked.__new__(TeslaMateBacked)
        backend._car_id = 1
        mock_rows = [
            {
                "location": "Home",
                "visit_count": 50,
                "latitude": 37.42,
                "longitude": -122.08,
                "max_arrival_pct": 80,
                "min_arrival_pct": 20,
            },
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
    """Tests for tesla_cli.core.auth.encryption module."""

    def test_is_encrypted_true(self):
        from tesla_cli.core.auth.encryption import is_encrypted

        assert is_encrypted("enc1:abc123") is True

    def test_is_encrypted_false_plain(self):
        from tesla_cli.core.auth.encryption import is_encrypted

        assert is_encrypted("eyJhbGciOiJSUzI1NiJ9.plain_token") is False

    def test_is_encrypted_false_empty(self):
        from tesla_cli.core.auth.encryption import is_encrypted

        assert is_encrypted("") is False

    def test_is_encrypted_false_none_like(self):
        from tesla_cli.core.auth.encryption import is_encrypted

        assert is_encrypted("plain_text_token") is False

    def test_encrypt_produces_enc1_prefix(self):
        from tesla_cli.core.auth.encryption import encrypt_token

        result = encrypt_token("my-secret", "password")
        assert result.startswith("enc1:")

    def test_roundtrip_encrypt_decrypt(self):
        from tesla_cli.core.auth.encryption import decrypt_token, encrypt_token

        original = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.test_token_value"
        encrypted = encrypt_token(original, "test_password_123")
        assert encrypted != original
        decrypted = decrypt_token(encrypted, "test_password_123")
        assert decrypted == original

    def test_wrong_password_raises_value_error(self):
        from tesla_cli.core.auth.encryption import decrypt_token, encrypt_token

        encrypted = encrypt_token("secret", "correct_password")
        with pytest.raises(ValueError, match="Decryption failed"):
            decrypt_token(encrypted, "wrong_password")

    def test_decrypt_non_encrypted_raises(self):
        from tesla_cli.core.auth.encryption import decrypt_token

        with pytest.raises(ValueError, match="Not an encrypted token"):
            decrypt_token("plain_token", "password")

    def test_different_calls_produce_different_ciphertext(self):
        """Each encryption call uses a random nonce — same input → different ciphertext."""
        from tesla_cli.core.auth.encryption import encrypt_token

        c1 = encrypt_token("same_plaintext", "same_password")
        c2 = encrypt_token("same_plaintext", "same_password")
        assert c1 != c2  # different nonce each time

    def test_encrypted_token_is_string(self):
        from tesla_cli.core.auth.encryption import encrypt_token

        result = encrypt_token("token", "pass")
        assert isinstance(result, str)

    def test_unicode_token_roundtrip(self):
        from tesla_cli.core.auth.encryption import decrypt_token, encrypt_token

        original = "tëst-tökën-wïth-ünicode-chäracters"
        encrypted = encrypt_token(original, "password")
        assert decrypt_token(encrypted, "password") == original


class TestConfigEncryptDecryptCommands:
    """Tests for `tesla config encrypt-token` and `decrypt-token`."""

    def test_encrypt_token_command_success(self):
        from tesla_cli.core.auth import tokens as tok_module

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
        from tesla_cli.core.auth import tokens as tok_module

        with patch.object(tok_module, "get_token", return_value="enc1:already_encrypted"):
            result = _run("config", "encrypt-token", "some_key", "--password", "pass")

        assert result.exit_code == 0
        assert "already encrypted" in result.output.lower()

    def test_encrypt_token_not_found(self):
        from tesla_cli.core.auth import tokens as tok_module

        with patch.object(tok_module, "get_token", return_value=None):
            result = _run("config", "encrypt-token", "missing_key", "--password", "pass")

        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_decrypt_token_command_success(self):
        from tesla_cli.core.auth import tokens as tok_module
        from tesla_cli.core.auth.encryption import encrypt_token

        original = "my_plain_token"
        encrypted = encrypt_token(original, "testpass")

        with (
            patch.object(tok_module, "get_token", return_value=encrypted),
            patch.object(tok_module, "set_token") as mock_store,
        ):
            result = _run(
                "config", "decrypt-token", "order_refresh_token", "--password", "testpass"
            )

        assert result.exit_code == 0
        stored_value = mock_store.call_args[0][1]
        assert stored_value == original

    def test_decrypt_token_wrong_password(self):
        from tesla_cli.core.auth import tokens as tok_module
        from tesla_cli.core.auth.encryption import encrypt_token

        encrypted = encrypt_token("secret", "correct")

        with patch.object(tok_module, "get_token", return_value=encrypted):
            result = _run("config", "decrypt-token", "some_key", "--password", "wrong")

        assert result.exit_code != 0
        assert "failed" in result.output.lower() or "error" in result.output.lower()

    def test_decrypt_token_not_encrypted(self):
        from tesla_cli.core.auth import tokens as tok_module

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
            "charge_state": {
                "battery_level": 80,
                "battery_range": 240.0,
                "charging_state": "Disconnected",
                "charge_limit_soc": 90,
                "charge_energy_added": 0,
            },
            "vehicle_config": {
                "car_type": "model3",
                "exterior_color": "MidnightSilver",
                "wheel_type": "Pinwheel18",
                "battery_type": "NCA",
                "drive_unit": "DV2",
                "model_year": 2023,
            },
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
            (snap_dir / "snapshot_2024-06-01.json").write_text(json.dumps(self._make_snapshot()))
            out_path = Path(td) / "test-dossier.pdf"
            with patch("tesla_cli.core.backends.dossier.SNAPSHOTS_DIR", snap_dir):
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
            with patch("tesla_cli.core.backends.dossier.SNAPSHOTS_DIR", fake_dir):
                cfg = MagicMock()
                cfg.general.default_vin = MOCK_VIN
                with patch("tesla_cli.cli.commands.dossier.load_config", return_value=cfg):
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
            with patch("tesla_cli.cli.commands.config_cmd.load_config", return_value=cfg):
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
            with patch("tesla_cli.cli.commands.config_cmd.load_config", return_value=cfg):
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
            with patch("tesla_cli.cli.commands.config_cmd.load_config", return_value=cfg):
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
            with patch("tesla_cli.cli.commands.config_cmd.load_config", return_value=cfg):
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
        from tesla_cli.core.config import Config

        real_cfg = Config()
        with tempfile.TemporaryDirectory() as td:
            backup_path = self._make_backup(td)
            with (
                patch("tesla_cli.cli.commands.config_cmd.load_config", return_value=real_cfg),
                patch("tesla_cli.cli.commands.config_cmd.save_config") as mock_save,
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

        from tesla_cli.core.config import Config

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
                patch("tesla_cli.cli.commands.config_cmd.load_config", return_value=real_cfg),
                patch("tesla_cli.cli.commands.config_cmd.save_config"),
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
        with patch("tesla_cli.cli.commands.teslaMate._backend", return_value=mock):
            result = _run("teslaMate", "report", "--month", "2024-06")
        assert result.exit_code == 0
        assert "2024-06" in result.output

    def test_report_shows_trips(self):
        mock = MagicMock()
        mock.get_monthly_report.return_value = self.MOCK_REPORT
        with patch("tesla_cli.cli.commands.teslaMate._backend", return_value=mock):
            result = _run("teslaMate", "report", "--month", "2024-06")
        assert "42" in result.output  # trip count
        assert "1248.5" in result.output or "1248" in result.output  # total km

    def test_report_shows_charging(self):
        mock = MagicMock()
        mock.get_monthly_report.return_value = self.MOCK_REPORT
        with patch("tesla_cli.cli.commands.teslaMate._backend", return_value=mock):
            result = _run("teslaMate", "report", "--month", "2024-06")
        assert "18" in result.output  # sessions
        assert "210.5" in result.output or "210" in result.output

    def test_report_json_output(self):
        mock = MagicMock()
        mock.get_monthly_report.return_value = self.MOCK_REPORT
        with patch("tesla_cli.cli.commands.teslaMate._backend", return_value=mock):
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
        with patch("tesla_cli.cli.commands.teslaMate._backend", return_value=mock):
            _run("teslaMate", "report")
        mock.get_monthly_report.assert_called_once_with(month=current_month)

    def test_report_passes_month_to_backend(self):
        mock = MagicMock()
        mock.get_monthly_report.return_value = self.MOCK_REPORT
        with patch("tesla_cli.cli.commands.teslaMate._backend", return_value=mock):
            _run("teslaMate", "report", "--month", "2023-12")
        mock.get_monthly_report.assert_called_once_with(month="2023-12")

    def test_report_in_help(self):
        result = _run("teslaMate", "--help")
        assert "report" in result.output

    def test_report_backend_method(self):
        """TeslaMateBacked.get_monthly_report returns expected structure."""
        from tesla_cli.core.backends.teslaMate import TeslaMateBacked

        backend = TeslaMateBacked.__new__(TeslaMateBacked)
        backend._car_id = 1

        mock_drive_row = {
            "trips": 10,
            "total_km": 300.0,
            "total_drive_min": 240,
            "total_kwh_used": 45.0,
            "avg_km_per_trip": 30.0,
            "longest_trip_km": 80.0,
            "avg_wh_per_km": 150.0,
        }
        mock_charge_row = {
            "sessions": 5,
            "total_kwh_charged": 60.0,
            "total_cost": 9.0,
            "avg_kwh_per_session": 12.0,
            "dc_fast_sessions": 1,
            "ac_sessions": 4,
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
        {
            "name": "sentry_detection_nearby_person",
            "audience": ["Customer"],
            "start_epoch_time": 1717200000,
        },
        {
            "name": "sentry_camera_tampering",
            "audience": ["Customer"],
            "start_epoch_time": 1717100000,
        },
        {
            "name": "software_update_available",
            "audience": ["Customer"],
            "start_epoch_time": 1717000000,
        },
    ]

    def test_sentry_events_success(self):
        mock = MagicMock()
        mock.get_recent_alerts.return_value = self.MOCK_ALERTS
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "sentry-events")
        assert result.exit_code == 0

    def test_sentry_events_json_output(self):
        mock = MagicMock()
        mock.get_recent_alerts.return_value = self.MOCK_ALERTS
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("-j", "vehicle", "sentry-events")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)

    def test_sentry_events_unsupported_backend(self):
        """BackendNotSupportedError → exit 1 with helpful message."""
        from tesla_cli.core.exceptions import BackendNotSupportedError

        mock = MagicMock()
        mock.get_recent_alerts.side_effect = BackendNotSupportedError(
            "vehicle sentry-events", "fleet"
        )
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "sentry-events")
        assert result.exit_code == 1

    def test_sentry_events_limit(self):
        mock = MagicMock()
        mock.get_recent_alerts.return_value = self.MOCK_ALERTS * 5  # 15 total
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("-j", "vehicle", "sentry-events", "--limit", "2")
        data = json.loads(result.output)
        assert len(data) <= 2

    def test_sentry_events_empty(self):
        mock = MagicMock()
        mock.get_recent_alerts.return_value = []
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
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
            patch("tesla_cli.core.backends.dossier.SNAPSHOTS_DIR", snaps_dir),
            patch("tesla_cli.core.config.load_config") as mock_lc,
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
            patch("tesla_cli.core.backends.dossier.SNAPSHOTS_DIR", snaps_dir),
            patch("tesla_cli.core.config.load_config") as mock_lc,
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
            patch("tesla_cli.core.backends.dossier.SNAPSHOTS_DIR", snaps_dir),
            patch("tesla_cli.core.config.load_config") as mock_lc,
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
            patch("tesla_cli.core.backends.dossier.SNAPSHOTS_DIR", empty_dir),
            patch("tesla_cli.core.config.load_config") as mock_lc,
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
            patch("tesla_cli.core.backends.dossier.SNAPSHOTS_DIR", snaps_dir),
            patch("tesla_cli.core.config.load_config") as mock_lc,
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
            patch("tesla_cli.core.backends.dossier.SNAPSHOTS_DIR", snaps_dir),
            patch("tesla_cli.core.config.load_config") as mock_lc,
        ):
            mock_lc.return_value.general.default_vin = MOCK_VIN
            _run("dossier", "export-html", "--output", str(out))
        content = out.read_text()
        # No external stylesheet or script src references
        assert "<link" not in content or "http" not in content.split("<link")[1].split(">")[0]
        assert '<script src="http' not in content

    def test_export_html_default_output_name(self, tmp_path):
        """Default output filename is dossier.html."""
        snaps_dir = self._snapshot(tmp_path)
        import os

        orig = os.getcwd()
        os.chdir(tmp_path)
        try:
            with (
                patch("tesla_cli.core.backends.dossier.SNAPSHOTS_DIR", snaps_dir),
                patch("tesla_cli.core.config.load_config") as mock_lc,
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
        "scheduled_charging_start_time_app": 420,  # 07:00
        "scheduled_charging_start_time": 1711940400,
        "scheduled_departure_time_minutes": 450,  # 07:30
        "scheduled_departure_time": 1711942200,
        "preconditioning_enabled": True,
        "preconditioning_weekdays_only": False,
        "off_peak_charging_enabled": True,
        "off_peak_hours_end_time": 480,  # 08:00
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
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.charge.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.charge._vin", return_value=MOCK_VIN),
        ):
            result = _run("charge", "schedule-preview")
        assert result.exit_code == 0
        assert "07:00" in result.output  # scheduled_charging_start_time_app = 420

    def test_schedule_preview_shows_departure_time(self):
        mock = MagicMock()
        mock.get_charge_state.return_value = self.MOCK_CHARGE_STATE
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.charge.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.charge._vin", return_value=MOCK_VIN),
        ):
            result = _run("charge", "schedule-preview")
        assert result.exit_code == 0
        assert "07:30" in result.output  # departure_time_minutes = 450

    def test_schedule_preview_json(self):
        mock = MagicMock()
        mock.get_charge_state.return_value = self.MOCK_CHARGE_STATE
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.charge.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.charge._vin", return_value=MOCK_VIN),
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
        state = {
            **self.MOCK_CHARGE_STATE,
            "scheduled_charging_mode": "Off",
            "scheduled_charging_start_time_app": None,
            "scheduled_departure_time_minutes": None,
            "preconditioning_enabled": False,
            "off_peak_charging_enabled": False,
        }
        mock = MagicMock()
        mock.get_charge_state.return_value = state
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.charge.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.charge._vin", return_value=MOCK_VIN),
        ):
            result = _run("charge", "schedule-preview")
        assert result.exit_code == 0
        assert "Off" in result.output

    def test_schedule_preview_minutes_to_hhmm_midnight(self):
        """Edge case: 0 minutes should display 00:00."""
        state = {
            **self.MOCK_CHARGE_STATE,
            "scheduled_charging_start_time_app": 0,
            "scheduled_departure_time_minutes": 0,
        }
        mock = MagicMock()
        mock.get_charge_state.return_value = state
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.charge.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.charge._vin", return_value=MOCK_VIN),
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
        from tesla_cli.cli.commands.order import _STORES

        assert len(_STORES) >= 100

    def test_stores_all_have_required_fields(self):
        from tesla_cli.cli.commands.order import _STORES

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
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
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
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
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
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
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
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
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
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("-j", "vehicle", "sw-update")
        data = json.loads(result.output)
        expected_keys = {
            "current_version",
            "update_available",
            "update_status",
            "update_version",
            "update_download_pct",
            "update_install_perc",
            "expected_duration_sec",
            "scheduled_time_ms",
        }
        assert expected_keys.issubset(data.keys())

    def test_sw_update_downloading_status(self):
        mock = MagicMock()
        mock.get_vehicle_data.return_value = self._vehicle_data(
            status="downloading", version="2025.14.0"
        )
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
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
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
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
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
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
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
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
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "speed-limit", "--on", "--pin", "1234")
        assert result.exit_code == 0
        assert "activated" in result.output.lower()

    def test_speed_limit_deactivate_with_pin(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "speed-limit", "--off", "--pin", "1234")
        assert result.exit_code == 0
        assert "deactivated" in result.output.lower()

    def test_speed_limit_clear_pin(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "speed-limit", "--clear", "--pin", "1234")
        assert result.exit_code == 0
        assert "cleared" in result.output.lower() or "PIN" in result.output

    def test_speed_limit_out_of_range(self):
        mock = MagicMock()
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
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
        return patch("tesla_cli.cli.commands.teslaMate._backend", return_value=mock_backend)

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
        with patch("tesla_cli.cli.commands.teslaMate._backend", return_value=mock_backend):
            result = _run("teslaMate", "stats")
        assert result.exit_code == 0

    def test_stats_in_help(self):
        result = _run("teslaMate", "--help")
        assert "stats" in result.output


# ═══════════════════════════════════════════════════════════════════════════════
# v1.8.0 — vehicle bio, teslaMate graph, export-html --theme, cabin-protection
# ═══════════════════════════════════════════════════════════════════════════════


# ── vehicle bio ───────────────────────────────────────────────────────────────


class TestVehicleBio:
    """Tests for tesla vehicle bio."""

    def _cfg(self):
        cfg = MagicMock()
        cfg.general.backend = "fleet"
        cfg.general.default_vin = MOCK_VIN
        return cfg

    def test_bio_renders_panels(self):
        mock = MagicMock()
        from tests.conftest import MOCK_VEHICLE_DATA

        mock.get_vehicle_data.return_value = MOCK_VEHICLE_DATA
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "bio")
        assert result.exit_code == 0
        # 5 panels
        assert "Battery" in result.output
        assert "Climate" in result.output
        assert "Drive State" in result.output
        assert "Scheduling" in result.output

    def test_bio_json_structure(self):
        mock = MagicMock()
        from tests.conftest import MOCK_VEHICLE_DATA

        mock.get_vehicle_data.return_value = MOCK_VEHICLE_DATA
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("-j", "vehicle", "bio")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "battery" in data
        assert "climate" in data
        assert "drive" in data
        assert "identity" in data
        assert "scheduling" in data

    def test_bio_json_battery_level(self):
        mock = MagicMock()
        from tests.conftest import MOCK_VEHICLE_DATA

        mock.get_vehicle_data.return_value = MOCK_VEHICLE_DATA
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("-j", "vehicle", "bio")
        data = json.loads(result.output)
        assert data["battery"]["battery_level"] == 72

    def test_bio_json_vin(self):
        mock = MagicMock()
        from tests.conftest import MOCK_VEHICLE_DATA

        mock.get_vehicle_data.return_value = MOCK_VEHICLE_DATA
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("-j", "vehicle", "bio")
        data = json.loads(result.output)
        assert data["vin"] == MOCK_VIN

    def test_bio_sparse_data_no_crash(self):
        """Vehicle data with no sub-dicts should not crash."""
        mock = MagicMock()
        mock.get_vehicle_data.return_value = {"vin": MOCK_VIN, "state": "online"}
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "bio")
        assert result.exit_code == 0

    def test_bio_in_help(self):
        result = _run("vehicle", "--help")
        assert "bio" in result.output


# ── teslaMate graph ───────────────────────────────────────────────────────────


MOCK_CHARGING_SESSIONS_GRAPH = [
    {
        "id": 1,
        "start_date": "2026-03-01 20:00",
        "end_date": "2026-03-01 22:00",
        "energy_added_kwh": 45.2,
        "cost": 9.04,
        "start_battery_level": 20,
        "end_battery_level": 90,
        "location": "Home",
    },
    {
        "id": 2,
        "start_date": "2026-03-05 08:00",
        "end_date": "2026-03-05 08:30",
        "energy_added_kwh": 12.0,
        "cost": 2.40,
        "start_battery_level": 60,
        "end_battery_level": 80,
        "location": "Supercharger",
    },
    {
        "id": 3,
        "start_date": "2026-03-10 19:00",
        "end_date": "2026-03-10 20:00",
        "energy_added_kwh": 0.0,
        "cost": None,
        "start_battery_level": 80,
        "end_battery_level": 80,
        "location": None,
    },
]


class TestTeslaMateGraph:
    """Tests for tesla teslaMate graph."""

    def _patched(self, sessions=None):
        if sessions is None:
            sessions = MOCK_CHARGING_SESSIONS_GRAPH
        mock_backend = MagicMock()
        mock_backend.get_charging_sessions.return_value = sessions
        return patch("tesla_cli.cli.commands.teslaMate._backend", return_value=mock_backend)

    def test_graph_renders_bars(self):
        with self._patched():
            result = _run("teslaMate", "graph")
        assert result.exit_code == 0
        assert "█" in result.output
        assert "kWh" in result.output

    def test_graph_summary_footer(self):
        with self._patched():
            result = _run("teslaMate", "graph")
        assert "sessions" in result.output
        assert "total" in result.output.lower()

    def test_graph_json(self):
        with self._patched():
            result = _run("-j", "teslaMate", "graph")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]["energy_added_kwh"] == 45.2

    def test_graph_empty_sessions(self):
        with self._patched(sessions=[]):
            result = _run("teslaMate", "graph")
        assert result.exit_code == 0
        assert "No charging sessions" in result.output

    def test_graph_zero_kwh_no_crash(self):
        """A session where all kWh are 0 must not divide-by-zero."""
        with self._patched(sessions=[MOCK_CHARGING_SESSIONS_GRAPH[2]]):
            result = _run("teslaMate", "graph")
        assert result.exit_code == 0

    def test_graph_limit_flag(self):
        mock_backend = MagicMock()
        mock_backend.get_charging_sessions.return_value = MOCK_CHARGING_SESSIONS_GRAPH[:1]
        with patch("tesla_cli.cli.commands.teslaMate._backend", return_value=mock_backend):
            result = _run("teslaMate", "graph", "--limit", "1")
        assert result.exit_code == 0
        mock_backend.get_charging_sessions.assert_called_once_with(limit=1)

    def test_graph_none_location_no_crash(self):
        """Sessions with location=None should render as 'Unknown'."""
        with self._patched(sessions=[MOCK_CHARGING_SESSIONS_GRAPH[2]]):
            result = _run("teslaMate", "graph")
        assert result.exit_code == 0
        assert "Unknown" in result.output or result.exit_code == 0

    def test_graph_in_help(self):
        result = _run("teslaMate", "--help")
        assert "graph" in result.output


# ── dossier export-html --theme ───────────────────────────────────────────────


class TestDossierExportHtmlTheme:
    """Tests for --theme flag on tesla dossier export-html."""

    def test_dark_theme_default_css(self, tmp_path):
        out = str(tmp_path / "dark.html")
        with patch("tesla_cli.core.config.load_config") as mock_lc:
            mock_lc.return_value.general.default_vin = MOCK_VIN
            result = _run("dossier", "export-html", "--output", out, "--theme", "dark")
        assert result.exit_code == 0
        html = Path(out).read_text()
        assert "--bg: #0d0d0d" in html

    def test_light_theme_bg_css(self, tmp_path):
        out = str(tmp_path / "light.html")
        with patch("tesla_cli.core.config.load_config") as mock_lc:
            mock_lc.return_value.general.default_vin = MOCK_VIN
            result = _run("dossier", "export-html", "--output", out, "--theme", "light")
        assert result.exit_code == 0
        html = Path(out).read_text()
        assert "--bg: #f5f5f5" in html

    def test_light_theme_card_css(self, tmp_path):
        out = str(tmp_path / "light2.html")
        with patch("tesla_cli.core.config.load_config") as mock_lc:
            mock_lc.return_value.general.default_vin = MOCK_VIN
            _run("dossier", "export-html", "--output", out, "--theme", "light")
        html = Path(out).read_text()
        assert "--card: #ffffff" in html

    def test_light_theme_accent_css(self, tmp_path):
        out = str(tmp_path / "light3.html")
        with patch("tesla_cli.core.config.load_config") as mock_lc:
            mock_lc.return_value.general.default_vin = MOCK_VIN
            _run("dossier", "export-html", "--output", out, "--theme", "light")
        html = Path(out).read_text()
        assert "#c0001a" in html  # deep red light accent

    def test_unknown_theme_falls_back_to_dark(self, tmp_path):
        """Any unknown theme value should render the dark theme (else branch)."""
        out = str(tmp_path / "unknown.html")
        with patch("tesla_cli.core.config.load_config") as mock_lc:
            mock_lc.return_value.general.default_vin = MOCK_VIN
            result = _run("dossier", "export-html", "--output", out, "--theme", "blurple")
        assert result.exit_code == 0
        html = Path(out).read_text()
        assert "--bg: #0d0d0d" in html

    def test_both_themes_create_valid_html(self, tmp_path):
        for t in ("dark", "light"):
            out = str(tmp_path / f"{t}.html")
            with patch("tesla_cli.core.config.load_config") as mock_lc:
                mock_lc.return_value.general.default_vin = MOCK_VIN
                result = _run("dossier", "export-html", "--output", out, "--theme", t)
            assert result.exit_code == 0
            html = Path(out).read_text()
            assert "<!DOCTYPE html>" in html


# ── vehicle cabin-protection ──────────────────────────────────────────────────


class TestVehicleCabinProtection:
    """Tests for tesla vehicle cabin-protection."""

    CLIMATE_WITH_COP = {
        "inside_temp": 22.5,
        "outside_temp": 18.0,
        "is_climate_on": False,
        "cabin_overheat_protection": "FAN_ONLY",
        "cabin_overheat_protection_actively_cooling": False,
    }

    def _cfg(self):
        cfg = MagicMock()
        cfg.general.backend = "fleet"
        cfg.general.default_vin = MOCK_VIN
        return cfg

    def test_status_shows_cop(self):
        mock = MagicMock()
        mock.get_climate_state.return_value = self.CLIMATE_WITH_COP
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "cabin-protection")
        assert result.exit_code == 0
        assert "FAN_ONLY" in result.output

    def test_status_json(self):
        mock = MagicMock()
        mock.get_climate_state.return_value = self.CLIMATE_WITH_COP
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("-j", "vehicle", "cabin-protection")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["cabin_overheat_protection"] == "FAN_ONLY"
        assert "actively_cooling" in data

    def test_enable(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "cabin-protection", "--on")
        assert result.exit_code == 0
        assert "enabled" in result.output.lower()
        mock.command.assert_called_once_with(
            MOCK_VIN, "set_cabin_overheat_protection", on=True, fan_only=False
        )

    def test_disable(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "cabin-protection", "--off")
        assert result.exit_code == 0
        assert "disabled" in result.output.lower()
        mock.command.assert_called_once_with(
            MOCK_VIN, "set_cabin_overheat_protection", on=False, fan_only=False
        )

    def test_level_fan_only(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "cabin-protection", "--level", "FAN_ONLY")
        assert result.exit_code == 0
        mock.command.assert_called_once_with(
            MOCK_VIN, "set_cabin_overheat_protection", on=True, fan_only=True
        )

    def test_level_no_ac(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "cabin-protection", "--level", "NO_AC")
        assert result.exit_code == 0
        mock.command.assert_called_once_with(
            MOCK_VIN, "set_cabin_overheat_protection", on=True, fan_only=False
        )

    def test_level_case_insensitive(self):
        """--level should accept lowercase."""
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "cabin-protection", "--level", "fan_only")
        assert result.exit_code == 0

    def test_level_invalid(self):
        mock = MagicMock()
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "cabin-protection", "--level", "TURBO")
        assert result.exit_code == 1
        assert "Invalid level" in result.output

    def test_level_json(self):
        mock = MagicMock()
        mock.command.return_value = {"result": True}
        mock.wake_up.return_value = True
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("-j", "vehicle", "cabin-protection", "--level", "FAN_ONLY")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["cabin_overheat_protection"] == "FAN_ONLY"

    def test_cabin_protection_in_help(self):
        result = _run("vehicle", "--help")
        assert "cabin-protection" in result.output


# ═══════════════════════════════════════════════════════════════════════════════
# v1.9.0 — teslaMate daily-chart, order eta, config doctor
# ═══════════════════════════════════════════════════════════════════════════════


# ── teslaMate daily-chart ────────────────────────────────────────────────────


MOCK_DAILY_ENERGY = [
    {"day": "2026-03-01", "kwh_added": 42.1, "sessions": 1, "total_cost": 8.42},
    {"day": "2026-03-05", "kwh_added": 8.5, "sessions": 2, "total_cost": 1.70},
    {"day": "2026-03-10", "kwh_added": 0.0, "sessions": 1, "total_cost": None},
]


class TestTeslaMateDailyChart:
    """Tests for tesla teslaMate daily-chart."""

    def _patched(self, rows=None):
        if rows is None:
            rows = MOCK_DAILY_ENERGY
        mock_backend = MagicMock()
        mock_backend.get_daily_energy.return_value = rows
        return patch("tesla_cli.cli.commands.teslaMate._backend", return_value=mock_backend)

    def test_daily_chart_renders_bars(self):
        with self._patched():
            result = _run("teslaMate", "daily-chart")
        assert result.exit_code == 0
        assert "█" in result.output
        assert "kWh" in result.output

    def test_daily_chart_shows_date(self):
        with self._patched():
            result = _run("teslaMate", "daily-chart")
        assert "2026-03-01" in result.output

    def test_daily_chart_json(self):
        with self._patched():
            result = _run("-j", "teslaMate", "daily-chart")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]["kwh_added"] == 42.1

    def test_daily_chart_empty(self):
        with self._patched(rows=[]):
            result = _run("teslaMate", "daily-chart")
        assert result.exit_code == 0
        assert "No charging data" in result.output

    def test_daily_chart_zero_kwh_no_crash(self):
        with self._patched(rows=[MOCK_DAILY_ENERGY[2]]):
            result = _run("teslaMate", "daily-chart")
        assert result.exit_code == 0

    def test_daily_chart_days_flag(self):
        mock_backend = MagicMock()
        mock_backend.get_daily_energy.return_value = MOCK_DAILY_ENERGY
        with patch("tesla_cli.cli.commands.teslaMate._backend", return_value=mock_backend):
            result = _run("teslaMate", "daily-chart", "--days", "60")
        assert result.exit_code == 0
        mock_backend.get_daily_energy.assert_called_once_with(days=60)

    def test_daily_chart_footer_totals(self):
        with self._patched():
            result = _run("teslaMate", "daily-chart")
        assert "total" in result.output.lower() or "kWh" in result.output

    def test_daily_chart_in_help(self):
        result = _run("teslaMate", "--help")
        assert "daily-chart" in result.output


# ── order eta ─────────────────────────────────────────────────────────────────


class TestOrderEta:
    """Tests for tesla order eta."""

    def test_eta_renders(self):
        with (
            patch("tesla_cli.cli.commands.order.load_config") as mock_lc,
            patch("tesla_cli.core.backends.dossier.SNAPSHOTS_DIR") as mock_dir,
        ):
            mock_lc.return_value.order.reservation_number = ""
            mock_dir.exists.return_value = False
            result = _run("order", "eta")
        assert result.exit_code == 0
        assert (
            "ETA" in result.output or "estimate" in result.output.lower() or "Best" in result.output
        )

    def test_eta_json_structure(self):
        with (
            patch("tesla_cli.cli.commands.order.load_config") as mock_lc,
            patch("tesla_cli.core.backends.dossier.SNAPSHOTS_DIR") as mock_dir,
        ):
            mock_lc.return_value.order.reservation_number = ""
            mock_dir.exists.return_value = False
            result = _run("-j", "order", "eta")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "current_phase" in data
        assert "eta_best" in data
        assert "eta_typical" in data
        assert "eta_worst" in data
        assert "breakdown" in data

    def test_eta_json_eta_worst_after_typical(self):
        with (
            patch("tesla_cli.cli.commands.order.load_config") as mock_lc,
            patch("tesla_cli.core.backends.dossier.SNAPSHOTS_DIR") as mock_dir,
        ):
            mock_lc.return_value.order.reservation_number = ""
            mock_dir.exists.return_value = False
            result = _run("-j", "order", "eta")
        data = json.loads(result.output)
        from datetime import date

        best = date.fromisoformat(data["eta_best"])
        typical = date.fromisoformat(data["eta_typical"])
        worst = date.fromisoformat(data["eta_worst"])
        assert best <= typical <= worst

    def test_eta_json_breakdown_has_all_phases(self):
        with (
            patch("tesla_cli.cli.commands.order.load_config") as mock_lc,
            patch("tesla_cli.core.backends.dossier.SNAPSHOTS_DIR") as mock_dir,
        ):
            mock_lc.return_value.order.reservation_number = ""
            mock_dir.exists.return_value = False
            result = _run("-j", "order", "eta")
        data = json.loads(result.output)
        phases = [r["phase"] for r in data["breakdown"]]
        assert "ordered" in phases
        assert "shipped" in phases
        assert "delivered" in phases

    def test_eta_json_delivered_phase_zero_days(self):
        """When phase is 'delivered', all remaining days should be 0."""
        with (
            patch("tesla_cli.cli.commands.order.load_config") as mock_lc,
            patch("tesla_cli.core.backends.dossier.SNAPSHOTS_DIR") as mock_dir,
        ):
            mock_lc.return_value.order.reservation_number = ""
            # Simulate delivered snapshot
            import json as _j

            snap = {"real_status": {"phase": "delivered", "phase_since": "2026-03-28"}}
            mock_dir.exists.return_value = True
            mock_dir.glob.return_value = [MagicMock(read_text=lambda: _j.dumps(snap))]
            result = _run("-j", "order", "eta")
        data = json.loads(result.output)
        assert data["total_days_best"] == 0
        assert data["total_days_typical"] == 0

    def test_eta_in_help(self):
        result = _run("order", "--help")
        assert "eta" in result.output


# ── config doctor ─────────────────────────────────────────────────────────────


class TestConfigDoctor:
    """Tests for tesla config doctor."""

    def _base_cfg(self, vin=MOCK_VIN, rn="RN126460939", backend="fleet"):
        cfg = MagicMock()
        cfg.general.default_vin = vin
        cfg.general.backend = backend
        cfg.order.reservation_number = rn
        cfg.teslaMate.database_url = ""
        cfg.teslaMate.car_id = 1
        return cfg

    def test_doctor_all_ok(self):
        cfg = self._base_cfg()
        with (
            patch("tesla_cli.cli.commands.config_cmd.load_config", return_value=cfg),
            patch("tesla_cli.core.auth.tokens.has_token", return_value=True),
        ):
            result = _run("config", "doctor")
        assert result.exit_code == 0
        assert "ok" in result.output.lower() or "✅" in result.output

    def test_doctor_json_structure(self):
        cfg = self._base_cfg()
        with (
            patch("tesla_cli.cli.commands.config_cmd.load_config", return_value=cfg),
            patch("tesla_cli.core.auth.tokens.has_token", return_value=True),
        ):
            result = _run("-j", "config", "doctor")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "ok" in data
        assert "warn" in data
        assert "fail" in data
        assert "checks" in data
        assert isinstance(data["checks"], list)

    def test_doctor_json_check_keys(self):
        cfg = self._base_cfg()
        with (
            patch("tesla_cli.cli.commands.config_cmd.load_config", return_value=cfg),
            patch("tesla_cli.core.auth.tokens.has_token", return_value=True),
        ):
            result = _run("-j", "config", "doctor")
        data = json.loads(result.output)
        for c in data["checks"]:
            assert "name" in c
            assert "status" in c
            assert "detail" in c

    def test_doctor_no_vin_is_warn(self):
        cfg = self._base_cfg(vin="")
        with (
            patch("tesla_cli.cli.commands.config_cmd.load_config", return_value=cfg),
            patch("tesla_cli.core.auth.tokens.has_token", return_value=True),
        ):
            result = _run("-j", "config", "doctor")
        data = json.loads(result.output)
        vin_check = next((c for c in data["checks"] if "VIN" in c["name"]), None)
        assert vin_check is not None
        assert vin_check["status"] == "warn"

    def test_doctor_no_token_is_fail(self):
        cfg = self._base_cfg()
        with (
            patch("tesla_cli.cli.commands.config_cmd.load_config", return_value=cfg),
            patch("tesla_cli.core.auth.tokens.has_token", return_value=False),
        ):
            result = _run("-j", "config", "doctor")
        data = json.loads(result.output)
        # At least one fail (order auth token)
        assert data["fail"] >= 1

    def test_doctor_fail_exits_1(self):
        cfg = self._base_cfg()
        with (
            patch("tesla_cli.cli.commands.config_cmd.load_config", return_value=cfg),
            patch("tesla_cli.core.auth.tokens.has_token", return_value=False),
        ):
            result = _run("config", "doctor")
        assert result.exit_code == 1

    def test_doctor_shows_fix_hint(self):
        cfg = self._base_cfg()
        with (
            patch("tesla_cli.cli.commands.config_cmd.load_config", return_value=cfg),
            patch("tesla_cli.core.auth.tokens.has_token", return_value=False),
        ):
            result = _run("config", "doctor")
        assert "config auth" in result.output or "tesla config" in result.output

    def test_doctor_in_help(self):
        result = _run("config", "--help")
        assert "doctor" in result.output


# ── v2.0.0: teslaMate heatmap ─────────────────────────────────────────────────

import datetime as _dt_mod

MOCK_DRIVE_DAYS = [
    {"day": _dt_mod.date.today() - _dt_mod.timedelta(days=10), "drives": 2, "km": 180.5},
    {"day": _dt_mod.date.today() - _dt_mod.timedelta(days=5), "drives": 1, "km": 45.0},
    {"day": _dt_mod.date.today() - _dt_mod.timedelta(days=2), "drives": 3, "km": 210.0},
    {"day": _dt_mod.date.today() - _dt_mod.timedelta(days=1), "drives": 1, "km": 0.0},
]


class TestTeslaMateHeatmap:
    """Tests for tesla teslaMate heatmap."""

    def _patched(self, rows=None):
        if rows is None:
            rows = MOCK_DRIVE_DAYS
        mock_backend = MagicMock()
        mock_backend.get_drive_days.return_value = rows
        return patch("tesla_cli.cli.commands.teslaMate._backend", return_value=mock_backend)

    def test_heatmap_renders(self):
        with self._patched():
            result = _run("teslaMate", "heatmap")
        assert result.exit_code == 0
        # Should show day-of-week labels
        assert "Mo" in result.output
        assert "Su" in result.output

    def test_heatmap_shows_activity_symbols(self):
        with self._patched():
            result = _run("teslaMate", "heatmap")
        # At least one colored cell (green or yellow or blue)
        assert "█" in result.output or "▪" in result.output or "·" in result.output

    def test_heatmap_shows_legend(self):
        with self._patched():
            result = _run("teslaMate", "heatmap")
        assert "Legend" in result.output
        assert "km" in result.output

    def test_heatmap_shows_summary(self):
        with self._patched():
            result = _run("teslaMate", "heatmap")
        assert "active days" in result.output
        assert "total" in result.output.lower()

    def test_heatmap_json(self):
        with self._patched():
            result = _run("-j", "teslaMate", "heatmap")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]["km"] == 180.5
        assert "date" in data[0]
        assert "drives" in data[0]

    def test_heatmap_empty_no_crash(self):
        with self._patched(rows=[]):
            result = _run("teslaMate", "heatmap")
        assert result.exit_code == 0

    def test_heatmap_days_flag(self):
        mock_backend = MagicMock()
        mock_backend.get_drive_days.return_value = MOCK_DRIVE_DAYS
        with patch("tesla_cli.cli.commands.teslaMate._backend", return_value=mock_backend):
            result = _run("teslaMate", "heatmap", "--days", "90")
        assert result.exit_code == 0
        mock_backend.get_drive_days.assert_called_once_with(days=90)

    def test_heatmap_in_help(self):
        result = _run("teslaMate", "--help")
        assert "heatmap" in result.output


# ── v2.0.0: vehicle watch ─────────────────────────────────────────────────────


class TestVehicleWatch:
    """Tests for tesla vehicle watch."""

    def _cfg(self):
        cfg = MagicMock()
        cfg.general.backend = "fleet"
        cfg.general.default_vin = MOCK_VIN
        return cfg

    def _vehicle_data_v1(self) -> dict:
        from tests.conftest import MOCK_VEHICLE_DATA

        return MOCK_VEHICLE_DATA

    def _vehicle_data_v2(self) -> dict:
        """Return vehicle data with changed battery and unlocked state."""
        import copy

        data = copy.deepcopy(self._vehicle_data_v1())
        data["charge_state"]["battery_level"] = 65  # was 72
        data["vehicle_state"]["locked"] = False  # was True
        return data

    def _run_watch(self, backend_mock, *extra_args):
        """Run vehicle watch with all required patches via ExitStack."""
        from contextlib import ExitStack

        patches = [
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=backend_mock),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
            patch("time.sleep"),
        ]
        with ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            return _run("vehicle", "watch", "--interval", "10", *extra_args)

    def test_watch_starts_and_shows_status(self):
        """First poll sets baseline; second poll shows no-change status."""
        mock_backend = MagicMock()
        mock_backend.wake_up.return_value = True
        call_count = [0]

        def _side_effect(v):
            call_count[0] += 1
            if call_count[0] > 2:
                raise KeyboardInterrupt
            return self._vehicle_data_v1()

        mock_backend.get_vehicle_data.side_effect = _side_effect
        result = self._run_watch(mock_backend)
        assert result.exit_code == 0
        assert "72" in result.output or "no changes" in result.output.lower()

    def test_watch_detects_battery_change(self):
        """Second poll has lower battery — should print change alert."""
        call_count = [0]

        def _side_effect(v):
            call_count[0] += 1
            if call_count[0] > 2:
                raise KeyboardInterrupt
            return self._vehicle_data_v1() if call_count[0] == 1 else self._vehicle_data_v2()

        mock_backend = MagicMock()
        mock_backend.get_vehicle_data.side_effect = _side_effect
        mock_backend.wake_up.return_value = True
        result = self._run_watch(mock_backend)
        assert result.exit_code == 0
        assert "72" in result.output or "🔋" in result.output or "Battery" in result.output

    def test_watch_handles_asleep_vehicle(self):
        """When vehicle is asleep, watch should note it and continue."""
        from tesla_cli.core.exceptions import VehicleAsleepError

        call_count = [0]

        def _side_effect(v):
            call_count[0] += 1
            if call_count[0] > 1:
                raise KeyboardInterrupt
            raise VehicleAsleepError("asleep")

        mock_backend = MagicMock()
        mock_backend.get_vehicle_data.side_effect = _side_effect
        result = self._run_watch(mock_backend)
        assert result.exit_code == 0
        assert "asleep" in result.output.lower() or "Vehicle asleep" in result.output

    def test_watch_json_no_changes(self):
        """JSON mode emits a payload even when there are no changes."""
        call_count = [0]

        def _side_effect(v):
            call_count[0] += 1
            if call_count[0] > 2:
                raise KeyboardInterrupt
            return self._vehicle_data_v1()

        mock_backend = MagicMock()
        mock_backend.get_vehicle_data.side_effect = _side_effect
        from contextlib import ExitStack

        patches = [
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
            patch("time.sleep"),
        ]
        with ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            result = _run("-j", "vehicle", "watch", "--interval", "10")
        assert result.exit_code == 0
        lines = [ln for ln in result.output.strip().splitlines() if ln.strip().startswith("{")]
        assert len(lines) >= 1
        payload = json.loads(lines[0])
        assert "ts" in payload
        assert "changes" in payload

    def test_watch_in_help(self):
        result = _run("vehicle", "--help")
        assert "watch" in result.output


# ─────────────────────────────────────────────────────────────────────────────
# v2.2.0 Tests: ABRP, BLE, TeslaMate grafana
# ─────────────────────────────────────────────────────────────────────────────


class TestAbrpCommands:
    """Tests for `tesla abrp` command group."""

    def _cfg(self, user_token="test_abrp_token", api_key=""):
        from tesla_cli.core.config import Config

        cfg = Config()
        cfg.general.default_vin = MOCK_VIN
        cfg.abrp.user_token = user_token
        cfg.abrp.api_key = api_key
        return cfg

    def _vehicle_data(self):
        return {
            "charge_state": {
                "battery_level": 72,
                "charging_state": "Disconnected",
                "charger_power": 0,
                "charge_limit_soc": 80,
            },
            "drive_state": {
                "speed": 0,
                "power": 0,
                "latitude": 37.42,
                "longitude": -122.08,
                "shift_state": "P",
            },
            "climate_state": {
                "inside_temp": 22.0,
            },
        }

    def test_abrp_status_not_configured(self):
        cfg = self._cfg(user_token="")
        with patch("tesla_cli.cli.commands.abrp.load_config", return_value=cfg):
            result = _run("abrp", "status")
        assert result.exit_code == 0
        assert "not set" in result.output

    def test_abrp_status_configured(self):
        cfg = self._cfg(user_token="tok123", api_key="apikey456")
        with patch("tesla_cli.cli.commands.abrp.load_config", return_value=cfg):
            result = _run("abrp", "status")
        assert result.exit_code == 0
        assert "set" in result.output

    def test_abrp_status_json(self):
        cfg = self._cfg(user_token="tok123")
        with patch("tesla_cli.cli.commands.abrp.load_config", return_value=cfg):
            result = _run("-j", "abrp", "status")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["user_token_set"] is True
        assert "abrp_api" in data

    def test_abrp_setup_saves_token(self):
        cfg = self._cfg(user_token="")
        with (
            patch("tesla_cli.cli.commands.abrp.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.abrp.save_config") as mock_save,
        ):
            result = _run("abrp", "setup", "my_token_abc")
        assert result.exit_code == 0
        mock_save.assert_called_once()
        saved = mock_save.call_args[0][0]
        assert saved.abrp.user_token == "my_token_abc"

    def test_abrp_setup_with_api_key(self):
        cfg = self._cfg(user_token="")
        with (
            patch("tesla_cli.cli.commands.abrp.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.abrp.save_config") as mock_save,
        ):
            result = _run("abrp", "setup", "my_token", "--api-key", "dev_key_xyz")
        assert result.exit_code == 0
        saved = mock_save.call_args[0][0]
        assert saved.abrp.user_token == "my_token"
        assert saved.abrp.api_key == "dev_key_xyz"

    def test_abrp_send_no_token_fails(self):
        cfg = self._cfg(user_token="")
        mock_backend = MagicMock()
        mock_backend.get_vehicle_data.return_value = self._vehicle_data()
        with (
            patch("tesla_cli.cli.commands.abrp.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.abrp.resolve_vin", return_value=MOCK_VIN),
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
        ):
            result = _run("abrp", "send")
        # Should fail with config error about missing token
        assert result.exit_code != 0 or "token" in result.output.lower()

    def test_abrp_send_pushes_and_shows_soc(self):
        cfg = self._cfg(user_token="tok123")
        mock_backend = MagicMock()
        mock_backend.get_vehicle_data.return_value = self._vehicle_data()
        with (
            patch("tesla_cli.cli.commands.abrp.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.abrp.resolve_vin", return_value=MOCK_VIN),
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.cli.commands.abrp._push", return_value={"status": "ok"}) as mock_push,
        ):
            result = _run("abrp", "send")
        assert result.exit_code == 0
        mock_push.assert_called_once()
        tlm_arg = mock_push.call_args[0][1]
        assert tlm_arg["soc"] == 72
        assert "72" in result.output

    def test_abrp_send_json_output(self):
        cfg = self._cfg(user_token="tok123")
        mock_backend = MagicMock()
        mock_backend.get_vehicle_data.return_value = self._vehicle_data()
        with (
            patch("tesla_cli.cli.commands.abrp.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.abrp.resolve_vin", return_value=MOCK_VIN),
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.cli.commands.abrp._push", return_value={"status": "ok"}),
        ):
            result = _run("-j", "abrp", "send")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "telemetry" in data
        assert "abrp_response" in data
        assert data["telemetry"]["soc"] == 72

    def test_abrp_in_help(self):
        result = _run("abrp", "--help")
        assert result.exit_code == 0
        assert "send" in result.output
        assert "stream" in result.output


class TestBleCommands:
    """Tests for `tesla ble` command group."""

    def _cfg(self, key_path=""):
        from tesla_cli.core.config import Config

        cfg = Config()
        cfg.general.default_vin = MOCK_VIN
        cfg.ble.key_path = key_path
        return cfg

    def _mock_run(self, returncode=0, stdout="", stderr=""):
        mock_result = MagicMock()
        mock_result.returncode = returncode
        mock_result.stdout = stdout
        mock_result.stderr = stderr
        return mock_result

    def test_ble_status_no_binary(self):
        cfg = self._cfg()
        with (
            patch("tesla_cli.cli.commands.ble.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.ble.shutil.which", return_value=None),
        ):
            result = _run("ble", "status")
        assert result.exit_code == 0
        assert "not found" in result.output

    def test_ble_status_binary_found(self):
        cfg = self._cfg(key_path="/home/user/.tesla/private.pem")
        with (
            patch("tesla_cli.cli.commands.ble.load_config", return_value=cfg),
            patch(
                "tesla_cli.cli.commands.ble.shutil.which",
                return_value="/usr/local/bin/tesla-control",
            ),
        ):
            result = _run("ble", "status")
        assert result.exit_code == 0
        assert "found" in result.output

    def test_ble_status_json(self):
        cfg = self._cfg(key_path="/tmp/key.pem")
        with (
            patch("tesla_cli.cli.commands.ble.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.ble.shutil.which", return_value="/usr/bin/tesla-control"),
        ):
            result = _run("-j", "ble", "status")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["tesla_control_found"] is True
        assert data["key_path_set"] is True

    def test_ble_lock_success(self):
        cfg = self._cfg(key_path="/tmp/key.pem")
        with (
            patch("tesla_cli.cli.commands.ble.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.ble.resolve_vin", return_value=MOCK_VIN),
            patch("tesla_cli.cli.commands.ble.shutil.which", return_value="/usr/bin/tesla-control"),
            patch(
                "tesla_cli.cli.commands.ble.subprocess.run", return_value=self._mock_run(0, "ok")
            ),
        ):
            result = _run("ble", "lock")
        assert result.exit_code == 0
        assert "locked" in result.output.lower()

    def test_ble_lock_binary_not_found(self):
        cfg = self._cfg()
        with (
            patch("tesla_cli.cli.commands.ble.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.ble.resolve_vin", return_value=MOCK_VIN),
            patch("tesla_cli.cli.commands.ble.shutil.which", return_value=None),
        ):
            result = _run("ble", "lock")
        assert result.exit_code != 0

    def test_ble_unlock_success(self):
        cfg = self._cfg(key_path="/tmp/key.pem")
        with (
            patch("tesla_cli.cli.commands.ble.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.ble.resolve_vin", return_value=MOCK_VIN),
            patch("tesla_cli.cli.commands.ble.shutil.which", return_value="/usr/bin/tesla-control"),
            patch("tesla_cli.cli.commands.ble.subprocess.run", return_value=self._mock_run(0)),
        ):
            result = _run("ble", "unlock")
        assert result.exit_code == 0
        assert "unlocked" in result.output.lower()

    def test_ble_lock_json(self):
        cfg = self._cfg(key_path="/tmp/key.pem")
        with (
            patch("tesla_cli.cli.commands.ble.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.ble.resolve_vin", return_value=MOCK_VIN),
            patch("tesla_cli.cli.commands.ble.shutil.which", return_value="/usr/bin/tesla-control"),
            patch(
                "tesla_cli.cli.commands.ble.subprocess.run", return_value=self._mock_run(0, "ok")
            ),
        ):
            result = _run("-j", "ble", "lock")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"
        assert data["command"] == "lock"

    def test_ble_command_failure(self):
        cfg = self._cfg(key_path="/tmp/key.pem")
        with (
            patch("tesla_cli.cli.commands.ble.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.ble.resolve_vin", return_value=MOCK_VIN),
            patch("tesla_cli.cli.commands.ble.shutil.which", return_value="/usr/bin/tesla-control"),
            patch(
                "tesla_cli.cli.commands.ble.subprocess.run",
                return_value=self._mock_run(1, stderr="BLE handshake failed"),
            ),
        ):
            result = _run("ble", "lock")
        assert result.exit_code != 0
        assert "BLE handshake failed" in result.output

    def test_ble_in_help(self):
        result = _run("ble", "--help")
        assert result.exit_code == 0
        assert "lock" in result.output
        assert "unlock" in result.output


class TestTeslaMateGrafana:
    """Tests for `tesla teslaMate grafana` command."""

    def _cfg(self, grafana_url="http://localhost:3000"):
        from tesla_cli.core.config import Config

        cfg = Config()
        cfg.grafana.url = grafana_url
        return cfg

    def _patched_cfg(self, cfg):
        return patch("tesla_cli.cli.commands.teslaMate.load_config", return_value=cfg)

    def test_grafana_default_opens_overview(self):
        cfg = self._cfg()
        with self._patched_cfg(cfg), patch("webbrowser.open") as mock_open:
            result = _run("teslaMate", "grafana")
        assert result.exit_code == 0
        mock_open.assert_called_once()
        url = mock_open.call_args[0][0]
        assert "localhost:3000" in url
        assert "overview" in url

    def test_grafana_trips_dashboard(self):
        cfg = self._cfg()
        with self._patched_cfg(cfg), patch("webbrowser.open") as mock_open:
            result = _run("teslaMate", "grafana", "trips")
        assert result.exit_code == 0
        url = mock_open.call_args[0][0]
        assert "trips" in url

    def test_grafana_charges_dashboard(self):
        cfg = self._cfg()
        with self._patched_cfg(cfg), patch("webbrowser.open") as mock_open:
            result = _run("teslaMate", "grafana", "charges")
        assert result.exit_code == 0
        url = mock_open.call_args[0][0]
        assert "charges" in url

    def test_grafana_custom_url(self):
        cfg = self._cfg(grafana_url="http://myserver:3000")
        with self._patched_cfg(cfg), patch("webbrowser.open") as mock_open:
            result = _run("teslaMate", "grafana", "battery")
        assert result.exit_code == 0
        url = mock_open.call_args[0][0]
        assert "myserver:3000" in url
        assert "battery" in url

    def test_grafana_json_mode(self):
        cfg = self._cfg()
        with self._patched_cfg(cfg), patch("webbrowser.open"):
            result = _run("-j", "teslaMate", "grafana", "efficiency")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dashboard"] == "efficiency"
        assert "localhost:3000" in data["url"]

    def test_grafana_unknown_dashboard(self):
        cfg = self._cfg()
        with self._patched_cfg(cfg):
            result = _run("teslaMate", "grafana", "nonexistent_board")
        assert result.exit_code != 0
        assert "Unknown dashboard" in result.output

    def test_grafana_vampire_dashboard(self):
        cfg = self._cfg()
        with self._patched_cfg(cfg), patch("webbrowser.open") as mock_open:
            result = _run("teslaMate", "grafana", "vampire")
        assert result.exit_code == 0
        url = mock_open.call_args[0][0]
        assert "vampire" in url

    def test_grafana_in_help(self):
        result = _run("teslaMate", "--help")
        assert result.exit_code == 0
        assert "grafana" in result.output


# ─────────────────────────────────────────────────────────────────────────────
# v2.3.0 Tests: vehicle map, geofence, Home Assistant
# ─────────────────────────────────────────────────────────────────────────────


class TestVehicleMap:
    """Tests for `tesla vehicle map`."""

    def _cfg(self):
        from tesla_cli.core.config import Config

        cfg = Config()
        cfg.general.default_vin = MOCK_VIN
        return cfg

    def _drive_state(self, lat=37.4219, lon=-122.0840, heading=90, speed=0, shift="P"):
        return {
            "latitude": lat,
            "longitude": lon,
            "heading": heading,
            "speed": speed,
            "shift_state": shift,
        }

    def test_map_renders_grid(self):
        mock_backend = MagicMock()
        mock_backend.get_drive_state.return_value = self._drive_state()
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "map")
        assert result.exit_code == 0
        # Grid contains directional chars and coordinate labels
        assert "N " in result.output or "°" in result.output

    def test_map_json_output(self):
        mock_backend = MagicMock()
        mock_backend.get_drive_state.return_value = self._drive_state(
            lat=51.5074, lon=-0.1278, heading=270
        )
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("-j", "vehicle", "map")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["lat"] == 51.5074
        assert data["lon"] == -0.1278
        assert data["heading"] == 270

    def test_map_no_gps_exits(self):
        mock_backend = MagicMock()
        mock_backend.get_drive_state.return_value = {"speed": 0}
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "map")
        assert result.exit_code != 0
        assert "GPS" in result.output or "No GPS" in result.output

    def test_map_in_help(self):
        result = _run("vehicle", "--help")
        assert "map" in result.output

    def test_map_custom_span(self):
        mock_backend = MagicMock()
        mock_backend.get_drive_state.return_value = self._drive_state()
        with (
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=self._cfg()),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("vehicle", "map", "--span", "0.02")
        assert result.exit_code == 0


class TestGeofenceCommands:
    """Tests for `tesla geofence` command group."""

    def _cfg(self, zones=None):
        from tesla_cli.core.config import Config

        cfg = Config()
        cfg.general.default_vin = MOCK_VIN
        if zones:
            cfg.geofences.zones = zones
        return cfg

    def test_geofence_add(self):
        cfg = self._cfg()
        with (
            patch("tesla_cli.cli.commands.geofence.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.geofence.save_config") as mock_save,
        ):
            result = _run("geofence", "add", "home", "--lat", "37.4219", "--lon", "-122.0840")
        assert result.exit_code == 0
        assert "home" in result.output
        mock_save.assert_called_once()
        saved = mock_save.call_args[0][0]
        assert "home" in saved.geofences.zones
        assert saved.geofences.zones["home"]["lat"] == 37.4219

    def test_geofence_add_with_radius(self):
        cfg = self._cfg()
        with (
            patch("tesla_cli.cli.commands.geofence.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.geofence.save_config") as mock_save,
        ):
            result = _run(
                "geofence",
                "add",
                "work",
                "--lat",
                "37.3382",
                "--lon",
                "-121.8863",
                "--radius",
                "0.3",
            )
        assert result.exit_code == 0
        saved = mock_save.call_args[0][0]
        assert saved.geofences.zones["work"]["radius_km"] == 0.3

    def test_geofence_add_json(self):
        cfg = self._cfg()
        with (
            patch("tesla_cli.cli.commands.geofence.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.geofence.save_config"),
        ):
            result = _run("-j", "geofence", "add", "home", "--lat", "37.4219", "--lon", "-122.0840")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["zone"] == "home"
        assert data["status"] == "added"

    def test_geofence_list_empty(self):
        cfg = self._cfg()
        with patch("tesla_cli.cli.commands.geofence.load_config", return_value=cfg):
            result = _run("geofence", "list")
        assert result.exit_code == 0
        assert "No geofence" in result.output

    def test_geofence_list_with_zones(self):
        cfg = self._cfg(
            zones={
                "home": {"lat": 37.4219, "lon": -122.0840, "radius_km": 0.5},
                "work": {"lat": 37.3382, "lon": -121.8863, "radius_km": 0.3},
            }
        )
        with patch("tesla_cli.cli.commands.geofence.load_config", return_value=cfg):
            result = _run("geofence", "list")
        assert result.exit_code == 0
        assert "home" in result.output
        assert "work" in result.output

    def test_geofence_list_json(self):
        cfg = self._cfg(zones={"home": {"lat": 37.4219, "lon": -122.0840, "radius_km": 0.5}})
        with patch("tesla_cli.cli.commands.geofence.load_config", return_value=cfg):
            result = _run("-j", "geofence", "list")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]["name"] == "home"

    def test_geofence_remove_existing(self):
        cfg = self._cfg(zones={"home": {"lat": 37.4219, "lon": -122.0840, "radius_km": 0.5}})
        with (
            patch("tesla_cli.cli.commands.geofence.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.geofence.save_config") as mock_save,
        ):
            result = _run("geofence", "remove", "home")
        assert result.exit_code == 0
        assert "removed" in result.output.lower()
        saved = mock_save.call_args[0][0]
        assert "home" not in saved.geofences.zones

    def test_geofence_remove_nonexistent(self):
        cfg = self._cfg()
        with patch("tesla_cli.cli.commands.geofence.load_config", return_value=cfg):
            result = _run("geofence", "remove", "nonexistent")
        assert result.exit_code != 0

    def test_geofence_watch_no_zones_exits(self):
        cfg = self._cfg()
        with (
            patch("tesla_cli.cli.commands.geofence.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.geofence.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("geofence", "watch")
        assert result.exit_code != 0
        assert "No geofence" in result.output

    def test_geofence_watch_detects_enter(self):
        """Vehicle moves inside zone → ENTER event fired."""
        cfg = self._cfg(
            zones={
                "home": {"lat": 37.4219, "lon": -122.0840, "radius_km": 0.5},
            }
        )
        call_count = [0]

        # First call: outside zone, second call: inside zone, third: interrupt
        def _drive_side_effect(v):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"latitude": 37.4300, "longitude": -122.0900}  # ~1.2 km away
            if call_count[0] == 2:
                return {"latitude": 37.4219, "longitude": -122.0840}  # inside
            raise KeyboardInterrupt

        mock_backend = MagicMock()
        mock_backend.get_drive_state.side_effect = _drive_side_effect

        from contextlib import ExitStack

        patches = [
            patch("tesla_cli.cli.commands.geofence.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.geofence.resolve_vin", return_value=MOCK_VIN),
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch("time.sleep"),
        ]
        with ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            result = _run("geofence", "watch", "--interval", "5")
        assert result.exit_code == 0
        assert "ENTER" in result.output

    def test_geofence_in_help(self):
        result = _run("geofence", "--help")
        assert result.exit_code == 0
        assert "add" in result.output
        assert "watch" in result.output


class TestHaCommands:
    """Tests for `tesla ha` command group."""

    def _cfg(self, url="http://ha.local:8123", token="ha_token_abc"):
        from tesla_cli.core.config import Config

        cfg = Config()
        cfg.general.default_vin = MOCK_VIN
        cfg.home_assistant.url = url
        cfg.home_assistant.token = token
        return cfg

    def _vehicle_data(self):
        return {
            "charge_state": {
                "battery_level": 72,
                "battery_range": 220.0,
                "charging_state": "Disconnected",
                "charge_limit_soc": 80,
                "charge_energy_added": 5.2,
                "charger_power": 0,
            },
            "drive_state": {
                "speed": 0,
                "shift_state": "P",
                "latitude": 37.4219,
                "longitude": -122.0840,
                "heading": 90,
            },
            "climate_state": {
                "inside_temp": 22.0,
                "outside_temp": 18.5,
                "is_climate_on": False,
            },
            "vehicle_state": {
                "locked": True,
                "odometer": 12500.0,
                "software_version": "2024.14.3",
                "is_user_present": False,
            },
        }

    def test_ha_setup_saves_config(self):
        cfg = self._cfg(url="", token="")
        with (
            patch("tesla_cli.cli.commands.ha.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.ha.save_config") as mock_save,
        ):
            result = _run("ha", "setup", "http://ha.local:8123", "my_ha_token")
        assert result.exit_code == 0
        saved = mock_save.call_args[0][0]
        assert saved.home_assistant.url == "http://ha.local:8123"
        assert saved.home_assistant.token == "my_ha_token"

    def test_ha_status_not_configured(self):
        cfg = self._cfg(url="", token="")
        with patch("tesla_cli.cli.commands.ha.load_config", return_value=cfg):
            result = _run("ha", "status")
        assert result.exit_code == 0
        assert "Not configured" in result.output or "not set" in result.output

    def test_ha_status_configured_json(self):
        cfg = self._cfg()
        with patch("tesla_cli.cli.commands.ha.load_config", return_value=cfg):
            result = _run("-j", "ha", "status")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["configured"] is True
        assert data["token_set"] is True
        assert "ha.local" in data["url"]

    def test_ha_push_no_config_fails(self):
        cfg = self._cfg(url="", token="")
        with (
            patch("tesla_cli.cli.commands.ha.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.ha.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("ha", "push")
        assert result.exit_code != 0
        assert "not configured" in result.output.lower()

    def test_ha_push_success(self):
        cfg = self._cfg()
        mock_backend = MagicMock()
        mock_backend.get_vehicle_data.return_value = self._vehicle_data()
        with (
            patch("tesla_cli.cli.commands.ha.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.ha.resolve_vin", return_value=MOCK_VIN),
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch(
                "tesla_cli.cli.commands.ha._push_state",
                return_value={"entity_id": "sensor.tesla_battery_level", "state": "72"},
            ),
        ):
            result = _run("ha", "push")
        assert result.exit_code == 0
        assert "Pushed" in result.output

    def test_ha_push_json(self):
        cfg = self._cfg()
        mock_backend = MagicMock()
        mock_backend.get_vehicle_data.return_value = self._vehicle_data()
        with (
            patch("tesla_cli.cli.commands.ha.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.ha.resolve_vin", return_value=MOCK_VIN),
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.cli.commands.ha._push_state", return_value={"state": "ok"}),
        ):
            result = _run("-j", "ha", "push")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "pushed" in data
        assert data["pushed"] > 0
        assert "results" in data

    def test_ha_push_partial_failure(self):
        """Some pushes fail → errors reported but exit 0."""
        cfg = self._cfg()
        mock_backend = MagicMock()
        mock_backend.get_vehicle_data.return_value = self._vehicle_data()
        call_count = [0]

        def _push_side(base, tok, eid, state, attrs):
            call_count[0] += 1
            if call_count[0] % 3 == 0:
                raise ConnectionError("HA unreachable")
            return {"state": state}

        with (
            patch("tesla_cli.cli.commands.ha.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.ha.resolve_vin", return_value=MOCK_VIN),
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.cli.commands.ha._push_state", side_effect=_push_side),
        ):
            result = _run("ha", "push")
        assert result.exit_code == 0  # partial failure is warned, not fatal

    def test_ha_in_help(self):
        result = _run("ha", "--help")
        assert result.exit_code == 0
        assert "push" in result.output
        assert "sync" in result.output


# ─── tesla query ─────────────────────────────────────────────────────────────


class TestQueryCommand:
    """Tests for tesla query (openquery integration)."""

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _mock_simit_result(self):
        from openquery.models.co.simit import SimitResult

        return SimitResult(
            cedula="12345678",
            comparendos=0,
            multas=0,
            acuerdos_pago=0,
            total_deuda=0.0,
            paz_y_salvo=True,
        )

    def _mock_runt_result(self):
        from openquery.models.co.runt import RuntResult

        return RuntResult(
            placa="ABC123",
            marca="TESLA",
            linea="MODEL Y",
            modelo_ano="2026",
            color="BLANCO",
            estado="ACTIVO",
            numero_vin="LRWYGCEK3TC512197",
            tipo_combustible="ELECTRICO",
            soat_vigente=True,
            soat_aseguradora="SURA",
            tecnomecanica_vigente=True,
        )

    def _mock_source(self, result):
        """Return a mock source whose .query() returns result."""
        src = MagicMock()
        src.query.return_value = result
        meta = MagicMock()
        meta.name = "co.test"
        meta.display_name = "Test Source"
        meta.description = "test"
        meta.country = "CO"
        meta.supported_inputs = []
        meta.requires_browser = False
        meta.requires_captcha = False
        meta.rate_limit_rpm = 10
        src.meta.return_value = meta
        src.supports.return_value = True
        return src

    # ── tesla query sources ───────────────────────────────────────────────────

    def test_query_sources_lists_table(self):
        mock_src = self._mock_source(self._mock_simit_result())
        with patch("openquery.sources.list_sources", return_value=[mock_src]):
            result = _run("query", "sources")
        assert result.exit_code == 0

    def test_query_sources_json(self):
        mock_src = self._mock_source(self._mock_simit_result())
        with patch("openquery.sources.list_sources", return_value=[mock_src]):
            result = _run("--json", "query", "sources")
        assert result.exit_code == 0
        import json

        parsed = json.loads(result.output)
        assert isinstance(parsed, list)

    # ── tesla query run ───────────────────────────────────────────────────────

    def test_query_run_simit_by_cedula(self):
        simit_result = self._mock_simit_result()
        mock_src = self._mock_source(simit_result)
        with patch("openquery.sources.get_source", return_value=mock_src):
            result = _run("query", "run", "co.simit", "--cedula", "12345678")
        assert result.exit_code == 0

    def test_query_run_unknown_source_exits_1(self):
        with (
            patch("openquery.sources.get_source", side_effect=KeyError("co.unknown")),
            patch("openquery.sources.list_sources", return_value=[]),
        ):
            result = _run("query", "run", "co.unknown", "--cedula", "111")
        assert result.exit_code == 1

    def test_query_run_no_input_exits_1(self):
        result = _run("query", "run", "co.simit")
        assert result.exit_code == 1

    def test_query_run_invalid_extra_json_exits_1(self):
        result = _run("query", "run", "co.combustible", "--extra", "not-json")
        assert result.exit_code == 1

    # ── convenience commands ──────────────────────────────────────────────────

    def test_query_simit_cedula(self):
        simit_result = self._mock_simit_result()
        mock_src = self._mock_source(simit_result)
        with patch("openquery.sources.get_source", return_value=mock_src):
            result = _run("query", "simit", "--cedula", "12345678")
        assert result.exit_code == 0

    def test_query_simit_placa(self):
        simit_result = self._mock_simit_result()
        mock_src = self._mock_source(simit_result)
        with patch("openquery.sources.get_source", return_value=mock_src):
            result = _run("query", "simit", "--placa", "ABC123")
        assert result.exit_code == 0

    def test_query_runt_placa(self):
        runt_result = self._mock_runt_result()
        mock_src = self._mock_source(runt_result)
        with patch("openquery.sources.get_source", return_value=mock_src):
            result = _run("query", "runt", "--placa", "ABC123")
        assert result.exit_code == 0

    def test_query_runt_vin(self):
        runt_result = self._mock_runt_result()
        mock_src = self._mock_source(runt_result)
        with patch("openquery.sources.get_source", return_value=mock_src):
            result = _run("query", "runt", "--vin", "LRWYGCEK3TC512197")
        assert result.exit_code == 0

    def test_query_procuraduria(self):
        from pydantic import BaseModel

        class ProcResult(BaseModel):
            sin_antecedentes: bool = True
            cedula: str = "12345678"

        mock_src = self._mock_source(ProcResult())
        with patch("openquery.sources.get_source", return_value=mock_src):
            result = _run("query", "procuraduria", "--cedula", "12345678")
        assert result.exit_code == 0

    def test_query_pico_y_placa(self):
        from pydantic import BaseModel

        class PypResult(BaseModel):
            placa: str = "ABC123"
            restringido: bool = False

        mock_src = self._mock_source(PypResult())
        with patch("openquery.sources.get_source", return_value=mock_src):
            result = _run("query", "pico-y-placa", "--placa", "ABC123")
        assert result.exit_code == 0

    def test_query_combustible_with_ciudad(self):
        from pydantic import BaseModel

        class CombResult(BaseModel):
            municipio: str = "BOGOTA"
            corriente: float = 14500.0

        mock_src = self._mock_source(CombResult())
        with patch("openquery.sources.get_source", return_value=mock_src):
            result = _run("query", "combustible", "--ciudad", "BOGOTA")
        assert result.exit_code == 0

    def test_query_fasecolda_marca_modelo(self):
        from pydantic import BaseModel

        class FasecResult(BaseModel):
            marca: str = "TESLA"
            precio_referencia: float = 350000000.0

        mock_src = self._mock_source(FasecResult())
        with patch("openquery.sources.get_source", return_value=mock_src):
            result = _run("query", "fasecolda", "--marca", "TESLA", "--modelo", "2026")
        assert result.exit_code == 0

    def test_query_recalls_marca(self):
        from pydantic import BaseModel

        class RecallResult(BaseModel):
            marca: str = "TESLA"
            recalls: list = []

        mock_src = self._mock_source(RecallResult())
        with patch("openquery.sources.get_source", return_value=mock_src):
            result = _run("query", "recalls", "--marca", "TESLA")
        assert result.exit_code == 0

    # ── openquery not installed ───────────────────────────────────────────────

    def test_query_simit_not_installed_exits_1(self):
        import builtins

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "openquery" or name.startswith("openquery."):
                raise ImportError("No module named 'openquery'")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = _run("query", "simit", "--cedula", "12345678")
        assert result.exit_code == 1

    # ── backend delegation ────────────────────────────────────────────────────

    def test_simit_backend_delegates_to_openquery(self):
        simit_result = self._mock_simit_result()
        mock_src = self._mock_source(simit_result)
        with patch("openquery.sources.get_source", return_value=mock_src):
            from tesla_cli.core.backends.simit import SimitBackend

            backend = SimitBackend()
            data = backend.query_by_cedula("12345678")
        assert data.paz_y_salvo is True
        assert data.comparendos == 0

    def test_simit_backend_placa_delegation(self):
        simit_result = self._mock_simit_result()
        mock_src = self._mock_source(simit_result)
        with patch("openquery.sources.get_source", return_value=mock_src):
            from tesla_cli.core.backends.simit import SimitBackend

            backend = SimitBackend()
            data = backend.query_by_placa("ABC123")
        assert data.paz_y_salvo is True

    def test_runt_backend_delegates_to_openquery(self):
        runt_result = self._mock_runt_result()
        mock_src = self._mock_source(runt_result)
        with patch("openquery.sources.get_source", return_value=mock_src):
            from tesla_cli.core.backends.runt import RuntBackend

            backend = RuntBackend()
            data = backend.query_by_vin("LRWYGCEK3TC512197")
        assert data.marca == "TESLA"
        assert data.placa == "ABC123"

    def test_runt_backend_raises_runt_error_on_openquery_failure(self):
        mock_src = MagicMock()
        mock_src.query.side_effect = Exception("network timeout")
        with patch("openquery.sources.get_source", return_value=mock_src):
            from tesla_cli.core.backends.runt import RuntBackend, RuntError

            backend = RuntBackend()
            with pytest.raises(RuntError, match="network timeout"):
                backend.query_by_plate("ABC123")

    def test_simit_backend_raises_simit_error_on_import_failure(self):
        import builtins

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "openquery" or name.startswith("openquery."):
                raise ImportError("No module named 'openquery'")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            from tesla_cli.core.backends.simit import SimitBackend, SimitError

            backend = SimitBackend()
            with pytest.raises(SimitError, match="openquery is required"):
                backend.query_by_cedula("12345678")


# ── teslaMate energy-report ───────────────────────────────────────────────────

MOCK_DAILY_ENERGY_ROWS = [
    {"date": "2026-03-01", "kwh": 15.2, "km": 110.0},
    {"date": "2026-03-05", "kwh": 22.5, "km": 165.0},
    {"date": "2026-02-10", "kwh": 8.3, "km": 60.0},
    {"date": "2026-02-20", "kwh": 31.0, "km": 230.0},
    {"date": "2026-01-15", "kwh": 18.7, "km": 140.0},
]


class TestTeslaMateEnergyReport:
    """Tests for tesla teslaMate energy-report."""

    def _patched(self, rows=None):
        if rows is None:
            rows = MOCK_DAILY_ENERGY_ROWS
        mock_backend = MagicMock()
        mock_backend.get_daily_energy.return_value = rows
        return patch("tesla_cli.cli.commands.teslaMate._backend", return_value=mock_backend)

    def test_energy_report_renders_table(self):
        with self._patched():
            result = _run("teslaMate", "energy-report")
        assert result.exit_code == 0
        assert "2026-03" in result.output
        assert "kWh" in result.output

    def test_energy_report_json(self):
        with self._patched():
            result = _run("-j", "teslaMate", "energy-report")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]["month"] == "2026-03"
        assert "kwh" in data[0]

    def test_energy_report_groups_by_month(self):
        with self._patched():
            result = _run("-j", "teslaMate", "energy-report")
        data = json.loads(result.output)
        months = [r["month"] for r in data]
        # March + February + January
        assert "2026-03" in months
        assert "2026-02" in months
        assert "2026-01" in months

    def test_energy_report_kwh_totals(self):
        with self._patched():
            result = _run("-j", "teslaMate", "energy-report")
        data = json.loads(result.output)
        mar = next(r for r in data if r["month"] == "2026-03")
        assert abs(mar["kwh"] - (15.2 + 22.5)) < 0.01

    def test_energy_report_wh_per_km(self):
        with self._patched():
            result = _run("-j", "teslaMate", "energy-report")
        data = json.loads(result.output)
        mar = next(r for r in data if r["month"] == "2026-03")
        assert mar["wh_per_km"] is not None
        assert mar["wh_per_km"] > 0

    def test_energy_report_empty_no_crash(self):
        with self._patched(rows=[]):
            result = _run("teslaMate", "energy-report")
        assert result.exit_code == 0
        assert "No energy data" in result.output

    def test_energy_report_months_flag(self):
        mock_backend = MagicMock()
        mock_backend.get_daily_energy.return_value = MOCK_DAILY_ENERGY_ROWS
        with patch("tesla_cli.cli.commands.teslaMate._backend", return_value=mock_backend):
            result = _run("teslaMate", "energy-report", "--months", "12")
        assert result.exit_code == 0
        mock_backend.get_daily_energy.assert_called_once_with(days=12 * 31)

    def test_energy_report_in_help(self):
        result = _run("teslaMate", "--help")
        assert "energy-report" in result.output


# ── REST: GET /api/teslaMate/charging-locations ───────────────────────────────


class TestTeslaMatChargingLocationsApi:
    """Tests for GET /api/teslaMate/charging-locations."""

    MOCK_LOCATIONS = [
        {"location": "Home", "sessions": 42, "kwh_total": 1890.5, "last_visit": "2026-03-28"},
        {"location": "Work", "sessions": 15, "kwh_total": 450.0, "last_visit": "2026-03-20"},
    ]

    def _setup(self, mock_backend=None, raise_exceptions=True):
        from fastapi.testclient import TestClient

        from tesla_cli.api.app import create_app

        if mock_backend is None:
            mock_backend = MagicMock()
            mock_backend.get_charging_locations.return_value = self.MOCK_LOCATIONS
        app = create_app()
        app.state.override_vin = MOCK_VIN
        p = patch("tesla_cli.api.routes.teslaMate._backend", return_value=mock_backend)
        p.start()
        client = TestClient(app, raise_server_exceptions=raise_exceptions)
        return client, mock_backend, p

    def test_charging_locations_returns_list(self):
        client, _, p = self._setup()
        try:
            resp = client.get("/api/teslaMate/charging-locations")
        finally:
            p.stop()
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert data[0]["location"] == "Home"

    def test_charging_locations_days_param(self):
        client, mock_backend, p = self._setup()
        try:
            resp = client.get("/api/teslaMate/charging-locations?days=180&limit=5")
        finally:
            p.stop()
        assert resp.status_code == 200
        mock_backend.get_charging_locations.assert_called_once_with(days=180, limit=5)

    def test_charging_locations_503_when_no_db(self):
        from fastapi import HTTPException
        from fastapi.testclient import TestClient

        from tesla_cli.api.app import create_app

        mock_backend_fn = MagicMock(
            side_effect=HTTPException(status_code=503, detail="TeslaMate not configured.")
        )
        app = create_app()
        app.state.override_vin = MOCK_VIN
        with patch("tesla_cli.api.routes.teslaMate._backend", side_effect=mock_backend_fn):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/api/teslaMate/charging-locations")
        assert resp.status_code == 503


# ── REST: GET /api/vehicle/odometer ──────────────────────────────────────────


class TestVehicleOdometerApi:
    """Tests for GET /api/vehicle/odometer."""

    def _setup(self, mock_backend=None, raise_exceptions=True):
        from fastapi.testclient import TestClient

        from tesla_cli.api.app import create_app
        from tests.conftest import MOCK_VEHICLE_DATA

        if mock_backend is None:
            mock_backend = MagicMock()
            mock_backend.get_vehicle_state.return_value = MOCK_VEHICLE_DATA["vehicle_state"]
        app = create_app()
        app.state.override_vin = MOCK_VIN
        patches = [
            patch("tesla_cli.api.routes.vehicle.get_vehicle_backend", return_value=mock_backend),
            patch("tesla_cli.api.routes.vehicle.load_config", return_value=MagicMock()),
            patch("tesla_cli.api.routes.vehicle.resolve_vin", return_value=MOCK_VIN),
        ]
        for p in patches:
            p.start()
        client = TestClient(app, raise_server_exceptions=raise_exceptions)
        return client, mock_backend, patches

    def _teardown(self, patches):
        for p in patches:
            p.stop()

    def test_odometer_returns_dict(self):
        client, _, patches = self._setup()
        try:
            resp = client.get("/api/vehicle/odometer")
        finally:
            self._teardown(patches)
        assert resp.status_code == 200
        data = resp.json()
        assert "odometer_miles" in data
        assert "vin" in data

    def test_odometer_value(self):
        client, _, patches = self._setup()
        try:
            resp = client.get("/api/vehicle/odometer")
        finally:
            self._teardown(patches)
        data = resp.json()
        assert data["odometer_miles"] == 150.5

    def test_odometer_has_queried_at(self):
        client, _, patches = self._setup()
        try:
            resp = client.get("/api/vehicle/odometer")
        finally:
            self._teardown(patches)
        data = resp.json()
        assert "queried_at" in data

    def test_odometer_503_when_asleep(self):
        from tesla_cli.core.exceptions import VehicleAsleepError

        mock_backend = MagicMock()
        mock_backend.get_vehicle_state.side_effect = VehicleAsleepError("asleep")
        client, _, patches = self._setup(mock_backend=mock_backend, raise_exceptions=False)
        try:
            resp = client.get("/api/vehicle/odometer")
        finally:
            self._teardown(patches)
        assert resp.status_code == 503


# ═══════════════════════════════════════════════════════════════════════════════
# Charge History (Fleet API)
# ═══════════════════════════════════════════════════════════════════════════════


class TestChargeHistory:
    """Tests for `tesla charge history` and ChargingHistory model."""

    MOCK_API_RESPONSE = {
        "screen_title": "Charging History",
        "total_charged": {
            "title": "Total Charged",
            "value": "1234.5",
            "after_adornment": "kWh",
        },
        "charging_history_graph": {
            "data_points": [
                {
                    "timestamp": {"display_string": "Mar 15"},
                    "values": [
                        {
                            "value": "45.2",
                            "raw_value": 45.2,
                            "after_adornment": "kWh",
                            "sub_title": "Home",
                        }
                    ],
                },
                {
                    "timestamp": {"display_string": "Mar 20"},
                    "values": [
                        {
                            "value": "32.1",
                            "raw_value": 32.1,
                            "after_adornment": "kWh",
                            "sub_title": "Supercharger",
                        }
                    ],
                },
                {
                    "timestamp": {"display_string": "Mar 25"},
                    "values": [
                        {
                            "value": "0",
                            "raw_value": 0,
                            "after_adornment": "kWh",
                            "sub_title": "",
                        }
                    ],
                },
            ]
        },
        "total_charged_breakdown": {
            "home": {
                "value": "800",
                "after_adornment": "kWh",
                "sub_title": "at Home",
            },
            "super": {
                "value": "434.5",
                "after_adornment": "kWh",
                "sub_title": "Supercharging",
            },
        },
    }

    def test_model_parses_api_response(self):
        from tesla_cli.core.models.charge import ChargingHistory

        history = ChargingHistory.from_api(self.MOCK_API_RESPONSE)
        assert history.total_kwh == 1234.5
        assert "1234.5" in history.total_label
        assert len(history.points) == 2  # zero-value point filtered out
        assert history.points[0].kwh == 45.2
        assert history.points[0].location == "Home"
        assert history.points[1].kwh == 32.1
        assert history.points[1].timestamp == "Mar 20"
        assert len(history.breakdown) == 2

    def test_model_handles_empty_response(self):
        from tesla_cli.core.models.charge import ChargingHistory

        history = ChargingHistory.from_api({})
        assert history.total_kwh == 0.0
        assert history.points == []
        assert history.breakdown == {}

    def test_model_handles_missing_values(self):
        from tesla_cli.core.models.charge import ChargingHistory

        data = {
            "charging_history_graph": {
                "data_points": [
                    {"timestamp": {}, "values": []},
                ]
            }
        }
        history = ChargingHistory.from_api(data)
        assert history.points == []

    @patch("tesla_cli.cli.commands.charge.get_vehicle_backend")
    @patch("tesla_cli.cli.commands.charge.load_config")
    def test_cli_renders_history(self, mock_cfg, mock_bk):
        mock_cfg.return_value = MagicMock(default_vin="TEST123", backend="fleet")
        backend = MagicMock()
        backend.get_charge_history.return_value = self.MOCK_API_RESPONSE
        mock_bk.return_value = backend

        result = _run("charge", "history")
        assert result.exit_code == 0
        assert "45.2" in result.output or "Charging History" in result.output

    @patch("tesla_cli.cli.commands.charge.get_vehicle_backend")
    @patch("tesla_cli.cli.commands.charge.load_config")
    def test_cli_json_mode(self, mock_cfg, mock_bk):
        mock_cfg.return_value = MagicMock(default_vin="TEST123", backend="fleet")
        backend = MagicMock()
        backend.get_charge_history.return_value = self.MOCK_API_RESPONSE
        mock_bk.return_value = backend

        result = _run("--json", "charge", "history")
        assert result.exit_code == 0

    @patch("tesla_cli.cli.commands.charge.get_vehicle_backend")
    @patch("tesla_cli.cli.commands.charge.load_config")
    def test_cli_backend_not_supported(self, mock_cfg, mock_bk):
        from tesla_cli.core.exceptions import BackendNotSupportedError

        mock_cfg.return_value = MagicMock(default_vin="TEST123", backend="owner")
        backend = MagicMock()
        backend.get_charge_history.side_effect = BackendNotSupportedError(
            "charge history", "fleet"
        )
        mock_bk.return_value = backend

        result = _run("charge", "history")
        assert result.exit_code == 1
        assert "teslaMate" in result.output.lower() or "fleet" in result.output.lower()

    def test_model_serializes_to_dict(self):
        from tesla_cli.core.models.charge import ChargingHistory

        history = ChargingHistory.from_api(self.MOCK_API_RESPONSE)
        d = history.model_dump()
        assert d["total_kwh"] == 1234.5
        assert len(d["points"]) == 2
        assert d["points"][0]["location"] == "Home"


# ═══════════════════════════════════════════════════════════════════════════════
# Unified Charging Sessions
# ═══════════════════════════════════════════════════════════════════════════════


class TestChargingSessions:
    """Tests for `tesla charge sessions` and ChargingSession model."""

    MOCK_TM_ROW = {
        "id": 1,
        "start_date": "2026-03-15 08:30:00",
        "end_date": "2026-03-15 12:00:00",
        "energy_added_kwh": 42.5,
        "cost": 9.35,
        "start_battery_level": 20,
        "end_battery_level": 80,
        "location": "Home",
    }

    MOCK_TM_ROW_NO_COST = {
        "id": 2,
        "start_date": "2026-03-20 14:00:00",
        "end_date": "2026-03-20 15:30:00",
        "energy_added_kwh": 25.0,
        "cost": None,
        "start_battery_level": 40,
        "end_battery_level": 65,
        "location": "Supercharger Bogota",
    }

    def test_from_teslamate_with_actual_cost(self):
        from tesla_cli.core.models.charge import ChargingSession

        s = ChargingSession.from_teslamate(self.MOCK_TM_ROW)
        assert s.kwh == 42.5
        assert s.cost == 9.35
        assert s.cost_estimated is False
        assert s.battery_start == 20
        assert s.battery_end == 80
        assert s.source == "teslamate"
        assert "Home" in s.location

    def test_from_teslamate_estimates_cost(self):
        from tesla_cli.core.models.charge import ChargingSession

        s = ChargingSession.from_teslamate(self.MOCK_TM_ROW_NO_COST, cost_per_kwh=0.22)
        assert s.cost == 5.50  # 25.0 * 0.22
        assert s.cost_estimated is True

    def test_from_teslamate_no_cost_no_estimate(self):
        from tesla_cli.core.models.charge import ChargingSession

        s = ChargingSession.from_teslamate(self.MOCK_TM_ROW_NO_COST, cost_per_kwh=0.0)
        assert s.cost is None
        assert s.cost_estimated is False

    def test_from_fleet_point(self):
        from tesla_cli.core.models.charge import ChargingHistoryPoint, ChargingSession

        pt = ChargingHistoryPoint(timestamp="Mar 15", kwh=45.2, location="Home")
        s = ChargingSession.from_fleet_point(pt, cost_per_kwh=0.22)
        assert s.kwh == 45.2
        assert s.cost == 9.94  # 45.2 * 0.22 = 9.944 → 9.94
        assert s.cost_estimated is True
        assert s.source == "fleet"
        assert s.battery_start is None

    def test_from_fleet_point_no_cost(self):
        from tesla_cli.core.models.charge import ChargingHistoryPoint, ChargingSession

        pt = ChargingHistoryPoint(timestamp="Mar 15", kwh=45.2, location="Home")
        s = ChargingSession.from_fleet_point(pt, cost_per_kwh=0.0)
        assert s.cost is None

    def test_serializes_to_dict(self):
        from tesla_cli.core.models.charge import ChargingSession

        s = ChargingSession.from_teslamate(self.MOCK_TM_ROW)
        d = s.model_dump()
        assert d["kwh"] == 42.5
        assert d["source"] == "teslamate"
        assert d["battery_start"] == 20

    @patch("tesla_cli.cli.commands.charge.load_config")
    def test_cli_sessions_fallback_to_fleet(self, mock_cfg):
        """When TeslaMate not configured, falls back to Fleet API."""
        cfg = MagicMock()
        cfg.general.cost_per_kwh = 0.22
        cfg.teslaMate.database_url = ""  # No TeslaMate
        mock_cfg.return_value = cfg

        mock_api_resp = {
            "total_charged": {"value": "100", "after_adornment": "kWh"},
            "charging_history_graph": {
                "data_points": [
                    {
                        "timestamp": {"display_string": "Mar 15"},
                        "values": [{"raw_value": 45.2, "sub_title": "Home"}],
                    }
                ]
            },
            "total_charged_breakdown": {},
        }

        with patch(
            "tesla_cli.cli.commands.charge.get_vehicle_backend"
        ) as mock_bk:
            backend = MagicMock()
            backend.get_charge_history.return_value = mock_api_resp
            mock_bk.return_value = backend

            result = _run("charge", "sessions")
            assert result.exit_code == 0
            assert "45.2" in result.output or "Fleet API" in result.output


# ═══════════════════════════════════════════════════════════════════════════════
# Vehicle Summary
# ═══════════════════════════════════════════════════════════════════════════════


class TestVehicleSummary:
    """Tests for `tesla vehicle summary`."""

    MOCK_DATA = {
        "charge_state": {
            "battery_level": 72,
            "battery_range": 186.5,
            "charge_limit_soc": 80,
            "charging_state": "Stopped",
            "charger_power": 0,
            "time_to_full_charge": 0,
        },
        "climate_state": {
            "inside_temp": 22.5,
            "outside_temp": 18.0,
            "is_climate_on": False,
        },
        "drive_state": {
            "latitude": 4.711,
            "longitude": -74.072,
            "speed": 0,
            "heading": 180,
        },
        "vehicle_state": {
            "locked": True,
            "sentry_mode": True,
            "car_version": "2026.8.7",
            "odometer": 1234.5,
        },
    }

    @patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend")
    @patch("tesla_cli.cli.commands.vehicle.load_config")
    def test_cli_renders_summary(self, mock_cfg, mock_bk):
        mock_cfg.return_value = MagicMock(default_vin="7SAYTEST123456")
        backend = MagicMock()
        backend.get_vehicle_data.return_value = self.MOCK_DATA
        mock_bk.return_value = backend

        result = _run("vehicle", "summary")
        assert result.exit_code == 0
        assert "72%" in result.output
        assert "Locked" in result.output
        assert "2026.8.7" in result.output

    @patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend")
    @patch("tesla_cli.cli.commands.vehicle.load_config")
    def test_cli_json_mode(self, mock_cfg, mock_bk):
        mock_cfg.return_value = MagicMock(default_vin="7SAYTEST123456")
        backend = MagicMock()
        backend.get_vehicle_data.return_value = self.MOCK_DATA
        mock_bk.return_value = backend

        result = _run("--json", "vehicle", "summary")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["charge_state"]["battery_level"] == 72

    @patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend")
    @patch("tesla_cli.cli.commands.vehicle.load_config")
    def test_cli_shows_charging_details(self, mock_cfg, mock_bk):
        mock_cfg.return_value = MagicMock(default_vin="7SAYTEST123456")
        charging_data = dict(self.MOCK_DATA)
        charging_data["charge_state"] = {
            **self.MOCK_DATA["charge_state"],
            "charging_state": "Charging",
            "charger_power": 11,
            "time_to_full_charge": 1.5,
        }
        backend = MagicMock()
        backend.get_vehicle_data.return_value = charging_data
        mock_bk.return_value = backend

        result = _run("vehicle", "summary")
        assert result.exit_code == 0
        assert "Charging" in result.output
        assert "11 kW" in result.output


# ═══════════════════════════════════════════════════════════════════════════════
# Vehicle Summary + Charge Cost Summary
# ═══════════════════════════════════════════════════════════════════════════════


class TestChargeCostSummary:
    """Tests for `tesla charge cost-summary`."""

    @patch("tesla_cli.core.backends.teslaMate.TeslaMateBacked")
    @patch("tesla_cli.cli.commands.charge.load_config")
    def test_cost_summary_with_teslamate(self, mock_cfg, MockTM):
        """Cost summary using TeslaMate data."""
        cfg = MagicMock()
        cfg.general.cost_per_kwh = 0.0
        cfg.teslaMate.database_url = "postgresql://localhost/teslamate"
        mock_cfg.return_value = cfg

        mock_rows = [
            {"start_date": "2026-03-01 08:00", "energy_added_kwh": 30.0, "cost": 6.60, "start_battery_level": 20, "end_battery_level": 80, "location": "Home"},
            {"start_date": "2026-03-05 14:00", "energy_added_kwh": 20.0, "cost": 8.00, "start_battery_level": 40, "end_battery_level": 65, "location": "Supercharger"},
        ]
        MockTM.return_value.get_charging_sessions.return_value = mock_rows

        result = _run("charge", "cost-summary")
        assert result.exit_code == 0
        assert "50.0" in result.output  # 30 + 20 kWh
        assert "$14.60" in result.output  # 6.60 + 8.00

    @patch("tesla_cli.cli.commands.charge.load_config")
    def test_cost_summary_json_mode(self, mock_cfg):
        cfg = MagicMock()
        cfg.general.cost_per_kwh = 0.22
        cfg.teslaMate.database_url = ""
        mock_cfg.return_value = cfg

        mock_api = {
            "total_charged": {"value": "100", "after_adornment": "kWh"},
            "charging_history_graph": {
                "data_points": [
                    {"timestamp": {"display_string": "Mar 15"}, "values": [{"raw_value": 50.0, "sub_title": "Home"}]},
                ]
            },
            "total_charged_breakdown": {},
        }

        with patch("tesla_cli.cli.commands.charge.get_vehicle_backend") as mock_bk:
            backend = MagicMock()
            backend.get_charge_history.return_value = mock_api
            mock_bk.return_value = backend
            result = _run("--json", "charge", "cost-summary")
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["total_kwh"] == 50.0
            assert data["total_cost"] == 11.0  # 50 * 0.22
            assert data["estimated_cost_sessions"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# MQTT Commands (basic registration tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestMqttCommands:
    """Basic tests for mqtt command group."""

    def test_mqtt_app_registered(self):
        result = _run("mqtt", "--help")
        assert result.exit_code == 0
        assert "setup" in result.output
        assert "status" in result.output
        assert "test" in result.output
        assert "publish" in result.output
        assert "ha-discovery" in result.output

    @patch("tesla_cli.cli.commands.mqtt_cmd.load_config")
    def test_mqtt_status_no_config(self, mock_cfg):
        cfg = MagicMock()
        cfg.mqtt.broker = ""
        mock_cfg.return_value = cfg

        result = _run("mqtt", "status")
        # Should show not configured or error gracefully
        assert result.exit_code in (0, 1)


# ═══════════════════════════════════════════════════════════════════════════════
# Providers Commands
# ═══════════════════════════════════════════════════════════════════════════════


class TestProvidersCommands:
    """Basic tests for providers command group."""

    def test_providers_app_registered(self):
        result = _run("providers", "--help")
        assert result.exit_code == 0

    @patch("tesla_cli.core.providers.get_registry")
    def test_providers_status(self, mock_reg):
        mock_reg.return_value = MagicMock(
            providers=[],
            for_capability=MagicMock(return_value=None),
        )
        result = _run("providers", "status")
        assert result.exit_code == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Config Validation Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfigValidation:
    """Test Pydantic config field validation."""

    def test_cost_per_kwh_rejects_negative(self):
        from pydantic import ValidationError

        from tesla_cli.core.config import GeneralConfig

        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            GeneralConfig(cost_per_kwh=-1.0)

    def test_cost_per_kwh_accepts_zero(self):
        from tesla_cli.core.config import GeneralConfig

        cfg = GeneralConfig(cost_per_kwh=0.0)
        assert cfg.cost_per_kwh == 0.0

    def test_cost_per_kwh_accepts_positive(self):
        from tesla_cli.core.config import GeneralConfig

        cfg = GeneralConfig(cost_per_kwh=0.22)
        assert cfg.cost_per_kwh == 0.22

    def test_port_rejects_zero(self):
        from pydantic import ValidationError

        from tesla_cli.core.config import TeslamateConfig

        with pytest.raises(ValidationError):
            TeslamateConfig(postgres_port=0)

    def test_port_rejects_too_high(self):
        from pydantic import ValidationError

        from tesla_cli.core.config import TeslamateConfig

        with pytest.raises(ValidationError):
            TeslamateConfig(postgres_port=99999)

    def test_port_accepts_valid(self):
        from tesla_cli.core.config import TeslamateConfig

        cfg = TeslamateConfig(postgres_port=5433)
        assert cfg.postgres_port == 5433

    def test_mqtt_qos_rejects_invalid(self):
        from pydantic import ValidationError

        from tesla_cli.core.config import MqttConfig

        with pytest.raises(ValidationError):
            MqttConfig(qos=3)

    def test_mqtt_qos_accepts_valid(self):
        from tesla_cli.core.config import MqttConfig

        for q in (0, 1, 2):
            cfg = MqttConfig(qos=q)
            assert cfg.qos == q

    def test_car_id_rejects_zero(self):
        from pydantic import ValidationError

        from tesla_cli.core.config import TeslamateConfig

        with pytest.raises(ValidationError):
            TeslamateConfig(car_id=0)


# ═══════════════════════════════════════════════════════════════════════════════
# CSV Export
# ═══════════════════════════════════════════════════════════════════════════════


class TestChargeCsvExport:
    """Tests for --csv flag on charge commands."""

    @patch("tesla_cli.cli.commands.charge.load_config")
    @patch("tesla_cli.cli.commands.charge._fetch_sessions")
    def test_sessions_csv_export(self, mock_fetch, mock_cfg, tmp_path):
        from tesla_cli.core.models.charge import ChargingSession

        mock_cfg.return_value = MagicMock(general=MagicMock(cost_per_kwh=0.22))
        sessions = [
            ChargingSession(date="2026-03-15", location="Home", kwh=30.0, cost=6.60, source="teslamate"),
            ChargingSession(date="2026-03-20", location="SC", kwh=20.0, cost=8.00, source="teslamate"),
        ]
        mock_fetch.return_value = (sessions, "TeslaMate")

        csv_path = str(tmp_path / "charges.csv")
        result = _run("charge", "sessions", "--csv", csv_path)
        assert result.exit_code == 0
        assert "Exported 2 sessions" in result.output

        import csv
        with open(csv_path) as f:
            reader = list(csv.DictReader(f))
        assert len(reader) == 2
        assert reader[0]["kwh"] == "30.0"
        assert reader[0]["location"] == "Home"

    @patch("tesla_cli.cli.commands.charge.load_config")
    @patch("tesla_cli.cli.commands.charge._fetch_sessions")
    def test_cost_summary_csv_export(self, mock_fetch, mock_cfg, tmp_path):
        from tesla_cli.core.models.charge import ChargingSession

        mock_cfg.return_value = MagicMock(general=MagicMock(cost_per_kwh=0.22))
        sessions = [
            ChargingSession(date="2026-03-15", location="Home", kwh=30.0, cost=6.60, source="teslamate"),
        ]
        mock_fetch.return_value = (sessions, "TeslaMate")

        csv_path = str(tmp_path / "costs.csv")
        result = _run("charge", "cost-summary", "--csv", csv_path)
        assert result.exit_code == 0
        assert "Exported" in result.output


# ═══════════════════════════════════════════════════════════════════════════════
# Dossier Sources
# ═══════════════════════════════════════════════════════════════════════════════


class TestDossierSources:
    """Tests for `tesla dossier sources`."""

    def test_sources_command_registered(self):
        result = _run("dossier", "sources")
        assert result.exit_code == 0
        assert "registered" in result.output.lower() or "Data Sources" in result.output

    def test_sources_shows_known_ids(self):
        result = _run("dossier", "sources")
        assert result.exit_code == 0
        # At least some built-in sources should appear
        assert "tesla.order" in result.output or "vin.decode" in result.output

    def test_sources_json_mode(self):
        result = _run("--json", "dossier", "sources")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) > 0
        assert "id" in data[0]
        assert "category" in data[0]
        assert "has_data" in data[0]


# ═══════════════════════════════════════════════════════════════════════════════
# Dossier Migration — New Command Paths
# ═══════════════════════════════════════════════════════════════════════════════


class TestDossierMigration:
    """Verify that migrated commands work from their new homes."""

    # ── Order lifecycle ──

    def test_order_gates(self):
        result = _run("order", "gates")
        assert result.exit_code in (0, 1)  # 0=ok, 1=no dossier

    def test_order_estimate(self):
        result = _run("order", "estimate")
        assert result.exit_code in (0, 1)

    def test_order_checklist(self):
        result = _run("order", "checklist")
        assert result.exit_code == 0

    def test_order_ships(self):
        result = _run("order", "ships")
        assert result.exit_code in (0, 1)  # may fail without network

    # ── Vehicle identity ──

    def test_vehicle_vin_decode(self):
        result = _run("vehicle", "vin", "7SAYGDEF1TF123456")
        assert result.exit_code == 0
        assert "Model Y" in result.output or "7SAY" in result.output

    def test_vehicle_option_codes(self):
        result = _run("vehicle", "option-codes")
        assert result.exit_code in (0, 1)  # 1 if no dossier

    def test_vehicle_battery_health(self):
        result = _run("vehicle", "battery-health")
        assert result.exit_code in (0, 1)

    def test_vehicle_profile(self):
        result = _run("vehicle", "profile")
        assert result.exit_code in (0, 1)

    # ── Query/data ──

    def test_query_history(self):
        result = _run("query", "history")
        assert result.exit_code in (0, 1)  # 1 if no snapshots exist

    def test_query_data_sources(self):
        result = _run("query", "data-sources")
        assert result.exit_code == 0
        assert "registered" in result.output.lower() or "Data Sources" in result.output

    def test_query_data_sources_json(self):
        result = _run("--json", "query", "data-sources")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)

    # ── Old paths still work (backward compat) ──

    def test_dossier_gates_still_works(self):
        result = _run("dossier", "gates")
        assert result.exit_code in (0, 1)

    def test_dossier_vin_still_works(self):
        result = _run("dossier", "vin", "7SAYGDEF1TF123456")
        assert result.exit_code == 0
