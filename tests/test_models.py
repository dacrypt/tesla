"""Tests for core Pydantic models: vehicle, climate, drive."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from tesla_cli.core.models.climate import ClimateState
from tesla_cli.core.models.drive import DriveState, Location
from tesla_cli.core.models.vehicle import VehicleData, VehicleSummary


# ── VehicleSummary ─────────────────────────────────────────────────────────────


class TestVehicleSummary:
    def test_defaults(self):
        v = VehicleSummary()
        assert v.vin == ""
        assert v.display_name == ""
        assert v.state == ""
        assert v.model == ""
        assert v.color == ""

    def test_explicit_values(self):
        v = VehicleSummary(
            vin="5YJ3E1EA1PF000001",
            display_name="My Tesla",
            state="online",
            model="modely",
            color="midnight",
        )
        assert v.vin == "5YJ3E1EA1PF000001"
        assert v.display_name == "My Tesla"
        assert v.state == "online"
        assert v.model == "modely"
        assert v.color == "midnight"

    def test_model_dump_roundtrip(self):
        v = VehicleSummary(vin="VIN123", display_name="Road Runner", state="asleep")
        dumped = v.model_dump()
        restored = VehicleSummary.model_validate(dumped)
        assert restored == v

    def test_model_dump_keys(self):
        dumped = VehicleSummary().model_dump()
        assert set(dumped.keys()) == {"vin", "display_name", "state", "model", "color"}

    def test_extra_fields_ignored(self):
        # Pydantic v2 default: extra fields are ignored, no ValidationError
        v = VehicleSummary.model_validate({"vin": "X", "unknown_field": "value"})
        assert v.vin == "X"
        assert not hasattr(v, "unknown_field")


# ── VehicleData ────────────────────────────────────────────────────────────────


class TestVehicleData:
    def test_defaults(self):
        v = VehicleData()
        assert v.vin == ""
        assert v.display_name == ""
        assert v.state == ""
        assert v.odometer == 0.0
        assert v.car_version == ""
        assert v.raw == {}

    def test_explicit_values(self):
        v = VehicleData(
            vin="5YJ3E1EA1PF000001",
            display_name="Model Y",
            state="online",
            odometer=12345.6,
            car_version="2025.2.6",
            raw={"extra": "data"},
        )
        assert v.vin == "5YJ3E1EA1PF000001"
        assert v.odometer == 12345.6
        assert v.car_version == "2025.2.6"
        assert v.raw == {"extra": "data"}

    def test_odometer_is_float(self):
        v = VehicleData(odometer=100)
        assert isinstance(v.odometer, float)
        assert v.odometer == 100.0

    def test_raw_default_factory(self):
        a = VehicleData()
        b = VehicleData()
        # Each instance gets its own dict (no shared mutable default)
        a.raw["key"] = "val"
        assert b.raw == {}

    def test_model_dump_roundtrip(self):
        v = VehicleData(vin="ABC", odometer=500.0, raw={"k": 1})
        restored = VehicleData.model_validate(v.model_dump())
        assert restored == v


# ── ClimateState ───────────────────────────────────────────────────────────────


class TestClimateState:
    def test_defaults(self):
        c = ClimateState()
        assert c.inside_temp is None
        assert c.outside_temp is None
        assert c.driver_temp_setting == 0.0
        assert c.passenger_temp_setting == 0.0
        assert c.is_climate_on is False
        assert c.is_preconditioning is False
        assert c.fan_status == 0
        assert c.seat_heater_left == 0
        assert c.seat_heater_right == 0
        assert c.seat_heater_rear_left == 0
        assert c.seat_heater_rear_center == 0
        assert c.seat_heater_rear_right == 0
        assert c.steering_wheel_heater is False
        assert c.is_front_defroster_on is False
        assert c.is_rear_defroster_on is False

    def test_explicit_values(self):
        c = ClimateState(
            inside_temp=22.5,
            outside_temp=18.0,
            driver_temp_setting=21.0,
            passenger_temp_setting=21.0,
            is_climate_on=True,
            is_preconditioning=False,
            fan_status=3,
            seat_heater_left=2,
            seat_heater_right=1,
            seat_heater_rear_left=0,
            seat_heater_rear_center=0,
            seat_heater_rear_right=0,
            steering_wheel_heater=True,
            is_front_defroster_on=False,
            is_rear_defroster_on=True,
        )
        assert c.inside_temp == 22.5
        assert c.outside_temp == 18.0
        assert c.is_climate_on is True
        assert c.fan_status == 3
        assert c.seat_heater_left == 2
        assert c.steering_wheel_heater is True
        assert c.is_rear_defroster_on is True

    def test_optional_temps_accept_none(self):
        c = ClimateState(inside_temp=None, outside_temp=None)
        assert c.inside_temp is None
        assert c.outside_temp is None

    def test_optional_temps_accept_values(self):
        c = ClimateState(inside_temp=25.0, outside_temp=-5.0)
        assert c.inside_temp == 25.0
        assert c.outside_temp == -5.0

    def test_model_dump_roundtrip(self):
        c = ClimateState(inside_temp=20.0, fan_status=2, seat_heater_left=3)
        restored = ClimateState.model_validate(c.model_dump())
        assert restored == c

    def test_all_seat_heaters_present(self):
        dumped = ClimateState().model_dump()
        for key in (
            "seat_heater_left",
            "seat_heater_right",
            "seat_heater_rear_left",
            "seat_heater_rear_center",
            "seat_heater_rear_right",
        ):
            assert key in dumped


# ── DriveState ─────────────────────────────────────────────────────────────────


class TestDriveState:
    def test_defaults(self):
        d = DriveState()
        assert d.latitude is None
        assert d.longitude is None
        assert d.heading == 0
        assert d.speed is None
        assert d.power == 0
        assert d.shift_state is None

    def test_explicit_values(self):
        d = DriveState(
            latitude=4.6097,
            longitude=-74.0817,
            heading=180,
            speed=60.0,
            power=15,
            shift_state="D",
        )
        assert d.latitude == pytest.approx(4.6097)
        assert d.longitude == pytest.approx(-74.0817)
        assert d.heading == 180
        assert d.speed == 60.0
        assert d.power == 15
        assert d.shift_state == "D"

    def test_optional_fields_none(self):
        d = DriveState(latitude=None, longitude=None, speed=None, shift_state=None)
        assert d.latitude is None
        assert d.speed is None
        assert d.shift_state is None

    def test_parked_shift_state(self):
        d = DriveState(shift_state="P")
        assert d.shift_state == "P"

    def test_model_dump_roundtrip(self):
        d = DriveState(latitude=1.0, longitude=2.0, heading=90, shift_state="D")
        restored = DriveState.model_validate(d.model_dump())
        assert restored == d


# ── Location ───────────────────────────────────────────────────────────────────


class TestLocation:
    def test_defaults(self):
        loc = Location(latitude=1.0, longitude=2.0)
        assert loc.heading == 0
        assert loc.maps_url == ""

    def test_explicit_values(self):
        loc = Location(
            latitude=4.6097,
            longitude=-74.0817,
            heading=270,
            maps_url="https://maps.google.com/?q=4.6097,-74.0817",
        )
        assert loc.latitude == pytest.approx(4.6097)
        assert loc.longitude == pytest.approx(-74.0817)
        assert loc.heading == 270
        assert "4.6097" in loc.maps_url

    def test_from_drive_state_basic(self):
        data = {"latitude": 4.6097, "longitude": -74.0817, "heading": 180}
        loc = Location.from_drive_state(data)
        assert loc.latitude == pytest.approx(4.6097)
        assert loc.longitude == pytest.approx(-74.0817)
        assert loc.heading == 180

    def test_from_drive_state_maps_url(self):
        data = {"latitude": 4.6097, "longitude": -74.0817, "heading": 0}
        loc = Location.from_drive_state(data)
        assert loc.maps_url == "https://maps.google.com/?q=4.6097,-74.0817"

    def test_from_drive_state_missing_fields_use_defaults(self):
        loc = Location.from_drive_state({})
        assert loc.latitude == 0.0
        assert loc.longitude == 0.0
        assert loc.heading == 0
        assert loc.maps_url == "https://maps.google.com/?q=0.0,0.0"

    def test_from_drive_state_negative_coords(self):
        data = {"latitude": -33.8688, "longitude": 151.2093, "heading": 45}
        loc = Location.from_drive_state(data)
        assert loc.latitude == pytest.approx(-33.8688)
        assert loc.longitude == pytest.approx(151.2093)
        assert "-33.8688" in loc.maps_url
        assert "151.2093" in loc.maps_url

    def test_from_drive_state_returns_location_instance(self):
        loc = Location.from_drive_state({"latitude": 0.0, "longitude": 0.0})
        assert isinstance(loc, Location)

    def test_model_dump_roundtrip(self):
        loc = Location(latitude=10.0, longitude=20.0, heading=90, maps_url="https://example.com")
        restored = Location.model_validate(loc.model_dump())
        assert restored == loc
