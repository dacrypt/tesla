"""serve command: tesla serve — launch local API server + web dashboard."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path

import typer

from tesla_cli.cli.output import console

serve_app = typer.Typer(name="serve", help="Launch local API server and web dashboard.")

_DEFAULT_PID_FILE = Path.home() / ".tesla-cli" / "server.pid"
_DEFAULT_PORT = 8080
_DEFAULT_HOST = "127.0.0.1"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _pid_file_path() -> Path:
    """Return the PID file path from config (or default)."""
    try:
        from tesla_cli.core.config import load_config

        return Path(load_config().server.pid_file)
    except Exception:  # noqa: BLE001
        return _DEFAULT_PID_FILE


def _read_pid() -> int | None:
    pf = _pid_file_path()
    if pf.exists():
        try:
            return int(pf.read_text().strip())
        except (ValueError, OSError):
            return None
    return None


def _is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _write_pid(pid: int) -> None:
    pf = _pid_file_path()
    pf.parent.mkdir(parents=True, exist_ok=True)
    pf.write_text(str(pid))


def _clear_pid() -> None:
    pf = _pid_file_path()
    if pf.exists():
        pf.unlink()


# ── Service file generation ───────────────────────────────────────────────────


def _systemd_unit(exec_path: str, port: int, host: str) -> str:
    return f"""\
[Unit]
Description=tesla-cli API server
After=network.target

[Service]
Type=simple
ExecStart={exec_path} serve --no-open --host {host} --port {port}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
"""


def _launchd_plist(exec_path: str, port: int, host: str) -> str:
    return f"""\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>          <string>com.tesla-cli.server</string>
  <key>ProgramArguments</key>
  <array>
    <string>{exec_path}</string>
    <string>serve</string>
    <string>--no-open</string>
    <string>--host</string><string>{host}</string>
    <string>--port</string><string>{port}</string>
  </array>
  <key>RunAtLoad</key>      <true/>
  <key>KeepAlive</key>      <true/>
  <key>StandardOutPath</key><string>{Path.home()}/.tesla-cli/server.log</string>
  <key>StandardErrorPath</key><string>{Path.home()}/.tesla-cli/server.log</string>
</dict>
</plist>
"""


@serve_app.command("install-service")
def serve_install_service(
    platform: str = typer.Option(
        "",
        "--platform",
        help="Service platform: 'systemd' or 'launchd'. Auto-detected if omitted.",
    ),
    port: int = typer.Option(_DEFAULT_PORT, "--port", "-p", help="Port for the service"),
    host: str = typer.Option(_DEFAULT_HOST, "--host", help="Host for the service"),
    print_only: bool = typer.Option(
        False,
        "--print",
        help="Print the service file without installing",
    ),
) -> None:
    """Generate and install a systemd (Linux) or launchd (macOS) service file.

    \b
    tesla serve install-service               # auto-detect platform
    tesla serve install-service --platform systemd
    tesla serve install-service --platform launchd
    tesla serve install-service --print       # preview without installing
    """
    import platform as _platform
    import shutil

    # Auto-detect
    if not platform:
        system = _platform.system().lower()
        if system == "darwin":
            platform = "launchd"
        elif system == "linux":
            platform = "systemd"
        else:
            console.print(
                f"[red]Unsupported platform: {system}. Use --platform systemd or launchd.[/red]"
            )
            raise typer.Exit(1)

    exec_path = shutil.which("tesla") or sys.executable + " -m tesla_cli"

    if platform == "systemd":
        content = _systemd_unit(exec_path, port, host)
        dest = Path.home() / ".config" / "systemd" / "user" / "tesla-cli.service"

        if print_only:
            console.print(content)
            return

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)
        console.print(
            f"[green]✓[/green] Systemd service installed: [bold]{dest}[/bold]\n\n"
            "  Enable and start:\n"
            "  [bold]systemctl --user daemon-reload[/bold]\n"
            "  [bold]systemctl --user enable --now tesla-cli[/bold]\n\n"
            "  View logs:\n"
            "  [bold]journalctl --user -u tesla-cli -f[/bold]"
        )

    elif platform == "launchd":
        content = _launchd_plist(exec_path, port, host)
        dest = Path.home() / "Library" / "LaunchAgents" / "com.tesla-cli.server.plist"

        if print_only:
            console.print(content)
            return

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)
        console.print(
            f"[green]✓[/green] LaunchAgent installed: [bold]{dest}[/bold]\n\n"
            "  Load now (starts on login automatically):\n"
            f"  [bold]launchctl load {dest}[/bold]\n\n"
            "  Unload:\n"
            f"  [bold]launchctl unload {dest}[/bold]"
        )

    else:
        console.print(f"[red]Unknown platform: {platform!r}. Use 'systemd' or 'launchd'.[/red]")
        raise typer.Exit(1)


# ── Subcommands ───────────────────────────────────────────────────────────────


@serve_app.command("stop")
def serve_stop() -> None:
    """Stop a running background server daemon.

    \b
    tesla serve stop
    """
    pid = _read_pid()
    if pid is None:
        console.print("[yellow]No running server found (no PID file).[/yellow]")
        raise typer.Exit(1)

    if not _is_running(pid):
        console.print(f"[yellow]Server PID {pid} is not running. Cleaning up PID file.[/yellow]")
        _clear_pid()
        raise typer.Exit(1)

    try:
        os.kill(pid, signal.SIGTERM)
        _clear_pid()
        console.print(f"[green]✓[/green] Server (PID {pid}) stopped.")
    except OSError as e:
        console.print(f"[red]Failed to stop server: {e}[/red]")
        raise typer.Exit(1)


@serve_app.command("status")
def serve_status(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Show whether the background server daemon is running.

    \b
    tesla serve status
    tesla serve status --json
    """
    import json as _json

    pid = _read_pid()
    running = pid is not None and _is_running(pid)

    if json_output:
        result: dict = {"running": running}
        if running and pid:
            result["pid"] = pid
        console.print(_json.dumps(result))
        return

    if running:
        console.print(f"[green]●[/green] Server is running (PID {pid})")
        console.print(
            f"  [dim]Dashboard:[/dim] [bold cyan]http://127.0.0.1:{_DEFAULT_PORT}/[/bold cyan]\n"
            f"  Stop with: [bold]tesla serve stop[/bold]"
        )
    else:
        if pid:
            _clear_pid()
        console.print("[dim]○ Server is not running.[/dim]")
        console.print("  Start with: [bold]tesla serve[/bold] or [bold]tesla serve --daemon[/bold]")


