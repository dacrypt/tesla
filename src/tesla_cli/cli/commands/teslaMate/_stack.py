"""``teslaMate`` commands — stack (see ``__init__.py``).

Names tests patch on ``tesla_cli.cli.commands.teslaMate`` are looked up as ``_m.<name>``.
"""

from __future__ import annotations

from tesla_cli.cli.commands import teslaMate as _m
from tesla_cli.cli.commands.teslaMate import (  # noqa: F401
    Progress,
    SpinnerColumn,
    Table,
    TextColumn,
    console,
    i18n_t,
    is_json_mode,
    json,
    render_success,
    save_config,
    teslaMate_app,
    typer,
)
from tesla_cli.cli.commands.teslaMate._analytics import (  # noqa: F401
    _kv,
)


@teslaMate_app.command("connect")
def teslaMate_connect(
    database_url: str = typer.Argument(
        ..., help="PostgreSQL URL: postgresql://user:pass@host:5432/teslaMate"
    ),
    car_id: int = typer.Option(1, "--car-id", "-c", help="TeslaMate car ID (1-based, default 1)"),
) -> None:
    """Configure and test a TeslaMate database connection.

    tesla teslaMate connect postgresql://user:pass@localhost:5432/teslaMate
    tesla teslaMate connect postgresql://user:pass@myserver/teslaMate --car-id 2
    """
    cfg = _m.load_config()
    cfg.teslaMate.database_url = database_url
    cfg.teslaMate.car_id = car_id

    # Test connection
    from tesla_cli.core.backends.teslaMate import TeslaMateBacked

    backend = TeslaMateBacked(database_url, car_id=car_id)

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as p:
        p.add_task("Testing connection...", total=None)
        try:
            ok = backend.ping()
            cars = backend.get_cars() if ok else []
        except Exception as exc:
            console.print(f"[red]Connection failed:[/red] {exc}")
            raise typer.Exit(1)

    if not ok:
        console.print("[red]Connection failed[/red] — ping returned False")
        raise typer.Exit(1)

    save_config(cfg)
    render_success(f"Connected to TeslaMate ({database_url})")

    if cars:
        console.print("\n  [dim]Cars in DB:[/dim]")
        for car in cars:
            active = " ← [bold cyan](selected)[/bold cyan]" if car["id"] == car_id else ""
            console.print(
                f"    [{car['id']}] {car.get('name') or '(unnamed)'} — {car.get('vin', '?')}{active}"
            )


