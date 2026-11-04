"""Vehicle control: charging, climate, locks, trunks, sentry, valet, schedules, sharing.

Part of the ``tesla vehicle`` command group (see ``__init__.py``). Names that
tests patch on ``tesla_cli.cli.commands.vehicle`` (backend factory, config,
VIN resolution, ``time``) are looked up through the package as ``_v.<name>``.
"""

from __future__ import annotations

from tesla_cli.cli.commands import vehicle as _v
from tesla_cli.cli.commands.vehicle import (  # noqa: F401
    ChargeState,
    ClimateState,
    Progress,
    SpinnerColumn,
    TextColumn,
    VinOption,
    console,
    is_json_mode,
    render_dict,
    render_model,
    render_success,
    render_table,
    typer,
    vehicle_app,
)


@vehicle_app.command("charge")
def vehicle_charge(
    vin: str | None = VinOption,
    action: str | None = typer.Argument(None, help="start | stop (omit to show status)"),
) -> None:
    """Show charge state or start/stop charging."""
    v = _v._vin(vin)

    if action == "start":
        _v._with_wake(lambda b, v: b.command(v, "charge_start"), v)
        render_success("Charging started")
    elif action == "stop":
        _v._with_wake(lambda b, v: b.command(v, "charge_stop"), v)
        render_success("Charging stopped")
    else:
        data = _v._with_wake(lambda b, v: b.get_charge_state(v), v)
        state = ChargeState.model_validate(data)
        render_model(state, title="Charge State")


@vehicle_app.command("climate")
def vehicle_climate(
    vin: str | None = VinOption,
    action: str | None = typer.Argument(None, help="on | off (omit to show status)"),
) -> None:
    """Show climate state or turn HVAC on/off."""
    v = _v._vin(vin)

    if action == "on":
        _v._with_wake(lambda b, v: b.command(v, "auto_conditioning_start"), v)
        render_success("Climate ON")
    elif action == "off":
        _v._with_wake(lambda b, v: b.command(v, "auto_conditioning_stop"), v)
        render_success("Climate OFF")
    else:
        data = _v._with_wake(lambda b, v: b.get_climate_state(v), v)
        state = ClimateState.model_validate(data)
        render_model(state, title="Climate State")


@vehicle_app.command("lock")
def vehicle_lock(vin: str | None = VinOption) -> None:
    """Lock the vehicle."""
    v = _v._vin(vin)
    _v._with_wake(lambda b, v: b.command(v, "door_lock"), v)
    render_success("Vehicle locked")


@vehicle_app.command("unlock")
def vehicle_unlock(vin: str | None = VinOption) -> None:
    """Unlock the vehicle."""
    v = _v._vin(vin)
    _v._with_wake(lambda b, v: b.command(v, "door_unlock"), v)
    render_success("Vehicle unlocked")


@vehicle_app.command("horn")
def vehicle_horn(vin: str | None = VinOption) -> None:
    """Honk the horn."""
    v = _v._vin(vin)
    _v._with_wake(lambda b, v: b.command(v, "honk_horn"), v)
    render_success("Horn honked")


@vehicle_app.command("flash")
def vehicle_flash(vin: str | None = VinOption) -> None:
    """Flash the lights."""
    v = _v._vin(vin)
    _v._with_wake(lambda b, v: b.command(v, "flash_lights"), v)
    render_success("Lights flashed")


@vehicle_app.command("wake")
def vehicle_wake(vin: str | None = VinOption) -> None:
    """Wake up the vehicle."""
    v = _v._vin(vin)
    backend = _v._backend()

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()
    ) as p:
        p.add_task("Waking vehicle...", total=None)
        result = backend.wake_up(v)

    if result:
        render_success("Vehicle is awake")
    else:
        console.print("[yellow]Wake command sent. Vehicle may take a moment to respond.[/yellow]")


@vehicle_app.command("trunk")
def vehicle_trunk(
    which: str = typer.Argument("rear", help="rear | front (frunk)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview action without executing"),
    vin: str | None = VinOption,
) -> None:
    """Open trunk or frunk."""
    v = _v._vin(vin)
    if dry_run:
        console.print(f"[dim]Dry run:[/dim] Would open {which} trunk for VIN ...{v[-6:]}")
        return
    cmd = "actuate_trunk"
    param = "rear" if which == "rear" else "front"
    _v._with_wake(lambda b, v: b.command(v, cmd, which_trunk=param), v)
    render_success(f"{which.title()} trunk opened")


