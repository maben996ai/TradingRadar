"""
Tests for:
  - /api/webhooks/feishu  (multi-webhook CRUD)
  - /api/data-sources  content_type filter & default
  - FeishuNotifier.send_card
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch


from app.models.models import SourceType
from app.services.crawlers.base import SourceInfo
from app.services.notifiers.feishu import FeishuNotifier
from app.services.notifiers.feishu_client import FeishuAppClient

REGISTER_PAYLOAD = {
    "email": "alice@example.com",
    "password": "password123",
    "display_name": "Alice",
}

MOCK_SOURCE_INFO = SourceInfo(
    platform_id="123456",
    name="测试UP主",
    profile_url="https://space.bilibili.com/123456",
    avatar_url=None,
)

WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/test-xxx"


# ── helpers ───────────────────────────────────────────────────────────────────


async def _make_data_source(client, auth_headers, content_type: str = "video"):
    with (
        patch(
            "app.api.data_sources.resolve_source",
            new=AsyncMock(return_value=(SourceType.BILIBILI, MOCK_SOURCE_INFO)),
        ),
        patch("app.api.data_sources._run_initial_crawl", new=AsyncMock()),
    ):
        resp = await client.post(
            "/api/data-sources",
            json={"url": "https://space.bilibili.com/123456", "content_type": content_type},
            headers=auth_headers,
        )
    return resp


# ── FeishuWebhooks API ────────────────────────────────────────────────────────


class TestFeishuWebhooksAPI:
    async def test_list_returns_empty_for_new_user(self, client, auth_headers):
        resp = await client.get("/api/webhooks/feishu", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_webhook_returns_201(self, client, auth_headers):
        resp = await client.post(
            "/api/webhooks/feishu",
            json={"name": "港股研究群", "webhook_url": WEBHOOK_URL},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "港股研究群"
        assert body["webhook_url"] == WEBHOOK_URL
        assert body["enabled"] is True

    async def test_create_webhook_appears_in_list(self, client, auth_headers):
        await client.post(
            "/api/webhooks/feishu",
            json={"name": "群A", "webhook_url": WEBHOOK_URL},
            headers=auth_headers,
        )
        await client.post(
            "/api/webhooks/feishu",
            json={"name": "群B", "webhook_url": WEBHOOK_URL + "2"},
            headers=auth_headers,
        )
        resp = await client.get("/api/webhooks/feishu", headers=auth_headers)
        assert resp.status_code == 200
        names = [w["name"] for w in resp.json()]
        assert "群A" in names
        assert "群B" in names

    async def test_update_webhook_name(self, client, auth_headers):
        create_resp = await client.post(
            "/api/webhooks/feishu",
            json={"name": "旧名字", "webhook_url": WEBHOOK_URL},
            headers=auth_headers,
        )
        webhook_id = create_resp.json()["id"]
        resp = await client.put(
            f"/api/webhooks/feishu/{webhook_id}",
            json={"name": "新名字"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "新名字"

    async def test_update_webhook_enabled_false(self, client, auth_headers):
        create_resp = await client.post(
            "/api/webhooks/feishu",
            json={"name": "群", "webhook_url": WEBHOOK_URL},
            headers=auth_headers,
        )
        webhook_id = create_resp.json()["id"]
        resp = await client.put(
            f"/api/webhooks/feishu/{webhook_id}",
            json={"enabled": False},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    async def test_delete_webhook_returns_204(self, client, auth_headers):
        create_resp = await client.post(
            "/api/webhooks/feishu",
            json={"name": "群", "webhook_url": WEBHOOK_URL},
            headers=auth_headers,
        )
        webhook_id = create_resp.json()["id"]
        resp = await client.delete(f"/api/webhooks/feishu/{webhook_id}", headers=auth_headers)
        assert resp.status_code == 204

    async def test_delete_webhook_removes_from_list(self, client, auth_headers):
        create_resp = await client.post(
            "/api/webhooks/feishu",
            json={"name": "群", "webhook_url": WEBHOOK_URL},
            headers=auth_headers,
        )
        webhook_id = create_resp.json()["id"]
        await client.delete(f"/api/webhooks/feishu/{webhook_id}", headers=auth_headers)
        list_resp = await client.get("/api/webhooks/feishu", headers=auth_headers)
        assert all(w["id"] != webhook_id for w in list_resp.json())

    async def test_delete_nonexistent_returns_404(self, client, auth_headers):
        resp = await client.delete("/api/webhooks/feishu/no-such-id", headers=auth_headers)
        assert resp.status_code == 404

    async def test_update_nonexistent_returns_404(self, client, auth_headers):
        resp = await client.put(
            "/api/webhooks/feishu/no-such-id",
            json={"name": "x"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_test_endpoint_calls_notifier(self, client, auth_headers):
        create_resp = await client.post(
            "/api/webhooks/feishu",
            json={"name": "群", "webhook_url": WEBHOOK_URL},
            headers=auth_headers,
        )
        webhook_id = create_resp.json()["id"]

        with patch(
            "app.api.webhooks._notifier.send_card",
            new=AsyncMock(),
        ) as mock_send:
            resp = await client.post(
                f"/api/webhooks/feishu/{webhook_id}/test",
                headers=auth_headers,
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        mock_send.assert_awaited_once()

    async def test_test_endpoint_nonexistent_returns_404(self, client, auth_headers):
        resp = await client.post("/api/webhooks/feishu/no-such-id/test", headers=auth_headers)
        assert resp.status_code == 404

    async def test_webhooks_isolated_between_users(self, client, auth_headers):
        """User A's webhooks are not visible to User B."""
        await client.post(
            "/api/webhooks/feishu",
            json={"name": "A的群", "webhook_url": WEBHOOK_URL},
            headers=auth_headers,
        )
        # register & login as user B
        await client.post(
            "/api/auth/register",
            json={"email": "bob@example.com", "password": "password123", "display_name": "Bob"},
        )
        login_resp = await client.post(
            "/api/auth/login",
            json={"email": "bob@example.com", "password": "password123"},
        )
        bob_headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

        resp = await client.get("/api/webhooks/feishu", headers=bob_headers)
        assert resp.json() == []


