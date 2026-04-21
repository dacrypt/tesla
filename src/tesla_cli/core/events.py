"""Persistent event and alert streams for source/domain changes."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from tesla_cli.core.config import CONFIG_DIR

EVENTS_DIR = CONFIG_DIR / "events"
EVENTS_FILE = EVENTS_DIR / "events.jsonl"
ALERTS_FILE = EVENTS_DIR / "alerts.jsonl"


def delete_events(prefixes: list[str], before: str | None = None) -> int:
    """Delete events whose source_id or domain_id starts with any of *prefixes*.

    Optionally restricts to events whose ``created_at`` is strictly before
    *before* (an ISO-8601 string).  Returns the number of events deleted.
    """
    all_events = _read_jsonl(EVENTS_FILE, limit=None)
    if not all_events:
        return 0

    before_dt: datetime | None = None
    if before:
        before_dt = datetime.fromisoformat(before)
        if before_dt.tzinfo is None:
            before_dt = before_dt.replace(tzinfo=UTC)

    kept: list[dict[str, Any]] = []
    deleted = 0
    for event in all_events:
        source = event.get("source_id") or ""
        domain = event.get("domain_id") or ""
        prefix_match = any(
            source.startswith(p) or domain.startswith(p) for p in prefixes
        )
        if prefix_match:
            if before_dt is not None:
                raw_ts = event.get("created_at", "")
                try:
                    event_dt = datetime.fromisoformat(str(raw_ts))
                    if event_dt.tzinfo is None:
                        event_dt = event_dt.replace(tzinfo=UTC)
                    if event_dt >= before_dt:
                        kept.append(event)
                        continue
                except (ValueError, TypeError):
                    pass
            deleted += 1
        else:
            kept.append(event)

    if deleted:
        _write_jsonl(EVENTS_FILE, kept)
    return deleted


def list_events(limit: int = 50) -> list[dict[str, Any]]:
    """Read recent event entries."""
    return _read_jsonl(EVENTS_FILE, limit)


def list_alerts(limit: int = 50, active_only: bool = False) -> list[dict[str, Any]]:
    """Read recent alert entries."""
    alerts = _read_jsonl(ALERTS_FILE, limit=None)
    if active_only:
        alerts = [item for item in alerts if not item.get("resolved_at")]
    if limit is not None:
        alerts = alerts[-limit:]
    return list(reversed(alerts))


def reconcile_source_alerts(source_entries: list[dict[str, Any]]) -> None:
    """Resolve stale source alerts that no longer match current visible source state."""
    alerts = _read_jsonl(ALERTS_FILE, limit=None)
    if not alerts:
        return
    source_map = {item.get("id"): item for item in source_entries}
    changed = False
    for item in alerts:
        if item.get("source_id") is None or item.get("resolved_at"):
            continue
        source = source_map.get(item.get("source_id"))
        if source is None:
            item["resolved_at"] = _now()
            changed = True
            continue
        current_error = source.get("error")
        if not current_error:
            item["resolved_at"] = _now()
            changed = True
            continue
        if item.get("message") != current_error:
            item["resolved_at"] = _now()
            changed = True
    if changed:
        _write_jsonl(ALERTS_FILE, alerts)


def reconcile_domain_alerts(domain_projections: list[dict[str, Any]]) -> None:
    """Resolve stale domain alerts that no longer match current domain truth."""
    alerts = _read_jsonl(ALERTS_FILE, limit=None)
    if not alerts:
        return

    domain_map = {item.get("domain_id"): item for item in domain_projections}
    changed = False
    for item in alerts:
        if item.get("kind") != "domain_change" or item.get("resolved_at"):
            continue
        domain_id = item.get("domain_id")
        projection = domain_map.get(domain_id)
        if projection is None:
            item["resolved_at"] = _now()
            changed = True
            continue
        severity = _domain_severity(domain_id, projection)
        message = projection.get("summary", "")
        if severity not in {"warning", "high", "critical"}:
            item["resolved_at"] = _now()
            changed = True
            continue
        if item.get("severity") != severity or item.get("message") != message:
            item["resolved_at"] = _now()
            changed = True
    if changed:
        _write_jsonl(ALERTS_FILE, alerts)


def ack_alert(alert_id: str) -> dict[str, Any] | None:
    """Mark an alert as acknowledged."""
    alerts = _read_jsonl(ALERTS_FILE, limit=None)
    changed = False
    matched = None
    for item in alerts:
        if item.get("alert_id") == alert_id:
            item["acked_at"] = _now()
            matched = item
            changed = True
            break
    if changed:
        _write_jsonl(ALERTS_FILE, alerts)
    return matched


def emit_source_change(
    source_id: str,
    changes: list[dict[str, Any]],
    refreshed_at: str | None = None,
) -> None:
    """Emit source change event and optional alert."""
    if not changes:
        return
    event = {
        "event_id": _id("evt"),
        "kind": "source_change",
        "source_id": source_id,
        "domain_id": None,
        "severity": _source_change_severity(source_id, changes),
        "title": source_id,
        "message": f"{len(changes)} change(s) detected",
        "changes": changes,
        "created_at": refreshed_at or _now(),
    }
    _append_jsonl(EVENTS_FILE, event)
    if event["severity"] in {"warning", "high", "critical"}:
        _open_alert(
            kind="source_change",
            source_id=source_id,
            domain_id=None,
            severity=event["severity"],
            title=source_id,
            message=event["message"],
            created_at=event["created_at"],
        )


def emit_source_health(
    source_id: str,
    error: str | None,
    previous_error: str | None,
    refreshed_at: str | None = None,
) -> None:
    """Emit source health degradation or recovery events."""
    timestamp = refreshed_at or _now()
    if error and not previous_error:
        event = {
            "event_id": _id("evt"),
            "kind": "health",
            "source_id": source_id,
            "domain_id": None,
            "severity": "warning",
            "title": source_id,
            "message": error,
            "created_at": timestamp,
        }
        _append_jsonl(EVENTS_FILE, event)
        _open_alert(
            kind="health",
            source_id=source_id,
            domain_id=None,
            severity="warning",
            title=source_id,
            message=error,
            created_at=timestamp,
        )
    elif previous_error and not error:
        event = {
            "event_id": _id("evt"),
            "kind": "resolved",
            "source_id": source_id,
            "domain_id": None,
            "severity": "info",
            "title": source_id,
            "message": "Source recovered",
            "created_at": timestamp,
        }
        _append_jsonl(EVENTS_FILE, event)
        _resolve_open_alerts(source_id=source_id, domain_id=None)


def emit_domain_change(
    domain_id: str,
    projection: dict[str, Any],
    previous_projection: dict[str, Any] | None = None,
) -> None:
    """Emit domain change event and optional alert on semantic change."""
    previous_projection = previous_projection or {}
    prev_summary = previous_projection.get("summary")
    prev_state = previous_projection.get("state")
    if prev_summary == projection.get("summary") and prev_state == projection.get("state"):
        return

    severity = _domain_severity(domain_id, projection)
    timestamp = projection.get("computed_at") or _now()
    event = {
        "event_id": _id("evt"),
        "kind": "domain_change",
        "source_id": None,
        "domain_id": domain_id,
        "severity": severity,
        "title": domain_id,
        "message": projection.get("summary", ""),
        "created_at": timestamp,
    }
    _append_jsonl(EVENTS_FILE, event)
    if severity in {"warning", "high", "critical"}:
        _open_alert(
            kind="domain_change",
            source_id=None,
            domain_id=domain_id,
            severity=severity,
            title=domain_id,
            message=projection.get("summary", ""),
            created_at=timestamp,
        )
    elif previous_projection:
        _resolve_open_alerts(source_id=None, domain_id=domain_id)


def _open_alert(
    *,
    kind: str,
    source_id: str | None,
    domain_id: str | None,
    severity: str,
    title: str,
    message: str,
    created_at: str,
) -> None:
    alerts = _read_jsonl(ALERTS_FILE, limit=None)
    changed = False
    for item in reversed(alerts):
        if (
            item.get("kind") == kind
            and item.get("source_id") == source_id
            and item.get("domain_id") == domain_id
            and not item.get("resolved_at")
        ):
            if item.get("message") == message:
                return
            item["resolved_at"] = created_at
            changed = True
    if changed:
        _write_jsonl(ALERTS_FILE, alerts)
    alert = {
        "alert_id": _id("alt"),
        "kind": kind,
        "source_id": source_id,
        "domain_id": domain_id,
        "severity": severity,
        "title": title,
        "message": message,
        "created_at": created_at,
        "acked_at": None,
        "resolved_at": None,
    }
    _append_jsonl(ALERTS_FILE, alert)


def _resolve_open_alerts(source_id: str | None, domain_id: str | None) -> None:
    alerts = _read_jsonl(ALERTS_FILE, limit=None)
    changed = False
    for item in alerts:
        if (
            item.get("source_id") == source_id
            and item.get("domain_id") == domain_id
            and not item.get("resolved_at")
        ):
            item["resolved_at"] = _now()
            changed = True
    if changed:
        _write_jsonl(ALERTS_FILE, alerts)


def _source_change_severity(source_id: str, changes: list[dict[str, Any]]) -> str:
    critical_sources = {"co.runt", "co.simit", "tesla.order", "tesla.portal", "us.nhtsa_recalls"}
    if source_id in critical_sources:
        return "high"
    if len(changes) >= 3:
        return "warning"
    return "info"


def _domain_severity(domain_id: str, projection: dict[str, Any]) -> str:
    flags = projection.get("derived_flags", {})
    if domain_id == "legal":
        if flags.get("has_fines") or flags.get("has_liens"):
            return "critical"
        return "info"
    if domain_id == "delivery":
        if flags.get("delivery_scheduled"):
            return "high"
        return "info"
    if domain_id == "safety":
        if flags.get("has_investigations"):
            return "critical"
        if flags.get("has_open_recalls"):
            return "high"
        return "info"
    if domain_id == "financial":
        if flags.get("has_fines_debt"):
            return "critical"
        return "info"
    if domain_id == "source_health":
        if flags.get("has_error_sources"):
            return "high"
        if flags.get("has_stale_sources"):
            return "warning"
    return "info"


def _read_jsonl(path, limit: int | None) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    lines = path.read_text().strip().splitlines()
    if not lines or lines == [""]:
        return []
    entries = []
    selected = lines if limit is None else lines[-limit:]
    for line in selected:
        try:
            entries.append(json.loads(line))
        except Exception:
            pass
    return entries


_MAX_JSONL_ENTRIES = 10_000
_MAX_JSONL_BYTES = 5 * 1024 * 1024  # 5 MB — trigger rotation check


def _append_jsonl(path, entry: dict[str, Any]) -> None:
    EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")
    # Only check rotation when file exceeds size threshold (avoids reading on every append)
    try:
        if path.stat().st_size > _MAX_JSONL_BYTES:
            _rotate_jsonl(path)
    except OSError:
        pass


def _rotate_jsonl(path) -> None:
    """Trim file to last _MAX_JSONL_ENTRIES lines if it exceeds the limit."""
    try:
        lines = path.read_text().strip().splitlines()
        if len(lines) > _MAX_JSONL_ENTRIES:
            path.write_text("\n".join(lines[-_MAX_JSONL_ENTRIES:]) + "\n")
    except Exception:
        pass


def _write_jsonl(path, entries: list[dict[str, Any]]) -> None:
    EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    if len(entries) > _MAX_JSONL_ENTRIES:
        entries = entries[-_MAX_JSONL_ENTRIES:]
    path.write_text("".join(json.dumps(entry, default=str) + "\n" for entry in entries))


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"
