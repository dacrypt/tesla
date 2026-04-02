"""Order tracking backend using unofficial Tesla endpoints.

Based on reverse-engineering from:
- teslaorderchecker (WesSec)
- tesla-order-status (niklaswa)
- tesla-delivery-status-web (GewoonJaap)

Delivery details come from browser scraping of the ownership portal SSR page
(window.Tesla.App.DeliveryDetails), since Tesla's API doesn't expose delivery
appointment data via Bearer tokens. The SSR page requires web session cookies.
"""

from __future__ import annotations

import json
import logging
import time as _time
from pathlib import Path
from typing import Any

import httpx
import jwt

from tesla_cli.core.auth import tokens
from tesla_cli.core.auth.oauth import refresh_access_token
from tesla_cli.core.exceptions import ApiError, AuthenticationError, OrderNotFoundError
from tesla_cli.core.models.order import (
    DeliveryAppointment,
    OrderChange,
    OrderDetails,
    OrderStatus,
    OrderTask,
)

logger = logging.getLogger(__name__)

# Tesla API endpoints (unofficial / reverse-engineered)
OWNER_API_BASE = "https://owner-api.teslamotors.com"
ORDERS_URL = f"{OWNER_API_BASE}/api/1/users/orders"
TASKS_API_BASE = "https://akamai-apigateway-vfx.tesla.com"

# Local state files
STATE_DIR = Path.home() / ".tesla-cli" / "state"
ORDER_STATE_FILE = STATE_DIR / "last_order.json"
DELIVERY_CACHE_FILE = STATE_DIR / "delivery.json"


