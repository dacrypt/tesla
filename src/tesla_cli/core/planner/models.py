"""Pydantic models for the native EV route planner (Phase 1 + Phase 2)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChargerSuggestion(BaseModel):
    ocm_id: int  # OpenChargeMap POI ID (stable ref)
    name: str  # Operator + title, e.g. "Tesla Supercharger - Honda, Tolima"
    lat: float
    lon: float
    operator: str | None = None  # e.g. "Tesla Motors Inc"
    network: str  # "tesla" | "ccs" | "other"
    max_power_kw: float | None = None
    connection_types: list[str] = Field(default_factory=list)
    distance_from_route_km: float = 0.0  # closest-to-polyline
    interp_index: int = 0  # which interp point this satisfies
    # Phase 2 SoC fields
    arrival_soc_kwh: float | None = None
    departure_soc_kwh: float | None = None
    charge_duration_min: int | None = None  # estimated charge time (linear model)
    soc_warning: str | None = None  # e.g. "insufficient range"


class PlannedRoute(BaseModel):
    origin_address: str
    origin_latlon: tuple[float, float]
    destination_address: str
    destination_latlon: tuple[float, float]
    total_distance_km: float
    total_duration_min: int
    stops: list[ChargerSuggestion]
    car_model: str | None = None  # ABRP car model id, e.g. "tesla:my:22:bt37:lr"
    initial_soc: float | None = None  # 0.0-1.0, used for --abrp-link only
    abrp_deep_link: str | None = None
    planned_at: str  # ISO-8601 UTC
    routing_provider: str  # "openroute" | "osrm"
    # Phase 2 consumption/SoC fields
    total_energy_kwh: float | None = None
    segments: list[dict] = Field(default_factory=list)
    consumption_source: str | None = None  # "baseline" | "teslamate-calibrated"

    def to_nav_route(self, name: str):  # -> Route (forward ref; avoid circular import)
        """Project to nav Route for persistence. Stops + final dest as Waypoints."""
        from tesla_cli.core.nav.route import Route, Waypoint

        ts = self.planned_at
        waypoints = [
            Waypoint(
                raw_address=s.name,
                lat=s.lat,
                lon=s.lon,
                geocode_provider="openchargemap",
                geocode_at=ts,
            )
            for s in self.stops
        ]
        waypoints.append(
            Waypoint(
                raw_address=self.destination_address,
                lat=self.destination_latlon[0],
                lon=self.destination_latlon[1],
                geocode_provider="native-planner",
                geocode_at=ts,
            )
        )
        return Route(
            name=name,
            waypoints=waypoints,
            created_at=ts,
            source="native-planner",
            source_id=f"{self.origin_latlon}->{self.destination_latlon}@{self.car_model or 'unknown'}",
        )
