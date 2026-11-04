"""Experimental features registry (core/experimental.py) and its surfaces."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tesla_cli.core import experimental as exp
from tests.conftest import run_cli


def _meta(error=None, refreshed="2026-11-01T00:00:00Z"):
    return lambda sid: {"id": sid, "error": error, "refreshed_at": refreshed}


def test_registry_ids_unique_and_sources_mapped():
    ids = [f.id for f in exp.FEATURES]
    assert len(ids) == len(set(ids))
    assert exp.feature_for_source("tesla.order").id == "order_tracking"
    assert exp.feature_for_source("co.runt").id == "co_registries"
    assert exp.feature_for_source("tesla.billing") is None


def test_sources_exist_in_registry():
    """Every source an experimental feature watches is a real source id."""
    import re

    from tesla_cli.core import sources

    src = Path(sources.__file__).read_text()
    declared = set(re.findall(r'id="([a-z_.]+)"', src))
    for f in exp.FEATURES:
        for s in f.sources:
            assert s in declared, s


def test_status_failing():
    with patch.object(exp, "_source_meta", side_effect=_meta(error="HTTP 404")):
        row = exp.status(exp.FEATURES[0])
    assert row["status"] == "failing" and "HTTP 404" in row["error"]


def test_status_unused_and_ok():
    with patch.object(exp, "_source_meta", side_effect=_meta(refreshed=None)):
        assert exp.status(exp.FEATURES[0])["status"] == "unused"
    with patch.object(exp, "_source_meta", side_effect=_meta()):
        assert exp.status(exp.FEATURES[0])["status"] == "ok"


def test_status_not_installed():
    feature = next(f for f in exp.FEATURES if f.requires_module)
    with patch("importlib.util.find_spec", return_value=None):
        row = exp.status(feature)
    assert row["status"] == "not-installed"
    assert "tesla-cli[query]" in row["remediation"]


def test_doctor_lists_experimental_rows():
    with patch.object(exp, "_source_meta", side_effect=_meta(error="boom")):
        result = run_cli("doctor", "--json")
    rows = json.loads(result.output)
    x = {r["name"]: r for r in rows if r["tier"] == "X"}
    assert x["order_tracking"]["status"] == "failing"


def test_api_experimental_endpoint():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from tesla_cli.api.app import create_app

    with patch.object(exp, "_source_meta", side_effect=_meta()):
        r = TestClient(create_app()).get("/api/doctor/experimental")
    assert r.status_code == 200
    assert {row["id"] for row in r.json()} == {f.id for f in exp.FEATURES}


def test_alert_title_marks_experimental(tmp_path, monkeypatch):
    from tesla_cli.core import events

    monkeypatch.setattr(events, "EVENTS_FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(events, "ALERTS_FILE", tmp_path / "alerts.jsonl")
    events.emit_source_health("tesla.order", "HTTP 410 Gone", None)
    alert = events.list_alerts()[0]
    assert "experimental" in alert["title"]
    assert alert["message"] == "HTTP 410 Gone"  # raw: reconcile compares it


def test_help_marks_experimental_groups():
    assert "experimental" in run_cli("order", "--help").output
    assert "experimental" in run_cli("data", "--help").output
