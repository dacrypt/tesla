"""SIMIT backend — delegates entirely to openquery co.simit.

Install openquery to use this backend:
    pip install 'tesla-cli[query]'
    uv add openquery
"""

from __future__ import annotations

import logging

from tesla_cli.core.models.dossier import SimitData

logger = logging.getLogger(__name__)


class SimitError(Exception):
    """SIMIT query error."""


class SimitBackend:
    """Query Colombia's SIMIT traffic fines system via openquery (co.simit).

    openquery handles browser automation, WAF bypass, caching and rate limiting.
    """

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    # ── Public API ────────────────────────────────────────────────────────────

    def query_by_cedula(self, cedula: str) -> SimitData:
        """Query SIMIT for fines by cédula number."""
        return self._query(cedula, doc_type="cedula")

    def query_by_placa(self, placa: str) -> SimitData:
        """Query SIMIT for fines by license plate."""
        return self._query(placa, doc_type="placa")

    # ── openquery delegation ──────────────────────────────────────────────────

    def _query(self, value: str, doc_type: str) -> SimitData:
        try:
            from openquery.sources import get_source
            from openquery.sources.base import DocumentType, QueryInput
        except ImportError as exc:
            raise SimitError(
                "openquery is required for SIMIT queries. Install: pip install 'tesla-cli[query]'"
            ) from exc

        dt = DocumentType.CEDULA if doc_type == "cedula" else DocumentType.PLATE
        try:
            src = get_source("co.simit")
            result = src.query(
                QueryInput(
                    document_type=dt,
                    document_number=value,
                )
            )
        except Exception as exc:
            raise SimitError(f"SIMIT query failed: {exc}") from exc

        # openquery SimitResult has identical fields to tesla-cli SimitData
        d = result.model_dump(exclude={"audit"})
        return SimitData(**{k: v for k, v in d.items() if k in SimitData.model_fields})
