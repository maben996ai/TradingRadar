from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.models.models import CrawlLog, CrawlLogStatus, DataSource, SourceType, ContentItem
from app.services.crawlers.base import SourceInfo


# ── helpers ──────────────────────────────────────────────────────────────────

REGISTER_PAYLOAD = {
    "email": "alice@example.com",
    "password": "password123",
    "display_name": "Alice",
}

MOCK_SOURCE_INFO = SourceInfo(
    platform_id="123456",
    name="测试创作者",
    profile_url="https://www.youtube.com/",
    avatar_url=None,
)


# ── auth ─────────────────────────────────────────────────────────────────────


class TestAuthRegister:
    async def test_register_returns_201_and_user_fields(self, client):
        resp = await client.post("/api/auth/register", json=REGISTER_PAYLOAD)
        assert resp.status_code == 201
        body = resp.json()
        assert body["email"] == "alice@example.com"
        assert body["display_name"] == "Alice"
        assert "id" in body

    async def test_register_duplicate_email_returns_409(self, client):
        await client.post("/api/auth/register", json=REGISTER_PAYLOAD)
        resp = await client.post("/api/auth/register", json=REGISTER_PAYLOAD)
        assert resp.status_code == 409

    async def test_register_uses_email_prefix_as_display_name_when_omitted(self, client):
        payload = {"email": "bob@example.com", "password": "password123"}
        resp = await client.post("/api/auth/register", json=payload)
        assert resp.status_code == 201
        assert resp.json()["display_name"] == "bob"

    async def test_register_short_password_returns_422(self, client):
        payload = {**REGISTER_PAYLOAD, "password": "short"}
        resp = await client.post("/api/auth/register", json=payload)
        assert resp.status_code == 422


