"""Live monitoring: trips, watch, streams, dashboards, readiness checks.

Part of the ``tesla vehicle`` command group (see ``__init__.py``). Names that
tests patch on ``tesla_cli.cli.commands.vehicle`` (backend factory, config,
VIN resolution, ``time``) are looked up through the package as ``_v.<name>``.
"""

from __future__ import annotations

from tesla_cli.cli.commands import vehicle as _v
from tesla_cli.cli.commands.vehicle import (  # noqa: F401
    Progress,
    SpinnerColumn,
    TextColumn,
    VehicleAsleepError,
    VinOption,
    console,
    is_json_mode,
    logging,
    typer,
    vehicle_app,
)


@vehicle_app.command("trips")
def vehicle_trips(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of recent trips to show"),
    vin: str | None = VinOption,
) -> None:
    """Show recent trip summary from vehicle service data.

    Note: Detailed trip history requires TeslaMate or Fleet API telemetry.
    This command shows what's available from the Owner API service data.
    """
    v = _v._vin(vin)

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()
    ) as p:
        p.add_task("Fetching trip data...", total=None)
        try:
            svc_data = _v._with_wake(lambda b, v: b.get_service_data(v), v)
        except Exception:
            svc_data = {}

        drive_state = _v._with_wake(lambda b, v: b.get_drive_state(v), v)
        vehicle_state = _v._with_wake(lambda b, v: b.get_vehicle_state(v), v)

    if is_json_mode():
        import json

        console.print(
            json.dumps(
                {
                    "service_data": svc_data,
                    "drive_state": drive_state,
                    "vehicle_state": vehicle_state,
                },
                indent=2,
                default=str,
            )
        )
        return

    odo = vehicle_state.get("odometer", 0)
    last_lat = drive_state.get("latitude")
    last_lon = drive_state.get("longitude")
    last_speed = drive_state.get("speed", 0) or 0
    heading = drive_state.get("heading", 0)
    native_type = drive_state.get("native_type", "")

    console.print("\n[bold cyan]Trip Data[/bold cyan]")
    console.print(f"  Odometer: [bold]{odo:.1f} mi[/bold]")
    if last_lat:
        console.print(
            f"  Last location: {last_lat:.4f}, {last_lon:.4f}  (heading {heading}°, {last_speed} mph)"
        )
        console.print(f"  Maps: https://maps.google.com/?q={last_lat},{last_lon}")

    if native_type:
        console.print(f"  Native type: {native_type}")

    console.print(
        "\n[dim]Tip: For full trip history with route maps, energy usage, and stats,\n"
        "     connect TeslaMate: https://docs.teslamate.org[/dim]"
    )


# ── Watch state keys ──────────────────────────────────────────────────────────

_WATCH_KEYS: list[tuple[str, str, str]] = [
    # (section, key, label)
    ("charge_state", "battery_level", "🔋 Battery"),
    ("charge_state", "charging_state", "⚡ Charging state"),
    ("charge_state", "charge_limit_soc", "⚡ Charge limit"),
    ("vehicle_state", "locked", "🔒 Locked"),
    ("vehicle_state", "is_user_present", "👤 User present"),
    ("vehicle_state", "df", "🚪 Driver front door"),
    ("vehicle_state", "pf", "🚪 Pass front door"),
    ("vehicle_state", "dr", "🚪 Driver rear door"),
    ("vehicle_state", "pr", "🚪 Pass rear door"),
    ("climate_state", "is_climate_on", "🌡️ Climate"),
    ("climate_state", "inside_temp", "🌡️ Cabin temp"),
    ("drive_state", "shift_state", "🚗 Shift state"),
    ("drive_state", "speed", "🚗 Speed"),
]


def _format_watch_change(
    curr: dict,
    changes: list[str],
    ts: str,
    tag: str,
    mode: str,
) -> str:
    """Format a watch poll result for display.

    mode='simple'  — key changes only (default)
    mode='detail'  — same as simple (alias kept for future expansion)
    mode='raw'     — JSON per change event
    """
    import json as _json

    if mode == "raw":
        clean = [c.replace("[bold]", "").replace("[/bold]", "") for c in changes]
        return _json.dumps({"ts": ts, "changes": clean, "state": {k: v for k, v in curr.items()}})

    if changes:
        lines = [f"  {tag}[dim]{ts}[/dim]  {c}" for c in changes]
        return "\n".join(lines)

    # No changes — show brief status line
    batt = curr.get("charge_state.battery_level", "?")
    state = curr.get("charge_state.charging_state", "Unknown")
    locked = curr.get("vehicle_state.locked", "?")
    return (
        f"  {tag}[dim]{ts}[/dim]  🔋{batt}%  ⚡{state}  🔒{'yes' if locked else 'no'}"
        "  [dim](no changes)[/dim]"
    )


