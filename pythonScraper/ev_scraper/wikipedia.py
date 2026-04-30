"""Wikimedia helpers used to enrich EV records with real vehicle photos."""

from __future__ import annotations

import time
from typing import Optional

import requests

from .config import COMMONS_API, USER_AGENT, WIKI_DELAY_S, WIKI_REST


def fetch_wikipedia_image(make_name: str, model_name: str) -> Optional[str]:
    """Finds the best available image URL for a vehicle from Wikimedia sources."""
    search_term = f"{make_name} {model_name} electric"

    try:
        response = requests.get(
            COMMONS_API,
            params={
                "action": "query",
                "generator": "search",
                "gsrsearch": search_term,
                "gsrlimit": 5,
                "gsrnamespace": 6,
                "prop": "imageinfo",
                "iiprop": "url|extmetadata",
                "iiurlwidth": 800,
                "format": "json",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=12,
        )
        response.raise_for_status()
        pages = response.json().get("query", {}).get("pages", {})

        for page in pages.values():
            image_info = (page.get("imageinfo") or [{}])[0]
            url = image_info.get("url", "")
            thumb = image_info.get("thumburl", "")
            if url and any(url.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png")):
                return thumb or url
    except Exception:
        pass

    time.sleep(WIKI_DELAY_S)

    article_title = f"{make_name} {model_name}".replace(" ", "_")
    try:
        response = requests.get(
            f"{WIKI_REST}/{requests.utils.quote(article_title)}",
            headers={"User-Agent": USER_AGENT},
            timeout=12,
        )
        if response.status_code == 200:
            thumbnail = response.json().get("thumbnail", {}).get("source")
            if thumbnail:
                return thumbnail
    except Exception:
        pass

    return None
