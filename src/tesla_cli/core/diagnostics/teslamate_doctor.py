"""TeslaMate stack doctor — 8 read-only checks reported as a structured report.

Each check is a pure function that swallows exceptions and returns a
``DoctorCheck``. ``run_doctor`` always returns a complete report, never
raises, so the CLI/API can rely on getting back a result.
"""

from __future__ import annotations

import logging
import subprocess
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel

logger = logging.getLogger(__name__)


# Required columns on the TeslaMate ``charges`` table for the curve queries.
REQUIRED_CHARGES_COLUMNS: tuple[str, ...] = (
    "date",
    "battery_level",
    "charger_power",
    "charger_actual_current",
    "charger_voltage",
    "charger_phases",
    "ideal_battery_range_km",
)


class DoctorCheck(BaseModel):
    """A single diagnostic check result."""

    name: str
    label: str
    ok: bool
    message: str
    hint: str | None = None


class DoctorReport(BaseModel):
    """Aggregated report from ``run_doctor``."""

    checks: list[DoctorCheck]
    failed: int
    total: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _backend_for(cfg: Any):
    """Build a TeslaMateBacked from cfg.teslaMate.database_url."""
    from tesla_cli.core.backends.teslaMate import TeslaMateBacked

    url = getattr(cfg.teslaMate, "database_url", "") or ""
    car_id = getattr(cfg.teslaMate, "car_id", 1) or 1
    return TeslaMateBacked(url, car_id=car_id)


def _stack_status() -> list[dict[str, Any]]:
    """Return TeslaMateStack().status() or [] on failure."""
    try:
        from tesla_cli.infra.teslamate_stack import TeslaMateStack

        return TeslaMateStack().status()
    except Exception:
        logger.warning("teslamate doctor: stack status failed", exc_info=True)
        return []


def _stack_grafana_port() -> int:
    """Best-effort lookup of the published Grafana port from cfg/stack."""
    try:
        from tesla_cli.core.config import load_config

        cfg = load_config()
        port = getattr(cfg.teslaMate, "grafana_port", 0) or 0
        if port:
            return int(port)
    except Exception:
        logger.warning("teslamate doctor: cfg load for grafana port failed", exc_info=True)
    return 3000


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def check_docker_daemon() -> DoctorCheck:
    name = "docker_daemon"
    label = "Docker daemon"
    try:
        r = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
        )
        if r.returncode == 0:
            return DoctorCheck(name=name, label=label, ok=True, message="docker info OK")
        return DoctorCheck(
            name=name,
            label=label,
            ok=False,
            message=f"docker info exit={r.returncode}",
            hint="Inicia Docker Desktop o `sudo systemctl start docker`.",
        )
    except FileNotFoundError:
        return DoctorCheck(
            name=name,
            label=label,
            ok=False,
            message="docker binary no encontrado en PATH",
            hint="Instala Docker: https://docs.docker.com/get-docker/",
        )
    except Exception as exc:  # subprocess.TimeoutExpired, OSError, etc.
        return DoctorCheck(
            name=name,
            label=label,
            ok=False,
            message=f"error ejecutando docker info: {exc}",
            hint="Verifica que el daemon de Docker esté corriendo.",
        )


def check_stack_running(stack_status: list[dict[str, Any]]) -> DoctorCheck:
    name = "stack_running"
    label = "Stack TeslaMate corriendo"
    try:
        running: dict[str, bool] = {}
        for svc in stack_status:
            svc_name = (svc.get("name") or "").lower()
            running[svc_name] = svc.get("state") == "running"
        # The compose template uses services: postgres, mosquitto, teslamate, grafana.
        teslamate_ok = running.get("teslamate", False)
        db_ok = running.get("postgres", False) or running.get("db", False)
        if teslamate_ok and db_ok:
            return DoctorCheck(
                name=name, label=label, ok=True, message="teslamate + postgres running"
            )
        missing = []
        if not teslamate_ok:
            missing.append("teslamate")
        if not db_ok:
            missing.append("postgres")
        return DoctorCheck(
            name=name,
            label=label,
            ok=False,
            message=f"servicios no running: {', '.join(missing) or 'ninguno detectado'}",
            hint="Arranca el stack con `tesla teslaMate start` o `tesla teslaMate install`.",
        )
    except Exception as exc:
        return DoctorCheck(
            name=name,
            label=label,
            ok=False,
            message=f"error consultando estado: {exc}",
            hint="Revisa que `docker compose` esté disponible.",
        )