@vehicle_app.command("watch")
def vehicle_watch(
    interval: int = typer.Option(60, "--interval", "-i", min=10, help="Poll interval in seconds"),
    notify: str | None = typer.Option(
        None, "--notify", help="Apprise URL for push notifications on change"
    ),
    on_change_exec: str | None = typer.Option(
        None,
        "--on-change-exec",
        help="Shell command to run on state change. Changes passed as JSON via TESLA_CHANGES env var.",
    ),
    all_vehicles: bool = typer.Option(
        False, "--all", "-A", help="Watch all configured vehicles simultaneously"
    ),
    mode: str = typer.Option(
        "simple",
        "--mode",
        help="Output mode: simple (key changes only), detail (same as simple), raw (JSON per change)",
    ),
    max_changes: int = typer.Option(
        0, "--max-changes", help="Stop after N state changes (0 = unlimited, useful for cron)"
    ),
    vin: str | None = VinOption,
) -> None:
    """Continuous vehicle monitoring — prints alerts on state changes.

    Polls every INTERVAL seconds and reports any change in battery,
    charging state, locks, climate, doors, or shift state.

    tesla vehicle watch
    tesla vehicle watch --on-change-exec "echo 'State changed!' >> /tmp/tesla.log"
    tesla vehicle watch --interval 30
    tesla vehicle watch --notify "tgram://botid/chatid"
    tesla vehicle watch --all
    tesla vehicle watch --all --notify "tgram://botid/chatid"
    tesla vehicle watch --mode raw
    tesla vehicle watch --max-changes 5
    Press Ctrl+C to stop.
    """
    import json as _json
    import threading
    from datetime import datetime as _dt

    if mode not in ("simple", "detail", "raw"):
        console.print("[red]--mode must be one of: simple, detail, raw[/red]")
        raise typer.Exit(1)

    cfg = _v.load_config()

    notifier = None
    if notify:
        try:
            import apprise

            notifier = apprise.Apprise()
            notifier.add(notify)
        except ImportError:
            console.print("[yellow]⚠ apprise not installed — notifications disabled[/yellow]")

    # Shared counter for max-changes tracking across threads
    _change_count: list[int] = [0]
    _change_lock = threading.Lock()

    def _snapshot(backend, target_v: str) -> dict:
        """Fetch vehicle data and extract watched keys into a flat dict."""
        try:
            data = backend.get_vehicle_data(target_v)
        except VehicleAsleepError:
            return {}
        flat: dict = {}
        for section, key, _label in _WATCH_KEYS:
            sec = data.get(section) or {}
            val = sec.get(key)
            if val is not None:
                flat[f"{section}.{key}"] = val
        return flat

    def _watch_one(target_v: str, prefix: str, stop: threading.Event | None) -> None:
        label = prefix
        backend = _v.get_vehicle_backend(cfg)
        prev: dict = {}
        while True:
            if stop is not None and stop.is_set():
                break
            curr = _snapshot(backend, target_v)
            tag = f"[cyan]{prefix}[/cyan]  " if prefix else ""
            if not curr:
                console.print(
                    f"  {tag}[dim]{_dt.now().strftime('%H:%M:%S')}[/dim]  [yellow]Vehicle asleep[/yellow]"
                )
            else:
                changes: list[str] = []
                for section, key, watch_label in _WATCH_KEYS:
                    fk = f"{section}.{key}"
                    if fk not in curr:
                        continue
                    old = prev.get(fk)
                    new = curr[fk]
                    if old is None:
                        continue  # first-seen value, don't alert
                    if new != old:
                        changes.append(f"{watch_label}: [bold]{old}[/bold] → [bold]{new}[/bold]")

                ts = _dt.now().strftime("%H:%M:%S")
                if is_json_mode():
                    payload = {
                        "ts": ts,
                        "vin": target_v,
                        "changes": [
                            c.replace("[bold]", "").replace("[/bold]", "") for c in changes
                        ],
                    }
                    console.print(_json.dumps(payload))
                else:
                    line = _format_watch_change(curr, changes, ts, tag, mode)
                    console.print(line)
                    if changes:
                        if notifier:
                            body = "\n".join(
                                c.replace("[bold]", "").replace("[/bold]", "") for c in changes
                            )
                            prefix_title = f"Tesla Watch — {label}" if label else "Tesla Watch"
                            notifier.notify(title=prefix_title, body=body)
                        if on_change_exec:
                            import os
                            import subprocess

                            change_data = [
                                {"key": c.split(":")[0].strip(), "change": c}
                                for c in [
                                    c.replace("[bold]", "").replace("[/bold]", "") for c in changes
                                ]
                            ]
                            env = {**os.environ, "TESLA_CHANGES": _json.dumps(change_data)}
                            subprocess.Popen(on_change_exec, shell=True, env=env)
                        if max_changes > 0:
                            with _change_lock:
                                _change_count[0] += len(changes)
                                if _change_count[0] >= max_changes:
                                    if stop is not None:
                                        stop.set()
                                    return
            prev = curr
            _v.time.sleep(interval)

    if all_vehicles:
        # Collect all VINs from default + aliases, deduplicated
        vins_raw: list[str] = []
        if cfg.general.default_vin:
            vins_raw.append(cfg.general.default_vin)
        vins_raw.extend(cfg.vehicles.aliases.values())
        vins: list[str] = list(dict.fromkeys(vins_raw))

        if not vins:
            console.print("[red]No VINs configured. Set default-vin or add aliases.[/red]")
            raise typer.Exit(1)

        alias_of = {v: a for a, v in cfg.vehicles.aliases.items()}
        stop_event = threading.Event()
        threads = []
        for target_v in vins:
            label = alias_of.get(target_v, target_v[-6:])
            t = threading.Thread(target=_watch_one, args=(target_v, label, stop_event), daemon=True)
            threads.append(t)

        for t in threads:
            t.start()

        console.print(
            f"\n  [bold]Watching {len(vins)} vehicle(s)...[/bold]  [dim]Press Ctrl+C to stop.[/dim]\n"
        )
        try:
            while True:
                _v.time.sleep(1)
        except KeyboardInterrupt:
            stop_event.set()
            for t in threads:
                t.join()
            console.print("\n  [dim]Watch stopped.[/dim]\n")
    else:
        v = _v._vin(vin)
        stop_msg = f" (stops after {max_changes} changes)" if max_changes > 0 else ""
        console.print(
            f"\n  [bold]Watching vehicle[/bold] [dim]{v}[/dim] — polling every [bold]{interval}s[/bold]{stop_msg}"
        )
        console.print("  [dim]Press Ctrl+C to stop.[/dim]\n")
        _single_stop = threading.Event()
        try:
            _watch_one(v, "", _single_stop)
        except KeyboardInterrupt:
            console.print("\n  [dim]Watch stopped.[/dim]\n")