@vehicle_app.command("sentry")
def vehicle_sentry(
    enable: bool | None = typer.Option(None, "--on/--off", help="Turn Sentry Mode on or off"),
    oneline: bool = typer.Option(False, "--oneline", "-1", help="Single-line output"),
    vin: str | None = VinOption,
) -> None:
    """Show or toggle Sentry Mode.

    tesla vehicle sentry              → show status
    tesla vehicle sentry --oneline    → 🛡 Sentry ON
    tesla vehicle sentry --on         → enable
    tesla vehicle sentry --off        → disable
    """
    v = _v._vin(vin)

    if enable is None:
        # Show status
        data = _v._with_wake(lambda b, v: b.get_vehicle_state(v), v)
        sentry_on = data.get("sentry_mode", False)
        available = data.get("sentry_mode_available", True)
        status = "ON" if sentry_on else "OFF"
        status_color = "green" if sentry_on else "dim"

        if oneline:
            icon = "\U0001f6e1"
            typer.echo(f"{icon} Sentry {status}")
            return

        if is_json_mode():
            import json

            console.print(
                json.dumps(
                    {
                        "sentry_mode": sentry_on,
                        "sentry_mode_available": available,
                    }
                )
            )
            return

        console.print(f"\n  Sentry Mode: [{status_color}][bold]{status}[/bold][/{status_color}]")
        if not available:
            console.print(
                "  [yellow]Note: Sentry Mode not available (vehicle may not be parked)[/yellow]"
            )
        return

    cmd = "set_sentry_mode"
    _v._with_wake(lambda b, v: b.command(v, cmd, on=enable), v)
    state = "enabled" if enable else "disabled"
    render_success(f"Sentry Mode {state}")


@vehicle_app.command("windows")
def vehicle_windows(
    action: str = typer.Argument("vent", help="Action: vent or close"),
    vin: str | None = VinOption,
) -> None:
    """Vent or close all windows.

    tesla vehicle windows vent    → vent all windows ~4 cm
    tesla vehicle windows close   → close all windows
    """
    v = _v._vin(vin)
    action = action.lower()
    if action not in ("vent", "close"):
        console.print("[red]Action must be 'vent' or 'close'.[/red]")
        raise typer.Exit(1)
    # command: window_control, params: command="vent"|"close", lat=0, lon=0
    _v._with_wake(lambda b, v: b.command(v, "window_control", command=action, lat=0, lon=0), v)
    render_success(f"Windows {'vented' if action == 'vent' else 'closed'}")


@vehicle_app.command("charge-port")
def vehicle_charge_port(
    action: str = typer.Argument("open", help="Action: open, close, or stop"),
    vin: str | None = VinOption,
) -> None:
    """Control the charging port door.

    tesla vehicle charge-port open    → open the charge port door
    tesla vehicle charge-port close   → close the charge port door
    tesla vehicle charge-port stop    → stop charging (unlocks port)
    """
    v = _v._vin(vin)
    action = action.lower()
    CMD_MAP = {
        "open": "charge_port_door_open",
        "close": "charge_port_door_close",
        "stop": "charge_stop",
    }
    if action not in CMD_MAP:
        console.print("[red]Action must be 'open', 'close', or 'stop'.[/red]")
        raise typer.Exit(1)
    _v._with_wake(lambda b, v: b.command(v, CMD_MAP[action]), v)
    labels = {
        "open": "Charge port opened",
        "close": "Charge port closed",
        "stop": "Charging stopped",
    }
    render_success(labels[action])


@vehicle_app.command("valet")
def vehicle_valet(
    on: bool | None = typer.Option(None, "--on/--off", help="Enable or disable valet mode"),
    password: str = typer.Option("", "--password", "-p", help="4-digit PIN for valet mode"),
    vin: str | None = VinOption,
) -> None:
    """Show or toggle Valet Mode.

    tesla vehicle valet              # show status
    tesla vehicle valet --on --password 1234
    tesla vehicle valet --off
    """
    import json as _json

    v = _v._vin(vin)

    if on is None:
        # Show current status
        state = _v._with_wake(lambda b, v: b.get_vehicle_state(v), v)
        valet_active = state.get("valet_mode", False)
        if is_json_mode():
            console.print(_json.dumps({"valet_mode": valet_active}, indent=2))
            return
        status = "[green]ON[/green]" if valet_active else "[dim]OFF[/dim]"
        console.print(f"  Valet Mode: {status}")
        return

    _v._with_wake(lambda b, v: b.set_valet_mode(v, on=on, password=password), v)
    action = "enabled" if on else "disabled"
    if is_json_mode():
        console.print(_json.dumps({"valet_mode": on, "action": action}, indent=2))
        return
    render_success(f"Valet Mode {action}")


