from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import settings
from .models import EVDBVehicleRaw
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
            db.add(
                EVDBVehicleRaw(
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
                )
            )
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
            logger.warning('remove_missing requested but no vehicles were fetched; skipping delete step')
        else:
            stale_records = db.execute(
                select(EVDBVehicleRaw).where(EVDBVehicleRaw.source_name == source_name)
            ).scalars()
            for record in stale_records:
                record_key = (record.source_vehicle_id, record.market)
                if record_key not in seen_keys:
                    db.delete(record)
                    stats.deleted += 1

    db.commit()
    logger.info('Sync completed: %s', stats)
    return stats


def list_vehicle_records(db: Session, limit: int = 24, offset: int = 0) -> tuple[list[EVDBVehicleRaw], int, int, int]:
    safe_limit = max(1, min(limit, MAX_LIST_LIMIT))
    safe_offset = max(0, offset)

    total = db.execute(select(func.count()).select_from(EVDBVehicleRaw)).scalar_one()
    records = db.execute(
        select(EVDBVehicleRaw).order_by(EVDBVehicleRaw.updated_at.desc()).limit(safe_limit).offset(safe_offset)
    ).scalars().all()
    return records, total, safe_limit, safe_offset


def get_vehicle_record(db: Session, vehicle_id: int) -> EVDBVehicleRaw | None:
    return db.execute(select(EVDBVehicleRaw).where(EVDBVehicleRaw.id == vehicle_id)).scalar_one_or_none()


def vehicle_summary_dict(record: EVDBVehicleRaw) -> dict[str, Any]:
    return {
        'id': record.id,
        'source_name': record.source_name,
        'source_vehicle_id': record.source_vehicle_id,
        'vehicle_slug': record.vehicle_slug,
        'vehicle_name': record.vehicle_name,
        'market': record.market,
        'raw_source_url': record.raw_source_url,
        'image_url': extract_vehicle_image_url(record.payload),
        'updated_at': record.updated_at,
    }


def vehicle_detail_dict(record: EVDBVehicleRaw) -> dict[str, Any]:
    payload = dict(record.payload) if isinstance(record.payload, dict) else {}
    data = vehicle_summary_dict(record)
    data['payload'] = payload
    return data


def extract_vehicle_image_url(payload: dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return None

    for key in ('image_url', 'image', 'picture', 'photo_url', 'thumbnail_url'):
        candidate = _to_non_empty_str(payload.get(key))
        if candidate:
            return candidate

    for container_key in ('images', 'gallery', 'media'):
        container = payload.get(container_key)
        candidate = _extract_from_container(container)
        if candidate:
            return candidate

    return None


def _extract_from_container(container: Any) -> str | None:
    if isinstance(container, str):
        return _to_non_empty_str(container)
    if isinstance(container, dict):
        for key in ('url', 'src', 'image_url', 'large', 'medium', 'small'):
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
