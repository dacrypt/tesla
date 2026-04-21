"""Tests for OrderBackend — mocked HTTP via pytest-httpx, no real API calls."""

from __future__ import annotations

import json
import re
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import jwt
import pytest

from tesla_cli.core.backends.order import (
    ORDERS_URL,
    TASKS_API_BASE,
    OrderBackend,
)
from tesla_cli.core.exceptions import AuthenticationError, OrderNotFoundError
from tesla_cli.core.models.order import (
    DeliveryAppointment,
    OrderChange,
    OrderStatus,
    OrderTask,
)

# ── Helpers ────────────────────────────────────────────────────────────────────

MOCK_RN = "RN126460939"
MOCK_VIN = "7SAYGDEE4RF000001"


def _fresh_iso(hours_ago: int = 1) -> str:
    return (datetime.now(UTC) - timedelta(hours=hours_ago)).isoformat().replace("+00:00", "Z")


def _make_jwt(exp_offset: int = 3600) -> str:
    """Return a JWT-like token that decodes without verification."""
    return jwt.encode(
        {"sub": "user", "exp": int(time.time()) + exp_offset},
        key="secret",
        algorithm="HS256",
    )


def _mock_order_raw() -> dict:
    return {
        "referenceNumber": MOCK_RN,
        "orderStatus": "CONFIRMED",
        "orderSubstatus": "PAYMENT_COMPLETE",
        "vin": MOCK_VIN,
        "orderDate": "2025-01-15",
        "delivery": {
            "estimatedDeliveryDate": "2025-06-01",
            "windowStart": "2025-05-28",
            "windowEnd": "2025-06-05",
        },
        "vehicleInfo": {
            "vehicleConfig": {
                "model": "modely",
                "exteriorColor": "STEALTH",
                "interiorColor": "WHITE",
                "wheels": "GEMINI",
                "autopilot": "AUTOPILOT",
                "fsd": False,
            }
        },
        "country": "US",
        "stateProvince": "CA",
    }


@pytest.fixture
def backend(tmp_path, monkeypatch):
    """OrderBackend with state dirs redirected to tmp_path."""
    monkeypatch.setattr("tesla_cli.core.backends.order.STATE_DIR", tmp_path)
    monkeypatch.setattr(
        "tesla_cli.core.backends.order.ORDER_STATE_FILE", tmp_path / "last_order.json"
    )
    monkeypatch.setattr(
        "tesla_cli.core.backends.order.DELIVERY_CACHE_FILE", tmp_path / "delivery.json"
    )
    monkeypatch.setattr(
        "tesla_cli.core.backends.order.PORTAL_CACHE_FILE", tmp_path / "tesla.portal.json"
    )
    return OrderBackend()


@pytest.fixture
def valid_token():
    return _make_jwt(exp_offset=3600)


@pytest.fixture
def patched_tokens(valid_token):
    """Patch get_token/set_token so no keyring access occurs."""
    with (
        patch("tesla_cli.core.backends.order.tokens.get_token") as mock_get,
        patch("tesla_cli.core.backends.order.tokens.set_token"),
    ):
        mock_get.side_effect = lambda key: valid_token if "access" in key else "refresh-tok"
        yield mock_get


# ── get_orders ─────────────────────────────────────────────────────────────────


def test_get_orders_success(httpx_mock, backend, patched_tokens):
    orders = [_mock_order_raw()]
    httpx_mock.add_response(url=ORDERS_URL, json={"response": orders})

    result = backend.get_orders()

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["referenceNumber"] == MOCK_RN


def test_get_orders_success_list_response(httpx_mock, backend, patched_tokens):
    """API returning a bare list (not wrapped in response key) is handled."""
    orders = [_mock_order_raw()]
    httpx_mock.add_response(url=ORDERS_URL, json=orders)

    result = backend.get_orders()
    assert len(result) == 1


def test_get_orders_auth_error(httpx_mock, backend, patched_tokens):
    httpx_mock.add_response(url=ORDERS_URL, status_code=401)

    with pytest.raises(AuthenticationError):
        backend.get_orders()


def test_get_orders_api_error(httpx_mock, backend, patched_tokens):
    from tesla_cli.core.exceptions import ApiError

    httpx_mock.add_response(url=ORDERS_URL, status_code=500, text="Internal Server Error")

    with pytest.raises(ApiError) as exc_info:
        backend.get_orders()
    assert exc_info.value.status_code == 500


