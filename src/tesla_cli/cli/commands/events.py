"""tesla events — manage the local events store."""

from __future__ import annotations

from typing import Annotated

import typer

from tesla_cli.cli.output import console

events_app = typer.Typer(
    name="events",
    help="Manage the local events store.",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

_DEFAULT_PREFIXES = ["test."]


@events_app.command("list")
def list_cmd(
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum events to show"),
) -> None:
    """Show recent source/domain events."""
    from tesla_cli.cli.commands.event_stream_cmd import events_command

    events_command(limit=limit)


@events_app.command("purge")
def purge_cmd(
    source_prefix: Annotated[
        list[str] | None,
        typer.Option("--source-prefix", help="Delete events whose source_id or domain_id starts with this prefix (repeatable)."),
    ] = None,
    before: Annotated[
        str | None,
        typer.Option("--before", help="Only delete events created before this ISO timestamp."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run/--no-dry-run", help="Preview without deleting."),
    ] = False,
) -> None:
    """Purge events from the local store matching prefix and/or time filters."""
    from tesla_cli.core.events import delete_events

    prefixes = source_prefix if source_prefix else _DEFAULT_PREFIXES

    if dry_run:
        # For dry-run: count without deleting by reading matching events
        from datetime import UTC, datetime

        from tesla_cli.core.events import (
            EVENTS_FILE,
            _read_jsonl,  # noqa: PLC2701
        )

        all_events = _read_jsonl(EVENTS_FILE, limit=None)
        before_dt = None
        if before:
            before_dt = datetime.fromisoformat(before)
            if before_dt.tzinfo is None:
                before_dt = before_dt.replace(tzinfo=UTC)

        count = 0
        for event in all_events:
            source = event.get("source_id") or ""
            domain = event.get("domain_id") or ""
            prefix_match = any(source.startswith(p) or domain.startswith(p) for p in prefixes)
            if prefix_match:
                if before_dt is not None:
                    raw_ts = event.get("created_at", "")
                    try:
                        event_dt = datetime.fromisoformat(str(raw_ts))
                        if event_dt.tzinfo is None:
                            event_dt = event_dt.replace(tzinfo=UTC)
                        if event_dt >= before_dt:
                            continue
                    except (ValueError, TypeError):
                        pass
                count += 1

        console.print(f"Deleted {count} events.")
        return

    count = delete_events(prefixes=prefixes, before=before)
    console.print(f"Deleted {count} events.")


def run_v491_purge_migration() -> int:
    """Run v4.9.1 migration: purge test. prefixed events with no time bound.

    Returns the number of deleted events.  Does not print anything.
    """
    from tesla_cli.core.events import delete_events

    return delete_events(prefixes=_DEFAULT_PREFIXES, before=None)
