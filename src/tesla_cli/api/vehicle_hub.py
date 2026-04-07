"""VehicleStateHub — single poller, broadcast to all SSE clients.

One background thread polls Tesla API at smart intervals.
SSE clients subscribe to receive push updates. REST endpoints
read the latest cached state without hitting Tesla API.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from typing import Any

log = logging.getLogger("tesla-cli.hub")

# Intervals (seconds)
NORMAL_INTERVAL = 30
DEGRADED_INTERVAL = 300  # 412 / asleep / repeated errors
MAX_CONSECUTIVE_ERRORS = 3


class VehicleStateHub:
    """Shared vehicle state poller + SSE broadcaster."""

    def __init__(self, backend: Any, vin: str, interval: int = NORMAL_INTERVAL) -> None:
        self._backend = backend
        self._vin = vin
        self._base_interval = interval
        self._interval = interval

        # Latest state
        self._latest: dict | None = None
        self._last_ts: float = 0
        self._error: str | None = None
        self._pre_delivery = False

        # SSE subscribers (asyncio queues)
        self._clients: list[asyncio.Queue] = []
        self._clients_lock = threading.Lock()

        # Polling control
        self._stopped = False
        self._consecutive_errors = 0
        self._wake_event = threading.Event()

    # ── Public API ──

    def start(self) -> None:
        """Start the background polling thread."""
        t = threading.Thread(target=self._poll_loop, daemon=True, name="vehicle-hub")
        t.start()
        log.info("VehicleStateHub started (vin=%s, interval=%ds)", self._vin[:8], self._interval)

    def stop(self) -> None:
        """Signal the polling thread to stop."""
        self._stopped = True
        self._wake_event.set()

    def get_latest(self) -> dict | None:
        """Return the most recent vehicle state (no API call)."""
        return self._latest

    def get_latest_ts(self) -> float:
        """Timestamp of the last successful fetch."""
        return self._last_ts

    def get_error(self) -> str | None:
        """Last error message, if any."""
        return self._error

    def is_pre_delivery(self) -> bool:
        return self._pre_delivery

    def invalidate(self) -> None:
        """Force an immediate re-fetch (e.g., after a command)."""
        self._wake_event.set()

    def subscribe(self) -> asyncio.Queue:
        """Register an SSE client. Returns a queue that receives events."""
        q: asyncio.Queue = asyncio.Queue(maxsize=10)
        with self._clients_lock:
            self._clients.append(q)
        log.debug("SSE client subscribed (%d total)", len(self._clients))
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        """Remove an SSE client."""
        with self._clients_lock:
            try:
                self._clients.remove(q)
            except ValueError:
                pass
        log.debug("SSE client unsubscribed (%d remaining)", len(self._clients))

    # ── Background polling ──

    def _poll_loop(self) -> None:
        """Main polling loop — runs in a daemon thread."""
        while not self._stopped:
            try:
                data = self._backend.get_vehicle_data(self._vin)
                self._latest = data
                self._last_ts = time.time()
                self._error = None
                self._consecutive_errors = 0
                self._pre_delivery = False

                # Reset to normal interval on success
                if self._interval != self._base_interval:
                    log.info("Hub recovered — interval back to %ds", self._base_interval)
                    self._interval = self._base_interval

                # Broadcast to SSE clients
                self._broadcast(data)

            except Exception as exc:
                err_str = str(exc)
                self._error = err_str
                self._consecutive_errors += 1

                if "412" in err_str:
                    self._pre_delivery = True
                    self._interval = DEGRADED_INTERVAL
                    log.info("Hub got 412 (pre-delivery) — slowing to %ds", self._interval)
                    # Broadcast error event so frontend knows
                    self._broadcast_error("pre_delivery", "Vehicle not accessible (pre-delivery)")
                elif "asleep" in err_str.lower() or "408" in err_str:
                    self._interval = DEGRADED_INTERVAL
                    log.debug("Vehicle asleep — slowing to %ds", self._interval)
                    self._broadcast_error("asleep", "Vehicle is asleep")
                elif self._consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    self._interval = DEGRADED_INTERVAL
                    log.warning(
                        "Hub: %d consecutive errors — slowing to %ds: %s",
                        self._consecutive_errors, self._interval, err_str,
                    )
                else:
                    log.debug("Hub poll error (%d/%d): %s", self._consecutive_errors, MAX_CONSECUTIVE_ERRORS, err_str)

            # Sleep with wake support (invalidate() can interrupt)
            self._wake_event.wait(timeout=self._interval)
            self._wake_event.clear()

    def _broadcast(self, data: dict) -> None:
        """Push vehicle data to all connected SSE clients."""
        ts = int(time.time())
        payload = json.dumps({"ts": ts, "data": _sanitize(data)})
        event = f"event: vehicle\ndata: {payload}\n\n"
        self._send_to_clients(event)

    def _broadcast_error(self, error_type: str, message: str) -> None:
        """Push error event to all connected SSE clients."""
        payload = json.dumps({"error": error_type, "message": message})
        event = f"event: error\ndata: {payload}\n\n"
        self._send_to_clients(event)

    def _send_to_clients(self, event: str) -> None:
        """Send an SSE event string to all subscriber queues."""
        with self._clients_lock:
            dead: list[asyncio.Queue] = []
            for q in self._clients:
                try:
                    q.put_nowait(event)
                except asyncio.QueueFull:
                    # Client is too slow — drop oldest and push new
                    try:
                        q.get_nowait()
                        q.put_nowait(event)
                    except Exception:
                        dead.append(q)
            for q in dead:
                try:
                    self._clients.remove(q)
                except ValueError:
                    pass


def _sanitize(data: Any) -> Any:
    """Remove non-JSON-serializable values (NaN, Inf)."""
    if isinstance(data, dict):
        return {k: _sanitize(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_sanitize(v) for v in data]
    if isinstance(data, float):
        import math
        if math.isnan(data) or math.isinf(data):
            return None
    return data