@vehicle_app.command("schedule-charge")
def vehicle_schedule_charge(
    time_str: str | None = typer.Argument(None, help="Charge time HH:MM (24h), e.g. 23:30"),
    off: bool = typer.Option(False, "--off", help="Disable scheduled charging"),
    vin: str | None = VinOption,
) -> None:
    """Set or disable scheduled charging.

    tesla vehicle schedule-charge 23:30   # charge at 11:30 PM
    tesla vehicle schedule-charge --off   # disable schedule
    tesla -j vehicle schedule-charge 06:00
    """
    import json as _json

    v = _v._vin(vin)

    if off:
        _v._with_wake(lambda b, v: b.set_scheduled_charging(v, enable=False, time_minutes=0), v)
        if is_json_mode():
            console.print(_json.dumps({"scheduled_charging": False}, indent=2))
            return
        render_success("Scheduled charging disabled")
        return

    if not time_str:
        # Show current schedule
        state = _v._with_wake(lambda b, v: b.get_charge_state(v), v)
        enabled = state.get("scheduled_charging_pending", False)
        sched_time = state.get("scheduled_charging_start_time")
        if is_json_mode():
            console.print(
                _json.dumps(
                    {
                        "scheduled_charging_pending": enabled,
                        "scheduled_charging_start_time": sched_time,
                    },
                    indent=2,
                )
            )
            return
        if enabled and sched_time:
            from datetime import datetime

            try:
                dt = datetime.fromtimestamp(int(sched_time), tz=datetime.UTC).strftime("%H:%M UTC")
            except Exception:
                dt = str(sched_time)
            console.print(f"  Scheduled Charging: [green]ON[/green] at {dt}")
        else:
            console.print("  Scheduled Charging: [dim]OFF[/dim]")
        return

    # Parse HH:MM → minutes since midnight
    try:
        parts = time_str.strip().split(":")
        hours, minutes = int(parts[0]), int(parts[1])
        if not (0 <= hours <= 23 and 0 <= minutes <= 59):
            raise ValueError
    except (ValueError, IndexError):
        console.print("[red]Invalid time format. Use HH:MM (24h), e.g. 23:30[/red]")
        raise typer.Exit(1)

    time_minutes = hours * 60 + minutes
    _v._with_wake(
        lambda b, v: b.set_scheduled_charging(v, enable=True, time_minutes=time_minutes), v
    )

    if is_json_mode():
        console.print(
            _json.dumps(
                {"scheduled_charging": True, "time": time_str, "time_minutes": time_minutes},
                indent=2,
            )
        )
        return
    render_success(f"Scheduled charging set to {time_str} ({time_minutes} min from midnight)")


@vehicle_app.command("homelink")
def vehicle_homelink(
    vin: str | None = VinOption,
) -> None:
    """Trigger HomeLink (garage door opener) when near home location.

    tesla vehicle homelink
    """
    import json as _json

    v = _v._vin(vin)

    # Get current GPS coordinates for the HomeLink proximity check
    drive = _v._with_wake(lambda b, v: b.get_drive_state(v), v)
    lat = drive.get("latitude", 0.0) or 0.0
    lon = drive.get("longitude", 0.0) or 0.0

    _v._with_wake(lambda b, v: b.command(v, "trigger_homelink", lat=lat, lon=lon), v)

    if is_json_mode():
        console.print(_json.dumps({"homelink": "triggered", "lat": lat, "lon": lon}, indent=2))
        return
    render_success("HomeLink triggered")


@vehicle_app.command("dashcam")
def vehicle_dashcam(
    vin: str | None = VinOption,
) -> None:
    """Save the current dashcam clip to USB storage.

    tesla vehicle dashcam
    """
    import json as _json

    v = _v._vin(vin)
    _v._with_wake(lambda b, v: b.command(v, "dashcam_save_clip"), v)

    if is_json_mode():
        console.print(_json.dumps({"dashcam_save": True}, indent=2))
        return
    render_success("Dashcam clip saved to USB storage")


@vehicle_app.command("rename")
def vehicle_rename(
    name: str = typer.Argument(..., help="New vehicle name"),
    vin: str | None = VinOption,
) -> None:
    """Rename the vehicle (requires firmware 2023.12+).

    tesla vehicle rename "My Tesla Y"
    """
    import json as _json

    v = _v._vin(vin)
    _v._with_wake(lambda b, v: b.command(v, "set_vehicle_name", vehicle_name=name), v)

    if is_json_mode():
        console.print(_json.dumps({"name": name}, indent=2))
        return
    render_success(f"Vehicle renamed to '{name}'")


