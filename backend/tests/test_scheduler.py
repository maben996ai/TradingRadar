from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.models import (
    CrawlLog,
    CrawlLogStatus,
    DataSource,
    FeishuWebhook,
    SourceType,
    User,
    ContentItem,
)
from app.services.crawlers.base import CrawledItem
from app.services.scheduler import SchedulerService, crawl_all_sources, crawl_source


def make_user() -> User:
    return User(email="test@example.com", password_hash="x", display_name="Tester")


def make_source(user_id: str, source_type: SourceType = SourceType.YOUTUBE) -> DataSource:
    return DataSource(
        user_id=user_id,
        source_type=source_type,
        external_id="123456",
        name="Test Source",
        profile_url="https://www.youtube.com/@testchannel",
    )


def make_video(
    platform_id: str = "BV001",
    title: str = "Test Video",
    published_at: datetime | None = None,
) -> CrawledItem:
    return CrawledItem(
        platform_id=platform_id,
        title=title,
        content_url=f"https://www.bilibili.com/video/{platform_id}",
        published_at=published_at or datetime(2024, 1, 1, tzinfo=UTC),
    )


@pytest.fixture
def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class TestSchedulerService:
    async def test_start_is_idempotent(self):
        svc = SchedulerService()
        with (
            patch.object(svc.scheduler, "start") as mock_start,
            patch.object(svc.scheduler, "add_job"),
        ):
            await svc.start()
            await svc.start()
        mock_start.assert_called_once()

    async def test_stop_is_idempotent(self):
        svc = SchedulerService()
        with patch.object(svc.scheduler, "start"), patch.object(svc.scheduler, "add_job"):
            await svc.start()

        with patch.object(svc.scheduler, "shutdown") as mock_shutdown:
            await svc.stop()
            await svc.stop()
        mock_shutdown.assert_called_once()

    async def test_stop_before_start_does_nothing(self):
        svc = SchedulerService()
        with patch.object(svc.scheduler, "shutdown") as mock_shutdown:
            await svc.stop()
        mock_shutdown.assert_not_called()


