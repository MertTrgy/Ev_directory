"""Unified FastAPI backend — DB persistence + EV scraper endpoints."""

from __future__ import annotations

import asyncio
import json
import os
import threading
from typing import Any, Dict, List

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .config import settings
from .db import SessionLocal
from .logging_config import configure_logging
from .schemas import (
    HealthResponse,
    SyncResponse,
    VehicleDetailResponse,
    VehicleListResponse,
    VehicleSummaryResponse,
)
from .service import (
    get_vehicle_record,
    list_vehicle_records,
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

app = FastAPI(title="EV Directory API", version="3.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_CLEARWATT_CACHE_FILE = os.path.join(settings.ev_data_dir, "clearwatt_cache.json")
_clearwatt_progress: Dict[str, Any] = {"running": False, "total": 0, "done": 0, "errors": 0}
_clearwatt_results: List[Dict[str, Any]] = []


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _save_clearwatt_cache(results: List[Dict[str, Any]]) -> None:
    try:
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


# ── JSON catalog (open-ev-data file) ──────────────────────────────────────────
# These literal routes must be declared BEFORE /vehicles/{vehicle_id}.

@app.get("/vehicles/json")
def get_vehicles_from_json() -> Dict[str, Any]:
    """Returns all normalized vehicles from the bundled open-ev-data JSON file."""
    if not os.path.exists(JSON_DATA_FILE):
        raise HTTPException(status_code=404, detail=f"Data file not found: {JSON_DATA_FILE}")
    try:
        raw = load_vehicle_dataset()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read data file: {exc}") from exc

    image_map = load_enriched().get("image_map", {})
    items = [normalize_vehicle(v, image_map) for v in raw.get("vehicles", [])]
    return {
        "source": "open-ev-data",
        "count": len(items),
        "generatedAt": raw.get("generated_at"),
        "items": items,
    }


@app.post("/vehicles/json/sync-to-db", response_model=SyncResponse)
async def sync_json_to_db(db: Session = Depends(get_db)) -> SyncResponse:
    """Loads the local open-ev-data JSON and upserts all vehicles into the database."""
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


# ── Image enrichment ───────────────────────────────────────────────────────────

@app.get("/vehicles/enrich-status")
def enrich_status() -> Dict[str, Any]:
    """Returns image-enrichment progress and overall completion counts."""
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
    """Starts background image-enrichment. Poll /vehicles/enrich-status for progress."""
    if state.enrichment_progress.get("running"):
        return {"status": "already_running", "progress": state.enrichment_progress}
    if not os.path.exists(JSON_DATA_FILE):
        raise HTTPException(status_code=404, detail="Source data file not found.")
    asyncio.create_task(run_enrichment_background())
    return {"status": "started", "message": "Poll /vehicles/enrich-status for progress."}


@app.post("/vehicles/enrich-stop")
def stop_enrichment() -> Dict[str, Any]:
    """Requests a graceful stop for the current enrichment job."""
    if not state.enrichment_progress.get("running"):
        return {"status": "not_running"}
    state.enrichment_progress["running"] = False
    return {"status": "stopping"}


# ── Wikipedia scrape ───────────────────────────────────────────────────────────

@app.post("/vehicles/scrape")
def scrape_wikipedia() -> Dict[str, Any]:
    """Scrapes the Wikipedia production-EV list and caches results in memory."""
    try:
        state.scrape_cache = scrape_vehicles()
        state.last_scrape_utc = now_utc()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Scrape failed: {exc}") from exc
    return {
        "source": "wikipedia",
        "count": len(state.scrape_cache),
        "scrapedAtUtc": state.last_scrape_utc,
        "items": state.scrape_cache,
    }


@app.delete("/vehicles/cache")
def clear_scrape_cache() -> Dict[str, Any]:
    """Clears the in-memory Wikipedia scrape cache."""
    cleared = len(state.scrape_cache)
    state.scrape_cache = []
    state.last_scrape_utc = None
    return {"cleared": cleared}


# ── Clearwatt scraper ──────────────────────────────────────────────────────────

@app.get("/vehicles/clearwatt/sitemap-count")
def clearwatt_sitemap_count() -> Dict[str, Any]:
    """Fetches the Clearwatt sitemap and returns the total vehicle URL count."""
    try:
        urls = fetch_vehicle_urls()
        return {"count": len(urls), "sample": urls[:5]}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/vehicles/clearwatt/status")
def clearwatt_scrape_status() -> Dict[str, Any]:
    """Returns current progress of the running (or last completed) Clearwatt scrape."""
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
    """Returns all vehicles cached from the last completed Clearwatt scrape."""
    if not _clearwatt_results and not _clearwatt_progress.get("running"):
        raise HTTPException(
            status_code=404,
            detail="No Clearwatt data cached. Run POST /vehicles/clearwatt/start first.",
        )
    return {
        "source": "clearwatt",
        "count": len(_clearwatt_results),
        "progress": _clearwatt_progress,
        "items": _clearwatt_results,
    }


@app.post("/vehicles/clearwatt/start")
def start_clearwatt_scrape() -> Dict[str, Any]:
    """Starts a background scrape of clearwatt.co.uk. Poll /vehicles/clearwatt/status."""
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
    """Requests a graceful stop of the running Clearwatt scrape."""
    if not _clearwatt_progress.get("running"):
        return {"status": "not_running"}
    _clearwatt_progress["running"] = False
    return {"status": "stopping"}


@app.post("/vehicles/clearwatt/sync-to-db", response_model=SyncResponse)
async def sync_clearwatt_to_db(db: Session = Depends(get_db)) -> SyncResponse:
    """Upserts all cached Clearwatt vehicles into the database."""
    if not _clearwatt_results:
        raise HTTPException(
            status_code=404,
            detail="No Clearwatt data cached. Run POST /vehicles/clearwatt/start first.",
        )
    stats = await sync_vehicles_to_db(db, _clearwatt_results, source_name="clearwatt")
    return SyncResponse(fetched=stats.fetched, inserted=stats.inserted, updated=stats.updated, unchanged=stats.unchanged, deleted=stats.deleted)


# ── Image search utility ───────────────────────────────────────────────────────

@app.get("/vehicles/image-search")
def image_search(brand: str, model: str) -> Dict[str, Any]:
    """Searches the web for an image URL for the given brand + model."""
    from .ev_scraper.web_image import fetch_web_image
    url = fetch_web_image(brand, model)
    return {"brand": brand, "model": model, "imageUrl": url, "found": url is not None}


# ── DB-backed vehicle endpoints ────────────────────────────────────────────────
# Parameterised route MUST come after all literal /vehicles/* routes above.

@app.get("/vehicles", response_model=VehicleListResponse)
def list_vehicles(
    limit: int = Query(default=24, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> VehicleListResponse:
    """Lists vehicles stored in the database with pagination."""
    records, total, safe_limit, safe_offset = list_vehicle_records(db, limit=limit, offset=offset)
    items = [VehicleSummaryResponse(**vehicle_summary_dict(record)) for record in records]
    return VehicleListResponse(items=items, total=total, limit=safe_limit, offset=safe_offset)


@app.get("/vehicles/{vehicle_id}", response_model=VehicleDetailResponse)
def vehicle_detail(vehicle_id: int, db: Session = Depends(get_db)) -> VehicleDetailResponse:
    """Returns full detail for a single vehicle stored in the database."""
    record = get_vehicle_record(db, vehicle_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Vehicle with id={vehicle_id} not found")
    return VehicleDetailResponse(**vehicle_detail_dict(record))


# ── External-API sync (legacy provider) ───────────────────────────────────────

@app.post("/sync", response_model=SyncResponse)
async def sync_from_api(
    remove_missing: bool = Query(default=False, description="Delete DB records absent from latest API response"),
    db: Session = Depends(get_db),
) -> SyncResponse:
    """Syncs vehicles from the configured external EVDB API into the database."""
    stats = await sync_evdb_data(db, remove_missing=remove_missing)
    return SyncResponse(
        fetched=stats.fetched,
        inserted=stats.inserted,
        updated=stats.updated,
        unchanged=stats.unchanged,
        deleted=stats.deleted,
    )


@app.post("/sync/update", response_model=SyncResponse)
async def sync_update(db: Session = Depends(get_db)) -> SyncResponse:
    """Syncs from external API and removes any records no longer present."""
    stats = await sync_evdb_data(db, remove_missing=True)
    return SyncResponse(
        fetched=stats.fetched,
        inserted=stats.inserted,
        updated=stats.updated,
        unchanged=stats.unchanged,
        deleted=stats.deleted,
    )
