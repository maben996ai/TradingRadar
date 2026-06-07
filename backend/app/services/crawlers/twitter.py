import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.models.models import SourceType
from app.services.crawlers.base import BaseCrawler, CrawledVideo, SourceInfo

settings = get_settings()


class TwitterCrawler(BaseCrawler):
    source_type = SourceType.TWITTER
    base_url = "https://api.twitterapi.io"

    async def resolve_source(self, url: str) -> SourceInfo:
        if not settings.twitterapi_io_api_key:
            raise ValueError("TWITTERAPI_IO_API_KEY is required to resolve X sources")

        username = self._extract_username(url)
        if username is None:
            raise ValueError("Unsupported X/Twitter profile URL")

        payload = await self._get_json(
            "/twitter/user/info",
            params={"userName": username},
        )
        if payload.get("status") == "error":
            raise ValueError(payload.get("msg") or "Failed to resolve X/Twitter user")

        user = payload.get("data") or {}
        user_id = user.get("id")
        user_name = user.get("userName") or username
        if not user_id:
            raise ValueError("Failed to resolve X/Twitter user")

        return SourceInfo(
            platform_id=user_id,
            name=user.get("name") or user_name,
            profile_url=user.get("url") or f"https://x.com/{user_name}",
            avatar_url=user.get("profilePicture"),
            raw_data=user,
        )

    async def fetch_latest_videos(self, external_id: str, limit: int = 20) -> list[CrawledVideo]:
        if not settings.twitterapi_io_api_key:
            return []

        payload = await self._get_json(
            "/twitter/user/last_tweets",
            params={
                "userId": external_id,
                "includeReplies": "false",
            },
        )
        if payload.get("status") == "error":
            raise ValueError(payload.get("message") or "Failed to fetch X/Twitter posts")

        results: list[CrawledVideo] = []
        for tweet in (payload.get("tweets") or [])[:limit]:
            tweet_id = tweet.get("id")
            if not tweet_id:
                continue

            text = (tweet.get("text") or "").strip()
            results.append(
                CrawledVideo(
                    platform_video_id=tweet_id,
                    title=text[:500] or tweet_id,
                    video_url=tweet.get("url") or self._tweet_url(tweet),
                    thumbnail_url=self._extract_thumbnail_url(tweet),
                    published_at=self._parse_datetime(tweet.get("createdAt")),
                    raw_data=tweet,
                )
            )
        return results

    async def _get_json(self, path: str, params: dict[str, str]) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{self.base_url}{path}",
                params=params,
                headers={"X-API-Key": settings.twitterapi_io_api_key},
            )
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Unexpected TwitterAPI.io response")
        return payload

    def _extract_username(self, url: str) -> str | None:
        parsed = urlparse(url.strip())
        if parsed.netloc.lower() not in {"twitter.com", "www.twitter.com", "x.com", "www.x.com"}:
            return None
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) != 1:
            return None
        username = parts[0]
        if username.lower() in {"home", "explore", "i", "intent", "notifications", "search"}:
            return None
        if not re.fullmatch(r"[A-Za-z0-9_]{1,15}", username):
            return None
        return username

    def _tweet_url(self, tweet: dict) -> str:
        author = tweet.get("author") or {}
        username = author.get("userName")
        tweet_id = tweet.get("id")
        if username and tweet_id:
            return f"https://x.com/{username}/status/{tweet_id}"
        return f"https://x.com/i/web/status/{tweet_id}"

    def _parse_datetime(self, value: str | None) -> datetime:
        if not value:
            return datetime.now(UTC)
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return datetime.now(UTC)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed

    def _extract_thumbnail_url(self, tweet: dict) -> str | None:
        media_items = []
        for container_key in ("extendedEntities", "extended_entities", "entities"):
            container = tweet.get(container_key) or {}
            media_items.extend(container.get("media") or [])
        media_items.extend(tweet.get("media") or [])
        media_items.extend(tweet.get("mediaDetails") or [])

        for item in media_items:
            if not isinstance(item, dict):
                continue
            for key in ("media_url_https", "media_url", "preview_image_url", "url"):
                value = item.get(key)
                if isinstance(value, str) and value.startswith("http"):
                    return value
        return None
