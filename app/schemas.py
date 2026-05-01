from datetime import datetime
from typing import Any

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    enriched_images: int = 0
    enrichment_status: dict[str, Any] = {}


class SyncResponse(BaseModel):
    fetched: int
    inserted: int
    updated: int
    unchanged: int
    deleted: int


class VehicleSummaryResponse(BaseModel):
    id: int
    source_name: str
    source_vehicle_id: str
    vehicle_slug: str | None
    vehicle_name: str | None
    market: str
    raw_source_url: str | None
    image_url: str | None
    updated_at: datetime
    is_favorite: bool = False
    year: int | None = None
    brand: str | None = None
    range_km: int | None = None
    power_kw: float | None = None
    battery_kwh: float | None = None


class VehicleDetailResponse(VehicleSummaryResponse):
    payload: dict[str, Any]


class VehicleListResponse(BaseModel):
    items: list[VehicleSummaryResponse]
    total: int
    limit: int
    offset: int


# ── Auth ──────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    role: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ── Favorites ─────────────────────────────────────────────────────────────────

class FavoriteResponse(BaseModel):
    id: int
    vehicle_id: int
    created_at: datetime
