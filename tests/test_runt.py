"""Unit tests for RUNT backend (openquery delegation)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from tesla_cli.core.backends.runt import RuntBackend, RuntError
from tesla_cli.core.models.dossier import RuntData


def _mock_runt_result(extra_fields: dict | None = None) -> MagicMock:
    """Return a mock openquery RuntResult with sensible defaults."""
    now = datetime.now(UTC)
    fields = dict(
        estado="REGISTRADO",
        placa="XYZ123",
        marca="TESLA",
        linea="MODELO Y",
        modelo_ano="2026",
        color="GRIS GRAFITO",
        clase_vehiculo="CAMIONETA",
        tipo_servicio="PARTICULAR",
        tipo_combustible="ELECTRICO",
        tipo_carroceria="SUV",
        numero_vin="LRWYGCEK3TC512197",
        numero_chasis="LRWYGCEK3TC512197",
        numero_motor="",
        cilindraje="0",
        puertas=4,
        peso_bruto_kg=1992,
        capacidad_pasajeros=5,
        numero_ejes=2,
        gravamenes=False,
        prendas=False,
        repotenciado=False,
        fecha_matricula="2025-01-15",
        autoridad_transito="SECRETARÍA DE TRÁNSITO",
        nombre_pais="COLOMBIA",
        queried_at=now,
        # openquery extra fields (superset)
        soat_vigente=True,
        soat_aseguradora="SURA",
        soat_vencimiento="2026-12-31",
        tecnomecanica_vigente=True,
        tecnomecanica_vencimiento="2026-06-30",
    )
    if extra_fields:
        fields.update(extra_fields)
    result = MagicMock()
    result.model_dump.return_value = fields
    return result


def _mock_source(result: MagicMock) -> MagicMock:
    src = MagicMock()
    src.query.return_value = result
    return src


class TestRuntBackendInit:
    def test_default_timeout(self):
        backend = RuntBackend()
        assert backend._timeout == 30.0

    def test_custom_timeout(self):
        backend = RuntBackend(timeout=60.0)
        assert backend._timeout == 60.0


class TestRuntBackendDelegation:
    """Test that RuntBackend delegates to openquery co.runt."""

    def test_query_by_vin_delegates_to_openquery(self):
        result = _mock_runt_result()
        with patch("openquery.sources.get_source", return_value=_mock_source(result)):
            data = RuntBackend().query_by_vin("LRWYGCEK3TC512197")
        assert isinstance(data, RuntData)
        assert data.marca == "TESLA"
        assert data.estado == "REGISTRADO"

    def test_query_by_plate_delegates_to_openquery(self):
        result = _mock_runt_result()
        with patch("openquery.sources.get_source", return_value=_mock_source(result)):
            data = RuntBackend().query_by_plate("XYZ123")
        assert isinstance(data, RuntData)
        assert data.placa == "XYZ123"

    def test_raises_runt_error_on_source_exception(self):
        src = MagicMock()
        src.query.side_effect = RuntimeError("timeout")
        with patch("openquery.sources.get_source", return_value=src), pytest.raises(RuntError, match="RUNT query failed"):
            RuntBackend().query_by_vin("VIN123")

    def test_raises_runt_error_when_openquery_not_installed(self):
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name.startswith("openquery"):
                raise ImportError("No module named 'openquery'")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import), pytest.raises(RuntError, match="openquery is required"):
            RuntBackend().query_by_vin("VIN123")

    def test_runt_data_fields_mapped_correctly(self):
        result = _mock_runt_result()
        with patch("openquery.sources.get_source", return_value=_mock_source(result)):
            data = RuntBackend().query_by_vin("LRWYGCEK3TC512197")
        assert data.linea == "MODELO Y"
        assert data.modelo_ano == "2026"
        assert data.tipo_combustible == "ELECTRICO"
        assert data.gravamenes is False
        assert data.puertas == 4
        assert data.capacidad_pasajeros == 5

    def test_extra_openquery_fields_ignored_gracefully(self):
        """Fields in openquery result not in RuntData.model_fields are discarded."""
        result = _mock_runt_result(extra_fields={
            "unknown_extra_field": "some_value",
            "another_unknown": 42,
        })
        with patch("openquery.sources.get_source", return_value=_mock_source(result)):
            data = RuntBackend().query_by_plate("XYZ123")
        assert isinstance(data, RuntData)
        assert not hasattr(data, "unknown_extra_field")

    def test_vin_doc_type_passed_to_openquery(self):
        """query_by_vin must use DocumentType.VIN."""
        from openquery.sources.base import DocumentType, QueryInput
        result = _mock_runt_result()
        src = _mock_source(result)
        with patch("openquery.sources.get_source", return_value=src):
            RuntBackend().query_by_vin("LRWYGCEK3TC512197")
        call_args = src.query.call_args[0][0]
        assert isinstance(call_args, QueryInput)
        assert call_args.document_type == DocumentType.VIN
        assert call_args.document_number == "LRWYGCEK3TC512197"

    def test_plate_doc_type_passed_to_openquery(self):
        """query_by_plate must use DocumentType.PLATE."""
        from openquery.sources.base import DocumentType
        result = _mock_runt_result()
        src = _mock_source(result)
        with patch("openquery.sources.get_source", return_value=src):
            RuntBackend().query_by_plate("XYZ123")
        call_args = src.query.call_args[0][0]
        assert call_args.document_type == DocumentType.PLATE
        assert call_args.document_number == "XYZ123"

    def test_co_runt_source_name_used(self):
        """Must request the 'co.runt' source specifically."""
        result = _mock_runt_result()
        with patch("openquery.sources.get_source", return_value=_mock_source(result)) as mock_gs:
            RuntBackend().query_by_vin("LRWYGCEK3TC512197")
        mock_gs.assert_called_once_with("co.runt")


class TestRuntData:
    """Test RuntData model."""

    def test_default_values(self):
        data = RuntData()
        assert data.marca == ""
        assert data.gravamenes is False
        assert data.prendas is False

    def test_serialization_round_trip(self):
        now = datetime.now(UTC)
        data = RuntData(
            estado="REGISTRADO",
            marca="TESLA",
            linea="MODELO Y",
            modelo_ano="2026",
            queried_at=now,
        )
        restored = RuntData.model_validate_json(data.model_dump_json())
        assert restored.marca == "TESLA"
        assert restored.estado == "REGISTRADO"