@vehicle_app.command("health-check")
def vehicle_health_check(vin: str | None = VinOption) -> None:
    """Comprehensive vehicle health summary: battery, firmware, tyres, alerts, sentry.

    \b
    tesla vehicle health-check
    tesla -j vehicle health-check
    """
    import json as _json

    cfg = _v.load_config()
    v = _v.resolve_vin(cfg, vin)
    b = _v.get_vehicle_backend(cfg)

    results: dict = {"vin": v, "checks": []}

    def _check(name: str, status: str, value: str, detail: str = "") -> None:
        results["checks"].append({"name": name, "status": status, "value": value, "detail": detail})

    # Fetch all states in one call
    try:
        data = b.get_vehicle_data(v)
    except VehicleAsleepError:
        console.print("[yellow]Vehicle is asleep — wake it first.[/yellow]")
        raise typer.Exit(1)
    except Exception as exc:
        console.print(f"[red]Failed to fetch vehicle data:[/red] {exc}")
        raise typer.Exit(1)

    cs = data.get("charge_state") or {}
    vs = data.get("vehicle_state") or {}

    # Battery
    level = cs.get("battery_level")
    if level is not None:
        st = "ok" if level >= 20 else "warn" if level >= 10 else "error"
        _check("Battery level", st, f"{level}%")
    else:
        _check("Battery level", "unknown", "—")

    # Charge limit
    limit = cs.get("charge_limit_soc")
    if limit is not None:
        st = "ok" if 70 <= limit <= 90 else "warn"
        _check(
            "Charge limit",
            st,
            f"{limit}%",
            "" if 70 <= (limit or 0) <= 90 else "Limit outside 70–90% range",
        )

    # Firmware
    sw = vs.get("car_version") or "—"
    pending = vs.get("software_update", {})
    has_update = bool(
        pending.get("status") not in (None, "", "available") and pending.get("version")
    )
    sw_status = "warn" if has_update else "ok"
    sw_detail = f"Update available: {pending.get('version', '')}" if has_update else ""
    _check("Firmware", sw_status, sw, sw_detail)

    # Tyre pressure
    tpms = {
        "FL": vs.get("tpms_pressure_fl"),
        "FR": vs.get("tpms_pressure_fr"),
        "RL": vs.get("tpms_pressure_rl"),
        "RR": vs.get("tpms_pressure_rr"),
    }
    low = [k for k, v_p in tpms.items() if v_p is not None and float(v_p) < 2.4]
    tyre_vals = {k: f"{float(v_p):.2f}" for k, v_p in tpms.items() if v_p is not None}
    if not tyre_vals:
        _check("Tyre pressure", "unknown", "—", "TPMS data unavailable")
    elif low:
        _check(
            "Tyre pressure",
            "warn",
            ", ".join(f"{k}:{tyre_vals.get(k, '?')}bar" for k in sorted(tyre_vals)),
            f"Low: {', '.join(low)}",
        )
    else:
        _check("Tyre pressure", "ok", ", ".join(f"{k}:{tyre_vals[k]}" for k in sorted(tyre_vals)))

    # Locks
    locked = vs.get("locked")
    if locked is not None:
        _check("Doors locked", "ok" if locked else "warn", "Yes" if locked else "No")

    # Sentry
    sentry = vs.get("sentry_mode")
    if sentry is not None:
        _check("Sentry mode", "ok", "On" if sentry else "Off")

    # Odometer
    odo = vs.get("odometer")
    if odo is not None:
        _check("Odometer", "ok", f"{float(odo):.0f} mi")

    if is_json_mode():
        console.print(_json.dumps(results, indent=2))
        return

    _ICON = {
        "ok": "[green]✓[/green]",
        "warn": "[yellow]⚠[/yellow]",
        "error": "[red]✗[/red]",
        "unknown": "[dim]?[/dim]",
    }
    from rich.table import Table as _Table

    t = _Table(title=f"Vehicle Health — {v[-6:]}", show_header=False, box=None, padding=(0, 2))
    t.add_column("s", width=3)
    t.add_column("k", style="bold", width=18)
    t.add_column("v", width=30)
    t.add_column("d", style="dim")

    for c in results["checks"]:
        icon = _ICON.get(c["status"], "?")
        t.add_row(icon, c["name"], c["value"], c.get("detail") or "")
    console.print(t)

    errors = sum(1 for c in results["checks"] if c["status"] == "error")
    warnings = sum(1 for c in results["checks"] if c["status"] == "warn")
    if errors:
        console.print(f"\n  [red]✗ {errors} issue(s) need attention[/red]")
    elif warnings:
        console.print(f"\n  [yellow]⚠ {warnings} item(s) to review[/yellow]")
    else:
        console.print("\n  [green]✓ All checks passed[/green]")