@teslaMate_app.command("status")
def teslaMate_status(
    oneline: bool = typer.Option(False, "--oneline", "-1", help="Single-line output"),
) -> None:
    """Show TeslaMate connection status and lifetime stats."""
    backend = _m._backend()

    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        transient=True,
        disable=is_json_mode() or oneline,
    ) as p:
        p.add_task("Fetching stats...", total=None)
        ok = backend.ping()
        drive_stats = backend.get_stats() if ok else {}
        charge_stats = backend.get_charging_stats() if ok else {}
        cars = backend.get_cars() if ok else []

    cfg = _m.load_config()

    # Managed stack info
    stack_info: dict = {}
    if cfg.teslaMate.managed:
        from pathlib import Path

        from tesla_cli.infra.teslamate_stack import TeslaMateStack

        stack = TeslaMateStack(Path(cfg.teslaMate.stack_dir) if cfg.teslaMate.stack_dir else None)
        stack_info = {
            "managed": True,
            "installed": stack.is_installed(),
            "services": stack.status(),
        }

    status_data = {
        "connected": ok,
        "database_url": cfg.teslaMate.database_url.split("@")[-1]
        if "@" in cfg.teslaMate.database_url
        else cfg.teslaMate.database_url,
        "car_id": cfg.teslaMate.car_id,
        "total_drives": drive_stats.get("total_drives", 0),
        "total_km": str(drive_stats.get("total_km", 0)),
        "total_kwh_driven": str(drive_stats.get("total_kwh", 0)),
        "first_drive": str(drive_stats.get("first_drive", ""))[:19],
        "last_drive": str(drive_stats.get("last_drive", ""))[:19],
        "total_charging_sessions": charge_stats.get("total_sessions", 0),
        "total_kwh_charged": str(charge_stats.get("total_kwh_added", 0)),
        "total_charging_cost": f"${charge_stats.get('total_cost', 0):.2f}",
    }
    if stack_info:
        status_data["stack"] = stack_info

    if is_json_mode():
        console.print_json(json.dumps(status_data, indent=2, default=str))
        return

    if oneline:
        connected = "✅ Connected" if ok else "❌ Disconnected"
        total_km = drive_stats.get("total_km", 0)
        charges = charge_stats.get("total_sessions", 0)
        parts = [connected, f"🚗 {total_km:,} km", f"⚡ {charges} charges"]
        console.print(" | ".join(parts))
        return

    from rich.panel import Panel

    status_icon = "[green]Connected[/green]" if ok else "[red]Not connected[/red]"
    mode_label = "[cyan]managed[/cyan]" if cfg.teslaMate.managed else "[dim]external[/dim]"
    console.print()
    console.print(
        Panel(
            f"{status_icon}  |  Mode: {mode_label}  |  DB: [dim]{status_data['database_url']}[/dim]  |  Car ID: [cyan]{cfg.teslaMate.car_id}[/cyan]",
            title="[bold]TeslaMate Integration[/bold]",
            border_style="cyan",
        )
    )

    # Show managed stack container status
    if stack_info and stack_info.get("services"):
        console.print("\n[bold]Docker Stack[/bold]")
        st = Table(show_header=True, box=None, padding=(0, 2))
        st.add_column("Service", style="bold")
        st.add_column("State")
        st.add_column("Image", style="dim")
        st.add_column("Status")
        for svc in stack_info["services"]:
            state = svc.get("state", "unknown")
            state_styled = (
                f"[green]{state}[/green]" if state == "running" else f"[red]{state}[/red]"
            )
            st.add_row(svc["name"], state_styled, svc.get("image", ""), svc.get("status", ""))
        console.print(st)

    if ok:
        console.print("\n[bold]Driving[/bold]")
        _kv(
            [
                ("Total trips", str(drive_stats.get("total_drives", 0))),
                ("Total distance", f"{drive_stats.get('total_km', 0)} km"),
                ("Total energy", f"{drive_stats.get('total_kwh', 0)} kWh"),
                ("Avg per trip", f"{drive_stats.get('avg_km_per_trip', 0)} km"),
                ("Longest trip", f"{drive_stats.get('longest_trip_km', 0)} km"),
                ("First drive", str(drive_stats.get("first_drive", ""))[:19]),
                ("Last drive", str(drive_stats.get("last_drive", ""))[:19]),
            ]
        )
        console.print("\n[bold]Charging[/bold]")
        _kv(
            [
                ("Total sessions", str(charge_stats.get("total_sessions", 0))),
                ("Total energy added", f"{charge_stats.get('total_kwh_added', 0)} kWh"),
                ("Total cost", f"${charge_stats.get('total_cost', 0):.2f}"),
                ("Avg per session", f"{charge_stats.get('avg_kwh_per_session', 0)} kWh"),
            ]
        )

    if cars:
        console.print("\n[bold]Cars in DB[/bold]")
        for car in cars:
            active = (
                " <- [bold cyan]active[/bold cyan]" if car["id"] == cfg.teslaMate.car_id else ""
            )
            console.print(
                f"  [{car['id']}] {car.get('name') or '(unnamed)'}  VIN: [dim]{car.get('vin', '?')}[/dim]{active}"
            )


# ── Grafana ──────────────────────────────────────────────────────────────────

