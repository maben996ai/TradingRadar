import hashlib
from datetime import UTC, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any

from app.core.config import get_settings
from app.models.models import SourceType
from app.services.crawlers.base import BaseCrawler, CrawledItem, SourceInfo
from app.services.jin10.mcp_client import Jin10MCPClient

JIN10_FLASH_EXTERNAL_ID = "jin10_flash"
JIN10_NEWS_EXTERNAL_ID = "jin10_news"
JIN10_CALENDAR_EXTERNAL_ID = "jin10_calendar"
JIN10_NAME = "金十数据"
JIN10_PROFILE_URL = "https://www.jin10.com"
JIN10_CALENDAR_FUTURE_WINDOW = timedelta(days=93)
JIN10_CALENDAR_HISTORY_WINDOW = timedelta(days=365)
JIN10_TIMEZONE = timezone(timedelta(hours=8))


class Jin10FlashCrawler(BaseCrawler):
    source_type = SourceType.FINANCE_NEWS

    async def resolve_source(self, url: str) -> SourceInfo:
        normalized = url.strip().lower()
        if normalized not in {"jin10://flash", "https://www.jin10.com", "https://flash.jin10.com"}:
            raise ValueError("Unsupported Jin10 source URL")
        return SourceInfo(
            platform_id=JIN10_FLASH_EXTERNAL_ID,
            name=JIN10_NAME,
            profile_url=JIN10_PROFILE_URL,
            raw_data={"tool": "list_flash"},
        )

    async def fetch_latest_items(self, external_id: str, limit: int = 20) -> list[CrawledItem]:
        if external_id not in {
            JIN10_FLASH_EXTERNAL_ID,
            JIN10_NEWS_EXTERNAL_ID,
            JIN10_CALENDAR_EXTERNAL_ID,
        }:
            raise ValueError("Unsupported Jin10 finance news source")

        settings = get_settings()
        if not settings.jin10_mcp_bearer_token:
            return []

        async with Jin10MCPClient(
            server_url=settings.jin10_mcp_server_url,
            bearer_token=settings.jin10_mcp_bearer_token,
            protocol_version=settings.jin10_mcp_protocol_version,
        ) as client:
            if external_id == JIN10_FLASH_EXTERNAL_ID:
                items = await self._list_paginated_items(client.list_flash, limit, "list_flash")
                return [
                    self._to_crawled_item(item, category="flash", fallback_url="https://flash.jin10.com")
                    for item in items[:limit]
                ]
            if external_id == JIN10_NEWS_EXTERNAL_ID:
                items = await self._list_paginated_items(client.list_news, limit, "list_news")
                return [
                    self._to_crawled_item(item, category="news", fallback_url=JIN10_PROFILE_URL)
                    for item in items[:limit]
                ]

            payload = await client.list_calendar()
            data = payload.get("data")
            if not isinstance(data, list):
                raise ValueError("Unexpected Jin10 list_calendar response")
            calendar_items = [
                self._to_calendar_item(item)
                for item in data
                if isinstance(item, dict) and self._calendar_item_in_sync_window(item)
            ]
            calendar_items.sort(key=lambda item: item.published_at)
            return calendar_items[:limit]

    async def _list_paginated_items(self, fetch_page, limit: int, tool_name: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        cursor: str | None = None
        while len(items) < limit:
            payload = await fetch_page(cursor=cursor)
            data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
            page_items = data.get("items") if isinstance(data, dict) else None
            if not isinstance(page_items, list):
                raise ValueError(f"Unexpected Jin10 {tool_name} response")
            items.extend(item for item in page_items if isinstance(item, dict))
            if not data.get("has_more"):
                break
            next_cursor = data.get("next_cursor")
            if not isinstance(next_cursor, str) or not next_cursor:
                break
            cursor = next_cursor
        return items

    def _to_crawled_item(
        self,
        item: dict[str, Any],
        category: str,
        fallback_url: str,
    ) -> CrawledItem:
        text = self._first_text(item, "title", "content", "text", "message", "introduction")
        platform_id = self._platform_id(item, text)
        content_url = self._first_text(item, "url", "link") or fallback_url
        published_at = self._parse_datetime(
            self._first_text(item, "time", "pub_time", "created_at", "published_at")
        )
        raw_data = dict(item)
        raw_data.setdefault("text", text)
        raw_data.setdefault("source_name", JIN10_NAME)
        raw_data.setdefault("jin10_category", category)

        return CrawledItem(
            platform_id=platform_id,
            title=text[:500] or platform_id,
            content_url=content_url,
            published_at=published_at,
            raw_data=raw_data,
        )

    def _to_calendar_item(self, item: dict[str, Any]) -> CrawledItem:
        title = self._first_text(item, "title")
        pub_time = self._first_text(item, "pub_time", "time")
        published_at = self._parse_datetime(pub_time)
        platform_id = self._platform_id(item, title)
        raw_data = dict(item)
        raw_data["text"] = self._calendar_text(item)
        raw_data["source_name"] = JIN10_NAME
        raw_data["jin10_category"] = "calendar"
        return CrawledItem(
            platform_id=platform_id,
            title=title[:500] or platform_id,
            content_url=JIN10_PROFILE_URL,
            published_at=published_at,
            raw_data=raw_data,
        )

    def _calendar_text(self, item: dict[str, Any]) -> str:
        title = self._first_text(item, "title")
        parts = [title] if title else []
        for label, key in (
            ("重要性", "star"),
            ("前值", "previous"),
            ("预期", "consensus"),
            ("实际", "actual"),
            ("修正", "revised"),
            ("影响", "affect_txt"),
        ):
            value = self._first_text(item, key)
            if value:
                parts.append(f"{label}: {value}")
        return "\n".join(parts)

    def _calendar_item_in_sync_window(self, item: dict[str, Any]) -> bool:
        pub_time = self._first_text(item, "pub_time", "time")
        published_at = self._parse_datetime(pub_time)
        now = datetime.now(UTC)
        return (
            now - JIN10_CALENDAR_HISTORY_WINDOW
            <= published_at
            <= now + JIN10_CALENDAR_FUTURE_WINDOW
        )

    def _platform_id(self, item: dict[str, Any], text: str) -> str:
        for key in ("id", "flash_id", "news_id"):
            value = item.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        basis = "|".join(
            [
                self._first_text(item, "time", "pub_time", "created_at", "published_at"),
                text,
            ]
        )
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]

    def _first_text(self, item: dict[str, Any], *keys: str) -> str:
        for key in keys:
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if value is not None and not isinstance(value, (dict, list)):
                return str(value).strip()
        return ""

    def _parse_datetime(self, value: str) -> datetime:
        if not value:
            return datetime.now(UTC)
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            try:
                parsed = parsedate_to_datetime(value)
            except (TypeError, ValueError):
                return datetime.now(UTC)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=JIN10_TIMEZONE).astimezone(UTC)
        return parsed.astimezone(UTC)
