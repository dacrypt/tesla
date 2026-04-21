"""Tests for derived domain projections."""

from __future__ import annotations

import json

import pytest

import tesla_cli.core.domains as domains_module
import tesla_cli.core.sources as sources_module


@pytest.fixture(autouse=True)
def _redirect_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(domains_module, "DOMAINS_DIR", tmp_path / "domains")
    monkeypatch.setattr(sources_module, "SOURCES_DIR", tmp_path / "sources")


def _write_source(source_id: str, payload: dict) -> None:
    sources_module.SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    (sources_module.SOURCES_DIR / f"{source_id}.json").write_text(json.dumps(payload))


class TestDeliveryDomain:
    def test_delivery_domain_uses_sources_only(self):
        _write_source(
            "tesla.order",
            {
                "data": {
                    "orderStatus": "VIN_ASSIGNED",
                    "orderSubstatus": "PREP_FOR_DELIVERY",
                    "vin": "LRWYGCEK3TC512197",
                    "delivery": {"estimatedDeliveryDate": "2026-04-21"},
                },
                "refreshed_at": "2026-04-07T12:00:00+00:00",
                "error": None,
            },
        )
        _write_source(
            "tesla.portal",
            {
                "data": {
                    "delivery_details": {
                        "deliveryAppointmentDateUtc": "2026-04-24T15:00:00Z",
                        "deliveryTiming": {
                            "appointment": "Apr 24 at 10:00 AM",
                            "pickupLocationTitle": "Bogotá Delivery Center",
                        },
                    }
                },
                "refreshed_at": "2026-04-07T12:05:00+00:00",
                "error": None,
            },
        )

        result = domains_module.get_domain("delivery")

        assert result is not None
        assert result["domain_id"] == "delivery"
        assert result["derived_flags"]["vin_assigned"] is True
        assert result["derived_flags"]["delivery_scheduled"] is True
        assert result["state"]["delivery_location"] == "Bogotá Delivery Center"
        assert "Delivery scheduled" in result["summary"]


class TestLegalDomain:
    def test_legal_domain_summarizes_registration_state(self):
        _write_source(
            "co.runt",
            {
                "data": {"placa": "ABC123", "no_identificacion": "123456", "gravamenes": []},
                "refreshed_at": "2026-04-07T12:00:00+00:00",
                "error": None,
            },
        )
        _write_source(
            "co.runt_soat",
            {
                "data": {"soat_vigente": True},
                "refreshed_at": "2026-04-07T12:01:00+00:00",
                "error": None,
            },
        )
        _write_source(
            "co.runt_rtm",
            {
                "data": {"rtm_vigente": True},
                "refreshed_at": "2026-04-07T12:02:00+00:00",
                "error": None,
            },
        )
        _write_source(
            "co.simit",
            {
                "data": {"comparendos": 0, "total_deuda": "0"},
                "refreshed_at": "2026-04-07T12:03:00+00:00",
                "error": None,
            },
        )

        result = domains_module.get_domain("legal")

        assert result is not None
        assert result["domain_id"] == "legal"
        assert result["state"]["plate"] == "ABC123"
        assert result["derived_flags"]["has_soat"] is True
        assert result["derived_flags"]["has_rtm"] is True
        assert result["derived_flags"]["has_fines"] is False
        assert "Plate assigned" in result["summary"]


class TestDomainPersistence:
    def test_recompute_domain_persists_projection(self):
        _write_source(
            "tesla.order",
            {
                "data": {"orderStatus": "ORDERED"},
                "refreshed_at": "2026-04-07T12:00:00+00:00",
                "error": None,
            },
        )

        result = domains_module.recompute_domain("delivery")

        assert (domains_module.DOMAINS_DIR / "delivery.json").exists()
        assert result["domain_id"] == "delivery"


