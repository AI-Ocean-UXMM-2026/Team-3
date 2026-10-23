from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.lifecycle import OrderStatus
from app.schemas.management import EditableOrderFields
from app.schemas.orders import Confidence


class BuyerCardResult(BaseModel):
    order_reference: UUID
    shop_display_name: str | None
    delivery_status: OrderStatus
    state: Literal["LOCKED", "VIEW_ONLY", "VERIFICATION_REQUIRED"]
    expires_at: datetime


class BuyerAuthorizationResult(BaseModel):
    access_token: str
    token_type: Literal["Bearer"]
    expires_at: datetime


class BuyerOtpChallengeResult(BaseModel):
    challenge_id: UUID
    destination_masked: str
    expires_at: datetime
    resend_after: datetime
    mode: Literal["DEMO", "SMS"]


class BuyerLookup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tracking_id: str = Field(min_length=1, max_length=128)
    phone: str = Field(min_length=5, max_length=32)


class BuyerLookupResult(BaseModel):
    token: str
    order_reference: UUID
    shop_display_name: str | None
    delivery_status: OrderStatus
    access_token: str
    token_type: Literal["Bearer"]
    expires_at: datetime


class LinkResult(BaseModel):
    link_id: UUID
    confirmation_url: str
    absolute_url: str | None
    expires_at: datetime
    buyer_handle: str | None = None


class BuyerActionResult(BaseModel):
    request_id: UUID
    decision: Literal["APPLIED", "REVIEW_REQUIRED"]
    reason_codes: list[str]
    order_status: OrderStatus
    confidence_level: Confidence
    submitted_at: datetime
    confirmed_at: datetime | None
    resolution: Literal["APPROVE", "REJECT"] | None
    editing_policy: dict = Field(default_factory=dict)


class BuyerDetailsResult(BaseModel):
    order_reference: UUID
    status: OrderStatus
    township: str | None
    street: str | None
    landmark: str | None
    building_floor_unit: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    delivery_time_window: str | None
    delivery_instructions: str | None
    proposed_latitude: Decimal | None = None
    proposed_longitude: Decimal | None = None
    initial_pin_requires_review: bool
    policy: dict


class RevocationResult(BaseModel):
    revoked: bool


class LocationReferenceResult(BaseModel):
    reference_set: bool
    independent_township_boundaries_available: bool


class BuyerReviewResult(BaseModel):
    request_id: UUID
    resolution: Literal["APPROVE", "REJECT"]
    order_version: int


class BuyerHistoryItem(BaseModel):
    id: UUID
    request_id: UUID
    kind: Literal["LOCATION", "RESPONSE"]
    decision: Literal["APPLIED", "REVIEW_REQUIRED"]
    reason_codes: list[str]
    previous_values: dict
    submitted_values: dict
    resolution: Literal["APPROVE", "REJECT"] | None
    resolution_reason: str | None
    resolved_by: UUID | None
    resolved_at: datetime | None
    created_at: datetime


class BuyerHistoryPage(BaseModel):
    items: list[BuyerHistoryItem]
    total: int
    page: int
    page_size: int


class VerifyBuyer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(pattern=r"^[0-9]{6}$", strict=True)


class BuyerLocation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    latitude: Decimal = Field(ge=-90, le=90, decimal_places=7, allow_inf_nan=False)
    longitude: Decimal = Field(ge=-180, le=180, decimal_places=7, allow_inf_nan=False)
    initial_pin_acknowledged: bool = Field(default=False, strict=True)

    @field_validator("latitude", "longitude", mode="before")
    @classmethod
    def no_boolean(cls, value):
        if isinstance(value, bool):
            raise ValueError("Coordinates must be decimal numbers")
        return value


class DeliveryWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def valid_window(self):
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("Time windows require explicit UTC offsets")
        duration = (self.end - self.start).total_seconds()
        if duration < 1800 or duration > 28800:
            raise ValueError("Time window must span between 30 minutes and 8 hours")
        return self


class BuyerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    action: Literal["AVAILABLE", "RESCHEDULE", "LEAVE_WITH_SECURITY", "INSTRUCTIONS"]
    time_window: DeliveryWindow | None = None
    instructions: str | None = Field(default=None, min_length=1, max_length=2000, strict=True)

    @field_validator("instructions")
    @classmethod
    def nonblank(cls, value):
        if value is not None and (not value.strip() or "\x00" in value):
            raise ValueError("Instructions must be nonblank")
        return value.strip() if value else value

    @model_validator(mode="after")
    def required_fields(self):
        if self.action == "RESCHEDULE" and self.time_window is None:
            raise ValueError("Rescheduling requires a time window")
        if self.action == "INSTRUCTIONS" and not self.instructions:
            raise ValueError("Instructions action requires instructions")
        return self


class BuyerRequestSubmission(BaseModel):
    """One atomic buyer save containing location and requested delivery details."""

    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    latitude: Decimal = Field(ge=-90, le=90, decimal_places=7, allow_inf_nan=False)
    longitude: Decimal = Field(ge=-180, le=180, decimal_places=7, allow_inf_nan=False)
    initial_pin_acknowledged: bool = Field(default=False, strict=True)
    action: Literal["AVAILABLE", "RESCHEDULE", "LEAVE_WITH_SECURITY", "INSTRUCTIONS"]
    time_window: DeliveryWindow
    instructions: str | None = Field(default=None, min_length=1, max_length=2000, strict=True)

    @field_validator("latitude", "longitude", mode="before")
    @classmethod
    def no_boolean_coordinates(cls, value):
        if isinstance(value, bool):
            raise ValueError("Coordinates must be decimal numbers")
        return value

    @field_validator("instructions")
    @classmethod
    def nonblank_instruction(cls, value):
        if value is not None and (not value.strip() or "\x00" in value):
            raise ValueError("Instructions must be nonblank")
        return value.strip() if value else value


class SetLocationReference(BuyerLocation):
    # request_id identifies an attestation, not a buyer idempotency key.
    township: str = Field(min_length=1, max_length=128)
    source_reference: str = Field(min_length=1, max_length=500, strict=True)
    independently_checked: Literal[True]

    @field_validator("township")
    @classmethod
    def township_alias(cls, value):
        return EditableOrderFields.known_township(value)

    @field_validator("source_reference")
    @classmethod
    def source_nonblank(cls, value):
        if not value.strip() or "\x00" in value:
            raise ValueError("Reference source is required")
        return value.strip()


class ReviewBuyerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1, strict=True)
    decision: Literal["APPROVE", "REJECT"]
    reason: str = Field(min_length=5, max_length=500, strict=True)

    @field_validator("reason")
    @classmethod
    def nonblank_reason(cls, value):
        if len(value.strip()) < 5 or "\x00" in value:
            raise ValueError("Review reason needs at least five nonblank characters")
        return value.strip()
