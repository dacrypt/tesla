"""Notification management: tesla notify test/list/add/remove."""

from __future__ import annotations

import typer

from tesla_cli.config import load_config, save_config
from tesla_cli.output import console, is_json_mode, render_success, render_warning

notify_app = typer.Typer(name="notify", help="Manage push notifications (Apprise).")


@notify_app.command("list")
def notify_list() -> None:
    """List configured notification URLs.

    tesla notify list
    tesla -j notify list
    """
    import json

    cfg = load_config()
    urls = cfg.notifications.apprise_urls
    enabled = cfg.notifications.enabled

    if is_json_mode():
        console.print_json(json.dumps({"enabled": enabled, "urls": urls}, indent=2))
        return

    from rich.table import Table

    status = "[green]enabled[/green]" if enabled else "[red]disabled[/red]"
    console.print(f"\n  Notifications: {status}")

    if not urls:
        console.print("  [dim]No notification URLs configured.[/dim]")
        console.print("\n  Add one with: [bold]tesla notify add <apprise-url>[/bold]")
        console.print("  Examples:")
        console.print("    tesla notify add tgram://BOT_TOKEN/CHAT_ID")
        console.print("    tesla notify add slack://TokenA/TokenB/TokenC/channel")
        console.print("    tesla notify add discord://webhook_id/webhook_token")
        console.print("    tesla notify add mailto://user:pass@gmail.com?to=me@gmail.com")
        return

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=4)
    table.add_column("URL")
    table.add_column("Service", width=14)

    for i, url in enumerate(urls, 1):
        service = url.split("://")[0] if "://" in url else "unknown"
        # Mask secrets in display
        display = url
        if "://" in url:
            scheme, rest = url.split("://", 1)
            parts = rest.split("/")
            # Mask middle tokens, keep scheme and last segment visible
            if len(parts) > 2:
                masked = "/".join(["***"] * (len(parts) - 1) + [parts[-1]])
                display = f"{scheme}://{masked}"
        table.add_row(str(i), display, service)

    console.print()
    console.print(table)
    console.print(f"\n  [dim]{len(urls)} URL(s) · notifications {'on' if enabled else 'off'}[/dim]")
    console.print("  [dim]Toggle: [bold]tesla config set notifications-enabled true/false[/bold][/dim]")


@notify_app.command("add")
def notify_add(
    url: str = typer.Argument(..., help="Apprise notification URL"),
) -> None:
    """Add a notification URL (Apprise format).

    tesla notify add tgram://BOT_TOKEN/CHAT_ID
    tesla notify add slack://TokenA/TokenB/TokenC/channel
    tesla notify add discord://webhook_id/webhook_token
    tesla notify add mailto://user:pass@gmail.com?to=me@gmail.com

    Full URL reference: https://github.com/caronc/apprise/wiki
    """
    cfg = load_config()
    if url in cfg.notifications.apprise_urls:
        console.print("[yellow]URL already in list.[/yellow]")
        raise typer.Exit()
    cfg.notifications.apprise_urls.append(url)
    cfg.notifications.enabled = True
    save_config(cfg)
    service = url.split("://")[0] if "://" in url else url
    render_success(f"Added {service} notification URL (notifications enabled)")


@notify_app.command("remove")
def notify_remove(
    index: int = typer.Argument(..., help="1-based index from 'tesla notify list'"),
) -> None:
    """Remove a notification URL by index.

    tesla notify remove 1
    """
    cfg = load_config()
    urls = cfg.notifications.apprise_urls
    if not urls:
        console.print("[yellow]No notification URLs configured.[/yellow]")
        raise typer.Exit(1)
    if index < 1 or index > len(urls):
        console.print(f"[red]Index {index} out of range (1–{len(urls)}).[/red]")
        raise typer.Exit(1)
    removed = urls.pop(index - 1)
    service = removed.split("://")[0] if "://" in removed else removed
    save_config(cfg)
    render_success(f"Removed {service} notification URL")