@vehicle_app.command("precondition")
def vehicle_precondition(
    on: bool = typer.Argument(..., help="Enable or disable max preconditioning"),
    vin: str | None = VinOption,
) -> None:
    """Toggle max preconditioning (blast heat/cool before a trip).

    tesla vehicle precondition true
    tesla vehicle precondition false
    tesla -j vehicle precondition true
    """
    import json as _json

    v = _v._vin(vin)
    _v._with_wake(lambda b, v: b.command(v, "set_preconditioning_max", on=on), v)

    if is_json_mode():
        console.print(_json.dumps({"preconditioning_max": on}, indent=2))
        return
    status = "enabled" if on else "disabled"
    render_success(f"Max preconditioning {status}")


@vehicle_app.command("screenshot")
def vehicle_screenshot(
    vin: str | None = VinOption,
) -> None:
    """Trigger a screenshot of the vehicle's display (saves to TeslaConnect).

    tesla vehicle screenshot
    tesla -j vehicle screenshot
    """
    import json as _json

    v = _v._vin(vin)
    _v._with_wake(lambda b, v: b.command(v, "trigger_vehicle_screenshot"), v)

    if is_json_mode():
        console.print(_json.dumps({"screenshot": "triggered"}, indent=2))
        return
    render_success("Screenshot triggered — check the TeslaConnect mobile app")


@vehicle_app.command("tonneau")
def vehicle_tonneau(
    action: str = typer.Argument(..., help="Action: open|close|stop|status"),
    vin: str | None = VinOption,
) -> None:
    """Control the Cybertruck tonneau cover.

    tesla vehicle tonneau open
    tesla vehicle tonneau close
    tesla vehicle tonneau stop
    tesla vehicle tonneau status
    tesla -j vehicle tonneau status
    """
    import json as _json

    v = _v._vin(vin)
    action = action.lower()

    if action == "status":
        state = _v._with_wake(lambda b, v: b.get_vehicle_state(v), v)
        tonneau_open = state.get("tonneau_open")
        door_state = state.get("tonneau_door_state", "unknown")
        data = {
            "tonneau_open": tonneau_open,
            "door_state": door_state,
        }
        if is_json_mode():
            console.print(_json.dumps(data, indent=2, default=str))
            return
        render_dict(data, title="Tonneau Cover Status")
        return

    command_map = {
        "open": "tonneau_open",
        "close": "tonneau_close",
        "stop": "tonneau_stop",
    }
    if action not in command_map:
        from tesla_cli.cli.output import console as _console

        _console.print(f"[red]Unknown action:[/red] {action}. Use: open|close|stop|status")
        raise typer.Exit(1)

    _v._with_wake(lambda b, v: b.command(v, command_map[action]), v)

    if is_json_mode():
        console.print(_json.dumps({"tonneau": action}, indent=2))
        return
    render_success(f"Tonneau cover {action} command sent")


