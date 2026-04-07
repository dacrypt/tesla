"""Backend factory."""

from __future__ import annotations

from tesla_cli.core.backends.base import VehicleBackend
from tesla_cli.core.backends.cached import CachedVehicleBackend

_cached_backend: CachedVehicleBackend | None = None
_cached_backend_key: str = ""


def _create_real_backend(config) -> VehicleBackend:
    """Instantiate the real backend based on config (no caching)."""
    if config.general.backend == "tessie":
        from tesla_cli.core.auth.tokens import TESSIE_TOKEN, get_token
        from tesla_cli.core.backends.tessie import TessieBackend
        from tesla_cli.core.exceptions import AuthenticationError

        token = get_token(TESSIE_TOKEN)
        if not token:
            raise AuthenticationError("Tessie not configured. Run: tesla config auth tessie")
        return TessieBackend(token=token)

    elif config.general.backend == "fleet":
        from tesla_cli.core.auth.tokens import FLEET_ACCESS_TOKEN, get_token
        from tesla_cli.core.backends.fleet import FleetBackend
        from tesla_cli.core.exceptions import AuthenticationError

        token = get_token(FLEET_ACCESS_TOKEN)
        if not token:
            raise AuthenticationError("Fleet API not configured. Run: tesla config auth fleet")
        return FleetBackend(access_token=token, region=config.fleet.region)

    elif config.general.backend == "fleet-signed":
        from tesla_cli.core.auth.tokens import FLEET_ACCESS_TOKEN, get_token
        from tesla_cli.core.backends.fleet_signed import FleetSignedBackend
        from tesla_cli.core.exceptions import AuthenticationError

        if not get_token(FLEET_ACCESS_TOKEN):
            raise AuthenticationError("Fleet API not configured. Run: tesla config auth fleet")
        return FleetSignedBackend()

    elif config.general.backend == "owner":
        from tesla_cli.core.auth.tokens import ORDER_REFRESH_TOKEN, get_token
        from tesla_cli.core.backends.owner import OwnerApiVehicleBackend
        from tesla_cli.core.exceptions import AuthenticationError

        if not get_token(ORDER_REFRESH_TOKEN):
            raise AuthenticationError("Owner API not configured. Run: tesla config auth order")
        return OwnerApiVehicleBackend()

    else:
        from tesla_cli.core.exceptions import ConfigurationError

        raise ConfigurationError(
            f"Unknown backend: {config.general.backend}. "
            "Use 'owner', 'tessie', 'fleet', or 'fleet-signed'."
        )


def get_vehicle_backend(config=None) -> VehicleBackend:
    """Return the configured vehicle backend, wrapped in a singleton CachedVehicleBackend."""
    global _cached_backend, _cached_backend_key

    if config is None:
        from tesla_cli.core.config import load_config

        config = load_config()

    key = f"{config.general.backend}:{id(config)}"
    if _cached_backend is not None and _cached_backend_key == key:
        return _cached_backend

    inner = _create_real_backend(config)
    _cached_backend = CachedVehicleBackend(inner, ttl=45)
    _cached_backend_key = key
    return _cached_backend