_GRAFANA_DASHBOARDS: dict[str, str] = {
    "overview": "/d/overview/overview",
    "trips": "/d/ZihFSXoZk/trips",
    "charges": "/d/7Cp9k_7Zz/charges",
    "battery": "/d/pf6xQMd7k/battery",
    "efficiency": "/d/5k7CaGFZz/efficiency",
    "locations": "/d/GhFG_aS7k/locations",
    "vampire": "/d/g_EIOX5Zz/vampire-drain",
    "updates": "/d/f4V4XRhZz/updates",
}

_GRAFANA_NAMES = ", ".join(_GRAFANA_DASHBOARDS.keys())


@teslaMate_app.command("grafana")
def teslaMate_grafana(
    dashboard: str = typer.Argument("overview", help=f"Dashboard: {_GRAFANA_NAMES}"),
) -> None:
    """Open a TeslaMate Grafana dashboard in your browser.

    tesla teslaMate grafana
    tesla teslaMate grafana trips
    tesla teslaMate grafana charges
    tesla -j teslaMate grafana battery
    """
    import json as _json
    import webbrowser

    cfg = _m.load_config()
    base = (cfg.grafana.url or "http://localhost:3000").rstrip("/")

    key = dashboard.lower()
    if key not in _GRAFANA_DASHBOARDS:
        console.print(
            f"[red]Unknown dashboard:[/red] {dashboard}\n[dim]Available:[/dim] {_GRAFANA_NAMES}"
        )
        raise typer.Exit(1)

    url = base + _GRAFANA_DASHBOARDS[key]

    if is_json_mode():
        console.print(_json.dumps({"dashboard": key, "url": url}))
        return

    console.print(f"Opening [bold cyan]{key}[/bold cyan] dashboard…  [dim]{url}[/dim]")
    webbrowser.open(url)


# ── managed stack lifecycle ──


@teslaMate_app.command("sync-tokens")
def teslaMate_sync_tokens() -> None:
    """Sync Tesla API tokens from keyring to TeslaMate.

    Injects the current Fleet API tokens into TeslaMate's database so it can
    start collecting vehicle data without manual sign-in.

    tesla teslaMate sync-tokens
    """
    cfg = _m.load_config()
    if not cfg.teslaMate.managed:
        console.print("[yellow]TeslaMate is not managed by CLI.[/yellow]")
        raise typer.Exit(1)

    from pathlib import Path

    from tesla_cli.infra.teslamate_stack import TeslaMateStack

    stack = TeslaMateStack(Path(cfg.teslaMate.stack_dir) if cfg.teslaMate.stack_dir else None)
    if not stack.is_running():
        console.print(
            "[yellow]TeslaMate stack is not running.[/yellow] Start with: tesla teslaMate start"
        )
        raise typer.Exit(1)

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as p:
        p.add_task("Syncing tokens...", total=None)
        ok = stack.sync_tokens_from_keyring()

    if ok:
        render_success("Tokens synced to TeslaMate. It should start collecting data shortly.")
    else:
        console.print(
            "[red]Token sync failed.[/red] Make sure you have valid Fleet API tokens (tesla config auth fleet)."
        )
        raise typer.Exit(1)