@vehicle_app.command("sw-update")
def vehicle_sw_update(
    watch: bool = typer.Option(
        False, "--watch", "-w", help="Watch mode: keep polling until update appears"
    ),
    interval: int = typer.Option(
        60, "--interval", "-i", help="Poll interval in minutes (watch mode)"
    ),
    notify: bool = typer.Option(
        False, "--notify", help="Send Apprise notification when update is detected"
    ),
    vin: str | None = VinOption,
) -> None:
    """Check for a pending OTA software update, or watch until one is available.

    tesla vehicle sw-update                          → one-shot check
    tesla vehicle sw-update --watch                 → poll every 60 min
    tesla vehicle sw-update --watch --interval 30   → poll every 30 min
    tesla vehicle sw-update --watch --notify        → + Apprise notification on detection
    """
    import json as _json

    v = _v._vin(vin)

    def _check_once() -> dict:
        """Fetch vehicle data and return software update info."""
        data = _v._with_wake(lambda b, v: b.get_vehicle_data(v), v)
        vs = data.get("vehicle_state", {})
        return {
            "current_version": vs.get("car_version", ""),
            "update_available": bool(
                vs.get("software_update", {}).get("status")
                in ("available", "scheduled", "installing", "downloading")
            ),
            "update_status": vs.get("software_update", {}).get("status", ""),
            "update_version": vs.get("software_update", {}).get("version", ""),
            "update_download_pct": vs.get("software_update", {}).get("download_perc", 0),
            "update_install_perc": vs.get("software_update", {}).get("install_perc", 0),
            "expected_duration_sec": vs.get("software_update", {}).get("expected_duration_sec", 0),
            "scheduled_time_ms": vs.get("software_update", {}).get("scheduled_time_ms", 0),
        }

    if not watch:
        info = _check_once()
        if is_json_mode():
            console.print(_json.dumps(info, indent=2))
            return
        from rich.panel import Panel
        from rich.table import Table as RTable

        t = RTable(show_header=False, box=None, padding=(0, 2))
        t.add_column("Key", style="dim", width=28)
        t.add_column("Value", style="bold")
        t.add_row("Current Version", info["current_version"])
        if info["update_available"]:
            t.add_row(
                "Update Status", f"[bold yellow]{info['update_status'].upper()}[/bold yellow]"
            )
            t.add_row("Update Version", f"[bold green]{info['update_version']}[/bold green]")
            if info["update_download_pct"]:
                t.add_row("Download", f"{info['update_download_pct']}%")
            if info["update_install_perc"]:
                t.add_row("Install", f"{info['update_install_perc']}%")
        else:
            t.add_row("Update Status", "[dim]No update pending[/dim]")
        console.print(Panel(t, title="[bold]Software Update Status[/bold]", border_style="cyan"))
        return

    # ── Watch mode ────────────────────────────────────────────────────────────
    import signal

    console.print(
        f"[dim]Watching for OTA updates every {interval} min. Press Ctrl+C to stop.[/dim]\n"
    )
    poll_secs = interval * 60
    try:
        while True:
            try:
                info = _check_once()
            except Exception as exc:
                console.print(f"[yellow]Poll error: {exc}[/yellow]")
                info = {}

            ts = __import__("datetime").datetime.now().strftime("%H:%M:%S")
            if info.get("update_available"):
                ver = info.get("update_version", "")
                status = info.get("update_status", "")
                console.print(
                    f"[bold green]✓ [{ts}] Update detected![/bold green] "
                    f"Version [bold]{ver}[/bold] — {status}"
                )
                if notify:
                    try:
                        import apprise

                        cfg = _v.load_config()
                        urls = getattr(cfg.notifications, "apprise_urls", []) or []
                        if urls:
                            a = apprise.Apprise()
                            for u in urls:
                                a.add(u)
                            a.notify(
                                title="Tesla OTA Update Available",
                                body=f"Version {ver} is {status} on your Tesla.",
                            )
                            console.print("[dim]Apprise notification sent.[/dim]")
                    except Exception as exc:
                        console.print(f"[yellow]Notify error: {exc}[/yellow]")
                break
            else:
                cur = info.get("current_version", "—")
                console.print(
                    f"[dim][{ts}] No update — current: {cur}. Next check in {interval} min.[/dim]"
                )

            _v.time.sleep(poll_secs)
    except (KeyboardInterrupt, signal.Signals):
        console.print("\n[dim]Stopped.[/dim]")


@vehicle_app.command("speed-limit")
def vehicle_speed_limit(
    limit_mph: int | None = typer.Option(None, "--limit", help="Set speed limit in mph (50–90)"),
    pin: str | None = typer.Option(None, "--pin", help="4-digit speed limit PIN"),
    on: bool = typer.Option(False, "--on", help="Activate speed limit mode (requires --pin)"),
    off: bool = typer.Option(False, "--off", help="Deactivate speed limit mode (requires --pin)"),
    clear: bool = typer.Option(
        False, "--clear", help="Clear the saved speed limit PIN (requires --pin)"
    ),
    vin: str | None = VinOption,
) -> None:
    """Show or control Speed Limit Mode.

    tesla vehicle speed-limit                          → show current status
    tesla vehicle speed-limit --limit 65               → set limit to 65 mph
    tesla vehicle speed-limit --on --pin 1234          → activate speed limit mode
    tesla vehicle speed-limit --off --pin 1234         → deactivate speed limit mode
    tesla vehicle speed-limit --clear --pin 1234       → clear saved PIN
    """
    import json as _json

    v = _v._vin(vin)

    if on:
        if not pin:
            console.print("[red]--pin is required to activate speed limit mode.[/red]")
            raise typer.Exit(1)
        _v._with_wake(lambda b, v: b.command(v, "speed_limit_activate", pin=pin), v)
        render_success("Speed Limit Mode activated")
        return

    if off:
        if not pin:
            console.print("[red]--pin is required to deactivate speed limit mode.[/red]")
            raise typer.Exit(1)
        _v._with_wake(lambda b, v: b.command(v, "speed_limit_deactivate", pin=pin), v)
        render_success("Speed Limit Mode deactivated")
        return

    if clear:
        if not pin:
            console.print("[red]--pin is required to clear the speed limit PIN.[/red]")
            raise typer.Exit(1)
        _v._with_wake(lambda b, v: b.command(v, "speed_limit_clear_pin", pin=pin), v)
        render_success("Speed Limit PIN cleared")
        return

    if limit_mph is not None:
        if not (50 <= limit_mph <= 90):
            console.print("[red]Speed limit must be between 50 and 90 mph.[/red]")
            raise typer.Exit(1)
        _v._with_wake(lambda b, v: b.command(v, "speed_limit_set_limit", limit_mph=limit_mph), v)
        render_success(f"Speed limit set to {limit_mph} mph")
        return

    # ── Status (no flags) ────────────────────────────────────────────────────
    data = _v._with_wake(lambda b, v: b.get_vehicle_state(v), v)
    slm = data.get("speed_limit_mode", {}) if isinstance(data, dict) else {}
    active = slm.get("active", False)
    current_limit = slm.get("current_limit_mph")
    max_limit = slm.get("max_limit_mph")
    min_limit = slm.get("min_limit_mph")
    pin_set = slm.get("pin_code_set", False)

    if is_json_mode():
        console.print(
            _json.dumps(
                {
                    "active": active,
                    "current_limit_mph": current_limit,
                    "max_limit_mph": max_limit,
                    "min_limit_mph": min_limit,
                    "pin_code_set": pin_set,
                },
                indent=2,
            )
        )
        return

    from rich.panel import Panel
    from rich.table import Table as RTable

    t = RTable(show_header=False, box=None, padding=(0, 2))
    t.add_column("Key", style="dim", width=24)
    t.add_column("Value", style="bold")
    t.add_row("Status", "[bold red]Active[/bold red]" if active else "[dim]Inactive[/dim]")
    if current_limit:
        t.add_row("Current Limit", f"{current_limit} mph")
    if max_limit:
        t.add_row("Max Limit", f"{max_limit} mph")
    if min_limit:
        t.add_row("Min Limit", f"{min_limit} mph")
    t.add_row("PIN Set", "Yes" if pin_set else "No")
    console.print(Panel(t, title="[bold]Speed Limit Mode[/bold]", border_style="red"))


