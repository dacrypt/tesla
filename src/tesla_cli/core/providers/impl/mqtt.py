"""L3 MQTT provider — publish vehicle state to an MQTT broker.

Outbound-only telemetry sink. On each `execute("push", data=..., vin=...)` call
it connects to the configured broker, publishes one JSON message per top-level
vehicle state key to `<topic_prefix>/<vin>/<key>`, then disconnects.

Topic layout (default prefix = "tesla"):
  tesla/<VIN>/charge_state  → {"battery_level": 80, ...}
  tesla/<VIN>/drive_state   → {"latitude": ..., ...}
  tesla/<VIN>/climate_state → {"inside_temp": ..., ...}
  tesla/<VIN>/vehicle_state → {"locked": true, ...}
  tesla/<VIN>/state         → full vehicle data blob

Requires paho-mqtt: `pip install 'tesla-cli[mqtt]'`
"""

from __future__ import annotations

import json
import time

from tesla_cli.config import Config
from tesla_cli.providers.base import (
    Capability,
    Provider,
    ProviderPriority,
    ProviderResult,
)


class MqttProvider(Provider):
    """L3 — MQTT telemetry sink.

    Publishes vehicle state snapshots to a configurable MQTT broker.
    Compatible with Home Assistant MQTT discovery, Node-RED, InfluxDB
    Telegraf, and any other MQTT consumer.
    """

    name        = "mqtt"
    description = "MQTT broker telemetry publisher"
    layer       = 3
    priority    = ProviderPriority.LOW
    capabilities = frozenset({Capability.TELEMETRY_PUSH})

    def __init__(self, config: Config) -> None:
        self._cfg = config

    @property
    def _mcfg(self):
        return self._cfg.mqtt

    def is_available(self) -> bool:
        if not self._mcfg.broker:
            return False
        try:
            import paho.mqtt.client  # noqa: F401
            return True
        except ImportError:
            return False

    def health_check(self) -> dict:
        if not self._mcfg.broker:
            return {"status": "down", "latency_ms": 0, "detail": "mqtt.broker not configured"}
        try:
            import paho.mqtt.client  # noqa: F401
        except ImportError:
            return {"status": "down", "latency_ms": 0,
                    "detail": "paho-mqtt not installed (pip install 'tesla-cli[mqtt]')"}

        try:
            t0 = time.monotonic()
            client = self._make_client("health-check")
            client.connect(self._mcfg.broker, self._mcfg.port, keepalive=5)
            client.disconnect()
            ms = (time.monotonic() - t0) * 1000
            return {"status": "ok", "latency_ms": round(ms, 1),
                    "detail": f"broker={self._mcfg.broker}:{self._mcfg.port}"}
        except Exception as exc:  # noqa: BLE001
            return {"status": "down", "latency_ms": 0, "detail": str(exc)}

    def execute(self, operation: str, **kwargs) -> ProviderResult:
        if operation not in ("push", "send"):
            return ProviderResult(ok=False, provider=self.name, error=f"Unknown operation: {operation}")

        data = kwargs.get("data") or {}
        vin  = kwargs.get("vin") or "unknown"

        try:
            prefix = (self._mcfg.topic_prefix or "tesla").rstrip("/")
            client = self._make_client(f"tesla-cli-{vin[-6:]}")

            t0 = time.monotonic()
            client.connect(self._mcfg.broker, self._mcfg.port, keepalive=30)

            msgs_published = 0
            # Publish each top-level state key as its own subtopic
            for key in ("charge_state", "drive_state", "climate_state", "vehicle_state"):
                if key in data and data[key]:
                    topic   = f"{prefix}/{vin}/{key}"
                    payload = json.dumps(data[key], default=str)
                    client.publish(topic, payload, qos=self._mcfg.qos, retain=self._mcfg.retain)
                    msgs_published += 1

            # Also publish the full blob for consumers that want everything
            full_topic = f"{prefix}/{vin}/state"
            client.publish(full_topic, json.dumps(data, default=str),
                           qos=self._mcfg.qos, retain=self._mcfg.retain)
            msgs_published += 1

            client.loop(timeout=0.5)  # flush outgoing queue
            client.disconnect()

            ms = (time.monotonic() - t0) * 1000
            return ProviderResult(
                ok=True,
                data={"messages": msgs_published, "broker": self._mcfg.broker},
                provider=self.name,
                latency_ms=ms,
            )
        except Exception as exc:  # noqa: BLE001
            return ProviderResult(ok=False, provider=self.name, error=str(exc))

    def fetch(self, operation: str, **kwargs) -> ProviderResult:
        return ProviderResult(ok=False, provider=self.name, error="MQTT provider is write-only")

    def status_row(self) -> dict:
        available = self.is_available()
        detail = self._mcfg.broker or "not configured"
        if available:
            detail = f"{self._mcfg.broker}:{self._mcfg.port}"
        return {
            "name":        self.name,
            "layer":       f"L{self.layer}",
            "available":   available,
            "capabilities": ", ".join(sorted(self.capabilities)),
            "detail":      detail,
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _make_client(self, client_id: str):
        import paho.mqtt.client as mqtt

        client = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv311)
        if self._mcfg.username:
            client.username_pw_set(self._mcfg.username, self._mcfg.password or "")
        if self._mcfg.tls:
            client.tls_set()
        return client
