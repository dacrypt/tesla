"""Data models for Tesla order tracking."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class OrderStatus(BaseModel):
    """Top-level order status from Tesla API."""

    reservation_number: str = ""
    order_status: str = ""
    order_substatus: str = ""
    vin: str = ""
    model: str = ""
    trim: str = ""
    exterior_color: str = ""
    interior_color: str = ""
    wheels: str = ""
    autopilot: str = ""
    has_fsd: bool = False
    order_date: str = ""
    estimated_delivery: str = ""
    delivery_window_start: str = ""
    delivery_window_end: str = ""
    country: str = ""
    state_or_province: str = ""
    mkt_options: str = ""

    # Raw data for anything we don't model
    raw: dict = Field(default_factory=dict)


class OrderTask(BaseModel):
    """A task/step in the order process."""

    task_type: str = ""
    task_status: str = ""
    task_name: str = ""
    completed: bool = False
    active: bool = False
    details: dict = Field(default_factory=dict)


class OrderDetails(BaseModel):
    """Full order details including tasks."""

    status: OrderStatus = Field(default_factory=OrderStatus)
    tasks: list[OrderTask] = Field(default_factory=list)
    vehicle_info: dict = Field(default_factory=dict)
    financing: dict = Field(default_factory=dict)
    trade_in: dict = Field(default_factory=dict)
    registration: dict = Field(default_factory=dict)
    delivery: dict = Field(default_factory=dict)


class OrderChange(BaseModel):
    """Represents a detected change in order status."""

    field: str
    old_value: str = ""
    new_value: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)


class DeliveryAppointment(BaseModel):
    """Current delivery appointment details (from SSR page or API)."""

    appointment_text: str = ""
    date_utc: str = ""
    location_name: str = ""
    address: str = ""
    disclaimer: str = ""
    duration_minutes: int = 0
    raw: dict = Field(default_factory=dict)


