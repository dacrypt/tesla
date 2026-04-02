"""Provider architecture for tesla-cli.

Every external tool, API, or service that can supply or consume Tesla data
is a *Provider*. The ProviderRegistry is the single entry point through which
the rest of the application obtains data and sends commands — it selects the
best available provider at runtime.

Layers
------
L0  BLE          tesla-control binary  — offline, fastest, no internet
L1  Vehicle API  Owner / Tessie / Fleet API — direct Tesla cloud
L2  Local DB     TeslaMate — historical data, charts, analytics
L3  External     ABRP, Home Assistant, Grafana, Apprise — ecosystem bridges

Usage
-----
    from tesla_cli.core.providers import get_registry
    registry = get_registry()

    # Get data from best available provider
    state = registry.get(Capability.VEHICLE_STATE).fetch("vehicle_data", vin=vin)

    # Fan-out: push to ALL providers that accept telemetry
    registry.fanout(Capability.TELEMETRY_PUSH, "push", data=state, vin=vin)

    # Full ecosystem status
    report = registry.status()
"""

from tesla_cli.core.providers.base import Capability, Provider, ProviderPriority, ProviderResult
from tesla_cli.core.providers.registry import ProviderRegistry

__all__ = [
    "Capability",
    "Provider",
    "ProviderPriority",
    "ProviderResult",
    "ProviderRegistry",
    "get_registry",
]

_registry: ProviderRegistry | None = None


def get_registry(force_reload: bool = False) -> ProviderRegistry:
    """Return the singleton ProviderRegistry, building it from config on first call."""
    global _registry
    if _registry is None or force_reload:
        from tesla_cli.core.providers.loader import build_registry

        _registry = build_registry()
    return _registry
