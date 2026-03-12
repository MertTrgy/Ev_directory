from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .config import settings
from .db import SessionLocal
from .logging_config import configure_logging
from .schemas import HealthResponse, SyncResponse, VehicleDetailResponse, VehicleListResponse, VehicleSummaryResponse
from .service import (
    get_vehicle_record,
    list_vehicle_records,
    sync_evdb_data,
    vehicle_detail_dict,
    vehicle_summary_dict,
)

configure_logging()

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list(),
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get('/health', response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status='ok', service=settings.app_name)


@app.post('/sync', response_model=SyncResponse)
async def sync(
    remove_missing: bool = Query(default=False, description='Delete records not present in latest API response'),
    db: Session = Depends(get_db),
) -> SyncResponse:
    stats = await sync_evdb_data(db, remove_missing=remove_missing)
    return SyncResponse(
        fetched=stats.fetched,
        inserted=stats.inserted,
        updated=stats.updated,
        unchanged=stats.unchanged,
        deleted=stats.deleted,
    )


@app.post('/sync/update', response_model=SyncResponse)
async def sync_update(db: Session = Depends(get_db)) -> SyncResponse:
    stats = await sync_evdb_data(db, remove_missing=True)
    return SyncResponse(
        fetched=stats.fetched,
        inserted=stats.inserted,
        updated=stats.updated,
        unchanged=stats.unchanged,
        deleted=stats.deleted,
    )


@app.get('/vehicles', response_model=VehicleListResponse)
def list_vehicles(
    limit: int = Query(default=24, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> VehicleListResponse:
    records, total, safe_limit, safe_offset = list_vehicle_records(db, limit=limit, offset=offset)
    items = [VehicleSummaryResponse(**vehicle_summary_dict(record)) for record in records]
    return VehicleListResponse(items=items, total=total, limit=safe_limit, offset=safe_offset)


@app.get('/vehicles/{vehicle_id}', response_model=VehicleDetailResponse)
def vehicle_detail(vehicle_id: int, db: Session = Depends(get_db)) -> VehicleDetailResponse:
    record = get_vehicle_record(db, vehicle_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f'Vehicle with id={vehicle_id} was not found')
    return VehicleDetailResponse(**vehicle_detail_dict(record))
