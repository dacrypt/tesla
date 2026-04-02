"""L3 Apprise notification provider.

Fan-out sink: receives alert events and delivers them to ALL configured
Apprise channels simultaneously (Telegram, Pushover, Slack, email, etc.).
"""

from __future__ import annotations

import time

from tesla_cli.core.config import Config
from tesla_cli.core.providers.base import (
    Capability,
    Provider,
    ProviderPriority,
    ProviderResult,
)


class AppriseProvider(Provider):
    """L3 — Multi-channel push notifications via Apprise.

    Delivers alerts to all configured notification URLs.
    Used as a fan-out sink: any subsystem can call registry.fanout(NOTIFY, "push")
    and this provider will deliver to every configured channel.
    """

    name = "apprise"
    description = "Push notifications (Apprise — Telegram, Slack, email, …)"
    layer = 3
    priority = ProviderPriority.LOW
    capabilities = frozenset({Capability.NOTIFY})

    def __init__(self, config: Config) -> None:
        self._cfg = config

    def is_available(self) -> bool:
        if not self._cfg.notifications.enabled:
            return False
        if not self._cfg.notifications.apprise_urls:
            return False
        try:
            import apprise  # noqa: F401

            return True
        except ImportError:
            return False

    def health_check(self) -> dict:
        if not self._cfg.notifications.enabled:
            return {"status": "down", "latency_ms": 0, "detail": "notifications disabled in config"}
        urls = self._cfg.notifications.apprise_urls
        if not urls:
            return {"status": "down", "latency_ms": 0, "detail": "no apprise_urls configured"}
        try:
            import apprise  # noqa: F401
        except ImportError:
            return {"status": "down", "latency_ms": 0, "detail": "apprise package not installed"}
        return {
            "status": "ok",
            "latency_ms": 0,
            "detail": f"{len(urls)} channel(s) configured",
        }

    def execute(self, operation: str, **kwargs) -> ProviderResult:
        if operation not in ("push", "notify", "send"):
            return ProviderResult(
                ok=False, provider=self.name, error=f"Unknown operation: {operation}"
            )

        title = kwargs.get("title", "Tesla Alert")
        body = kwargs.get("body", "") or kwargs.get("message", "")

        try:
            import apprise

            a = apprise.Apprise()
            for url in self._cfg.notifications.apprise_urls:
                a.add(url)
            t0 = time.monotonic()
            ok = a.notify(title=title, body=body)
            ms = (time.monotonic() - t0) * 1000
            return ProviderResult(
                ok=bool(ok),
                provider=self.name,
                latency_ms=round(ms, 1),
                data={"channels": len(self._cfg.notifications.apprise_urls)},
                error=None if ok else "Some channels failed",
            )
        except ImportError:
            return ProviderResult(ok=False, provider=self.name, error="apprise not installed")
        except Exception as exc:  # noqa: BLE001
            return ProviderResult(ok=False, provider=self.name, error=str(exc))
