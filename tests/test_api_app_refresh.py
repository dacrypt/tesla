"""Tests for API background source refresh behavior."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from tesla_cli.api.app import _refresh_stale_sources_once
from tesla_cli.core.sources import SourceDef


def test_refresh_stale_sources_once_refreshes_and_broadcasts():
    hub = MagicMock()
    hub_ref = [hub]

    with (
        patch("tesla_cli.core.sources._SOURCES", {"tesla.order": object(), "co.runt": object()}),
        patch("tesla_cli.core.sources._is_stale", side_effect=lambda sid: sid == "tesla.order"),
        patch("tesla_cli.core.sources.refresh_source", return_value={"data": {"vin": "VIN123"}, "error": None}),
        patch("tesla_cli.core.sources.get_cached", return_value={"vin": "VIN123"}),
    ):
        refreshed, failed = _refresh_stale_sources_once(hub_ref)

    assert refreshed == ["tesla.order"]
    assert failed == []
    hub.broadcast_source.assert_called_once_with("tesla.order", {"vin": "VIN123"})


def test_refresh_stale_sources_once_collects_failures():
    with (
        patch("tesla_cli.core.sources._SOURCES", {"co.runt": object()}),
        patch("tesla_cli.core.sources._is_stale", return_value=True),
        patch("tesla_cli.core.sources.refresh_source", return_value={"error": "boom"}),
    ):
        refreshed, failed = _refresh_stale_sources_once([None])

    assert refreshed == []
    assert failed == [{"id": "co.runt", "error": "boom"}]


def test_refresh_stale_sources_once_skips_manual_sources():
    manual = SourceDef(id="co.manual", name="Manual", category="servicios", auto_refresh=False)
    auto = SourceDef(id="co.auto", name="Auto", category="servicios")

    with (
        patch("tesla_cli.core.sources._SOURCES", {"co.manual": manual, "co.auto": auto}),
        patch("tesla_cli.core.sources._is_stale", return_value=True),
        patch("tesla_cli.core.sources.refresh_source", return_value={"data": {"ok": True}, "error": None}) as refresh,
        patch("tesla_cli.core.sources.get_cached", return_value={"ok": True}),
    ):
        refreshed, failed = _refresh_stale_sources_once([None])

    assert refreshed == ["co.auto"]
    assert failed == []
    refresh.assert_called_once_with("co.auto")
