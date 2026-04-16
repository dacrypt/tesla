from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_module(module_name: str, file_name: str):
    path = ROOT / file_name
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


change_detector = _load_module("change_detector", "change-detector.py")
refresh_mission_control = _load_module("refresh_mission_control", "refresh-mission-control.py")


def test_flatten_ignores_metadata():
    data = {
        "generated_at": "2026-01-01T00:00:00",
        "runt": {
            "estado": "REGISTRADO",
            "queried_at": "2026-01-01T00:00:00",
        },
    }

    flat = change_detector.flatten(data)

    assert "generated_at" not in flat
    assert "runt.queried_at" not in flat
    assert flat["runt.estado"] == "REGISTRADO"



def test_flatten_unwraps_provenance():
    data = {
        "runt": {
            "_meta": {"status": "ok"},
            "data": {
                "placa": "ABC123",
                "estado": "REGISTRADO",
            },
        }
    }

    flat = change_detector.flatten(data)

    assert flat["runt.placa"] == "ABC123"
    assert flat["runt.estado"] == "REGISTRADO"
    assert "runt._meta" not in flat



def test_section_has_data_with_provenance():
    raw = {
        "runt": {
            "_meta": {"status": "ok"},
            "data": {"estado": "REGISTRADO"},
        }
    }

    assert change_detector.section_has_data(raw, "runt") is True



def test_section_has_data_without_provenance():
    raw = {
        "runt": {"estado": "REGISTRADO"},
    }

    assert change_detector.section_has_data(raw, "runt") is True



def test_detect_no_changes_identical_data(tmp_path, monkeypatch):
    current = {
        "runt": {"estado": "REGISTRADO", "placa": "ABC123"},
        "order": {"status": "BOOKED"},
    }
    history_dir = tmp_path / "history"
    history_dir.mkdir()
    data_file = tmp_path / "mission-control-data.json"
    last_snapshot = history_dir / "last-snapshot.json"
    data_file.write_text(json.dumps(current))
    last_snapshot.write_text(json.dumps(current))

    monkeypatch.setattr(change_detector, "DATA_FILE", data_file)
    monkeypatch.setattr(change_detector, "HISTORY_DIR", history_dir)
    monkeypatch.setattr(change_detector, "LAST_SNAPSHOT", last_snapshot)

    assert change_detector.detect_changes() == []



def test_detect_change_in_field(tmp_path, monkeypatch):
    previous = {
        "runt": {"estado": "REGISTRADO", "placa": "ABC123"},
        "order": {"status": "BOOKED"},
    }
    current = {
        "runt": {"estado": "REGISTRADO", "placa": "XYZ987"},
        "order": {"status": "BOOKED"},
    }
    history_dir = tmp_path / "history"
    history_dir.mkdir()
    data_file = tmp_path / "mission-control-data.json"
    last_snapshot = history_dir / "last-snapshot.json"
    data_file.write_text(json.dumps(current))
    last_snapshot.write_text(json.dumps(previous))

    monkeypatch.setattr(change_detector, "DATA_FILE", data_file)
    monkeypatch.setattr(change_detector, "HISTORY_DIR", history_dir)
    monkeypatch.setattr(change_detector, "LAST_SNAPSHOT", last_snapshot)

    changes = change_detector.detect_changes()

    assert len(changes) == 1
    assert changes[0]["field"] == "runt.placa"
    assert changes[0]["type"] == "changed"
    assert changes[0]["old"] == "ABC123"
    assert changes[0]["new"] == "XYZ987"



def test_skip_failed_section(tmp_path, monkeypatch):
    previous = {
        "runt": {
            "_meta": {"status": "ok"},
            "data": {"placa": "ABC123", "estado": "REGISTRADO"},
        },
        "order": {"status": "BOOKED"},
    }
    current = {
        "runt": {
            "_meta": {"status": "error"},
            "data": {"placa": "XYZ987", "estado": "REGISTRADO"},
        },
        "order": {"status": "BOOKED"},
    }
    history_dir = tmp_path / "history"
    history_dir.mkdir()
    data_file = tmp_path / "mission-control-data.json"
    last_snapshot = history_dir / "last-snapshot.json"
    data_file.write_text(json.dumps(current))
    last_snapshot.write_text(json.dumps(previous))

    monkeypatch.setattr(change_detector, "DATA_FILE", data_file)
    monkeypatch.setattr(change_detector, "HISTORY_DIR", history_dir)
    monkeypatch.setattr(change_detector, "LAST_SNAPSHOT", last_snapshot)

    assert change_detector.detect_changes() == []



def test_refresh_module_exposes_main():
    assert callable(refresh_mission_control.main)