# ═══════════════════════════════════════════════════════════════════════════════
# Absorbed from stream.py, dashboard.py, sharing.py
# ═══════════════════════════════════════════════════════════════════════════════


@vehicle_app.command("stream")
def vehicle_stream(
    interval: float = typer.Option(5.0, "--interval", "-i", help="Refresh interval in seconds"),
    count: int = typer.Option(0, "--count", "-n", help="Stop after N refreshes (0=forever)"),
    mqtt_url: str | None = typer.Option(None, "--mqtt", help="MQTT broker URL"),
    vin: str | None = VinOption,
) -> None:
    """Real-time vehicle telemetry stream.

    tesla vehicle stream
    tesla vehicle stream --interval 10
    tesla vehicle stream --count 20
    """
    import json as _json

    from rich.live import Live
    from rich.table import Table as _Table

    cfg = _v.load_config()
    v = _v.resolve_vin(cfg, vin)
    backend = _v._backend()

    iteration = 0
    try:
        with Live(console=console, refresh_per_second=1, transient=False) as live:
            while True:
                try:
                    data = backend.get_vehicle_data(v)
                except VehicleAsleepError:
                    console.print("[yellow]Vehicle asleep, waking...[/yellow]")
                    backend.wake_up(v)
                    _v.time.sleep(5)
                    continue

                if is_json_mode():
                    console.print_json(_json.dumps(data, indent=2, default=str))
                    raise typer.Exit(0)

                cs = data.get("charge_state", {})
                cl = data.get("climate_state", {})
                ds = data.get("drive_state", {})
                vs = data.get("vehicle_state", {})

                t = _Table(title=f"Tesla Stream — {v[-6:]}", show_lines=True)
                t.add_column("Key", style="cyan", width=22)
                t.add_column("Value", width=30)

                t.add_row("Battery", f"{cs.get('battery_level', '?')}%")
                t.add_row("Range", f"{cs.get('battery_range', 0):.1f} mi")
                t.add_row("Charging", cs.get("charging_state", "?"))
                if cs.get("charging_state") == "Charging":
                    t.add_row("Charge Rate", f"{cs.get('charger_power', 0)} kW")
                t.add_row("Inside Temp", f"{cl.get('inside_temp', '?')}°C")
                t.add_row("Outside Temp", f"{cl.get('outside_temp', '?')}°C")
                lat = ds.get("latitude")
                lon = ds.get("longitude")
                if lat and lon:
                    t.add_row("Location", f"{lat:.4f}, {lon:.4f}")
                t.add_row("Speed", f"{ds.get('speed') or 0} mph")
                t.add_row("Locked", "Yes" if vs.get("locked") else "No")
                t.add_row("Sentry", "ON" if vs.get("sentry_mode") else "off")
                t.add_row("Software", vs.get("car_version", "?"))
                t.add_row("Odometer", f"{vs.get('odometer', 0):,.0f} mi")

                live.update(t)

                # MQTT publish if configured
                if mqtt_url:
                    try:
                        from tesla_cli.core.providers.impl.mqtt import MqttProvider

                        mp = MqttProvider(cfg)
                        if mp.available():
                            mp.push(data)
                    except Exception:
                        logging.getLogger(__name__).debug("Ignored error", exc_info=True)

                iteration += 1
                if count and iteration >= count:
                    break
                _v.time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[dim]Stream stopped.[/dim]")


