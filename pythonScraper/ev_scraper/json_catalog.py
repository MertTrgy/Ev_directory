"""Normalization helpers for the bundled open-ev-data JSON file."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def get_range_km(vehicle: Dict[str, Any]) -> Optional[float]:
    """Picks the WLTP range when available and otherwise uses the first rating."""
    rated = (vehicle.get("range") or {}).get("rated") or []
    for entry in rated:
        if entry.get("cycle") == "wltp":
            return entry.get("range_km")
    return rated[0].get("range_km") if rated else None


def normalize_vehicle(
    vehicle: Dict[str, Any],
    image_map: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Flattens one raw open-ev-data vehicle into the API response shape."""
    make = (vehicle.get("make") or {}).get("name", "Unknown")
    model = (vehicle.get("model") or {}).get("name", "Unknown")
    trim = (vehicle.get("trim") or {}).get("name")
    year = vehicle.get("year", 0)

    powertrain = vehicle.get("powertrain") or {}
    battery = vehicle.get("battery") or {}
    charging = vehicle.get("charging") or {}
    body = vehicle.get("body") or {}
    performance = vehicle.get("performance") or {}
    availability = vehicle.get("availability") or {}
    sources: List[Dict[str, Any]] = vehicle.get("sources") or []

    range_raw = get_range_km(vehicle)

    slug_make = (vehicle.get("make") or {}).get("slug", make.lower())
    slug_model = (vehicle.get("model") or {}).get("slug", model.lower())
    key = f"{slug_make}|{slug_model}|{year}"

    image_url = (
        image_map[key]
        if image_map and key in image_map
        else f"https://picsum.photos/seed/{slug_make}-{slug_model}/800/400"
    )

    return {
        "brand": make,
        "model": model,
        "trim": trim,
        "year": year,
        "vehicleType": vehicle.get("vehicle_type"),
        "drivetrain": powertrain.get("drivetrain"),
        "rangeKm": int(range_raw) if range_raw is not None else 0,
        "powerKw": powertrain.get("system_power_kw"),
        "batteryKwh": battery.get("pack_capacity_kwh_net") or battery.get("pack_capacity_kwh_gross"),
        "acChargeKw": (charging.get("ac") or {}).get("max_power_kw"),
        "dcChargeKw": (charging.get("dc") or {}).get("max_power_kw"),
        "bodyStyle": body.get("style"),
        "seats": body.get("seats"),
        "acceleration": performance.get("acceleration_0_100_kmh_s"),
        "topSpeedKmh": performance.get("top_speed_kmh"),
        "availabilityStatus": availability.get("status"),
        "imageUrl": image_url,
        "uniqueCode": vehicle.get("unique_code"),
        "primarySourceUrl": next((source.get("url") for source in sources if source.get("url")), None),
        "sourceLinks": [source.get("url") for source in sources if source.get("url")],
        "raw": vehicle,
    }
