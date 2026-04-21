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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import jwt

from tesla_cli import __version__
from tesla_cli.core.auth import tokens
from tesla_cli.core.auth.oauth import refresh_access_token
from tesla_cli.core.exceptions import ApiError, AuthenticationError, OrderNotFoundError
from tesla_cli.core.models.order import (
    DeliveryAppointment,
    OrderChange,
    OrderDetails,
    OrderStatus,
    OrderTask,
    PortalDocument,
)

logger = logging.getLogger(__name__)

# Tesla API endpoints (unofficial / reverse-engineered)
OWNER_API_BASE = "https://owner-api.teslamotors.com"
ORDERS_URL = f"{OWNER_API_BASE}/api/1/users/orders"
TASKS_API_BASE = "https://akamai-apigateway-vfx.tesla.com"

# Local state files
TESLA_CLI_DIR = Path.home() / ".tesla-cli"
STATE_DIR = TESLA_CLI_DIR / "state"
SOURCES_DIR = TESLA_CLI_DIR / "sources"
ORDER_STATE_FILE = STATE_DIR / "last_order.json"
DELIVERY_CACHE_FILE = STATE_DIR / "delivery.json"
PORTAL_CACHE_FILE = SOURCES_DIR / "tesla.portal.json"
DELIVERY_CACHE_MAX_AGE_HOURS = 72


