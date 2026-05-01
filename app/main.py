"""FastAPI backend — EV Directory Phase 2."""

from __future__ import annotations

import asyncio
import json
import os
import threading
from typing import Any, Dict, List

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .auth import create_access_token, decode_token, hash_password, verify_password
from .config import settings
from .db import SessionLocal
from .logging_config import configure_logging
from .models import User
from .schemas import (
    FavoriteResponse,
    HealthResponse,
    SyncResponse,
    TokenResponse,
    UserCreate,
    UserResponse,
    VehicleDetailResponse,
    VehicleListResponse,
    VehicleSummaryResponse,
)
from .service import (
    add_favorite,
    create_user,
    get_user_by_email,
    get_user_by_id,
    get_user_favorite_ids,
    get_user_favorites,
    get_vehicle_record,
    get_vehicles_by_ids,
    list_vehicle_records,
    remove_favorite,
    sync_evdb_data,
    sync_vehicles_to_db,
    vehicle_detail_dict,
    vehicle_summary_dict,
)
from .ev_scraper.config import JSON_DATA_FILE
from .ev_scraper.enrichment import run_enrichment_background
from .ev_scraper.json_catalog import normalize_vehicle
from .ev_scraper import state
from .ev_scraper.storage import load_enriched, load_vehicle_dataset, now_utc
from .ev_scraper.wikipedia_scraper import scrape_vehicles
from .ev_scraper.clearwatt_scraper import fetch_vehicle_urls, scrape_all_vehicles

configure_logging()

