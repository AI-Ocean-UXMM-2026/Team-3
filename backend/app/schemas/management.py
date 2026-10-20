import re
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from app.domain.lifecycle import OrderStatus, UserRole
from app.parsing.normalization import DIGITS
from app.parsing.places import township_dictionary
from app.parsing.rules import extract_phones
from app.schemas.orders import AddressFields, Confidence, ParseRequest


class EditableOrderFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    customer_name: str | None = Field(default=None, min_length=1, max_length=200)
    customer_phone: str | None = Field(default=None, min_length=1, max_length=40)
    township: str | None = Field(default=None, min_length=1, max_length=128)
    street: str | None = Field(default=None, min_length=1, max_length=1000)
    landmark: str | None = Field(default=None, min_length=1, max_length=1000)
    building: str | None = Field(default=None, min_length=1, max_length=500)
    floor: str | None = Field(default=None, min_length=1, max_length=100)
    unit: str | None = Field(default=None, min_length=1, max_length=100)
    latitude: Decimal | None = Field(
        default=None, ge=-90, le=90, decimal_places=7, allow_inf_nan=False
    )
    longitude: Decimal | None = Field(
        default=None, ge=-180, le=180, decimal_places=7, allow_inf_nan=False
    )
    cod_amount: Decimal | None = Field(default=None, ge=0, le=1000000000, decimal_places=0)
    delivery_instructions: str | None = Field(default=None, min_length=1, max_length=2000)
    delivery_time_window: str | None = Field(default=None, min_length=1, max_length=500)

    @field_validator("*", mode="before")
    @classmethod
    def text_types(cls, value, info):
        if info.field_name not in {"latitude", "longitude", "cod_amount", "expected_version"}:
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError("Text fields require a nonblank string or null")
            return value.strip() if isinstance(value, str) else value
        if isinstance(value, bool):
            raise ValueError("Boolean is not a numeric value")
        return value

    @field_validator("cod_amount", mode="before")
    @classmethod
    def whole_mmk(cls, value):
        if value is None:
            return None
        if type(value) is int:
            return Decimal(value)
        if isinstance(value, str) and re.fullmatch(r"[0-9]{1,10}", value):
            return Decimal(value)
        raise ValueError("COD must be a whole MMK integer or digit string, or null")

    @field_validator("customer_phone")
    @classmethod
    def valid_mobile(cls, value):
        if value is not None:
            text = value.translate(DIGITS)
            address, sources = AddressFields(), {}
            extract_phones(text, address, sources)
            if not re.fullmatch(r"[+0-9 \t-]+", text) or not address.phone_number:
                raise ValueError("Customer phone must be one valid Myanmar mobile number")
            return address.phone_number
        return None

    @field_validator("township")
    @classmethod
    def known_township(cls, value):
        if value is None:
            return None
        text = re.sub(r"(?:[ \t]+township|မြို့နယ်)$", "", value, flags=re.I).strip()
        text = " ".join(text.casefold().split())
        matches = {
            place["name"]
            for place in township_dictionary()["townships"]
            if text in {" ".join(alias.casefold().split()) for alias in place["aliases"]}
        }
        if len(matches) != 1:
            raise ValueError("Township must match a single supported Yangon township alias")
        return matches.pop()

    @model_validator(mode="after")
    def paired_coordinates(self):
        provided = self.model_fields_set
        if ("latitude" in provided) != ("longitude" in provided):
            raise ValueError("Supply latitude and longitude together")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Both coordinates must be set, or both null")
        return self


class StructuredOrder(EditableOrderFields):
    @model_validator(mode="after")
    def meaningful_input(self):
        if not any(getattr(self, field) is not None for field in self.model_fields_set):
            raise ValueError("Structured order must contain at least one non-null field")
        return self


class CreateOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")
    merchant_id: UUID
    raw_text: str | None = None
    structured: StructuredOrder | None = None

    @field_validator("raw_text")
    @classmethod
    def validate_raw(cls, value):
        return ParseRequest(raw_text=value).raw_text if value is not None else None

    @model_validator(mode="after")
    def exactly_one_input(self):
        if (self.raw_text is None) == (self.structured is None):
            raise ValueError("Supply exactly one of raw_text or structured")
        return self


class CorrectOrder(EditableOrderFields):
    expected_version: int = Field(ge=1, strict=True)

    @model_validator(mode="after")
    def has_correction(self):
        if not self.model_fields_set - {"expected_version"}:
            raise ValueError("At least one editable field is required")
        return self


class ChangeStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: OrderStatus
    expected_version: int = Field(ge=1, strict=True)
    acknowledge_unverified_location: bool = Field(default=False, strict=True)
    cod_collected: bool | None = Field(default=None, strict=True)

    @model_validator(mode="after")
    def collection_action(self):
        if self.cod_collected is not None and self.status != OrderStatus.DELIVERED:
            raise ValueError("COD collection is only applicable to DELIVERED")
        return self


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    merchant_id: UUID
    customer_name: str | None
    customer_phone: str | None
    original_message: str | None
    normalized_message: str | None
    township: str | None
    street: str | None
    landmark: str | None
    building: str | None
    floor: str | None
    unit: str | None
    building_floor_unit: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    cod_amount: Decimal | None
    delivery_instructions: str | None
    delivery_time_window: str | None
    confidence_level: Confidence
    confidence_reasons: list[dict]
    parsing_mode: str
    ai_availability_status: str
    field_sources: dict
    parsing_metadata: dict
    manual_review_required: bool
    status: OrderStatus
    version: int
    created_at: datetime
    updated_at: datetime

    @field_serializer("cod_amount")
    def money_string(self, value):
        return format(value, ".0f") if value is not None else None


class OrderPage(BaseModel):
    items: list[OrderResponse]
    total: int
    page: int
    page_size: int


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    order_id: UUID
    event_type: str
    previous_status: OrderStatus | None
    new_status: OrderStatus
    metadata: dict = Field(validation_alias="event_metadata")
    created_at: datetime


class EventPage(BaseModel):
    items: list[EventResponse]
    total: int
    page: int
    page_size: int


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    email: str
    role: UserRole
    created_at: datetime
    updated_at: datetime
