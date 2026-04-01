"""ProviderRegistry — the single orchestration hub for all ecosystem providers.

The registry is the ONLY entry point the rest of the application should use
to obtain data or send commands. It handles:

  - Capability routing   → best available provider for an operation
  - Priority ordering    → L0 BLE > L1 API > L2 Local > L3 External
  - Fallback chains      → try next provider if primary fails
  - Fan-out              → broadcast to ALL providers that handle a capability
  - Health reporting     → full ecosystem status in one call
"""

from __future__ import annotations

import time

from tesla_cli.core.providers.base import Provider, ProviderResult


class CapabilityNotAvailableError(Exception):
    """Raised when no configured provider can serve a capability."""

    def __init__(self, capability: str, reason: str = "") -> None:
        self.capability = capability
        msg = f"No available provider for capability: {capability}"
        if reason:
            msg += f" — {reason}"
        super().__init__(msg)


class ProviderRegistry:
    """Manages all registered providers and routes operations to the right one.

    Typical usage
    -------------
        registry = ProviderRegistry()
        registry.register(VehicleApiProvider(cfg))
        registry.register(TeslaMateProvider(cfg))
        registry.register(BleProvider(cfg))

        # Best provider for reading vehicle state
        provider = registry.get(Capability.VEHICLE_STATE)
        result   = provider.fetch("vehicle_data", vin=vin)

        # Try in priority order, fall back on failure
        result = registry.fetch_with_fallback(Capability.VEHICLE_STATE, "vehicle_data", vin=vin)

        # Push to ALL notification providers simultaneously
        results = registry.fanout(Capability.NOTIFY, "push", title="Alert", body="Locked")

        # Full ecosystem health
        report = registry.status()
    """

    def __init__(self) -> None:
        self._providers: list[Provider] = []

    # ── Registration ──────────────────────────────────────────────────────────

    def register(self, provider: Provider) -> ProviderRegistry:
        """Register a provider. Returns self for chaining."""
        self._providers.append(provider)
        # Keep sorted highest→lowest priority
        self._providers.sort(key=lambda p: p.priority, reverse=True)
        return self

    def unregister(self, name: str) -> None:
        """Remove provider by name."""
        self._providers = [p for p in self._providers if p.name != name]

    # ── Discovery ─────────────────────────────────────────────────────────────

    def all(self) -> list[Provider]:
        """All registered providers, sorted by priority (highest first)."""
        return list(self._providers)

    def for_capability(self, capability: str, *, available_only: bool = True) -> list[Provider]:
        """All providers that support a capability, sorted by priority."""
        return [
            p for p in self._providers
            if capability in p.capabilities
            and (not available_only or p.is_available())
        ]

    def get(self, capability: str) -> Provider:
        """Return the highest-priority available provider for capability.

        Raises CapabilityNotAvailableError if none are available.
        """
        providers = self.for_capability(capability)
        if not providers:
            configured = self.for_capability(capability, available_only=False)
            reason = (
                "none configured" if not configured
                else f"configured ({', '.join(p.name for p in configured)}) but not available"
            )
            raise CapabilityNotAvailableError(capability, reason)
        return providers[0]

    def has(self, capability: str) -> bool:
        """Return True if any available provider supports capability."""
        return bool(self.for_capability(capability))

    # ── Data access ───────────────────────────────────────────────────────────

    def fetch(self, capability: str, operation: str, **kwargs) -> ProviderResult:
        """Fetch from the best available provider."""
        provider = self.get(capability)
        return provider.fetch(operation, **kwargs)

    def fetch_with_fallback(
        self,
        capability: str,
        operation: str,
        **kwargs,
    ) -> ProviderResult:
        """Try providers in priority order; return first success.

        Falls through to the next provider if the current one raises or
        returns ok=False.
        """
        providers = self.for_capability(capability)
        if not providers:
            raise CapabilityNotAvailableError(capability)

        last_result: ProviderResult | None = None
        for provider in providers:
            try:
                result = provider.fetch(operation, **kwargs)
                if result.ok:
                    return result
                last_result = result
            except Exception as exc:  # noqa: BLE001
                last_result = ProviderResult(
                    ok=False, provider=provider.name, error=str(exc)
                )
        return last_result or ProviderResult(ok=False, error="all providers failed")

    def execute(self, capability: str, operation: str, **kwargs) -> ProviderResult:
        """Execute a command via the best available provider."""
        provider = self.get(capability)
        return provider.execute(operation, **kwargs)

    def execute_with_fallback(
        self,
        capability: str,
        operation: str,
        **kwargs,
    ) -> ProviderResult:
        """Try command execution in priority order; return first success."""
        providers = self.for_capability(capability)
        if not providers:
            raise CapabilityNotAvailableError(capability)

        last_result: ProviderResult | None = None
        for provider in providers:
            try:
                result = provider.execute(operation, **kwargs)
                if result.ok:
                    return result
                last_result = result
            except Exception as exc:  # noqa: BLE001
                last_result = ProviderResult(
                    ok=False, provider=provider.name, error=str(exc)
                )
        return last_result or ProviderResult(ok=False, error="all providers failed")

    # ── Fan-out ───────────────────────────────────────────────────────────────

    def fanout(
        self,
        capability: str,
        operation: str,
        **kwargs,
    ) -> list[ProviderResult]:
        """Execute an operation on ALL available providers for a capability.

        Used for:
          - Pushing telemetry to ALL sinks (ABRP + HA + MQTT simultaneously)
          - Sending notifications to ALL configured channels
          - Syncing state across multiple home automation platforms

        Returns a list of results from every provider (ok or not).
        """
        providers = self.for_capability(capability)
        results: list[ProviderResult] = []
        for provider in providers:
            try:
                results.append(provider.execute(operation, **kwargs))
            except Exception as exc:  # noqa: BLE001
                results.append(ProviderResult(
                    ok=False, provider=provider.name, error=str(exc)
                ))
        return results

    # ── Health / status ───────────────────────────────────────────────────────

    def status(self) -> list[dict]:
        """Return full ecosystem status — one entry per registered provider."""
        return [p.status_row() for p in self._providers]

    def health_report(self) -> list[dict]:
        """Deep health check — calls health_check() on every provider.

        This may perform network I/O and take a few seconds.
        """
        report = []
        for provider in self._providers:
            t0 = time.monotonic()
            try:
                h = provider.health_check()
                h["provider"] = provider.name
                h.setdefault("latency_ms", round((time.monotonic() - t0) * 1000, 1))
            except Exception as exc:  # noqa: BLE001
                h = {
                    "provider":   provider.name,
                    "status":     "down",
                    "latency_ms": round((time.monotonic() - t0) * 1000, 1),
                    "detail":     str(exc),
                }
            report.append(h)
        return report

    def capability_map(self) -> dict[str, list[str]]:
        """Return {capability: [provider_names]} for all capabilities."""
        caps: dict[str, list[str]] = {}
        for provider in self._providers:
            for cap in provider.capabilities:
                caps.setdefault(cap, []).append(provider.name)
        return caps

    def __repr__(self) -> str:  # pragma: no cover
        return f"ProviderRegistry({len(self._providers)} providers)"
