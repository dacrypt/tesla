"""generate_summary next-step hints (the status fallback used to be unreachable)."""

from __future__ import annotations

from tesla_cli.core.backends.order import generate_summary
from tesla_cli.core.models.order import OrderStatus


def _status(**kw) -> OrderStatus:
    return OrderStatus(reservation_number="RN123456789", model="Model Y", **kw)


def test_reserved_without_vin_hints_wait_for_vin():
    assert "Next: wait for VIN assignment." in generate_summary(_status(order_status="RESERVED"))


def test_reserved_with_vin_hints_logistics():
    out = generate_summary(_status(order_status="RESERVED", vin="7SAYGDEE4RF000001"))
    assert "Next: wait for logistics and delivery scheduling." in out


def test_pending_task_wins_over_status_hint():
    details = {
        "_details": {
            "tasks": {
                "finalPayment": {"enabled": True, "complete": False},
                "registration": {"enabled": True, "complete": True},
            }
        }
    }
    out = generate_summary(_status(order_status="RESERVED"), details=details)
    assert "Next step: complete final payment." in out
    assert "wait for VIN" not in out


def test_unknown_task_id_is_humanised():
    details = {"_details": {"tasks": {"trade_in": {"enabled": True, "complete": False}}}}
    assert "Next step: trade in." in generate_summary(_status(), details=details)
