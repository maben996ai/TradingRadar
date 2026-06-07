import re

from app.models.models import SourceType
from app.services.crawlers.base import SourceInfo
from app.services.crawlers.registry import crawler_registry

SOURCE_PATTERNS: dict[SourceType, tuple[str, ...]] = {
    SourceType.YOUTUBE: (
        r"https?://(?:www\.)?youtube\.com/channel/[\w-]+",
        r"https?://(?:www\.)?youtube\.com/@[\w.-]+",
    ),
    SourceType.TWITTER: (
        r"https?://(?:www\.)?(?:twitter\.com|x\.com)/[A-Za-z0-9_]+/?(?:\?.*)?$",
    ),
}


async def resolve_source(url: str) -> tuple[SourceType, SourceInfo]:
    normalized_url = url.strip()
    for source_type, patterns in SOURCE_PATTERNS.items():
        if any(re.search(pattern, normalized_url, flags=re.IGNORECASE) for pattern in patterns):
            crawler = crawler_registry.get(source_type)
            source = await crawler.resolve_source(normalized_url)
            return source_type, source

    raise ValueError("Unsupported source URL")
