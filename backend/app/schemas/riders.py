import re
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.lifecycle import OrderStatus
from app.schemas.management import EditableOrderFields
from app.schemas.orders import Confidence

OperationalStatus = Literal["AVAILABLE", "ON_BREAK", "OFFLINE"]
FailureReason = Literal[
    "CUSTOMER_UNAVAILABLE",
    "ADDRESS_NOT_FOUND",
    "CUSTOMER_REFUSED",
    "ACCESS_BLOCKED",
    "COD_NOT_COLLECTED",
    "OTHER",
]


class RiderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200, strict=True)
    email: str | None = Field(default=None, min_length=3, max_length=254, strict=True)
    contact_phone: str | None = Field(default=None, min_length=1, max_length=40, strict=True)
    operational_status: OperationalStatus = "OFFLINE"

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value):
        if not value.strip() or "\x00" in value:
            raise ValueError("Name cannot be blank")
        return value.strip()

    @field_validator("email")
    @classmethod
    def email_format(cls, value):
        if value is not None:
            value = value.strip().lower()
            if (
                "\x00" in value
                or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value)
                or value.endswith("@riders.invalid")
            ):
                raise ValueError("Provide a valid contact email, or omit it")
        return value

    @field_validator("contact_phone")
    @classmethod
    def phone(cls, value):
        return EditableOrderFields.valid_mobile(value)


class RiderPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1, strict=True)
    operational_status: OperationalStatus


class RiderResponse(BaseModel):
    id: UUID
    name: str
    email: str | None
    contact_phone: str | None
    operational_status: OperationalStatus
    version: int
    created_at: datetime
    updated_at: datetime


class RiderPage(BaseModel):
    items: list[RiderResponse]
    total: int
    page: int
    page_size: int


class AssignOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1, strict=True)
    rider_id: UUID
    route_id: UUID | None = None
    stop_sequence: int | None = Field(default=None, ge=1, le=10000, strict=True)


class UnassignOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1, strict=True)


class SequencePatch(UnassignOrder):
    stop_sequence: int | None = Field(ge=1, le=10000, strict=True)


class DeliveryAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1, strict=True)
    request_id: UUID
    action: Literal["START", "DELIVERED", "FAILED", "ACCEPT", "DECLINE"]
    assignment_id: UUID | None = None
    offer_version: int | None = Field(default=None, ge=1, strict=True)
    cod_collected: bool | None = Field(default=None, strict=True)
    actual_amount: int | None = Field(default=None, ge=0, le=1000000000, strict=True)
    difference_reason: str | None = Field(default=None, min_length=1, max_length=500)
    failure_reason: FailureReason | None = None
    failure_note: str | None = Field(default=None, min_length=1, max_length=500, strict=True)

    @model_validator(mode="after")
    def action_fields(self):
        if self.action in {"ACCEPT", "DECLINE"} and (
            self.assignment_id is None or self.offer_version is None
        ):
            raise ValueError("Offer response requires assignment_id and offer_version")
        if self.action == "FAILED":
            if not self.failure_reason:
                raise ValueError("Failed delivery requires a reason code")
        elif self.failure_reason is not None or self.failure_note is not None:
            raise ValueError("Failure details are only permitted for FAILED")
        if self.action != "DELIVERED" and self.cod_collected is not None:
            raise ValueError("COD collection can only be recorded with DELIVERED")
        if self.action != "DELIVERED" and (
            self.actual_amount is not None or self.difference_reason is not None
        ):
            raise ValueError("Actual cash can only be recorded with DELIVERED")
        if self.failure_note is not None:
            if not self.failure_note.strip() or "\x00" in self.failure_note:
                raise ValueError("Failure note must be nonblank")
            self.failure_note = self.failure_note.strip()
        return self


class AssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    order_id: UUID
    rider_id: UUID
    dispatcher_id: UUID
    status: Literal["ACTIVE", "UNASSIGNED", "COMPLETED", "FAILED", "CANCELLED"]
    response_status: Literal["PENDING", "ACCEPTED", "DECLINED"] = "ACCEPTED"
    offer_version: int = 1
    allocation_cycle: int | None = None
    responded_at: datetime | None = None
    stop_sequence: int | None
    failure_reason: str | None
    failure_note: str | None
    cod_collected: bool | None
    assigned_at: datetime
    updated_at: datetime
    ended_at: datetime | None


class AssignmentResult(BaseModel):
    assignment: AssignmentResponse
    order_status: OrderStatus
    order_version: int


class AssignmentPage(BaseModel):
    items: list[AssignmentResponse]
    total: int
    page: int
    page_size: int


class ActionResult(BaseModel):
    request_id: UUID
    assignment_id: UUID
    order_id: UUID
    rider_id: UUID
    status: OrderStatus
    assignment_status: str
    order_version: int
    cod_collected: bool | None
    failure_reason: FailureReason | None
    updated_at: datetime
    response_status: Literal["PENDING", "ACCEPTED", "DECLINED"] = "ACCEPTED"
    offer_version: int = 1
    allocation_status: str | None = None
    outcome: str | None = None
    replacement_assignment: AssignmentResponse | None = None
    replacement_route: dict | None = None
    reason: str | None = None


class QueueDelivery(BaseModel):
    assignment_id: UUID
    response_status: Literal["PENDING", "ACCEPTED", "DECLINED"] = "ACCEPTED"
    offer_version: int = 1
    allocation_cycle: int | None = None
    allocation_status: str | None = None
    order_id: UUID
    status: OrderStatus
    order_version: int
    stop_sequence: int | None
    customer_name: str | None
    customer_phone: str | None
    township: str | None
    street: str | None
    landmark: str | None
    building_floor_unit: str | None
    delivery_instructions: str | None
    delivery_time_window: str | None
    confirmed_window_start: datetime | None
    cod_amount: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    coordinate_status: Literal["MISSING", "UNCONFIRMED", "BUYER_CONFIRMED"]
    navigation_ready: bool
    navigation_url: str | None
    confidence_level: Confidence
    location_verification: dict
    buyer_confirmation: dict
    updated_at: datetime


class QueueResponse(BaseModel):
    rider_id: UUID
    operational_status: OperationalStatus
    cursor: str
    unchanged: bool
    total: int
    items: list[QueueDelivery]
    generated_at: datetime
