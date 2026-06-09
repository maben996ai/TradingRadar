from app.models.models import SourceType
from app.services.crawlers.jin10 import Jin10FlashCrawler
from app.services.crawlers.twitter import TwitterCrawler
from app.services.crawlers.youtube import YouTubeCrawler


class CrawlerRegistry:
    def __init__(self) -> None:
        self._crawlers = {
            SourceType.YOUTUBE: YouTubeCrawler(),
            SourceType.TWITTER: TwitterCrawler(),
            SourceType.FINANCE_NEWS: Jin10FlashCrawler(),
        }

    def get(self, source_type: SourceType):
        return self._crawlers[source_type]

    def supported_types(self) -> tuple[SourceType, ...]:
        return tuple(self._crawlers.keys())


crawler_registry = CrawlerRegistry()
