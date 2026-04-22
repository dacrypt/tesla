"""Send a single destination to the vehicle nav (used by `nav place send` and the
upcoming REST API). Wraps backend.share() so both CLI and API share one entrypoint."""

from __future__ import annotations

from typing import Any, Protocol


class _ShareCapableBackend(Protocol):
    def share(
        self, vin: str, value: str, locale: str = "en-US", timestamp_ms: int | None = None
    ) -> dict[str, Any]: ...


def send_place(
    backend: _ShareCapableBackend,
    vin: str,
    address: str,
    locale: str = "en-US",
) -> dict[str, Any]:
    """Send a destination string to the car via the signed share command.

    `address` may be a postal address or a "lat,lon" coordinate pair — the Tesla
    nav system handles both via share_ext_content_raw.
    """
    return backend.share(vin, address, locale=locale)
