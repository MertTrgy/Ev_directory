"""FastAPI entrypoint for the Project E Python EV scraper service."""

from __future__ import annotations

import asyncio
import json
import os
import threading
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException

from ev_scraper.config import JSON_DATA_FILE, SOURCE_URL
from ev_scraper.enrichment import run_enrichment_background
from ev_scraper.json_catalog import normalize_vehicle
from ev_scraper import state
from ev_scraper.storage import load_enriched, load_vehicle_dataset, now_utc
from ev_scraper.wikipedia_scraper import scrape_vehicles
from ev_scraper.clearwatt_scraper import scrape_all_vehicles, fetch_vehicle_urls

app = FastAPI(title="Project E - EV Scraper", version="2.3.0")

# ── Clearwatt scrape state ────────────────────────────────────────────────────
_CLEARWATT_CACHE_FILE = os.path.join(os.path.dirname(__file__), "clearwatt_cache.json")

_clearwatt_progress: Dict[str, Any] = {"running": False, "total": 0, "done": 0, "errors": 0}
_clearwatt_results:  List[Dict[str, Any]] = []


def _save_clearwatt_cache(results: List[Dict[str, Any]]) -> None:
    try:
        with open(_CLEARWATT_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"count": len(results), "items": results}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass  # non-critical


def _load_clearwatt_cache() -> List[Dict[str, Any]]:
    try:
        if os.path.exists(_CLEARWATT_CACHE_FILE):
            with open(_CLEARWATT_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("items", [])
    except Exception:
        pass
    return []


# Pre-load cache from disk on startup so data survives restarts
_clearwatt_results = _load_clearwatt_cache()


@app.get("/health")
def health() -> Dict[str, Any]:
    """Reports service health plus the current image-enrichment state."""
    enriched = load_enriched()
    image_map = enriched.get("image_map", {})
    return {
        "status": "ok",
        "enrichedImages": len(image_map),
        "enrichedUpdated": enriched.get("updated_at"),
        "enrichmentStatus": state.enrichment_progress,
    }


@app.post("/vehicles/scrape")
def scrape() -> Dict[str, Any]:
    """Runs the legacy Wikipedia scrape and caches the result in memory."""
    try:
        state.scrape_cache = scrape_vehicles()
        state.last_scrape_utc = now_utc()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Scrape failed: {exc}") from exc

    return {
        "source": SOURCE_URL,
        "count": len(state.scrape_cache),
        "scrapedAtUtc": state.last_scrape_utc,
        "items": state.scrape_cache,
    }


@app.delete("/vehicles/cache")
def clear_cache() -> Dict[str, Any]:
    """Clears the in-memory scrape cache used by the legacy workflow."""
    cleared = len(state.scrape_cache)
    state.scrape_cache = []
    state.last_scrape_utc = None
    return {"cleared": cleared}


@app.get("/vehicles/json")
def get_vehicles_from_json() -> Dict[str, Any]:
    """Returns normalized vehicles from the bundled open-ev-data file."""
    if not os.path.exists(JSON_DATA_FILE):
        raise HTTPException(status_code=404, detail=f"Data file not found: {JSON_DATA_FILE}")

    try:
        raw = load_vehicle_dataset()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read data file: {exc}") from exc

    image_map = load_enriched().get("image_map", {})
    vehicles_raw = raw.get("vehicles", [])
    items = [normalize_vehicle(vehicle, image_map) for vehicle in vehicles_raw]

    return {
        "source": "open-ev-data",
        "count": len(items),
        "generatedAt": raw.get("generated_at"),
        "items": items,
    }


@app.post("/vehicles/enrich-all")
async def start_enrichment_all() -> Dict[str, Any]:
    """Starts the background image-enrichment task when it is not already running."""
    if state.enrichment_progress.get("running"):
        return {"status": "already_running", "progress": state.enrichment_progress}

    if not os.path.exists(JSON_DATA_FILE):
        raise HTTPException(status_code=404, detail="Source data file not found.")

    asyncio.create_task(run_enrichment_background())
    return {
        "status": "started",
        "message": "Enrichment running in background. Poll /vehicles/enrich-status for progress.",
    }


@app.post("/vehicles/enrich-stop")
def stop_enrichment() -> Dict[str, Any]:
    """Requests a graceful stop for the current enrichment job."""
    if not state.enrichment_progress.get("running"):
        return {"status": "not_running"}

    state.enrichment_progress["running"] = False
    return {"status": "stopping", "message": "Will stop after the current vehicle."}


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


# ── Clearwatt scraper endpoints ───────────────────────────────────────────────

@app.post("/vehicles/clearwatt/start")
def start_clearwatt_scrape() -> Dict[str, Any]:
    """
    Starts a background scrape of https://clearwatt.co.uk/directory.
    Returns immediately. Poll GET /vehicles/clearwatt/status for progress.
    When complete, GET /vehicles/clearwatt returns the full vehicle list.
    """
    global _clearwatt_results

    if _clearwatt_progress.get("running"):
        return {"status": "already_running", "progress": _clearwatt_progress}

    def _run() -> None:
        global _clearwatt_results
        _clearwatt_results = scrape_all_vehicles(_clearwatt_progress)
        _save_clearwatt_cache(_clearwatt_results)  # persist to disk

    threading.Thread(target=_run, daemon=True).start()
    return {
        "status": "started",
        "message": "Clearwatt scrape running in background. Poll /vehicles/clearwatt/status for progress.",
    }


@app.get("/vehicles/clearwatt/status")
def clearwatt_scrape_status() -> Dict[str, Any]:
    """Returns current progress of the running (or last completed) clearwatt scrape."""
    return {
        "running":  _clearwatt_progress.get("running", False),
        "total":    _clearwatt_progress.get("total", 0),
        "done":     _clearwatt_progress.get("done", 0),
        "errors":   _clearwatt_progress.get("errors", 0),
        "cached":   len(_clearwatt_results),
        "error":    _clearwatt_progress.get("error"),
    }


@app.post("/vehicles/clearwatt/stop")
def stop_clearwatt_scrape() -> Dict[str, Any]:
    """Requests a graceful stop of the running clearwatt scrape."""
    if not _clearwatt_progress.get("running"):
        return {"status": "not_running"}
    _clearwatt_progress["running"] = False
    return {"status": "stopping", "message": "Will stop after the current vehicle."}


@app.get("/vehicles/clearwatt")
def get_clearwatt_vehicles() -> Dict[str, Any]:
    """
    Returns all vehicles scraped from clearwatt (cached from last completed run).
    Start a scrape first with POST /vehicles/clearwatt/start.
    """
    if not _clearwatt_results and not _clearwatt_progress.get("running"):
        raise HTTPException(
            status_code=404,
            detail="No clearwatt data cached. Run POST /vehicles/clearwatt/start first.",
        )
    return {
        "source":   "clearwatt",
        "count":    len(_clearwatt_results),
        "progress": _clearwatt_progress,
        "items":    _clearwatt_results,
    }


@app.get("/vehicles/image-search")
def image_search(brand: str, model: str) -> Dict[str, Any]:
    """Test endpoint — searches for an image URL for the given brand + model."""
    from ev_scraper.web_image import fetch_web_image
    url = fetch_web_image(brand, model)
    return {"brand": brand, "model": model, "imageUrl": url, "found": url is not None}


@app.get("/vehicles/clearwatt/sitemap-count")
def clearwatt_sitemap_count() -> Dict[str, Any]:
    """Quick check — fetches the sitemap and returns the number of vehicle URLs found."""
    try:
        urls = fetch_vehicle_urls()
        return {"count": len(urls), "sample": urls[:5]}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
