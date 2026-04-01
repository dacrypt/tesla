"""Backend factory."""

from __future__ import annotations

from tesla_cli.core.config import Config


def get_vehicle_backend(config: Config):
    """Return the configured vehicle backend."""
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

    elif config.general.backend == "owner":
        from tesla_cli.core.auth.tokens import ORDER_REFRESH_TOKEN, get_token
        from tesla_cli.core.backends.owner import OwnerApiVehicleBackend
        from tesla_cli.core.exceptions import AuthenticationError

        if not get_token(ORDER_REFRESH_TOKEN):
            raise AuthenticationError(
                "Owner API not configured. Run: tesla config auth order"
            )
        return OwnerApiVehicleBackend()

    else:
        from tesla_cli.core.exceptions import ConfigurationError

        raise ConfigurationError(
            f"Unknown backend: {config.general.backend}. Use 'owner', 'tessie', or 'fleet'."
        )