@vehicle_app.command("dashboard")
def vehicle_dashboard(vin: str | None = VinOption) -> None:
    """Unified multi-panel vehicle status dashboard.

    tesla vehicle dashboard
    tesla -j vehicle dashboard
    """
    import json as _json

    from rich.columns import Columns
    from rich.panel import Panel
    from rich.table import Table as _Table

    v = _v._vin(vin)
    data = _v._with_wake(lambda b, v: b.get_vehicle_data(v), v)

    if is_json_mode():
        console.print(_json.dumps(data, indent=2, default=str))
        return

    charge = data.get("charge_state", {})
    climate = data.get("climate_state", {})
    drive = data.get("drive_state", {})
    vehicle = data.get("vehicle_state", {})
    config = data.get("vehicle_config", {})

    def _bool_icon(val):
        return "\u2705" if val else "\u274c" if val is not None else "\u2753"

    def _bar(level):
        filled = level // 5
        empty = 20 - filled
        color = "green" if level > 60 else "yellow" if level > 20 else "red"
        return f"[{color}]{chr(9608) * filled}{chr(9617) * empty}[/{color}] {level}%"

    battery_level = charge.get("battery_level", 0)
    bt = _Table(show_header=False, box=None, padding=(0, 1))
    bt.add_column("K", style="bold cyan", width=20)
    bt.add_column("V")
    bt.add_row("Battery", _bar(battery_level))
    bt.add_row("Range", f"{charge.get('battery_range', 0):.0f} mi")
    bt.add_row("Charge Limit", f"{charge.get('charge_limit_soc', 0)}%")
    bt.add_row("Charging", charge.get("charging_state", "Unknown"))
    if charge.get("charging_state") == "Charging":
        bt.add_row("Power", f"{charge.get('charger_power', 0)} kW")
        bt.add_row("Time Left", f"{charge.get('time_to_full_charge', 0):.1f} hr")

    lat = drive.get("latitude", 0)
    lon = drive.get("longitude", 0)
    lt = _Table(show_header=False, box=None, padding=(0, 1))
    lt.add_column("K", style="bold cyan", width=20)
    lt.add_column("V")
    lt.add_row("Coordinates", f"{lat:.5f}, {lon:.5f}" if lat else "Unknown")
    speed = drive.get("speed")
    lt.add_row("Speed", f"{speed} mph" if speed else "Parked")

    st = _Table(show_header=False, box=None, padding=(0, 1))
    st.add_column("K", style="bold cyan", width=20)
    st.add_column("V")
    st.add_row("Locked", _bool_icon(vehicle.get("locked")))
    st.add_row("Sentry Mode", _bool_icon(vehicle.get("sentry_mode")))
    st.add_row("Software", vehicle.get("car_version", "Unknown"))
    st.add_row("Odometer", f"{vehicle.get('odometer', 0):,.0f} mi")

    ct = _Table(show_header=False, box=None, padding=(0, 1))
    ct.add_column("K", style="bold cyan", width=20)
    ct.add_column("V")
    ct.add_row("Climate On", _bool_icon(climate.get("is_climate_on")))
    inside = climate.get("inside_temp")
    outside = climate.get("outside_temp")
    ct.add_row("Inside", f"{inside}\u00b0C" if inside is not None else "N/A")
    ct.add_row("Outside", f"{outside}\u00b0C" if outside is not None else "N/A")

    name = data.get("display_name", data.get("vehicle_name", v))
    model = config.get("car_type", "Tesla")

    panels = [
        Panel(bt, title="\U0001f50b Battery & Charging", border_style="green"),
        Panel(lt, title="\U0001f4cd Location", border_style="blue"),
        Panel(st, title="\U0001f512 Security", border_style="red"),
        Panel(ct, title="\U0001f321\ufe0f Climate", border_style="yellow"),
    ]

    console.print()
    console.print(f"[bold]\U0001f697 {name}[/bold] ({model}) \u2014 {v}")
    console.print()
    console.print(Columns(panels, equal=True, expand=True))


