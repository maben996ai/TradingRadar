"""
Tests for DataSource source_config field and SourceType placeholder values.
"""

from unittest.mock import AsyncMock, patch


from app.models.models import DataSource, SourceType
from app.services.crawlers.base import SourceInfo

MOCK_SOURCE_INFO = SourceInfo(
    platform_id="123456",
    name="测试创作者",
    profile_url="https://www.youtube.com/",
    avatar_url=None,
)


async def _create_data_source(client, auth_headers, extra: dict | None = None):
    payload = {"url": "https://www.youtube.com/"}
    if extra:
        payload.update(extra)
    with (
        patch(
            "app.api.data_sources.resolve_source",
            new=AsyncMock(return_value=(SourceType.YOUTUBE, MOCK_SOURCE_INFO)),
        ),
        patch("app.api.data_sources._run_initial_crawl", new=AsyncMock()),
    ):
        return await client.post("/api/data-sources", json=payload, headers=auth_headers)


class TestDataSourceConfig:
    async def test_source_config_roundtrip(self, client, auth_headers):
        config = {"rss_url": "https://x.com/feed", "etag": "abc"}
        resp = await _create_data_source(client, auth_headers, {"source_config": config})
        assert resp.status_code == 201
        source_id = resp.json()["id"]

        get_resp = await client.get("/api/data-sources", headers=auth_headers)
        item = next(s for s in get_resp.json() if s["id"] == source_id)
        assert item["source_config"] == config

    async def test_source_config_defaults_to_none(self, client, auth_headers):
        resp = await _create_data_source(client, auth_headers)
        assert resp.status_code == 201
        assert resp.json()["source_config"] is None

    async def test_source_type_placeholder_values(self, db, auth_headers, client):
        me = await client.get("/api/auth/me", headers=auth_headers)
        user_id = me.json()["id"]

        for st in (SourceType.WECHAT_ARTICLE, SourceType.WEBSITE, SourceType.RSS, SourceType.PDF):
            source = DataSource(
                user_id=user_id,
                source_type=st,
                external_id=f"ext_{st.value}",
                name=f"Source {st.value}",
                profile_url=f"https://example.com/{st.value}",
            )
            db.add(source)
        await db.commit()

        resp = await client.get("/api/data-sources", headers=auth_headers)
        assert resp.status_code == 200
        types = {s["source_type"] for s in resp.json()}
        assert SourceType.WECHAT_ARTICLE.value in types
        assert SourceType.WEBSITE.value in types
        assert SourceType.RSS.value in types
        assert SourceType.PDF.value in types

    async def test_unsupported_source_url_returns_400(self, client, auth_headers):
        resp = await client.post(
            "/api/data-sources",
            json={"url": "https://twitter.com/someone"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
