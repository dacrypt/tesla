"""Unit tests for SIMIT backend."""

from __future__ import annotations

from unittest.mock import MagicMock

from tesla_cli.core.backends.simit import SimitBackend
from tesla_cli.core.models.dossier import SimitData


class TestSimitData:
    def test_default_values(self):
        data = SimitData()
        assert data.comparendos == 0
        assert data.multas == 0
        assert data.acuerdos_pago == 0
        assert data.total_deuda == 0.0
        assert data.paz_y_salvo is False
        assert data.historial == []

    def test_round_trip_json(self):
        data = SimitData(
            cedula="98669543",
            paz_y_salvo=True,
            historial=[{"comparendo": "123", "estado": "Aplicado"}],
        )
        restored = SimitData.model_validate_json(data.model_dump_json())
        assert restored.cedula == "98669543"
        assert restored.paz_y_salvo is True
        assert len(restored.historial) == 1


class TestParseResults:
    def test_parse_paz_y_salvo(self):
        backend = SimitBackend()
        page = MagicMock()
        page.locator.return_value.inner_text.return_value = (
            "Resumen\nComparendos: 0\nMultas: 0\nAcuerdos de pago: 0\nTotal: $ 0\n"
            "No tienes comparendos ni multas registradas en Simit"
        )

        result = backend._parse_results(page, "98669543", "cedula")

        assert result.cedula == "98669543"
        assert result.comparendos == 0
        assert result.multas == 0
        assert result.acuerdos_pago == 0
        assert result.total_deuda == 0.0
        assert result.paz_y_salvo is True

    def test_parse_with_fines(self):
        backend = SimitBackend()
        page = MagicMock()
        page.locator.return_value.inner_text.return_value = (
            "Resumen\nComparendos: 3\nMultas: 2\nAcuerdos de pago: 1\nTotal: $ 1.500.000"
        )

        result = backend._parse_results(page, "12345678", "cedula")

        assert result.comparendos == 3
        assert result.multas == 2
        assert result.acuerdos_pago == 1
        assert result.total_deuda == 1500000.0
        assert result.paz_y_salvo is False


class TestHelpers:
    def test_extract_int(self):
        assert SimitBackend._extract_int("Comparendos: 7", r"Comparendos:\s*(\d+)") == 7
        assert SimitBackend._extract_int("nada", r"Comparendos:\s*(\d+)") == 0

    def test_extract_money(self):
        assert SimitBackend._extract_money("Total: $ 0") == 0.0
        assert SimitBackend._extract_money("Total: $ 1.500.000") == 1500000.0
        assert SimitBackend._extract_money("Total: $ 123.456,78") == 123456.78


class TestParseHistorial:
    def test_parse_historial_rows(self):
        backend = SimitBackend()

        button = MagicMock()
        button.count.return_value = 1
        button.first = button

        def cell(text):
            c = MagicMock()
            c.inner_text.return_value = text
            return c

        row = MagicMock()
        cells = MagicMock()
        cells.count.return_value = 8
        vals = [
            "05001000000051651111",
            "Medellin 05001000",
            "11/03/2026",
            "4777749",
            "Medellin",
            "CIA CIACON S.A.S.",
            "11/03/2026",
            "Aplicado",
        ]
        cells.nth.side_effect = lambda i: cell(vals[i])
        row.locator.return_value = cells

        rows = MagicMock()
        rows.count.return_value = 1
        rows.nth.return_value = row

        page = MagicMock()
        page.get_by_role.return_value = button
        page.locator.return_value = rows

        result = backend._parse_historial(page)
        assert len(result) == 1
        assert result[0]["comparendo"] == "05001000000051651111"
        assert result[0]["estado"] == "Aplicado"
