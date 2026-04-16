"""Integration tests for SIMIT backend.

Run with:
  .venv/bin/python3 -m pytest tests/test_simit_integration.py -v -m integration
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from tesla_cli.core.backends.simit import SimitBackend
from tesla_cli.core.models.dossier import SimitData

pytestmark = pytest.mark.integration

CEDULA = "98669543"


@pytest.fixture(scope="module")
def live_result() -> SimitData:
    backend = SimitBackend(timeout=30.0)
    return backend.query_by_cedula(CEDULA)


class TestSimitLiveQuery:
    def test_query_cedula_paz_y_salvo(self, live_result: SimitData):
        assert isinstance(live_result, SimitData)
        assert live_result.cedula == CEDULA
        assert live_result.comparendos == 0
        assert live_result.multas == 0
        assert live_result.paz_y_salvo is True

    def test_query_returns_historial(self, live_result: SimitData):
        assert isinstance(live_result.historial, list)
        assert len(live_result.historial) >= 1
        assert "comparendo" in live_result.historial[0]
        assert "estado" in live_result.historial[0]

    def test_queried_at_is_recent(self, live_result: SimitData):
        assert (datetime.now() - live_result.queried_at) < timedelta(minutes=2)
