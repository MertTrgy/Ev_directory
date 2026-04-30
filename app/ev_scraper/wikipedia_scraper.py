"""Legacy Wikipedia table scraper kept for the original sync workflow."""

from __future__ import annotations

import datetime as dt
import re
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from .config import SOURCE_URL, USER_AGENT


def normalize_year(value: str) -> int:
    match = re.search(r"(19|20)\d{2}", value)
    if not match:
        return dt.datetime.now(dt.timezone.utc).year
    return int(match.group(0))


def extract_headers(table) -> List[str]:
    return [header.get_text(" ", strip=True).lower() for header in table.select("tr th")]


def find_index(headers: List[str], candidates: List[str]) -> int:
    for index, header in enumerate(headers):
        for candidate in candidates:
            if candidate in header:
                return index
    return -1


def split_brand_model(vehicle: str, manufacturer: Optional[str]) -> Tuple[str, str]:
    clean_vehicle = re.sub(r"\[[^\]]+\]", "", vehicle).strip()
    clean_maker = re.sub(r"\[[^\]]+\]", "", (manufacturer or "")).strip()

    if clean_maker:
        if clean_vehicle.lower().startswith(clean_maker.lower()):
            model = clean_vehicle[len(clean_maker):].strip(" -")
            return clean_maker, model or clean_vehicle
        return clean_maker, clean_vehicle

    parts = clean_vehicle.split(" ", 1)
    return (parts[0], parts[0]) if len(parts) == 1 else (parts[0], parts[1])


def to_item(brand: str, model: str, year: int) -> Dict[str, object]:
    seed = requests.utils.quote(f"{brand}-{model}", safe="")
    return {
        "brand": brand,
        "model": model,
        "year": year,
        "rangeKm": 0,
        "priceUsd": None,
        "drivetrain": None,
        "imageUrl": f"https://picsum.photos/seed/{seed}/800/400",
    }


def scrape_vehicles() -> List[Dict[str, object]]:
    try:
        response = requests.get(SOURCE_URL, timeout=30, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Failed to fetch Wikipedia source: {exc}") from exc

    soup = BeautifulSoup(response.text, "lxml")
    items: Dict[str, Dict[str, object]] = {}

    for table in soup.select("table.wikitable"):
        headers = extract_headers(table)
        name_index = find_index(headers, ["vehicle", "model", "car"])
        maker_index = find_index(headers, ["manufacturer", "maker", "automaker"])
        year_index = find_index(headers, ["launch", "introduced", "year", "first sold"])

        if name_index < 0:
            continue

        for row in table.select("tr")[1:]:
            cells = row.select("td")
            if not cells or name_index >= len(cells):
                continue

            vehicle_name = cells[name_index].get_text(" ", strip=True)
            if not vehicle_name:
                continue

            manufacturer = (
                cells[maker_index].get_text(" ", strip=True) if 0 <= maker_index < len(cells) else None
            )
            launch_text = cells[year_index].get_text(" ", strip=True) if 0 <= year_index < len(cells) else ""

            brand, model = split_brand_model(vehicle_name, manufacturer)
            year = normalize_year(launch_text)

            if brand and model:
                key = f"{brand.lower()}|{model.lower()}|{year}"
                items[key] = to_item(brand, model, year)

    if not items:
        raise RuntimeError("No EV data rows scraped from source.")

    return sorted(items.values(), key=lambda item: (item["brand"], item["model"], item["year"]))
