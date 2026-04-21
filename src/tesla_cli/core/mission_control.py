"""Mission Control read model derived from sources and domains."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from tesla_cli.core import domains, events, sources
from tesla_cli.core.config import CONFIG_DIR

UI_DIR = CONFIG_DIR / "ui"


def build_mission_control() -> dict[str, Any]:
    """Build and persist the Mission Control view model."""
    domain_list = domains.list_domains()
    source_list = sources.list_sources()
    events.reconcile_domain_alerts(domain_list)
    events.reconcile_source_alerts(source_list)
    source_details = [sources.get_cached_with_meta(item["id"]) for item in source_list]

    view = {
        "generated_at": _now(),
        "executive": _build_executive(domain_list, source_list),
        "domains": domain_list,
        "sources": [
            _merge_source_detail(item, detail)
            for item, detail in zip(source_list, source_details, strict=False)
        ],
        "critical_diffs": _build_critical_diffs(source_list, source_details),
        "timeline": _build_timeline(domain_list, source_list),
        "active_alerts": events.list_alerts(limit=20, active_only=True),
    }
    _save_view("mission-control.json", view)
    return view


def build_dashboard_summary() -> dict[str, Any]:
    """Build a compact dashboard summary derived from Mission Control."""
    view = build_mission_control()
    executive = view["executive"]
    summary = {
        "generated_at": view["generated_at"],
        "delivery_readiness": executive["delivery_readiness"],
        "financial_state": executive["financial_state"],
        "legal_readiness": executive["legal_readiness"],
        "safety_posture": executive["safety_posture"],
        "source_health": executive["source_health"],
        "active_alerts_count": executive["active_alerts_count"],
        "last_successful_refresh": executive["last_successful_refresh"],
        "critical_changes_count": len(view["critical_diffs"]),
    }
    _save_view("dashboard-summary.json", summary)
    return summary


def build_legacy_mission_control_payload() -> dict[str, Any]:
    """Build a compatibility payload for legacy Mission Control consumers."""
    view = build_mission_control()
    portal_cached = sources.get_cached("tesla.portal") or {}
    order_cached = sources.get_cached("tesla.order") or {}
    delivery_cached = sources.get_cached("tesla.delivery") or {}
    tasks_cached = sources.get_cached("tesla.tasks") or {}
    payload = {
        "generated_at": view["generated_at"],
        "generated_at_local": view["generated_at"],
        "sources": {
            item["id"]: {
                "ok": not item.get("stale") and not item.get("error"),
                "ts": item.get("refreshed_at"),
            }
            for item in view.get("sources", [])
        },
        "delivery": _extract_delivery_payload(delivery_cached, portal_cached, order_cached),
        "simit": _wrap_source_payload(sources.get_cached("co.simit") or {}),
        "epa": _wrap_source_payload(sources.get_cached("us.epa_fuel_economy") or {}),
        "nhtsa_recalls": _wrap_source_payload(sources.get_cached("us.nhtsa_recalls") or {}),
        "nhtsa_complaints": _wrap_source_payload(sources.get_cached("us.nhtsa_complaints") or {}),
        "nhtsa_investigations": _wrap_source_payload(
            sources.get_cached("us.nhtsa_investigations") or {}
        ),
        "tesla_tasks": _extract_tesla_tasks(tasks_cached, portal_cached, order_cached),
        "cron_runs": {"total": 0, "ok": 0, "errors": 0, "runs": []},
        "cron_job": {"schedule": "-", "last_status": "-"},
        "_mission_control_view": {
            "executive": view.get("executive", {}),
            "active_alerts_count": len(view.get("active_alerts", [])),
            "timeline_count": len(view.get("timeline", [])),
        },
    }
    return payload


def _save_view(filename: str, payload: dict[str, Any]) -> None:
    UI_DIR.mkdir(parents=True, exist_ok=True)
    (UI_DIR / filename).write_text(json.dumps(payload, default=str, indent=2))


def _wrap_source_payload(data: dict) -> dict:
    """Mimic the old wrapped shape expected by compatibility consumers."""
    return data.get("data", data) if isinstance(data, dict) else {}


def _extract_delivery_payload(delivery_data: dict, portal_data: dict, order_data: dict) -> dict:
    """Prefer explicit delivery source, then portal, then enriched order cache."""
    delivery_raw = _wrap_source_payload(delivery_data)
    if delivery_raw:
        portal_raw = _wrap_source_payload(portal_data)
        if (
            isinstance(portal_raw, dict)
            and portal_raw.get("delivery_details")
            and "delivery_details" not in delivery_raw
        ):
            delivery_raw = {**delivery_raw, "delivery_details": portal_raw.get("delivery_details")}
        if delivery_raw.get("appointmentDateUtc") and "delivery_details" not in delivery_raw:
            delivery_raw = {
                **delivery_raw,
                "delivery_details": {
                    "deliveryAppointmentDateUtc": delivery_raw.get("appointmentDateUtc", ""),
                    "deliveryTiming": {
                        "appointment": delivery_raw.get("appointment", ""),
                        "pickupLocationTitle": delivery_raw.get("location", ""),
                        "formattedAddressSingleLine": delivery_raw.get("address", ""),
                    },
                },
            }
        return delivery_raw
    portal_raw = _wrap_source_payload(portal_data)
    if portal_raw:
        return portal_raw
    order_raw = _wrap_source_payload(order_data)
    delivery = order_raw.get("delivery") or {}
    if not isinstance(delivery, dict):
        return {}
    appointment = delivery.get("appointment", "")
    appointment_date = delivery.get("appointmentDateUtc", "")
    location = delivery.get("location", "")
    address = delivery.get("address", "")
    if not any([appointment, appointment_date, location, address]):
        return delivery
    return {
        **delivery,
        "delivery_details": {
            "deliveryAppointmentDateUtc": appointment_date,
            "deliveryTiming": {
                "appointment": appointment,
                "pickupLocationTitle": location,
                "formattedAddressSingleLine": address,
            },
        },
    }


def _extract_tesla_tasks(tasks_data: dict, portal_data: dict, order_data: dict) -> dict:
    """Extract Tesla task shape from explicit source, portal, or order cache."""
    direct = _wrap_source_payload(tasks_data)
    if isinstance(direct, dict) and direct:
        return direct
    raw = _wrap_source_payload(portal_data)
    tasks = raw.get("tasks") or raw.get("tesla_tasks") or {}
    if not tasks:
        order_raw = _wrap_source_payload(order_data)
        tasks = order_raw.get("tasks") or order_raw.get("tesla_tasks") or {}
    if isinstance(tasks, list):
        mapped = {}
        for task in tasks:
            key = task.get("taskType") or task.get("task_type") or task.get("key")
            if key:
                mapped[key] = {
                    "complete": task.get("completed", False),
                    "enabled": task.get("enabled", task.get("active", False)),
                    "status": task.get("taskStatus") or task.get("status") or "",
                }
        return mapped
    return tasks if isinstance(tasks, dict) else {}


def _build_executive(
    domain_list: list[dict[str, Any]], source_list: list[dict[str, Any]]
) -> dict[str, Any]:
    domain_map = {item["domain_id"]: item for item in domain_list}
    delivery = domain_map.get("delivery", {})
    financial = domain_map.get("financial", {})
    legal = domain_map.get("legal", {})
    safety = domain_map.get("safety", {})

    health_sources = [item for item in source_list if item.get("auto_refresh", True)]
    ok_sources = sum(
        1 for item in health_sources if not item.get("stale") and not item.get("error")
    )
    degraded_sources = [
        item["id"] for item in health_sources if item.get("stale") or item.get("error")
    ]

    last_successful_refresh = max(
        (
            item.get("refreshed_at")
            for item in health_sources
            if item.get("refreshed_at") and not item.get("error")
        ),
        default=None,
    )

    active_alerts = events.list_alerts(limit=200, active_only=True)
    return {
        "delivery_readiness": {
            "status": delivery.get("health", {}).get("status", "missing"),
            "summary": delivery.get("summary", "No delivery projection yet"),
        },
        "legal_readiness": {
            "status": legal.get("health", {}).get("status", "missing"),
            "summary": legal.get("summary", "No legal projection yet"),
        },
        "financial_state": {
            "status": financial.get("health", {}).get("status", "missing"),
            "summary": financial.get("summary", "No financial projection yet"),
        },
        "safety_posture": {
            "status": safety.get("health", {}).get("status", "missing"),
            "summary": safety.get("summary", "No safety projection yet"),
        },
        "source_health": {
            "ok_sources": ok_sources,
            "total_sources": len(health_sources),
            "degraded_sources": degraded_sources,
            "status": (
                "ok"
                if ok_sources == len(health_sources)
                else "degraded"
                if ok_sources
                else "missing"
            ),
        },
        "active_alerts_count": len(active_alerts),
        "last_successful_refresh": last_successful_refresh,
    }


def _merge_source_detail(summary: dict[str, Any], detail: dict[str, Any] | None) -> dict[str, Any]:
    detail = detail or {}
    return {
        **summary,
        "data": detail.get("data"),
        "changes": detail.get("changes", []),
        "refreshed_at": detail.get("refreshed_at", summary.get("refreshed_at")),
        "error": detail.get("error", summary.get("error")),
        "stale": detail.get("stale", summary.get("stale")),
    }


def _build_critical_diffs(
    source_list: list[dict[str, Any]],
    source_details: list[dict[str, Any] | None],
) -> list[dict[str, Any]]:
    critical = []
    for item, detail in zip(source_list, source_details, strict=False):
        changes = (detail or {}).get("changes") or []
        if not changes:
            continue
        critical.append(
            {
                "source_id": item["id"],
                "source_name": item["name"],
                "changes_count": len(changes),
                "changes": changes[:5],
                "refreshed_at": item.get("refreshed_at"),
            }
        )
    critical.sort(key=lambda entry: entry.get("changes_count", 0), reverse=True)
    return critical[:10]


def _build_timeline(
    domain_list: list[dict[str, Any]],
    source_list: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Show only timeline entries that still match current domain truth."""
    rows = events.list_events(limit=100)
    domain_map = {item["domain_id"]: item for item in domain_list}
    source_map = {item["id"]: item for item in source_list}
    filtered = []
    for row in rows:
        if row.get("kind") == "domain_change":
            domain_id = row.get("domain_id")
            current = domain_map.get(domain_id)
            if current is None:
                continue
            if row.get("message") != current.get("summary"):
                continue
        if row.get("kind") == "health":
            source_id = row.get("source_id")
            current = source_map.get(source_id)
            if current is None:
                continue
            if row.get("message") != current.get("error"):
                continue
        if row.get("kind") in {"source_change", "resolved"}:
            source_id = row.get("source_id")
            if source_id and source_id not in source_map:
                continue
        filtered.append(row)
    return filtered[:20]


def _now() -> str:
    return datetime.now(UTC).isoformat()
