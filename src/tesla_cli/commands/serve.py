"""serve command: tesla serve — launch local API server + web dashboard."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path

import typer

from tesla_cli.output import console

serve_app = typer.Typer(name="serve", help="Launch local API server and web dashboard.")

_DEFAULT_PID_FILE = Path.home() / ".tesla-cli" / "server.pid"
_DEFAULT_PORT = 8080
_DEFAULT_HOST = "127.0.0.1"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pid_file_path() -> Path:
    """Return the PID file path from config (or default)."""
    try:
        from tesla_cli.config import load_config
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
    port: int = typer.Option(_DEFAULT_PORT, "--port", "-p",
                             help="Port to listen on"),
    host: str = typer.Option(_DEFAULT_HOST, "--host",
                             help="Host to bind (127.0.0.1 = localhost only)"),
    open_browser: bool = typer.Option(True, "--open/--no-open",
                                      help="Open browser on start"),
    reload: bool = typer.Option(False, "--reload",
                                help="Auto-reload on code changes (dev mode)"),
    vin: str | None = typer.Option(None, "--vin", "-v",
                                   help="VIN or alias to serve"),
    daemon: bool = typer.Option(False, "--daemon", "-d",
                                help="Run server in background (detached)"),
    api_key: str | None = typer.Option(None, "--api-key",
                                       help="Require this key on all /api/* requests"),
) -> None:
    """Start the tesla-cli API server and open the web dashboard.

    \b
    tesla serve                          # localhost:8080
    tesla serve --port 3000              # custom port
    tesla serve --host 0.0.0.0           # LAN-accessible (add --api-key for security)
    tesla serve --no-open                # headless
    tesla serve --vin mycar              # specific vehicle
    tesla serve --daemon                 # run in background
    tesla serve --api-key s3cr3t         # require API key on all /api/* requests
    tesla serve stop                     # stop background daemon
    tesla serve status                   # check daemon status

    The dashboard will be available at http://localhost:<PORT>/
    API docs at http://localhost:<PORT>/api/docs
    """
    if ctx.invoked_subcommand is not None:
        return

    # Persist --api-key into config if provided
    if api_key:
        try:
            from tesla_cli.config import load_config, save_config
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
        argv = [sys.executable, "-m", "tesla_cli", "serve",
                "--port", str(port), "--host", host, "--no-open"]
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

    from tesla_cli.server.app import create_app

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

    from tesla_cli.config import load_config
    from tesla_cli.config import resolve_vin as _resolve_vin

    try:
        cfg = load_config()
        resolved_vin = _resolve_vin(cfg, vin) if vin else None
    except Exception:  # noqa: BLE001
        resolved_vin = None

    fastapi_app = create_app(vin=resolved_vin)

    uvicorn.run(
        fastapi_app,
        host=host,
        port=port,
        reload=reload,
        log_level="warning",
    )
