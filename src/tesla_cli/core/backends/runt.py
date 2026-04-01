"""RUNT backend — delegates entirely to openquery co.runt.

Install openquery to use this backend:
    pip install 'tesla-cli[query]'
    uv add openquery
"""

from __future__ import annotations

import logging

from tesla_cli.core.models.dossier import RuntData

logger = logging.getLogger(__name__)


class RuntError(Exception):
    """RUNT query error."""


class RuntBackend:
    """Query Colombia's RUNT vehicle registry via openquery (co.runt).

    openquery handles Playwright WAF bypass, multi-engine CAPTCHA solving
    (PaddleOCR / EasyOCR / Tesseract voting), caching and rate limiting.
    """

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    # ── Public API ────────────────────────────────────────────────────────────

    def query_by_vin(self, vin: str) -> RuntData:
        """Query RUNT for vehicle info by VIN."""
        return self._query(vin, doc_type="vin")

    def query_by_plate(self, placa: str) -> RuntData:
        """Query RUNT for vehicle info by license plate."""
        return self._query(placa, doc_type="placa")

    # ── openquery delegation ──────────────────────────────────────────────────

    def _query(self, value: str, doc_type: str) -> RuntData:
        try:
            from openquery.sources import get_source
            from openquery.sources.base import DocumentType, QueryInput
        except ImportError as exc:
            raise RuntError(
                "openquery is required for RUNT queries. "
                "Install: pip install 'tesla-cli[query]'"
            ) from exc

        if doc_type == "vin":
            dt = DocumentType.VIN
        elif doc_type == "placa":
            dt = DocumentType.PLATE
        else:
            dt = DocumentType.CEDULA

        try:
            src = get_source("co.runt")
            result = src.query(QueryInput(
                document_type=dt,
                document_number=value,
            ))
        except Exception as exc:
            raise RuntError(f"RUNT query failed: {exc}") from exc

        # openquery RuntResult is a superset of tesla-cli RuntData
        # (adds soat_*, tecnomecanica_*, blindaje, etc.)
        d = result.model_dump(exclude={"audit"})
        return RuntData(**{k: v for k, v in d.items() if k in RuntData.model_fields})
