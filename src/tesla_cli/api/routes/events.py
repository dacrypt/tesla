"""Event stream API."""

from __future__ import annotations

from fastapi import APIRouter

from tesla_cli.core import events

router = APIRouter()


def _is_test_event(e: dict) -> bool:
    """Fixtures from the test suite use source_id/domain_id prefixed with 'test.'.
    They occasionally leak into the real events store when tests run against
    the user's actual data dir. Filter them out at read time so the UI stays clean."""
    for key in ("source_id", "domain_id", "kind"):
        val = e.get(key) or ""
        if isinstance(val, str) and val.startswith("test."):
            return True
    return False


@router.get("")
def events_list(limit: int = 50, include_test: bool = False) -> list:
    """List recent events.

    Test-fixture events (source_id prefixed with `test.`) are filtered out by
    default; pass `?include_test=true` to see them.
    """
    limit = min(limit, 500)
    # Over-fetch so we still return `limit` real events after filtering.
    raw = events.list_events(limit=limit * 3 if not include_test else limit)
    if include_test:
        return raw[:limit]
    return [e for e in raw if not _is_test_event(e)][:limit]