def check_db_reachable(cfg: Any) -> DoctorCheck:
    name = "db_reachable"
    label = "DB TeslaMate alcanzable"
    url = getattr(cfg.teslaMate, "database_url", "") or ""
    if not url:
        return DoctorCheck(
            name=name,
            label=label,
            ok=False,
            message="cfg.teslaMate.database_url está vacío",
            hint="Configura con `tesla teslaMate connect postgresql://...` o `tesla teslaMate install`.",
        )
    try:
        backend = _backend_for(cfg)
        ok = bool(backend.ping())
        if ok:
            return DoctorCheck(name=name, label=label, ok=True, message="ping() OK")
        return DoctorCheck(
            name=name,
            label=label,
            ok=False,
            message="ping() devolvió False",
            hint=(
                "Verifica que el contenedor postgres esté arriba y que la DSN apunte al puerto "
                "publicado (ver check `dsn_host_correct`)."
            ),
        )
    except Exception as exc:
        return DoctorCheck(
            name=name,
            label=label,
            ok=False,
            message=f"excepción durante ping: {exc}",
            hint="Revisa la DSN, las credenciales y que el contenedor esté arriba.",
        )


def check_dsn_host_correct(cfg: Any, stack_status: list[dict[str, Any]]) -> DoctorCheck:
    name = "dsn_host_correct"
    label = "DSN host correcto"
    url = getattr(cfg.teslaMate, "database_url", "") or ""
    if not url:
        return DoctorCheck(
            name=name,
            label=label,
            ok=False,
            message="cfg.teslaMate.database_url está vacío",
            hint="Configura una DSN apuntando a `localhost:<puerto_publicado>`.",
        )
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
    except Exception as exc:
        return DoctorCheck(
            name=name,
            label=label,
            ok=False,
            message=f"DSN inválida: {exc}",
            hint="Usa el formato `postgresql://user:pass@localhost:5432/teslamate`.",
        )

    local_hosts = {"", "localhost", "127.0.0.1", "::1"}
    if host in local_hosts:
        return DoctorCheck(name=name, label=label, ok=True, message=f"host={host or 'localhost'}")

    # Host is non-local — fail only if the managed stack is detected running locally.
    stack_running_locally = any((svc.get("state") == "running") for svc in stack_status)
    pg_port = getattr(cfg.teslaMate, "postgres_port", 5432) or 5432
    suggested = f"postgresql://teslamate:<password>@localhost:{pg_port}/teslamate"
    if stack_running_locally:
        return DoctorCheck(
            name=name,
            label=label,
            ok=False,
            message=f"DSN apunta a host `{host}`, pero el stack corre localmente",
            hint=(
                f"Tu API corre en host pero el DSN apunta a `{host}` (nombre de contenedor). "
                f"Cámbialo a `localhost:{pg_port}`. Sugerencia: {suggested}. "
                "El flag `tesla teslaMate doctor --fix` está planeado para automatizar este cambio."
            ),
        )
    return DoctorCheck(
        name=name,
        label=label,
        ok=True,
        message=f"host={host} (stack no corre local — se acepta)",
    )


def check_car_registered(cfg: Any) -> DoctorCheck:
    name = "car_registered"
    label = "Vehículo registrado en TeslaMate"
    try:
        backend = _backend_for(cfg)
        with backend._cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM cars")
            row = cur.fetchone()
        count = int((row or {}).get("n", 0)) if isinstance(row, dict) else int((row or [0])[0])
        if count >= 1:
            return DoctorCheck(
                name=name, label=label, ok=True, message=f"{count} vehículo(s) en `cars`"
            )
        return DoctorCheck(
            name=name,
            label=label,
            ok=False,
            message="tabla `cars` vacía",
            hint=(
                "TeslaMate no ve ningún vehículo. Inicia sesión en TeslaMate UI (puerto 4000) "
                "con tus tokens Tesla."
            ),
        )
    except Exception as exc:
        return DoctorCheck(
            name=name,
            label=label,
            ok=False,
            message=f"no se pudo consultar `cars`: {exc}",
            hint="Verifica que la DB sea alcanzable (ver check `db_reachable`).",
        )


