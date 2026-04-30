"""Scraper for https://clearwatt.co.uk/directory vehicle pages.

Strategy:
1. Fetch /vehicles-sitemap.xml to get all vehicle page URLs.
2. For each URL, fetch raw HTML and extract the embedded __NEXT_DATA__ JSON
   (Next.js SSR — no JS execution needed).
3. All specs are stored as arrays of {label, value, unit} objects.
   Build a label→value dict then map to our schema.
4. Unit conversions: miles→km, mph→km/h, m→mm, hours→minutes.
"""

from __future__ import annotations

import json
import re
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

SITEMAP_URL   = "https://clearwatt.co.uk/vehicles-sitemap.xml"
MILES_TO_KM   = 1.60934
MPH_TO_KMH    = 1.60934
REQUEST_DELAY = 1.2  # seconds between requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; ProjectE-DataBot/1.0; educational/research use)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
    "Accept-Language": "en-GB,en;q=0.9",
}


# ── Sitemap ───────────────────────────────────────────────────────────────────

def fetch_vehicle_urls() -> List[str]:
    resp = requests.get(SITEMAP_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    root = ET.fromstring(resp.text)
    return [
        loc.text.strip()
        for loc in root.findall(".//sm:loc", ns)
        if loc.text and "/directory/" in loc.text
    ]


# ── Page parsing ──────────────────────────────────────────────────────────────

def _extract_next_data(html: str) -> Optional[Dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    tag = soup.find("script", {"id": "__NEXT_DATA__"})
    if not tag or not tag.string:
        return None
    try:
        return json.loads(tag.string)
    except (json.JSONDecodeError, TypeError):
        return None


def scrape_vehicle_page(url: str) -> Optional[Dict[str, Any]]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            return None
        data = _extract_next_data(resp.text)
        if not data:
            return None
        page_props = data.get("props", {}).get("pageProps", {})
        # clearwatt uses the key "ev" in pageProps
        ev = page_props.get("ev") or page_props.get("vehicle") or page_props.get("car")
        if not ev:
            return None
        return _map_vehicle(ev, url)
    except Exception:
        return None


# ── Label-array helpers ───────────────────────────────────────────────────────

def _label_map(arr: Any) -> Dict[str, str]:
    """Converts [{label, value, unit}] → {label.lower(): value_string}."""
    if not isinstance(arr, list):
        return {}
    result: Dict[str, str] = {}
    for item in arr:
        if not isinstance(item, dict):
            continue
        label = item.get("label", "")
        value = item.get("value")
        if label and value is not None:
            result[label.lower().strip()] = str(value).strip()
    return result


def _get(m: Dict[str, str], *keys: str) -> Optional[str]:
    """Returns first matching value for any of the given label keys."""
    for k in keys:
        v = m.get(k.lower())
        if v is not None and v != "" and v.lower() not in ("n/a", "none", "null", "-"):
            return v
    return None


# ── Unit conversion helpers ───────────────────────────────────────────────────

def _to_km(miles: Any) -> Optional[int]:
    try:
        return round(float(miles) * MILES_TO_KM) if miles is not None else None
    except (TypeError, ValueError):
        return None

def _to_kmh(mph: Any) -> Optional[float]:
    try:
        return round(float(mph) * MPH_TO_KMH, 1) if mph is not None else None
    except (TypeError, ValueError):
        return None

def _m_to_mm(metres: Any) -> Optional[int]:
    """Clearwatt gives dimensions in metres (e.g. 4.7) — convert to mm."""
    try:
        return round(float(metres) * 1000) if metres is not None else None
    except (TypeError, ValueError):
        return None

def _f(v: Any) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None

def _i(v: Any) -> Optional[int]:
    try:
        return int(float(v)) if v is not None else None
    except (TypeError, ValueError):
        return None

def _parse_time_min(s: Any) -> Optional[int]:
    """Parse 'X hours Y minutes' or 'X min' style strings → total minutes."""
    if s is None:
        return None
    text = str(s).lower()
    hours_m = re.search(r"(\d+)\s*hour", text)
    mins_m  = re.search(r"(\d+)\s*min", text)
    total = 0
    if hours_m:
        total += int(hours_m.group(1)) * 60
    if mins_m:
        total += int(mins_m.group(1))
    return total if total > 0 else _i(s)  # fallback: treat as plain number

def _parse_years(s: Any) -> Tuple[Optional[int], Optional[int]]:
    """Parse '2021-2023' or '2023' → (start, end)."""
    if not s:
        return None, None
    text = str(s).strip()
    parts = re.split(r"[-–]", text)
    try:
        start = int(parts[0].strip())
        end   = int(parts[-1].strip()) if len(parts) > 1 else start
        return start, end
    except (ValueError, IndexError):
        return None, None


# ── Mapper ────────────────────────────────────────────────────────────────────

def _map_vehicle(ev: Dict[str, Any], source_url: str) -> Dict[str, Any]:
    # Build label→value maps for each detail array
    batt  = _label_map(ev.get("battery_details"))
    rng   = _label_map(ev.get("range_details"))
    chg   = _label_map(ev.get("charge_details"))    # clearwatt calls it charge_details
    perf  = _label_map(ev.get("performance_details"))
    dim   = _label_map(ev.get("dimensions_details"))
    basic = _label_map(ev.get("basic_details"))

    # ── Identity ──────────────────────────────────────────────────────────────
    brand     = ev.get("make") or _get(basic, "manufacturer") or ""
    model     = ev.get("model") or _get(basic, "model") or ""
    trim      = ev.get("model_version") or _get(basic, "variant") or None
    year      = _i(ev.get("year"))
    body_style = _get(dim, "body style")
    drivetrain = _get(dim, "drivetrain")
    seats     = _i(_get(dim, "number of seats"))

    # ── Production years ──────────────────────────────────────────────────────
    prod_start, prod_end = _parse_years(_get(basic, "years in production"))

    # ── Image ─────────────────────────────────────────────────────────────────
    images = ev.get("images") or []
    image_url = None
    if images and isinstance(images[0], dict):
        image_url = images[0].get("image_url") or images[0].get("url")
    elif images:
        image_url = str(images[0])

    # ── Battery ───────────────────────────────────────────────────────────────
    gross_kwh  = _f(_get(batt, "battery capacity (total)"))
    usable_kwh = _f(_get(batt, "battery capacity (usable)"))
    chemistry  = _get(batt, "battery chemistry")
    voltage_v  = _f(_get(batt, "nominal voltage"))

    # ── Range ─────────────────────────────────────────────────────────────────
    # wltp_lab_range is a dedicated object (in miles)
    wltp_obj   = ev.get("wltp_lab_range") or {}
    wltp_miles = _f(wltp_obj.get("tested_range"))

    # benchmark ranges (in miles)
    bench    = ev.get("benchmark_real_range_new") or {}
    typical  = bench.get("typical") or {}
    real_miles = _f(typical.get("maxValue"))  # use upper end of typical range

    # Seasonal ranges from range_details array (in miles)
    spring_miles = _f(_get(rng, "spring"))
    summer_miles = _f(_get(rng, "summer"))
    autumn_miles = _f(_get(rng, "autumn"))
    winter_miles = _f(_get(rng, "winter"))
    avg_miles    = _f(_get(rng, "average"))

    wltp_km   = _to_km(wltp_miles)
    real_km   = _to_km(real_miles or avg_miles)
    spring_km = _to_km(spring_miles)
    summer_km = _to_km(summer_miles)
    autumn_km = _to_km(autumn_miles)
    winter_km = _to_km(winter_miles)

    # ── Charging ──────────────────────────────────────────────────────────────
    motorway_min  = _parse_time_min(_get(chg, "motorway"))   # 10→80% rapid charge
    dest_min      = _parse_time_min(_get(chg, "destination"))
    home_min      = _parse_time_min(_get(chg, "home"))
    dc_port       = _get(chg, "charging port")
    dc_max_kw     = _f(_get(chg, "dc fast charge max power"))
    ac_max_kw     = _f(_get(chg, "ac slow charge max power"))

    # ── Performance ───────────────────────────────────────────────────────────
    acc_s      = _f(_get(perf, "0-62 mph"))
    top_mph    = _f(_get(perf, "top speed"))
    power_kw   = _f(_get(perf, "total power"))
    power_hp   = _i(_get(perf, "brake horsepower (bhp)"))
    power_ps   = round(power_hp * 1.01387) if power_hp else None
    torque_nm  = _i(_get(perf, "max torque"))

    # ── Dimensions (clearwatt reports in metres, we store mm) ─────────────────
    length_mm = _m_to_mm(_get(dim, "length"))
    width_mm  = _m_to_mm(_get(dim, "width"))
    height_mm = _m_to_mm(_get(dim, "height"))
    cargo_l   = _i(_get(dim, "boot space"))

    # ── Core range for ev_data ────────────────────────────────────────────────
    range_km = wltp_km or real_km or 0

    return {
        # Core
        "brand":               brand.strip(),
        "model":               model.strip(),
        "trim":                trim.strip() if trim else None,
        "year":                year,
        "bodyStyle":           body_style,
        "drivetrain":          drivetrain,
        "seats":               seats,
        "rangeKm":             range_km,
        "batteryKwh":          gross_kwh,
        "powerKw":             power_kw,
        "dcChargeKw":          dc_max_kw,
        "acceleration":        acc_s,
        "productionStartYear": prod_start,
        "productionEndYear":   prod_end,
        "imageUrl":            image_url,
        "source":              "clearwatt",
        "sourceUrl":           source_url,
        # Satellite
        "range": {
            "wltpKm":          wltp_km,
            "realWorldKm":     real_km,
            "cityMildKm":      spring_km,
            "highwayMildKm":   summer_km,
            "combinedMildKm":  autumn_km,
            "cityColdKm":      winter_km,
            "combinedColdKm":  winter_km,
        },
        "battery": {
            "grossKwh":      gross_kwh,
            "usableKwh":     usable_kwh,
            "chemistry":     chemistry,
            "nominalVoltageV": voltage_v,
        },
        "charging": {
            "dcPortType":         dc_port,
            "dcMaxKw":            dc_max_kw,
            "acMaxKw":            ac_max_kw,
            "dc1080Min":          motorway_min,
            "timeDestinationMin": dest_min,
            "timeHomeMin":        home_min,
        },
        "performance": {
            "acceleration0100S": acc_s,   # 0-62mph ≈ 0-100km/h
            "topSpeedKmH":       _to_kmh(top_mph),
            "powerKw":           power_kw,
            "powerHp":           power_hp,
            "powerPs":           power_ps,
            "torqueNm":          torque_nm,
            "drivetrain":        drivetrain,
        },
        "dimensions": {
            "lengthMm":        length_mm,
            "widthMm":         width_mm,
            "heightMm":        height_mm,
            "cargoLStd":       cargo_l,
        },
    }


# ── Full scrape with progress tracking ───────────────────────────────────────

def scrape_all_vehicles(
    progress: Dict[str, Any],
    delay: float = REQUEST_DELAY,
) -> List[Dict[str, Any]]:
    progress.update({
        "running": True,
        "total":   0,
        "done":    0,
        "errors":  0,
    })

    try:
        urls = fetch_vehicle_urls()
    except Exception as exc:
        progress.update({"running": False, "error": str(exc)})
        return []

    progress["total"] = len(urls)
    results: List[Dict[str, Any]] = []

    for i, url in enumerate(urls):
        if not progress.get("running"):
            break  # honour stop/pause request

        vehicle = scrape_vehicle_page(url)
        if vehicle and vehicle.get("brand"):
            results.append(vehicle)
        else:
            progress["errors"] += 1

        progress["done"] = i + 1

        if i < len(urls) - 1:
            time.sleep(delay)

    progress["running"] = False
    return results