@vehicle_app.command("bio")
def vehicle_bio(vin: str | None = VinOption) -> None:
    """Comprehensive single-screen vehicle profile — all states at once.

    tesla vehicle bio
    tesla -j vehicle bio | jq '.battery.battery_level'
    """
    import json as _json

    v = _v._vin(vin)

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()
    ) as p:
        p.add_task("Loading vehicle profile...", total=None)
        data = _v._with_wake(lambda b, v: b.get_vehicle_data(v), v)

    vs = data.get("vehicle_state", {}) or {}
    cs = data.get("charge_state", {}) or {}
    clim = data.get("climate_state", {}) or {}
    vcfg = data.get("vehicle_config", {}) or {}

    if is_json_mode():
        console.print(
            _json.dumps(
                {
                    "vin": data.get("vin", v),
                    "name": data.get("display_name") or data.get("vehicle_name", ""),
                    "state": data.get("state", ""),
                    "identity": {
                        "vin": data.get("vin", v),
                        "model": vcfg.get("car_type", ""),
                        "color": vcfg.get("exterior_color", ""),
                        "sw_version": vs.get("car_version", ""),
                    },
                    "battery": {
                        "battery_level": cs.get("battery_level"),
                        "battery_range": cs.get("battery_range"),
                        "charging_state": cs.get("charging_state"),
                        "charge_limit_soc": cs.get("charge_limit_soc"),
                    },
                    "climate": {
                        "is_climate_on": clim.get("is_climate_on"),
                        "inside_temp": clim.get("inside_temp"),
                        "outside_temp": clim.get("outside_temp"),
                    },
                    "drive": {
                        "locked": vs.get("locked"),
                        "sentry_mode": vs.get("sentry_mode"),
                        "valet_mode": vs.get("valet_mode"),
                        "odometer": vs.get("odometer"),
                        "sw_version": vs.get("car_version"),
                    },
                    "scheduling": {
                        "scheduled_charging_pending": cs.get("scheduled_charging_pending"),
                        "scheduled_charging_start_time": cs.get("scheduled_charging_start_time"),
                        "scheduled_departure_time": cs.get("scheduled_departure_time"),
                    },
                },
                indent=2,
                default=str,
            )
        )
        return

    from rich.panel import Panel as _Panel
    from rich.table import Table as _Table

    display_name = data.get("display_name") or data.get("vehicle_name") or v
    state_txt = data.get("state", "unknown")

    def _row(t: _Table, label: str, value: object, color: str = "white") -> None:
        if value is None or str(value) in ("None", ""):
            t.add_row(f"[dim]{label}[/dim]", "[dim]—[/dim]")
        else:
            t.add_row(f"[dim]{label}[/dim]", f"[{color}]{value}[/{color}]")

    def _kv() -> _Table:
        t = _Table(show_header=False, box=None, padding=(0, 2), expand=True)
        t.add_column("k", width=26)
        t.add_column("v")
        return t

    # Identity
    t_id = _kv()
    _row(t_id, "VIN", data.get("vin", v), "cyan")
    _row(t_id, "Model", vcfg.get("car_type", ""), "cyan")
    _row(t_id, "Color", vcfg.get("exterior_color", ""))
    _row(t_id, "Name", display_name, "bold")
    _row(t_id, "SW Version", vs.get("car_version", ""))
    _row(t_id, "State", state_txt, "green" if state_txt == "online" else "yellow")

    # Battery
    lvl = cs.get("battery_level")
    rng = cs.get("battery_range")
    cs_txt = cs.get("charging_state", "")
    lim = cs.get("charge_limit_soc")
    t_bat = _kv()
    bc = "green" if (lvl or 0) >= 50 else "yellow" if (lvl or 0) >= 20 else "red"
    _row(t_bat, "Level", f"{lvl}%" if lvl is not None else None, bc)
    _row(t_bat, "Range", f"{rng} mi" if rng else None)
    _row(t_bat, "Charging", cs_txt, "green" if cs_txt == "Charging" else "dim")
    _row(t_bat, "Charge Limit", f"{lim}%" if lim else None)

    # Climate
    hvac_on = clim.get("is_climate_on")
    inside = clim.get("inside_temp")
    outside = clim.get("outside_temp")
    t_clim = _kv()
    _row(t_clim, "HVAC", "ON" if hvac_on else "OFF", "green" if hvac_on else "dim")
    _row(t_clim, "Inside temp", f"{inside}°C" if inside is not None else None)
    _row(t_clim, "Outside temp", f"{outside}°C" if outside is not None else None)

    # Drive state
    locked = vs.get("locked")
    sentry = vs.get("sentry_mode")
    valet = vs.get("valet_mode")
    odometer = vs.get("odometer")
    t_drv = _kv()
    _row(t_drv, "Locked", "LOCKED" if locked else "UNLOCKED", "green" if locked else "red")
    _row(t_drv, "Sentry", "ON" if sentry else "off", "yellow" if sentry else "dim")
    _row(t_drv, "Valet", "ON" if valet else "off", "yellow" if valet else "dim")
    _row(t_drv, "Odometer", f"{odometer:.1f} mi" if odometer else None)

    # Scheduling
    sched_pending = cs.get("scheduled_charging_pending")
    sched_time = cs.get("scheduled_charging_start_time")
    dep_time = cs.get("scheduled_departure_time")
    t_sched = _kv()
    if sched_pending and sched_time:
        try:
            from datetime import UTC, datetime

            dt_s = datetime.fromtimestamp(int(sched_time), tz=UTC).strftime("%H:%M UTC")
        except Exception:
            dt_s = str(sched_time)
        _row(t_sched, "Scheduled Charge", dt_s, "cyan")
    else:
        _row(t_sched, "Scheduled Charge", "Not set")
    if dep_time:
        try:
            from datetime import UTC, datetime  # noqa: F811

            dt_d = datetime.fromtimestamp(int(dep_time), tz=UTC).strftime("%H:%M UTC")
        except Exception:
            dt_d = str(dep_time)
        _row(t_sched, "Departure", dt_d, "cyan")

    console.print()
    console.print(_Panel(t_id, title=f"[bold cyan]{display_name}[/bold cyan]", border_style="cyan"))
    console.print(_Panel(t_bat, title="[bold]Battery[/bold]", border_style="green"))
    console.print(_Panel(t_clim, title="[bold]Climate[/bold]", border_style="blue"))
    console.print(_Panel(t_drv, title="[bold]Drive State[/bold]", border_style="yellow"))
    console.print(_Panel(t_sched, title="[bold]Scheduling[/bold]", border_style="dim"))


