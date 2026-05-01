from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Float, Integer, cast, func, select
from sqlalchemy.orm import Session

from .config import settings
from .models import EVVehicleRaw as EVDBVehicleRaw
from .models import Favorite, User
from .provider import EVDBProvider

logger = logging.getLogger(__name__)
MAX_LIST_LIMIT = 200


@dataclass
class SyncStats:
    fetched: int = 0
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    deleted: int = 0


# ── External API sync ──────────────────────────────────────────────────────────

async def sync_evdb_data(db: Session, remove_missing: bool = False) -> SyncStats:
    provider = EVDBProvider()
    vehicles = await provider.fetch_vehicles()

    stats = SyncStats(fetched=len(vehicles))
    now = datetime.now(timezone.utc)
    source_name = settings.evdb_source_name
    seen_keys: set[tuple[str, str]] = set()

    for vehicle in vehicles:
        key = (vehicle.source_vehicle_id, vehicle.market)
        seen_keys.add(key)

        existing = db.execute(
            select(EVDBVehicleRaw).where(
                EVDBVehicleRaw.source_name == source_name,
                EVDBVehicleRaw.source_vehicle_id == vehicle.source_vehicle_id,
                EVDBVehicleRaw.market == vehicle.market,
            )
        ).scalar_one_or_none()

        if existing is None:
            db.add(EVDBVehicleRaw(
                source_name=source_name,
                source_vehicle_id=vehicle.source_vehicle_id,
                vehicle_slug=vehicle.vehicle_slug,
                vehicle_name=vehicle.vehicle_name,
                market=vehicle.market,
                payload_hash=vehicle.payload_hash,
                payload=vehicle.payload,
                raw_source_url=vehicle.raw_source_url,
                first_seen_at=now,
                last_seen_at=now,
                updated_at=now,
            ))
            stats.inserted += 1
            continue

        if existing.payload_hash != vehicle.payload_hash:
            existing.vehicle_slug = vehicle.vehicle_slug
            existing.vehicle_name = vehicle.vehicle_name
            existing.payload_hash = vehicle.payload_hash
            existing.payload = vehicle.payload
            existing.raw_source_url = vehicle.raw_source_url
            existing.last_seen_at = now
            existing.updated_at = now
            stats.updated += 1
        else:
            existing.last_seen_at = now
            stats.unchanged += 1

    if remove_missing:
        if not seen_keys:
            logger.warning("remove_missing requested but no vehicles were fetched; skipping delete step")
        else:
            stale_records = db.execute(
                select(EVDBVehicleRaw).where(EVDBVehicleRaw.source_name == source_name)
            ).scalars()
            for record in stale_records:
                if (record.source_vehicle_id, record.market) not in seen_keys:
                    db.delete(record)
                    stats.deleted += 1

    db.commit()
    logger.info("Sync completed: %s", stats)
    return stats


# ── Generic scraper-to-DB sync ─────────────────────────────────────────────────

