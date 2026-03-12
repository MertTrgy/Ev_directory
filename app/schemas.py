from datetime import datetime
from typing import Any

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str


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


class VehicleDetailResponse(VehicleSummaryResponse):
    payload: dict[str, Any]


class VehicleListResponse(BaseModel):
    items: list[VehicleSummaryResponse]
    total: int
    limit: int
    offset: int