_CABIN_LEVEL_MAP: dict[str, dict] = {
    "FAN_ONLY": {"on": True, "fan_only": True},
    "NO_AC": {"on": True, "fan_only": False},
    "CHARGE_ON": {"on": True, "fan_only": False},
}


@vehicle_app.command("cabin-protection")
def vehicle_cabin_protection(
    on: bool | None = typer.Option(
        None, "--on/--off", help="Enable or disable cabin overheat protection"
    ),
    level: str | None = typer.Option(
        None,
        "--level",
        help="Protection level: FAN_ONLY | NO_AC | CHARGE_ON",
    ),
    vin: str | None = VinOption,
) -> None:
    """Show or control Cabin Overheat Protection.

    tesla vehicle cabin-protection              → show current status
    tesla vehicle cabin-protection --on         → enable protection
    tesla vehicle cabin-protection --off        → disable protection
    tesla vehicle cabin-protection --level FAN_ONLY
    tesla vehicle cabin-protection --level NO_AC
    tesla -j vehicle cabin-protection
    """
    import json as _json

    v = _v._vin(vin)
    VALID_LEVELS = tuple(_CABIN_LEVEL_MAP.keys())

    # ── Status (no flags) ────────────────────────────────────────────────────
    if on is None and level is None:
        data = _v._with_wake(lambda b, v: b.get_climate_state(v), v)
        cop = data.get("cabin_overheat_protection", "Unknown")
        cop_active = data.get("cabin_overheat_protection_actively_cooling", False)
        if is_json_mode():
            console.print(
                _json.dumps(
                    {
                        "cabin_overheat_protection": cop,
                        "actively_cooling": cop_active,
                    },
                    indent=2,
                )
            )
            return
        sc = "green" if cop not in ("Off", "Unknown", None) else "dim"
        console.print(f"\n  Cabin Overheat Protection: [{sc}][bold]{cop}[/bold][/{sc}]")
        if cop_active:
            console.print("  [yellow]Currently actively cooling[/yellow]")
        return

    # ── --level flag ─────────────────────────────────────────────────────────
    if level is not None:
        lu = level.upper()
        if lu not in VALID_LEVELS:
            console.print(
                f"[red]Invalid level '{level}'. Choose from: {', '.join(VALID_LEVELS)}[/red]"
            )
            raise typer.Exit(1)
        params = _CABIN_LEVEL_MAP[lu]
        _v._with_wake(lambda b, v: b.command(v, "set_cabin_overheat_protection", **params), v)
        if is_json_mode():
            console.print(_json.dumps({"cabin_overheat_protection": lu, **params}, indent=2))
            return
        render_success(f"Cabin Overheat Protection set to {lu}")
        return

    # ── --on / --off ─────────────────────────────────────────────────────────
    _v._with_wake(
        lambda b, v: b.command(v, "set_cabin_overheat_protection", on=bool(on), fan_only=False), v
    )
    if is_json_mode():
        console.print(_json.dumps({"cabin_overheat_protection": "on" if on else "off"}, indent=2))
        return
    render_success(f"Cabin Overheat Protection {'enabled' if on else 'disabled'}")


