from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

from app.models.models import SourceType


@dataclass
class SourceInfo:
    platform_id: str
    name: str
    profile_url: str
    avatar_url: str | None = None
    raw_data: dict = field(default_factory=dict)


@dataclass
class CrawledItem:
    platform_id: str
    title: str
    content_url: str
    published_at: datetime
    thumbnail_url: str | None = None
    raw_data: dict = field(default_factory=dict)


class BaseCrawler(ABC):
    source_type: SourceType

    @abstractmethod
    async def resolve_source(self, url: str) -> SourceInfo:
        raise NotImplementedError

    @abstractmethod
    async def fetch_latest_items(self, external_id: str, limit: int = 20) -> list[CrawledItem]:
        raise NotImplementedError