@vehicle_app.command("ready")
def vehicle_ready(
    oneline: bool = typer.Option(False, "--oneline", "-1", help="Single-line output"),
    vin: str | None = VinOption,
) -> None:
    """Morning check: am I ready to drive?

    Combines battery level, charge schedule, cabin temperature, alerts,
    and vehicle state into a single "ready to go" assessment.

    tesla vehicle ready
    tesla vehicle ready --oneline
    tesla -j vehicle ready
    """
    import json as _json

    v = _v._vin(vin)
    data = _v._with_wake(lambda b, v: b.get_vehicle_data(v), v)

    cs = data.get("charge_state", {})
    cl = data.get("climate_state", {})
    vs = data.get("vehicle_state", {})

    level = cs.get("battery_level", 0)
    range_mi = cs.get("battery_range", 0)
    range_km = round(range_mi * 1.60934, 1) if range_mi else 0
    charging = cs.get("charging_state", "Unknown")
    limit = cs.get("charge_limit_soc", 0)
    inside = cl.get("inside_temp")
    outside = cl.get("outside_temp")
    locked = vs.get("locked", False)
    sentry = vs.get("sentry_mode", False)
    sw_update = vs.get("software_update") or {}
    update_available = sw_update.get("status", "") not in ("", "available")
    precond = cl.get("is_preconditioning", False)
    climate_on = cl.get("is_climate_on", False)

    # Assess readiness
    issues: list[str] = []
    good: list[str] = []

    if level >= 20:
        good.append(f"Battery {level}% ({range_km} km)")
    else:
        issues.append(f"Low battery: {level}% ({range_km} km)")

    if charging == "Charging":
        eta = cs.get("time_to_full_charge", 0)
        eta_str = f"{int(eta)}h{int((eta % 1) * 60):02d}m" if eta else ""
        issues.append(f"Still charging — {eta_str} to {limit}%")
    elif charging == "Complete":
        good.append(f"Charge complete ({limit}%)")
    elif level >= limit:
        good.append(f"At charge limit ({limit}%)")

    if outside is not None and outside < 5:
        if climate_on or precond:
            good.append(f"Preconditioning active ({outside}\u00b0C outside)")
        else:
            issues.append(f"Cold outside ({outside}\u00b0C) \u2014 consider preconditioning")
    elif inside is not None:
        good.append(f"Cabin {inside}\u00b0C")

    if locked:
        good.append("Locked")
    else:
        issues.append("Vehicle unlocked")

    if sentry:
        good.append("Sentry ON")

    if update_available:
        issues.append("Software update pending")

    if is_json_mode():
        console.print_json(
            _json.dumps(
                {
                    "ready": len(issues) == 0,
                    "battery_level": level,
                    "range_km": range_km,
                    "charging_state": charging,
                    "inside_temp": inside,
                    "outside_temp": outside,
                    "locked": locked,
                    "sentry_mode": sentry,
                    "preconditioning": precond or climate_on,
                    "issues": issues,
                    "good": good,
                },
                indent=2,
            )
        )
        return

    if oneline:
        status = "\u2705 Ready" if not issues else f"\u26a0\ufe0f {len(issues)} issue(s)"
        parts = [status, f"\U0001f50b {level}%"]
        if inside is not None:
            parts.append(f"\U0001f321 {inside}\u00b0C")
        if charging == "Charging":
            parts.append("\u26a1 Charging")
        typer.echo(" | ".join(parts))
        return

    console.print()
    if not issues:
        console.print("  [bold green]\u2705 Ready to drive![/bold green]")
    else:
        console.print(f"  [bold yellow]\u26a0\ufe0f  {len(issues)} issue(s)[/bold yellow]")

    console.print()
    for g in good:
        console.print(f"  [green]\u2713[/green] {g}")
    for i in issues:
        console.print(f"  [yellow]\u26a0[/yellow] {i}")
    console.print()