class TestCrawlSource:
    async def test_new_videos_are_inserted(self, db, session_factory):
        user = make_user()
        db.add(user)
        await db.flush()
        source = make_source(user.id)
        db.add(source)
        await db.commit()

        mock_crawler = AsyncMock()
        mock_crawler.fetch_latest_items = AsyncMock(return_value=[make_video("BV001")])

        with (
            patch("app.services.scheduler.crawler_registry") as mock_registry,
            patch("app.services.scheduler.AsyncSessionLocal", session_factory),
        ):
            mock_registry.get.return_value = mock_crawler
            inserted = await crawl_source(source)

        assert inserted == 1
        async with session_factory() as s:
            videos = list(await s.scalars(select(ContentItem).where(ContentItem.data_source_id == source.id)))
        assert len(videos) == 1
        assert videos[0].platform_id == "BV001"

    async def test_duplicate_videos_are_not_reinserted(self, db, session_factory):
        user = make_user()
        db.add(user)
        await db.flush()
        source = make_source(user.id)
        db.add(source)
        await db.flush()
        existing = ContentItem(
            data_source_id=source.id,
            platform_id="BV001",
            title="Existing",
            content_url="https://www.bilibili.com/video/BV001",
            published_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        db.add(existing)
        await db.commit()

        mock_crawler = AsyncMock()
        mock_crawler.fetch_latest_items = AsyncMock(return_value=[make_video("BV001")])

        with (
            patch("app.services.scheduler.crawler_registry") as mock_registry,
            patch("app.services.scheduler.AsyncSessionLocal", session_factory),
        ):
            mock_registry.get.return_value = mock_crawler
            inserted = await crawl_source(source)

        assert inserted == 0

    async def test_crawl_log_is_created_on_success(self, db, session_factory):
        user = make_user()
        db.add(user)
        await db.flush()
        source = make_source(user.id)
        db.add(source)
        await db.commit()

        mock_crawler = AsyncMock()
        mock_crawler.fetch_latest_items = AsyncMock(return_value=[make_video("BV001")])

        with (
            patch("app.services.scheduler.crawler_registry") as mock_registry,
            patch("app.services.scheduler.AsyncSessionLocal", session_factory),
        ):
            mock_registry.get.return_value = mock_crawler
            await crawl_source(source)

        async with session_factory() as s:
            log = await s.scalar(select(CrawlLog).where(CrawlLog.data_source_id == source.id))
        assert log is not None
        assert log.status == CrawlLogStatus.SUCCESS
        assert log.items_found == 1

    async def test_empty_crawl_creates_log_with_zero_videos(self, db, session_factory):
        user = make_user()
        db.add(user)
        await db.flush()
        source = make_source(user.id)
        db.add(source)
        await db.commit()

        mock_crawler = AsyncMock()
        mock_crawler.fetch_latest_items = AsyncMock(return_value=[])

        with (
            patch("app.services.scheduler.crawler_registry") as mock_registry,
            patch("app.services.scheduler.AsyncSessionLocal", session_factory),
        ):
            mock_registry.get.return_value = mock_crawler
            inserted = await crawl_source(source)

        assert inserted == 0
        async with session_factory() as s:
            log = await s.scalar(select(CrawlLog).where(CrawlLog.data_source_id == source.id))
        assert log.items_found == 0


class TestCrawlSourceDedup:
    async def test_existing_video_fields_are_not_overwritten(self, db, session_factory):
        """已入库视频不应被 crawler 返回的新字段覆盖。"""
        user = make_user()
        db.add(user)
        await db.flush()
        source = make_source(user.id)
        db.add(source)
        await db.flush()
        existing = ContentItem(
            data_source_id=source.id,
            platform_id="BV001",
            title="Original Title",
            thumbnail_url="https://cdn/old.jpg",
            content_url="https://www.bilibili.com/video/BV001",
            published_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        db.add(existing)
        await db.commit()

        mock_crawler = AsyncMock()
        mock_crawler.fetch_latest_items = AsyncMock(
            return_value=[make_video("BV001", title="Updated Title")]
        )

        with (
            patch("app.services.scheduler.crawler_registry") as mock_registry,
            patch("app.services.scheduler.AsyncSessionLocal", session_factory),
        ):
            mock_registry.get.return_value = mock_crawler
            await crawl_source(source)

        async with session_factory() as s:
            row = await s.scalar(select(ContentItem).where(ContentItem.platform_id == "BV001"))
        assert row.title == "Original Title"
        assert row.thumbnail_url == "https://cdn/old.jpg"


class TestCrawlSourceInitialization:
    async def test_first_crawl_sets_source_initialized_at(self, db, session_factory):
        """首次抓取结束后，source.initialized_at 从 None 变为有值。"""
        user = make_user()
        db.add(user)
        await db.flush()
        source = make_source(user.id)
        db.add(source)
        await db.commit()

        async with session_factory() as s:
            row = await s.get(DataSource, source.id)
        assert row.initialized_at is None

        mock_crawler = AsyncMock()
        mock_crawler.fetch_latest_items = AsyncMock(return_value=[make_video("BV001")])

        with (
            patch("app.services.scheduler.crawler_registry") as mock_registry,
            patch("app.services.scheduler.AsyncSessionLocal", session_factory),
            patch("app.services.scheduler._notifier.send_card", new=AsyncMock()),
        ):
            mock_registry.get.return_value = mock_crawler
            await crawl_source(source)

        async with session_factory() as s:
            refreshed = await s.get(DataSource, source.id)
        assert refreshed.initialized_at is not None

    async def test_first_crawl_sets_initialized_at_even_when_no_videos(self, db, session_factory):
        """即使抓取结果为空，也要结束初始化，避免前端一直转圈。"""
        user = make_user()
        db.add(user)
        await db.flush()
        source = make_source(user.id)
        db.add(source)
        await db.commit()

        mock_crawler = AsyncMock()
        mock_crawler.fetch_latest_items = AsyncMock(return_value=[])

        with (
            patch("app.services.scheduler.crawler_registry") as mock_registry,
            patch("app.services.scheduler.AsyncSessionLocal", session_factory),
        ):
            mock_registry.get.return_value = mock_crawler
            await crawl_source(source)

        async with session_factory() as s:
            refreshed = await s.get(DataSource, source.id)
        assert refreshed.initialized_at is not None

    async def test_subsequent_crawl_preserves_initialized_at(self, db, session_factory):
        """再次抓取不应重置 initialized_at。"""
        user = make_user()
        db.add(user)
        await db.flush()
        initialized = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)
        source = make_source(user.id)
        source.initialized_at = initialized
        db.add(source)
        await db.flush()
        existing = ContentItem(
            data_source_id=source.id,
            platform_id="BV001",
            title="Existing",
            content_url="https://www.bilibili.com/video/BV001",
            published_at=datetime(2024, 1, 1, tzinfo=UTC),
            notified_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        db.add(existing)
        await db.commit()

        mock_crawler = AsyncMock()
        mock_crawler.fetch_latest_items = AsyncMock(return_value=[make_video("BV002")])

        with (
            patch("app.services.scheduler.crawler_registry") as mock_registry,
            patch("app.services.scheduler.AsyncSessionLocal", session_factory),
            patch("app.services.scheduler._notifier.send_card", new=AsyncMock()),
        ):
            mock_registry.get.return_value = mock_crawler
            await crawl_source(source)

        async with session_factory() as s:
            refreshed = await s.get(DataSource, source.id)
        assert refreshed.initialized_at is not None
        assert refreshed.initialized_at.replace(tzinfo=UTC) == initialized


class TestCrawlSourceNotifications:
    async def test_first_crawl_only_sends_latest_video_once(self, db, session_factory):
        """首次抓取多条内容时，只发送最新 1 条通知。"""
        user = make_user()
        db.add(user)
        await db.flush()
        source = make_source(user.id)
        db.add(source)
        db.add(
            FeishuWebhook(
                user_id=user.id,
                name="test",
                webhook_url="https://open.feishu.cn/x",
                enabled=True,
            )
        )
        await db.commit()

        base = datetime(2024, 6, 1, tzinfo=UTC)
        crawled = [
            make_video("BV003", title="newest", published_at=base + timedelta(hours=2)),
            make_video("BV002", title="middle", published_at=base + timedelta(hours=1)),
            make_video("BV001", title="oldest", published_at=base),
        ]
        mock_crawler = AsyncMock()
        mock_crawler.fetch_latest_items = AsyncMock(return_value=crawled)

        with (
            patch("app.services.scheduler.crawler_registry") as mock_registry,
            patch("app.services.scheduler.AsyncSessionLocal", session_factory),
            patch("app.services.scheduler._notifier.send_card", new=AsyncMock()) as mock_send,
        ):
            mock_registry.get.return_value = mock_crawler
            await crawl_source(source)

        mock_send.assert_awaited_once()
        _, kwargs = mock_send.await_args
        assert kwargs["title"] == "newest"
        assert kwargs["content_url"].endswith("BV003")
        assert kwargs["is_new_creator"] is True

    async def test_first_crawl_premarks_older_videos_as_notified(self, db, session_factory):
        """首次抓取 3 条 → 除最新 1 条外 notified_at 被预填。"""
        user = make_user()
        db.add(user)
        await db.flush()
        source = make_source(user.id)
        db.add(source)
        await db.commit()

        base = datetime(2024, 6, 1, tzinfo=UTC)
        crawled = [
            make_video("BV003", title="newest", published_at=base + timedelta(hours=2)),
            make_video("BV002", title="middle", published_at=base + timedelta(hours=1)),
            make_video("BV001", title="oldest", published_at=base),
        ]
        mock_crawler = AsyncMock()
        mock_crawler.fetch_latest_items = AsyncMock(return_value=crawled)

        with (
            patch("app.services.scheduler.crawler_registry") as mock_registry,
            patch("app.services.scheduler.AsyncSessionLocal", session_factory),
            patch("app.services.scheduler._notifier.send_card", new=AsyncMock()),
        ):
            mock_registry.get.return_value = mock_crawler
            await crawl_source(source)

        async with session_factory() as s:
            rows = list(
                await s.scalars(
                    select(ContentItem)
                    .where(ContentItem.data_source_id == source.id)
                    .order_by(ContentItem.published_at.desc())
                )
            )
        assert len(rows) == 3
        assert rows[1].notified_at is not None
        assert rows[2].notified_at is not None

    async def test_successful_notification_sets_notified_at(self, db, session_factory):
        """单 webhook 成功 → notified_at 被写入。"""
        user = make_user()
        db.add(user)
        await db.flush()
        source = make_source(user.id)
        db.add(source)
        db.add(
            FeishuWebhook(
                user_id=user.id,
                name="test",
                webhook_url="https://open.feishu.cn/x",
                enabled=True,
            )
        )
        await db.commit()

        mock_crawler = AsyncMock()
        mock_crawler.fetch_latest_items = AsyncMock(return_value=[make_video("BV001")])

        with (
            patch("app.services.scheduler.crawler_registry") as mock_registry,
            patch("app.services.scheduler.AsyncSessionLocal", session_factory),
            patch("app.services.scheduler._notifier.send_card", new=AsyncMock()) as mock_send,
        ):
            mock_registry.get.return_value = mock_crawler
            await crawl_source(source)

        mock_send.assert_awaited()
        async with session_factory() as s:
            row = await s.scalar(select(ContentItem).where(ContentItem.platform_id == "BV001"))
        assert row.notified_at is not None

    async def test_failed_notification_leaves_notified_at_null(self, db, session_factory):
        """webhook 失败 → notified_at 保持 None，下次 tick 可重试。"""
        user = make_user()
        db.add(user)
        await db.flush()
        source = make_source(user.id)
        db.add(source)
        db.add(
            FeishuWebhook(
                user_id=user.id,
                name="test",
                webhook_url="https://open.feishu.cn/x",
                enabled=True,
            )
        )
        await db.commit()

        mock_crawler = AsyncMock()
        mock_crawler.fetch_latest_items = AsyncMock(return_value=[make_video("BV001")])

        with (
            patch("app.services.scheduler.crawler_registry") as mock_registry,
            patch("app.services.scheduler.AsyncSessionLocal", session_factory),
            patch(
                "app.services.scheduler._notifier.send_card",
                new=AsyncMock(side_effect=RuntimeError("boom")),
            ),
        ):
            mock_registry.get.return_value = mock_crawler
            await crawl_source(source)

        async with session_factory() as s:
            row = await s.scalar(select(ContentItem).where(ContentItem.platform_id == "BV001"))
        assert row.notified_at is None

    async def test_retry_succeeds_after_previous_failure(self, db, session_factory):
        """首次失败后再次 tick：不再抓取新视频，但会重发之前未通知的。"""
        user = make_user()
        db.add(user)
        await db.flush()
        source = make_source(user.id)
        db.add(source)
        await db.flush()
        db.add(
            FeishuWebhook(
                user_id=user.id,
                name="test",
                webhook_url="https://open.feishu.cn/x",
                enabled=True,
            )
        )
        existing = ContentItem(
            data_source_id=source.id,
            platform_id="BV001",
            title="pending",
            content_url="https://www.bilibili.com/video/BV001",
            published_at=datetime(2024, 6, 1, tzinfo=UTC),
            notified_at=None,
        )
        db.add(existing)
        await db.commit()

        mock_crawler = AsyncMock()
        mock_crawler.fetch_latest_items = AsyncMock(
            return_value=[make_video("BV001", title="pending")]
        )

        with (
            patch("app.services.scheduler.crawler_registry") as mock_registry,
            patch("app.services.scheduler.AsyncSessionLocal", session_factory),
            patch("app.services.scheduler._notifier.send_card", new=AsyncMock()) as mock_send,
        ):
            mock_registry.get.return_value = mock_crawler
            await crawl_source(source)

        mock_send.assert_awaited()
        async with session_factory() as s:
            row = await s.scalar(select(ContentItem).where(ContentItem.platform_id == "BV001"))
        assert row.notified_at is not None


class TestCrawlAllSources:
    async def test_failed_crawl_writes_failed_log(self, db, session_factory):
        user = make_user()
        db.add(user)
        await db.flush()
        source = make_source(user.id)
        db.add(source)
        await db.commit()

        async def _fake_crawl_source(s):
            raise RuntimeError("API timeout")

        with (
            patch("app.services.scheduler.AsyncSessionLocal", session_factory),
            patch("app.services.scheduler.crawl_source", side_effect=_fake_crawl_source),
        ):
            await crawl_all_sources()

        async with session_factory() as s:
            log = await s.scalar(select(CrawlLog).where(CrawlLog.data_source_id == source.id))
        assert log.status == CrawlLogStatus.FAILED
        assert "API timeout" in log.message


class TestRunInitialCrawl:
    async def test_failure_records_failed_log(self, db, session_factory):
        """首次抓取失败时应写入 FAILED 日志，避免信源一直停留在「初始化中」。"""
        from app.api.data_sources import _run_initial_crawl

        user = make_user()
        db.add(user)
        await db.flush()
        source = make_source(user.id)
        db.add(source)
        await db.commit()

        with (
            patch("app.api.data_sources.AsyncSessionLocal", session_factory),
            patch(
                "app.api.data_sources.crawl_source",
                new=AsyncMock(side_effect=RuntimeError("429 Too Many Requests")),
            ),
        ):
            await _run_initial_crawl(source.id)

        async with session_factory() as s:
            log = await s.scalar(select(CrawlLog).where(CrawlLog.data_source_id == source.id))
        assert log is not None
        assert log.status == CrawlLogStatus.FAILED
        assert "429" in (log.message or "")
        assert log.items_found == 0