# ── get_order_status ───────────────────────────────────────────────────────────


def test_get_order_status_found(httpx_mock, backend, patched_tokens):
    httpx_mock.add_response(url=ORDERS_URL, json={"response": [_mock_order_raw()]})

    status = backend.get_order_status(MOCK_RN)

    assert isinstance(status, OrderStatus)
    assert status.reservation_number == MOCK_RN
    assert status.vin == MOCK_VIN
    assert status.order_status == "CONFIRMED"
    assert status.model == "modely"
    assert status.exterior_color == "STEALTH"


def test_get_order_status_not_found(httpx_mock, backend, patched_tokens):
    httpx_mock.add_response(url=ORDERS_URL, json={"response": [_mock_order_raw()]})

    with pytest.raises(OrderNotFoundError):
        backend.get_order_status("RN_NONEXISTENT")


def test_get_order_status_fields(httpx_mock, backend, patched_tokens):
    httpx_mock.add_response(url=ORDERS_URL, json={"response": [_mock_order_raw()]})

    status = backend.get_order_status(MOCK_RN)

    assert status.estimated_delivery == "2025-06-01"
    assert status.delivery_window_start == "2025-05-28"
    assert status.delivery_window_end == "2025-06-05"
    assert status.country == "US"
    assert status.state_or_province == "CA"
    assert status.has_fsd is False


# ── get_order_tasks ────────────────────────────────────────────────────────────


_TASKS_URL_RE = re.compile(re.escape(f"{TASKS_API_BASE}/tasks"))


def test_get_order_tasks(httpx_mock, backend, patched_tokens):
    tasks_data = [
        {
            "taskType": "PAYMENT",
            "taskStatus": "COMPLETE",
            "taskName": "Payment Received",
            "completed": True,
            "active": False,
        },
        {
            "taskType": "DELIVERY",
            "taskStatus": "PENDING",
            "taskName": "Schedule Delivery",
            "completed": False,
            "active": True,
        },
    ]
    httpx_mock.add_response(url=_TASKS_URL_RE, json=tasks_data)

    tasks = backend.get_order_tasks(MOCK_RN)

    assert len(tasks) == 2
    assert all(isinstance(t, OrderTask) for t in tasks)
    assert tasks[0].task_type == "PAYMENT"
    assert tasks[0].completed is True
    assert tasks[1].task_type == "DELIVERY"
    assert tasks[1].active is True


def test_get_order_tasks_empty_on_error(httpx_mock, backend, patched_tokens):
    httpx_mock.add_response(url=_TASKS_URL_RE, status_code=404)

    tasks = backend.get_order_tasks(MOCK_RN)
    assert tasks == []


def test_get_order_tasks_falls_back_to_portal_cache(httpx_mock, backend, patched_tokens, tmp_path):
    httpx_mock.add_response(
        url=_TASKS_URL_RE, status_code=400, json={"message": "Unable to process your request."}
    )
    (tmp_path / "tesla.portal.json").write_text(
        json.dumps(
            {
                "data": {
                    "tasks": {
                        "deliveryAcceptance": {"complete": False, "enabled": True},
                        "finalPayment": {"complete": True, "enabled": False},
                    }
                }
            }
        )
    )

    tasks = backend.get_order_tasks(MOCK_RN)

    assert len(tasks) == 2
    assert {t.task_type for t in tasks} == {"deliveryAcceptance", "finalPayment"}


def test_get_order_tasks_wrapped_response(httpx_mock, backend, patched_tokens):
    wrapped = {"tasks": [{"taskType": "DOCS", "taskStatus": "PENDING", "completed": False}]}
    httpx_mock.add_response(url=_TASKS_URL_RE, json=wrapped)

    tasks = backend.get_order_tasks(MOCK_RN)
    assert len(tasks) == 1
    assert tasks[0].task_type == "DOCS"


# ── _parse_order_status ────────────────────────────────────────────────────────


def test_parse_order_status_full_format(backend):
    data = _mock_order_raw()
    status = backend._parse_order_status(data)

    assert status.reservation_number == MOCK_RN
    assert status.vin == MOCK_VIN
    assert status.order_status == "CONFIRMED"
    assert status.model == "modely"
    assert status.exterior_color == "STEALTH"
    assert status.interior_color == "WHITE"
    assert status.wheels == "GEMINI"
    assert status.autopilot == "AUTOPILOT"
    assert status.has_fsd is False
    assert status.raw == data


