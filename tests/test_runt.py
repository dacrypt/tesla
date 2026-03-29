"""Unit tests for RUNT backend."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest

from tesla_cli.backends.runt import RuntBackend, RuntError
from tesla_cli.models.dossier import RuntData


class TestSolveCaptcha:
    """Test captcha solving."""

    def test_solve_returns_alphanumeric(self):
        """Solve should return only alphanumeric chars."""
        # Create a simple test image with PIL
        from PIL import Image, ImageDraw, ImageFont

        img = Image.new("RGB", (200, 60), color="white")
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
        except (OSError, IOError):
            font = ImageFont.load_default()
        draw.text((20, 10), "AB12C", fill="black", font=font)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        image_bytes = buf.getvalue()

        backend = RuntBackend()
        result = backend._solve_captcha(image_bytes)

        # Should be alphanumeric only
        assert result.isalnum(), f"Expected alphanumeric, got: '{result}'"
        # Should be at most 5 chars (we truncate)
        assert len(result) <= 5

    def test_solve_empty_image_raises(self):
        """Too-small OCR result should raise."""
        # Blank white image — OCR returns empty
        from PIL import Image

        img = Image.new("RGB", (50, 20), color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        backend = RuntBackend()
        with pytest.raises(RuntError, match="too few characters"):
            backend._solve_captcha(buf.getvalue())


class TestQuery:
    """Test _query method with mocked Playwright page."""

    def test_query_success(self):
        """Successful query returns parsed data."""
        import json as _json

        backend = RuntBackend()
        mock_page = MagicMock()
        mock_page.evaluate.return_value = {
            "status": 200,
            "body": _json.dumps({
                "infoVehiculo": {
                    "estadoAutomotor": "REGISTRADO",
                    "marca": "TESLA",
                    "linea": "MODELO Y",
                    "modelo": "2026",
                    "color": "GRIS GRAFITO",
                    "vin": "5YJ3E1EA1PF000001",
                    "numChasis": "5YJ3E1EA1PF000001",
                    "tipoCombustible": "ELECTRICO",
                    "tipoCarroceria": "SUV",
                    "clase": "CAMIONETA",
                    "puertas": "4",
                    "pesoBruto": "1992",
                    "pasajerosSentados": "5",
                    "numeroEjes": "2",
                    "gravamenes": "NO",
                }
            }),
        }

        result = backend._query(mock_page, "5YJ3E1EA1PF000001", "abc12", "test-uuid")
        assert result["infoVehiculo"]["marca"] == "TESLA"

    def test_query_captcha_fail_raises(self):
        """401 response raises RuntError."""
        backend = RuntBackend()
        mock_page = MagicMock()
        mock_page.evaluate.return_value = {
            "status": 401,
            "body": "Unauthorized",
        }

        with pytest.raises(RuntError, match="Captcha verification failed"):
            backend._query(mock_page, "VIN", "bad", "uuid")

    def test_query_server_error_raises(self):
        """500 response raises RuntError."""
        backend = RuntBackend()
        mock_page = MagicMock()
        mock_page.evaluate.return_value = {
            "status": 500,
            "body": "Internal Server Error",
        }

        with pytest.raises(RuntError, match="500"):
            backend._query(mock_page, "VIN", "abc", "uuid")


class TestRetryLogic:
    """Test that query_by_vin retries on failure.

    query_by_vin launches Playwright internally. We mock sync_playwright
    to provide a fake page, and mock the internal methods with correct
    signatures (they now take a `page` argument).
    """

    def test_retries_on_captcha_failure(self):
        """Should retry up to MAX_RETRIES times."""
        backend = RuntBackend()
        call_count = 0

        def mock_generate(page):
            nonlocal call_count
            call_count += 1
            return ("uuid-" + str(call_count), b"\x89PNG" + b"\x00" * 200)

        def mock_query(page, vin, captcha, cid):
            raise RuntError("Captcha error")

        # Mock Playwright so query_by_vin can create its page
        mock_page = MagicMock()
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser

        with patch("tesla_cli.backends.runt.sync_playwright") as mock_sp, \
             patch.object(backend, "_generate_captcha", side_effect=mock_generate), \
             patch.object(backend, "_solve_captcha", return_value="abc12"), \
             patch.object(backend, "_query", side_effect=mock_query):
            mock_sp.return_value.__enter__ = MagicMock(return_value=mock_pw)
            mock_sp.return_value.__exit__ = MagicMock(return_value=False)

            with pytest.raises(RuntError, match="All 3 attempts failed"):
                backend.query_by_vin("TESTVIN")

        assert call_count == 3

    def test_succeeds_on_second_attempt(self):
        """Should succeed if second attempt works."""
        backend = RuntBackend()
        attempt = 0

        def mock_generate(page):
            return ("uuid", b"\x89PNG" + b"\x00" * 200)

        def mock_query(page, vin, captcha, cid):
            nonlocal attempt
            attempt += 1
            if attempt == 1:
                raise RuntError("Captcha failed")
            return {
                "infoVehiculo": {
                    "estadoAutomotor": "REGISTRADO",
                    "marca": "TESLA",
                    "linea": "MODELO Y",
                    "modelo": "2026",
                    "vin": vin,
                }
            }

        mock_page = MagicMock()
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser

        with patch("tesla_cli.backends.runt.sync_playwright") as mock_sp, \
             patch.object(backend, "_generate_captcha", side_effect=mock_generate), \
             patch.object(backend, "_solve_captcha", return_value="abc12"), \
             patch.object(backend, "_query", side_effect=mock_query):
            mock_sp.return_value.__enter__ = MagicMock(return_value=mock_pw)
            mock_sp.return_value.__exit__ = MagicMock(return_value=False)

            result = backend.query_by_vin("TESTVIN")

        assert result.marca == "TESLA"
        assert attempt == 2


class TestParseResponse:
    """Test response parsing into RuntData."""

    def test_parse_with_info_vehiculo(self):
        """Parse response with infoVehiculo wrapper."""
        backend = RuntBackend()
        data = {
            "infoVehiculo": {
                "estadoAutomotor": "REGISTRADO",
                "marca": "TESLA",
                "linea": "MODELO Y",
                "modelo": "2026",
                "color": "GRIS GRAFITO",
                "vin": "5YJ3E1EA1PF000001",
                "numChasis": "5YJ3E1EA1PF000001",
                "tipoCombustible": "ELECTRICO",
                "tipoCarroceria": "SUV",
                "clase": "CAMIONETA",
                "puertas": "4",
                "pesoBruto": "1992",
                "pasajerosSentados": "5",
                "numeroEjes": "2",
                "gravamenes": "NO",
            }
        }

        result = backend._parse_response(data, "5YJ3E1EA1PF000001")

        assert isinstance(result, RuntData)
        assert result.estado == "REGISTRADO"
        assert result.marca == "TESLA"
        assert result.linea == "MODELO Y"
        assert result.modelo_ano == "2026"
        assert result.color == "GRIS GRAFITO"
        assert result.tipo_combustible == "ELECTRICO"
        assert result.tipo_carroceria == "SUV"
        assert result.clase_vehiculo == "CAMIONETA"
        assert result.puertas == 4
        assert result.peso_bruto_kg == 1992
        assert result.capacidad_pasajeros == 5
        assert result.numero_ejes == 2
        assert result.gravamenes is False

    def test_parse_flat_response(self):
        """Parse flat response (no infoVehiculo wrapper)."""
        backend = RuntBackend()
        data = {
            "estadoAutomotor": "MATRICULADO",
            "marca": "CHEVROLET",
            "placa": "ABC123",
        }

        result = backend._parse_response(data, "")
        assert result.estado == "MATRICULADO"
        assert result.marca == "CHEVROLET"
        assert result.placa == "ABC123"
