"""FeishuAppClient 单元测试：token 获取与缓存、图片上传、错误路径。"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.notifiers.feishu_client import FeishuAppClient


def _make_async_client_mock(responses: list):
    """构造一个按调用顺序返回预设 response 的 httpx.AsyncClient mock。"""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=responses)
    mock_client.get = AsyncMock(side_effect=responses)
    return mock_client


def _response(
    status: int = 200,
    json_data: dict | None = None,
    content: bytes = b"",
    headers: dict | None = None,
):
    r = MagicMock(spec=httpx.Response)
    r.status_code = status
    r.json = MagicMock(return_value=json_data or {})
    r.content = content
    r.headers = headers or {"content-type": "image/jpeg"}
    r.raise_for_status = MagicMock()
    return r


class TestFeishuAppClientConfigured:
    def test_not_configured_when_both_empty(self):
        client = FeishuAppClient(app_id="", app_secret="")
        assert client.configured is False

    def test_not_configured_when_only_app_id(self):
        client = FeishuAppClient(app_id="cli_x", app_secret="")
        assert client.configured is False

    def test_configured_when_both_present(self):
        client = FeishuAppClient(app_id="cli_x", app_secret="sec")
        assert client.configured is True


class TestTenantAccessToken:
    async def test_raises_when_not_configured(self):
        client = FeishuAppClient(app_id="", app_secret="")
        with pytest.raises(RuntimeError):
            await client.get_tenant_access_token()

    async def test_fetches_token_from_open_api(self):
        client = FeishuAppClient(app_id="cli_x", app_secret="sec")
        token_resp = _response(
            json_data={"code": 0, "tenant_access_token": "t-abc", "expire": 7200}
        )

        with patch("app.services.notifiers.feishu_client.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = _make_async_client_mock([token_resp])
            token = await client.get_tenant_access_token()

        assert token == "t-abc"

    async def test_reuses_cached_token_within_ttl(self):
        client = FeishuAppClient(app_id="cli_x", app_secret="sec")
        token_resp = _response(
            json_data={"code": 0, "tenant_access_token": "t-cached", "expire": 7200}
        )

        with patch("app.services.notifiers.feishu_client.httpx.AsyncClient") as mock_cls:
            first = _make_async_client_mock([token_resp])
            mock_cls.return_value = first
            t1 = await client.get_tenant_access_token()
            # Second call should not hit the API at all
            t2 = await client.get_tenant_access_token()

        assert t1 == t2 == "t-cached"
        # httpx.AsyncClient should only have been instantiated once
        assert mock_cls.call_count == 1

    async def test_refetches_when_token_expired(self):
        client = FeishuAppClient(app_id="cli_x", app_secret="sec")
        # First response sets expire very small so safety window makes it already expired
        resp1 = _response(json_data={"code": 0, "tenant_access_token": "t-old", "expire": 10})
        resp2 = _response(json_data={"code": 0, "tenant_access_token": "t-new", "expire": 7200})

        with patch("app.services.notifiers.feishu_client.httpx.AsyncClient") as mock_cls:
            # Each async with creates a new client instance
            mock_cls.side_effect = [
                _make_async_client_mock([resp1]),
                _make_async_client_mock([resp2]),
            ]
            t1 = await client.get_tenant_access_token()
            # Force expiry
            client._token_expires_at = time.time() - 1
            t2 = await client.get_tenant_access_token()

        assert t1 == "t-old"
        assert t2 == "t-new"

    async def test_raises_when_api_returns_error_code(self):
        client = FeishuAppClient(app_id="cli_x", app_secret="sec")
        err_resp = _response(json_data={"code": 99991663, "msg": "app_id invalid"})

        with patch("app.services.notifiers.feishu_client.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = _make_async_client_mock([err_resp])
            with pytest.raises(RuntimeError) as ei:
                await client.get_tenant_access_token()

        assert "99991663" in str(ei.value) or "app_id invalid" in str(ei.value)


class TestUploadImageFromUrl:
    async def test_raises_when_not_configured(self):
        client = FeishuAppClient(app_id="", app_secret="")
        with pytest.raises(RuntimeError):
            await client.upload_image_from_url("https://example.com/a.jpg")

    async def test_uploads_and_returns_image_key(self):
        client = FeishuAppClient(app_id="cli_x", app_secret="sec")
        # Pre-populate token cache to skip token call
        client._token = "cached-token"
        client._token_expires_at = time.time() + 10_000

        download_resp = _response(
            content=b"\xff\xd8\xff fake jpeg",
            headers={"content-type": "image/jpeg"},
        )
        upload_resp = _response(
            json_data={"code": 0, "data": {"image_key": "img_v3_AAAA"}},
        )

        call_history = []

        def fake_client_factory(*args, **kwargs):
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)

            async def fake_get(url, **kw):
                call_history.append(("get", url, kw))
                return download_resp

            async def fake_post(url, **kw):
                call_history.append(("post", url, kw))
                return upload_resp

            mock_client.get = fake_get
            mock_client.post = fake_post
            return mock_client

        with patch(
            "app.services.notifiers.feishu_client.httpx.AsyncClient",
            side_effect=fake_client_factory,
        ):
            key = await client.upload_image_from_url("https://i.ytimg.com/bfs/x.jpg")

        assert key == "img_v3_AAAA"
        # 至少应有 1 次 GET（下载封面） + 1 次 POST（上传到飞书）
        methods = [c[0] for c in call_history]
        assert methods.count("get") == 1
        assert methods.count("post") == 1

    async def test_sends_user_agent_header_when_downloading_image(self):
        """下载封面时带通用 User-Agent。"""
        client = FeishuAppClient(app_id="cli_x", app_secret="sec")
        client._token = "cached-token"
        client._token_expires_at = time.time() + 10_000

        captured_get_kwargs = {}

        def fake_client_factory(*args, **kwargs):
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)

            async def fake_get(url, **kw):
                captured_get_kwargs.update(kw)
                return _response(content=b"img", headers={"content-type": "image/jpeg"})

            async def fake_post(url, **kw):
                return _response(json_data={"code": 0, "data": {"image_key": "k"}})

            mock_client.get = fake_get
            mock_client.post = fake_post
            return mock_client

        with patch(
            "app.services.notifiers.feishu_client.httpx.AsyncClient",
            side_effect=fake_client_factory,
        ):
            await client.upload_image_from_url("https://i.ytimg.com/bfs/x.jpg")

        headers = captured_get_kwargs.get("headers", {})
        assert headers == {"User-Agent": "Mozilla/5.0"}

    async def test_uses_bearer_token_when_uploading(self):
        client = FeishuAppClient(app_id="cli_x", app_secret="sec")
        client._token = "tenant-token-xyz"
        client._token_expires_at = time.time() + 10_000

        captured_post_kwargs = {}

        def fake_client_factory(*args, **kwargs):
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)

            async def fake_get(url, **kw):
                return _response(content=b"img", headers={"content-type": "image/jpeg"})

            async def fake_post(url, **kw):
                captured_post_kwargs["url"] = url
                captured_post_kwargs.update(kw)
                return _response(json_data={"code": 0, "data": {"image_key": "k"}})

            mock_client.get = fake_get
            mock_client.post = fake_post
            return mock_client

        with patch(
            "app.services.notifiers.feishu_client.httpx.AsyncClient",
            side_effect=fake_client_factory,
        ):
            await client.upload_image_from_url("https://i.ytimg.com/bfs/x.jpg")

        assert "im/v1/images" in captured_post_kwargs["url"]
        headers = captured_post_kwargs.get("headers", {})
        assert headers.get("Authorization") == "Bearer tenant-token-xyz"
        # 必须是 multipart: data + files
        assert captured_post_kwargs.get("data", {}).get("image_type") == "message"
        assert "image" in captured_post_kwargs.get("files", {})

    async def test_raises_on_upload_api_error(self):
        client = FeishuAppClient(app_id="cli_x", app_secret="sec")
        client._token = "t"
        client._token_expires_at = time.time() + 10_000

        def fake_client_factory(*args, **kwargs):
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=_response(content=b"x"))
            mock_client.post = AsyncMock(
                return_value=_response(json_data={"code": 99991672, "msg": "no permission"})
            )
            return mock_client

        with patch(
            "app.services.notifiers.feishu_client.httpx.AsyncClient",
            side_effect=fake_client_factory,
        ):
            with pytest.raises(RuntimeError) as ei:
                await client.upload_image_from_url("https://example.com/x.jpg")

        assert "99991672" in str(ei.value) or "no permission" in str(ei.value)