class OrderBackend:
    """Backend for Tesla order tracking and delivery monitoring."""

    def __init__(self) -> None:
        self._client = httpx.Client(timeout=30)

    # ── Authentication ─────────────────────────────────────────

    def _get_access_token(self) -> str:
        """Get a valid access token, refreshing if needed."""
        access = tokens.get_token(tokens.ORDER_ACCESS_TOKEN)
        refresh = tokens.get_token(tokens.ORDER_REFRESH_TOKEN)

        if not refresh:
            raise AuthenticationError(
                "Not authenticated for order tracking. Run: tesla config auth order"
            )

        if access:
            try:
                payload = jwt.decode(access, options={"verify_signature": False})
                if payload.get("exp", 0) > _time.time() + 60:
                    return access
            except jwt.DecodeError:
                pass

        token_data = refresh_access_token(refresh)
        new_access = token_data["access_token"]
        tokens.set_token(tokens.ORDER_ACCESS_TOKEN, new_access)
        if "refresh_token" in token_data:
            tokens.set_token(tokens.ORDER_REFRESH_TOKEN, token_data["refresh_token"])
        return new_access

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json",
            "User-Agent": "tesla-cli/0.1.0",
        }

    # ── Order status (owner-api) ───────────────────────────────

    def get_orders(self) -> list[dict[str, Any]]:
        """List all orders for the authenticated user."""
        resp = self._client.get(ORDERS_URL, headers=self._headers())
        if resp.status_code == 401:
            raise AuthenticationError("Token expired. Run: tesla config auth order")
        if resp.status_code != 200:
            raise ApiError(resp.status_code, f"Failed to get orders: {resp.text}")
        data = resp.json()
        return data.get("response", data) if isinstance(data, dict) else data

    def get_order_status(self, reservation_number: str) -> OrderStatus:
        """Get status for a specific order by RN."""
        orders = self.get_orders()
        for order in orders if isinstance(orders, list) else [orders]:
            rn = order.get("referenceNumber", order.get("rn", ""))
            if rn == reservation_number:
                return self._parse_order_status(order)

        raise OrderNotFoundError(f"Order {reservation_number} not found")

    def get_order_tasks(self, reservation_number: str) -> list[OrderTask]:
        """Get order tasks/steps from the tasks API."""
        params = {
            "referenceNumber": reservation_number,
            "deviceLanguage": "en",
            "deviceCountry": "US",
            "appVersion": "4.40.0",
        }
        resp = self._client.get(
            f"{TASKS_API_BASE}/tasks",
            params=params,
            headers=self._headers(),
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        tasks = []
        for item in data if isinstance(data, list) else data.get("tasks", data.get("response", [])):
            tasks.append(
                OrderTask(
                    task_type=item.get("taskType", item.get("type", "")),
                    task_status=item.get("taskStatus", item.get("status", "")),
                    task_name=item.get("taskName", item.get("name", "")),
                    completed=item.get("completed", False),
                    active=item.get("active", False),
                    details=item,
                )
            )
        return tasks

    def get_order_details(self, reservation_number: str) -> OrderDetails:
        """Get full order details including tasks and delivery data."""
        status = self.get_order_status(reservation_number)
        tasks = self.get_order_tasks(reservation_number)

        # Enrich with delivery cache data
        delivery_data = status.raw.get("delivery", {})
        cached = self._load_delivery_cache()
        if cached:
            dd = cached.get("delivery_details", {})
            timing = dd.get("deliveryTiming", {})
            delivery_data = {
                **delivery_data,
                "appointment": timing.get("appointment", ""),
                "appointmentDateUtc": dd.get("deliveryAppointmentDateUtc", ""),
                "location": timing.get("pickupLocationTitle", ""),
                "address": timing.get("formattedAddressSingleLine", ""),
                "cachedAt": cached.get("fetched_at", ""),
            }

        return OrderDetails(
            status=status,
            tasks=tasks,
            delivery=delivery_data,
            financing=status.raw.get("financing", {}),
            trade_in=status.raw.get("tradeIn", {}),
            registration=status.raw.get("registration", {}),
            vehicle_info=status.raw.get("vehicleInfo", status.raw.get("vehicle", {})),
        )

    # ── Change detection ───────────────────────────────────────

    def detect_changes(self, reservation_number: str) -> list[OrderChange]:
        """Compare current order + delivery state with last saved state.

        Tracks changes in: order status, VIN, delivery date, location, etc.
        Sends notifications via Apprise if configured.
        """
        current = self.get_order_status(reservation_number)
        current_dict = current.model_dump(exclude={"raw"})

        # Enrich with delivery appointment data from cache
        try:
            appointment = self.get_delivery_appointment(reservation_number)
            current_dict["delivery_appointment"] = appointment.appointment_text
            current_dict["delivery_date_utc"] = appointment.date_utc
            current_dict["delivery_location"] = appointment.location_name
        except Exception:
            logger.warning("Failed to enrich order with delivery data", exc_info=True)

        changes: list[OrderChange] = []
        prev_dict = self._load_state()

        if prev_dict:
            for key, new_val in current_dict.items():
                old_val = prev_dict.get(key, "")
                if str(new_val) != str(old_val) and new_val:
                    changes.append(
                        OrderChange(
                            field=key,
                            old_value=str(old_val),
                            new_value=str(new_val),
                        )
                    )

        self._save_state(current_dict)
        return changes

    # ── Delivery details (browser-scraped cache) ───────────────

    def get_delivery_appointment(self, reservation_number: str) -> DeliveryAppointment:
        """Get delivery appointment from local cache.

        Cache is populated via: tesla order delivery --import <file>
        The JSON file is generated by a browser snippet that scrapes
        window.Tesla.App.DeliveryDetails from the SSR order page.
        """
        cached = self._load_delivery_cache()
        if cached:
            dd = cached.get("delivery_details", {})
            timing = dd.get("deliveryTiming", {})
            return DeliveryAppointment(
                appointment_text=timing.get("appointment", ""),
                date_utc=dd.get("deliveryAppointmentDateUtc", ""),
                location_name=timing.get("pickupLocationTitle", ""),
                address=timing.get("formattedAddressSingleLine", ""),
                disclaimer=timing.get("disclaimer", ""),
                duration_minutes=timing.get("duration", 0),
                raw=dd,
            )

        # Fallback: basic order data from owner-api
        try:
            status = self.get_order_status(reservation_number)
            return DeliveryAppointment(
                appointment_text=f"Estimated: {status.estimated_delivery}"
                if status.estimated_delivery
                else "",
                date_utc=status.estimated_delivery,
                raw={"source": "owner-api-fallback", "order_status": status.order_status},
            )
        except Exception:
            logger.warning("Failed to get delivery appointment", exc_info=True)
            return DeliveryAppointment(raw={"source": "no-data"})

    def import_delivery_data(
        self, file_path: str | Path
    ) -> tuple[DeliveryAppointment, list[OrderChange]]:
        """Import delivery data from a browser-scraped JSON file.

        Returns the appointment and any detected changes vs. previous cache.
        """
        path = Path(file_path)
        new_data = json.loads(path.read_text())

        # Detect changes vs. previous cache
        changes: list[OrderChange] = []
        prev = self._load_delivery_cache()
        if prev:
            prev_dd = prev.get("delivery_details", {})
            new_dd = new_data.get("delivery_details", {})
            prev_timing = prev_dd.get("deliveryTiming", {})
            new_timing = new_dd.get("deliveryTiming", {})

            change_fields = [
                (
                    "delivery_date",
                    prev_dd.get("deliveryAppointmentDateUtc", ""),
                    new_dd.get("deliveryAppointmentDateUtc", ""),
                ),
                (
                    "delivery_appointment",
                    prev_timing.get("appointment", ""),
                    new_timing.get("appointment", ""),
                ),
                (
                    "delivery_location",
                    prev_timing.get("pickupLocationTitle", ""),
                    new_timing.get("pickupLocationTitle", ""),
                ),
                (
                    "delivery_address",
                    prev_timing.get("formattedAddressSingleLine", ""),
                    new_timing.get("formattedAddressSingleLine", ""),
                ),
            ]
            for field, old_val, new_val in change_fields:
                if old_val != new_val and new_val:
                    changes.append(
                        OrderChange(field=field, old_value=str(old_val), new_value=str(new_val))
                    )

        self._save_delivery_cache(new_data)
        appointment = self.get_delivery_appointment(
            new_data.get("order", {}).get("referenceNumber", "")
        )
        return appointment, changes

    # ── Order status parsing ───────────────────────────────────

    def _parse_order_status(self, data: dict) -> OrderStatus:
        """Parse raw order data into OrderStatus model.

        Handles multiple response formats from different Tesla API versions.
        Also parses mktOptions to extract config when vehicleInfo is absent.
        """
        vehicle = data.get("vehicleInfo", data.get("vehicle", {}))
        config = vehicle.get("vehicleConfig", vehicle.get("config", {}))
        delivery = data.get("delivery", {})

        # For sparse responses (like CO orders), parse mktOptions
        model = config.get("model", data.get("model", ""))
        exterior_color = config.get("exteriorColor", config.get("PAINT", ""))
        interior_color = config.get("interiorColor", config.get("INTERIOR", ""))
        wheels = config.get("wheels", config.get("WHEELS", ""))
        trim = config.get("trimCode", config.get("trim", ""))

        mkt_options = data.get("mktOptions", "")
        if mkt_options and not model:
            model = data.get("modelCode", "").upper()

        return OrderStatus(
            reservation_number=data.get("referenceNumber", data.get("rn", "")),
            order_status=data.get("orderStatus", data.get("status", "")),
            order_substatus=data.get("orderSubstatus", ""),
            vin=data.get("vin", vehicle.get("vin", "")),
            model=model,
            trim=trim,
            exterior_color=exterior_color,
            interior_color=interior_color,
            wheels=wheels,
            autopilot=config.get("autopilot", ""),
            has_fsd=config.get("fsd", False) or "FSD" in str(config),
            order_date=data.get("orderDate", data.get("createdAt", "")),
            estimated_delivery=delivery.get("estimatedDeliveryDate", ""),
            delivery_window_start=delivery.get(
                "windowStart", delivery.get("deliveryWindowStart", "")
            ),
            delivery_window_end=delivery.get("windowEnd", delivery.get("deliveryWindowEnd", "")),
            country=data.get("country", data.get("countryCode", "")),
            state_or_province=data.get("stateProvince", data.get("region", "")),
            mkt_options=mkt_options,
            raw=data,
        )

    # ── State persistence ──────────────────────────────────────

    def _load_state(self) -> dict | None:
        if ORDER_STATE_FILE.exists():
            return json.loads(ORDER_STATE_FILE.read_text())
        return None

    def _save_state(self, data: dict) -> None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        ORDER_STATE_FILE.write_text(json.dumps(data, default=str))

    def _load_delivery_cache(self) -> dict | None:
        if DELIVERY_CACHE_FILE.exists():
            return json.loads(DELIVERY_CACHE_FILE.read_text())
        return None

    def _save_delivery_cache(self, data: dict) -> None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        DELIVERY_CACHE_FILE.write_text(json.dumps(data, default=str, indent=2))
