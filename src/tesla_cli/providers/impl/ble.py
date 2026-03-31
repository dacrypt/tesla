"""L0 BLE provider — tesla-control binary.

The highest-priority provider. Works completely offline via Bluetooth.
No internet, no Tesla servers, sub-second latency. Falls back gracefully
if the binary is absent or the key is unconfigured.
"""

from __future__ import annotations

import shutil
import subprocess

from tesla_cli.config import Config
from tesla_cli.providers.base import (
    Capability,
    Provider,
    ProviderPriority,
    ProviderResult,
)

_BLE_COMMANDS = {
    "lock":            "lock",
    "unlock":          "unlock",
    "climate_on":      "climate-on",
    "climate_off":     "climate-off",
    "charge_start":    "charging-start",
    "charge_stop":     "charging-stop",
    "flash_lights":    "flash-lights",
    "honk_horn":       "honk",
    "trunk_open":      "trunk-open",
    "frunk_open":      "frunk-open",
    "windows_vent":    "windows-vent",
    "windows_close":   "windows-close",
}


class BleProvider(Provider):
    """L0 — BLE direct control via tesla-control binary.

    Highest priority: operates entirely offline, no internet required.
    Available only when `tesla-control` binary is on PATH and a BLE key
    has been configured.
    """

    name        = "ble"
    description = "BLE direct (tesla-control binary, offline)"
    layer       = 0
    priority    = ProviderPriority.CRITICAL
    capabilities = frozenset({
        Capability.VEHICLE_COMMAND,   # lock/unlock/climate/charge/horn/flash
    })

    def __init__(self, config: Config) -> None:
        self._cfg = config

    def _binary(self) -> str | None:
        return shutil.which("tesla-control")

    def is_available(self) -> bool:
        return bool(self._binary()) and bool(self._cfg.ble.key_path)

    def health_check(self) -> dict:
        binary = self._binary()
        if not binary:
            return {"status": "down", "latency_ms": 0, "detail": "tesla-control binary not found on PATH"}
        if not self._cfg.ble.key_path:
            return {"status": "down", "latency_ms": 0, "detail": "BLE key not configured (tesla ble setup-key)"}
        return {"status": "ok", "latency_ms": 0, "detail": f"binary={binary}"}

    def execute(self, operation: str, **kwargs) -> ProviderResult:
        ble_cmd = _BLE_COMMANDS.get(operation, operation)
        vin     = kwargs.get("vin") or self._cfg.general.default_vin
        binary  = self._binary()
        if not binary:
            return ProviderResult(ok=False, provider=self.name, error="tesla-control not found")

        args = [binary, "-ble"]
        if vin:
            args += ["-vin", vin]
        if self._cfg.ble.key_path:
            args += ["-key-file", self._cfg.ble.key_path]
        args.append(ble_cmd)

        try:
            r, ms = self._timed(
                subprocess.run,  # noqa: S603
                args, capture_output=True, text=True, timeout=30,
            )
            ok = r.returncode == 0
            return ProviderResult(
                ok=ok, provider=self.name, latency_ms=ms,
                data={"stdout": r.stdout.strip(), "stderr": r.stderr.strip()},
                error=r.stderr.strip() if not ok else None,
            )
        except subprocess.TimeoutExpired:
            return ProviderResult(ok=False, provider=self.name, error="BLE timeout (30s)")
        except Exception as exc:  # noqa: BLE001
            return ProviderResult(ok=False, provider=self.name, error=str(exc))
