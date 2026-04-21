"""SIMIT backend.

Queries Colombia's traffic fines portal via Playwright headless browser.
SIMIT is an Angular SPA and does not expose a stable public REST API for this
flow, so we automate the browser to submit the search form and parse results.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime

from tesla_cli.core.models.dossier import SimitData

logger = logging.getLogger(__name__)

SIMIT_URL = "https://www.fcm.org.co/simit/#/estado-cuenta"


class SimitError(Exception):
    """SIMIT query error."""


class SimitBackend:
    """Query Colombia's SIMIT traffic fines system via Playwright."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def query_by_cedula(self, cedula: str) -> SimitData:
        """Query SIMIT for fines by cédula number."""
        return self._query(cedula, kind="cedula")

    def query_by_placa(self, placa: str) -> SimitData:
        """Query SIMIT for fines by license plate."""
        return self._query(placa, kind="placa")

    def _query(self, value: str, kind: str) -> SimitData:
        try:
            return self._query_openquery(value, kind)
        except ImportError as exc:
            raise SimitError(
                "openquery is required for SIMIT queries. Install: pip install 'tesla-cli[query]'"
            ) from exc
        except Exception as exc:
            logger.warning(
                "OpenQuery SIMIT query failed, falling back to Playwright: %s", exc, exc_info=True
            )

        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.set_default_timeout(self._timeout * 1000)
                page.goto(SIMIT_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)

                self._submit_query(page, value)
                self._wait_for_results(page)

                result = self._parse_results(page, value, kind)
                result.historial = self._parse_historial(page)
                return result
            except PlaywrightTimeoutError as exc:
                raise SimitError(f"Timed out querying SIMIT: {exc}") from exc
            except SimitError:
                raise
            except Exception as exc:
                raise SimitError(f"SIMIT query failed: {exc}") from exc
            finally:
                browser.close()

    def _query_openquery(self, value: str, kind: str) -> SimitData:
        from openquery.sources import get_source
        from openquery.sources.base import DocumentType, QueryInput

        dt = DocumentType.CEDULA if kind == "cedula" else DocumentType.PLATE
        src = get_source("co.simit")
        result = src.query(QueryInput(document_type=dt, document_number=value))
        if isinstance(result, SimitData):
            return result
        if hasattr(result, "model_dump"):
            payload = result.model_dump()
        elif hasattr(result, "dict"):
            payload = result.dict()
        else:
            payload = dict(result)
        payload.setdefault("cedula", value)
        payload.setdefault("queried_at", datetime.now())
        return SimitData(**payload)

    def _submit_query(self, page, value: str) -> None:
        input_box = page.get_by_role(
            "textbox",
            name=re.compile(r"Número de identificación|Número de identificación o placa", re.I),
        )
        input_box.wait_for(state="visible", timeout=15000)
        input_box.click()
        input_box.fill(value)

        submit = page.get_by_role("button", name=re.compile(r"Realizar consulta", re.I))
        submit.click()

    def _wait_for_results(self, page) -> None:
        page.wait_for_function(
            """
            () => {
                const text = document.body.innerText || '';
                return text.includes('Comparendos:')
                    || text.includes('No tienes comparendos ni multas')
                    || text.includes('Paz y Salvo');
            }
            """,
            timeout=20000,
        )
        page.wait_for_timeout(1200)

    def _parse_results(self, page, value: str, kind: str) -> SimitData:
        text = page.locator("body").inner_text()
        result = SimitData(queried_at=datetime.now())
        if kind == "cedula":
            result.cedula = value
        else:
            result.cedula = value

        result.comparendos = self._extract_int(text, r"Comparendos:\s*(\d+)")
        result.multas = self._extract_int(text, r"Multas:\s*(\d+)")
        result.acuerdos_pago = self._extract_int(text, r"Acuerdos de pago:\s*(\d+)")
        result.total_deuda = self._extract_money(text)

        paz_y_salvo_text = "No tienes comparendos ni multas" in text or "Paz y Salvo" in text
        result.paz_y_salvo = paz_y_salvo_text or (
            result.comparendos == 0 and result.multas == 0 and result.total_deuda == 0.0
        )
        return result

    def _parse_historial(self, page) -> list[dict]:
        historial: list[dict] = []
        try:
            button = page.get_by_role("button", name=re.compile(r"Ver historial", re.I))
            if button.count() == 0:
                return historial
            button.first.click()
            page.wait_for_timeout(1200)

            rows = page.locator("table tbody tr")
            count = rows.count()
            for i in range(count):
                cells = rows.nth(i).locator("td")
                if cells.count() < 8:
                    continue
                historial.append(
                    {
                        "comparendo": cells.nth(0).inner_text().strip(),
                        "secretaria": cells.nth(1).inner_text().strip(),
                        "fecha_curso": cells.nth(2).inner_text().strip(),
                        "numero_curso": cells.nth(3).inner_text().strip(),
                        "ciudad": cells.nth(4).inner_text().strip(),
                        "centro_instruccion": cells.nth(5).inner_text().strip(),
                        "fecha_reporte": cells.nth(6).inner_text().strip(),
                        "estado": cells.nth(7).inner_text().strip(),
                    }
                )
        except Exception as exc:
            logger.warning("Could not parse SIMIT historial: %s", exc, exc_info=True)
        return historial

    @staticmethod
    def _extract_int(text: str, pattern: str) -> int:
        match = re.search(pattern, text, re.I)
        return int(match.group(1)) if match else 0

    @staticmethod
    def _extract_money(text: str) -> float:
        match = re.search(r"Total:\s*\$\s*([\d.,]+)", text, re.I)
        if not match:
            return 0.0
        raw = match.group(1).replace(" ", "")
        # COP formatting generally uses dots for thousands and optional comma decimals.
        normalized = raw.replace(".", "").replace(",", ".")
        try:
            return float(normalized)
        except ValueError:
            return 0.0
