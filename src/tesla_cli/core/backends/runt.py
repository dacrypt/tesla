"""RUNT (Registro Único Nacional de Tránsito) backend.

Queries Colombia's vehicle registry API directly to get real-time vehicle data.
Uses Playwright to bypass the Imperva WAF (the API requires browser cookies).

Flow:
1. Launch headless browser → navigate to RUNT page (acquires WAF cookies)
2. Use page.evaluate() to fetch captcha via the API (from browser context)
3. Solve captcha with pytesseract OCR
4. POST auth query via page.evaluate()
5. Parse response into RuntData model
"""

from __future__ import annotations

import base64
import io
import logging
import re
from datetime import datetime

from playwright.sync_api import sync_playwright

from tesla_cli.models.dossier import RuntData

logger = logging.getLogger(__name__)

RUNT_PAGE = "https://www.runt.gov.co/consultaCiudadana/#/consultaVehiculo"
BASE_URL = "https://runtproapi.runt.gov.co/CYRConsultaVehiculoMS"
CAPTCHA_URL = f"{BASE_URL}/captcha/libre-captcha/generar"
AUTH_URL = f"{BASE_URL}/auth"

MAX_RETRIES = 3


class RuntError(Exception):
    """RUNT query error."""


class RuntBackend:
    """Query Colombia's RUNT vehicle registry.

    Uses Playwright headless browser to bypass WAF, then makes
    API calls via page.evaluate() (JavaScript fetch from browser context).
    """

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def query_by_vin(self, vin: str) -> RuntData:
        """Full flow: launch browser, generate captcha, solve, query RUNT.

        Retries up to MAX_RETRIES times if captcha solving fails.
        """
        last_error: Exception | None = None

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.set_default_timeout(self._timeout * 1000)

                # Navigate to RUNT page to acquire WAF cookies
                logger.info("Navigating to RUNT page to acquire WAF cookies...")
                page.goto(RUNT_PAGE, wait_until="networkidle", timeout=self._timeout * 1000)

                for attempt in range(1, MAX_RETRIES + 1):
                    try:
                        logger.info("RUNT query attempt %d/%d for VIN %s", attempt, MAX_RETRIES, vin)

                        # Step 1: Generate captcha via browser fetch
                        captcha_id, image_bytes = self._generate_captcha(page)

                        # Step 2: Solve captcha with OCR
                        captcha_text = self._solve_captcha(image_bytes)
                        logger.info("Captcha solved: %s", captcha_text)

                        # Step 3: Query via browser fetch
                        data = self._query(page, vin, captcha_text, captcha_id)

                        # Step 4: Parse into RuntData
                        return self._parse_response(data, vin)

                    except RuntError as e:
                        last_error = e
                        logger.warning("Attempt %d failed: %s", attempt, e)
                        if attempt < MAX_RETRIES:
                            continue
                    except Exception as e:
                        last_error = e
                        logger.warning("Attempt %d failed unexpectedly: %s", attempt, e, exc_info=True)
                        if attempt < MAX_RETRIES:
                            continue
            finally:
                browser.close()

        raise RuntError(f"All {MAX_RETRIES} attempts failed. Last error: {last_error}")

    def query_by_plate(self, placa: str) -> RuntData:
        """Query RUNT by license plate number."""
        last_error: Exception | None = None

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.set_default_timeout(self._timeout * 1000)
                page.goto(RUNT_PAGE, wait_until="networkidle", timeout=self._timeout * 1000)

                for attempt in range(1, MAX_RETRIES + 1):
                    try:
                        captcha_id, image_bytes = self._generate_captcha(page)
                        captcha_text = self._solve_captcha(image_bytes)
                        data = self._query_plate(page, placa, captcha_text, captcha_id)
                        return self._parse_response(data, "")
                    except (RuntError, Exception) as e:
                        last_error = e
                        if attempt < MAX_RETRIES:
                            continue
            finally:
                browser.close()

        raise RuntError(f"All {MAX_RETRIES} attempts failed. Last error: {last_error}")

    def _generate_captcha(self, page) -> tuple[str, bytes]:
        """Generate a captcha via browser-context fetch.

        Returns:
            Tuple of (captcha_id, image_bytes)
        """
        result = page.evaluate(f"""async () => {{
            const r = await fetch('{CAPTCHA_URL}');
            const data = await r.json();
            return {{
                id: data.id || data.idLibreCaptcha || '',
                imagen: data.imagen || data.image || data.captcha || '',
                error: data.error || false,
            }};
        }}""")

        captcha_id = result.get("id", "")
        if not captcha_id:
            raise RuntError(f"No captcha ID in response: {result}")

        image_data = result.get("imagen", "")
        if not image_data:
            raise RuntError("No captcha image in response")

        # Decode base64 image
        if "," in image_data:
            # data:image/png;base64,... format
            image_data = image_data.split(",", 1)[1]

        try:
            image_bytes = base64.b64decode(image_data)
        except Exception as e:
            raise RuntError(f"Cannot decode captcha image: {e}")

        if len(image_bytes) < 100:
            raise RuntError(f"Captcha image too small ({len(image_bytes)} bytes)")

        return captcha_id, image_bytes

    def _solve_captcha(self, image_bytes: bytes) -> str:
        """Solve captcha using pytesseract OCR.

        The RUNT captcha is very simple — 5 alphanumeric characters
        with slight distortion.
        """
        try:
            return self._solve_with_pytesseract(image_bytes)
        except ImportError:
            logger.warning("pytesseract not available")
            raise RuntError(
                "pytesseract is required for captcha solving. "
                "Install: brew install tesseract && pip install pytesseract"
            )

    def _solve_with_pytesseract(self, image_bytes: bytes) -> str:
        """Solve using pytesseract (preferred)."""
        import pytesseract
        from PIL import Image, ImageFilter, ImageOps

        img = Image.open(io.BytesIO(image_bytes))

        # Pre-process for better OCR
        img = img.convert("L")  # Grayscale
        img = ImageOps.autocontrast(img)  # Enhance contrast
        # Threshold to black and white
        img = img.point(lambda x: 255 if x > 128 else 0, "1")
        # Scale up for better recognition
        img = img.resize((img.width * 3, img.height * 3), Image.LANCZOS)
        # Slight blur to smooth edges
        img = img.filter(ImageFilter.MedianFilter(3))

        # OCR with restrictive whitelist
        text = pytesseract.image_to_string(
            img,
            config="--psm 8 -c tessedit_char_whitelist=abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
        )
        text = re.sub(r"[^a-zA-Z0-9]", "", text.strip())

        if len(text) < 3:
            raise RuntError(f"OCR returned too few characters: '{text}'")

        # Take first 5 chars (captcha is always 5)
        return text[:5]

    def _query(self, page, vin: str, captcha_text: str, captcha_id: str) -> dict:
        """POST auth query to RUNT API by VIN via browser fetch."""
        return self._execute_query(page, tipo_consulta="2", campo="vin", valor=vin,
                                   captcha_text=captcha_text, captcha_id=captcha_id)

    def _query_plate(self, page, placa: str, captcha_text: str, captcha_id: str) -> dict:
        """POST auth query to RUNT API by plate via browser fetch."""
        return self._execute_query(page, tipo_consulta="1", campo="placa", valor=placa,
                                   captcha_text=captcha_text, captcha_id=captcha_id)

    def _execute_query(self, page, tipo_consulta: str, campo: str, valor: str,
                       captcha_text: str, captcha_id: str) -> dict:
        """Unified POST auth query to RUNT API via browser fetch.

        Args:
            page: Playwright page with WAF cookies.
            tipo_consulta: "2" for VIN, "1" for plate.
            campo: "vin" or "placa".
            valor: The actual VIN or plate number.
            captcha_text: Solved captcha text.
            captcha_id: Captcha ID from generation step.
        """
        import json

        body = {
            "procedencia": "NACIONAL",
            "tipoConsulta": tipo_consulta,
            "placa": valor if campo == "placa" else None,
            "tipoDocumento": "C",
            "documento": None,
            "vin": valor if campo == "vin" else None,
            "soat": None,
            "aseguradora": "",
            "rtm": None,
            "reCaptcha": None,
            "captcha": captcha_text,
            "valueCaptchaEncripted": "",
            "idLibreCaptcha": captcha_id,
            "verBannerSoat": True,
            "configuracion": {
                "tiempoInactividad": "900",
                "tiempoCuentaRegresiva": "10",
            },
        }

        body_json = json.dumps(body)

        result = page.evaluate(f"""async () => {{
            const r = await fetch('{AUTH_URL}', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: {json.dumps(body_json)},
            }});
            const text = await r.text();
            return {{ status: r.status, body: text }};
        }}""")

        status = result.get("status", 0)
        body_text = result.get("body", "")

        if status == 401 or status == 403:
            raise RuntError(f"Captcha verification failed ({status})")

        if status != 200:
            raise RuntError(f"RUNT API returned {status}: {body_text[:200]}")

        try:
            data = json.loads(body_text)
        except json.JSONDecodeError as e:
            raise RuntError(f"Invalid JSON response: {e}")

        # Check for error in response body
        if isinstance(data, dict):
            error_msg = data.get("mensaje", data.get("message", ""))
            if error_msg and "captcha" in error_msg.lower():
                raise RuntError(f"Captcha error: {error_msg}")
            if data.get("error") is True:
                desc = data.get("descripcionRespuesta", data.get("mensaje", "Unknown error"))
                raise RuntError(f"RUNT error: {desc}")

        return data

    def _parse_response(self, data: dict, vin: str) -> RuntData:
        """Parse RUNT API response into RuntData model."""
        # The response structure may have infoVehiculo or be flat
        vehicle = data
        if "infoVehiculo" in data:
            vehicle = data["infoVehiculo"]
        elif "vehiculo" in data:
            vehicle = data["vehiculo"]

        # Map fields — RUNT uses various key formats
        def g(keys: list[str], default: str = "") -> str:
            """Get first matching key from vehicle data."""
            for k in keys:
                val = vehicle.get(k)
                if val is not None:
                    return str(val).strip()
            return default

        def gi(keys: list[str], default: int = 0) -> int:
            """Get first matching key as int."""
            val = g(keys, str(default))
            try:
                return int(val)
            except (ValueError, TypeError):
                return default

        def gb(keys: list[str], default: bool = False) -> bool:
            """Get first matching key as bool."""
            val = g(keys, "")
            if val.upper() in ("SI", "SÍ", "YES", "TRUE", "1"):
                return True
            if val.upper() in ("NO", "FALSE", "0"):
                return False
            return default

        return RuntData(
            queried_at=datetime.now(),
            # Identificación
            estado=g(["estadoAutomotor", "estado"], ""),
            placa=g(["placa", "placaActual"], ""),
            licencia_transito=g(["numLicencia", "licenciaTransito"], ""),
            id_automotor=gi(["idAutomotor"], 0),
            tarjeta_registro=g(["tarjetaRegistro"], ""),
            # Clasificación
            clase_vehiculo=g(["clase", "claseVehiculo"], ""),
            id_clase_vehiculo=gi(["idClaseVehiculo"], 0),
            clasificacion=g(["clasificacion"], ""),
            tipo_servicio=g(["tipoServicio"], ""),
            # Fabricante
            marca=g(["marca"], ""),
            linea=g(["linea"], ""),
            modelo_ano=g(["modelo"], ""),
            color=g(["color"], ""),
            # Identificadores
            numero_serie=g(["numSerie"], ""),
            numero_motor=g(["numMotor"], ""),
            numero_chasis=g(["numChasis"], ""),
            numero_vin=g(["vin"], vin),
            # Especificaciones
            tipo_combustible=g(["tipoCombustible"], ""),
            tipo_carroceria=g(["tipoCarroceria"], ""),
            cilindraje=g(["cilindraje"], "0"),
            puertas=gi(["puertas"], 0),
            peso_bruto_kg=gi(["pesoBruto"], 0),
            capacidad_carga=g(["capacidadCarga"], ""),
            capacidad_pasajeros=gi(["pasajerosSentados"], 0),
            numero_ejes=gi(["numeroEjes"], 0),
            # Estado legal
            gravamenes=gb(["gravamenes"]),
            prendas=gb(["prendas"]),
            repotenciado=gb(["repotenciado"]),
            antiguo_clasico=gb(["antiguoClasico"]),
            vehiculo_ensenanza=gb(["vehiculoEnsenanza"]),
            seguridad_estado=gb(["seguridadEstado"]),
            # Regrabaciones
            regrabacion_motor=gb(["esRegrabadoMotor"]),
            num_regrabacion_motor=g(["numRegraMotor"], ""),
            regrabacion_chasis=gb(["esRegrabadoChasis"]),
            num_regrabacion_chasis=g(["numRegraChasis"], ""),
            regrabacion_serie=gb(["esRegrabadoSerie"]),
            num_regrabacion_serie=g(["numRegraSerie"], ""),
            regrabacion_vin=gb(["esRegrabadoVin"]),
            num_regrabacion_vin=g(["numRegraVin"], ""),
            # Registro
            fecha_matricula=g(["fechaMatricula"], ""),
            fecha_registro=g(["fechaRegistro"], ""),
            autoridad_transito=g(["organismoTransito"], ""),
            dias_matriculado=gi(["diasMatriculado"], 0) or None,
            # Importación
            importacion=gi(["importacion"], 0),
            fecha_expedicion_lt_importacion=g(["fechaExpedLTImportacion"], ""),
            fecha_vencimiento_lt_importacion=g(["fechaVenciLTImportacion"], ""),
            nombre_pais=g(["nombrePais"], ""),
            # DIAN
            ver_valida_dian=gb(["verValidaDIAN"]),
            validacion_dian=g(["validacionDIAN"], ""),
            # Otros
            subpartida=g(["subpartida"], ""),
            no_identificacion=g(["noIdentificacion"], ""),
            mostrar_solicitudes=gb(["mostrarSolicitudes"]),
        )
