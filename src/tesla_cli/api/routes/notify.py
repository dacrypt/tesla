"""Notification API routes: /api/notify/*"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from tesla_cli.core.config import load_config, save_config

router = APIRouter()


@router.get("/list")
def notify_list() -> dict:
    """List configured notification channels."""
    cfg = load_config()
    return {
        "enabled": cfg.notifications.enabled,
        "channels": cfg.notifications.apprise_urls,
        "template": cfg.notifications.message_template,
    }


@router.post("/test")
def notify_test() -> dict:
    """Send a test notification to all configured channels."""
    cfg = load_config()
    urls = cfg.notifications.apprise_urls
    if not urls:
        raise HTTPException(status_code=404, detail="No notification channels configured.")

    try:
        import apprise

        apobj = apprise.Apprise()
        for url in urls:
            apobj.add(url)
        ok = apobj.notify(
            title="Tesla CLI — Test Notification",
            body="This is a test notification from tesla-cli.",
            notify_type=apprise.NotifyType.INFO,
        )
        return {"status": "ok" if ok else "failed", "channels": len(urls)}
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="apprise not installed. Run: pip install apprise",
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


class AddChannelRequest(BaseModel):
    url: str


@router.post("/add")
def notify_add(body: AddChannelRequest) -> dict:
    """Add a notification channel URL."""
    cfg = load_config()
    if body.url in cfg.notifications.apprise_urls:
        raise HTTPException(status_code=409, detail="Channel already configured.")
    cfg.notifications.apprise_urls.append(body.url)
    cfg.notifications.enabled = True
    save_config(cfg)
    return {"status": "ok", "channels": len(cfg.notifications.apprise_urls)}


class RemoveChannelRequest(BaseModel):
    index: int


@router.post("/remove")
def notify_remove(body: RemoveChannelRequest) -> dict:
    """Remove a notification channel by index (0-based)."""
    cfg = load_config()
    urls = cfg.notifications.apprise_urls
    if body.index < 0 or body.index >= len(urls):
        raise HTTPException(
            status_code=404, detail=f"Invalid index {body.index}. Have {len(urls)} channels."
        )
    removed = urls.pop(body.index)
    if not urls:
        cfg.notifications.enabled = False
    save_config(cfg)
    return {"status": "ok", "removed": removed, "remaining": len(urls)}


@router.get("/channels")
def list_channels() -> dict:
    """List all configured notification channels with status."""
    cfg = load_config()
    urls = cfg.notifications.apprise_urls
    channels = []
    for i, url in enumerate(urls):
        # Mask credentials in URLs for display
        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            display = f"{parsed.scheme}://{parsed.netloc}{parsed.path}" if parsed.scheme else url
        except Exception:  # noqa: BLE001
            display = url
        channels.append({"index": i, "url": display})
    return {
        "enabled": cfg.notifications.enabled,
        "count": len(urls),
        "channels": channels,
        "template": cfg.notifications.message_template,
    }


class SendNotificationRequest(BaseModel):
    message: str
    title: str = "Tesla CLI"


@router.post("/send")
def send_notification(body: SendNotificationRequest) -> dict:
    """Send a custom notification to all configured channels."""
    cfg = load_config()
    urls = cfg.notifications.apprise_urls
    if not urls:
        raise HTTPException(status_code=404, detail="No notification channels configured.")

    try:
        import apprise

        apobj = apprise.Apprise()
        for url in urls:
            apobj.add(url)
        ok = apobj.notify(
            title=body.title,
            body=body.message,
            notify_type=apprise.NotifyType.INFO,
        )
        _log_notification(body.title, body.message, "send", bool(ok))
        return {"status": "ok" if ok else "failed", "channels": len(urls)}
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="apprise not installed. Run: pip install apprise",
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/history")
def notification_history(limit: int = 50) -> list:
    """Get notification history (most recent first)."""
    history_file = Path.home() / ".tesla-cli" / "notification_history.jsonl"
    if not history_file.exists():
        return []
    lines = history_file.read_text().strip().split("\n")
    entries = []
    for line in reversed(lines[-limit:]):
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def _redact_message(message: str) -> str:
    """Truncate and redact PII (VINs, RNs) from a notification message."""
    import re

    msg = message[:100]
    msg = re.sub(r"\b[A-HJ-NPR-Z0-9]{17}\b", "***VIN***", msg)
    msg = re.sub(r"\bRN\d+\b", "***RN***", msg)
    return msg


def _log_notification(title: str, message: str, channel: str, success: bool) -> None:
    """Append a notification event to the JSONL history log."""
    import os
    from datetime import datetime

    entry = {
        "timestamp": datetime.now().isoformat(),
        "title": title,
        "message": _redact_message(message),
        "channel": channel,
        "success": success,
    }
    history_file = Path.home() / ".tesla-cli" / "notification_history.jsonl"
    history_file.parent.mkdir(parents=True, exist_ok=True)
    with history_file.open("a") as f:
        f.write(json.dumps(entry) + "\n")
    os.chmod(history_file, 0o600)
