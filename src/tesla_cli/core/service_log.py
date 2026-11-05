"""Maintenance items, a log of completed services, and due-date reminders.

Reminders used to be computed from the odometer alone (API) or from dates
passed on every run (CLI), so "overdue" could never be known: nothing recorded
when a service was actually done. This module keeps that record in
``~/.tesla-cli/service_log.json`` and derives due dates from the last logged
service of each item — by distance, by time, or whichever comes first.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

DUE_SOON_KM = 2_000
DUE_SOON_DAYS = 30


@dataclass(frozen=True)
class MaintenanceItem:
    id: str
    name: str
    description: str
    interval_km: int | None = None
    interval_days: int | None = None


ITEMS: tuple[MaintenanceItem, ...] = (
    # ids are part of the REST API (/api/service/reminders) — keep them stable.
    MaintenanceItem("tires", "Tire Rotation", "Rotate tires every 10,000 km", interval_km=10_000),
    MaintenanceItem(
        "cabin_air",
        "Cabin Air Filter",
        "Replace cabin air filter every 2 years / 24,000 km",
        interval_km=24_000,
        interval_days=730,
    ),
    MaintenanceItem(
        "brake_fluid",
        "Brake Fluid Test",
        "Test brake fluid every 4 years / 40,000 km",
        interval_km=40_000,
        interval_days=1460,
    ),
    MaintenanceItem(
        "hepa_filter",
        "HEPA Filter",
        "Replace HEPA filter every 3 years / 48,000 km",
        interval_km=48_000,
        interval_days=1095,
    ),
    MaintenanceItem(
        "ac_desiccant",
        "A/C Desiccant Bag",
        "Replace A/C desiccant bag every 6 years / 96,000 km",
        interval_km=96_000,
        interval_days=2190,
    ),
)
_BY_ID = {i.id: i for i in ITEMS}


def item(item_id: str) -> MaintenanceItem:
    try:
        return _BY_ID[item_id]
    except KeyError:
        valid = ", ".join(_BY_ID)
        raise ValueError(f"Unknown maintenance item {item_id!r}. Valid: {valid}") from None


def log_path() -> Path:
    from tesla_cli.core import config as _config

    return Path(_config.CONFIG_DIR) / "service_log.json"


def load_log() -> list[dict[str, Any]]:
    path = log_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return []
    return data if isinstance(data, list) else []


def record(
    item_id: str, *, km: float | None = None, on: date | None = None, note: str = ""
) -> dict[str, Any]:
    """Log that *item_id* was serviced at *km* on *on* (default: today)."""
    item(item_id)  # validates
    entry: dict[str, Any] = {"item": item_id, "date": (on or date.today()).isoformat()}
    if km is not None:
        if km < 0:
            raise ValueError("km must be >= 0")
        entry["km"] = round(float(km))
    if note:
        entry["note"] = note[:200]
    entries = load_log() + [entry]
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2))
    return entry


def last_service(item_id: str, entries: list[dict[str, Any]] | None = None) -> dict | None:
    """Most recent log entry for *item_id* (by date, then km)."""
    rows = [e for e in (entries if entries is not None else load_log()) if e.get("item") == item_id]
    if not rows:
        return None
    return max(rows, key=lambda e: (e.get("date", ""), e.get("km", -1)))


def reminders(
    odometer_km: float | None,
    *,
    today: date | None = None,
    entries: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """One row per maintenance item with next due km/date and overdue flags.

    ``basis`` is ``"logged"`` when a completed service is on record, else
    ``"estimated"`` (next multiple of the interval; overdue cannot be known).
    """
    today = today or date.today()
    entries = entries if entries is not None else load_log()
    odo = round(odometer_km) if odometer_km else 0  # 0 = unknown (car asleep)
    rows = []
    for it in ITEMS:
        last = last_service(it.id, entries)
        row: dict[str, Any] = {
            "id": it.id,
            "name": it.name,
            "description": it.description,
            "interval_km": it.interval_km,
            "interval_days": it.interval_days,
            "current_odometer_km": odo,
            "last_service": last,
            "basis": "logged" if last else "estimated",
            "next_service_km": None,
            "km_until_service": None,
            "next_service_date": None,
            "days_until_service": None,
        }
        if it.interval_km:
            if last and last.get("km") is not None:
                next_km = last["km"] + it.interval_km
            elif odo:
                next_km = (odo // it.interval_km + 1) * it.interval_km
            else:
                next_km = it.interval_km
            row["next_service_km"] = next_km
            row["km_until_service"] = next_km - odo
        if it.interval_days and last and last.get("date"):
            due = date.fromisoformat(last["date"]) + timedelta(days=it.interval_days)
            row["next_service_date"] = due.isoformat()
            row["days_until_service"] = (due - today).days

        km_left, days_left = row["km_until_service"], row["days_until_service"]
        logged = last is not None
        row["overdue"] = logged and (
            (km_left is not None and km_left <= 0) or (days_left is not None and days_left <= 0)
        )
        row["due_soon"] = (km_left is not None and km_left <= DUE_SOON_KM) or (
            days_left is not None and days_left <= DUE_SOON_DAYS
        )
        if it.interval_km and odo and km_left is not None:
            done = it.interval_km - km_left
            row["progress_pct"] = max(0, min(100, round(done / it.interval_km * 100)))
        else:
            row["progress_pct"] = 0
        rows.append(row)
    return rows