class OrderBackend:
    """Backend for Tesla order tracking and delivery monitoring."""

    def __init__(self) -> None:
        self._client = httpx.Client(timeout=30)
        self.last_query_meta: dict[str, Any] = {}

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
            "User-Agent": f"tesla-cli/{__version__}",
        }

    # ── Order status (owner-api) ───────────────────────────────

    def get_orders(self) -> list[dict[str, Any]]:
        """List all orders for the authenticated user."""
        resp = self._client.get(ORDERS_URL, headers=self._headers())
        self.last_query_meta = {
            "url": str(resp.request.url),
            "method": resp.request.method,
            "status_code": resp.status_code,
            "response_text_excerpt": resp.text[:2000],
        }
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
        """Get order tasks/steps from Tesla, falling back to cached portal data."""
        params = {
            "referenceNumber": reservation_number,
            "deviceLanguage": "es",
            "deviceCountry": "CO",
            "appVersion": "4.50.0",
        }
        resp = self._client.get(
            f"{TASKS_API_BASE}/tasks",
            params=params,
            headers=self._headers(),
        )
        self.last_query_meta = {
            "url": str(resp.request.url),
            "method": resp.request.method,
            "status_code": resp.status_code,
            "response_text_excerpt": resp.text[:2000],
        }
        if resp.status_code == 200:
            data = resp.json()
            parsed = self._parse_task_items(
                data if isinstance(data, list) else data.get("tasks", data.get("response", []))
            )
            if parsed:
                return parsed

        portal_tasks = self._load_portal_tasks_for_order(reservation_number)
        if portal_tasks:
            return portal_tasks
        return []

    def get_order_details(self, reservation_number: str) -> OrderDetails:
        """Get full order details including tasks and delivery data."""
        status = self.get_order_status(reservation_number)
        tasks = self.get_order_tasks(reservation_number)
        if not tasks:
            tasks = self._extract_tasks_from_order_payload(status.raw)

        delivery_data = self._build_delivery_data(
            reservation_number=reservation_number,
            vin=status.vin,
            raw_order=status.raw,
        )

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
        status = None
        try:
            status = self.get_order_status(reservation_number)
        except Exception:
            logger.warning(
                "Failed to resolve live order status for delivery cache validation", exc_info=True
            )

        cached = self._load_delivery_cache_for_order(
            reservation_number=reservation_number,
            vin=status.vin if status else "",
        )
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
            status = status or self.get_order_status(reservation_number)
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

    # ── Portal documents ───────────────────────────────────────

    def get_portal_documents(self, portal_data: dict) -> list[PortalDocument]:
        """Extract document metadata from portal scrape data.

        Scans all window.Tesla.App.* keys for document-like objects:
        - Objects with url/name/type fields
        - Lists of objects with .pdf URLs
        - Known keys: Documents, DocumentList, OrderDocuments
        """
        docs: list[PortalDocument] = []
        seen_urls: set[str] = set()

        def _extract_from_value(value: object, category: str = "") -> None:
            if isinstance(value, list):
                for item in value:
                    _extract_from_value(item, category)
            elif isinstance(value, dict):
                url = value.get("url", value.get("URL", value.get("downloadUrl", "")))
                name = value.get(
                    "name",
                    value.get("title", value.get("documentName", value.get("fileName", ""))),
                )
                doc_type = value.get(
                    "type", value.get("documentType", value.get("category", category))
                )
                doc_id = value.get("id", value.get("documentId", value.get("document_id", "")))
                if url and isinstance(url, str) and url not in seen_urls:
                    seen_urls.add(url)
                    docs.append(
                        PortalDocument(
                            document_id=str(doc_id),
                            name=str(name or url.split("/")[-1].split("?")[0]),
                            category=str(doc_type or category),
                            url=url,
                        )
                    )
                    return
                # Recurse into sub-keys looking for nested documents
                for sub_key, sub_val in value.items():
                    if isinstance(sub_val, (dict, list)):
                        _extract_from_value(sub_val, category or sub_key.lower())

        # Check well-known keys first
        known_keys = [
            "Documents",
            "DocumentList",
            "OrderDocuments",
            "PurchaseDocuments",
            "RegistrationDocuments",
            "InsuranceDocuments",
        ]
        for key in known_keys:
            if key in portal_data:
                _extract_from_value(portal_data[key], category=key.replace("Documents", "").lower())

        # Scan remaining keys for anything containing PDF URLs
        for key, value in portal_data.items():
            if key in known_keys or key.startswith("__"):
                continue
            _scan_for_pdf_urls(value, key.lower(), seen_urls, docs)

        return docs

    def download_document(self, doc: PortalDocument, output_dir: Path) -> Path:
        """Download a document from the portal URL to local storage.

        Returns path to the downloaded file.
        """
        import re

        output_dir.mkdir(parents=True, exist_ok=True)

        # Derive filename: prefer doc.name, fallback to URL basename
        raw_name = doc.name or doc.url.split("/")[-1].split("?")[0] or f"document-{doc.document_id}"
        # Sanitize filename
        safe_name = re.sub(r"[^\w\s.\-]", "_", raw_name).strip()
        if not safe_name.lower().endswith(".pdf") and ".pdf" in doc.url.lower():
            safe_name += ".pdf"

        out_path = output_dir / safe_name

        resp = self._client.get(doc.url, follow_redirects=True)
        if resp.status_code != 200:
            raise ApiError(resp.status_code, f"Failed to download {doc.name}: {resp.text[:200]}")

        out_path.write_bytes(resp.content)
        return out_path

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

    def _load_delivery_cache_for_order(
        self,
        reservation_number: str,
        vin: str = "",
        *,
        allow_stale: bool = False,
    ) -> dict | None:
        cached = self._load_delivery_cache()
        if not cached:
            return None
        try:
            fetched_at = cached.get("fetched_at", "")
            if fetched_at:
                fetched = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
                age_hours = (datetime.now(UTC) - fetched.astimezone(UTC)).total_seconds() / 3600
                cached["_cache_age_hours"] = age_hours
                if age_hours > DELIVERY_CACHE_MAX_AGE_HOURS:
                    cached["_stale"] = True
                    if not allow_stale:
                        return None
        except Exception:
            logger.warning("Failed to validate delivery cache timestamp", exc_info=True)
            return None

        order = cached.get("order", {}) if isinstance(cached, dict) else {}
        cached_rn = str(order.get("referenceNumber") or "").strip()
        cached_vin = str(order.get("vin") or "").strip()
        if reservation_number and cached_rn and cached_rn != reservation_number:
            return None
        if vin and cached_vin and cached_vin != vin:
            return None
        return cached

    def _save_delivery_cache(self, data: dict) -> None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        DELIVERY_CACHE_FILE.write_text(json.dumps(data, default=str, indent=2))

    def _build_delivery_data(
        self, reservation_number: str, vin: str, raw_order: dict[str, Any]
    ) -> dict[str, Any]:
        delivery_data = dict(raw_order.get("delivery", {}) or {})

        portal_cached = self._load_portal_cache_for_order(reservation_number, vin)
        if portal_cached:
            delivery_data = self._merge_delivery_from_portal(delivery_data, portal_cached)

        cached = self._load_delivery_cache_for_order(
            reservation_number=reservation_number,
            vin=vin,
            allow_stale=not bool(delivery_data),
        )
        if cached:
            dd = cached.get("delivery_details", {})
            timing = dd.get("deliveryTiming", {})
            delivery_data = {
                **delivery_data,
                "appointment": timing.get("appointment", delivery_data.get("appointment", "")),
                "appointmentDateUtc": dd.get(
                    "deliveryAppointmentDateUtc", delivery_data.get("appointmentDateUtc", "")
                ),
                "location": timing.get("pickupLocationTitle", delivery_data.get("location", "")),
                "address": timing.get(
                    "formattedAddressSingleLine", delivery_data.get("address", "")
                ),
                "cachedAt": cached.get("fetched_at", ""),
                "cacheStale": bool(cached.get("_stale")),
                "cacheAgeHours": round(float(cached.get("_cache_age_hours", 0)), 2)
                if cached.get("_cache_age_hours") is not None
                else None,
            }
        return delivery_data

    def _load_portal_cache_for_order(
        self, reservation_number: str, vin: str = ""
    ) -> dict[str, Any] | None:
        if not PORTAL_CACHE_FILE.exists():
            return None
        try:
            cached = json.loads(PORTAL_CACHE_FILE.read_text())
        except Exception:
            return None
        data = cached.get("data") if isinstance(cached, dict) else None
        if not isinstance(data, dict) or not data:
            return None
        order = data.get("Order") or data.get("order") or data.get("Vehicle") or {}
        if isinstance(order, dict):
            cached_rn = str(order.get("referenceNumber") or order.get("rn") or "").strip()
            cached_vin = str(order.get("vin") or "").strip()
            if reservation_number and cached_rn and cached_rn != reservation_number:
                return None
            if vin and cached_vin and cached_vin != vin:
                return None
        return data

    def _merge_delivery_from_portal(
        self, delivery_data: dict[str, Any], portal_data: dict[str, Any]
    ) -> dict[str, Any]:
        dd = portal_data.get("DeliveryDetails") or portal_data.get("delivery_details") or {}
        timing = dd.get("deliveryTiming", {}) if isinstance(dd, dict) else {}
        if not isinstance(dd, dict):
            return delivery_data
        return {
            **delivery_data,
            "appointment": timing.get("appointment", delivery_data.get("appointment", "")),
            "appointmentDateUtc": dd.get(
                "deliveryAppointmentDateUtc", delivery_data.get("appointmentDateUtc", "")
            ),
            "location": timing.get("pickupLocationTitle", delivery_data.get("location", "")),
            "address": timing.get("formattedAddressSingleLine", delivery_data.get("address", "")),
        }

    def _load_portal_tasks_for_order(self, reservation_number: str) -> list[OrderTask]:
        portal_data = self._load_portal_cache_for_order(reservation_number)
        if not portal_data:
            return []
        for key in ("tasks", "Tasks", "tesla_tasks", "preDeliveryTasks"):
            parsed = self._parse_task_items(portal_data.get(key))
            if parsed:
                return parsed
        app_order = portal_data.get("Order") or portal_data.get("order") or {}
        for key in ("tasks", "Tasks", "tesla_tasks", "preDeliveryTasks"):
            parsed = self._parse_task_items(
                app_order.get(key) if isinstance(app_order, dict) else None
            )
            if parsed:
                return parsed
        return []

    def _extract_tasks_from_order_payload(self, raw_order: dict[str, Any]) -> list[OrderTask]:
        details = raw_order.get("_details", raw_order.get("details", {}))
        if not isinstance(details, dict):
            return []
        return self._parse_task_items(details.get("tasks"))

    def _parse_task_items(self, raw_tasks: Any) -> list[OrderTask]:
        if not raw_tasks:
            return []
        items: list[dict[str, Any]] = []
        if isinstance(raw_tasks, list):
            items = [item for item in raw_tasks if isinstance(item, dict)]
        elif isinstance(raw_tasks, dict):
            for key, value in raw_tasks.items():
                if isinstance(value, dict):
                    item = dict(value)
                    item.setdefault("taskType", key)
                    item.setdefault("taskName", key)
                    if "completed" not in item:
                        item["completed"] = bool(item.get("complete"))
                    if "active" not in item:
                        item["active"] = bool(item.get("enabled", True))
                    if "taskStatus" not in item:
                        if item.get("completed"):
                            item["taskStatus"] = "COMPLETE"
                        elif item.get("active"):
                            item["taskStatus"] = "PENDING"
                        else:
                            item["taskStatus"] = "DISABLED"
                    items.append(item)
        parsed = []
        for item in items:
            parsed.append(
                OrderTask(
                    task_type=item.get("taskType", item.get("type", "")),
                    task_status=item.get("taskStatus", item.get("status", "")),
                    task_name=item.get("taskName", item.get("name", item.get("taskType", ""))),
                    completed=item.get("completed", item.get("complete", False)),
                    active=item.get("active", item.get("enabled", False)),
                    details=item,
                )
            )
        return [task for task in parsed if task.task_type]


