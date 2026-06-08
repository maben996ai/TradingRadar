import asyncio
import logging
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.models.models import (
    ContentItem,
    CrawlLogStatus,
    DataSource,
    CrawlLog,
    CalendarEvent,
    FeishuWebhook,
    MacroObservation,
    SourceType,
)
from app.services.calendar.service import refresh_all as refresh_calendar_all
from app.services.crawlers.registry import crawler_registry
from app.services.macro.service import refresh_all as refresh_macro_all
from app.services.notifiers.feishu import FeishuNotifier

logger = logging.getLogger(__name__)

_notifier = FeishuNotifier()

REGULAR_CRAWL_INTERVAL_MINUTES = 30
SOCIAL_MEDIA_CRAWL_INTERVAL_MINUTES = 15
SOCIAL_MEDIA_SOURCE_TYPES = (SourceType.TWITTER,)
# 宏观/日历每天一次，固定在美股收盘+财报落定后：23:00 UTC ≈ 北京 07:00
DAILY_REFRESH_UTC_HOUR = 23


class SchedulerService:
    def __init__(self) -> None:
        self.scheduler = AsyncIOScheduler()
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        self.scheduler.add_job(
            crawl_regular_sources,
            "interval",
            minutes=REGULAR_CRAWL_INTERVAL_MINUTES,
            id="crawl_regular_sources",
            replace_existing=True,
            coalesce=True,
            misfire_grace_time=300,
        )
        self.scheduler.add_job(
            crawl_social_media_sources,
            "interval",
            minutes=SOCIAL_MEDIA_CRAWL_INTERVAL_MINUTES,
            id="crawl_social_media_sources",
            replace_existing=True,
            coalesce=True,
            misfire_grace_time=300,
        )
        self.scheduler.add_job(
            refresh_macro_indicators,
            "cron",
            hour=DAILY_REFRESH_UTC_HOUR,
            minute=0,
            timezone="UTC",
            id="refresh_macro_indicators",
            replace_existing=True,
            coalesce=True,
            misfire_grace_time=3600,
        )
        self.scheduler.add_job(
            refresh_calendar_events,
            "cron",
            hour=DAILY_REFRESH_UTC_HOUR,
            minute=0,
            timezone="UTC",
            id="refresh_calendar_events",
            replace_existing=True,
            coalesce=True,
            misfire_grace_time=3600,
        )
        self.scheduler.start()
        self._started = True
        # 首启若数据为空则立即生成一次（不阻塞启动）
        asyncio.create_task(_initial_macro_refresh())
        asyncio.create_task(_initial_calendar_refresh())

    async def stop(self) -> None:
        if not self._started:
            return
        self.scheduler.shutdown(wait=False)
        self._started = False


FIRST_CRAWL_LIMIT = 30
INCREMENTAL_CRAWL_LIMIT = 2


async def refresh_macro_indicators() -> None:
    """每日刷新宏观指标观测；未配置 FRED_API_KEY 时跳过。"""
    if not get_settings().fred_api_key:
        return
    async with AsyncSessionLocal() as db:
        try:
            inserted = await refresh_macro_all(db)
            logger.info("Macro refresh inserted %d observations", inserted)
        except Exception as exc:
            logger.warning("Macro refresh failed: %s", exc)


async def _initial_macro_refresh() -> None:
    if not get_settings().fred_api_key:
        return
    async with AsyncSessionLocal() as db:
        count = await db.scalar(select(func.count()).select_from(MacroObservation))
    if (count or 0) == 0:
        await refresh_macro_indicators()


async def refresh_calendar_events() -> None:
    """每日刷新财经日历事件（精选种子 / TE / FMP，按可用 key 自动选择）。"""
    async with AsyncSessionLocal() as db:
        try:
            inserted = await refresh_calendar_all(db)
            logger.info("Calendar refresh inserted %d events", inserted)
        except Exception as exc:
            logger.warning("Calendar refresh failed: %s", exc)


async def _initial_calendar_refresh() -> None:
    async with AsyncSessionLocal() as db:
        count = await db.scalar(select(func.count()).select_from(CalendarEvent))
    if (count or 0) == 0:
        await refresh_calendar_events()


async def _get_webhook_urls(user_id: str) -> list[str]:
    async with AsyncSessionLocal() as db:
        rows = await db.scalars(
            select(FeishuWebhook).where(
                FeishuWebhook.user_id == user_id, FeishuWebhook.enabled.is_(True)
            )
        )
        return [r.webhook_url for r in rows]


