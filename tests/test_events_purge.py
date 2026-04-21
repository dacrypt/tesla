"""Unit test for delete_events() purge helper — T1.2."""

from __future__ import annotations

import pytest

import tesla_cli.core.events as events_module


@pytest.fixture(autouse=True)
def _redirect_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(events_module, "EVENTS_DIR", tmp_path / "events")
    monkeypatch.setattr(events_module, "EVENTS_FILE", tmp_path / "events" / "events.jsonl")
    monkeypatch.setattr(events_module, "ALERTS_FILE", tmp_path / "events" / "alerts.jsonl")


def _seed(events: list[dict]) -> None:
    """Write events directly to the events file."""
    import json

    events_module.EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    events_module.EVENTS_FILE.write_text(
        "".join(json.dumps(e) + "\n" for e in events)
    )


def test_purge_respects_source_prefix_and_before():
    """delete_events() must delete only events that match the prefix AND are
    strictly before the cutoff.  Events without a prefix match or after the
    cutoff must be preserved."""
    from tesla_cli.core.events import delete_events, list_events

    _seed(
        [
            {
                "event_id": "evt_001",
                "kind": "source_change",
                "source_id": "test.foo",
                "domain_id": None,
                "severity": "info",
                "title": "test.foo",
                "message": "change",
                "created_at": "2026-01-01T10:00:00+00:00",
            },
            {
                "event_id": "evt_002",
                "kind": "source_change",
                "source_id": "real.event",
                "domain_id": None,
                "severity": "info",
                "title": "real.event",
                "message": "change",
                "created_at": "2026-01-01T09:00:00+00:00",
            },
            {
                "event_id": "evt_003",
                "kind": "source_change",
                "source_id": "test.bar",
                "domain_id": None,
                "severity": "info",
                "title": "test.bar",
                "message": "old",
                "created_at": "2026-01-01T08:00:00+00:00",  # "old" — before cutoff
            },
            {
                "event_id": "evt_004",
                "kind": "source_change",
                "source_id": "test.baz",
                "domain_id": None,
                "severity": "info",
                "title": "test.baz",
                "message": "new",
                "created_at": "2026-01-01T12:00:00+00:00",  # "new" — after cutoff
            },
        ]
    )

    # Cutoff is between "old" (08:00) and "new" (12:00); test.foo (10:00) also
    # falls before the cutoff so it would be deleted IF we bound by time — but
    # we test with the cutoff set to 09:30 so only test.bar (08:00) qualifies.
    cutoff = "2026-01-01T09:30:00+00:00"

    deleted = delete_events(prefixes=["test."], before=cutoff)

    # Only test.bar should be deleted (prefix match AND before cutoff)
    assert deleted == 1

    remaining_ids = {e["event_id"] for e in list_events(limit=100)}
    assert "evt_003" not in remaining_ids, "test.bar must be deleted"
    assert "evt_001" in remaining_ids, "test.foo must remain (after cutoff)"
    assert "evt_002" in remaining_ids, "real.event must remain (no prefix match)"
    assert "evt_004" in remaining_ids, "test.baz must remain (after cutoff)"
