"""Fleet Telemetry commands: tesla telemetry install/start/stop/status/configure/logs."""

from __future__ import annotations

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn

from tesla_cli.cli.output import console, is_json_mode, render_dict, render_success
from tesla_cli.core.config import load_config, save_config

telemetry_app = typer.Typer(
    name="telemetry",
    help="Self-hosted fleet-telemetry server management.",
)


def _stack():
    from pathlib import Path

    from tesla_cli.infra.fleet_telemetry_stack import FleetTelemetryStack

    cfg = load_config()
    stack_dir = Path(cfg.telemetry.stack_dir) if cfg.telemetry.stack_dir else None
    return FleetTelemetryStack(stack_dir)


@telemetry_app.command("install")
def telemetry_install(
    hostname: str = typer.Argument(..., help="FQDN of this machine (e.g. telemetry.example.com)"),
    port: int = typer.Option(4443, "--port", "-p", help="Port for fleet-telemetry server"),
    force: bool = typer.Option(False, "--force", help="Reinstall even if already installed"),
) -> None:
    """Install the self-hosted fleet-telemetry Docker stack with TLS certificates.

    Generates a self-signed CA + server certificate, writes Docker Compose
    and config files, then pulls and starts the fleet-telemetry container.

    tesla telemetry install telemetry.example.com
    tesla telemetry install telemetry.example.com --port 4443
    """
    from tesla_cli.infra.fleet_telemetry_stack import FleetTelemetryStack

    stack = FleetTelemetryStack()
    stack.check_docker()
    stack.check_docker_compose()

    console.print(
        f"[bold]Installing fleet-telemetry stack[/bold]\n"
        f"  Hostname: [cyan]{hostname}[/cyan]\n"
        f"  Port:     [cyan]{port}[/cyan]\n"
        f"  Dir:      [dim]{stack.stack_dir}[/dim]\n"
    )

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()
    ) as p:
        p.add_task("Generating TLS certificates + starting container...", total=None)
        result = stack.install(hostname=hostname, port=port, force=force)

    cfg = load_config()
    cfg.telemetry.enabled = True
    cfg.telemetry.managed = True
    cfg.telemetry.hostname = hostname
    cfg.telemetry.port = port
    cfg.telemetry.stack_dir = result["stack_dir"]
    cfg.telemetry.ca_cert_path = result["ca_cert_path"]
    cfg.telemetry.server_cert_path = result["server_cert_path"]
    cfg.telemetry.server_key_path = result["server_key_path"]
    save_config(cfg)

    status = "[green]healthy[/green]" if result["healthy"] else "[yellow]starting[/yellow]"
    render_success(
        f"Fleet-telemetry installed and running ({status}).\n\n"
        f"  CA cert:     {result['ca_cert_path']}\n"
        f"  Server cert: {result['server_cert_path']}\n\n"
        f"Next: configure your vehicle to stream to this server:\n"
        f"  [bold]tesla telemetry configure[/bold]"
    )


@telemetry_app.command("start")
def telemetry_start() -> None:
    """Start the fleet-telemetry Docker stack.

    tesla telemetry start
    """
    stack = _stack()
    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()
    ) as p:
        p.add_task("Starting fleet-telemetry...", total=None)
        stack.start()
    render_success("Fleet-telemetry started.")


@telemetry_app.command("stop")
def telemetry_stop() -> None:
    """Stop the fleet-telemetry Docker stack.

    tesla telemetry stop
    """
    stack = _stack()
    stack.stop()
    render_success("Fleet-telemetry stopped.")


@telemetry_app.command("restart")
def telemetry_restart() -> None:
    """Restart the fleet-telemetry Docker stack.

    tesla telemetry restart
    """
    stack = _stack()
    stack.restart()
    render_success("Fleet-telemetry restarted.")


@telemetry_app.command("status")
def telemetry_status(
    vin: str | None = typer.Option(
        None, "--vin", "-v", help="VIN or alias (uses default if omitted)"
    ),
) -> None:
    """Show fleet-telemetry server status and vehicle streaming config.

    tesla telemetry status
    tesla telemetry status --vin <VIN>
    """
    cfg = load_config()
    stack = _stack()

    server_info: dict = {
        "enabled": cfg.telemetry.enabled,
        "hostname": cfg.telemetry.hostname or "(not configured)",
        "port": cfg.telemetry.port,
        "managed": cfg.telemetry.managed,
        "stack_dir": cfg.telemetry.stack_dir or "(not installed)",
    }

    if cfg.telemetry.managed and stack.is_installed():
        server_info["services"] = stack.status()
        server_info["running"] = stack.is_running()

    vehicle_config: dict | None = None
    if vin or cfg.general.default_vin:
        from tesla_cli.core.backends.fleet_telemetry import load_fleet_telemetry_backend
        from tesla_cli.core.config import resolve_vin
        from tesla_cli.core.exceptions import ConfigurationError

        v = resolve_vin(cfg, vin)
        try:
            backend = load_fleet_telemetry_backend()
            with Progress(
                SpinnerColumn(),
                TextColumn("{task.description}"),
                transient=True,
                disable=is_json_mode(),
            ) as p:
                p.add_task(f"Fetching streaming config for {v}...", total=None)
                vehicle_config = backend.get_streaming_config(v)
        except ConfigurationError as exc:
            console.print(f"[yellow]Vehicle config unavailable:[/yellow] {exc}")

    data = {"server": server_info}
    if vehicle_config is not None:
        data["vehicle_streaming_config"] = vehicle_config

    render_dict(data, title="Fleet Telemetry Status")


