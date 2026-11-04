"""Experimental features — built on unofficial or fragile upstreams.

These features work today but depend on interfaces nobody promises to keep:
undocumented Tesla endpoints, scraped web pages, CAPTCHA-protected government
sites, or an uncalibrated model. They are labelled in CLI help, reported by
``tesla doctor`` / ``GET /api/experimental``, and when one of their data
sources starts failing the resulting alert says so (see core/events.py).

Status is computed offline from the last cached result of each source:
``ok`` · ``failing`` (last refresh errored) · ``unused`` (never refreshed) ·
``not-installed`` (optional dependency missing).
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass


@dataclass(frozen=True)
class ExperimentalFeature:
    id: str
    title: str
    risk: str  # why it can break
    sources: tuple[str, ...] = ()  # source ids in core/sources.py
    requires_module: str | None = None  # optional dependency
    install_hint: str | None = None


FEATURES: tuple[ExperimentalFeature, ...] = (
    ExperimentalFeature(
        id="order_tracking",
        title="Order tracking",
        risk="Uses undocumented Tesla owner-api and order-tasks endpoints that can "
        "change or disappear without notice.",
        sources=("tesla.order", "tesla.tasks", "tesla.delivery"),
    ),
    ExperimentalFeature(
        id="ownership_portal",
        title="Ownership-portal scraping",
        risk="Logs into tesla.com in a headless browser and parses page data; "
        "any redesign of the portal breaks it.",
        sources=("tesla.portal",),
    ),
    ExperimentalFeature(
        id="co_registries",
        title="Colombian registries (RUNT, SIMIT, …)",
        risk="Scrapes government websites that use CAPTCHAs and change markup without notice.",
        sources=("co.runt", "co.simit"),
        requires_module="openquery",
        install_hint="pip install 'tesla-cli[query]'",
    ),
    ExperimentalFeature(
        id="ev_planner_model",
        title="EV route planner consumption model",
        risk="Ships with baseline coefficients; predictions are approximate until "
        "calibrated with `tesla nav consumption calibrate`.",
    ),
)

_BY_SOURCE = {src: f for f in FEATURES for src in f.sources}


def feature_for_source(source_id: str) -> ExperimentalFeature | None:
    """The experimental feature a data source belongs to, if any."""
    return _BY_SOURCE.get(source_id)


def _source_meta(source_id: str) -> dict | None:
    try:
        from tesla_cli.core.sources import get_cached_with_meta

        return get_cached_with_meta(source_id)
    except Exception:  # noqa: BLE001 — status must never crash doctor
        return None


def status(feature: ExperimentalFeature) -> dict:
    """JSON-serializable status row for *feature* (offline, no network)."""
    row: dict = {"id": feature.id, "title": feature.title, "risk": feature.risk}
    if feature.requires_module and importlib.util.find_spec(feature.requires_module) is None:
        row["status"] = "not-installed"
        if feature.install_hint:
            row["remediation"] = feature.install_hint
        return row
    metas = [m for m in (_source_meta(s) for s in feature.sources) if m]
    failing = [m for m in metas if m.get("error")]
    if failing:
        row["status"] = "failing"
        row["error"] = f"{failing[0]['id']}: {failing[0]['error']}"[:300]
        row["remediation"] = (
            "Upstream may have changed. Retry later, check for a tesla-cli update, "
            "or run with --debug and report it."
        )
    elif feature.sources and not any(m.get("refreshed_at") for m in metas):
        row["status"] = "unused"
    else:
        row["status"] = "ok"
    return row


def status_all() -> list[dict]:
    return [status(f) for f in FEATURES]
