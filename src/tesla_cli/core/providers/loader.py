"""Build and populate the ProviderRegistry from the current config.

This is the composition root for the provider architecture. Every time
the registry is needed, this function assembles it from the user's config
and registers all available providers in priority order.

Adding a new provider
---------------------
1. Create `providers/impl/myprovider.py` with a Provider subclass.
2. Import it here and add a registration block below.
"""

from __future__ import annotations

from tesla_cli.core.config import Config, load_config
from tesla_cli.core.providers.registry import ProviderRegistry


def build_registry(config: Config | None = None) -> ProviderRegistry:
    """Build and return a fully populated ProviderRegistry.

    Registers all providers whose minimum configuration is present.
    Providers that are not configured are silently skipped — they will
    show as "not available" in `tesla providers status`.
    """
    if config is None:
        config = load_config()

    registry = ProviderRegistry()

    # ── L0: BLE (highest priority — offline, fastest) ──────────────────────
    from tesla_cli.core.providers.impl.ble import BleProvider

    registry.register(BleProvider(config))

    # ── L1: Vehicle API (Owner / Tessie / Fleet) ───────────────────────────
    from tesla_cli.core.providers.impl.vehicle_api import VehicleApiProvider

    registry.register(VehicleApiProvider(config))

    # ── L2: TeslaMate local DB ─────────────────────────────────────────────
    from tesla_cli.core.providers.impl.teslaMate import TeslaMateProvider

    registry.register(TeslaMateProvider(config))

    # ── L3: Outbound sinks (all registered; fan-out uses all available) ────

    from tesla_cli.core.providers.impl.abrp import AbrpProvider

    registry.register(AbrpProvider(config))

    from tesla_cli.core.providers.impl.ha import HomeAssistantProvider

    registry.register(HomeAssistantProvider(config))

    from tesla_cli.core.providers.impl.apprise_notify import AppriseProvider

    registry.register(AppriseProvider(config))

    from tesla_cli.core.providers.impl.mqtt import MqttProvider

    registry.register(MqttProvider(config))

    return registry