app = FastAPI(title="EV Directory API", version="4.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_CLEARWATT_CACHE_FILE = os.path.join(settings.ev_data_dir, "data", "clearwatt_cache.json")
_clearwatt_progress: Dict[str, Any] = {"running": False, "total": 0, "done": 0, "errors": 0}
_clearwatt_results: List[Dict[str, Any]] = []

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _save_clearwatt_cache(results: List[Dict[str, Any]]) -> None:
    try:
        os.makedirs(os.path.dirname(_CLEARWATT_CACHE_FILE), exist_ok=True)
        with open(_CLEARWATT_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"count": len(results), "items": results}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _load_clearwatt_cache() -> List[Dict[str, Any]]:
    try:
        if os.path.exists(_CLEARWATT_CACHE_FILE):
            with open(_CLEARWATT_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("items", [])
    except Exception:
        pass
    return []


_clearwatt_results = _load_clearwatt_cache()


# ── Auth dependencies ──────────────────────────────────────────────────────────

def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    if not token:
        return None
    payload = decode_token(token)
    if not payload:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    return get_user_by_id(db, int(user_id))


def require_user(current_user: User | None = Depends(get_current_user)) -> User:
    if current_user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return current_user


def require_admin(current_user: User = Depends(require_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    enriched = load_enriched()
    image_map = enriched.get("image_map", {})
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        enriched_images=len(image_map),
        enrichment_status=state.enrichment_progress,
    )


# ── Auth endpoints ─────────────────────────────────────────────────────────────

@app.post("/auth/signup", response_model=TokenResponse)
def signup(body: UserCreate, db: Session = Depends(get_db)) -> TokenResponse:
    if get_user_by_email(db, body.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    user = create_user(db, body.email, hash_password(body.password))
    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        user=UserResponse(id=user.id, email=user.email, role=user.role, created_at=user.created_at),
    )


@app.post("/auth/login", response_model=TokenResponse)
def login(body: UserCreate, db: Session = Depends(get_db)) -> TokenResponse:
    user = get_user_by_email(db, body.email)
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        user=UserResponse(id=user.id, email=user.email, role=user.role, created_at=user.created_at),
    )


@app.get("/auth/me", response_model=UserResponse)
def me(current_user: User = Depends(require_user)) -> UserResponse:
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role,
        created_at=current_user.created_at,
    )


# ── Favorites endpoints ────────────────────────────────────────────────────────

@app.get("/favorites", response_model=VehicleListResponse)
def list_favorites(
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> VehicleListResponse:
    records = get_user_favorites(db, current_user.id)
    fav_ids = {r.id for r in records}
    items = []
    for record in records:
        d = vehicle_summary_dict(record)
        d["is_favorite"] = record.id in fav_ids
        items.append(VehicleSummaryResponse(**d))
    return VehicleListResponse(items=items, total=len(items), limit=len(items), offset=0)


@app.post("/favorites/{vehicle_id}", response_model=FavoriteResponse)
def add_to_favorites(
    vehicle_id: int,
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> FavoriteResponse:
    if get_vehicle_record(db, vehicle_id) is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    try:
        fav = add_favorite(db, current_user.id, vehicle_id)
        return FavoriteResponse(id=fav.id, vehicle_id=fav.vehicle_id, created_at=fav.created_at)
    except Exception:
        raise HTTPException(status_code=409, detail="Already in favorites")


@app.delete("/favorites/{vehicle_id}")
def remove_from_favorites(
    vehicle_id: int,
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    if not remove_favorite(db, current_user.id, vehicle_id):
        raise HTTPException(status_code=404, detail="Not in favorites")
    return {"removed": True}


# ── JSON catalog (open-ev-data file) ──────────────────────────────────────────

@app.get("/vehicles/json")
def get_vehicles_from_json() -> Dict[str, Any]:
    if not os.path.exists(JSON_DATA_FILE):
        raise HTTPException(status_code=404, detail=f"Data file not found: {JSON_DATA_FILE}")
    try:
        raw = load_vehicle_dataset()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read data file: {exc}") from exc

    image_map = load_enriched().get("image_map", {})
    items = [normalize_vehicle(v, image_map) for v in raw.get("vehicles", [])]
    return {"source": "open-ev-data", "count": len(items), "generatedAt": raw.get("generated_at"), "items": items}


@app.post("/vehicles/json/sync-to-db", response_model=SyncResponse)
async def sync_json_to_db(db: Session = Depends(get_db)) -> SyncResponse:
    if not os.path.exists(JSON_DATA_FILE):
        raise HTTPException(status_code=404, detail="Data file not found.")
    try:
        raw = load_vehicle_dataset()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read data file: {exc}") from exc

    image_map = load_enriched().get("image_map", {})
    normalized = [normalize_vehicle(v, image_map) for v in raw.get("vehicles", [])]
    stats = await sync_vehicles_to_db(db, normalized, source_name="open-ev-data-json")
    return SyncResponse(fetched=stats.fetched, inserted=stats.inserted, updated=stats.updated, unchanged=stats.unchanged, deleted=stats.deleted)


# ── Comparison endpoint ────────────────────────────────────────────────────────

@app.get("/vehicles/compare")
def compare_vehicles(
    ids: str = Query(..., description="Comma-separated vehicle IDs (2–4)"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    vehicle_ids = [int(x.strip()) for x in ids.split(",") if x.strip().isdigit()]
    if len(vehicle_ids) < 2 or len(vehicle_ids) > 4:
        raise HTTPException(status_code=400, detail="Provide 2–4 comma-separated vehicle IDs")
    records = get_vehicles_by_ids(db, vehicle_ids)
    if len(records) != len(vehicle_ids):
        raise HTTPException(status_code=404, detail="One or more vehicles not found")
    return {"count": len(records), "items": [vehicle_detail_dict(r) for r in records]}


# ── Image enrichment ───────────────────────────────────────────────────────────

@app.get("/vehicles/enrich-status")
def enrich_status() -> Dict[str, Any]:
    enriched = load_enriched()
    image_map = enriched.get("image_map", {})
    total = 0
    if os.path.exists(JSON_DATA_FILE):
        try:
            total = len(load_vehicle_dataset().get("vehicles", []))
        except Exception:
            pass
    return {
        "totalVehicles": total,
        "enrichedImages": len(image_map),
        "remaining": total - len(image_map),
        "percentComplete": round(len(image_map) / total * 100, 1) if total else 0,
        "updatedAt": enriched.get("updated_at"),
        "job": state.enrichment_progress,
    }


@app.post("/vehicles/enrich-all")
async def start_enrichment_all() -> Dict[str, Any]:
    if state.enrichment_progress.get("running"):
        return {"status": "already_running", "progress": state.enrichment_progress}
    if not os.path.exists(JSON_DATA_FILE):
        raise HTTPException(status_code=404, detail="Source data file not found.")
    asyncio.create_task(run_enrichment_background())
    return {"status": "started", "message": "Poll /vehicles/enrich-status for progress."}


@app.post("/vehicles/enrich-stop")
def stop_enrichment() -> Dict[str, Any]:
    if not state.enrichment_progress.get("running"):
        return {"status": "not_running"}
    state.enrichment_progress["running"] = False
    return {"status": "stopping"}


# ── Wikipedia scrape ───────────────────────────────────────────────────────────

@app.post("/vehicles/scrape")
def scrape_wikipedia() -> Dict[str, Any]:
    try:
        state.scrape_cache = scrape_vehicles()
        state.last_scrape_utc = now_utc()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Scrape failed: {exc}") from exc
    return {"source": "wikipedia", "count": len(state.scrape_cache), "scrapedAtUtc": state.last_scrape_utc, "items": state.scrape_cache}


@app.delete("/vehicles/cache")
def clear_scrape_cache() -> Dict[str, Any]:
    cleared = len(state.scrape_cache)
    state.scrape_cache = []
    state.last_scrape_utc = None
    return {"cleared": cleared}


# ── Clearwatt scraper ──────────────────────────────────────────────────────────

@app.get("/vehicles/clearwatt/sitemap-count")
def clearwatt_sitemap_count() -> Dict[str, Any]:
    try:
        urls = fetch_vehicle_urls()
        return {"count": len(urls), "sample": urls[:5]}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/vehicles/clearwatt/status")
def clearwatt_scrape_status() -> Dict[str, Any]:
    return {
        "running": _clearwatt_progress.get("running", False),
        "total": _clearwatt_progress.get("total", 0),
        "done": _clearwatt_progress.get("done", 0),
        "errors": _clearwatt_progress.get("errors", 0),
        "cached": len(_clearwatt_results),
        "error": _clearwatt_progress.get("error"),
    }


@app.get("/vehicles/clearwatt")
def get_clearwatt_vehicles() -> Dict[str, Any]:
    if not _clearwatt_results and not _clearwatt_progress.get("running"):
        raise HTTPException(status_code=404, detail="No Clearwatt data cached. Run POST /vehicles/clearwatt/start first.")
    return {"source": "clearwatt", "count": len(_clearwatt_results), "progress": _clearwatt_progress, "items": _clearwatt_results}


@app.post("/vehicles/clearwatt/start")
def start_clearwatt_scrape() -> Dict[str, Any]:
    global _clearwatt_results
    if _clearwatt_progress.get("running"):
        return {"status": "already_running", "progress": _clearwatt_progress}

    def _run() -> None:
        global _clearwatt_results
        _clearwatt_results = scrape_all_vehicles(_clearwatt_progress)
        _save_clearwatt_cache(_clearwatt_results)

    threading.Thread(target=_run, daemon=True).start()
    return {"status": "started", "message": "Poll /vehicles/clearwatt/status for progress."}


@app.post("/vehicles/clearwatt/stop")
def stop_clearwatt_scrape() -> Dict[str, Any]:
    if not _clearwatt_progress.get("running"):
        return {"status": "not_running"}
    _clearwatt_progress["running"] = False
    return {"status": "stopping"}


@app.post("/vehicles/clearwatt/sync-to-db", response_model=SyncResponse)
async def sync_clearwatt_to_db(db: Session = Depends(get_db)) -> SyncResponse:
    if not _clearwatt_results:
        raise HTTPException(status_code=404, detail="No Clearwatt data cached. Run POST /vehicles/clearwatt/start first.")
    stats = await sync_vehicles_to_db(db, _clearwatt_results, source_name="clearwatt")
    return SyncResponse(fetched=stats.fetched, inserted=stats.inserted, updated=stats.updated, unchanged=stats.unchanged, deleted=stats.deleted)


# ── Image search utility ───────────────────────────────────────────────────────

@app.get("/vehicles/image-search")
def image_search(brand: str, model: str) -> Dict[str, Any]:
    from .ev_scraper.web_image import fetch_web_image
    url = fetch_web_image(brand, model)
    return {"brand": brand, "model": model, "imageUrl": url, "found": url is not None}


# ── DB-backed vehicle endpoints ────────────────────────────────────────────────

@app.get("/vehicles", response_model=VehicleListResponse)
def list_vehicles(
    limit: int = Query(default=24, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None),
    brand: str | None = Query(default=None),
    market: str | None = Query(default=None),
    year_min: int | None = Query(default=None),
    year_max: int | None = Query(default=None),
    range_min_km: int | None = Query(default=None),
    range_max_km: int | None = Query(default=None),
    body_style: str | None = Query(default=None),
    drivetrain: str | None = Query(default=None),
    sort_by: str = Query(default="updated"),
    order: str = Query(default="desc"),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
) -> VehicleListResponse:
    records, total, safe_limit, safe_offset = list_vehicle_records(
        db, limit=limit, offset=offset,
        search=search, brand=brand, market=market,
        year_min=year_min, year_max=year_max,
        range_min_km=range_min_km, range_max_km=range_max_km,
        body_style=body_style, drivetrain=drivetrain,
        sort_by=sort_by, order=order,
    )
    fav_ids = get_user_favorite_ids(db, current_user.id) if current_user else set()
    items = []
    for record in records:
        d = vehicle_summary_dict(record)
        d["is_favorite"] = record.id in fav_ids
        items.append(VehicleSummaryResponse(**d))
    return VehicleListResponse(items=items, total=total, limit=safe_limit, offset=safe_offset)


@app.get("/vehicles/{vehicle_id}", response_model=VehicleDetailResponse)
def vehicle_detail(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
) -> VehicleDetailResponse:
    record = get_vehicle_record(db, vehicle_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Vehicle with id={vehicle_id} not found")
    fav_ids = get_user_favorite_ids(db, current_user.id) if current_user else set()
    d = vehicle_detail_dict(record)
    d["is_favorite"] = record.id in fav_ids
    return VehicleDetailResponse(**d)


# ── External-API sync ──────────────────────────────────────────────────────────

@app.post("/sync", response_model=SyncResponse)
async def sync_from_api(
    remove_missing: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> SyncResponse:
    stats = await sync_evdb_data(db, remove_missing=remove_missing)
    return SyncResponse(fetched=stats.fetched, inserted=stats.inserted, updated=stats.updated, unchanged=stats.unchanged, deleted=stats.deleted)


@app.post("/sync/update", response_model=SyncResponse)
async def sync_update(db: Session = Depends(get_db)) -> SyncResponse:
    stats = await sync_evdb_data(db, remove_missing=True)
    return SyncResponse(fetched=stats.fetched, inserted=stats.inserted, updated=stats.updated, unchanged=stats.unchanged, deleted=stats.deleted)