class TestAuthLogin:
    async def test_login_returns_access_token(self, client):
        await client.post("/api/auth/register", json=REGISTER_PAYLOAD)
        resp = await client.post(
            "/api/auth/login",
            json={"email": "alice@example.com", "password": "password123"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

    async def test_login_wrong_password_returns_401(self, client):
        await client.post("/api/auth/register", json=REGISTER_PAYLOAD)
        resp = await client.post(
            "/api/auth/login",
            json={"email": "alice@example.com", "password": "wrongpassword"},
        )
        assert resp.status_code == 401

    async def test_login_unknown_email_returns_401(self, client):
        resp = await client.post(
            "/api/auth/login",
            json={"email": "nobody@example.com", "password": "password123"},
        )
        assert resp.status_code == 401


class TestAuthMe:
    async def test_me_returns_current_user(self, client, auth_headers):
        resp = await client.get("/api/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["email"] == "test@example.com"

    async def test_me_without_token_returns_401(self, client):
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 401


# ── data sources ──────────────────────────────────────────────────────────────


class TestDataSourcesAPI:
    @pytest.fixture(autouse=True)
    def _mock_background_crawl(self):
        """避免每个创建 data source 的测试真的触发后台抓取。"""
        with patch("app.api.data_sources._run_initial_crawl", new=AsyncMock(return_value=None)):
            yield

    async def test_list_data_sources_empty_for_new_user(self, client, auth_headers):
        resp = await client.get("/api/data-sources", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_data_source_returns_201(self, client, auth_headers):
        with patch(
            "app.api.data_sources.resolve_source",
            new=AsyncMock(return_value=(SourceType.YOUTUBE, MOCK_SOURCE_INFO)),
        ):
            resp = await client.post(
                "/api/data-sources",
                json={"url": "https://www.youtube.com/"},
                headers=auth_headers,
            )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "测试创作者"
        assert body["source_type"] == "youtube"
        assert body["external_id"] == "123456"

    async def test_create_duplicate_data_source_returns_409(self, client, auth_headers):
        with patch(
            "app.api.data_sources.resolve_source",
            new=AsyncMock(return_value=(SourceType.YOUTUBE, MOCK_SOURCE_INFO)),
        ):
            await client.post(
                "/api/data-sources",
                json={"url": "https://www.youtube.com/"},
                headers=auth_headers,
            )
            resp = await client.post(
                "/api/data-sources",
                json={"url": "https://www.youtube.com/"},
                headers=auth_headers,
            )
        assert resp.status_code == 409

    async def test_create_data_source_unsupported_url_returns_400(self, client, auth_headers):
        with patch(
            "app.api.data_sources.resolve_source",
            new=AsyncMock(side_effect=ValueError("Unsupported source URL")),
        ):
            resp = await client.post(
                "/api/data-sources",
                json={"url": "https://twitter.com/someone"},
                headers=auth_headers,
            )
        assert resp.status_code == 400

    async def test_delete_data_source_returns_204(self, client, auth_headers, db):
        with patch(
            "app.api.data_sources.resolve_source",
            new=AsyncMock(return_value=(SourceType.YOUTUBE, MOCK_SOURCE_INFO)),
        ):
            create_resp = await client.post(
                "/api/data-sources",
                json={"url": "https://www.youtube.com/"},
                headers=auth_headers,
            )
        source_id = create_resp.json()["id"]
        resp = await client.delete(f"/api/data-sources/{source_id}", headers=auth_headers)
        assert resp.status_code == 204

    async def test_delete_nonexistent_data_source_returns_404(self, client, auth_headers):
        resp = await client.delete("/api/data-sources/nonexistent-id", headers=auth_headers)
        assert resp.status_code == 404

    async def test_create_data_source_returns_initialized_at_null(self, client, auth_headers):
        """新建信源响应里 initialized_at 为 null，表示正在初始化。"""
        with patch(
            "app.api.data_sources.resolve_source",
            new=AsyncMock(return_value=(SourceType.YOUTUBE, MOCK_SOURCE_INFO)),
        ):
            resp = await client.post(
                "/api/data-sources",
                json={"url": "https://www.youtube.com/"},
                headers=auth_headers,
            )
        assert resp.status_code == 201
        assert resp.json()["initialized_at"] is None

    async def test_create_data_source_schedules_initialization_task(self, client, auth_headers):
        """POST /api/data-sources 应在后台调度初始化流程，不阻塞响应。"""
        mock_initial_crawl = AsyncMock(return_value=None)
        with (
            patch(
                "app.api.data_sources.resolve_source",
                new=AsyncMock(return_value=(SourceType.YOUTUBE, MOCK_SOURCE_INFO)),
            ),
            patch("app.api.data_sources._run_initial_crawl", new=mock_initial_crawl),
        ):
            resp = await client.post(
                "/api/data-sources",
                json={"url": "https://www.youtube.com/"},
                headers=auth_headers,
            )
        assert resp.status_code == 201
        mock_initial_crawl.assert_awaited_once()

    async def test_manual_crawl_endpoint_removed(self, client, auth_headers):
        """不再对外暴露手动触发抓取端点。"""
        with patch(
            "app.api.data_sources.resolve_source",
            new=AsyncMock(return_value=(SourceType.YOUTUBE, MOCK_SOURCE_INFO)),
        ):
            create_resp = await client.post(
                "/api/data-sources",
                json={"url": "https://www.youtube.com/"},
                headers=auth_headers,
            )
        source_id = create_resp.json()["id"]
        resp = await client.post(f"/api/data-sources/{source_id}/crawl", headers=auth_headers)
        assert resp.status_code in (404, 405)

    async def test_patch_data_source_note(self, client, auth_headers):
        with patch(
            "app.api.data_sources.resolve_source",
            new=AsyncMock(return_value=(SourceType.YOUTUBE, MOCK_SOURCE_INFO)),
        ):
            create_resp = await client.post(
                "/api/data-sources",
                json={"url": "https://www.youtube.com/"},
                headers=auth_headers,
            )
        source_id = create_resp.json()["id"]

        resp = await client.patch(
            f"/api/data-sources/{source_id}",
            json={"note": "重点关注"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["note"] == "重点关注"

    async def test_patch_data_source_note_nonexistent_returns_404(self, client, auth_headers):
        resp = await client.patch(
            "/api/data-sources/nonexistent-id",
            json={"note": "test"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_patch_data_source_note_clears_to_none(self, client, auth_headers):
        with patch(
            "app.api.data_sources.resolve_source",
            new=AsyncMock(return_value=(SourceType.YOUTUBE, MOCK_SOURCE_INFO)),
        ):
            create_resp = await client.post(
                "/api/data-sources",
                json={"url": "https://www.youtube.com/", "note": "原备注"},
                headers=auth_headers,
            )
        source_id = create_resp.json()["id"]

        resp = await client.patch(
            f"/api/data-sources/{source_id}",
            json={"note": None},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["note"] is None

    async def test_create_data_source_default_category_is_none(self, client, auth_headers):
        with patch(
            "app.api.data_sources.resolve_source",
            new=AsyncMock(return_value=(SourceType.YOUTUBE, MOCK_SOURCE_INFO)),
        ):
            resp = await client.post(
                "/api/data-sources",
                json={"url": "https://www.youtube.com/"},
                headers=auth_headers,
            )
        assert resp.status_code == 201
        assert resp.json()["category"] is None

    async def test_patch_data_source_category(self, client, auth_headers):
        with patch(
            "app.api.data_sources.resolve_source",
            new=AsyncMock(return_value=(SourceType.YOUTUBE, MOCK_SOURCE_INFO)),
        ):
            create_resp = await client.post(
                "/api/data-sources",
                json={"url": "https://www.youtube.com/"},
                headers=auth_headers,
            )
        source_id = create_resp.json()["id"]

        resp = await client.patch(
            f"/api/data-sources/{source_id}",
            json={"category": "宏观经济"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["category"] == "宏观经济"

    async def test_create_data_source_default_starred_is_false(self, client, auth_headers):
        with patch(
            "app.api.data_sources.resolve_source",
            new=AsyncMock(return_value=(SourceType.YOUTUBE, MOCK_SOURCE_INFO)),
        ):
            resp = await client.post(
                "/api/data-sources",
                json={"url": "https://www.youtube.com/"},
                headers=auth_headers,
            )
        assert resp.status_code == 201
        assert resp.json()["starred"] is False

    async def test_patch_data_source_starred(self, client, auth_headers):
        with patch(
            "app.api.data_sources.resolve_source",
            new=AsyncMock(return_value=(SourceType.YOUTUBE, MOCK_SOURCE_INFO)),
        ):
            create_resp = await client.post(
                "/api/data-sources",
                json={"url": "https://www.youtube.com/"},
                headers=auth_headers,
            )
        source_id = create_resp.json()["id"]

        resp = await client.patch(
            f"/api/data-sources/{source_id}",
            json={"starred": True},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["starred"] is True

    async def test_list_data_sources_filter_starred(self, client, auth_headers):
        with patch(
            "app.api.data_sources.resolve_source",
            new=AsyncMock(return_value=(SourceType.YOUTUBE, MOCK_SOURCE_INFO)),
        ):
            create_resp = await client.post(
                "/api/data-sources",
                json={"url": "https://www.youtube.com/"},
                headers=auth_headers,
            )
        source_id = create_resp.json()["id"]

        await client.patch(
            f"/api/data-sources/{source_id}",
            json={"starred": True},
            headers=auth_headers,
        )

        resp = await client.get("/api/data-sources?starred=true", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["starred"] is True

    async def test_list_data_sources_filter_starred_excludes_unstarred(self, client, auth_headers):
        with patch(
            "app.api.data_sources.resolve_source",
            new=AsyncMock(return_value=(SourceType.YOUTUBE, MOCK_SOURCE_INFO)),
        ):
            await client.post(
                "/api/data-sources",
                json={"url": "https://www.youtube.com/"},
                headers=auth_headers,
            )

        resp = await client.get("/api/data-sources?starred=true", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []


# ── videos ───────────────────────────────────────────────────────────────────


class TestVideosAPI:
    async def _seed_video(self, db, user_id: str) -> ContentItem:
        source = DataSource(
            user_id=user_id,
            source_type=SourceType.YOUTUBE,
            external_id="111",
            name="Seeded Source",
            profile_url="https://www.youtube.com/@seeded-source",
        )
        db.add(source)
        await db.flush()
        video = ContentItem(
            data_source_id=source.id,
            platform_id="VIDtest",
            title="Test Video",
            content_url="https://www.youtube.com/watch?v=VIDtest",
            published_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        db.add(video)
        await db.commit()
        return video

    async def test_list_videos_returns_user_videos(self, client, auth_headers, db):
        me_resp = await client.get("/api/auth/me", headers=auth_headers)
        user_id = me_resp.json()["id"]
        await self._seed_video(db, user_id)

        resp = await client.get("/api/content-items", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 1
        assert resp.json()["items"][0]["title"] == "Test Video"

    async def test_list_videos_filter_by_source_type(self, client, auth_headers, db):
        me_resp = await client.get("/api/auth/me", headers=auth_headers)
        user_id = me_resp.json()["id"]
        await self._seed_video(db, user_id)

        resp = await client.get("/api/content-items?source_type=twitter", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    async def test_list_videos_requires_auth(self, client):
        resp = await client.get("/api/content-items")
        assert resp.status_code == 401


# ── settings ─────────────────────────────────────────────────────────────────


class TestSettingsAPI:
    async def test_get_feishu_settings_returns_defaults(self, client, auth_headers):
        resp = await client.get("/api/settings/feishu", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["feishu_webhook_url"] is None

    async def test_update_feishu_webhook(self, client, auth_headers):
        resp = await client.put(
            "/api/settings/feishu",
            json={"feishu_webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert (
            resp.json()["feishu_webhook_url"] == "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
        )

    async def test_update_then_get_reflects_change(self, client, auth_headers):
        await client.put(
            "/api/settings/feishu",
            json={"feishu_webhook_url": "https://example.com/webhook"},
            headers=auth_headers,
        )
        resp = await client.get("/api/settings/feishu", headers=auth_headers)
        assert resp.json()["feishu_webhook_url"] == "https://example.com/webhook"


# ── crawl logs ────────────────────────────────────────────────────────────────


class TestCrawlLogsAPI:
    async def _seed_log(
        self, db, user_id: str, status: CrawlLogStatus, external_id: str = "999"
    ) -> CrawlLog:
        source = DataSource(
            user_id=user_id,
            source_type=SourceType.YOUTUBE,
            external_id=external_id,
            name="Log Source",
            profile_url=f"https://www.youtube.com/@log-{external_id}",
        )
        db.add(source)
        await db.flush()
        log = CrawlLog(data_source_id=source.id, status=status, items_found=1)
        db.add(log)
        await db.commit()
        return log

    async def test_list_crawl_logs_returns_user_logs(self, client, auth_headers, db):
        me_resp = await client.get("/api/auth/me", headers=auth_headers)
        user_id = me_resp.json()["id"]
        await self._seed_log(db, user_id, CrawlLogStatus.SUCCESS)

        resp = await client.get("/api/crawl-logs", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    async def test_filter_by_status(self, client, auth_headers, db):
        me_resp = await client.get("/api/auth/me", headers=auth_headers)
        user_id = me_resp.json()["id"]
        await self._seed_log(db, user_id, CrawlLogStatus.SUCCESS, external_id="998")
        await self._seed_log(db, user_id, CrawlLogStatus.FAILED, external_id="999")

        resp = await client.get("/api/crawl-logs?status=failed", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["status"] == "failed"

    async def test_requires_auth(self, client):
        resp = await client.get("/api/crawl-logs")
        assert resp.status_code == 401
