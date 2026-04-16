"""Tests for the Mission Control read model."""

from __future__ import annotations

import json

import pytest

import tesla_cli.core.mission_control as mission_control_module


@pytest.fixture(autouse=True)
def _redirect_ui_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(mission_control_module, "UI_DIR", tmp_path / "ui")


def test_build_mission_control_from_sources_and_domains(monkeypatch):
    monkeypatch.setattr(
        mission_control_module.domains,
        "list_domains",
        lambda: [
            {
                "domain_id": "delivery",
                "computed_at": "2026-04-07T12:00:00+00:00",
                "summary": "Delivery scheduled for 2026-04-24",
                "health": {"status": "ok"},
            },
            {
                "domain_id": "legal",
                "computed_at": "2026-04-07T12:01:00+00:00",
                "summary": "Plate assigned: ABC123",
                "health": {"status": "degraded"},
            },
            {
                "domain_id": "financial",
                "computed_at": "2026-04-07T12:02:00+00:00",
                "summary": "Payment: financing",
                "health": {"status": "ok"},
            },
            {
                "domain_id": "safety",
                "computed_at": "2026-04-07T12:03:00+00:00",
                "summary": "2 NHTSA recall(s)",
                "health": {"status": "degraded"},
            },
        ],
    )
    monkeypatch.setattr(
        mission_control_module.sources,
        "list_sources",
        lambda: [
            {
                "id": "tesla.order",
                "name": "Tesla Order",
                "refreshed_at": "2026-04-07T11:59:00+00:00",
                "stale": False,
                "error": None,
            },
            {
                "id": "co.runt",
                "name": "RUNT",
                "refreshed_at": "2026-04-07T11:58:00+00:00",
                "stale": True,
                "error": None,
            },
        ],
    )
    details = {
        "tesla.order": {
            "data": {"vin": "VIN123"},
            "changes": [{"field": "orderStatus", "old": "ORDERED", "new": "VIN_ASSIGNED"}],
            "refreshed_at": "2026-04-07T11:59:00+00:00",
            "error": None,
            "stale": False,
        },
        "co.runt": {
            "data": {"placa": "ABC123"},
            "changes": [],
            "refreshed_at": "2026-04-07T11:58:00+00:00",
            "error": None,
            "stale": True,
        },
    }
    monkeypatch.setattr(
        mission_control_module.sources,
        "get_cached_with_meta",
        lambda source_id: details[source_id],
    )
    monkeypatch.setattr(
        mission_control_module.events,
        "list_events",
        lambda limit=20: [{"kind": "source_change", "source_id": "tesla.order"}],
    )
    monkeypatch.setattr(
        mission_control_module.events,
        "list_alerts",
        lambda limit=20, active_only=True: [{"kind": "domain_change", "domain_id": "legal"}],
    )

    result = mission_control_module.build_mission_control()

    assert result["executive"]["delivery_readiness"]["status"] == "ok"
    assert result["executive"]["legal_readiness"]["status"] == "degraded"
    assert result["executive"]["financial_state"]["status"] == "ok"
    assert result["executive"]["safety_posture"]["status"] == "degraded"
    assert result["executive"]["source_health"]["total_sources"] == 2
    assert result["critical_diffs"][0]["source_id"] == "tesla.order"
    assert result["timeline"][0]["kind"] == "source_change"
    assert result["active_alerts"][0]["domain_id"] == "legal"
    assert (mission_control_module.UI_DIR / "mission-control.json").exists()


def test_build_mission_control_persists_json(monkeypatch):
    monkeypatch.setattr(mission_control_module.domains, "list_domains", lambda: [])
    monkeypatch.setattr(mission_control_module.sources, "list_sources", lambda: [])
    monkeypatch.setattr(mission_control_module.sources, "get_cached_with_meta", lambda _source_id: {})

    mission_control_module.build_mission_control()

    payload = json.loads((mission_control_module.UI_DIR / "mission-control.json").read_text())
    assert "executive" in payload
    assert "domains" in payload
    assert "sources" in payload


