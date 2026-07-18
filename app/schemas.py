"""Pydantic request/response schemas."""
import datetime as dt

from pydantic import BaseModel, EmailStr, Field


# --- Auth ---
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = ""


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    plan: str
    created_at: dt.datetime

    class Config:
        from_attributes = True


# --- API keys ---
class ApiKeyCreateIn(BaseModel):
    name: str = "default"


class ApiKeyOut(BaseModel):
    id: int
    name: str
    prefix: str
    created_at: dt.datetime

    class Config:
        from_attributes = True


class ApiKeyCreatedOut(ApiKeyOut):
    key: str  # full key — returned only once at creation


# --- Assessment ---
class DamageItem(BaseModel):
    damage_type: str
    severity: str
    detection_confidence: float
    severity_confidence: float
    repair: str
    cost_min: int
    cost_max: int
    cost_avg: int = 0
    parts_cost: list[int] = []
    labor_cost: list[int] = []
    paint_cost: list[int] = []
    repair_time: str = ""
    box: list[int]  # [x1, y1, x2, y2]


class AssessmentOut(BaseModel):
    id: int
    damages: list[DamageItem]
    total_min: int
    total_max: int
    currency: str = "USD"
    inference_ms: float
    annotated_image: str | None = None  # base64 JPEG
    warning: str | None = None
    gradcam_image: str | None = None    # base64 JPEG
    disclaimer: str = (
        "Cost estimates are indicative, based on US average repair pricing. "
        "Actual costs vary by location, vehicle make/model, and repair shop."
    )


class UsageOut(BaseModel):
    plan: str
    monthly_quota: int
    used_this_month: int
    remaining: int
