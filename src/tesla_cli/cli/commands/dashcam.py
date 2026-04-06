"""Dashcam commands: tesla dashcam process|list|export."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import typer

from tesla_cli.cli.output import console, render_success

dashcam_app = typer.Typer(name="dashcam", help="Dashcam clip management and video processing.")

_TESLACAM_SUBDIRS = ("SavedClips", "SentryClips", "RecentClips")


@dashcam_app.command("process")
def dashcam_process(
    input_dir: str = typer.Argument(help="Directory containing TeslaCam clips"),
    output: str = typer.Option("output.mp4", "--output", "-o", help="Output file"),
    layout: str = typer.Option(
        "FULLSCREEN",
        "--layout",
        "-l",
        help="Layout: FULLSCREEN, WIDESCREEN, PERSPECTIVE, CROSS, DIAMOND",
    ),
    quality: str = typer.Option(
        "HIGH",
        "--quality",
        "-q",
        help="Quality: LOW, MEDIUM, HIGH, HIGHEST",
    ),
) -> None:
    """Process TeslaCam clips into a merged video.

    Requires tesla_dashcam: pip install tesla_dashcam

    \b
    tesla dashcam process /Volumes/TESLADRIVE/TeslaCam/SavedClips
    tesla dashcam process ./clips --output merged.mp4 --layout WIDESCREEN
    tesla dashcam process ./clips --quality HIGHEST
    """
    if shutil.which("tesla_dashcam") is None:
        console.print(
            "[red]tesla_dashcam not found.[/red]\n"
            "Install it with: [bold]pip install tesla_dashcam[/bold]"
        )
        raise typer.Exit(1)

    input_path = Path(input_dir).expanduser()
    if not input_path.exists():
        console.print(f"[red]Input directory not found:[/red] {input_path}")
        raise typer.Exit(1)

    cmd = [
        "tesla_dashcam",
        str(input_path),
        "--output",
        str(Path(output).expanduser()),
        "--layout",
        layout.upper(),
        "--quality",
        quality.upper(),
    ]

    console.print(f"\n  [bold]Processing TeslaCam clips[/bold]  [dim]{input_path}[/dim]")
    console.print(
        f"  Layout: [cyan]{layout.upper()}[/cyan]  Quality: [cyan]{quality.upper()}[/cyan]"
    )
    console.print(f"  Output: [dim]{output}[/dim]\n")

    try:
        result = subprocess.run(cmd, check=False)  # noqa: S603
        if result.returncode != 0:
            console.print(f"[red]tesla_dashcam exited with code {result.returncode}.[/red]")
            raise typer.Exit(result.returncode)
    except FileNotFoundError:
        console.print("[red]tesla_dashcam executable not found in PATH.[/red]")
        raise typer.Exit(1)

    render_success(f"Video saved to: {output}")


@dashcam_app.command("list")
def dashcam_list(
    usb_path: str = typer.Argument("/Volumes/TESLADRIVE", help="Path to TeslaCam USB drive"),
) -> None:
    """List available dashcam clips on the USB drive.

    Shows date, clip type (saved/sentry/recent), file count, and total size.

    \b
    tesla dashcam list
    tesla dashcam list /Volumes/TESLADRIVE
    tesla dashcam list /media/usb
    """
    teslacam_root = Path(usb_path).expanduser() / "TeslaCam"
    if not teslacam_root.exists():
        console.print(
            f"[red]TeslaCam directory not found at:[/red] {teslacam_root}\n"
            "[dim]Make sure the USB drive is mounted and contains a TeslaCam folder.[/dim]"
        )
        raise typer.Exit(1)

    from rich.table import Table

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Date", width=20)
    table.add_column("Type", width=12)
    table.add_column("Files", width=8, justify="right")
    table.add_column("Size", width=10, justify="right")

    total_clips = 0

    for subdir_name in _TESLACAM_SUBDIRS:
        subdir = teslacam_root / subdir_name
        if not subdir.exists():
            continue

        clip_type = subdir_name.replace("Clips", "").lower()

        # Each date is a sub-folder
        date_dirs = sorted(
            (d for d in subdir.iterdir() if d.is_dir()),
            key=lambda d: d.name,
            reverse=True,
        )

        if not date_dirs:
            # Some setups store clips directly without date folders
            files = list(subdir.glob("*.mp4"))
            if files:
                total_size = sum(f.stat().st_size for f in files)
                table.add_row(
                    subdir_name,
                    clip_type,
                    str(len(files)),
                    _human_size(total_size),
                )
                total_clips += len(files)
            continue

        for date_dir in date_dirs:
            files = list(date_dir.glob("*.mp4"))
            if not files:
                continue
            total_size = sum(f.stat().st_size for f in files)
            table.add_row(
                date_dir.name,
                clip_type,
                str(len(files)),
                _human_size(total_size),
            )
            total_clips += len(files)

    if total_clips == 0:
        console.print(f"[yellow]No dashcam clips found in:[/yellow] {teslacam_root}")
        return

    console.print()
    console.print(table)
    console.print(f"\n  [dim]{total_clips} clip(s) total[/dim]\n")


@dashcam_app.command("export")
def dashcam_export(
    usb_path: str = typer.Argument("/Volumes/TESLADRIVE", help="Path to TeslaCam USB drive"),
    output_dir: str = typer.Option(
        "~/Tesla/DashcamExport", "--output", "-o", help="Local destination directory"
    ),
    clip_type: str = typer.Option(
        "all", "--type", "-t", help="Clip type to copy: saved, sentry, recent, all"
    ),
) -> None:
    """Copy dashcam clips from USB to local storage.

    \b
    tesla dashcam export
    tesla dashcam export --type saved --output ~/Movies/Tesla
    tesla dashcam export /media/usb --type sentry
    """
    valid_types = {"saved", "sentry", "recent", "all"}
    if clip_type not in valid_types:
        console.print(
            f"[red]Unknown clip type '{clip_type}'.[/red]  Valid: {', '.join(sorted(valid_types))}"
        )
        raise typer.Exit(1)

    teslacam_root = Path(usb_path).expanduser() / "TeslaCam"
    if not teslacam_root.exists():
        console.print(
            f"[red]TeslaCam directory not found at:[/red] {teslacam_root}\n"
            "[dim]Make sure the USB drive is mounted and contains a TeslaCam folder.[/dim]"
        )
        raise typer.Exit(1)

    dest_root = Path(output_dir).expanduser()
    dest_root.mkdir(parents=True, exist_ok=True)

    # Map friendly names to folder names
    type_map = {
        "saved": "SavedClips",
        "sentry": "SentryClips",
        "recent": "RecentClips",
    }

    subdirs_to_copy: list[str] = (
        list(type_map.values()) if clip_type == "all" else [type_map[clip_type]]
    )

    copied = 0
    skipped = 0

    for subdir_name in subdirs_to_copy:
        src_dir = teslacam_root / subdir_name
        if not src_dir.exists():
            continue

        dest_dir = dest_root / subdir_name
        dest_dir.mkdir(parents=True, exist_ok=True)

        console.print(f"\n  Copying [bold]{subdir_name}[/bold] → [dim]{dest_dir}[/dim]")

        for src_file in sorted(src_dir.rglob("*.mp4")):
            # Preserve relative structure (date sub-folders)
            rel = src_file.relative_to(src_dir)
            dest_file = dest_dir / rel
            dest_file.parent.mkdir(parents=True, exist_ok=True)

            if dest_file.exists() and dest_file.stat().st_size == src_file.stat().st_size:
                skipped += 1
                continue

            shutil.copy2(src_file, dest_file)
            copied += 1
            console.print(f"    [dim]{rel}[/dim]")

    console.print()
    render_success(
        f"Export complete: {copied} file(s) copied, {skipped} skipped (already exist).\n"
        f"  Destination: {dest_root}"
    )


# ── Helpers ────────────────────────────────────────────────────────────────────


def _human_size(num_bytes: int) -> str:
    """Return a human-readable file size string."""
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024:
            return f"{num_bytes:.0f} {unit}"
        num_bytes //= 1024
    return f"{num_bytes:.0f} TB"
