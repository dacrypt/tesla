"""Cached vehicle backend — TTL cache + request coalescing.

Wraps any VehicleBackend to:
1. Cache get_vehicle_data() responses for TTL seconds
2. Deduplicate concurrent requests for the same VIN
3. Derive charge/climate/drive state from cached vehicle_data
"""

from __future__ import annotations

import threading
import time
from typing import Any

from tesla_cli.core.backends.base import VehicleBackend


class CachedVehicleBackend(VehicleBackend):
    def __init__(self, inner: VehicleBackend, ttl: int = 45) -> None:
        self._inner = inner
        self._ttl = ttl
        self._cache: dict[str, tuple[Any, float]] = {}  # key → (data, timestamp)
        self._pending: dict[str, threading.Event] = {}  # key → in-flight event
        self._lock = threading.Lock()

    def _get_or_fetch(self, key: str, fetch_fn) -> Any:
        """Check cache → wait for pending → fetch + cache."""
        with self._lock:
            # Check cache
            if key in self._cache:
                data, ts = self._cache[key]
                if time.time() - ts < self._ttl:
                    return data

            # Check if another thread is already fetching
            if key in self._pending:
                event = self._pending[key]
                # Release lock and wait
                self._lock.release()
                try:
                    event.wait(timeout=30)
                finally:
                    self._lock.acquire()
                if key in self._cache:
                    return self._cache[key][0]
                raise RuntimeError(f"Coalesced request for {key} failed")

            # Mark as pending
            event = threading.Event()
            self._pending[key] = event

        # Fetch outside lock
        try:
            data = fetch_fn()
            with self._lock:
                self._cache[key] = (data, time.time())
                return data
        finally:
            with self._lock:
                self._pending.pop(key, None)
                event.set()

    def invalidate(self, vin: str | None = None) -> None:
        """Clear cache after commands (lock, climate, etc.)."""
        with self._lock:
            if vin:
                keys = [k for k in self._cache if vin in k]
                for k in keys:
                    del self._cache[k]
            else:
                self._cache.clear()

    # ── VehicleBackend interface ──

    def list_vehicles(self) -> list:
        return self._get_or_fetch("list_vehicles", self._inner.list_vehicles)

    def get_vehicle_data(self, vin: str) -> dict:
        return self._get_or_fetch(f"vdata:{vin}", lambda: self._inner.get_vehicle_data(vin))

    def get_charge_state(self, vin: str) -> dict:
        data = self.get_vehicle_data(vin)
        return data.get("charge_state", data)

    def get_climate_state(self, vin: str) -> dict:
        data = self.get_vehicle_data(vin)
        return data.get("climate_state", data)

    def get_drive_state(self, vin: str) -> dict:
        data = self.get_vehicle_data(vin)
        return data.get("drive_state", data)

    def get_vehicle_state(self, vin: str) -> dict:
        data = self.get_vehicle_data(vin)
        return data.get("vehicle_state", data)

    def get_vehicle_config(self, vin: str) -> dict:
        data = self.get_vehicle_data(vin)
        return data.get("vehicle_config", data)

    # ── Commands pass through + invalidate cache ──

    def command(self, vin: str, cmd: str, **params) -> dict:
        from tesla_cli.core.exceptions import BackendNotSupportedError

        try:
            result = self._inner.command(vin, cmd, **params)
        except BackendNotSupportedError:
            self.invalidate(vin)  # Invalidate even on VCP errors to prevent stale state
            raise
        self.invalidate(vin)  # Clear cache after state-changing command
        return result

    def wake_up(self, vin: str) -> bool:
        result = self._inner.wake_up(vin)
        self.invalidate(vin)
        return result

    # ── Delegate remaining methods ──
    # These pass through to the inner backend unchanged. They aren't cached
    # because they are either rarely called, already time-bounded by the
    # server, or state-mutating. Without these explicit forwards, the base
    # VehicleBackend stubs raise BackendNotSupportedError even when the inner
    # (e.g. Fleet) backend implements them.

    def mobile_enabled(self, vin: str) -> bool:
        return self._inner.mobile_enabled(vin)

    def get_nearby_charging_sites(self, vin: str) -> dict:
        return self._inner.get_nearby_charging_sites(vin)

    def get_service_data(self, vin: str) -> dict:
        return self._inner.get_service_data(vin)

    def get_release_notes(self, vin: str) -> dict:
        return self._inner.get_release_notes(vin)

    def get_recent_alerts(self, vin: str) -> dict:
        return self._inner.get_recent_alerts(vin)

    def get_fleet_status(self, vin: str) -> dict:
        return self._inner.get_fleet_status(vin)

    def get_charge_history(self) -> dict:
        return self._inner.get_charge_history()

    def get_safety_score(self, vin: str) -> dict:
        return self._inner.get_safety_score(vin)

    def get_drive_score(self, vin: str) -> dict:
        return self._inner.get_drive_score(vin)

    def get_service_visits(self, vin: str) -> list:
        return self._inner.get_service_visits(vin)

    def get_service_appointments(self) -> dict:
        return self._inner.get_service_appointments()

    def get_invitations(self, vin: str) -> list:
        return self._inner.get_invitations(vin)

    def create_invitation(self, vin: str) -> dict:
        result = self._inner.create_invitation(vin)
        self.invalidate(vin)
        return result

    def revoke_invitation(self, vin: str, invitation_id: str) -> dict:
        result = self._inner.revoke_invitation(vin, invitation_id)
        self.invalidate(vin)
        return result

    def add_charge_schedule(
        self, vin: str, days: str, time: int, lat: float, lon: float, enabled: bool = True
    ) -> dict:
        result = self._inner.add_charge_schedule(vin, days, time, lat, lon, enabled)
        self.invalidate(vin)
        return result

    def remove_charge_schedule(self, vin: str, schedule_id: int) -> dict:
        result = self._inner.remove_charge_schedule(vin, schedule_id)
        self.invalidate(vin)
        return result

    def add_precondition_schedule(
        self, vin: str, days: str, time: int, lat: float, lon: float, enabled: bool = True
    ) -> dict:
        result = self._inner.add_precondition_schedule(vin, days, time, lat, lon, enabled)
        self.invalidate(vin)
        return result

    def remove_precondition_schedule(self, vin: str, schedule_id: int) -> dict:
        result = self._inner.remove_precondition_schedule(vin, schedule_id)
        self.invalidate(vin)
        return result