def generate_summary(
    status: OrderStatus,
    runt: dict[str, Any] | None = None,
    details: dict[str, Any] | None = None,
) -> str:
    """Generate a human-readable order summary from structured data.

    Template-based (no LLM) — builds sentences from order phase signals.
    Optionally enriched with delivery/financing details from raw order data.
    """
    parts: list[str] = []
    model_name = status.model or "Tesla"
    raw = details or status.raw or {}

    # VIN status
    if status.vin:
        parts.append(f"Your {model_name} already has a VIN.")
    else:
        parts.append(f"Your {model_name} does not have a VIN assigned yet.")

    # Financing info (from _details or raw)
    _details = raw.get("_details", raw.get("details", {}))
    financing = _details.get("financing", raw.get("financing", {}))
    if isinstance(financing, dict) and financing.get("financingPartnerName"):
        partner = financing["financingPartnerName"]
        amount = financing.get("financingAmount")
        if amount and isinstance(amount, (int, float)):
            amount_str = f"$ {amount:,.0f}".replace(",", ".")
            parts.append(f"Financed by {partner} for {amount_str}.")
        else:
            parts.append(f"Financed by {partner}.")
        # Amount due
        due = financing.get("amountDueCustomer", financing.get("amountDue"))
        if due and isinstance(due, (int, float)):
            due_str = f"$ {abs(due):,.0f}".replace(",", ".")
            parts.append(f"There is an amount due of {'-' if due < 0 else ''}{due_str}.")

    # Delivery appointment (from _details.tasks.scheduling or delivery data)
    tasks = _details.get("tasks", {})
    scheduling = tasks.get("scheduling", {}) if isinstance(tasks, dict) else {}
    if isinstance(scheduling, dict) and scheduling.get("deliveryAddressTitle"):
        addr = scheduling["deliveryAddressTitle"]
        appt_date = scheduling.get("cardMessageTitle", "")
        if appt_date and "at" in str(appt_date).lower():
            parts.append(f"Delivery: {appt_date} at {addr}.")
        elif scheduling.get("appointmentStatusName") == "Scheduled":
            parts.append(f"Delivery scheduled at {addr}.")
    elif status.order_status and "deliver" in status.order_status.lower():
        if status.estimated_delivery:
            parts.append(f"Delivery scheduled for {status.estimated_delivery}.")
        else:
            parts.append("Delivery has been scheduled.")
    elif status.delivery_window_start and status.delivery_window_end:
        parts.append(
            f"Estimated delivery window: {status.delivery_window_start} — {status.delivery_window_end}."
        )
    elif status.estimated_delivery:
        parts.append(f"Estimated delivery: {status.estimated_delivery}.")

    # Registration / plate (Colombia RUNT)
    if runt:
        placa = runt.get("placa", "")
        if placa:
            parts.append(f"License plate: {placa}.")
        else:
            parts.append("Your vehicle does not have a license plate yet.")

    # Next action hints based on tasks
    if isinstance(tasks, dict):
        pending = [
            t_id
            for t_id, t_data in tasks.items()
            if isinstance(t_data, dict) and not t_data.get("complete") and t_data.get("enabled")
        ]
        if pending:
            # Map task IDs to friendly names
            task_names = {
                "finalPayment": "complete final payment",
                "FinalPayment": "complete final payment",
                "deliveryAcceptance": "accept delivery",
                "DeliveryAcceptance": "accept delivery",
                "registration": "complete registration",
                "Registration": "complete registration",
                "agreements": "sign agreements",
                "Agreements": "sign agreements",
                "financing": "confirm financing",
                "Financing": "confirm financing",
                "scheduling": "schedule delivery",
                "Scheduling": "schedule delivery",
            }
            next_task = pending[0]
            friendly = task_names.get(next_task, next_task.replace("_", " ").lower())
            parts.append(f"Next step: {friendly}.")
    else:
        # Fallback hints from order status
        status_lower = (status.order_status or "").lower()
        if "reserved" in status_lower and not status.vin:
            parts.append("Next: wait for VIN assignment.")
        elif status.vin and "reserved" in status_lower:
            parts.append("Next: wait for logistics and delivery scheduling.")

    return " ".join(parts)


