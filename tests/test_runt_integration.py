"""Integration tests for RUNT backend — queries the real RUNT API.

Run with: .venv/bin/python3 -m pytest tests/test_runt_integration.py -v -m integration
"""

from __future__ import annotations

import io

import pytest

from tesla_cli.backends.runt import RuntBackend, RuntError
from tesla_cli.models.dossier import RuntData

# Mark all tests in this module as integration
pytestmark = pytest.mark.integration

VIN = "YOUR_VIN_HERE"  # Replace with your VIN to run integration tests


class TestRuntLiveQuery:
    """Tests that actually hit the RUNT API."""

    def test_query_vin_tesla(self):
        """Query known Tesla VIN and validate response."""
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

    def test_captcha_generation_and_solving(self):
        """Download a real captcha and verify OCR produces 5 chars."""
        backend = RuntBackend(timeout=30.0)
        captcha_id, image_bytes = backend._generate_captcha()

        # Captcha ID should be a UUID
        assert len(captcha_id) > 10, f"Captcha ID too short: {captcha_id}"

        # Image should be valid
        assert len(image_bytes) > 100, f"Image too small: {len(image_bytes)} bytes"

        # Solve it
        solved = backend._solve_captcha(image_bytes)
        assert solved.isalnum(), f"Expected alphanumeric, got: '{solved}'"
        assert 3 <= len(solved) <= 5, f"Expected 3-5 chars, got {len(solved)}: '{solved}'"

    def test_captcha_image_is_valid_png_or_jpeg(self):
        """Verify captcha image is a valid image format."""
        from PIL import Image

        backend = RuntBackend(timeout=30.0)
        _, image_bytes = backend._generate_captcha()

        # Should be openable by PIL
        img = Image.open(io.BytesIO(image_bytes))
        assert img.size[0] > 0
        assert img.size[1] > 0
        assert img.format in ("PNG", "JPEG", "GIF", "BMP", "WEBP")
