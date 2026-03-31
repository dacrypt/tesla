"""serve command: tesla serve — launch local API server + web dashboard."""

from __future__ import annotations

import typer

from tesla_cli.output import console

serve_app = typer.Typer(name="serve", help="Launch local API server and web dashboard.")


@serve_app.callback(invoke_without_command=True)
def serve(
    ctx: typer.Context,
    port: int    = typer.Option(8080, "--port", "-p",    help="Port to listen on"),
    host: str    = typer.Option("127.0.0.1", "--host",  help="Host to bind (127.0.0.1 = localhost only)"),
    open_browser: bool = typer.Option(True,  "--open/--no-open", help="Open browser on start"),
    reload: bool = typer.Option(False, "--reload",               help="Auto-reload on code changes (dev mode)"),
    vin: str | None = typer.Option(None, "--vin", "-v",          help="VIN or alias to serve"),
) -> None:
    """Start the tesla-cli API server and open the web dashboard.

    \b
    tesla serve                          # localhost:8080
    tesla serve --port 3000              # custom port
    tesla serve --host 0.0.0.0           # LAN-accessible
    tesla serve --no-open                # headless
    tesla serve --vin mycar              # specific vehicle

    The dashboard will be available at http://localhost:<PORT>/
    API docs at http://localhost:<PORT>/api/docs
    """
    if ctx.invoked_subcommand is not None:
        return

    # Check for FastAPI + uvicorn
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

    url = f"http://{host if host != '0.0.0.0' else '127.0.0.1'}:{port}"

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

    # Build the FastAPI app with the resolved VIN
    from tesla_cli.config import load_config
    from tesla_cli.config import resolve_vin as _resolve_vin
    try:
        cfg  = load_config()
        resolved_vin = _resolve_vin(cfg, vin) if vin else None
    except Exception:
        resolved_vin = None

    fastapi_app = create_app(vin=resolved_vin)

    uvicorn.run(
        fastapi_app,
        host=host,
        port=port,
        reload=reload,
        log_level="warning",  # suppress uvicorn noise; tesla-cli handles its own output
    )