def test_build_dashboard_summary_persists_json(monkeypatch):
    monkeypatch.setattr(
        mission_control_module,
        "build_mission_control",
        lambda: {
            "generated_at": "2026-04-07T12:00:00+00:00",
            "executive": {
                "delivery_readiness": {"status": "ok", "summary": "Delivery scheduled"},
                "financial_state": {"status": "ok", "summary": "Payment: financing"},
                "legal_readiness": {"status": "degraded", "summary": "Plate assigned"},
                "safety_posture": {"status": "degraded", "summary": "2 NHTSA recall(s)"},
                "source_health": {"status": "degraded", "ok_sources": 1, "total_sources": 2},
                "active_alerts_count": 0,
                "last_successful_refresh": "2026-04-07T11:59:00+00:00",
            },
            "critical_diffs": [{"source_id": "tesla.order"}],
        },
    )

    result = mission_control_module.build_dashboard_summary()

    assert result["critical_changes_count"] == 1
    assert result["delivery_readiness"]["status"] == "ok"
    assert result["financial_state"]["status"] == "ok"
    assert result["safety_posture"]["status"] == "degraded"
    assert (mission_control_module.UI_DIR / "dashboard-summary.json").exists()


def test_build_legacy_payload_uses_read_model_and_sources(monkeypatch):
    monkeypatch.setattr(
        mission_control_module,
        "build_mission_control",
        lambda: {
            "generated_at": "2026-04-07T12:00:00+00:00",
            "executive": {},
            "sources": [
                {"id": "tesla.order", "refreshed_at": "2026-04-07T11:59:00+00:00", "stale": False, "error": None},
                {"id": "co.runt", "refreshed_at": "2026-04-07T11:58:00+00:00", "stale": True, "error": None},
            ],
            "active_alerts": [{"kind": "domain_change"}],
            "timeline": [{"kind": "source_change"}],
        },
    )
    monkeypatch.setattr(
        mission_control_module.sources,
        "get_cached",
        lambda source_id: {
            "tesla.portal": {"delivery_details": {"enabled": True}},
            "co.simit": {"paz_y_salvo": True, "comparendos": 0, "total_deuda": 0},
            "us.epa_fuel_economy": {"ev_motor": "Cached Motor", "range_mi": 320},
            "us.nhtsa_recalls": {"count": 1},
            "us.nhtsa_complaints": {"total": 2},
            "us.nhtsa_investigations": {"count": 0},
        }.get(source_id),
    )

    payload = mission_control_module.build_legacy_mission_control_payload()

    assert payload["generated_at_local"] == "2026-04-07T12:00:00+00:00"
    assert payload["sources"]["tesla.order"]["ok"] is True
    assert payload["sources"]["co.runt"]["ok"] is False
    assert payload["epa"]["ev_motor"] == "Cached Motor"
    assert payload["_mission_control_view"]["active_alerts_count"] == 1


def test_build_legacy_payload_falls_back_to_enriched_order_cache(monkeypatch):
    monkeypatch.setattr(
        mission_control_module,
        "build_mission_control",
        lambda: {"generated_at": "2026-04-07T12:00:00+00:00", "executive": {}, "sources": [], "active_alerts": [], "timeline": []},
    )
    monkeypatch.setattr(
        mission_control_module.sources,
        "get_cached",
        lambda source_id: {
            "tesla.portal": {},
            "tesla.order": {
                "delivery": {
                    "appointment": "Apr 24, 2026 10:00",
                    "appointmentDateUtc": "2026-04-24T15:00:00Z",
                    "location": "Bogotá Delivery Center",
                    "address": "Cra 123 #45-67",
                },
                "tasks": [
                    {"taskType": "deliveryAcceptance", "completed": False, "active": True, "taskStatus": "PENDING"}
                ],
            },
            "tesla.delivery": {
                "appointment": "Apr 24, 2026 10:00",
                "appointmentDateUtc": "2026-04-24T15:00:00Z",
                "location": "Bogotá Delivery Center",
                "address": "Cra 123 #45-67",
            },
            "tesla.tasks": {
                "deliveryAcceptance": {"complete": False, "enabled": True, "status": "PENDING"},
            },
        }.get(source_id),
    )

    payload = mission_control_module.build_legacy_mission_control_payload()

    assert payload["delivery"]["delivery_details"]["deliveryAppointmentDateUtc"] == "2026-04-24T15:00:00Z"
    assert payload["tesla_tasks"]["deliveryAcceptance"]["enabled"] is True