async def sync_vehicles_to_db(
    db: Session,
    vehicles: list[dict[str, Any]],
    source_name: str = "open-ev-data-json",
) -> SyncStats:
    stats = SyncStats(fetched=len(vehicles))
    now = datetime.now(timezone.utc)

    for vehicle in vehicles:
        unique_code = vehicle.get("uniqueCode") or vehicle.get("unique_code")
        brand = vehicle.get("brand", "unknown")
        model = vehicle.get("model", "unknown")
        year = vehicle.get("year", 0)

        if not unique_code:
            unique_code = f"{brand}-{model}-{year}".lower().replace(" ", "-")

        source_vehicle_id = str(unique_code)
        vehicle_name = f"{brand} {model}".strip() or None
        vehicle_slug = f"{brand}-{model}".lower().replace(" ", "-") if brand and model else None
        raw_url = vehicle.get("primarySourceUrl") or vehicle.get("sourceUrl")

        payload_hash = hashlib.sha256(
            json.dumps(vehicle, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest()

        existing = db.execute(
            select(EVDBVehicleRaw).where(
                EVDBVehicleRaw.source_name == source_name,
                EVDBVehicleRaw.source_vehicle_id == source_vehicle_id,
                EVDBVehicleRaw.market == "global",
            )
        ).scalar_one_or_none()

        if existing is None:
            db.add(EVDBVehicleRaw(
                source_name=source_name,
                source_vehicle_id=source_vehicle_id,
                vehicle_slug=vehicle_slug,
                vehicle_name=vehicle_name,
                market="global",
                payload_hash=payload_hash,
                payload=vehicle,
                raw_source_url=raw_url,
                first_seen_at=now,
                last_seen_at=now,
                updated_at=now,
            ))
            stats.inserted += 1
        elif existing.payload_hash != payload_hash:
            existing.vehicle_slug = vehicle_slug
            existing.vehicle_name = vehicle_name
            existing.payload_hash = payload_hash
            existing.payload = vehicle
            existing.raw_source_url = raw_url
            existing.last_seen_at = now
            existing.updated_at = now
            stats.updated += 1
        else:
            existing.last_seen_at = now
            stats.unchanged += 1

    db.commit()
    logger.info("sync_vehicles_to_db(%s) completed: %s", source_name, stats)
    return stats


# ── DB query helpers ───────────────────────────────────────────────────────────

def list_vehicle_records(
    db: Session,
    limit: int = 24,
    offset: int = 0,
    search: str | None = None,
    brand: str | None = None,
    market: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    range_min_km: int | None = None,
    range_max_km: int | None = None,
    body_style: str | None = None,
    drivetrain: str | None = None,
    sort_by: str = "updated",
    order: str = "desc",
) -> tuple[list[EVDBVehicleRaw], int, int, int]:
    safe_limit = max(1, min(limit, MAX_LIST_LIMIT))
    safe_offset = max(0, offset)

    stmt = select(EVDBVehicleRaw)

    if search:
        stmt = stmt.where(EVDBVehicleRaw.vehicle_name.ilike(f"%{search}%"))
    if brand:
        stmt = stmt.where(EVDBVehicleRaw.payload["brand"].astext.ilike(f"%{brand}%"))
    if market:
        stmt = stmt.where(EVDBVehicleRaw.market == market)
    if year_min is not None:
        stmt = stmt.where(cast(EVDBVehicleRaw.payload["year"].astext, Integer) >= year_min)
    if year_max is not None:
        stmt = stmt.where(cast(EVDBVehicleRaw.payload["year"].astext, Integer) <= year_max)
    if range_min_km is not None:
        stmt = stmt.where(cast(EVDBVehicleRaw.payload["rangeKm"].astext, Float) >= range_min_km)
    if range_max_km is not None:
        stmt = stmt.where(cast(EVDBVehicleRaw.payload["rangeKm"].astext, Float) <= range_max_km)
    if body_style:
        stmt = stmt.where(EVDBVehicleRaw.payload["bodyStyle"].astext.ilike(f"%{body_style}%"))
    if drivetrain:
        stmt = stmt.where(EVDBVehicleRaw.payload["drivetrain"].astext.ilike(f"%{drivetrain}%"))

    sort_col: Any
    if sort_by == "name":
        sort_col = EVDBVehicleRaw.vehicle_name
    elif sort_by == "year":
        sort_col = cast(EVDBVehicleRaw.payload["year"].astext, Integer)
    elif sort_by == "range":
        sort_col = cast(EVDBVehicleRaw.payload["rangeKm"].astext, Float)
    elif sort_by == "power":
        sort_col = cast(EVDBVehicleRaw.payload["powerKw"].astext, Float)
    else:
        sort_col = EVDBVehicleRaw.updated_at

    stmt = stmt.order_by(sort_col.asc().nulls_last() if order == "asc" else sort_col.desc().nulls_last())

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    records = db.execute(stmt.limit(safe_limit).offset(safe_offset)).scalars().all()
    return list(records), total, safe_limit, safe_offset


def get_vehicle_record(db: Session, vehicle_id: int) -> EVDBVehicleRaw | None:
    return db.execute(
        select(EVDBVehicleRaw).where(EVDBVehicleRaw.id == vehicle_id)
    ).scalar_one_or_none()


def get_vehicles_by_ids(db: Session, vehicle_ids: list[int]) -> list[EVDBVehicleRaw]:
    records = db.execute(
        select(EVDBVehicleRaw).where(EVDBVehicleRaw.id.in_(vehicle_ids))
    ).scalars().all()
    id_order = {vid: i for i, vid in enumerate(vehicle_ids)}
    return sorted(records, key=lambda r: id_order.get(r.id, 999))


def vehicle_summary_dict(record: EVDBVehicleRaw) -> dict[str, Any]:
    payload = record.payload or {}
    return {
        "id": record.id,
        "source_name": record.source_name,
        "source_vehicle_id": record.source_vehicle_id,
        "vehicle_slug": record.vehicle_slug,
        "vehicle_name": record.vehicle_name,
        "market": record.market,
        "raw_source_url": record.raw_source_url,
        "image_url": extract_vehicle_image_url(payload),
        "updated_at": record.updated_at,
        "year": _safe_int(payload.get("year")),
        "brand": _safe_str(payload.get("brand")),
        "range_km": _safe_int(payload.get("rangeKm")),
        "power_kw": _safe_float(payload.get("powerKw")),
        "battery_kwh": _safe_float(payload.get("batteryKwh")),
    }


def vehicle_detail_dict(record: EVDBVehicleRaw) -> dict[str, Any]:
    data = vehicle_summary_dict(record)
    data["payload"] = dict(record.payload) if isinstance(record.payload, dict) else {}
    return data


# ── User / Auth helpers ────────────────────────────────────────────────────────

def get_user_by_email(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()


def create_user(db: Session, email: str, password_hash: str) -> User:
    user = User(email=email, password_hash=password_hash)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ── Favorites helpers ──────────────────────────────────────────────────────────

def get_user_favorites(db: Session, user_id: int) -> list[EVDBVehicleRaw]:
    return list(db.execute(
        select(EVDBVehicleRaw)
        .join(Favorite, Favorite.vehicle_id == EVDBVehicleRaw.id)
        .where(Favorite.user_id == user_id)
        .order_by(Favorite.created_at.desc())
    ).scalars().all())


def get_user_favorite_ids(db: Session, user_id: int) -> set[int]:
    rows = db.execute(select(Favorite.vehicle_id).where(Favorite.user_id == user_id)).scalars().all()
    return set(rows)


def add_favorite(db: Session, user_id: int, vehicle_id: int) -> Favorite:
    fav = Favorite(user_id=user_id, vehicle_id=vehicle_id)
    db.add(fav)
    db.commit()
    db.refresh(fav)
    return fav


def remove_favorite(db: Session, user_id: int, vehicle_id: int) -> bool:
    fav = db.execute(
        select(Favorite).where(Favorite.user_id == user_id, Favorite.vehicle_id == vehicle_id)
    ).scalar_one_or_none()
    if fav is None:
        return False
    db.delete(fav)
    db.commit()
    return True


# ── Image extraction helpers ───────────────────────────────────────────────────

def extract_vehicle_image_url(payload: dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in ("imageUrl", "image_url", "image", "picture", "photo_url", "thumbnail_url"):
        candidate = _to_non_empty_str(payload.get(key))
        if candidate:
            return candidate
    for container_key in ("images", "gallery", "media"):
        container = payload.get(container_key)
        candidate = _extract_from_container(container)
        if candidate:
            return candidate
    return None


def _extract_from_container(container: Any) -> str | None:
    if isinstance(container, str):
        return _to_non_empty_str(container)
    if isinstance(container, dict):
        for key in ("url", "src", "image_url", "large", "medium", "small"):
            candidate = _to_non_empty_str(container.get(key))
            if candidate:
                return candidate
    if isinstance(container, list):
        for item in container:
            candidate = _extract_from_container(item)
            if candidate:
                return candidate
    return None


def _to_non_empty_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _safe_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _safe_str(value: Any) -> str | None:
    return str(value).strip() if value is not None else None