@teslaMate_app.command("install")
def teslaMate_install(
    postgres_port: int = typer.Option(5432, "--postgres-port", help="PostgreSQL port"),
    grafana_port: int = typer.Option(3000, "--grafana-port", help="Grafana port"),
    teslamate_port: int = typer.Option(4000, "--teslamate-port", help="TeslaMate web UI port"),
    mqtt_port: int = typer.Option(1883, "--mqtt-port", help="Mosquitto MQTT port"),
    timezone: str = typer.Option("America/Bogota", "--tz", help="Timezone for TeslaMate"),
    force: bool = typer.Option(False, "--force", help="Reinstall even if already installed"),
) -> None:
    """Install and start a fully managed TeslaMate stack (Docker Compose).

    Sets up PostgreSQL, TeslaMate, Grafana, and Mosquitto. Credentials are
    generated automatically and stored in the system keyring.

    tesla teslaMate install
    tesla teslaMate install --grafana-port 3001 --tz America/New_York
    """
    from tesla_cli.core.exceptions import DockerNotFoundError, TeslaMateStackError
    from tesla_cli.infra.teslamate_stack import TeslaMateStack

    stack = TeslaMateStack()

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as p:
        task = p.add_task("Checking Docker...", total=None)

        # Port conflict check
        conflicts = stack.check_ports(postgres_port, grafana_port, teslamate_port, mqtt_port)
        if conflicts:
            names = ", ".join(f"{n} (:{p})" for n, p in conflicts)
            console.print(f"[red]Port conflict:[/red] {names} already in use.")
            console.print(
                "[dim]Use --postgres-port, --grafana-port, etc. to pick different ports.[/dim]"
            )
            raise typer.Exit(1)

        p.update(task, description="Installing TeslaMate stack...")
        try:
            result = stack.install(
                postgres_port=postgres_port,
                grafana_port=grafana_port,
                teslamate_port=teslamate_port,
                mqtt_port=mqtt_port,
                timezone=timezone,
                force=force,
            )
        except (DockerNotFoundError, TeslaMateStackError) as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)

    # Auto-configure tesla-cli
    cfg = _m.load_config()
    cfg.teslaMate.database_url = result["database_url"]
    cfg.teslaMate.managed = True
    cfg.teslaMate.stack_dir = result["stack_dir"]
    cfg.teslaMate.postgres_port = result["postgres_port"]
    cfg.teslaMate.grafana_port = result["grafana_port"]
    cfg.teslaMate.teslamate_port = result["teslamate_port"]
    cfg.teslaMate.mqtt_port = result["mqtt_port"]
    cfg.grafana.url = f"http://localhost:{result['grafana_port']}"
    cfg.mqtt.broker = "localhost"
    cfg.mqtt.port = result["mqtt_port"]
    save_config(cfg)

    health_icon = "[green]healthy[/green]" if result["healthy"] else "[yellow]starting...[/yellow]"
    render_success("TeslaMate stack installed and running")
    console.print(f"\n  Stack health: {health_icon}")
    console.print(f"  TeslaMate UI: [link]http://localhost:{teslamate_port}[/link]")
    console.print(
        f"  Grafana:      [link]http://localhost:{grafana_port}[/link]  (admin / {result['grafana_password']})"
    )
    console.print(f"  PostgreSQL:   localhost:{postgres_port}")
    console.print(f"  MQTT:         localhost:{mqtt_port}")

    # Auto-sync tokens from keyring → TeslaMate
    import time as _t

    _t.sleep(5)  # Wait for TeslaMate to be ready
    if stack.sync_tokens_from_keyring():
        console.print("\n  [green]Tesla tokens synced automatically.[/green]")
    elif not result["has_tesla_tokens"]:
        console.print("\n[yellow]No Tesla tokens found.[/yellow] Run: tesla config auth fleet")
    console.print()


@teslaMate_app.command("start")
def teslaMate_start() -> None:
    """Start the managed TeslaMate stack.

    tesla teslaMate start
    """
    cfg = _m.load_config()
    if not cfg.teslaMate.managed:
        console.print("[yellow]TeslaMate is configured as external (not managed by CLI).[/yellow]")
        console.print("Run [bold]tesla teslaMate install[/bold] to set up a managed stack.")
        raise typer.Exit(1)

    from pathlib import Path

    from tesla_cli.core.exceptions import TeslaMateStackError
    from tesla_cli.infra.teslamate_stack import TeslaMateStack

    stack = TeslaMateStack(Path(cfg.teslaMate.stack_dir) if cfg.teslaMate.stack_dir else None)

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as p:
        p.add_task("Starting TeslaMate stack...", total=None)
        try:
            stack.start()
        except TeslaMateStackError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)

    render_success("TeslaMate stack started")

    # Auto-sync tokens
    import time as _t

    _t.sleep(5)
    if stack.sync_tokens_from_keyring():
        console.print("  [green]Tokens synced.[/green]")