# ── Main serve command ────────────────────────────────────────────────────────


@serve_app.callback(invoke_without_command=True)
def serve(
    ctx: typer.Context,
    port: int = typer.Option(_DEFAULT_PORT, "--port", "-p", help="Port to listen on"),
    host: str = typer.Option(
        _DEFAULT_HOST, "--host", help="Host to bind (127.0.0.1 = localhost only)"
    ),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="Open browser on start"),
    reload: bool = typer.Option(False, "--reload", help="Auto-reload on code changes (dev mode)"),
    vin: str | None = typer.Option(None, "--vin", "-v", help="VIN or alias to serve"),
    daemon: bool = typer.Option(
        False, "--daemon", "-d", help="Run server in background (detached)"
    ),
    api_key: str | None = typer.Option(
        None, "--api-key", help="Require this key on all /api/* requests"
    ),
    build_ui: bool = typer.Option(
        False, "--build-ui", help="Run npm build in ui/ before starting (implies --serve-ui)"
    ),
    serve_ui: bool = typer.Option(
        False, "--serve-ui", help="Serve React app from ui/dist/ on the same port"
    ),
) -> None:
    """Start the tesla-cli API server.

    \b
    tesla serve                          # localhost:8080, serves ui/dist/ if built
    tesla serve --build-ui               # build React app first, then serve
    tesla serve --port 3000              # custom port
    tesla serve --host 0.0.0.0           # LAN-accessible (add --api-key for security)
    tesla serve --no-open                # headless
    tesla serve --vin mycar              # specific vehicle
    tesla serve --daemon                 # run in background
    tesla serve --api-key s3cr3t         # require API key on all /api/* requests
    tesla serve stop                     # stop background daemon
    tesla serve status                   # check daemon status

    API docs at http://localhost:<PORT>/api/docs
    """
    if ctx.invoked_subcommand is not None:
        return

    # ── Build UI if requested ────────────────────────────────────────────────
    if build_ui:
        # Walk up from src/tesla_cli/commands/ to project root, then into ui/
        _here = Path(__file__).resolve().parent
        for _candidate in [_here.parent.parent.parent / "ui", Path.cwd() / "ui"]:
            if (_candidate / "package.json").exists():
                ui_dir = _candidate
                break
        else:
            console.print("[red]ui/ directory not found.[/red] Cannot build frontend.")
            raise typer.Exit(1)
        console.print("[dim]Building React UI...[/dim]")
        result = subprocess.run(
            ["npm", "run", "build"],
            cwd=ui_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            console.print(f"[red]UI build failed:[/red]\n{result.stderr}")
            raise typer.Exit(1)
        console.print("[green]UI built successfully.[/green]")

    # Persist --api-key into config if provided
    if api_key:
        try:
            from tesla_cli.core.config import load_config, save_config

            cfg = load_config()
            cfg.server.api_key = api_key
            save_config(cfg)
            console.print("[green]✓[/green] API key saved to config.")
        except Exception as e:  # noqa: BLE001
            console.print(f"[yellow]Warning: could not save API key to config: {e}[/yellow]")

    url = f"http://{host if host != '0.0.0.0' else '127.0.0.1'}:{port}"

    # ── Daemon mode: launch subprocess and detach ─────────────────────────────
    if daemon:
        existing_pid = _read_pid()
        if existing_pid and _is_running(existing_pid):
            console.print(
                f"[yellow]Server already running (PID {existing_pid}).[/yellow]\n"
                f"  Stop it first: [bold]tesla serve stop[/bold]"
            )
            raise typer.Exit(1)

        # Build child argv — same command without --daemon
        argv = [
            sys.executable,
            "-m",
            "tesla_cli",
            "serve",
            "--port",
            str(port),
            "--host",
            host,
            "--no-open",
        ]
        if reload:
            argv.append("--reload")
        if vin:
            argv += ["--vin", vin]

        proc = subprocess.Popen(
            argv,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        _write_pid(proc.pid)
        console.print(
            f"[green]✓[/green] Server started in background (PID {proc.pid})\n"
            f"  Dashboard  [bold cyan]{url}/[/bold cyan]\n"
            f"  API docs   [bold cyan]{url}/api/docs[/bold cyan]\n"
            f"  Stop with: [bold]tesla serve stop[/bold]"
        )
        return

    # ── Foreground mode ───────────────────────────────────────────────────────
    try:
        import fastapi  # noqa: F401
        import uvicorn
    except ImportError:
        console.print(
            "[red]FastAPI/uvicorn not installed.[/red]\n\n"
            "Install the serve extras:\n"
            "  [bold]pip install 'tesla-cli[serve]'[/bold]\n"
            "  or\n"
            "  [bold]uv pip install 'tesla-cli[serve]'[/bold]"
        )
        raise typer.Exit(1)

    from tesla_cli.api.app import create_app

    console.print(
        f"\n  [bold]tesla-cli API server[/bold]\n\n"
        f"  Dashboard  [bold cyan]{url}/[/bold cyan]\n"
        f"  API docs   [bold cyan]{url}/api/docs[/bold cyan]\n"
        f"  Press [bold]Ctrl+C[/bold] to stop.\n"
    )

    if open_browser:
        import threading
        import time
        import webbrowser

        def _open():
            time.sleep(1.2)
            webbrowser.open(url)

        threading.Thread(target=_open, daemon=True).start()

    from tesla_cli.core.config import load_config
    from tesla_cli.core.config import resolve_vin as _resolve_vin

    try:
        cfg = load_config()
        resolved_vin = _resolve_vin(cfg, vin) if vin else None
    except Exception:  # noqa: BLE001
        resolved_vin = None

    fastapi_app = create_app(vin=resolved_vin, serve_ui=serve_ui or build_ui)

    uvicorn.run(
        fastapi_app,
        host=host,
        port=port,
        reload=reload,
        log_level="warning",
    )



@serve_app.command("uninstall-service")
def serve_uninstall_service() -> None:
    """Remove the tesla-cli systemd/launchd service file.

    \b
    tesla serve uninstall-service    # auto-detect and remove
    """
    import platform as _platform

    system = _platform.system().lower()

    if system == "darwin":
        dest = Path.home() / "Library" / "LaunchAgents" / "com.tesla-cli.server.plist"
        if dest.exists():
            import subprocess

            subprocess.run(["launchctl", "unload", str(dest)], capture_output=True)
            dest.unlink()
            console.print(f"[green]\u2713[/green] LaunchAgent removed: [bold]{dest}[/bold]")
        else:
            console.print("[yellow]No LaunchAgent found to remove.[/yellow]")

    elif system == "linux":
        dest = Path.home() / ".config" / "systemd" / "user" / "tesla-cli.service"
        if dest.exists():
            import subprocess

            subprocess.run(
                ["systemctl", "--user", "disable", "--now", "tesla-cli"],
                capture_output=True,
            )
            dest.unlink()
            subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
            console.print(f"[green]\u2713[/green] Systemd service removed: [bold]{dest}[/bold]")
        else:
            console.print("[yellow]No systemd service found to remove.[/yellow]")

    else:
        console.print(f"[red]Unsupported platform: {system}[/red]")
        raise typer.Exit(1)
