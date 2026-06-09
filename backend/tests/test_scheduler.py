from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.models import (
    ContentItem,
    CrawlLog,
    CrawlLogStatus,
    DataSource,
    FeishuWebhook,
    SourceType,
    User,
)
from app.services.crawlers.base import CrawledItem
from app.services.scheduler import (
    SchedulerService,
    crawl_all_sources,
    crawl_finance_news_sources,
    crawl_jin10_calendar_sources,
    crawl_jin10_flash_sources,
    crawl_jin10_news_sources,
    crawl_regular_sources,
    crawl_social_media_sources,
    crawl_source,
    ensure_builtin_finance_news_sources,
    prune_jin10_calendar_history,
    refresh_calendar_events,
    refresh_macro_indicators,
)


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
    platform_id: str = "VID001",
    title: str = "Test Video",
    published_at: datetime | None = None,
) -> CrawledItem:
    return CrawledItem(
        platform_id=platform_id,
        title=title,
        content_url=f"https://www.youtube.com/watch?v={platform_id}",
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

    async def test_start_registers_regular_and_social_media_jobs(self):
        svc = SchedulerService()
        with (
            patch.object(svc.scheduler, "start"),
            patch.object(svc.scheduler, "add_job") as mock_add_job,
        ):
            await svc.start()

        jobs = {
            call.args[0]: {
                "trigger": call.args[1],
                "minutes": call.kwargs.get("minutes"),
                "hour": call.kwargs.get("hour"),
                "id": call.kwargs["id"],
            }
            for call in mock_add_job.call_args_list
        }
        assert jobs[crawl_regular_sources] == {
            "trigger": "interval",
            "minutes": 30,
            "hour": None,
            "id": "crawl_regular_sources",
        }
        assert jobs[crawl_social_media_sources] == {
            "trigger": "interval",
            "minutes": 15,
            "hour": None,
            "id": "crawl_social_media_sources",
        }
        assert jobs[crawl_jin10_flash_sources] == {
            "trigger": "interval",
            "minutes": 5,
            "hour": None,
            "id": "crawl_jin10_flash_sources",
        }
        assert jobs[crawl_jin10_news_sources] == {
            "trigger": "interval",
            "minutes": 60,
            "hour": None,
            "id": "crawl_jin10_news_sources",
        }
        assert jobs[crawl_jin10_calendar_sources] == {
            "trigger": "cron",
            "minutes": None,
            "hour": 23,
            "id": "crawl_jin10_calendar_sources",
        }
        # 宏观/日历改为每日固定 23:00 UTC 的 cron
        assert jobs[refresh_macro_indicators] == {
            "trigger": "cron",
            "minutes": None,
            "hour": 23,
            "id": "refresh_macro_indicators",
        }
        assert jobs[refresh_calendar_events] == {
            "trigger": "cron",
            "minutes": None,
            "hour": 23,
            "id": "refresh_calendar_events",
        }

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
        mock_crawler.fetch_latest_items = AsyncMock(return_value=[make_video("VID001")])

        with (
            patch("app.services.scheduler.crawler_registry") as mock_registry,
            patch("app.services.scheduler.AsyncSessionLocal", session_factory),
        ):
            mock_registry.get.return_value = mock_crawler
            inserted = await crawl_source(source)

        assert inserted == 1
        async with session_factory() as s:
            videos = list(
                await s.scalars(select(ContentItem).where(ContentItem.data_source_id == source.id))
            )
        assert len(videos) == 1
        assert videos[0].platform_id == "VID001"

    async def test_duplicate_videos_are_not_reinserted(self, db, session_factory):
        user = make_user()
        db.add(user)
        await db.flush()
        source = make_source(user.id)
        db.add(source)
        await db.flush()
        existing = ContentItem(
            data_source_id=source.id,
            platform_id="VID001",
            title="Existing",
            content_url="https://www.youtube.com/watch?v=VID001",
            published_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        db.add(existing)
        await db.commit()

        mock_crawler = AsyncMock()
        mock_crawler.fetch_latest_items = AsyncMock(return_value=[make_video("VID001")])

        with (
            patch("app.services.scheduler.crawler_registry") as mock_registry,
            patch("app.services.scheduler.AsyncSessionLocal", session_factory),
        ):
            mock_registry.get.return_value = mock_crawler
            inserted = await crawl_source(source)

        assert inserted == 0

    async def test_finance_news_crawl_uses_high_frequency_limit(self, db, session_factory):
        user = make_user()
        db.add(user)
        await db.flush()
        source = make_source(user.id, SourceType.FINANCE_NEWS)
        source.external_id = "jin10_flash"
        db.add(source)
        await db.flush()
        db.add(
            ContentItem(
                data_source_id=source.id,
                platform_id="existing",
                title="Existing",
                content_url="https://www.jin10.com",
                published_at=datetime(2024, 1, 1, tzinfo=UTC),
            )
        )
        await db.commit()

        mock_crawler = AsyncMock()
        mock_crawler.fetch_latest_items = AsyncMock(return_value=[])

        with (
            patch("app.services.scheduler.crawler_registry") as mock_registry,
            patch("app.services.scheduler.AsyncSessionLocal", session_factory),
        ):
            mock_registry.get.return_value = mock_crawler
            await crawl_source(source)

        mock_crawler.fetch_latest_items.assert_awaited_once_with("jin10_flash", limit=30)

    async def test_jin10_calendar_crawl_uses_three_month_window_limit(self, db, session_factory):
        user = make_user()
        db.add(user)
        await db.flush()
        source = make_source(user.id, SourceType.FINANCE_NEWS)
        source.external_id = "jin10_calendar"
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

        mock_crawler.fetch_latest_items.assert_awaited_once_with("jin10_calendar", limit=1000)

    async def test_prune_jin10_calendar_history_removes_items_older_than_one_year(
        self, db, session_factory
    ):
        user = make_user()
        db.add(user)
        await db.flush()
        source = make_source(user.id, SourceType.FINANCE_NEWS)
        source.external_id = "jin10_calendar"
        db.add(source)
        await db.flush()
        old_item = ContentItem(
            data_source_id=source.id,
            platform_id="old",
            title="Old Calendar",
            content_url="https://www.jin10.com",
            published_at=datetime.now(UTC) - timedelta(days=370),
        )
        recent_item = ContentItem(
            data_source_id=source.id,
            platform_id="recent",
            title="Recent Calendar",
            content_url="https://www.jin10.com",
            published_at=datetime.now(UTC) - timedelta(days=30),
        )
        db.add_all([old_item, recent_item])
        await db.commit()

        with patch("app.services.scheduler.AsyncSessionLocal", session_factory):
            deleted = await prune_jin10_calendar_history()

        assert deleted == 1
        async with session_factory() as s:
            remaining = set(await s.scalars(select(ContentItem.platform_id)))
        assert remaining == {"recent"}

    async def test_jin10_calendar_existing_items_are_updated(self, db, session_factory):
        user = make_user()
        db.add(user)
        await db.flush()
        source = make_source(user.id, SourceType.FINANCE_NEWS)
        source.external_id = "jin10_calendar"
        db.add(source)
        await db.flush()
        db.add(
            ContentItem(
                data_source_id=source.id,
                platform_id="calendar-1",
                title="美国CPI",
                content_url="https://www.jin10.com",
                published_at=datetime(2026, 1, 1, tzinfo=UTC),
                raw_data={"actual": ""},
            )
        )
        await db.commit()

        mock_crawler = AsyncMock()
        mock_crawler.fetch_latest_items = AsyncMock(
            return_value=[
                CrawledItem(
                    platform_id="calendar-1",
                    title="美国CPI",
                    content_url="https://www.jin10.com",
                    published_at=datetime(2026, 1, 1, tzinfo=UTC),
                    raw_data={"actual": "2.4%", "affect_txt": "利多"},
                )
            ]
        )

        with (
            patch("app.services.scheduler.crawler_registry") as mock_registry,
            patch("app.services.scheduler.AsyncSessionLocal", session_factory),
        ):
            mock_registry.get.return_value = mock_crawler
            inserted = await crawl_source(source)

        assert inserted == 0
        async with session_factory() as s:
            row = await s.scalar(select(ContentItem).where(ContentItem.platform_id == "calendar-1"))
        assert row.raw_data["actual"] == "2.4%"
        assert row.raw_data["affect_txt"] == "利多"

    async def test_crawl_log_is_created_on_success(self, db, session_factory):
        user = make_user()
        db.add(user)
        await db.flush()
        source = make_source(user.id)
        db.add(source)
        await db.commit()

        mock_crawler = AsyncMock()
        mock_crawler.fetch_latest_items = AsyncMock(return_value=[make_video("VID001")])

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
            platform_id="VID001",
            title="Original Title",
            thumbnail_url="https://cdn/old.jpg",
            content_url="https://www.youtube.com/watch?v=VID001",
            published_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        db.add(existing)
        await db.commit()

        mock_crawler = AsyncMock()
        mock_crawler.fetch_latest_items = AsyncMock(
            return_value=[make_video("VID001", title="Updated Title")]
        )

        with (
            patch("app.services.scheduler.crawler_registry") as mock_registry,
            patch("app.services.scheduler.AsyncSessionLocal", session_factory),
        ):
            mock_registry.get.return_value = mock_crawler
            await crawl_source(source)

        async with session_factory() as s:
            row = await s.scalar(select(ContentItem).where(ContentItem.platform_id == "VID001"))
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
        mock_crawler.fetch_latest_items = AsyncMock(return_value=[make_video("VID001")])

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
            platform_id="VID001",
            title="Existing",
            content_url="https://www.youtube.com/watch?v=VID001",
            published_at=datetime(2024, 1, 1, tzinfo=UTC),
            notified_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        db.add(existing)
        await db.commit()

        mock_crawler = AsyncMock()
        mock_crawler.fetch_latest_items = AsyncMock(return_value=[make_video("VID002")])

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
            make_video("VID003", title="newest", published_at=base + timedelta(hours=2)),
            make_video("VID002", title="middle", published_at=base + timedelta(hours=1)),
            make_video("VID001", title="oldest", published_at=base),
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
        assert kwargs["content_url"].endswith("VID003")
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
            make_video("VID003", title="newest", published_at=base + timedelta(hours=2)),
            make_video("VID002", title="middle", published_at=base + timedelta(hours=1)),
            make_video("VID001", title="oldest", published_at=base),
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
        mock_crawler.fetch_latest_items = AsyncMock(return_value=[make_video("VID001")])

        with (
            patch("app.services.scheduler.crawler_registry") as mock_registry,
            patch("app.services.scheduler.AsyncSessionLocal", session_factory),
            patch("app.services.scheduler._notifier.send_card", new=AsyncMock()) as mock_send,
        ):
            mock_registry.get.return_value = mock_crawler
            await crawl_source(source)

        mock_send.assert_awaited()
        async with session_factory() as s:
            row = await s.scalar(select(ContentItem).where(ContentItem.platform_id == "VID001"))
        assert row.notified_at is not None

    async def test_jin10_flash_does_not_send_feishu_notification(self, db, session_factory):
        user = make_user()
        db.add(user)
        await db.flush()
        source = make_source(user.id, SourceType.FINANCE_NEWS)
        source.external_id = "jin10_flash"
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
        mock_crawler.fetch_latest_items = AsyncMock(return_value=[make_video("FLASH001")])

        with (
            patch("app.services.scheduler.crawler_registry") as mock_registry,
            patch("app.services.scheduler.AsyncSessionLocal", session_factory),
            patch("app.services.scheduler._notifier.send_card", new=AsyncMock()) as mock_send,
        ):
            mock_registry.get.return_value = mock_crawler
            await crawl_source(source)

        mock_send.assert_not_awaited()
        async with session_factory() as s:
            row = await s.scalar(select(ContentItem).where(ContentItem.platform_id == "FLASH001"))
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
        mock_crawler.fetch_latest_items = AsyncMock(return_value=[make_video("VID001")])

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
            row = await s.scalar(select(ContentItem).where(ContentItem.platform_id == "VID001"))
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
            platform_id="VID001",
            title="pending",
            content_url="https://www.youtube.com/watch?v=VID001",
            published_at=datetime(2024, 6, 1, tzinfo=UTC),
            notified_at=None,
        )
        db.add(existing)
        await db.commit()

        mock_crawler = AsyncMock()
        mock_crawler.fetch_latest_items = AsyncMock(
            return_value=[make_video("VID001", title="pending")]
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
            row = await s.scalar(select(ContentItem).where(ContentItem.platform_id == "VID001"))
        assert row.notified_at is not None


class TestCrawlAllSources:
    async def test_ensure_builtin_finance_news_sources_creates_three_per_user(self, db, session_factory):
        user = make_user()
        db.add(user)
        await db.commit()

        with patch("app.services.scheduler.AsyncSessionLocal", session_factory):
            inserted = await ensure_builtin_finance_news_sources()
            inserted_again = await ensure_builtin_finance_news_sources()

        assert inserted == 3
        assert inserted_again == 0
        async with session_factory() as s:
            sources = list(await s.scalars(
                select(DataSource).where(DataSource.source_type == SourceType.FINANCE_NEWS)
            ))
        assert {source.external_id for source in sources} == {
            "jin10_flash",
            "jin10_news",
            "jin10_calendar",
        }
        assert {source.content_type.value for source in sources} == {"news", "article", "market"}

    async def test_social_media_crawl_requests_every_twitter_source(self, db, session_factory):
        user = make_user()
        db.add(user)
        await db.flush()
        twitter_one = make_source(user.id, SourceType.TWITTER)
        twitter_one.external_id = "twitter-1"
        twitter_two = make_source(user.id, SourceType.TWITTER)
        twitter_two.external_id = "twitter-2"
        youtube = make_source(user.id, SourceType.YOUTUBE)
        youtube.external_id = "youtube-1"
        db.add_all([twitter_one, twitter_two, youtube])
        await db.commit()

        requested_ids: list[str] = []

        async def _fake_crawl_source(source):
            requested_ids.append(source.external_id)
            return 0

        with (
            patch("app.services.scheduler.AsyncSessionLocal", session_factory),
            patch("app.services.scheduler.crawl_source", side_effect=_fake_crawl_source),
        ):
            await crawl_social_media_sources()

        assert sorted(requested_ids) == ["twitter-1", "twitter-2"]

    async def test_regular_crawl_excludes_social_media_sources(self, db, session_factory):
        user = make_user()
        db.add(user)
        await db.flush()
        twitter = make_source(user.id, SourceType.TWITTER)
        twitter.external_id = "twitter-1"
        youtube = make_source(user.id, SourceType.YOUTUBE)
        youtube.external_id = "youtube-1"
        finance_news = make_source(user.id, SourceType.FINANCE_NEWS)
        finance_news.external_id = "jin10_flash"
        db.add_all([twitter, youtube, finance_news])
        await db.commit()

        requested_ids: list[str] = []

        async def _fake_crawl_source(source):
            requested_ids.append(source.external_id)
            return 0

        with (
            patch("app.services.scheduler.AsyncSessionLocal", session_factory),
            patch("app.services.scheduler.crawl_source", side_effect=_fake_crawl_source),
        ):
            await crawl_regular_sources()

        assert requested_ids == ["youtube-1"]

    async def test_finance_news_crawl_requests_all_builtin_finance_news_sources(
        self, db, session_factory
    ):
        user = make_user()
        db.add(user)
        await db.flush()
        for external_id in ("jin10_flash", "jin10_news", "jin10_calendar"):
            source = make_source(user.id, SourceType.FINANCE_NEWS)
            source.external_id = external_id
            db.add(source)
        await db.commit()

        requested_ids: list[str] = []

        async def _fake_crawl_source(source):
            requested_ids.append(source.external_id)
            return 0

        with (
            patch("app.services.scheduler.AsyncSessionLocal", session_factory),
            patch("app.services.scheduler.crawl_source", side_effect=_fake_crawl_source),
        ):
            await crawl_finance_news_sources()

        assert sorted(requested_ids) == ["jin10_calendar", "jin10_flash", "jin10_news"]

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
