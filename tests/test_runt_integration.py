"""Integration tests for the live RUNT backend."""

from __future__ import annotations

import importlib.util as _ilu

import pytest

from tesla_cli.core.backends.runt import RuntBackend
from tesla_cli.core.models.dossier import RuntData

pytestmark = pytest.mark.integration

VIN = "LRWYGCEK3TC512197"
_openquery_available = _ilu.find_spec("openquery") is not None


@pytest.mark.skipif(not _openquery_available, reason="openquery not installed")
class TestRuntLiveQuery:
    """Tests that hit the real RUNT source through openquery co.runt."""

    def test_query_vin_tesla(self):
        backend = RuntBackend(timeout=30.0)
        result = backend.query_by_vin(VIN)

        assert isinstance(result, RuntData)
        assert result.marca == "TESLA"
        assert result.linea == "MODELO Y"
        assert result.modelo_ano == "2026"
        assert result.estado == "REGISTRADO"
        assert result.numero_vin == VIN
        assert result.tipo_combustible == "ELECTRICO"
        assert result.tipo_carroceria == "SUV"
        assert result.clase_vehiculo == "CAMIONETA"
        assert result.peso_bruto_kg > 0
        assert result.capacidad_pasajeros == 5