@vehicle_app.command("stream-live")
def vehicle_stream_live(
    lines: int = typer.Option(
        50, "--lines", "-n", help="Number of recent log lines to show before following"
    ),
    raw: bool = typer.Option(False, "--raw", help="Print raw log lines without formatting"),
    vin: str | None = VinOption,
) -> None:
    """Stream real-time telemetry from the self-hosted fleet-telemetry server.

    Tails the fleet-telemetry Docker container logs, which receive data
    streamed directly from your vehicle.

    Requires: tesla telemetry install + tesla telemetry configure

    tesla vehicle stream-live
    tesla vehicle stream-live --lines 100
    tesla vehicle stream-live --raw
    """

    cfg = _v.load_config()

    if not cfg.telemetry.enabled or not cfg.telemetry.managed:
        console.print(
            "[red]Self-hosted fleet-telemetry not configured.[/red]\n"
            "Run: [bold]tesla telemetry install <hostname>[/bold]\n"
            "Then: [bold]tesla telemetry configure[/bold]"
        )
        raise typer.Exit(1)

    from pathlib import Path

    from tesla_cli.infra.fleet_telemetry_stack import FleetTelemetryStack

    stack_dir = Path(cfg.telemetry.stack_dir) if cfg.telemetry.stack_dir else None
    stack = FleetTelemetryStack(stack_dir)

    if not stack.is_installed():
        console.print(
            "[red]Fleet-telemetry stack is not installed.[/red]\n"
            "Run: [bold]tesla telemetry install <hostname>[/bold]"
        )
        raise typer.Exit(1)

    if not stack.is_running():
        console.print(
            "[yellow]Fleet-telemetry container is not running.[/yellow]\n"
            "Start it with: [bold]tesla telemetry start[/bold]"
        )
        raise typer.Exit(1)

    console.print(
        "[bold]Streaming from fleet-telemetry server...[/bold] [dim](Ctrl+C to stop)[/dim]"
    )

    proc = stack.logs(lines=lines, follow=True)
    try:
        for line in proc.stdout or []:
            if raw:
                console.print(line, end="")
            else:
                console.print(line, end="")
    except KeyboardInterrupt:
        proc.terminate()