@teslaMate_app.command("stop")
def teslaMate_stop() -> None:
    """Stop the managed TeslaMate stack.

    tesla teslaMate stop
    """
    cfg = _m.load_config()
    if not cfg.teslaMate.managed:
        console.print("[yellow]TeslaMate is configured as external (not managed by CLI).[/yellow]")
        raise typer.Exit(1)

    from pathlib import Path

    from tesla_cli.infra.teslamate_stack import TeslaMateStack

    stack = TeslaMateStack(Path(cfg.teslaMate.stack_dir) if cfg.teslaMate.stack_dir else None)
    stack.stop()
    render_success("TeslaMate stack stopped")


@teslaMate_app.command("restart")
def teslaMate_restart() -> None:
    """Restart the managed TeslaMate stack.

    tesla teslaMate restart
    """
    cfg = _m.load_config()
    if not cfg.teslaMate.managed:
        console.print("[yellow]TeslaMate is configured as external (not managed by CLI).[/yellow]")
        raise typer.Exit(1)

    from pathlib import Path

    from tesla_cli.core.exceptions import TeslaMateStackError
    from tesla_cli.infra.teslamate_stack import TeslaMateStack

    stack = TeslaMateStack(Path(cfg.teslaMate.stack_dir) if cfg.teslaMate.stack_dir else None)

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as p:
        p.add_task("Restarting TeslaMate stack...", total=None)
        try:
            stack.restart()
        except TeslaMateStackError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)

    render_success("TeslaMate stack restarted")


@teslaMate_app.command("update")
def teslaMate_update() -> None:
    """Pull latest Docker images and recreate containers.

    tesla teslaMate update
    """
    cfg = _m.load_config()
    if not cfg.teslaMate.managed:
        console.print("[yellow]TeslaMate is configured as external (not managed by CLI).[/yellow]")
        raise typer.Exit(1)

    from pathlib import Path

    from tesla_cli.infra.teslamate_stack import TeslaMateStack

    stack = TeslaMateStack(Path(cfg.teslaMate.stack_dir) if cfg.teslaMate.stack_dir else None)

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as p:
        p.add_task("Pulling latest images & restarting...", total=None)
        output = stack.update()

    render_success("TeslaMate stack updated")
    if output:
        for line in output.strip().splitlines()[-5:]:
            console.print(f"  [dim]{line}[/dim]")


@teslaMate_app.command("logs")
def teslaMate_logs(
    service: str | None = typer.Option(
        None, "--service", "-s", help="Service: teslamate, postgres, grafana, mosquitto"
    ),
    lines: int = typer.Option(100, "--lines", "-n", help="Number of log lines"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
) -> None:
    """Show logs from the managed TeslaMate stack.

    tesla teslaMate logs
    tesla teslaMate logs --service teslamate --lines 50
    tesla teslaMate logs -f
    """
    cfg = _m.load_config()
    if not cfg.teslaMate.managed:
        console.print("[yellow]TeslaMate is configured as external (not managed by CLI).[/yellow]")
        raise typer.Exit(1)

    from pathlib import Path

    from tesla_cli.core.exceptions import TeslaMateStackError
    from tesla_cli.infra.teslamate_stack import TeslaMateStack

    stack = TeslaMateStack(Path(cfg.teslaMate.stack_dir) if cfg.teslaMate.stack_dir else None)

    try:
        result = stack.logs(service=service, lines=lines, follow=follow)
        if follow:
            # Streaming mode — forward output until Ctrl+C
            try:
                for line in result.stdout:  # type: ignore[union-attr]
                    console.print(line, end="", highlight=False)
            except KeyboardInterrupt:
                result.terminate()  # type: ignore[union-attr]
        else:
            if result.stdout:  # type: ignore[union-attr]
                console.print(result.stdout, highlight=False)  # type: ignore[union-attr]
    except TeslaMateStackError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)


