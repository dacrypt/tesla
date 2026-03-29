"""Drive state models."""

from __future__ import annotations

from pydantic import BaseModel


class DriveState(BaseModel):
    latitude: float | None = None
    longitude: float | None = None
    heading: int = 0
    speed: float | None = None
    power: int = 0
    shift_state: str | None = None


class Location(BaseModel):
    latitude: float
    longitude: float
    heading: int = 0
    maps_url: str = ""

    @classmethod
    def from_drive_state(cls, data: dict) -> Location:
        lat = data.get("latitude", 0.0)
        lon = data.get("longitude", 0.0)
        heading = data.get("heading", 0)
        return cls(
            latitude=lat,
            longitude=lon,
            heading=heading,
            maps_url=f"https://maps.google.com/?q={lat},{lon}",
        )
