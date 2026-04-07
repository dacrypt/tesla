"""Dashcam API routes: /api/dashcam/*"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter()

_TESLACAM_SUBDIRS = ("SavedClips", "SentryClips", "RecentClips")


def _human_size(num_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024:
            return f"{num_bytes:.0f} {unit}"
        num_bytes //= 1024
    return f"{num_bytes:.0f} TB"


@router.get("/status")
def dashcam_status(usb_path: str = "/Volumes/TESLADRIVE") -> dict:
    """Check if USB drive with TeslaCam is connected."""
    teslacam_root = Path(usb_path).expanduser() / "TeslaCam"
    mounted = Path(usb_path).exists()
    teslacam_found = teslacam_root.exists()

    subdirs: dict[str, bool] = {}
    if teslacam_found:
        for sub in _TESLACAM_SUBDIRS:
            subdirs[sub] = (teslacam_root / sub).exists()

    return {
        "usb_path": usb_path,
        "mounted": mounted,
        "teslacam_found": teslacam_found,
        "subdirs": subdirs,
    }


@router.get("/clips")
def list_clips(usb_path: str = "/Volumes/TESLADRIVE") -> list[dict]:
    """List available dashcam clips on USB drive.

    Scans TeslaCam/SavedClips, SentryClips, and RecentClips directories.
    Returns list of {type, date, file_count, size_bytes, size_human}.
    """
    teslacam_root = Path(usb_path).expanduser() / "TeslaCam"
    if not teslacam_root.exists():
        raise HTTPException(
            status_code=404,
            detail=f"TeslaCam directory not found at: {teslacam_root}. "
            "Make sure the USB drive is mounted.",
        )

    clips: list[dict] = []

    for subdir_name in _TESLACAM_SUBDIRS:
        subdir = teslacam_root / subdir_name
        if not subdir.exists():
            continue

        clip_type = subdir_name.replace("Clips", "").lower()

        date_dirs = sorted(
            (d for d in subdir.iterdir() if d.is_dir()),
            key=lambda d: d.name,
            reverse=True,
        )

        if not date_dirs:
            files = list(subdir.glob("*.mp4"))
            if files:
                total_size = sum(f.stat().st_size for f in files)
                clips.append(
                    {
                        "type": clip_type,
                        "date": subdir_name,
                        "file_count": len(files),
                        "size_bytes": total_size,
                        "size_human": _human_size(total_size),
                    }
                )
            continue

        for date_dir in date_dirs:
            files = list(date_dir.glob("*.mp4"))
            if not files:
                continue
            total_size = sum(f.stat().st_size for f in files)
            clips.append(
                {
                    "type": clip_type,
                    "date": date_dir.name,
                    "file_count": len(files),
                    "size_bytes": total_size,
                    "size_human": _human_size(total_size),
                }
            )

    return clips
