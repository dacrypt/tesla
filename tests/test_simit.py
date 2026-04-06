"""Unit tests for SIMIT backend (openquery delegation)."""

from __future__ import annotations

import importlib.util as _ilu
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from tesla_cli.core.backends.simit import SimitBackend, SimitError
from tesla_cli.core.models.dossier import SimitData

_openquery_available = _ilu.find_spec("openquery") is not None
_skip_no_openquery = pytest.mark.skipif(
    not _openquery_available, reason="openquery not installed"
)


def _mock_simit_result(extra_fields: dict | None = None) -> MagicMock:
    """Return a mock openquery SimitResult with sensible defaults."""
    now = datetime.now(UTC)
    fields = dict(
        cedula="12345678",
        comparendos=0,
        multas=0,
        acuerdos_pago=0,
        total_deuda=0.0,
        paz_y_salvo=True,
        historial=[],
        queried_at=now,
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


class TestSimitData:
    """Test SimitData model."""

    def test_default_values(self):
        data = SimitData()
        assert data.comparendos == 0
        assert data.multas == 0
        assert data.acuerdos_pago == 0
        assert data.total_deuda == 0.0
        assert data.paz_y_salvo is False
        assert data.historial == []

    def test_paz_y_salvo_serialization(self):
        """Paz y salvo data round-trips through JSON."""
        data = SimitData(
            cedula="12345678",
            comparendos=0,
            multas=0,
            acuerdos_pago=0,
            total_deuda=0.0,
            paz_y_salvo=True,
            historial=[{"comparendo": "123", "estado": "Aplicado"}],
        )
        json_str = data.model_dump_json()
        restored = SimitData.model_validate_json(json_str)
        assert restored.paz_y_salvo is True
        assert restored.cedula == "12345678"
        assert len(restored.historial) == 1

    def test_with_fines(self):
        """SimitData with fines."""
        data = SimitData(
            cedula="12345678",
            comparendos=3,
            multas=2,
            acuerdos_pago=1,
            total_deuda=1500000.0,
            paz_y_salvo=False,
        )
        assert data.comparendos == 3
        assert data.multas == 2
        assert data.total_deuda == 1500000.0
        assert data.paz_y_salvo is False


class TestSimitBackendInit:
    def test_default_timeout(self):
        backend = SimitBackend()
        assert backend._timeout == 30.0

    def test_custom_timeout(self):
        backend = SimitBackend(timeout=60.0)
        assert backend._timeout == 60.0


@_skip_no_openquery
class TestSimitBackendDelegation:
    """Test that SimitBackend delegates to openquery co.simit."""

    def test_query_by_cedula_delegates_to_openquery(self):
        result = _mock_simit_result()
        with patch("openquery.sources.get_source", return_value=_mock_source(result)):
            data = SimitBackend().query_by_cedula("12345678")
        assert isinstance(data, SimitData)
        assert data.cedula == "12345678"
        assert data.paz_y_salvo is True

    def test_query_by_placa_delegates_to_openquery(self):
        result = _mock_simit_result(
            extra_fields={
                "cedula": "XYZ123",
                "paz_y_salvo": False,
                "comparendos": 2,
                "total_deuda": 500000.0,
            }
        )
        with patch("openquery.sources.get_source", return_value=_mock_source(result)):
            data = SimitBackend().query_by_placa("XYZ123")
        assert isinstance(data, SimitData)
        assert data.paz_y_salvo is False
        assert data.comparendos == 2

    def test_raises_simit_error_on_source_exception(self):
        src = MagicMock()
        src.query.side_effect = RuntimeError("connection refused")
        with (
            patch("openquery.sources.get_source", return_value=src),
            pytest.raises(SimitError, match="SIMIT query failed"),
        ):
            SimitBackend().query_by_cedula("12345678")

    def test_raises_simit_error_when_openquery_not_installed(self):
        import builtins

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name.startswith("openquery"):
                raise ImportError("No module named 'openquery'")
            return real_import(name, *args, **kwargs)

        with (
            patch("builtins.__import__", side_effect=mock_import),
            pytest.raises(SimitError, match="openquery is required"),
        ):
            SimitBackend().query_by_cedula("12345678")

    def test_simit_data_fields_mapped_correctly(self):
        result = _mock_simit_result(
            extra_fields={
                "comparendos": 3,
                "multas": 1,
                "total_deuda": 750000.0,
                "paz_y_salvo": False,
                "historial": [{"comparendo": "ABC123", "estado": "Pendiente"}],
            }
        )
        with patch("openquery.sources.get_source", return_value=_mock_source(result)):
            data = SimitBackend().query_by_cedula("12345678")
        assert data.comparendos == 3
        assert data.multas == 1
        assert data.total_deuda == 750000.0
        assert data.paz_y_salvo is False
        assert len(data.historial) == 1

    def test_extra_openquery_fields_ignored_gracefully(self):
        """Fields not in SimitData.model_fields are silently discarded."""
        result = _mock_simit_result(
            extra_fields={
                "unknown_field": "surprise",
                "another_extra": 999,
            }
        )
        with patch("openquery.sources.get_source", return_value=_mock_source(result)):
            data = SimitBackend().query_by_placa("XYZ123")
        assert isinstance(data, SimitData)
        assert not hasattr(data, "unknown_field")

    def test_cedula_doc_type_passed_to_openquery(self):
        """query_by_cedula must use DocumentType.CEDULA."""
        from openquery.sources.base import DocumentType, QueryInput

        result = _mock_simit_result()
        src = _mock_source(result)
        with patch("openquery.sources.get_source", return_value=src):
            SimitBackend().query_by_cedula("12345678")
        call_args = src.query.call_args[0][0]
        assert isinstance(call_args, QueryInput)
        assert call_args.document_type == DocumentType.CEDULA
        assert call_args.document_number == "12345678"

    def test_plate_doc_type_passed_to_openquery(self):
        """query_by_placa must use DocumentType.PLATE."""
        from openquery.sources.base import DocumentType

        result = _mock_simit_result()
        src = _mock_source(result)
        with patch("openquery.sources.get_source", return_value=src):
            SimitBackend().query_by_placa("XYZ123")
        call_args = src.query.call_args[0][0]
        assert call_args.document_type == DocumentType.PLATE
        assert call_args.document_number == "XYZ123"

    def test_co_simit_source_name_used(self):
        """Must request the 'co.simit' source specifically."""
        result = _mock_simit_result()
        with patch("openquery.sources.get_source", return_value=_mock_source(result)) as mock_gs:
            SimitBackend().query_by_cedula("12345678")
        mock_gs.assert_called_once_with("co.simit")