# ── DataSources content_type ──────────────────────────────────────────────────


class TestDataSourcesContentType:
    async def test_create_defaults_to_video(self, client, auth_headers):
        resp = await _make_data_source(client, auth_headers)
        assert resp.status_code == 201
        assert resp.json()["content_type"] == "video"

    async def test_create_with_explicit_content_type(self, client, auth_headers):
        resp = await _make_data_source(client, auth_headers, content_type="article")
        assert resp.status_code == 201
        assert resp.json()["content_type"] == "article"

    async def test_list_filter_by_content_type_video(self, client, auth_headers):
        await _make_data_source(client, auth_headers, content_type="video")
        resp = await client.get("/api/data-sources?content_type=video", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["content_type"] == "video"

    async def test_list_filter_excludes_other_types(self, client, auth_headers):
        await _make_data_source(client, auth_headers, content_type="video")
        resp = await client.get("/api/data-sources?content_type=article", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_without_filter_returns_all(self, client, auth_headers):
        with (
            patch(
                "app.api.data_sources.resolve_source",
                new=AsyncMock(
                    side_effect=[
                        (SourceType.BILIBILI, MOCK_SOURCE_INFO),
                        (
                            SourceType.BILIBILI,
                            SourceInfo(
                                platform_id="999999",
                                name="另一个UP主",
                                profile_url="https://space.bilibili.com/999999",
                                avatar_url=None,
                            ),
                        ),
                    ]
                ),
            ),
            patch("app.api.data_sources._run_initial_crawl", new=AsyncMock()),
        ):
            await client.post(
                "/api/data-sources",
                json={"url": "https://space.bilibili.com/123456", "content_type": "video"},
                headers=auth_headers,
            )
            await client.post(
                "/api/data-sources",
                json={"url": "https://space.bilibili.com/999999", "content_type": "article"},
                headers=auth_headers,
            )

        resp = await client.get("/api/data-sources", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    async def test_patch_content_type(self, client, auth_headers):
        create_resp = await _make_data_source(client, auth_headers, content_type="video")
        source_id = create_resp.json()["id"]

        resp = await client.patch(
            f"/api/data-sources/{source_id}",
            json={"content_type": "article"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["content_type"] == "article"

    async def test_patch_content_type_then_filtered_out(self, client, auth_headers):
        """After changing type from video to article, video filter returns empty."""
        create_resp = await _make_data_source(client, auth_headers, content_type="video")
        source_id = create_resp.json()["id"]

        await client.patch(
            f"/api/data-sources/{source_id}",
            json={"content_type": "article"},
            headers=auth_headers,
        )

        resp = await client.get("/api/data-sources?content_type=video", headers=auth_headers)
        assert resp.json() == []


# ── FeishuNotifier ────────────────────────────────────────────────────────────


class TestFeishuNotifier:
    async def test_send_card_posts_to_webhook(self):
        notifier = FeishuNotifier()
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            await notifier.send_card(
                webhook_url=WEBHOOK_URL,
                title="测试视频标题",
                creator_name="测试创作者",
                platform="bilibili",
                content_url="https://www.bilibili.com/video/BV1",
            )

        mock_client.post.assert_awaited_once()
        call_args = mock_client.post.call_args
        payload = call_args.kwargs["json"]
        assert payload["msg_type"] == "interactive"
        assert "card" in payload

    async def test_send_card_skips_when_no_webhook_url(self):
        notifier = FeishuNotifier()
        with patch("httpx.AsyncClient") as mock_client_cls:
            await notifier.send_card(
                webhook_url="",
                title="title",
                creator_name="creator",
                platform="bilibili",
                content_url="https://www.bilibili.com",
            )
            mock_client_cls.assert_not_called()

    async def test_send_card_new_creator_uses_blue_header(self):
        notifier = FeishuNotifier()
        sent_payload = {}

        async def fake_post(url, *, json):
            sent_payload.update(json)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(
                side_effect=lambda url, **kw: sent_payload.update(kw.get("json", {}))
            )
            mock_client_cls.return_value = mock_client

            await notifier.send_card(
                webhook_url=WEBHOOK_URL,
                title="首条视频",
                creator_name="新创作者",
                platform="youtube",
                content_url="https://youtube.com/watch?v=abc",
                is_new_creator=True,
            )

        assert sent_payload.get("card", {}).get("header", {}).get("template") == "blue"

    async def test_send_card_existing_creator_uses_green_header(self):
        notifier = FeishuNotifier()
        sent_payload = {}

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(
                side_effect=lambda url, **kw: sent_payload.update(kw.get("json", {}))
            )
            mock_client_cls.return_value = mock_client

            await notifier.send_card(
                webhook_url=WEBHOOK_URL,
                title="新视频",
                creator_name="老创作者",
                platform="bilibili",
                content_url="https://www.bilibili.com/video/BV1",
                is_new_creator=False,
            )

        assert sent_payload.get("card", {}).get("header", {}).get("template") == "green"

    async def test_send_card_title_contains_video_link(self):
        notifier = FeishuNotifier()
        sent_payload = {}

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(
                side_effect=lambda url, **kw: sent_payload.update(kw.get("json", {}))
            )
            mock_client_cls.return_value = mock_client

            content_url = "https://www.bilibili.com/video/BV123"
            await notifier.send_card(
                webhook_url=WEBHOOK_URL,
                title="港股分析",
                creator_name="财经UP",
                platform="bilibili",
                content_url=content_url,
            )

        elements = sent_payload.get("card", {}).get("elements", [])
        title_element = next((e for e in elements if e.get("tag") == "div" and "text" in e), None)
        assert title_element is not None
        assert content_url in title_element["text"]["content"]

    async def test_send_card_without_app_falls_back_to_text_link(self):
        """未配置自建应用时，封面以文本链接形式嵌入。"""
        notifier = FeishuNotifier(app_client=FeishuAppClient(app_id="", app_secret=""))
        sent_payload = {}

        with patch("app.services.notifiers.feishu.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(
                side_effect=lambda url, **kw: sent_payload.update(kw.get("json", {}))
            )
            mock_client_cls.return_value = mock_client

            await notifier.send_card(
                webhook_url=WEBHOOK_URL,
                title="港股分析",
                creator_name="财经UP",
                platform="bilibili",
                content_url="https://www.bilibili.com/video/BV1",
                thumbnail_url="https://i0.hdslb.com/cover.jpg",
            )

        elements = sent_payload.get("card", {}).get("elements", [])
        assert not any(e.get("tag") == "img" for e in elements)
        title_element = next((e for e in elements if e.get("tag") == "div" and "text" in e), None)
        assert "封面预览" in title_element["text"]["content"]

    async def test_send_card_uploads_cover_when_app_configured(self):
        """配置了自建应用时，上传封面并以 img 元素嵌入卡片。"""
        app_client = FeishuAppClient(app_id="cli_test", app_secret="secret")
        notifier = FeishuNotifier(app_client=app_client)
        sent_payload = {}

        async def fake_upload(url):
            assert url == "https://i0.hdslb.com/cover.jpg"
            return "img_v3_0001"

        with (
            patch.object(
                app_client, "upload_image_from_url", new=AsyncMock(side_effect=fake_upload)
            ),
            patch("app.services.notifiers.feishu.httpx.AsyncClient") as mock_client_cls,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(
                side_effect=lambda url, **kw: sent_payload.update(kw.get("json", {}))
            )
            mock_client_cls.return_value = mock_client

            await notifier.send_card(
                webhook_url=WEBHOOK_URL,
                title="港股分析",
                creator_name="财经UP",
                platform="bilibili",
                content_url="https://www.bilibili.com/video/BV1",
                thumbnail_url="https://i0.hdslb.com/cover.jpg",
            )

        elements = sent_payload.get("card", {}).get("elements", [])
        img_element = next((e for e in elements if e.get("tag") == "img"), None)
        assert img_element is not None
        assert img_element["img_key"] == "img_v3_0001"
        assert img_element["mode"] == "crop_center"
        # 使用 img 元素后不应再出现封面预览文案
        title_element = next((e for e in elements if e.get("tag") == "div" and "text" in e), None)
        assert "封面预览" not in title_element["text"]["content"]

    async def test_send_card_uses_compact_card_layout_for_cover(self):
        notifier = FeishuNotifier()
        sent_payload = {}

        with patch("app.services.notifiers.feishu.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(
                side_effect=lambda url, **kw: sent_payload.update(kw.get("json", {}))
            )
            mock_client_cls.return_value = mock_client

            await notifier.send_card(
                webhook_url=WEBHOOK_URL,
                title="港股分析",
                creator_name="财经UP",
                platform="bilibili",
                content_url="https://www.bilibili.com/video/BV1",
            )

        card = sent_payload.get("card", {})
        assert card.get("config", {}).get("wide_screen_mode") is False

    async def test_send_card_includes_published_at_second_precision(self):
        """published_at 有分秒信息 → 卡片 fields 含 yyyy-MM-dd HH:mm:ss。"""
        notifier = FeishuNotifier(app_client=FeishuAppClient(app_id="", app_secret=""))
        sent_payload = {}

        with patch("app.services.notifiers.feishu.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(
                side_effect=lambda url, **kw: sent_payload.update(kw.get("json", {}))
            )
            mock_client_cls.return_value = mock_client

            await notifier.send_card(
                webhook_url=WEBHOOK_URL,
                title="港股分析",
                creator_name="财经UP",
                platform="bilibili",
                content_url="https://www.bilibili.com/video/BV1",
                published_at=datetime(2026, 4, 19, 15, 30, 42, tzinfo=UTC),
            )

        elements = sent_payload.get("card", {}).get("elements", [])
        texts = [
            f["text"]["content"]
            for el in elements
            if el.get("tag") == "div" and "fields" in el
            for f in el["fields"]
        ]
        joined = "\n".join(texts)
        assert "2026-04-19 15:30:42" in joined
        assert "发布时间" in joined

    async def test_send_card_published_at_hour_precision_fallback(self):
        """分秒都为 0 → 降级为小时级 yyyy-MM-dd HH:00:00。"""
        notifier = FeishuNotifier(app_client=FeishuAppClient(app_id="", app_secret=""))
        sent_payload = {}

        with patch("app.services.notifiers.feishu.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(
                side_effect=lambda url, **kw: sent_payload.update(kw.get("json", {}))
            )
            mock_client_cls.return_value = mock_client

            await notifier.send_card(
                webhook_url=WEBHOOK_URL,
                title="港股分析",
                creator_name="财经UP",
                platform="bilibili",
                content_url="https://www.bilibili.com/video/BV1",
                published_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
            )

        elements = sent_payload.get("card", {}).get("elements", [])
        texts = [
            f["text"]["content"]
            for el in elements
            if el.get("tag") == "div" and "fields" in el
            for f in el["fields"]
        ]
        joined = "\n".join(texts)
        assert "2024-01-01 10:00:00" in joined

    async def test_send_card_without_published_at_omits_field(self):
        """published_at=None → fields 中不含 '发布时间'。"""
        notifier = FeishuNotifier(app_client=FeishuAppClient(app_id="", app_secret=""))
        sent_payload = {}

        with patch("app.services.notifiers.feishu.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(
                side_effect=lambda url, **kw: sent_payload.update(kw.get("json", {}))
            )
            mock_client_cls.return_value = mock_client

            await notifier.send_card(
                webhook_url=WEBHOOK_URL,
                title="港股分析",
                creator_name="财经UP",
                platform="bilibili",
                content_url="https://www.bilibili.com/video/BV1",
            )

        elements = sent_payload.get("card", {}).get("elements", [])
        texts = [
            f["text"]["content"]
            for el in elements
            if el.get("tag") == "div" and "fields" in el
            for f in el["fields"]
        ]
        joined = "\n".join(texts)
        assert "发布时间" not in joined

    async def test_send_card_upload_failure_falls_back_to_text_link(self):
        """上传失败时优雅回退到文本链接。"""
        app_client = FeishuAppClient(app_id="cli_test", app_secret="secret")
        notifier = FeishuNotifier(app_client=app_client)
        sent_payload = {}

        with (
            patch.object(
                app_client,
                "upload_image_from_url",
                new=AsyncMock(side_effect=RuntimeError("boom")),
            ),
            patch("app.services.notifiers.feishu.httpx.AsyncClient") as mock_client_cls,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(
                side_effect=lambda url, **kw: sent_payload.update(kw.get("json", {}))
            )
            mock_client_cls.return_value = mock_client

            await notifier.send_card(
                webhook_url=WEBHOOK_URL,
                title="港股分析",
                creator_name="财经UP",
                platform="bilibili",
                content_url="https://www.bilibili.com/video/BV1",
                thumbnail_url="https://i0.hdslb.com/cover.jpg",
            )

        elements = sent_payload.get("card", {}).get("elements", [])
        assert not any(e.get("tag") == "img" for e in elements)
        title_element = next((e for e in elements if e.get("tag") == "div" and "text" in e), None)
        assert "封面预览" in title_element["text"]["content"]
