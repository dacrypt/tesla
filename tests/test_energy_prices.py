"""Tests for core/backends/energy_prices.py and api/routes/energy_prices.py.

openquery is installed in the dev env and its ``co.tarifas_energia`` source
performs real HTTP, so ``openquery.sources.get_source`` is always patched.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from tesla_cli.core.backends import energy_prices as ep
from tesla_cli.core.config import Config
from tests.conftest import MOCK_VIN

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from tesla_cli.api.app import create_app  # noqa: E402


@pytest.fixture(autouse=True)
def _no_openquery_network():
    with patch("openquery.sources.get_source", side_effect=RuntimeError("offline")) as m:
        yield m


def _oq_returning(payload: dict):
    src = MagicMock()
    src.query.return_value = SimpleNamespace(model_dump=lambda exclude=None: payload)
    return src


# ── nearest_city ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize("city", list(ep.CITY_COORDS))
def test_nearest_city_exact_coords(city):
    lat, lon = ep.CITY_COORDS[city]
    assert ep.nearest_city(lat, lon) == city


def test_nearest_city_close_point():
    # El Poblado, Medellín
    assert ep.nearest_city(6.21, -75.57) == "medellin"


# ── get_tariffs fallback ────────────────────────────────────────────────────


def test_fallback_all_estratos():
    tariffs = ep.get_tariffs("Bogota")
    assert [t["estrato"] for t in tariffs] == [1, 2, 3, 4, 5, 6]
    assert tariffs[0]["empresa"] == "Enel Colombia"


def test_fallback_single_estrato_and_normalisation():
    tariffs = ep.get_tariffs("  MEDELLIN ", estrato=3)
    assert tariffs == [
        {"estrato": 3, "valor_kwh": 486.0, "empresa": "EPM", "municipio": "Medellín"}
    ]


def test_fallback_unknown_city_uses_bogota():
    assert ep.get_tariffs("tunja", 4)[0]["empresa"] == "Enel Colombia"


def test_fallback_does_not_mutate_static_table():
    ep.get_tariffs("cali", 2)
    assert len(ep._FALLBACK_TARIFFS["cali"]) == 6


# ── get_tariffs via openquery ───────────────────────────────────────────────


def test_openquery_tariffs_filtered_by_estrato(_no_openquery_network):
    _no_openquery_network.side_effect = None
    src = _oq_returning(
        {"tariffs": [{"estrato": 1, "valor_kwh": 1.0}, {"estrato": 2, "valor_kwh": 2.0}]}
    )
    _no_openquery_network.return_value = src
    assert ep.get_tariffs("Cali", 2) == [{"estrato": 2, "valor_kwh": 2.0}]
    _no_openquery_network.assert_called_with("co.tarifas_energia")
    qi = src.query.call_args.args[0]
    assert qi.document_number == "cali"
    assert qi.extra == {"ciudad": "cali", "estrato": 2}


def test_openquery_items_key_all_estratos(_no_openquery_network):
    _no_openquery_network.side_effect = None
    _no_openquery_network.return_value = _oq_returning({"items": [{"estrato": 9}]})
    assert ep.get_tariffs("cali") == [{"estrato": 9}]


def test_openquery_empty_result_falls_back(_no_openquery_network):
    _no_openquery_network.side_effect = None
    _no_openquery_network.return_value = _oq_returning({"tariffs": []})
    assert ep.get_tariffs("cali", 1)[0]["empresa"] == "EMCALI"


# ── get_vehicle_location ────────────────────────────────────────────────────


def _patch_vehicle(data=None, exc=None):
    backend = MagicMock()
    if exc:
        backend.get_vehicle_data.side_effect = exc
    else:
        backend.get_vehicle_data.return_value = data
    return [
        patch("tesla_cli.core.config.load_config", return_value=Config()),
        patch("tesla_cli.core.config.resolve_vin", return_value=MOCK_VIN),
        patch("tesla_cli.core.backends.get_vehicle_backend", return_value=backend),
    ]


def _with(patches, fn):
    for p in patches:
        p.start()
    try:
        return fn()
    finally:
        for p in patches:
            p.stop()


def test_vehicle_location_from_drive_state():
    ps = _patch_vehicle({"drive_state": {"latitude": "6.2", "longitude": -75.5}})
    assert _with(ps, ep.get_vehicle_location) == (6.2, -75.5)


def test_vehicle_location_missing_coords():
    ps = _patch_vehicle({"drive_state": {"latitude": 6.2}})
    assert _with(ps, ep.get_vehicle_location) == (None, None)


def test_vehicle_location_no_drive_state():
    ps = _patch_vehicle({"drive_state": None})
    assert _with(ps, ep.get_vehicle_location) == (None, None)


def test_vehicle_location_backend_error():
    ps = _patch_vehicle(exc=RuntimeError("asleep"))
    assert _with(ps, ep.get_vehicle_location) == (None, None)


# ── API routes /api/energy/tariffs* ─────────────────────────────────────────


@pytest.fixture(scope="module")
def client():
    with patch("tesla_cli.api.app.load_config", return_value=Config()):
        app = create_app(vin=None)
    return TestClient(app, raise_server_exceptions=False)


def test_route_tariffs_default(client):
    r = client.get("/api/energy/tariffs")
    assert r.status_code == 200
    body = r.json()
    assert body["ciudad"] == "bogota"
    assert body["estrato"] == 0
    assert body["total"] == 6 == len(body["tariffs"])


def test_route_tariffs_city_estrato(client):
    body = client.get("/api/energy/tariffs?ciudad=Cartagena&estrato=5").json()
    assert body["ciudad"] == "cartagena"
    assert body["tariffs"] == [
        {"estrato": 5, "valor_kwh": 854.0, "empresa": "Afinia", "municipio": "Cartagena"}
    ]


def test_route_tariffs_error_502(client):
    with patch.object(ep, "get_tariffs", side_effect=RuntimeError("bad")):
        r = client.get("/api/energy/tariffs")
    assert r.status_code == 502
    assert "bad" in r.json()["detail"]


def test_route_compare(client):
    body = client.get("/api/energy/tariffs/compare").json()
    names = [c["name"] for c in body["cities"]]
    assert names == ["bogota", "medellin", "cali", "barranquilla", "cartagena"]
    med = body["cities"][1]
    assert med["empresa"] == "EPM"
    assert [e["estrato"] for e in med["estratos"]] == [1, 2, 3, 4, 5, 6]
    assert med["estratos"][0] == {"estrato": 1, "valor_kwh": 354.0}


def test_route_compare_handles_empty_and_unsorted(client):
    def fake(city, estrato=0):
        if city == "cali":
            return []
        return [{"estrato": 2, "valor_kwh": 2.0}, {"estrato": 1, "valor_kwh": 1.0}]

    with patch.object(ep, "get_tariffs", side_effect=fake):
        body = client.get("/api/energy/tariffs/compare").json()
    cali = next(c for c in body["cities"] if c["name"] == "cali")
    assert cali == {"name": "cali", "empresa": "", "estratos": []}
    assert [e["estrato"] for e in body["cities"][0]["estratos"]] == [1, 2]


def test_route_compare_error(client):
    with patch.object(ep, "get_tariffs", side_effect=RuntimeError("x")):
        assert client.get("/api/energy/tariffs/compare").status_code == 502


def test_route_vehicle_location_gps(client):
    with patch.object(ep, "get_vehicle_location", return_value=(10.39, -75.51)):
        body = client.get("/api/energy/tariffs/vehicle-location").json()
    assert body["city"] == "cartagena"
    assert body["location_source"] == "vehicle_gps"
    assert body["estrato"] == 4
    assert body["valor_kwh"] == 683.0
    assert body["lat"] == 10.39


def test_route_vehicle_location_default(client):
    with patch.object(ep, "get_vehicle_location", return_value=(None, None)):
        body = client.get("/api/energy/tariffs/vehicle-location").json()
    assert body["city"] == "bogota"
    assert body["location_source"] == "default"
    assert body["lat"] is None and body["lon"] is None


def test_route_vehicle_location_estrato_fallback_and_defaults(client):
    calls = []

    def fake(city, estrato=0):
        calls.append(estrato)
        return [] if estrato == 4 else [{"valor_kwh": 1.5}]

    with (
        patch.object(ep, "get_vehicle_location", return_value=(None, None)),
        patch.object(ep, "get_tariffs", side_effect=fake),
    ):
        body = client.get("/api/energy/tariffs/vehicle-location").json()
    assert calls == [4, 0]
    assert body["estrato"] == 4
    assert body["empresa"] == ""
    assert body["municipio"] == "Bogota"


def test_route_vehicle_location_no_data_404(client):
    with (
        patch.object(ep, "get_vehicle_location", return_value=(None, None)),
        patch.object(ep, "get_tariffs", return_value=[]),
    ):
        r = client.get("/api/energy/tariffs/vehicle-location")
    assert r.status_code == 404
    assert "bogota" in r.json()["detail"]


def test_route_vehicle_location_error_502(client):
    with patch.object(ep, "get_vehicle_location", side_effect=RuntimeError("gps")):
        r = client.get("/api/energy/tariffs/vehicle-location")
    assert r.status_code == 502
