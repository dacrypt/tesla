"""Tests for persistent event and alert streams."""

from __future__ import annotations

import json

import pytest

import tesla_cli.core.domains as domains_module
import tesla_cli.core.events as events_module
import tesla_cli.core.sources as sources_module
from tesla_cli.core.sources import SourceDef, refresh_source, register_source


@pytest.fixture(autouse=True)
def _redirect_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(events_module, "EVENTS_DIR", tmp_path / "events")
    monkeypatch.setattr(events_module, "EVENTS_FILE", tmp_path / "events" / "events.jsonl")
    monkeypatch.setattr(events_module, "ALERTS_FILE", tmp_path / "events" / "alerts.jsonl")
    monkeypatch.setattr(sources_module, "SOURCES_DIR", tmp_path / "sources")
    monkeypatch.setattr(sources_module, "HISTORY_DIR", tmp_path / "source_history")
    monkeypatch.setattr(sources_module, "DIFFS_DIR", tmp_path / "source_diffs")
    monkeypatch.setattr(sources_module, "AUDIT_DIR", tmp_path / "source_audits")
    monkeypatch.setattr(domains_module, "DOMAINS_DIR", tmp_path / "domains")
    # `_SOURCES` is a module-global registry populated at import time by
    # `_register_defaults()`. Earlier tests may have mutated it (added test
    # fixtures, cleared real sources, etc.) — snapshot/restore so this
    # suite's `register_source` calls always take precedence.
    saved = dict(sources_module._SOURCES)
    sources_module._SOURCES.clear()
    yield
    sources_module._SOURCES.clear()
    sources_module._SOURCES.update(saved)


def _write_source(source_id: str, payload: dict) -> None:
    sources_module.SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    (sources_module.SOURCES_DIR / f"{source_id}.json").write_text(json.dumps(payload))


def test_source_refresh_emits_events_and_alerts():
    values = iter([{"placa": "ABC123"}, {"placa": "XYZ987"}])
    src = SourceDef(
        id="co.runt",
        name="RUNT",
        category="registro",
        fetch_fn=lambda: next(values),
        ttl=3600,
    )
    register_source(src)

    refresh_source("co.runt")
    refresh_source("co.runt")

    events = events_module.list_events(limit=10)
    alerts = events_module.list_alerts(limit=10, active_only=True)

    assert any(
        item["kind"] == "source_change" and item["source_id"] == "co.runt" for item in events
    )
    assert any(item["source_id"] == "co.runt" for item in alerts)


def test_source_recovery_resolves_health_alert():
    events_module.emit_source_health(
        "tesla.order", error="boom", previous_error=None, refreshed_at="2026-04-07T12:00:00+00:00"
    )
    assert len(events_module.list_alerts(limit=10, active_only=True)) == 1

    events_module.emit_source_health(
        "tesla.order", error=None, previous_error="boom", refreshed_at="2026-04-07T12:01:00+00:00"
    )

    assert len(events_module.list_alerts(limit=10, active_only=True)) == 0


def test_domain_recompute_emits_event_and_alert():
    _write_source(
        "co.runt",
        {
            "data": {"placa": "ABC123", "gravamenes": ["lease"]},
            "refreshed_at": "2026-04-07T12:00:00+00:00",
            "error": None,
        },
    )
    _write_source(
        "co.runt_soat",
        {
            "data": {"soat_vigente": True},
            "refreshed_at": "2026-04-07T12:00:00+00:00",
            "error": None,
        },
    )
    _write_source(
        "co.runt_rtm",
        {"data": {"rtm_vigente": True}, "refreshed_at": "2026-04-07T12:00:00+00:00", "error": None},
    )
    _write_source(
        "co.simit",
        {
            "data": {"comparendos": 2, "total_deuda": "50000"},
            "refreshed_at": "2026-04-07T12:00:00+00:00",
            "error": None,
        },
    )

    domains_module.recompute_domain("legal")

    events = events_module.list_events(limit=10)
    alerts = events_module.list_alerts(limit=10, active_only=True)

    assert any(item["kind"] == "domain_change" and item["domain_id"] == "legal" for item in events)
    assert any(item["domain_id"] == "legal" for item in alerts)


def test_domain_change_resolves_previous_open_alert_for_same_domain():
    events_module.emit_domain_change(
        "delivery",
        {
            "computed_at": "2026-04-07T12:00:00+00:00",
            "summary": "Delivery scheduled for 2026-04-24",
            "state": {"delivery_date": "2026-04-24"},
            "derived_flags": {"delivery_scheduled": True},
            "health": {"status": "ok"},
        },
        previous_projection={},
    )
    first_active = events_module.list_alerts(limit=10, active_only=True)
    assert len(first_active) == 1

    events_module.emit_domain_change(
        "delivery",
        {
            "computed_at": "2026-04-07T12:10:00+00:00",
            "summary": "Delivery scheduled for 2026-04-26",
            "state": {"delivery_date": "2026-04-26"},
            "derived_flags": {"delivery_scheduled": True},
            "health": {"status": "ok"},
        },
        previous_projection={
            "summary": "Delivery scheduled for 2026-04-24",
            "state": {"delivery_date": "2026-04-24"},
        },
    )

    active = events_module.list_alerts(limit=10, active_only=True)
    assert len(active) == 1
    assert "2026-04-26" in active[0]["message"]


def test_non_actionable_domain_change_does_not_open_alert():
    events_module.emit_domain_change(
        "financial",
        {
            "computed_at": "2026-04-07T12:00:00+00:00",
            "summary": "No financial signals available yet",
            "state": {},
            "derived_flags": {"has_financing": False, "has_fines_debt": False},
            "health": {"status": "degraded"},
        },
        previous_projection={},
    )

    active = events_module.list_alerts(limit=10, active_only=True)
    assert active == []


def test_reconcile_domain_alerts_resolves_stale_open_alerts():
    events_module.emit_domain_change(
        "delivery",
        {
            "computed_at": "2026-04-07T12:00:00+00:00",
            "summary": "Delivery scheduled for 2026-04-24",
            "state": {"delivery_date": "2026-04-24"},
            "derived_flags": {"delivery_scheduled": True},
            "health": {"status": "ok"},
        },
        previous_projection={},
    )

    events_module.reconcile_domain_alerts(
        [
            {
                "domain_id": "delivery",
                "summary": "VIN assigned (512197)",
                "state": {"vin": "LRWYGCEK3TC512197"},
                "derived_flags": {"delivery_scheduled": False, "vin_assigned": True},
                "health": {"status": "degraded"},
            }
        ]
    )

    active = events_module.list_alerts(limit=10, active_only=True)
    assert active == []


def test_ack_alert_marks_alert_without_resolving():
    events_module.emit_source_health(
        "tesla.order",
        error="boom",
        previous_error=None,
        refreshed_at="2026-04-07T12:00:00+00:00",
    )
    active = events_module.list_alerts(limit=10, active_only=True)
    alert_id = active[0]["alert_id"]

    acked = events_module.ack_alert(alert_id)

    assert acked is not None
    assert acked["acked_at"] is not None
    assert acked["resolved_at"] is None
