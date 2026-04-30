"""Disk helpers for loading the EV dataset and enrichment cache."""

from __future__ import annotations

import datetime as dt
import json
import os
from typing import Any, Dict

from .config import ENRICHED_FILE, JSON_DATA_FILE


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def load_vehicle_dataset() -> Dict[str, Any]:
    with open(JSON_DATA_FILE, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_enriched() -> Dict[str, Any]:
    if os.path.exists(ENRICHED_FILE):
        try:
            with open(ENRICHED_FILE, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            pass
    return {"updated_at": None, "image_map": {}}


def save_enriched(data: Dict[str, Any]) -> None:
    data["updated_at"] = now_utc()
    tmp = ENRICHED_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, ENRICHED_FILE)
