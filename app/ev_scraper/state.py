"""In-memory state shared across scraper endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

scrape_cache: List[Dict[str, Any]] = []
last_scrape_utc: Optional[str] = None

enrichment_progress: Dict[str, Any] = {
    "running": False,
    "processed": 0,
    "total": 0,
    "found": 0,
    "startedAt": None,
    "completedAt": None,
    "error": None,
    "lastError": None,
}


def reset_enrichment_progress(started_at: str) -> None:
    enrichment_progress.update(
        {
            "running": True,
            "processed": 0,
            "total": 0,
            "found": 0,
            "startedAt": started_at,
            "completedAt": None,
            "error": None,
            "lastError": None,
        }
    )