@notify_app.command("test")
def notify_test(
    title: str = typer.Option("Tesla CLI — Test", "--title", "-t", help="Notification title"),
    body: str = typer.Option(
        "🚗 This is a test notification from tesla-cli. If you see this, notifications are working!",
        "--body", "-b",
        help="Notification body text",
    ),
) -> None:
    """Send a test notification to all configured channels.

    tesla notify test
    tesla notify test --title "My Tesla" --body "Test message"
    """
    import json

    cfg = load_config()

    if not cfg.notifications.apprise_urls:
        console.print(
            "[yellow]No notification URLs configured.[/yellow]\n"
            "Add one first: [bold]tesla notify add tgram://BOT_TOKEN/CHAT_ID[/bold]"
        )
        raise typer.Exit(1)

    results: list[dict] = []

    try:
        import apprise
    except ImportError:
        console.print("[red]apprise is not installed.[/red] Run: pip install apprise")
        raise typer.Exit(1)

    from rich.progress import Progress, SpinnerColumn, TextColumn

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()) as p:
        p.add_task(f"Sending to {len(cfg.notifications.apprise_urls)} channel(s)...", total=None)

        # Format body using template (fallback to raw body if template keys unknown)
        import time as _time
        tmpl = cfg.notifications.message_template
        try:
            template_body = tmpl.format(
                event="test",
                vehicle="tesla-cli",
                detail="connectivity test",
                ts=_time.strftime("%Y-%m-%d %H:%M"),
            )
        except KeyError:
            template_body = tmpl
        effective_body = body if body != (
            "\U0001f697 This is a test notification from tesla-cli. If you see this, notifications are working!"
        ) else template_body

        for url in cfg.notifications.apprise_urls:
            service = url.split("://")[0] if "://" in url else "unknown"
            try:
                apobj = apprise.Apprise()
                apobj.add(url)
                ok = apobj.notify(title=title, body=effective_body)
                results.append({"url": service, "success": ok, "error": None})
            except Exception as e:
                results.append({"url": service, "success": False, "error": str(e)})

    if is_json_mode():
        console.print_json(json.dumps(results, indent=2))
        return

    console.print()
    all_ok = all(r["success"] for r in results)
    for r in results:
        icon = "[green]✅[/green]" if r["success"] else "[red]❌[/red]"
        err = f"  [dim red]{r['error']}[/dim red]" if r["error"] else ""
        console.print(f"  {icon}  {r['url']}{err}")

    console.print()
    if all_ok:
        render_success(f"Test notification sent to {len(results)} channel(s)")
    else:
        failed = sum(1 for r in results if not r["success"])
        render_warning(f"{failed}/{len(results)} channel(s) failed — check your URLs")


@notify_app.command("set-template")
def notify_set_template(
    template: str = typer.Argument(..., help="Template string: use {event}, {vehicle}, {detail}, {ts}"),
) -> None:
    """Set a custom notification message template.

    \b
    tesla notify set-template "{event}: {vehicle} at {detail}"
    tesla notify set-template "Tesla alert — {event}: {detail}"

    Available placeholders: {event}, {vehicle}, {detail}, {ts}
    """
    cfg = load_config()
    cfg.notifications.message_template = template
    save_config(cfg)
    from tesla_cli.output import render_success as _render_success
    _render_success(f"Template saved: [bold]{template}[/bold]")


@notify_app.command("show-template")
def notify_show_template() -> None:
    """Show the current notification message template.

    \b
    tesla notify show-template
    tesla -j notify show-template
    """
    import json as _json

    cfg = load_config()
    tmpl = cfg.notifications.message_template

    if is_json_mode():
        console.print(_json.dumps({"template": tmpl}))
        return

    console.print(f"[dim]Template:[/dim] [bold]{tmpl}[/bold]")
    console.print("[dim]Placeholders: {{event}}, {{vehicle}}, {{detail}}, {{ts}}[/dim]")
