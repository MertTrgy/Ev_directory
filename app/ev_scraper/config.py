"""Shared configuration for the EV scraper service."""

from __future__ import annotations

import os

SOURCE_URL = "https://en.wikipedia.org/wiki/List_of_production_battery_electric_vehicles"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
WIKI_REST = "https://en.wikipedia.org/api/rest_v1/page/summary"
USER_AGENT = "ProjectE-EVDirectory/1.0 (ev-directory-app; open-source project)"
WIKI_DELAY_S = 0.5

# EV_DATA_DIR env var overrides; default walks 3 levels up:
#   app/ev_scraper/config.py → app/ev_scraper → app → project root
DATA_DIR = os.environ.get("EV_DATA_DIR") or os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

# Locate the open-ev-data JSON: versioned name first, then generic name,
# then the pythonScraper subdirectory as last resort.
_CANDIDATES = [
    os.path.join(DATA_DIR, "open-ev-data-v1.24.0.json"),
    os.path.join(DATA_DIR, "open-ev-data.json"),
    os.path.join(DATA_DIR, "pythonScraper", "open-ev-data-v1.24.0.json"),
]
JSON_DATA_FILE = next((p for p in _CANDIDATES if os.path.exists(p)), _CANDIDATES[0])

ENRICHED_FILE = os.path.join(DATA_DIR, "ev-data-enriched.json")
