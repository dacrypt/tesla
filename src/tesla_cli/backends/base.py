"""Abstract vehicle backend interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class VehicleBackend(ABC):
    """Interface that all vehicle backends must implement."""

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