@teslaMate_app.command("uninstall")
def teslaMate_uninstall(
    remove_data: bool = typer.Option(
        False, "--remove-data", help="Also remove database volumes (destructive)"
    ),
) -> None:
    """Stop and remove managed TeslaMate containers.

    tesla teslaMate uninstall
    tesla teslaMate uninstall --remove-data
    """
    cfg = _m.load_config()
    if not cfg.teslaMate.managed:
        console.print("[yellow]TeslaMate is configured as external (not managed by CLI).[/yellow]")
        raise typer.Exit(1)

    if remove_data:
        console.print(
            "[red]WARNING: This will permanently delete all TeslaMate data (trips, charging history, etc.)[/red]"
        )
        confirm = typer.confirm("Are you sure?")
        if not confirm:
            raise typer.Abort()

    from pathlib import Path

    from tesla_cli.infra.teslamate_stack import TeslaMateStack

    stack = TeslaMateStack(Path(cfg.teslaMate.stack_dir) if cfg.teslaMate.stack_dir else None)
    stack.uninstall(remove_volumes=remove_data)

    cfg.teslaMate.managed = False
    cfg.teslaMate.database_url = ""
    cfg.teslaMate.stack_dir = ""
    save_config(cfg)

    render_success(
        "TeslaMate stack removed"
        + (" (data deleted)" if remove_data else " (data volumes preserved)")
    )


# ---------------------------------------------------------------------------
# Data import
# ---------------------------------------------------------------------------

_TESLAFI_REQUIRED_COLS = {"Date", "Odometer"}
_TESLAFI_COL_MAP: dict[str, str] = {
    "Date": "date",
    "Battery Level": "battery_level",
    "Charge Rate": "charge_rate",
    "Inside Temp": "inside_temp",
    "Outside Temp": "outside_temp",
    "Odometer": "odometer",
    "Speed": "speed",
    "Latitude": "latitude",
    "Longitude": "longitude",
    "Elevation": "elevation",
    "Heading": "heading",
    "Power": "power",
    "Ideal Battery Range": "ideal_battery_range",
    "Rated Battery Range": "rated_battery_range",
    "State": "state",
    "Charging State": "charging_state",
}


def _detect_format(file: str, fmt: str) -> str:
    """Auto-detect import format from extension and/or headers."""
    if fmt != "auto":
        return fmt

    import pathlib

    path = pathlib.Path(file)
    ext = path.suffix.lower()

    if ext == ".json":
        return "teslamate-json"

    if ext == ".csv":
        import csv as _csv

        with open(file, newline="", encoding="utf-8-sig") as fh:
            reader = _csv.DictReader(fh)
            headers = set(reader.fieldnames or [])
        if _TESLAFI_REQUIRED_COLS.issubset(headers):
            return "teslafi-csv"
        return "csv"

    return "csv"


def _parse_teslafi_csv(file: str) -> list[dict]:
    """Parse a TeslaFi CSV export into normalized row dicts."""
    import csv as _csv

    rows: list[dict] = []
    with open(file, newline="", encoding="utf-8-sig") as fh:
        reader = _csv.DictReader(fh)
        for raw in reader:
            row: dict = {}
            for src_col, dst_col in _TESLAFI_COL_MAP.items():
                val = raw.get(src_col, "").strip()
                row[dst_col] = val if val not in ("", "None", "null") else None
            rows.append(row)
    return rows