async def crawl_source(source: DataSource) -> int:
    crawler = crawler_registry.get(source.source_type)

    async with AsyncSessionLocal() as db:
        existing_count = await db.scalar(
            select(func.count())
            .select_from(ContentItem)
            .where(ContentItem.data_source_id == source.id)
        )

    is_first_crawl = (existing_count or 0) == 0
    limit = FIRST_CRAWL_LIMIT if is_first_crawl else INCREMENTAL_CRAWL_LIMIT

    items = await crawler.fetch_latest_items(source.external_id, limit=limit)

    inserted_count = 0
    async with AsyncSessionLocal() as db:
        if not items:
            db.add(
                CrawlLog(
                    data_source_id=source.id,
                    status=CrawlLogStatus.SUCCESS,
                    message=None,
                    items_found=0,
                )
            )
            if is_first_crawl:
                source_row = await db.get(DataSource, source.id)
                if source_row is not None and source_row.initialized_at is None:
                    source_row.initialized_at = datetime.now(UTC)
            await db.commit()
            return 0

        fetched_ids = {item.platform_id for item in items}
        existing_ids = set(
            await db.scalars(
                select(ContentItem.platform_id).where(
                    ContentItem.data_source_id == source.id,
                    ContentItem.platform_id.in_(fetched_ids),
                )
            )
        )

        new_items: list[ContentItem] = []
        for item in items:
            if item.platform_id in existing_ids:
                continue
            new_item = ContentItem(
                data_source_id=source.id,
                platform_id=item.platform_id,
                title=item.title,
                thumbnail_url=item.thumbnail_url,
                content_url=item.content_url,
                published_at=item.published_at,
                raw_data=item.raw_data,
            )
            db.add(new_item)
            new_items.append(new_item)

        # 首次抓取：除最新 1 条外，全部预标为已通知，避免"升级即爆量"
        if is_first_crawl and len(new_items) > 1:
            sorted_new = sorted(new_items, key=lambda v: v.published_at, reverse=True)
            now = datetime.now(UTC)
            for v in sorted_new[1:]:
                v.notified_at = now

        if is_first_crawl:
            source_row = await db.get(DataSource, source.id)
            if source_row is not None and source_row.initialized_at is None:
                source_row.initialized_at = datetime.now(UTC)

        inserted_count = len(new_items)
        db.add(
            CrawlLog(
                data_source_id=source.id,
                status=CrawlLogStatus.SUCCESS,
                message=None,
                items_found=inserted_count,
            )
        )
        await db.commit()

    # 通知阶段：扫描 notified_at IS NULL 的待发内容，任一失败则保持 None 供下次重试
    if not source.notifications_enabled:
        return inserted_count

    webhook_urls = await _get_webhook_urls(source.user_id)
    if not webhook_urls:
        return inserted_count

    async with AsyncSessionLocal() as db:
        pending = list(
            await db.scalars(
                select(ContentItem)
                .where(
                    ContentItem.data_source_id == source.id,
                    ContentItem.notified_at.is_(None),
                )
                .order_by(ContentItem.published_at.desc())
            )
        )

    for item in pending:
        all_ok = True
        for webhook_url in webhook_urls:
            try:
                await _notifier.send_card(
                    webhook_url=webhook_url,
                    title=item.title,
                    creator_name=source.name,
                    platform=source.source_type,
                    content_url=item.content_url,
                    thumbnail_url=item.thumbnail_url,
                    published_at=item.published_at,
                    is_new_creator=is_first_crawl,
                )
            except Exception as exc:
                logger.warning(
                    "Feishu notify failed for content_item=%s webhook=%s: %s",
                    item.id,
                    webhook_url,
                    exc,
                )
                all_ok = False
        if all_ok:
            async with AsyncSessionLocal() as db:
                row = await db.get(ContentItem, item.id)
                if row is not None:
                    row.notified_at = datetime.now(UTC)
                    await db.commit()

    return inserted_count


async def _crawl_sources(source_types: tuple[SourceType, ...]) -> None:
    if not source_types:
        return

    async with AsyncSessionLocal() as db:
        sources = list(
            await db.scalars(select(DataSource).where(DataSource.source_type.in_(source_types)))
        )

    results = await asyncio.gather(*[crawl_source(s) for s in sources], return_exceptions=True)

    failed = [(sources[i], exc) for i, exc in enumerate(results) if isinstance(exc, Exception)]
    if not failed:
        return

    async with AsyncSessionLocal() as db:
        for source, exc in failed:
            db.add(
                CrawlLog(
                    data_source_id=source.id,
                    status=CrawlLogStatus.FAILED,
                    message=str(exc),
                    items_found=0,
                )
            )
        await db.commit()


async def crawl_all_sources() -> None:
    await _crawl_sources(crawler_registry.supported_types())


async def crawl_regular_sources() -> None:
    source_types = tuple(
        source_type
        for source_type in crawler_registry.supported_types()
        if source_type not in SOCIAL_MEDIA_SOURCE_TYPES
    )
    await _crawl_sources(source_types)


async def crawl_social_media_sources() -> None:
    await _crawl_sources(SOCIAL_MEDIA_SOURCE_TYPES)


scheduler_service = SchedulerService()
