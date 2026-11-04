"""Tests for GET /api/init (api/routes/init.py)."""

from __future__ import annotations

import json
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from tesla_cli.api.app import create_app  # noqa: E402
from tesla_cli.core import computed, sources  # noqa: E402
from tesla_cli.core.auth import tokens  # noqa: E402
from tesla_cli.core.config import Config  # noqa: E402
from tests.conftest import MOCK_VIN  # noqa: E402

_SRC = {
    "tesla.order": SimpleNamespace(country=""),
    "co.runt": SimpleNamespace(country="CO"),
    "co.simit": SimpleNamespace(country="CO"),
    "us.epa": SimpleNamespace(country="US"),
}


@pytest.fixture(scope="module")
def app():
    with patch("tesla_cli.api.app.load_config", return_value=Config()):
        return create_app(vin=None)


@pytest.fixture
def env(app, tmp_path):
    cfg = Config()
    cfg.general.default_vin = MOCK_VIN
    cfg.general.country = "CO"
    cache: dict = {}
    delivery_file = tmp_path / "delivery.json"
    drivers = MagicMock(return_value=[{"name": "Ana", "role": "owner"}])
    ps = [
        patch("tesla_cli.api.routes.init.load_config", return_value=cfg),
        patch.object(sources, "_SOURCES", _SRC),
        patch.object(sources, "get_cached", side_effect=lambda sid: cache.get(sid)),
        patch("tesla_cli.core.backends.order.DELIVERY_CACHE_FILE", delivery_file),
        patch.object(computed, "_get_epa_data", return_value={}),
        patch.object(tokens, "has_token", side_effect=lambda k: k == tokens.ORDER_ACCESS_TOKEN),
        patch("tesla_cli.core.db.get_vehicle_drivers", drivers),
    ]
    for p in ps:
        p.start()
    app.state.vehicle_hub = None
    ns = SimpleNamespace(
        client=TestClient(app, raise_server_exceptions=False),
        app=app,
        cfg=cfg,
        cache=cache,
        delivery_file=delivery_file,
        drivers=drivers,
    )
    yield ns
    app.state.vehicle_hub = None
    for p in ps:
        p.stop()


def _hub(latest=None, pre_delivery=False):
    h = MagicMock()
    h.get_latest.return_value = latest
    h.is_pre_delivery.return_value = pre_delivery
    return h


def test_init_minimal_payload_shape(env):
    r = env.client.get("/api/init")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {
        "sources",
        "computed",
        "location",
        "drivers",
        "auth",
        "automations",
        "vehicle",
    }
    assert body["sources"] == {}
    assert body["vehicle"] is None
    assert body["location"] == {
        "lat": 4.711,
        "lon": -74.072,
        "city": "bogota",
        "source": "default",
    }
    assert body["computed"]["real_status"]["phase"] == "produced"
    assert body["computed"]["specs"]["model"] == "Model Y"
    assert body["drivers"] == [{"name": "Ana", "role": "owner"}]
    env.drivers.assert_called_once_with(MOCK_VIN)
    assert body["auth"] == {
        "authenticated": True,
        "backend": env.cfg.general.backend,
        "has_fleet": False,
        "has_order": True,
        "has_tessie": False,
    }


def test_init_filters_sources_by_country(env):
    env.cache.update(
        {
            "tesla.order": {"orderStatus": "BOOKED", "mktOptions": "PPSB,WY20P"},
            "co.runt": {"estado": "REGISTRADO", "placa": "XYZ987", "soat_vigente": True},
            "us.epa": {"ignored": True},
        }
    )
    body = env.client.get("/api/init").json()
    assert set(body["sources"]) == {"tesla.order", "co.runt"}
    rs = body["computed"]["real_status"]
    assert rs["tesla_api_status"] == "BOOKED"
    assert rs["phase"] == "delivered"
    specs = body["computed"]["specs"]
    assert specs["exterior_color"] == "Negro Obsidiana Metálico"
    assert specs["wheels"] == 'Rines 20" Performance'


def test_init_country_switch_includes_other_sources(env):
    env.cfg.general.country = "US"
    env.cache.update({"us.epa": {"x": 1}, "co.runt": {"estado": "X"}})
    body = env.client.get("/api/init").json()
    assert set(body["sources"]) == {"us.epa"}


@pytest.mark.parametrize(
    "mkt",
    [
        [{"code": "PPSB"}, "WY20P"],
        None,
    ],
)
def test_init_option_codes_list_and_missing(env, mkt):
    env.cache["tesla.order"] = {"mktOptions": mkt} if mkt else {"optionCodes": 12345}
    body = env.client.get("/api/init").json()
    specs = body["computed"]["specs"]
    if mkt:
        assert specs["exterior_color"] == "Negro Obsidiana Metálico"
        assert specs["wheels"] == 'Rines 20" Performance'
    else:
        assert specs["exterior_color"] == "Stealth Grey"


