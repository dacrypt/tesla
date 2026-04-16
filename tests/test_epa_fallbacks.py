"""Tests for EPA source-first fallback behavior."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from tesla_cli.core import computed
from tesla_cli.core.backends.dossier import DossierBackend


def test_computed_epa_prefers_source_cache():
    with patch(
        "tesla_cli.core.sources.get_cached",
        return_value={"ev_motor": "90 kW front + 200 kW rear", "range_mi": 320},
    ):
        result = computed._get_epa_data()
    assert result["ev_motor"] == "90 kW front + 200 kW rear"
    assert result["range_mi"] == 320


def test_computed_epa_falls_back_to_api():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "evMotor": "90 kW front + 200 kW rear",
        "range": 320,
        "rangeCity": 330,
        "rangeHwy": 310,
    }
    with (
        patch("tesla_cli.core.sources.get_cached", return_value=None),
        patch("httpx.Client.get", return_value=mock_response),
    ):
        result = computed._get_epa_data()
    assert result["ev_motor"] == "90 kW front + 200 kW rear"
    assert result["range_mi"] == 320


def test_dossier_backend_epa_prefers_source_cache():
    backend = DossierBackend()
    try:
        with patch(
            "tesla_cli.core.sources.get_cached",
            return_value={"ev_motor": "Cached Motor", "range_mi": 300},
        ):
            result = backend._get_epa_data()
        assert result["ev_motor"] == "Cached Motor"
        assert result["range_mi"] == 300
    finally:
        backend._client.close()