def check_recent_charge_data(cfg: Any) -> DoctorCheck:
    name = "recent_charge_data"
    label = "Muestras de carga recientes"
    try:
        backend = _backend_for(cfg)
        with backend._cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM cars")
            row = cur.fetchone()
            cars_count = (
                int((row or {}).get("n", 0)) if isinstance(row, dict) else int((row or [0])[0])
            )
            if cars_count == 0:
                # Fresh install: defer to car_registered, don't double-fail.
                return DoctorCheck(
                    name=name,
                    label=label,
                    ok=True,
                    message="omitido: no hay vehículos registrados",
                )

            cur.execute("SELECT COUNT(*) AS n FROM charges WHERE date > NOW() - INTERVAL '30 days'")
            row = cur.fetchone()
            charges_count = (
                int((row or {}).get("n", 0)) if isinstance(row, dict) else int((row or [0])[0])
            )
        if charges_count >= 1:
            return DoctorCheck(
                name=name,
                label=label,
                ok=True,
                message=f"{charges_count} muestra(s) en últimos 30 días",
            )
        return DoctorCheck(
            name=name,
            label=label,
            ok=False,
            message="0 muestras de carga en últimos 30 días",
            hint=(
                "Sin muestras de carga en 30 días — verifica que TeslaMate esté logueado y "
                "el vehículo haya cargado."
            ),
        )
    except Exception as exc:
        return DoctorCheck(
            name=name,
            label=label,
            ok=False,
            message=f"no se pudo consultar `charges`: {exc}",
            hint="Verifica que la DB sea alcanzable (ver check `db_reachable`).",
        )


def check_grafana_reachable(stack_status: list[dict[str, Any]], port: int) -> DoctorCheck:
    name = "grafana_reachable"
    label = "Grafana alcanzable"
    stack_running_any = any(svc.get("state") == "running" for svc in stack_status)
    if not stack_running_any:
        return DoctorCheck(
            name=name,
            label=label,
            ok=True,
            message="skipped: stack not running",
        )
    url = f"http://localhost:{port}/api/health"
    try:
        import urllib.request

        with urllib.request.urlopen(url, timeout=3) as resp:  # noqa: S310 (localhost only)
            status = getattr(resp, "status", None) or resp.getcode()
        if status == 200:
            return DoctorCheck(name=name, label=label, ok=True, message=f"GET {url} → 200")
        return DoctorCheck(
            name=name,
            label=label,
            ok=False,
            message=f"GET {url} → {status}",
            hint="Mira los logs: `tesla teslaMate logs grafana`.",
        )
    except Exception as exc:
        return DoctorCheck(
            name=name,
            label=label,
            ok=False,
            message=f"GET {url} falló: {exc}",
            hint="Revisa que el contenedor grafana esté arriba y el puerto publicado.",
        )


def check_schema_columns(cfg: Any) -> DoctorCheck:
    name = "schema_columns"
    label = "Esquema `charges` (columnas requeridas)"
    try:
        backend = _backend_for(cfg)
        with backend._cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'charges'"
            )
            rows = cur.fetchall() or []
        present: set[str] = set()
        for r in rows:
            col = r.get("column_name") if isinstance(r, dict) else (r[0] if r else None)
            if col:
                present.add(str(col))
        missing = [c for c in REQUIRED_CHARGES_COLUMNS if c not in present]
        if not missing:
            return DoctorCheck(
                name=name,
                label=label,
                ok=True,
                message=f"{len(REQUIRED_CHARGES_COLUMNS)} columnas presentes",
            )
        return DoctorCheck(
            name=name,
            label=label,
            ok=False,
            message=f"falta(n) columna(s): {', '.join(missing)}",
            hint=(
                f"TeslaMate schema drift detectado — falta(n) columna(s): {', '.join(missing)}. "
                "Verifica versión de TeslaMate."
            ),
        )
    except Exception as exc:
        return DoctorCheck(
            name=name,
            label=label,
            ok=False,
            message=f"no se pudo introspectar `charges`: {exc}",
            hint="Verifica que la DB sea alcanzable (ver check `db_reachable`).",
        )


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


def run_doctor(cfg: Any) -> DoctorReport:
    """Run all 8 checks and return a complete ``DoctorReport``.

    Never raises — each individual check wraps its own failure modes.
    """
    stack_status = _stack_status()
    grafana_port = _stack_grafana_port()

    checks: list[DoctorCheck] = [
        check_docker_daemon(),
        check_stack_running(stack_status),
        check_db_reachable(cfg),
        check_dsn_host_correct(cfg, stack_status),
        check_car_registered(cfg),
        check_recent_charge_data(cfg),
        check_grafana_reachable(stack_status, grafana_port),
        check_schema_columns(cfg),
    ]
    failed = sum(1 for c in checks if not c.ok)
    return DoctorReport(checks=checks, failed=failed, total=len(checks))
