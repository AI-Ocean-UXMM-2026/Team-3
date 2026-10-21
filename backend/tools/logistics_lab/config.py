from pydantic import BaseModel, ConfigDict, Field


class SimulationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)
    orders: int = Field(default=100, ge=0, le=5000)
    seed: int = Field(default=20261021, ge=0, le=2**32 - 1)
    merchants: int = Field(default=3, ge=1, le=20)
    hubs: int = Field(default=2, ge=1, le=10)
    riders: int = Field(default=6, ge=1, le=40)
    batch_size: int = Field(default=100, ge=1, le=250)
    read_samples: int = Field(default=15, ge=5, le=50)
    workflow_limit: int = Field(default=24, ge=0, le=5000)
    confirmation_rate: float = Field(default=0.65, ge=0, le=1)
    delivery_failure_rate: float = Field(default=0.20, ge=0, le=1)
    demo: bool = False


class ComparisonConfig(BaseModel):
    """All values are assumptions, never measured courier parameters."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    baseline_failure_rate: float = Field(default=0.15, ge=0, le=1)
    unconfirmed_failure_rate: float = Field(default=0.15, ge=0, le=1)
    confirmed_failure_rate: float = Field(default=0.08, ge=0, le=1)
    confirmation_rate: float = Field(default=0.65, ge=0, le=1)
    baseline_seconds_per_order: float = Field(default=120, ge=0, le=3600)
    lannpya_seconds_per_order: float = Field(default=45, ge=0, le=3600)
    confirmation_handling_seconds: float = Field(default=60, ge=0, le=3600)
    labour_mmk_per_hour: float = Field(default=3000, ge=0, le=1000000)
    failed_attempt_cost_mmk: float = Field(default=3500, ge=0, le=10000000)
