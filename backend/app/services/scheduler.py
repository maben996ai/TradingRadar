import asyncio
import logging
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.models.models import CrawlLogStatus, DataSource, CrawlLog, FeishuWebhook, Video
from app.services.crawlers.registry import crawler_registry
from app.services.notifiers.feishu import FeishuNotifier

logger = logging.getLogger(__name__)

_notifier = FeishuNotifier()


class SchedulerService:
    def __init__(self) -> None:
        self.scheduler = AsyncIOScheduler()
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        self.scheduler.add_job(
            crawl_all_sources,
            "interval",
            minutes=30,
            id="crawl_all_sources",
            replace_existing=True,
            coalesce=True,
            misfire_grace_time=300,
        )
        self.scheduler.start()
        self._started = True

    async def stop(self) -> None:
        if not self._started:
            return
        self.scheduler.shutdown(wait=False)
        self._started = False


FIRST_CRAWL_LIMIT = 30
INCREMENTAL_CRAWL_LIMIT = 2


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
            select(func.count()).select_from(Video).where(Video.data_source_id == source.id)
        )

    is_first_crawl = (existing_count or 0) == 0
    limit = FIRST_CRAWL_LIMIT if is_first_crawl else INCREMENTAL_CRAWL_LIMIT

    videos = await crawler.fetch_latest_videos(source.external_id, limit=limit)

    inserted_count = 0
    async with AsyncSessionLocal() as db:
        if not videos:
            db.add(
                CrawlLog(
                    data_source_id=source.id,
                    status=CrawlLogStatus.SUCCESS,
                    message=None,
                    videos_found=0,
                )
            )
            if is_first_crawl:
                source_row = await db.get(DataSource, source.id)
                if source_row is not None and source_row.initialized_at is None:
                    source_row.initialized_at = datetime.now(UTC)
            await db.commit()
            return 0

        fetched_ids = {v.platform_video_id for v in videos}
        existing_ids = set(
            await db.scalars(
                select(Video.platform_video_id).where(
                    Video.data_source_id == source.id,
                    Video.platform_video_id.in_(fetched_ids),
                )
            )
        )

        new_videos: list[Video] = []
        for video in videos:
            if video.platform_video_id in existing_ids:
                continue
            new_video = Video(
                data_source_id=source.id,
                platform_video_id=video.platform_video_id,
                title=video.title,
                thumbnail_url=video.thumbnail_url,
                video_url=video.video_url,
                published_at=video.published_at,
                raw_data=video.raw_data,
            )
            db.add(new_video)
            new_videos.append(new_video)

        # 首次抓取：除最新 1 条外，全部预标为已通知，避免"升级即爆量"
        if is_first_crawl and len(new_videos) > 1:
            sorted_new = sorted(new_videos, key=lambda v: v.published_at, reverse=True)
            now = datetime.now(UTC)
            for v in sorted_new[1:]:
                v.notified_at = now

        if is_first_crawl:
            source_row = await db.get(DataSource, source.id)
            if source_row is not None and source_row.initialized_at is None:
                source_row.initialized_at = datetime.now(UTC)

        inserted_count = len(new_videos)
        db.add(
            CrawlLog(
                data_source_id=source.id,
                status=CrawlLogStatus.SUCCESS,
                message=None,
                videos_found=inserted_count,
            )
        )
        await db.commit()

    # 通知阶段：扫描 notified_at IS NULL 的待发视频，任一失败则保持 None 供下次重试
    if not source.notifications_enabled:
        return inserted_count

    webhook_urls = await _get_webhook_urls(source.user_id)
    if not webhook_urls:
        return inserted_count

    async with AsyncSessionLocal() as db:
        pending = list(
            await db.scalars(
                select(Video)
                .where(Video.data_source_id == source.id, Video.notified_at.is_(None))
                .order_by(Video.published_at.desc())
            )
        )

    for video in pending:
        all_ok = True
        for webhook_url in webhook_urls:
            try:
                await _notifier.send_card(
                    webhook_url=webhook_url,
                    title=video.title,
                    creator_name=source.name,
                    platform=source.source_type,
                    video_url=video.video_url,
                    thumbnail_url=video.thumbnail_url,
                    published_at=video.published_at,
                    is_new_creator=is_first_crawl,
                )
            except Exception as exc:
                logger.warning(
                    "Feishu notify failed for video=%s webhook=%s: %s",
                    video.id,
                    webhook_url,
                    exc,
                )
                all_ok = False
        if all_ok:
            async with AsyncSessionLocal() as db:
                row = await db.get(Video, video.id)
                if row is not None:
                    row.notified_at = datetime.now(UTC)
                    await db.commit()

    return inserted_count


async def crawl_all_sources() -> None:
    async with AsyncSessionLocal() as db:
        sources = list(await db.scalars(
            select(DataSource).where(
                DataSource.source_type.in_(crawler_registry.supported_types())
            )
        ))

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
                    videos_found=0,
                )
            )
        await db.commit()


scheduler_service = SchedulerService()