class TestSafetyDomain:
    def test_safety_domain_summarizes_recalls_and_investigations(self):
        _write_source(
            "us.nhtsa_recalls",
            {
                "data": {"count": 2},
                "refreshed_at": "2026-04-07T12:00:00+00:00",
                "error": None,
            },
        )
        _write_source(
            "us.nhtsa_complaints",
            {
                "data": {"total": 3},
                "refreshed_at": "2026-04-07T12:01:00+00:00",
                "error": None,
            },
        )
        _write_source(
            "us.nhtsa_investigations",
            {
                "data": {"count": 1},
                "refreshed_at": "2026-04-07T12:02:00+00:00",
                "error": None,
            },
        )
        _write_source(
            "co.recalls",
            {
                "data": {"count": 1},
                "refreshed_at": "2026-04-07T12:03:00+00:00",
                "error": None,
            },
        )

        result = domains_module.get_domain("safety")

        assert result is not None
        assert result["domain_id"] == "safety"
        assert result["state"]["nhtsa_recalls_count"] == 2
        assert result["derived_flags"]["has_open_recalls"] is True
        assert result["derived_flags"]["has_investigations"] is True
        assert "recall" in result["summary"].lower()


class TestFinancialDomain:
    def test_financial_domain_summarizes_payment_and_value(self):
        _write_source(
            "tesla.portal",
            {
                "data": {"payment_method": "financing", "lender": "Bancolombia"},
                "refreshed_at": "2026-04-07T12:00:00+00:00",
                "error": None,
            },
        )
        _write_source(
            "co.fasecolda",
            {
                "data": {"valor_comercial": "245000000"},
                "refreshed_at": "2026-04-07T12:01:00+00:00",
                "error": None,
            },
        )
        _write_source(
            "co.simit",
            {
                "data": {"comparendos": 1, "total_deuda": "50000"},
                "refreshed_at": "2026-04-07T12:02:00+00:00",
                "error": None,
            },
        )
        _write_source(
            "tesla.order",
            {
                "data": {"paymentMethod": "financing"},
                "refreshed_at": "2026-04-07T12:03:00+00:00",
                "error": None,
            },
        )

        result = domains_module.get_domain("financial")

        assert result is not None
        assert result["domain_id"] == "financial"
        assert result["state"]["payment_method"] == "financing"
        assert result["state"]["commercial_value"] == "245000000"
        assert result["derived_flags"]["has_financing"] is True
        assert result["derived_flags"]["has_fines_debt"] is True

    def test_financial_domain_requests_manual_portal_refresh_when_portal_missing(self):
        _write_source(
            "tesla.order",
            {
                "data": {"paymentMethod": ""},
                "refreshed_at": "2026-04-07T12:03:00+00:00",
                "error": None,
            },
        )

        result = domains_module.get_domain("financial")

        assert result is not None
        assert result["summary"] == "Manual Tesla portal refresh required for financing details"
        assert result["derived_flags"]["portal_refresh_required"] is True


class TestIdentityDomain:
    def test_identity_domain_summarizes_vin_and_model(self):
        _write_source(
            "tesla.order",
            {
                "data": {"vin": "LRWYGCEK3TC512197", "modelCode": "MYLR"},
                "refreshed_at": "2026-04-07T12:00:00+00:00",
                "error": None,
            },
        )
        _write_source(
            "vin.decode",
            {
                "data": {
                    "model": "Model Y",
                    "model_year": "2026",
                    "manufacturer": "Tesla",
                    "plant": "Shanghai",
                },
                "refreshed_at": "2026-04-07T12:01:00+00:00",
                "error": None,
            },
        )

        result = domains_module.get_domain("identity")

        assert result is not None
        assert result["domain_id"] == "identity"
        assert result["state"]["vin"] == "LRWYGCEK3TC512197"
        assert result["state"]["model"] == "Model Y"
        assert result["derived_flags"]["has_vin"] is True
        assert result["derived_flags"]["has_decoded_identity"] is True


class TestSourceHealthDomain:
    def test_source_health_domain_summarizes_registered_sources(self, monkeypatch):
        monkeypatch.setattr(
            domains_module,
            "list_sources",
            lambda: [
                {"id": "tesla.order", "category": "financiero", "stale": False, "error": None},
                {"id": "co.runt", "category": "registro", "stale": True, "error": None},
                {"id": "co.simit", "category": "infracciones", "stale": False, "error": "boom"},
            ],
        )

        result = domains_module.get_domain("source_health")

        assert result is not None
        assert result["domain_id"] == "source_health"
        assert result["state"]["ok_sources"] == 1
        assert result["state"]["total_sources"] == 3
        assert result["derived_flags"]["has_degraded_sources"] is True
        assert result["health"]["status"] == "degraded"
