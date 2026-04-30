"""Disk helpers for loading the EV dataset and enrichment cache."""

from __future__ import annotations

import datetime as dt
import json
import os
from typing import Any, Dict

from .config import ENRICHED_FILE, JSON_DATA_FILE


def now_utc() -> str:
    """Returns the current UTC timestamp in ISO-8601 format."""
    return dt.datetime.now(dt.timezone.utc).isoformat()


def load_vehicle_dataset() -> Dict[str, Any]:
    """Loads the bundled open-ev-data JSON payload."""
    with open(JSON_DATA_FILE, "r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def load_enriched() -> Dict[str, Any]:
    """Reads the local image-enrichment cache from disk when present."""
    if os.path.exists(ENRICHED_FILE):
        try:
            with open(ENRICHED_FILE, "r", encoding="utf-8") as file_handle:
                return json.load(file_handle)
        except Exception:
            pass

    return {"updated_at": None, "image_map": {}}


def save_enriched(data: Dict[str, Any]) -> None:
    """Persists the image-enrichment cache to disk using an atomic write.

    Writes to a temp file first then renames so concurrent readers never see
    a half-written file (which would cause a JSONDecodeError).
    """
    data["updated_at"] = now_utc()
    tmp = ENRICHED_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as file_handle:
        json.dump(data, file_handle, indent=2, ensure_ascii=False)
    os.replace(tmp, ENRICHED_FILE)
