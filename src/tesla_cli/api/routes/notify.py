"""Notification API routes: /api/notify/*"""

from __future__ import annotations

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
        return {"status": "ok" if ok else "failed", "channels": len(urls)}
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="apprise not installed. Run: pip install apprise",
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
