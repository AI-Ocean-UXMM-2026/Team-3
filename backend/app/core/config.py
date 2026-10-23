import base64
import json
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LANNPYA_",
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ai_provider: Literal["mock", "disabled", "gemini", "json_http"] = "mock"
    ai_model: str | None = Field(default=None, min_length=1, max_length=128)
    ai_api_key: SecretStr | None = None
    ai_endpoint: str | None = None
    ai_external_requests_enabled: bool = False
    parser_mode: Literal["hybrid", "rules", "mock"] = "hybrid"
    ai_timeout_seconds: float = Field(default=3.0, gt=0, le=30, allow_inf_nan=False)
    ai_max_input_chars: int = Field(default=2000, ge=128, le=4000)
    environment: Literal["local", "test", "production"] = "local"
    routing_provider: Literal["disabled", "offline", "google", "ors"] = "offline"
    routing_external_requests_enabled: bool = False
    google_demo_enabled: bool = False
    google_demo_max_requests: int = Field(default=0, ge=0, le=10)
    google_demo_budget_directory: Path = (
        Path(__file__).resolve().parents[3] / ".tmp/google-dispatch-budget"
    )
    google_routes_api_key: SecretStr | None = None
    ors_api_key: SecretStr | None = None
    routing_two_wheeler_enabled: bool = False
    routing_request_timeout_seconds: float = Field(default=10, gt=0, le=30, allow_inf_nan=False)
    routing_max_stops: int = Field(default=25, ge=1, le=50)
    routing_requests_per_minute: int = Field(default=10, ge=1, le=60)
    routing_plan_ttl_minutes: int = Field(default=15, ge=1, le=60)
    order_management_enabled: bool = False
    supabase_auth_enabled: bool = False
    supabase_url: str | None = None
    supabase_publishable_key: str | None = None
    buyer_rate_limit_secret: SecretStr | None = None
    auto_provision_users: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "LANNPYA_AUTO_PROVISION_USERS", "AUTO_PROVISION_USERS", "LANNPYA_AUTO_PROVISION_DISPATCHERS"
        ),
    )

    @model_validator(mode="after")
    def auth_configuration(self):
        if self.supabase_auth_enabled:
            parsed = urlsplit(self.supabase_url or "")
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
                or not self.supabase_publishable_key
            ):
                raise ValueError(
                    "Supabase Auth requires an HTTPS project origin and publishable key"
                )
            self.supabase_url = self.supabase_url.rstrip("/")
            key = self.supabase_publishable_key
            public = key.startswith("sb_publishable_")
            if not public:
                try:
                    payload = key.split(".")[1]
                    public = (
                        json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))[
                            "role"
                        ]
                        == "anon"
                    )
                except (ValueError, KeyError, IndexError):
                    public = False
            if not public:
                raise ValueError("Supabase browser configuration requires a publishable/anon key")
        if self.environment == "production":
            if self.buyer_otp_mode != "twilio" or not self.buyer_otp_external_sends_enabled:
                raise ValueError("Production requires explicitly enabled Twilio Verify")
            if not (self.buyer_twilio_account_sid and self.buyer_twilio_auth_token and self.buyer_twilio_verify_service_sid):
                raise ValueError("Production Twilio Verify credentials are required")
        if self.buyer_reminder_external_sends_enabled:
            if not (self.buyer_twilio_account_sid and self.buyer_twilio_auth_token):
                raise ValueError("Buyer reminder SMS requires Twilio Messaging credentials")
            if bool(self.buyer_twilio_messaging_service_sid) == bool(self.buyer_twilio_message_from):
                raise ValueError("Configure exactly one Twilio Messaging Service SID or sender")
        return self

    database_url: SecretStr = Field(
        default=SecretStr("sqlite+pysqlite:///./data/lannpya_dev.sqlite3"),
        validation_alias=AliasChoices("LANNPYA_DATABASE_URL", "DATABASE_URL"),
    )
    dev_access_token: SecretStr | None = None
    dev_actor_id: UUID | None = None
    rider_max_active_assignments: int = Field(default=100, ge=1, le=200)
    rider_require_cod_confirmation: bool = True
    buyer_link_hours: int = Field(default=72, ge=1, le=168)
    buyer_session_minutes: int = Field(default=15, ge=1, le=30)
    buyer_frontend_base_url: str | None = None
    # Browser key for Google Maps JS + Places; restrict it by HTTP referrer in Google Cloud.
    google_maps_browser_key: str | None = Field(default=None, max_length=200)
    buyer_request_limit_per_minute: int = Field(default=60, ge=1, le=600)
    buyer_verify_limit_per_minute: int = Field(default=10, ge=1, le=60)
    buyer_rescheduling_enabled: bool = False
    buyer_leave_with_security_enabled: bool = False
    buyer_cutoff_hour: int = Field(default=15, ge=0, le=23)
    buyer_min_notice_minutes: int = Field(default=120, ge=0, le=1440)
    buyer_max_schedule_days: int = Field(default=7, ge=1, le=30)
    buyer_cross_township_fee_mmk: int | None = Field(default=None, ge=0, le=1000000000)
    buyer_otp_mode: Literal["demo", "twilio"] = "demo"
    buyer_otp_external_sends_enabled: bool = False
    buyer_twilio_account_sid: str | None = None
    buyer_twilio_auth_token: SecretStr | None = None
    buyer_twilio_verify_service_sid: str | None = None
    buyer_reminder_external_sends_enabled: bool = False
    buyer_reminder_lead_minutes: int = Field(default=30, ge=1, le=1440)
    buyer_twilio_messaging_service_sid: str | None = None
    buyer_twilio_message_from: str | None = None
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://localhost:3000",
            "http://localhost:5500",
            "http://127.0.0.1:5500",
        ]
    )

    @field_validator("buyer_frontend_base_url")
    @classmethod
    def frontend_url(cls, value):
        if value is None:
            return None
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Buyer frontend URL must be an HTTP(S) base without credentials")
        if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("Non-local buyer frontend URLs require HTTPS")
        return value.rstrip("/")

    @field_validator("cors_origins")
    @classmethod
    def validate_origins(cls, origins: list[str]) -> list[str]:
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.netloc
                != parsed.hostname + (f":{parsed.port}" if parsed.port is not None else "")
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("CORS entries must be exact HTTP(S) origins without paths")
        return origins
