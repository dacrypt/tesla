"""Integration tests for SIMIT backend — queries the real SIMIT website.

Run with: .venv/bin/python3 -m pytest tests/test_simit_integration.py -v -m integration
"""

from __future__ import annotations

import pytest

from tesla_cli.core.backends.simit import SimitBackend
from tesla_cli.core.models.dossier import SimitData

# Mark all tests in this module as integration
pytestmark = pytest.mark.integration

CEDULA = "12345678"  # Replace with your cédula to run integration tests


class TestSimitLiveQuery:
    """Tests that actually hit the SIMIT website."""

    def test_query_cedula_paz_y_salvo(self):
        """Query known cédula and validate paz y salvo response."""
        backend = SimitBackend(timeout=30.0)
        result = backend.query_by_cedula(CEDULA)

        assert isinstance(result, SimitData)
        assert result.cedula == CEDULA
        assert result.comparendos == 0
        assert result.multas == 0
        assert result.total_deuda == 0.0
        assert result.paz_y_salvo is True

    def test_query_returns_historial(self):
        """Query should also return historical records."""
        backend = SimitBackend(timeout=30.0)
        result = backend.query_by_cedula(CEDULA)

        # We know from browser inspection there are 3 historial records
        assert isinstance(result.historial, list)
        assert len(result.historial) == 3

        # Validate first record structure
        if result.historial:
            record = result.historial[0]
            assert "comparendo" in record
            assert "estado" in record
            assert record["estado"] == "Aplicado"

    def test_queried_at_is_recent(self):
        """queried_at should be set to current time."""
        from datetime import datetime, timedelta

        backend = SimitBackend(timeout=30.0)
        result = backend.query_by_cedula(CEDULA)

        assert result.queried_at is not None
        # Should be within the last 2 minutes
        assert (datetime.now() - result.queried_at) < timedelta(minutes=2)

    def test_json_serialization(self):
        """Result should serialize to JSON cleanly."""
        backend = SimitBackend(timeout=30.0)
        result = backend.query_by_cedula(CEDULA)

        json_str = result.model_dump_json()
        assert CEDULA in json_str
        assert "paz_y_salvo" in json_str

        # Round-trip
        restored = SimitData.model_validate_json(json_str)
        assert restored.cedula == CEDULA
        assert restored.paz_y_salvo == result.paz_y_salvo