def test_init_delivery_cache_top_level_fields(env):
    future = (date.today() + timedelta(days=5)).isoformat()
    env.delivery_file.write_text(
        json.dumps(
            {
                "date_utc": future + "T15:00:00Z",
                "location_name": "Tesla Medellin Centro de Entrega",
                "appointment_text": "Martes 10am",
            }
        )
    )
    body = env.client.get("/api/init").json()
    rs = body["computed"]["real_status"]
    assert rs["delivery_date"] == future
    assert rs["delivery_location"] == "Tesla Medellin Centro de Entrega"
    assert rs["phase"] == "delivery_scheduled"
    assert rs["phase_description"] == "Martes 10am"
    # Location derived from delivery cache name
    assert body["location"]["city"] == "medellin"
    assert body["location"]["source"] == "delivery_cache"
    assert body["location"]["lat"] == 6.244


def test_init_delivery_cache_nested_fields(env):
    env.delivery_file.write_text(
        json.dumps(
            {
                "delivery_details": {
                    "deliveryAppointmentDateUtc": "2020-01-02T00:00:00Z",
                    "deliveryTiming": {
                        "pickupLocationTitle": "Tesla Cali",
                        "appointment": "Jan 2",
                    },
                }
            }
        )
    )
    body = env.client.get("/api/init").json()
    rs = body["computed"]["real_status"]
    assert rs["delivery_date"] == "2020-01-02"
    assert rs["delivery_location"] == "Tesla Cali"
    assert rs["delivery_appointment"] == "Jan 2"
    assert rs["phase"] == "delivered"
    assert body["location"]["city"] == "cali"


def test_init_delivery_cache_unknown_city_defaults(env):
    env.delivery_file.write_text(json.dumps({"location_name": "Somewhere Else"}))
    body = env.client.get("/api/init").json()
    assert body["location"]["source"] == "default"


def test_init_corrupt_delivery_cache_is_best_effort(env):
    env.delivery_file.write_text("{not json")
    r = env.client.get("/api/init")
    assert r.status_code == 200
    body = r.json()
    assert body["location"]["source"] == "default"
    assert body["computed"]["real_status"]["delivery_date"] == ""


def test_init_vehicle_from_hub_and_gps_location(env):
    latest = {"drive_state": {"latitude": 10.96, "longitude": -74.79}, "vin": MOCK_VIN}
    env.app.state.vehicle_hub = _hub(latest)
    body = env.client.get("/api/init").json()
    assert body["vehicle"] == latest
    assert body["location"] == {
        "lat": 10.96,
        "lon": -74.79,
        "city": "barranquilla",
        "source": "vehicle_gps",
    }


def test_init_hub_without_gps_falls_through(env):
    env.app.state.vehicle_hub = _hub({"drive_state": {"latitude": None}})
    body = env.client.get("/api/init").json()
    assert body["location"]["source"] == "default"
    assert body["vehicle"] == {"drive_state": {"latitude": None}}


def test_init_hub_pre_delivery_marker(env):
    env.app.state.vehicle_hub = _hub(None, pre_delivery=True)
    body = env.client.get("/api/init").json()
    assert body["vehicle"] == {"_pre_delivery": True}


def test_init_hub_no_data_no_marker(env):
    env.app.state.vehicle_hub = _hub(None, pre_delivery=False)
    assert env.client.get("/api/init").json()["vehicle"] is None


def test_init_no_vin_skips_drivers(env):
    env.cfg.general.default_vin = ""
    body = env.client.get("/api/init").json()
    assert body["drivers"] == []
    env.drivers.assert_not_called()
    assert body["computed"]["real_status"]["vin_assigned"] is False


def test_init_sections_fail_independently(env):
    env.drivers.side_effect = RuntimeError("db locked")
    with (
        patch.object(sources, "get_cached", side_effect=RuntimeError("cache")),
        patch.object(tokens, "has_token", side_effect=RuntimeError("keyring")),
        patch.object(computed, "compute_specs", side_effect=RuntimeError("specs")),
    ):
        r = env.client.get("/api/init")
    assert r.status_code == 200
    body = r.json()
    assert body["sources"] == {}
    assert body["auth"] is None
    assert body["drivers"] == []
    # real_status is assigned before compute_specs raises
    assert body["computed"]["real_status"]["phase"] == "produced"
    assert body["computed"]["specs"] is None