def test_parse_order_status_sparse_format(backend):
    """Handles sparse CO-style responses using alternate field names."""
    data = {
        "rn": "RN999",
        "status": "PLACED",
        "vin": "",
        "modelCode": "y",
        "mktOptions": "MYYY04,PAINT01",
        "createdAt": "2025-01-01",
        "countryCode": "CO",
        "region": "Bogota",
        "delivery": {},
        "vehicle": {},
    }
    status = backend._parse_order_status(data)

    assert status.reservation_number == "RN999"
    assert status.order_status == "PLACED"
    assert status.country == "CO"
    assert status.state_or_province == "Bogota"
    assert status.mkt_options == "MYYY04,PAINT01"


def test_parse_order_status_has_fsd_from_config_string(backend):
    """has_fsd=True when FSD appears in config."""
    data = {
        "referenceNumber": "RN1",
        "orderStatus": "PLACED",
        "vehicleInfo": {
            "vehicleConfig": {
                "model": "modely",
                "FSD_COMPUTER": True,
            }
        },
        "delivery": {},
    }
    status = backend._parse_order_status(data)
    assert status.has_fsd is True


# ── detect_changes ─────────────────────────────────────────────────────────────


def test_detect_changes_new_order(httpx_mock, backend, patched_tokens, tmp_path):
    """No previous state — returns empty list, saves state."""
    # detect_changes calls get_order_status once directly, then get_delivery_appointment
    # which calls get_order_status again (no cache file) — register as reusable.
    httpx_mock.add_response(
        url=ORDERS_URL, json={"response": [_mock_order_raw()]}, is_reusable=True
    )
    httpx_mock.add_response(url=_TASKS_URL_RE, status_code=404, is_optional=True)

    changes = backend.detect_changes(MOCK_RN)

    assert changes == []
    state_file = tmp_path / "last_order.json"
    assert state_file.exists()
    saved = json.loads(state_file.read_text())
    assert saved["reservation_number"] == MOCK_RN


def test_detect_changes_with_diff(httpx_mock, backend, patched_tokens, tmp_path):
    """Changed VIN is detected as an OrderChange."""
    prev = {
        "reservation_number": MOCK_RN,
        "order_status": "CONFIRMED",
        "vin": "OLD_VIN",
        "model": "modely",
        "trim": "",
        "exterior_color": "STEALTH",
        "interior_color": "WHITE",
        "wheels": "GEMINI",
        "autopilot": "AUTOPILOT",
        "has_fsd": False,
        "order_date": "2025-01-15",
        "estimated_delivery": "2025-06-01",
        "delivery_window_start": "2025-05-28",
        "delivery_window_end": "2025-06-05",
        "country": "US",
        "state_or_province": "CA",
        "order_substatus": "PAYMENT_COMPLETE",
        "mkt_options": "",
    }
    state_file = tmp_path / "last_order.json"
    state_file.write_text(json.dumps(prev))

    httpx_mock.add_response(
        url=ORDERS_URL, json={"response": [_mock_order_raw()]}, is_reusable=True
    )
    httpx_mock.add_response(url=_TASKS_URL_RE, status_code=404, is_optional=True)

    changes = backend.detect_changes(MOCK_RN)

    vin_change = next((c for c in changes if c.field == "vin"), None)
    assert vin_change is not None
    assert isinstance(vin_change, OrderChange)
    assert vin_change.old_value == "OLD_VIN"
    assert vin_change.new_value == MOCK_VIN


def test_detect_changes_no_diff(httpx_mock, backend, patched_tokens, tmp_path):
    """Identical state produces no changes."""
    raw = _mock_order_raw()
    httpx_mock.add_response(url=ORDERS_URL, json={"response": [raw]}, is_reusable=True)
    httpx_mock.add_response(url=_TASKS_URL_RE, status_code=404, is_optional=True)
    # First call seeds the state
    backend.detect_changes(MOCK_RN)

    # Second call with same data — responses are reusable, no need to re-register
    changes = backend.detect_changes(MOCK_RN)

    assert changes == []


# ── get_delivery_appointment ───────────────────────────────────────────────────


