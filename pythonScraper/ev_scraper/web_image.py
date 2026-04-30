"""Web image search helpers to enrich EV records with vehicle photos.

Strategy (in order):
1. DuckDuckGo Instant Answer API — public, no key, returns Wikipedia images for known entities.
2. DuckDuckGo image search — full results via undocumented i.js endpoint.
3. Wikipedia REST API thumbnail — article image as final fallback.
"""

from __future__ import annotations

import re
import time
import urllib.parse
from typing import Optional

import requests

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ProjectE-EVBot/1.0; educational use)",
    "Accept-Language": "en-US,en;q=0.9",
}
_TIMEOUT = 12
_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")


def _is_image_url(url: str) -> bool:
    return bool(url) and any(url.lower().split("?")[0].endswith(ext) for ext in _IMAGE_EXTS)


def _unwrap_ddg_proxy(proxy_url: str) -> Optional[str]:
    """DDG proxies images via /iu/?u=ENCODED_URL — extract the real URL."""
    parsed = urllib.parse.urlparse(proxy_url)
    params = urllib.parse.parse_qs(parsed.query)
    raw = params.get("u", [None])[0]
    return urllib.parse.unquote(raw) if raw else None


def _fetch_ddg_instant(query: str) -> Optional[str]:
    """DuckDuckGo Instant Answer API — free, no API key, returns entity images."""
    try:
        resp = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": "1", "t": "project_e_ev"},
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        proxy = data.get("Image", "")
        if proxy:
            real = _unwrap_ddg_proxy(proxy) if "/iu/?" in proxy else proxy
            if _is_image_url(real):
                return real
        # Some results embed an image in RelatedTopics
        for topic in data.get("RelatedTopics", []):
            if not isinstance(topic, dict):
                continue
            icon_url = (topic.get("Icon") or {}).get("URL", "")
            if icon_url and _is_image_url(icon_url):
                real = _unwrap_ddg_proxy(icon_url) if "/iu/?" in icon_url else icon_url
                if _is_image_url(real):
                    return real
    except Exception:
        pass
    return None


def _get_ddg_vqd(query: str) -> Optional[str]:
    """Fetches the VQD token that DDG requires for image search API calls."""
    try:
        resp = requests.get(
            "https://duckduckgo.com/",
            params={"q": query, "iax": "images", "ia": "images"},
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        # Try response header first (more stable)
        if "X-DuckDuckGo-VQD" in resp.headers:
            return resp.headers["X-DuckDuckGo-VQD"]
        # Fall back to HTML patterns (DDG has changed this format several times)
        for pattern in [
            r'vqd=["\']([\d-]+)["\']',
            r'"vqd":\s*"([^"]+)"',
            r"vqd=([\d-]+)&",
            r"data-vqd=[\"']([\d-]+)[\"']",
        ]:
            m = re.search(pattern, resp.text)
            if m:
                return m.group(1)
    except Exception:
        pass
    return None


def _fetch_ddg_images(query: str) -> Optional[str]:
    """Full DuckDuckGo image search — returns the first suitable result URL."""
    vqd = _get_ddg_vqd(query)
    if not vqd:
        return None
    try:
        resp = requests.get(
            "https://duckduckgo.com/i.js",
            params={"q": query, "vqd": vqd, "o": "json", "p": "1", "f": ",,,,,"},
            headers={**_HEADERS, "Referer": "https://duckduckgo.com/"},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        for item in results[:5]:
            url = item.get("image", "")
            if _is_image_url(url):
                return url
    except Exception:
        pass
    return None


def _fetch_wikipedia_thumbnail(make_name: str, model_name: str) -> Optional[str]:
    """Fetches the Wikipedia article lead thumbnail for the vehicle."""
    article = f"{make_name} {model_name}".replace(" ", "_")
    try:
        resp = requests.get(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(article)}",
            headers={"User-Agent": _HEADERS["User-Agent"]},
            timeout=_TIMEOUT,
        )
        if resp.status_code == 200:
            thumbnail = resp.json().get("thumbnail", {}).get("source")
            if thumbnail:
                return thumbnail
    except Exception:
        pass
    return None


def fetch_web_image(make_name: str, model_name: str) -> Optional[str]:
    """Finds the best available image for a vehicle via web search.

    Tries in order:
    1. DDG Instant Answer (fast, reliable for well-known EVs)
    2. DDG image search (broader coverage)
    3. Wikipedia article thumbnail (final fallback)
    """
    query = f"{make_name} {model_name} electric car"

    url = _fetch_ddg_instant(query)
    if url:
        return url

    time.sleep(0.4)

    url = _fetch_ddg_images(query)
    if url:
        return url

    time.sleep(0.4)

    return _fetch_wikipedia_thumbnail(make_name, model_name)
