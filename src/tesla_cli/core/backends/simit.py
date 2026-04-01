"""SIMIT (Sistema Integrado de Información sobre Multas y Sanciones por
Infracciones de Tránsito) backend.

Queries Colombia's traffic fines system via Playwright headless browser.
The SIMIT website is an Angular SPA with no public REST API, so we automate
the browser to fill the form, click search, and parse the DOM results.

No captcha required — just cédula or plate number.

Flow:
1. Navigate to https://www.fcm.org.co/simit/#/estado-cuenta
2. Wait for form to load
3. Fill cédula/plate in the text input
4. Click "Realizar consulta"
5. Wait for results to render
6. Parse summary: comparendos, multas, acuerdos de pago, total
7. Optionally click "Ver historial" to get historical records
"""

from __future__ import annotations

import logging
import re
from datetime import datetime

from tesla_cli.models.dossier import SimitData

logger = logging.getLogger(__name__)

SIMIT_URL = "https://www.fcm.org.co/simit/#/estado-cuenta"


class SimitError(Exception):
    """SIMIT query error."""


class SimitBackend:
    """Query Colombia's SIMIT traffic fines system.

    Uses Playwright headless browser to navigate the Angular SPA,
    fill the search form, and parse DOM results.
    """

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def query_by_cedula(self, cedula: str) -> SimitData:
        """Query SIMIT for fines by cédula number."""
        return self._query(cedula)

    def query_by_placa(self, placa: str) -> SimitData:
        """Query SIMIT for fines by license plate."""
        return self._query(placa)

    def _query(self, search_term: str) -> SimitData:
        """Full flow: launch browser, fill form, parse results."""
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.set_default_timeout(self._timeout * 1000)

                # Navigate to SIMIT
                logger.info("Navigating to SIMIT...")
                page.goto(SIMIT_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)

                # Wait for the Angular SPA to fully render the estado-cuenta view
                logger.info("Waiting for search form...")
                # The form uses aria-label for accessibility
                input_locator = page.get_by_label("Número de identificación o placa del vehículo")
                input_locator.wait_for(state="visible", timeout=15000)

                # Fill search term
                input_locator.fill(search_term)
                logger.info("Filled search term: %s", search_term)

                # Wait for anti-bot JS to enable the button
                page.wait_for_timeout(2000)

                # Click "Realizar consulta" using aria/text matching
                submit_locator = page.get_by_role("button", name="Realizar consulta")
                submit_locator.click()
                logger.info("Clicked submit button")

                # Wait for results to appear — either summary or error message
                page.wait_for_selector(
                    'strong, [class*="resumen"], [class*="result"], h3:has-text("No tienes")',
                    timeout=20000,
                )
                # Give Angular a moment to fully render
                page.wait_for_timeout(2000)

                # Parse results
                result = self._parse_results(page, search_term)

                # Try to get historial
                result.historial = self._parse_historial(page)

                return result

            except SimitError:
                raise
            except Exception as e:
                raise SimitError(f"SIMIT query failed: {e}") from e
            finally:
                browser.close()

    def _parse_results(self, page, search_term: str) -> SimitData:
        """Parse the results summary from the page DOM."""
        data = SimitData(
            queried_at=datetime.now(),
            cedula=search_term,
        )

        # Check for "paz y salvo" (no fines)
        paz_salvo_img = page.query_selector('img[alt*="Paz y Salvo"], img[alt*="paz y salvo"]')
        no_fines_heading = page.query_selector('h3:has-text("No tienes comparendos ni multas")')

        if paz_salvo_img or no_fines_heading:
            data.paz_y_salvo = True
            logger.info("Paz y salvo — no fines found")

        # Parse summary numbers from the results section
        # The page shows: Comparendos: N, Multas: N, Acuerdos de pago: N, Total: $ X
        body_text = page.inner_text("body")

        # Extract comparendos count
        m = re.search(r'Comparendos:\s*(\d+)', body_text)
        if m:
            data.comparendos = int(m.group(1))

        # Extract multas count
        m = re.search(r'Multas:\s*(\d+)', body_text)
        if m:
            data.multas = int(m.group(1))

        # Extract acuerdos de pago count
        m = re.search(r'Acuerdos de pago:\s*(\d+)', body_text)
        if m:
            data.acuerdos_pago = int(m.group(1))

        # Extract total amount
        m = re.search(r'Total:\s*\$\s*([\d.,]+)', body_text)
        if m:
            amount_str = m.group(1).replace('.', '').replace(',', '.')
            try:
                data.total_deuda = float(amount_str)
            except ValueError:
                data.total_deuda = 0.0

        # If all counts are 0 and total is 0, it's paz y salvo
        if data.comparendos == 0 and data.multas == 0 and data.total_deuda == 0:
            data.paz_y_salvo = True

        logger.info(
            "SIMIT results — comparendos=%d, multas=%d, acuerdos=%d, total=$%.0f, paz_y_salvo=%s",
            data.comparendos, data.multas, data.acuerdos_pago, data.total_deuda, data.paz_y_salvo,
        )

        return data

    def _parse_historial(self, page) -> list[dict]:
        """Try to click 'Ver historial' and parse the historical records table."""
        historial = []
        try:
            # Look for "Ver historial (N)" button
            historial_btn = page.query_selector('button:has-text("Ver historial")')
            if not historial_btn:
                logger.info("No historial button found")
                return historial

            # Extract count from button text
            btn_text = historial_btn.inner_text()
            logger.info("Found historial button: %s", btn_text)

            historial_btn.click()
            page.wait_for_timeout(2000)

            # Parse the table that appears
            rows = page.query_selector_all('table tbody tr')
            if not rows:
                logger.info("No historial rows found")
                return historial

            for row in rows:
                cells = row.query_selector_all('td')
                if len(cells) >= 8:
                    record = {
                        "comparendo": (cells[0].inner_text() or "").strip(),
                        "secretaria": (cells[1].inner_text() or "").strip(),
                        "fecha_curso": (cells[2].inner_text() or "").strip(),
                        "numero_curso": (cells[3].inner_text() or "").strip(),
                        "ciudad": (cells[4].inner_text() or "").strip(),
                        "centro_instruccion": (cells[5].inner_text() or "").strip(),
                        "fecha_reporte": (cells[6].inner_text() or "").strip(),
                        "estado": (cells[7].inner_text() or "").strip(),
                    }
                    historial.append(record)

            logger.info("Parsed %d historial records", len(historial))

        except Exception as e:
            logger.warning("Could not parse historial: %s", e)

        return historial
