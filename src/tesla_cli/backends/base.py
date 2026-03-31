"""Abstract vehicle backend interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class VehicleBackend(ABC):
    """Interface that all vehicle backends must implement.

    Core methods (marked @abstractmethod) must be implemented by every backend.
    Extended methods have default stubs that raise BackendNotSupportedError;
    backends that support them should override with real implementations.
    """

    # ── Core — every backend must implement these ────────────────────────────

    @abstractmethod
    def list_vehicles(self) -> list[dict[str, Any]]:
        """List all vehicles associated with the account."""
        ...

    @abstractmethod
    def get_vehicle_data(self, vin: str) -> dict[str, Any]:
        """Get complete vehicle data."""
        ...

    @abstractmethod
    def get_charge_state(self, vin: str) -> dict[str, Any]:
        """Get charging state."""
        ...

    @abstractmethod
    def get_climate_state(self, vin: str) -> dict[str, Any]:
        """Get climate/HVAC state."""
        ...

    @abstractmethod
    def get_drive_state(self, vin: str) -> dict[str, Any]:
        """Get drive state (location, speed, etc.)."""
        ...

    @abstractmethod
    def get_vehicle_config(self, vin: str) -> dict[str, Any]:
        """Get vehicle configuration."""
        ...

    @abstractmethod
    def wake_up(self, vin: str) -> bool:
        """Wake up the vehicle. Returns True if awake."""
        ...

    @abstractmethod
    def command(self, vin: str, command: str, **params: Any) -> dict[str, Any]:
        """Send a command to the vehicle."""
        ...

    # ── Extended — default stubs raise BackendNotSupportedError ─────────────
    # Backends that support these should override them.

    def get_vehicle_state(self, vin: str) -> dict[str, Any]:
        """Get vehicle state (locks, sentry, software version, odometer, etc.)."""
        # Backends that don't override this can derive it from vehicle_data.
        data = self.get_vehicle_data(vin)
        return data.get("vehicle_state", {})

    def get_service_data(self, vin: str) -> dict[str, Any]:
        """Get service / trip data."""
        from tesla_cli.exceptions import BackendNotSupportedError
        raise BackendNotSupportedError("vehicle service-data", "owner or fleet")

    def get_nearby_charging_sites(self, vin: str) -> dict[str, Any]:
        """Get nearby Superchargers and destination chargers."""
        from tesla_cli.exceptions import BackendNotSupportedError
        raise BackendNotSupportedError("vehicle nearby", "owner or fleet")

    def get_release_notes(self, vin: str) -> dict[str, Any]:
        """Get OTA firmware release notes."""
        from tesla_cli.exceptions import BackendNotSupportedError
        raise BackendNotSupportedError("vehicle release-notes", "fleet")

    def get_recent_alerts(self, vin: str) -> dict[str, Any]:
        """Get recent vehicle fault alerts."""
        from tesla_cli.exceptions import BackendNotSupportedError
        raise BackendNotSupportedError("vehicle alerts", "fleet")

    def get_charge_history(self) -> dict[str, Any]:
        """Get lifetime charging history (Fleet API only)."""
        from tesla_cli.exceptions import BackendNotSupportedError
        raise BackendNotSupportedError(
            "charge history",
            "fleet  (or use `tesla teslaMate charging` if you have TeslaMate)"
        )

    def get_invitations(self, vin: str) -> list[dict[str, Any]]:
        """List driver invitations for the vehicle."""
        from tesla_cli.exceptions import BackendNotSupportedError
        raise BackendNotSupportedError("sharing list", "fleet")

    def create_invitation(self, vin: str) -> dict[str, Any]:
        """Create a new driver invitation."""
        from tesla_cli.exceptions import BackendNotSupportedError
        raise BackendNotSupportedError("sharing invite", "fleet")

    def revoke_invitation(self, vin: str, invitation_id: str) -> dict[str, Any]:
        """Revoke a driver invitation."""
        from tesla_cli.exceptions import BackendNotSupportedError
        raise BackendNotSupportedError("sharing revoke", "fleet")