def test_get_delivery_appointment_from_cache(backend, tmp_path):
    cache = {
        "fetched_at": _fresh_iso(),
        "order": {"referenceNumber": MOCK_RN},
        "delivery_details": {
            "deliveryAppointmentDateUtc": "2025-06-02T14:00:00Z",
            "deliveryTiming": {
                "appointment": "June 2, 2025 at 2:00 PM",
                "pickupLocationTitle": "Tesla Delivery Hub - Downtown",
                "formattedAddressSingleLine": "123 Main St, San Francisco, CA 94105",
                "disclaimer": "Please arrive 10 minutes early.",
                "duration": 60,
            },
        },
    }
    (tmp_path / "delivery.json").write_text(json.dumps(cache))

    appt = backend.get_delivery_appointment(MOCK_RN)

    assert isinstance(appt, DeliveryAppointment)
    assert appt.appointment_text == "June 2, 2025 at 2:00 PM"
    assert appt.date_utc == "2025-06-02T14:00:00Z"
    assert appt.location_name == "Tesla Delivery Hub - Downtown"
    assert appt.address == "123 Main St, San Francisco, CA 94105"
    assert appt.disclaimer == "Please arrive 10 minutes early."
    assert appt.duration_minutes == 60


def test_get_delivery_appointment_ignores_stale_cache(
    httpx_mock, backend, patched_tokens, tmp_path
):
    cache = {
        "fetched_at": "2025-01-01T10:00:00Z",
        "order": {"referenceNumber": MOCK_RN, "vin": MOCK_VIN},
        "delivery_details": {
            "deliveryAppointmentDateUtc": "2025-06-02T14:00:00Z",
            "deliveryTiming": {
                "appointment": "June 2, 2025 at 2:00 PM",
                "pickupLocationTitle": "Tesla Delivery Hub - Downtown",
                "formattedAddressSingleLine": "123 Main St, San Francisco, CA 94105",
            },
        },
    }
    (tmp_path / "delivery.json").write_text(json.dumps(cache))
    httpx_mock.add_response(url=ORDERS_URL, json={"response": [_mock_order_raw()]})

    appt = backend.get_delivery_appointment(MOCK_RN)

    assert isinstance(appt, DeliveryAppointment)
    assert appt.raw.get("source") == "owner-api-fallback"


def test_get_delivery_appointment_no_cache_fallback_api(
    httpx_mock, backend, patched_tokens, tmp_path
):
    """With no cache, falls back to owner-api estimated delivery date."""
    # No delivery.json in tmp_path
    httpx_mock.add_response(url=ORDERS_URL, json={"response": [_mock_order_raw()]})

    appt = backend.get_delivery_appointment(MOCK_RN)

    assert isinstance(appt, DeliveryAppointment)
    assert "2025-06-01" in appt.appointment_text or appt.date_utc == "2025-06-01"


def test_get_delivery_appointment_no_cache_no_api(backend, tmp_path):
    """With no cache and no tokens, returns empty DeliveryAppointment gracefully."""
    with patch("tesla_cli.core.backends.order.tokens.get_token", return_value=None):
        appt = backend.get_delivery_appointment(MOCK_RN)

    assert isinstance(appt, DeliveryAppointment)
    assert appt.raw.get("source") == "no-data"


# ── import_delivery_data ───────────────────────────────────────────────────────


def test_get_order_details_uses_stale_delivery_cache_when_no_live_delivery(
    httpx_mock, backend, patched_tokens, tmp_path
):
    raw = _mock_order_raw()
    raw["delivery"] = {}
    httpx_mock.add_response(url=ORDERS_URL, json={"response": [raw]})
    httpx_mock.add_response(
        url=_TASKS_URL_RE, status_code=400, json={"message": "Unable to process your request."}
    )
    (tmp_path / "delivery.json").write_text(
        json.dumps(
            {
                "fetched_at": "2025-01-01T10:00:00Z",
                "order": {"referenceNumber": MOCK_RN, "vin": MOCK_VIN},
                "delivery_details": {
                    "deliveryAppointmentDateUtc": "2025-06-02T14:00:00Z",
                    "deliveryTiming": {
                        "appointment": "June 2, 2025 at 2:00 PM",
                        "pickupLocationTitle": "Tesla Delivery Hub - Downtown",
                        "formattedAddressSingleLine": "123 Main St, San Francisco, CA 94105",
                    },
                },
            }
        )
    )

    details = backend.get_order_details(MOCK_RN)

    assert details.delivery["appointmentDateUtc"] == "2025-06-02T14:00:00Z"
    assert details.delivery["cacheStale"] is True
    assert details.delivery["location"] == "Tesla Delivery Hub - Downtown"


