"""Tests for change-detector.py pipeline logic."""

import json
import sys
import tempfile
from pathlib import Path

import pytest

# Import from change-detector.py (it's a script, not a package)
_script = Path(__file__).parent.parent / "change-detector.py"
if not _script.exists():
    pytest.skip(
        "change-detector.py not present (gitignored personal script)", allow_module_level=True
    )

sys.path.insert(0, str(Path(__file__).parent.parent))
from importlib.util import module_from_spec, spec_from_file_location

_spec = spec_from_file_location("change_detector", _script)
cd = module_from_spec(_spec)
_spec.loader.exec_module(cd)


class TestFlatten:
    def test_ignores_metadata_fields(self):
        data = {"generated_at": "2026-01-01", "order": {"status": "BOOKED"}}
        flat = cd.flatten(data)
        assert "generated_at" not in flat
        assert "order.status" in flat

    def test_ignores_queried_at(self):
        data = {"runt": {"estado": "REGISTRADO", "queried_at": "2026-01-01"}}
        flat = cd.flatten(data)
        assert "runt.estado" in flat
        assert "runt.queried_at" not in flat

    def test_ignores_sources(self):
        data = {"sources": {"tesla": {"ok": True}}, "order": {"status": "X"}}
        flat = cd.flatten(data)
        assert "order.status" in flat
        assert not any("sources" in k for k in flat)

    def test_ignores_meta_in_provenance(self):
        data = {"runt": {"_meta": {"source": "RUNT"}, "data": {"placa": "ABC"}}}
        flat = cd.flatten(data)
        assert "runt.placa" in flat
        assert flat["runt.placa"] == "ABC"
        assert not any("_meta" in k for k in flat)

    def test_unwraps_provenance(self):
        data = {"order": {"_meta": {"source": "Tesla"}, "data": {"status": "BOOKED", "vin": "X"}}}
        flat = cd.flatten(data)
        assert flat.get("order.status") == "BOOKED"
        assert flat.get("order.vin") == "X"

    def test_handles_flat_data(self):
        """Non-provenance data should still work."""
        data = {"order": {"status": "BOOKED"}}
        flat = cd.flatten(data)
        assert flat["order.status"] == "BOOKED"

    def test_lists_serialized_as_json(self):
        data = {"items": {"tags": ["a", "b"]}}
        flat = cd.flatten(data)
        assert flat["items.tags"] == '["a", "b"]'

    def test_none_becomes_empty_string(self):
        data = {"x": {"val": None}}
        flat = cd.flatten(data)
        assert flat["x.val"] == ""


class TestSectionHasData:
    def test_with_provenance_ok(self):
        raw = {"runt": {"_meta": {"status": "ok"}, "data": {"placa": ""}}}
        assert cd.section_has_data(raw, "runt") is True

    def test_with_provenance_failed(self):
        raw = {"runt": {"_meta": {"status": "error"}, "data": None}}
        assert cd.section_has_data(raw, "runt") is False

    def test_without_provenance(self):
        raw = {"runt": {"estado": "REGISTRADO"}}
        assert cd.section_has_data(raw, "runt") is True

    def test_missing_section(self):
        raw = {}
        assert cd.section_has_data(raw, "runt") is False

    def test_empty_dict(self):
        raw = {"runt": {}}
        assert cd.section_has_data(raw, "runt") is False

    def test_none_value(self):
        raw = {"runt": None}
        assert cd.section_has_data(raw, "runt") is False


class TestDetectChanges:
    def setup_method(self):
        self._tmpdir = tempfile.mkdtemp()
        self._orig_data = cd.DATA_FILE
        self._orig_hist = cd.HISTORY_DIR
        self._orig_snap = cd.LAST_SNAPSHOT
        self._orig_log = cd.CHANGES_LOG
        cd.DATA_FILE = Path(self._tmpdir) / "data.json"
        cd.HISTORY_DIR = Path(self._tmpdir) / "history"
        cd.LAST_SNAPSHOT = cd.HISTORY_DIR / "last-snapshot.json"
        cd.CHANGES_LOG = cd.HISTORY_DIR / "changes.jsonl"
        cd.HISTORY_DIR.mkdir()

    def teardown_method(self):
        cd.DATA_FILE = self._orig_data
        cd.HISTORY_DIR = self._orig_hist
        cd.LAST_SNAPSHOT = self._orig_snap
        cd.CHANGES_LOG = self._orig_log
        import shutil

        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_no_changes_identical(self):
        data = {"order": {"status": "BOOKED"}, "runt": {"placa": ""}}
        cd.DATA_FILE.write_text(json.dumps(data))
        cd.LAST_SNAPSHOT.write_text(json.dumps(data))
        changes = cd.detect_changes()
        assert changes == []

    def test_detects_real_change(self):
        prev = {"order": {"status": "BOOKED"}, "runt": {"placa": ""}}
        curr = {"order": {"status": "BOOKED"}, "runt": {"placa": "ABC123"}}
        cd.LAST_SNAPSHOT.write_text(json.dumps(prev))
        cd.DATA_FILE.write_text(json.dumps(curr))
        changes = cd.detect_changes()
        assert len(changes) == 1
        assert changes[0]["field"] == "runt.placa"
        assert changes[0]["new"] == "ABC123"
        assert changes[0]["priority"] == "HIGH"

    def test_skips_section_missing_in_current(self):
        """If SIMIT failed this run (missing), don't alert about it."""
        prev = {"order": {"status": "BOOKED"}, "simit": {"comparendos": 0}}
        curr = {"order": {"status": "BOOKED"}}  # simit missing = failed
        cd.LAST_SNAPSHOT.write_text(json.dumps(prev))
        cd.DATA_FILE.write_text(json.dumps(curr))
        changes = cd.detect_changes()
        assert changes == []  # no false positive

    def test_skips_section_missing_in_previous(self):
        """If SIMIT was missing before (first run), don't alert about it appearing."""
        prev = {"order": {"status": "BOOKED"}}
        curr = {"order": {"status": "BOOKED"}, "simit": {"comparendos": 0}}
        cd.LAST_SNAPSHOT.write_text(json.dumps(prev))
        cd.DATA_FILE.write_text(json.dumps(curr))
        changes = cd.detect_changes()
        assert changes == []  # simit appearing is not a change, it's recovery

    def test_first_run_no_changes(self):
        data = {"order": {"status": "BOOKED"}}
        cd.DATA_FILE.write_text(json.dumps(data))
        # No snapshot exists yet
        changes = cd.detect_changes()
        assert changes == []
        assert cd.LAST_SNAPSHOT.exists()  # created baseline

    def test_provenance_wrapped_data(self):
        prev = {"runt": {"_meta": {"status": "ok"}, "data": {"placa": ""}}}
        curr = {"runt": {"_meta": {"status": "ok"}, "data": {"placa": "XYZ789"}}}
        cd.LAST_SNAPSHOT.write_text(json.dumps(prev))
        cd.DATA_FILE.write_text(json.dumps(curr))
        changes = cd.detect_changes()
        assert len(changes) == 1
        assert changes[0]["field"] == "runt.placa"
        assert changes[0]["new"] == "XYZ789"