def _parse_teslamate_json(file: str) -> dict:
    """Load a TeslaMate JSON backup."""
    import pathlib

    data = json.loads(pathlib.Path(file).read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {"rows": data}


def _parse_generic_csv(file: str) -> list[dict]:
    """Parse a generic CSV file, returning rows as-is."""
    import csv as _csv

    rows: list[dict] = []
    with open(file, newline="", encoding="utf-8-sig") as fh:
        reader = _csv.DictReader(fh)
        for raw in reader:
            rows.append(dict(raw))
    return rows


def _preview_rows(rows: list[dict], n: int = 5) -> None:
    """Print first n rows as a Rich table."""
    from rich.table import Table

    if not rows:
        console.print("[yellow]No rows to preview.[/yellow]")
        return

    cols = list(rows[0].keys())
    t = Table(title=f"Preview (first {min(n, len(rows))} rows)", header_style="bold cyan")
    for col in cols:
        t.add_column(str(col), no_wrap=True, max_width=20)
    for row in rows[:n]:
        t.add_row(*[str(row.get(k) or "") for k in cols])
    console.print(t)


def _insert_teslafi_rows(database_url: str, car_id: int, rows: list[dict]) -> int:
    """Insert TeslaFi rows into TeslaMate positions table via psycopg2."""
    try:
        import psycopg2  # type: ignore[import]
    except ImportError:
        console.print("[red]psycopg2 not installed.[/red] Run: pip install psycopg2-binary")
        raise typer.Exit(1)

    sql = """
        INSERT INTO positions
            (car_id, date, latitude, longitude, speed, heading, elevation,
             odometer, battery_level, outside_temp, inside_temp, power,
             ideal_battery_range_km, rated_battery_range_km)
        VALUES
            (%(car_id)s, %(date)s, %(latitude)s, %(longitude)s, %(speed)s,
             %(heading)s, %(elevation)s, %(odometer)s, %(battery_level)s,
             %(outside_temp)s, %(inside_temp)s, %(power)s,
             %(ideal_battery_range)s, %(rated_battery_range)s)
        ON CONFLICT DO NOTHING
    """

    def _safe_float(val) -> float | None:
        try:
            return float(val) if val is not None else None
        except (TypeError, ValueError):
            return None

    def _safe_int(val) -> int | None:
        try:
            return int(float(val)) if val is not None else None
        except (TypeError, ValueError):
            return None

    conn = psycopg2.connect(database_url)
    inserted = 0
    try:
        with conn.cursor() as cur:
            for row in rows:
                cur.execute(
                    sql,
                    {
                        "car_id": car_id,
                        "date": row.get("date"),
                        "latitude": _safe_float(row.get("latitude")),
                        "longitude": _safe_float(row.get("longitude")),
                        "speed": _safe_float(row.get("speed")),
                        "heading": _safe_int(row.get("heading")),
                        "elevation": _safe_float(row.get("elevation")),
                        "odometer": _safe_float(row.get("odometer")),
                        "battery_level": _safe_int(row.get("battery_level")),
                        "outside_temp": _safe_float(row.get("outside_temp")),
                        "inside_temp": _safe_float(row.get("inside_temp")),
                        "power": _safe_float(row.get("power")),
                        "ideal_battery_range": _safe_float(row.get("ideal_battery_range")),
                        "rated_battery_range": _safe_float(row.get("rated_battery_range")),
                    },
                )
                inserted += cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return inserted


@teslaMate_app.command("import")
def teslamate_import(
    file: str = typer.Argument(help="Path to CSV or JSON file"),
    fmt: str = typer.Option(
        "auto", "--format", "-f", help="Format: auto, teslafi-csv, teslamate-json, csv"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be imported without writing"
    ),
) -> None:
    """Import historical data from TeslaFi CSV or TeslaMate JSON backup.

    \b
    tesla teslaMate import teslafi_export.csv
    tesla teslaMate import backup.json --format teslamate-json
    tesla teslaMate import data.csv --dry-run
    """
    import pathlib

    path = pathlib.Path(file)
    if not path.exists():
        console.print(f"[red]File not found:[/red] {file}")
        raise typer.Exit(1)

    detected = _detect_format(file, fmt)
    console.print(f"  [dim]Format detected:[/dim] [bold]{detected}[/bold]")

    # Parse
    rows: list[dict] = []
    json_data: dict | None = None

    if detected == "teslafi-csv":
        with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as p:
            p.add_task("Parsing TeslaFi CSV...", total=None)
            rows = _parse_teslafi_csv(file)
    elif detected == "teslamate-json":
        with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as p:
            p.add_task("Parsing TeslaMate JSON...", total=None)
            json_data = _parse_teslamate_json(file)
        # For JSON, summarise tables rather than flat rows
        if isinstance(json_data, dict):
            for _table, table_rows in json_data.items():
                if isinstance(table_rows, list):
                    rows.extend(table_rows[:5])  # preview only first 5 per table
    else:
        # generic CSV
        with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as p:
            p.add_task("Parsing CSV...", total=None)
            rows = _parse_generic_csv(file)

    total_rows = len(rows)

    # Preview
    _preview_rows(rows[:5] if detected != "teslamate-json" else rows, n=5)

    # Date range
    dates = [
        r.get("date") or r.get("Date") or r.get("started_at") or r.get("timestamp") for r in rows
    ]
    dates = [d for d in dates if d]
    date_range = f"{min(dates)[:10]} → {max(dates)[:10]}" if dates else "unknown"

    console.print()
    console.print("  [bold]Summary[/bold]")
    console.print(f"  File:        {path.name}")
    console.print(f"  Format:      {detected}")
    console.print(f"  Rows found:  {total_rows:,}")
    console.print(f"  Date range:  {date_range}")

    if dry_run:
        console.print("\n  [yellow]--dry-run: no data written.[/yellow]")
        return

    if detected == "teslamate-json":
        console.print(
            "\n  [yellow]TeslaMate JSON restore is not yet implemented.[/yellow]\n"
            "  [dim]Use the TeslaMate web UI or psql to restore from a JSON backup.[/dim]"
        )
        raise typer.Exit(1)

    # Require DB connection for actual insert
    cfg = _m.load_config()
    database_url = cfg.teslaMate.database_url
    car_id = cfg.teslaMate.car_id

    if not database_url:
        console.print(f"[red]{i18n_t('teslaMate.not_configured')}[/red]")
        console.print("  [dim]Managed stack: tesla teslaMate install[/dim]")
        raise typer.Exit(1)

    console.print(f"\n  Inserting {total_rows:,} rows into TeslaMate DB (car_id={car_id})...")

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as p:
        p.add_task("Importing...", total=None)
        if detected in ("teslafi-csv", "csv"):
            # Re-parse full file for actual insert
            if detected == "teslafi-csv":
                all_rows = _parse_teslafi_csv(file)
            else:
                all_rows = _parse_generic_csv(file)
            inserted = _insert_teslafi_rows(database_url, car_id, all_rows)
        else:
            inserted = 0

    console.print(f"  [green]Done.[/green] {inserted:,} rows imported.")


@teslaMate_app.command("doctor")
def teslaMate_doctor(
    json_output: bool = typer.Option(
        False, "--json", help="Emit JSON instead of formatted output."
    ),
) -> None:
    """Diagnose TeslaMate stack health (8 checks). Exit code = number of failed checks."""
    from tesla_cli.core.diagnostics.teslamate_doctor import run_doctor

    cfg = _m.load_config()
    report = run_doctor(cfg)
    if json_output:
        typer.echo(report.model_dump_json(indent=2))
    else:
        for c in report.checks:
            mark = "✓" if c.ok else "✗"
            color = typer.colors.GREEN if c.ok else typer.colors.RED
            typer.secho(f"{mark} {c.label}: {c.message}", fg=color)
            if not c.ok and c.hint:
                typer.secho(f"   → {c.hint}", fg=typer.colors.YELLOW)
        typer.echo()
        if report.failed == 0:
            typer.secho(f"All {report.total} checks passed.", fg=typer.colors.GREEN, bold=True)
        else:
            typer.secho(
                f"{report.failed}/{report.total} checks failed.",
                fg=typer.colors.RED,
                bold=True,
            )
    raise typer.Exit(code=report.failed)