def format_share_text(
    status: OrderStatus,
    summary: str,
    include_vin: bool = False,
) -> str:
    """Format order status as shareable text."""
    lines: list[str] = []

    # Header
    model = status.model or "Tesla"
    trim = f" {status.trim}" if status.trim else ""
    order_st = status.order_status or "Unknown"
    lines.append(f"\U0001f697 Tesla {model}{trim} — {order_st}")

    # Summary
    lines.append(f"\U0001f4cb {summary}")

    # Config
    if status.exterior_color or status.interior_color:
        ext = status.exterior_color or "?"
        int_ = status.interior_color or "?"
        lines.append(f"\U0001f3a8 {ext} / {int_}")
    if status.wheels:
        lines.append(f"\U0001f6de {status.wheels}")

    # Optional VIN
    if include_vin and status.vin:
        lines.append(f"\U0001f511 VIN: {status.vin}")

    return "\n".join(lines)


def _scan_for_pdf_urls(
    value: object,
    category: str,
    seen_urls: set[str],
    docs: list[PortalDocument],
) -> None:
    """Recursively scan a portal data value for PDF-bearing document objects."""
    if isinstance(value, list):
        for item in value:
            _scan_for_pdf_urls(item, category, seen_urls, docs)
    elif isinstance(value, dict):
        url = value.get("url", value.get("URL", value.get("downloadUrl", "")))
        if url and isinstance(url, str) and ".pdf" in url.lower() and url not in seen_urls:
            seen_urls.add(url)
            name = value.get(
                "name",
                value.get("title", value.get("documentName", value.get("fileName", ""))),
            )
            doc_type = value.get("type", value.get("documentType", value.get("category", category)))
            doc_id = value.get("id", value.get("documentId", value.get("document_id", "")))
            docs.append(
                PortalDocument(
                    document_id=str(doc_id),
                    name=str(name or url.split("/")[-1].split("?")[0]),
                    category=str(doc_type or category),
                    url=url,
                )
            )
        else:
            for sub_val in value.values():
                if isinstance(sub_val, (dict, list)):
                    _scan_for_pdf_urls(sub_val, category, seen_urls, docs)