def test_import_delivery_data_first_import(backend, tmp_path):
    """First import: no previous cache, no changes detected."""
    delivery_file = tmp_path / "scraped.json"
    data = {
        "order": {"referenceNumber": MOCK_RN},
        "delivery_details": {
            "deliveryAppointmentDateUtc": "2025-06-02T14:00:00Z",
            "deliveryTiming": {
                "appointment": "June 2, 2025 at 2:00 PM",
                "pickupLocationTitle": "Tesla Hub",
                "formattedAddressSingleLine": "123 Main St",
            },
        },
        "fetched_at": _fresh_iso(),
    }
    delivery_file.write_text(json.dumps(data))

    appt, changes = backend.import_delivery_data(delivery_file)

    assert isinstance(appt, DeliveryAppointment)
    assert appt.appointment_text == "June 2, 2025 at 2:00 PM"
    assert changes == []
    assert (tmp_path / "delivery.json").exists()


def test_import_delivery_data_detects_changes(backend, tmp_path):
    """Second import with different date produces an OrderChange."""
    # Seed previous cache
    prev_cache = {
        "order": {"referenceNumber": MOCK_RN},
        "delivery_details": {
            "deliveryAppointmentDateUtc": "2025-05-15T14:00:00Z",
            "deliveryTiming": {
                "appointment": "May 15, 2025 at 2:00 PM",
                "pickupLocationTitle": "Tesla Hub",
                "formattedAddressSingleLine": "123 Main St",
            },
        },
    }
    (tmp_path / "delivery.json").write_text(json.dumps(prev_cache))

    new_file = tmp_path / "scraped_new.json"
    new_data = {
        "order": {"referenceNumber": MOCK_RN},
        "delivery_details": {
            "deliveryAppointmentDateUtc": "2025-06-02T14:00:00Z",
            "deliveryTiming": {
                "appointment": "June 2, 2025 at 2:00 PM",
                "pickupLocationTitle": "Tesla Hub",
                "formattedAddressSingleLine": "123 Main St",
            },
        },
    }
    new_file.write_text(json.dumps(new_data))

    appt, changes = backend.import_delivery_data(new_file)

    date_change = next((c for c in changes if c.field == "delivery_date"), None)
    assert date_change is not None
    assert date_change.old_value == "2025-05-15T14:00:00Z"
    assert date_change.new_value == "2025-06-02T14:00:00Z"

    appt_change = next((c for c in changes if c.field == "delivery_appointment"), None)
    assert appt_change is not None
    assert appt_change.new_value == "June 2, 2025 at 2:00 PM"


def test_import_delivery_data_saves_cache(backend, tmp_path):
    delivery_file = tmp_path / "scraped.json"
    data = {
        "order": {"referenceNumber": MOCK_RN},
        "delivery_details": {
            "deliveryAppointmentDateUtc": "2025-07-01T09:00:00Z",
            "deliveryTiming": {"appointment": "July 1", "pickupLocationTitle": "Hub"},
        },
    }
    delivery_file.write_text(json.dumps(data))

    backend.import_delivery_data(delivery_file)

    saved = json.loads((tmp_path / "delivery.json").read_text())
    assert saved["delivery_details"]["deliveryAppointmentDateUtc"] == "2025-07-01T09:00:00Z"


# ── Token refresh path ─────────────────────────────────────────────────────────


def test_expired_token_triggers_refresh(httpx_mock, backend, tmp_path):
    """Expired access token causes refresh_access_token to be called."""
    expired_token = _make_jwt(exp_offset=-100)  # already expired
    new_token = _make_jwt(exp_offset=3600)

    with (
        patch(
            "tesla_cli.core.backends.order.tokens.get_token",
            side_effect=lambda key: expired_token if "access" in key else "refresh-tok",
        ),
        patch("tesla_cli.core.backends.order.tokens.set_token"),
        patch(
            "tesla_cli.core.backends.order.refresh_access_token",
            return_value={"access_token": new_token},
        ) as mock_refresh,
    ):
        httpx_mock.add_response(url=ORDERS_URL, json={"response": [_mock_order_raw()]})
        backend.get_orders()

    mock_refresh.assert_called_once_with("refresh-tok")


def test_no_refresh_token_raises_auth_error(backend, tmp_path):
    """Missing refresh token raises AuthenticationError immediately."""
    with (
        patch(
            "tesla_cli.core.backends.order.tokens.get_token",
            return_value=None,
        ),
        pytest.raises(AuthenticationError, match="Not authenticated"),
    ):
        backend.get_orders()
