"""Tests for tesla_cli.core.planner.chargers."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

import pytest
from pytest_httpx import HTTPXMock

OCM_URL_RE = re.compile(r"^https://api\.openchargemap\.io/v3/poi/.*")
OCM_REFDATA_RE = re.compile(r"^https://api\.openchargemap\.io/v3/referencedata/.*")

from tesla_cli.core.planner.chargers import (
    OCM_CONNECTION_CCS_COMBO_2,
    OCM_CONNECTION_TESLA_SUPERCHARGER,
    OCM_OPERATOR_TESLA,
    ChargerAuthError,
    ChargerLookupError,
    find_chargers_near_point,
    probe_taxonomy,
)


def _poi(
    ocm_id: int,
    title: str,
    lat: float,
    lon: float,
    *,
    operator_id=None,
    operator_title=None,
    conn_type_id=None,
    conn_type_title=None,
    power_kw=None,
) -> dict:
    return {
        "ID": ocm_id,
        "AddressInfo": {"Title": title, "Latitude": lat, "Longitude": lon},
        "OperatorInfo": (
            {"ID": operator_id, "Title": operator_title} if operator_id is not None else None
        ),
        "Connections": [
            {
                "ConnectionType": (
                    {"ID": conn_type_id, "Title": conn_type_title}
                    if conn_type_id is not None
                    else None
                ),
                "PowerKW": power_kw,
            }
        ]
        if conn_type_id is not None or power_kw is not None
        else [],
    }


def test_empty_key_raises_auth_with_signup_url() -> None:
    with pytest.raises(ChargerAuthError) as exc:
        find_chargers_near_point(4.71, -74.07, "")
    assert "openchargemap.org" in str(exc.value)
    assert "tesla config set" in str(exc.value)


def test_parse_response_returns_suggestions(httpx_mock: HTTPXMock) -> None:
    pois = [
        _poi(
            1,
            "SC Honda",
            5.2,
            -74.7,
            operator_id=OCM_OPERATOR_TESLA,
            operator_title="Tesla Motors Inc",
            conn_type_id=OCM_CONNECTION_TESLA_SUPERCHARGER,
            conn_type_title="Tesla (Model S/X)",
            power_kw=250.0,
        ),
        _poi(
            2,
            "CCS Guaduas",
            5.1,
            -74.6,
            operator_id=99,
            operator_title="Enel X",
            conn_type_id=OCM_CONNECTION_CCS_COMBO_2,
            conn_type_title="CCS (Type 2)",
            power_kw=50.0,
        ),
    ]
    httpx_mock.add_response(url=OCM_URL_RE, json=pois)
    results = find_chargers_near_point(5.2, -74.7, "fake", network="any")
    assert len(results) == 2
    r1, r2 = results
    assert r1.ocm_id == 1
    assert r1.network == "tesla"
    assert r1.operator == "Tesla Motors Inc"
    assert r1.max_power_kw == pytest.approx(250.0)
    assert "Tesla" in r1.name
    assert r2.network == "ccs"
    assert r2.max_power_kw == pytest.approx(50.0)


def test_empty_response_returns_empty_list(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=OCM_URL_RE, json=[])
    assert find_chargers_near_point(0.0, 0.0, "k") == []


def test_network_tesla_adds_operator_and_conn_params(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=OCM_URL_RE, json=[])
    find_chargers_near_point(4.71, -74.07, "k", network="tesla")
    req = httpx_mock.get_requests()[0]
    params = parse_qs(urlparse(str(req.url)).query)
    assert params.get("operatorid") == [str(OCM_OPERATOR_TESLA)]
    assert "connectiontypeid" in params
    ctypes = params["connectiontypeid"][0].split(",")
    assert str(OCM_CONNECTION_TESLA_SUPERCHARGER) in ctypes
    assert str(OCM_CONNECTION_CCS_COMBO_2) in ctypes


def test_network_ccs_only_sets_connection_ids(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=OCM_URL_RE, json=[])
    find_chargers_near_point(4.71, -74.07, "k", network="ccs")
    req = httpx_mock.get_requests()[0]
    params = parse_qs(urlparse(str(req.url)).query)
    assert "operatorid" not in params
    assert "connectiontypeid" in params


def test_min_power_filters_weak_chargers(httpx_mock: HTTPXMock) -> None:
    pois = [
        _poi(
            1,
            "Slow",
            5.0,
            -74.0,
            operator_id=99,
            operator_title="Other",
            conn_type_id=OCM_CONNECTION_CCS_COMBO_2,
            conn_type_title="CCS",
            power_kw=22.0,
        ),
        _poi(
            2,
            "Fast",
            5.0,
            -74.0,
            operator_id=99,
            operator_title="Other",
            conn_type_id=OCM_CONNECTION_CCS_COMBO_2,
            conn_type_title="CCS",
            power_kw=150.0,
        ),
    ]
    httpx_mock.add_response(url=OCM_URL_RE, json=pois)
    results = find_chargers_near_point(5.0, -74.0, "k", min_power_kw=100.0)
    assert len(results) == 1
    assert results[0].ocm_id == 2


def test_401_raises_auth(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=OCM_URL_RE, status_code=401)
    with pytest.raises(ChargerAuthError):
        find_chargers_near_point(0.0, 0.0, "bad")


def test_probe_taxonomy_returns_tesla_and_connection_types(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=OCM_REFDATA_RE,
        json={
            "Operators": [
                {"ID": OCM_OPERATOR_TESLA, "Title": "Tesla Motors Inc"},
                {"ID": 1, "Title": "Other Network"},
            ],
            "ConnectionTypes": [
                {"ID": OCM_CONNECTION_TESLA_SUPERCHARGER, "Title": "Tesla (Model S/X)"},
                {"ID": OCM_CONNECTION_CCS_COMBO_2, "Title": "CCS (Type 2)"},
                {"ID": 100, "Title": "Something else"},
            ],
        },
    )
    result = probe_taxonomy("k")
    assert any(op["ID"] == OCM_OPERATOR_TESLA for op in result["tesla_operators"])
    ids = [c["ID"] for c in result["connection_types"]]
    assert OCM_CONNECTION_TESLA_SUPERCHARGER in ids
    assert OCM_CONNECTION_CCS_COMBO_2 in ids
    assert 100 not in ids


def test_probe_taxonomy_empty_key_raises() -> None:
    with pytest.raises(ChargerAuthError):
        probe_taxonomy("")


def test_rate_limited_raises_lookup_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=OCM_URL_RE, status_code=429)
    with pytest.raises(ChargerLookupError):
        find_chargers_near_point(0.0, 0.0, "k")