@telemetry_app.command("configure")
def telemetry_configure(
    vin: str | None = typer.Option(
        None, "--vin", "-v", help="VIN or alias (uses default if omitted)"
    ),
    fields: str = typer.Option(
        "",
        "--fields",
        "-f",
        help="Comma-separated field names to stream (default: standard set)",
    ),
) -> None:
    """Configure a vehicle to stream telemetry to your self-hosted server.

    Sends the fleet telemetry config to Tesla's Fleet API so the vehicle
    knows where to connect and which fields to send.

    tesla telemetry configure
    tesla telemetry configure --vin <VIN>
    tesla telemetry configure --fields BatteryLevel,VehicleSpeed,Location
    """
    from tesla_cli.core.backends.fleet_telemetry import load_fleet_telemetry_backend, read_ca_cert
    from tesla_cli.core.config import resolve_vin
    from tesla_cli.core.exceptions import ConfigurationError

    cfg = load_config()

    if not cfg.telemetry.hostname:
        console.print(
            "[red]Fleet-telemetry hostname not configured.[/red]\n"
            "Run: [bold]tesla telemetry install <hostname>[/bold]"
        )
        raise typer.Exit(1)

    v = resolve_vin(cfg, vin)

    try:
        ca_cert_pem = read_ca_cert(cfg.telemetry.ca_cert_path)
    except ConfigurationError as exc:
        console.print(f"[red]Certificate error:[/red] {exc}")
        raise typer.Exit(1)

    field_dict: dict | None = None
    if fields:
        from tesla_cli.core.backends.fleet_telemetry import _default_fields

        all_defaults = _default_fields()
        field_dict = {
            name.strip(): {"interval_seconds": 10} for name in fields.split(",") if name.strip()
        }
        # Validate field names (warn about unknowns but proceed)
        unknown = [k for k in field_dict if k not in all_defaults]
        if unknown:
            console.print(
                f"[yellow]Unknown field names (proceeding anyway):[/yellow] {', '.join(unknown)}"
            )

    try:
        backend = load_fleet_telemetry_backend()
        with Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            transient=True,
            disable=is_json_mode(),
        ) as p:
            p.add_task(f"Configuring telemetry for {v}...", total=None)
            result = backend.configure_streaming(
                vin=v,
                hostname=cfg.telemetry.hostname,
                port=cfg.telemetry.port,
                ca_cert=ca_cert_pem,
                fields=field_dict,
            )
    except ConfigurationError as exc:
        console.print(f"[red]Configuration error:[/red] {exc}")
        raise typer.Exit(1)
    except Exception as exc:
        console.print(f"[red]API error:[/red] {exc}")
        raise typer.Exit(1)

    render_success(
        f"Vehicle {v} configured to stream to {cfg.telemetry.hostname}:{cfg.telemetry.port}"
    )
    if result:
        render_dict(result, title="API Response")


@telemetry_app.command("stop-streaming")
def telemetry_stop_streaming(
    vin: str | None = typer.Option(
        None, "--vin", "-v", help="VIN or alias (uses default if omitted)"
    ),
) -> None:
    """Stop a vehicle from streaming telemetry (delete streaming config).

    tesla telemetry stop-streaming
    tesla telemetry stop-streaming --vin <VIN>
    """
    from tesla_cli.core.backends.fleet_telemetry import load_fleet_telemetry_backend
    from tesla_cli.core.config import resolve_vin
    from tesla_cli.core.exceptions import ConfigurationError

    cfg = load_config()
    v = resolve_vin(cfg, vin)

    try:
        backend = load_fleet_telemetry_backend()
        with Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            transient=True,
            disable=is_json_mode(),
        ) as p:
            p.add_task(f"Removing streaming config for {v}...", total=None)
            backend.delete_streaming_config(v)
    except ConfigurationError as exc:
        console.print(f"[red]Configuration error:[/red] {exc}")
        raise typer.Exit(1)
    except Exception as exc:
        console.print(f"[red]API error:[/red] {exc}")
        raise typer.Exit(1)

    render_success(f"Streaming config removed for {v}.")


@telemetry_app.command("logs")
def telemetry_logs(
    lines: int = typer.Option(100, "--lines", "-n", help="Number of log lines to show"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
) -> None:
    """Show fleet-telemetry server logs.

    tesla telemetry logs
    tesla telemetry logs --follow
    tesla telemetry logs --lines 50
    """
    stack = _stack()

    if follow:
        proc = stack.logs(lines=lines, follow=True)
        try:
            for line in proc.stdout or []:
                console.print(line, end="")
        except KeyboardInterrupt:
            proc.terminate()
            console.print("\n[dim]Log stream stopped.[/dim]")
    else:
        result = stack.logs(lines=lines, follow=False)
        output = result.stdout or ""
        if output:
            console.print(output)
        else:
            console.print("[dim]No log output.[/dim]")