@vehicle_app.command("schedule-update")
def vehicle_schedule_update(
    delay: int = typer.Option(
        0, "--delay", "-d", help="Delay in minutes before installing (0 = now)"
    ),
    vin: str | None = VinOption,
) -> None:
    """Schedule a pending OTA software update to install.

    \b
    tesla vehicle schedule-update            # install immediately
    tesla vehicle schedule-update --delay 60 # install in 60 minutes
    tesla -j vehicle schedule-update
    """
    import json as _json

    cfg = _v.load_config()
    v = _v.resolve_vin(cfg, vin)
    b = _v.get_vehicle_backend(cfg)

    offset_sec = delay * 60
    result = b.schedule_software_update(v, offset_sec=offset_sec)

    if is_json_mode():
        console.print(_json.dumps({"ok": bool(result), "delay_min": delay, "vin": v}))
        return

    if result:
        msg = "immediately" if delay == 0 else f"in {delay} minutes"
        render_success(f"Software update scheduled to install [bold]{msg}[/bold].")
    else:
        console.print("[red]Failed to schedule software update.[/red]")
        raise typer.Exit(1)


@vehicle_app.command("invite")
def vehicle_invite(vin: str | None = VinOption) -> None:
    """Create a new driver invitation link."""
    from tesla_cli.core.exceptions import BackendNotSupportedError

    v = _v._vin(vin)
    backend = _v._backend()
    try:
        data = backend.create_invitation(v)
    except BackendNotSupportedError as exc:
        console.print(f"[yellow]{exc}[/yellow]")
        raise typer.Exit(1)
    render_dict(data, title="New Invitation")


@vehicle_app.command("invitations")
def vehicle_invitations(vin: str | None = VinOption) -> None:
    """List current driver invitations."""
    from tesla_cli.core.exceptions import BackendNotSupportedError

    v = _v._vin(vin)
    backend = _v._backend()
    try:
        invitations = backend.get_invitations(v)
    except BackendNotSupportedError as exc:
        console.print(f"[yellow]{exc}[/yellow]")
        raise typer.Exit(1)
    if not invitations:
        render_success("No active invitations")
        return
    render_table(
        invitations,
        columns=["id", "owner", "state", "created_at"],
        title="Driver Invitations",
    )


@vehicle_app.command("revoke-invite")
def vehicle_revoke_invite(
    invitation_id: str = typer.Argument(..., help="Invitation ID to revoke"),
    vin: str | None = VinOption,
) -> None:
    """Revoke a driver invitation."""
    from tesla_cli.core.exceptions import BackendNotSupportedError

    v = _v._vin(vin)
    backend = _v._backend()
    try:
        backend.revoke_invitation(v, invitation_id)
    except BackendNotSupportedError as exc:
        console.print(f"[yellow]{exc}[/yellow]")
        raise typer.Exit(1)
    render_success(f"Invitation {invitation_id} revoked")
