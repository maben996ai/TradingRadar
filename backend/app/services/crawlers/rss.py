"""RSS/Atom 信源采集器。external_id 即订阅源 URL，feedparser 解析后产出 CrawledItem。"""

import hashlib
from datetime import UTC, datetime
from time import mktime
from urllib.parse import urlparse

import feedparser
import httpx

from app.models.models import SourceType
from app.services.crawlers.base import BaseCrawler, CrawledItem, SourceInfo

REQUEST_TIMEOUT = 25.0
USER_AGENT = "Mozilla/5.0 (compatible; TradingRadar/1.0)"
# 摘要短于该阈值时去原文页抓全文（多数 feed 只给几十字预告，无法支撑按公司名检索）
FULLTEXT_THRESHOLD = 500
FULLTEXT_MAX_CHARS = 20000


class RSSCrawler(BaseCrawler):
    source_type = SourceType.RSS

    async def _fetch_feed(self, url: str):
        """异步拉取后再解析（feedparser.parse(url) 是同步网络请求，会阻塞事件循环）。"""
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        return feedparser.parse(resp.content)

    async def resolve_source(self, url: str) -> SourceInfo:
        normalized = url.strip()
        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Unsupported RSS feed URL")

        feed = await self._fetch_feed(normalized)
        if feed.bozo and not feed.entries:
            raise ValueError(f"Failed to parse RSS feed: {normalized}")

        title = (feed.feed.get("title") or parsed.netloc).strip()
        site_url = feed.feed.get("link") or normalized
        return SourceInfo(
            platform_id=normalized,
            name=title,
            profile_url=site_url,
            raw_data={"feed_title": title},
        )

    async def fetch_latest_items(self, external_id: str, limit: int = 20) -> list[CrawledItem]:
        feed = await self._fetch_feed(external_id)
        if feed.bozo and not feed.entries:
            raise ValueError(f"Failed to parse RSS feed: {external_id}")

        results: list[CrawledItem] = []
        for entry in feed.entries[:limit]:
            title = (entry.get("title") or "").strip()
            link = (entry.get("link") or external_id).strip()
            summary = self._extract_summary(entry)
            if len(summary) < FULLTEXT_THRESHOLD and link.startswith("http"):
                summary = await self._fetch_fulltext(link) or summary
            platform_id = self._platform_id(entry, link, title)
            raw_data = {
                "title": title,
                "text": summary,
                "link": link,
                "feed_url": external_id,
            }
            results.append(
                CrawledItem(
                    platform_id=platform_id,
                    title=(title or summary[:120] or platform_id)[:500],
                    content_url=link,
                    published_at=self._parse_datetime(entry),
                    raw_data=raw_data,
                )
            )
        return results

    async def _fetch_fulltext(self, url: str) -> str:
        """抓取文章页正文（剥 HTML），失败时返回空串回退到原摘要。"""
        try:
            async with httpx.AsyncClient(
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                content_type = resp.headers.get("content-type", "")
                if "html" not in content_type and "xml" not in content_type:
                    return ""  # PDF/二进制等不当正文
                html = resp.text
        except httpx.HTTPError:
            return ""
        import re

        html = re.sub(r"(?is)<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ", html)
        text = re.sub(r"<[^>]+>", " ", html)
        # 控制字符（含 \x00）会破坏 JSON 落库，一并清掉
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:FULLTEXT_MAX_CHARS]

    def _extract_summary(self, entry: dict) -> str:
        for key in ("summary", "description"):
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                return self._strip_html(value).strip()
        content = entry.get("content")
        if isinstance(content, list) and content:
            value = content[0].get("value")
            if isinstance(value, str):
                return self._strip_html(value).strip()
        return ""

    def _strip_html(self, text: str) -> str:
        import re

        return re.sub(r"<[^>]+>", "", text)

    def _platform_id(self, entry: dict, link: str, title: str) -> str:
        guid = entry.get("id") or entry.get("guid")
        if isinstance(guid, str) and guid.strip():
            return guid.strip()[:255]
        basis = f"{link}|{title}"
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]

    def _parse_datetime(self, entry: dict) -> datetime:
        for key in ("published_parsed", "updated_parsed"):
            parsed = entry.get(key)
            if parsed:
                try:
                    return datetime.fromtimestamp(mktime(parsed), tz=UTC)
                except (OverflowError, ValueError, TypeError):
                    continue
        return datetime.now(UTC)
