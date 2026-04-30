"""Shared configuration for the EV scraper service."""

from __future__ import annotations

import os

SOURCE_URL = "https://en.wikipedia.org/wiki/List_of_production_battery_electric_vehicles"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
WIKI_REST = "https://en.wikipedia.org/api/rest_v1/page/summary"
USER_AGENT = "ProjectE-EVDirectory/1.0 (ev-directory-app; open-source project)"
WIKI_DELAY_S = 0.5

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
JSON_DATA_FILE = os.path.join(BASE_DIR, "open-ev-data-v1.24.0.json")
ENRICHED_FILE = os.path.join(BASE_DIR, "ev-data-enriched.json")
