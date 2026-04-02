"""providers command: tesla providers status|test|capabilities.

Shows the full ecosystem provider map: what's configured, what's available,
and which provider will be selected for each capability.
"""

from __future__ import annotations

import typer

from tesla_cli.cli.output import console, is_json_mode

providers_app = typer.Typer(
    name="providers",
    help="Ecosystem provider registry — status, health, capabilities.",
)


@providers_app.command("status")
def providers_status() -> None:
    """Show all registered providers and their availability.

    tesla providers status
    tesla -j providers status
    """
    import json as _json

    from tesla_cli.core.providers import get_registry
    from tesla_cli.core.providers.base import Capability

    registry = get_registry()
    rows = registry.status()

    if is_json_mode():
        console.print(_json.dumps(rows, indent=2))
        return

    from rich.table import Table, box

    t = Table(
        title="[bold]Ecosystem Providers[/bold]",
        box=box.SIMPLE_HEAD,
        show_lines=False,
        padding=(0, 1),
    )
    t.add_column("Layer", style="dim", width=5, justify="center")
    t.add_column("Provider", width=18)
    t.add_column("Status", width=12)
    t.add_column("Capabilities", min_width=30)
    t.add_column("Description", style="dim")

    _layer_label = {0: "L0", 1: "L1", 2: "L2", 3: "L3"}
    _layer_color = {0: "magenta", 1: "cyan", 2: "blue", 3: "yellow"}

    for row in rows:
        layer_n = int(str(row.get("layer", "L1")).lstrip("L") or 1)
        col = _layer_color.get(layer_n, "white")
        layer = f"[{col}]{row['layer']}[/{col}]"
        avail = row.get("available", False)
        status = "[green]✓ available[/green]" if avail else "[dim]✗ unavailable[/dim]"
        caps = "  ".join(
            f"[{'green' if avail else 'dim'}]{c.split('.', 1)[-1]}[/{'green' if avail else 'dim'}]"
            for c in sorted(row.get("capabilities", []))
        )
        t.add_row(layer, f"[bold]{row['name']}[/bold]", status, caps, row.get("description", ""))

    console.print()
    console.print(t)

    # Capability routing summary
    cap_map = registry.capability_map()
    console.print()
    console.print(
        "  [bold]Capability routing[/bold] [dim](→ highest-priority available provider)[/dim]\n"
    )

    all_caps = Capability.all()
    for cap in sorted(all_caps):
        try:
            best = registry.get(cap)
            console.print(f"  [dim]{cap:<26}[/dim]  [green]→ {best.name}[/green]")
        except Exception:  # noqa: BLE001
            providers_for_cap = cap_map.get(cap, [])
            if providers_for_cap:
                console.print(
                    f"  [dim]{cap:<26}[/dim]  [yellow]→ configured ({', '.join(providers_for_cap)}) but unavailable[/yellow]"
                )
            else:
                console.print(f"  [dim]{cap:<26}[/dim]  [red]→ no provider[/red]")
    console.print()


@providers_app.command("test")
def providers_test() -> None:
    """Run a full health check on all providers (makes network calls).

    tesla providers test
    tesla -j providers test
    """
    import json as _json

    from rich.progress import Progress, SpinnerColumn, TextColumn

    from tesla_cli.core.providers import get_registry

    registry = get_registry()
    all_providers = registry.all()

    results: list[dict] = []

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as p:
        task = p.add_task(f"Testing {len(all_providers)} providers...", total=len(all_providers))
        for provider in all_providers:
            p.update(task, description=f"Testing {provider.name}…")
            h = provider.health_check()
            h["provider"] = provider.name
            h["layer"] = f"L{provider.layer}"
            results.append(h)
            p.advance(task)

    if is_json_mode():
        console.print(_json.dumps(results, indent=2))
        return

    from rich.table import Table, box

    t = Table(box=box.SIMPLE_HEAD, padding=(0, 1))
    t.add_column("Layer", style="dim", width=5, justify="center")
    t.add_column("Provider", width=18)
    t.add_column("Status", width=14)
    t.add_column("Latency", width=10, justify="right")
    t.add_column("Detail", style="dim")

    for h in results:
        status = h.get("status", "?")
        color = "green" if status == "ok" else ("yellow" if status == "degraded" else "red")
        ms = h.get("latency_ms", 0)
        t.add_row(
            h.get("layer", "?"),
            f"[bold]{h['provider']}[/bold]",
            f"[{color}]{status}[/{color}]",
            f"{ms:.0f} ms" if ms else "—",
            h.get("detail", ""),
        )

    console.print()
    console.print(t)
    console.print()


@providers_app.command("capabilities")
def providers_capabilities() -> None:
    """Show the full capability map — which providers serve what.

    tesla providers capabilities
    tesla -j providers capabilities
    """
    import json as _json

    from tesla_cli.core.providers import get_registry
    from tesla_cli.core.providers.base import Capability

    registry = get_registry()

    if is_json_mode():
        out = {}
        for cap in sorted(Capability.all()):
            available = [p.name for p in registry.for_capability(cap)]
            all_p = [p.name for p in registry.for_capability(cap, available_only=False)]
            out[cap] = {"available": available, "all": all_p}
        console.print(_json.dumps(out, indent=2))
        return

    from rich.table import Table, box

    t = Table(
        title="[bold]Capability Map[/bold]",
        box=box.SIMPLE_HEAD,
        padding=(0, 1),
    )
    t.add_column("Capability", width=26)
    t.add_column("Available Providers", min_width=30)
    t.add_column("All Configured", style="dim")

    for cap in sorted(Capability.all()):
        available = registry.for_capability(cap, available_only=True)
        all_p = registry.for_capability(cap, available_only=False)
        avail_str = "  ".join(f"[green]{p.name}[/green]" for p in available) or "[dim]none[/dim]"
        all_str = ", ".join(p.name for p in all_p) or "—"
        t.add_row(f"[dim]{cap}[/dim]", avail_str, all_str)

    console.print()
    console.print(t)
    console.print()
