"""Background image-enrichment workflow for the open-ev-data dataset."""

from __future__ import annotations

import asyncio
from typing import Dict

from .state import enrichment_progress, reset_enrichment_progress
from .storage import load_enriched, load_vehicle_dataset, now_utc, save_enriched
from .web_image import fetch_web_image


async def run_enrichment_background() -> None:
    reset_enrichment_progress(now_utc())

    try:
        raw = load_vehicle_dataset()
        vehicles = raw.get("vehicles", [])
        enrichment_progress["total"] = len(vehicles)

        enriched: Dict[str, object] = load_enriched()
        image_map = dict(enriched.get("image_map", {}))

        for index, vehicle in enumerate(vehicles):
            if not enrichment_progress["running"]:
                break

            await asyncio.sleep(0)

            try:
                slug_make = (vehicle.get("make") or {}).get("slug", "")
                slug_model = (vehicle.get("model") or {}).get("slug", "")
                make_name = (vehicle.get("make") or {}).get("name", "")
                model_name = (vehicle.get("model") or {}).get("name", "")
                year = vehicle.get("year", 0)
                key = f"{slug_make}|{slug_model}|{year}"

                if key not in image_map:
                    image_url = await asyncio.to_thread(fetch_web_image, make_name, model_name)
                    if image_url:
                        image_map[key] = image_url
                        enrichment_progress["found"] += 1
            except Exception as exc:
                enrichment_progress["lastError"] = str(exc)

            enrichment_progress["processed"] = index + 1

            if (index + 1) % 10 == 0:
                try:
                    enriched["image_map"] = dict(image_map)
                    await asyncio.to_thread(save_enriched, enriched)
                except Exception:
                    pass

        try:
            enriched["image_map"] = dict(image_map)
            await asyncio.to_thread(save_enriched, enriched)
        except Exception as save_exc:
            enrichment_progress["error"] = f"Final save failed: {save_exc}"
    except Exception as exc:
        enrichment_progress["error"] = str(exc)
    finally:
        enrichment_progress["running"] = False
        enrichment_progress["completedAt"] = now_utc()
