"""RUNT backend — delegates to openquery co.runt with a safer page wait mode."""

from __future__ import annotations

import logging

from tesla_cli.core.models.dossier import RuntData

logger = logging.getLogger(__name__)


class RuntError(Exception):
    """RUNT query error."""


class RuntBackend:
    """Query Colombia's RUNT vehicle registry via openquery (co.runt)."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def query_by_vin(self, vin: str) -> RuntData:
        return self._query(vin, doc_type="vin")

    def query_by_plate(self, placa: str) -> RuntData:
        return self._query(placa, doc_type="placa")

    def _make_source(self):
        try:
            from openquery.sources import get_source

            source = get_source("co.runt")
            if hasattr(source, "_timeout"):
                source._timeout = self._timeout
            return source
        except Exception:
            logger.debug("Falling back to TeslaCliRuntSource for co.runt", exc_info=True)

        from openquery.core.browser import BrowserManager
        from openquery.exceptions import CaptchaError, SourceError
        from openquery.sources.co.runt import (
            MAX_RETRIES,
            RUNT_PAGE,
            RuntSource,
            _build_captcha_chain,
        )

        class TeslaCliRuntSource(RuntSource):
            def _query_with_retries(self, tipo_consulta, campo, valor, tipo_documento="C", audit=False):
                browser = BrowserManager(headless=self._headless, timeout=self._timeout)
                solver = _build_captcha_chain()
                last_error = None
                collector = None

                if audit:
                    from openquery.core.audit import AuditCollector

                    collector = AuditCollector("co.runt", campo, valor)

                with browser.page(RUNT_PAGE, wait_until="domcontentloaded") as page:
                    if collector:
                        collector.attach(page)

                    for attempt in range(1, MAX_RETRIES + 1):
                        try:
                            logger.info("RUNT attempt %d/%d for %s=%s", attempt, MAX_RETRIES, campo, valor)
                            captcha_id, image_bytes = self._generate_captcha(page)
                            captcha_text = solver.solve(image_bytes)
                            logger.info("Captcha solved: %s", captcha_text)
                            if collector:
                                collector.screenshot(page, f"captcha_attempt_{attempt}")
                            data = self._execute_query(
                                page,
                                tipo_consulta,
                                campo,
                                valor,
                                captcha_text,
                                captcha_id,
                                tipo_documento=tipo_documento,
                            )
                            vin = valor if campo == "vin" else ""
                            result = self._parse_response(data, vin)
                            if collector:
                                collector.screenshot(page, "result")
                                result_json = result.model_dump_json()
                                result.audit = collector.generate_pdf(page, result_json)
                            return result
                        except (SourceError, CaptchaError) as exc:
                            last_error = exc
                            logger.warning("Attempt %d failed: %s", attempt, exc)
                        except Exception as exc:
                            last_error = exc
                            logger.warning("Attempt %d failed unexpectedly: %s", attempt, exc, exc_info=True)

                raise SourceError("co.runt", f"All {MAX_RETRIES} attempts failed. Last error: {last_error}")

        return TeslaCliRuntSource(timeout=self._timeout)

    def _query(self, value: str, doc_type: str) -> RuntData:
        try:
            from openquery.sources.base import DocumentType, QueryInput
        except ImportError as exc:
            raise RuntError(
                "openquery is required for RUNT queries. Install: pip install 'tesla-cli[query]'"
            ) from exc

        if doc_type == "vin":
            dt = DocumentType.VIN
        elif doc_type == "placa":
            dt = DocumentType.PLATE
        else:
            dt = DocumentType.CEDULA

        try:
            src = self._make_source()
            result = src.query(QueryInput(document_type=dt, document_number=value))
        except Exception as exc:
            logger.warning("RUNT query failed", exc_info=True)
            raise RuntError(f"RUNT query failed: {exc}") from exc

        data = result.model_dump(exclude={"audit"})
        return RuntData(**{k: v for k, v in data.items() if k in RuntData.model_fields})
