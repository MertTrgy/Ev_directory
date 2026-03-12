from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import quote, urlsplit, urlunsplit

import httpx

from .config import settings

logger = logging.getLogger(__name__)


@dataclass
class ProviderVehicle:
    source_vehicle_id: str
    vehicle_slug: str | None
    vehicle_name: str | None
    market: str
    raw_source_url: str | None
    payload_hash: str
    payload: dict[str, Any]


class EVDBProviderError(Exception):
    pass


class EVDBProvider:
    def __init__(self) -> None:
        self.list_url = settings.evdb_data_url
        self.detail_url_template = settings.evdb_vehicle_detail_url_template or self._derive_detail_url_template(
            self.list_url
        )
        self.timeout = settings.evdb_timeout_seconds
        self.requests_per_second = settings.requests_per_second
        self.page_size = max(1, min(settings.evdb_page_size, 100))
        self.market = settings.evdb_market
        self.fetch_vehicle_details = settings.evdb_fetch_vehicle_details

    def _headers(self) -> dict[str, str]:
        headers = {'Accept': 'application/json'}
        if settings.evdb_api_key:
            headers[settings.evdb_api_key_header] = settings.evdb_api_key
        return headers

    async def fetch_vehicles(self) -> list[ProviderVehicle]:
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            summaries = await self._fetch_all_summaries(client)
            return await self._build_provider_vehicles(client, summaries)

    async def _fetch_all_summaries(self, client: httpx.AsyncClient) -> list[dict[str, Any]]:
        page = 1
        summaries: list[dict[str, Any]] = []

        while True:
            data = await self._fetch_json(
                client,
                self.list_url,
                params={'page': page, 'per_page': self.page_size},
            )
            items, total_pages = self._extract_page_items(data)
            if not items:
                break

            summaries.extend(items)

            if total_pages is None or page >= total_pages:
                break

            page += 1

        return summaries

    async def _build_provider_vehicles(
        self,
        client: httpx.AsyncClient,
        items: list[dict[str, Any]],
    ) -> list[ProviderVehicle]:
        vehicles: list[ProviderVehicle] = []

        for item in items:
            source_vehicle_id = self._pick_first_string(
                item,
                ['unique_code', 'id', 'vehicle_id', 'vehicleId', 'uid', 'slug'],
            )
            if not source_vehicle_id:
                source_vehicle_id = self._stable_hash(item)

            detail_payload: dict[str, Any] | None = None
            raw_source_url: str | None = None

            if self.fetch_vehicle_details:
                detail_payload, raw_source_url = await self._fetch_vehicle_detail(client, source_vehicle_id)

            payload = detail_payload or item
            payload_hash = self._stable_hash(payload)
            vehicle_slug = self._resolve_vehicle_slug(payload, item)
            vehicle_name = self._resolve_vehicle_name(payload, item)
            market = self._pick_first_string(item, ['market', 'country', 'region']) or self.market

            vehicles.append(
                ProviderVehicle(
                    source_vehicle_id=source_vehicle_id,
                    vehicle_slug=vehicle_slug,
                    vehicle_name=vehicle_name,
                    market=market,
                    raw_source_url=raw_source_url or self._pick_first_string(item, ['url', 'detail_url', 'detailUrl']),
                    payload_hash=payload_hash,
                    payload=payload,
                )
            )

        return vehicles

    async def _fetch_json(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        try:
            response = await client.get(url, headers=self._headers(), params=params)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise EVDBProviderError(f'Failed request to {url}: {exc}') from exc

        await asyncio.sleep(1 / max(self.requests_per_second, 0.1))
        return response.json()

    async def _fetch_vehicle_detail(
        self,
        client: httpx.AsyncClient,
        unique_code: str,
    ) -> tuple[dict[str, Any] | None, str | None]:
        if not self.detail_url_template:
            return None, None

        encoded_code = quote(unique_code, safe='')
        detail_url = self.detail_url_template.format(unique_code=encoded_code)

        try:
            data = await self._fetch_json(client, detail_url)
        except EVDBProviderError as exc:
            logger.warning('Detail fetch failed for %s: %s', unique_code, exc)
            return None, detail_url

        if isinstance(data, dict):
            data.setdefault('unique_code', unique_code)
            return data, detail_url

        logger.warning('Unexpected detail payload type for %s: %s', unique_code, type(data).__name__)
        return None, detail_url

    def _extract_page_items(self, data: Any) -> tuple[list[dict[str, Any]], int | None]:
        if isinstance(data, dict):
            vehicles = data.get('vehicles')
            if isinstance(vehicles, list):
                total_pages = None
                pagination = data.get('pagination')
                if isinstance(pagination, dict):
                    value = pagination.get('total_pages')
                    if isinstance(value, int) and value > 0:
                        total_pages = value
                return [item for item in vehicles if isinstance(item, dict)], total_pages

        items = self._extract_list(data)
        return [item for item in items if isinstance(item, dict)], None

    def _extract_list(self, data: Any) -> list[Any]:
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ('vehicles', 'data', 'results', 'items', 'makes'):
                value = data.get(key)
                if isinstance(value, list):
                    return value
        raise EVDBProviderError('Could not find a vehicle list in the provider response.')

    @staticmethod
    def _resolve_vehicle_slug(payload: dict[str, Any], summary: dict[str, Any]) -> str | None:
        model_slug = EVDBProvider._pick_nested_string(payload, [('model', 'slug')])
        if model_slug:
            return model_slug
        return EVDBProvider._pick_first_string(summary, ['model_slug', 'slug', 'vehicle_slug', 'vehicleSlug'])

    @staticmethod
    def _resolve_vehicle_name(payload: dict[str, Any], summary: dict[str, Any]) -> str | None:
        model_name = EVDBProvider._pick_nested_string(payload, [('model', 'name')]) or EVDBProvider._pick_first_string(
            summary, ['model_name', 'name']
        )
        trim_name = EVDBProvider._pick_nested_string(payload, [('trim', 'name')]) or EVDBProvider._pick_first_string(
            summary, ['trim_name']
        )
        if model_name and trim_name:
            return f'{model_name} {trim_name}'.strip()
        return model_name or trim_name

    @staticmethod
    def _pick_first_string(item: dict[str, Any], keys: Iterable[str]) -> str | None:
        for key in keys:
            value = item.get(key)
            if value is None:
                continue
            if isinstance(value, (str, int, float)):
                text = str(value).strip()
                if text:
                    return text
        return None

    @staticmethod
    def _pick_nested_string(item: dict[str, Any], paths: Iterable[tuple[str, str]]) -> str | None:
        for root, key in paths:
            value = item.get(root)
            if not isinstance(value, dict):
                continue
            nested = value.get(key)
            if nested is None:
                continue
            text = str(nested).strip()
            if text:
                return text
        return None

    @staticmethod
    def _derive_detail_url_template(list_url: str) -> str | None:
        parts = urlsplit(list_url)
        if not parts.path.endswith('/vehicles/list'):
            return None

        detail_path = f"{parts.path[: -len('/vehicles/list')]}/vehicles/code/{{unique_code}}"
        return urlunsplit((parts.scheme, parts.netloc, detail_path, '', ''))

    @staticmethod
    def _stable_hash(item: Any) -> str:
        payload = json.dumps(item, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()
