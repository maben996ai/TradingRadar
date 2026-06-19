from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
import respx
from httpx import AsyncClient, Response
from sqlalchemy import select

from app.models.models import ContentItem, DataSource, SourceType, User
from app.services.research import service as research_service
from app.services.research.rss_sources import RSS_BUILTIN_SOURCES
from app.services.research.service import (
    SEC_SOURCE_KEY,
    TickerNotFound,
    _short_name,
    list_sources,
    resolve_company_name,
    search_source,
)

FEED_URL = RSS_BUILTIN_SOURCES[0]["url"]

COMPANY_TICKERS = {
    "0": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA CORP"},
}

SUBMISSIONS = {
    "filings": {
        "recent": {
            "form": ["10-Q", "8-K", "4"],
            "accessionNumber": ["0001-26-000001", "0001-26-000002", "0001-26-000003"],
            "primaryDocument": ["nvda-10q.htm", "nvda-8k.htm", "form4.xml"],
            "filingDate": [
                datetime.now(UTC).date().isoformat(),
                (datetime.now(UTC).date() - timedelta(days=200)).isoformat(),
                datetime.now(UTC).date().isoformat(),
            ],
            "primaryDocDescription": ["10-Q", "8-K", "Form 4"],
        }
    }
}


def _mock_sec(fmp_status: int = 500):
    respx.get(research_service.FMP_SEARCH_URL).mock(return_value=Response(fmp_status, json=[]))
    respx.get(research_service.COMPANY_TICKERS_URL).mock(
        return_value=Response(200, json=COMPANY_TICKERS)
    )
    respx.get(research_service.SUBMISSIONS_URL.format(cik="0001045810")).mock(
        return_value=Response(200, json=SUBMISSIONS)
    )


async def _seed_rss_item(
    db, *, title: str, text: str, url: str, days_ago: int = 1, feed: str = FEED_URL
):
    user = await db.scalar(select(User).where(User.email == "r@example.com"))
    if user is None:
        user = User(email="r@example.com", password_hash="x", display_name="R")
        db.add(user)
        await db.flush()
    source = await db.scalar(select(DataSource).where(DataSource.external_id == feed))
    if source is None:
        source = DataSource(
            user_id=user.id,
            source_type=SourceType.RSS,
            external_id=feed,
            name="Test Feed",
            profile_url="https://example.com",
        )
        db.add(source)
        await db.flush()
    db.add(
        ContentItem(
            data_source_id=source.id,
            platform_id=url,
            title=title,
            content_url=url,
            published_at=datetime.now(UTC) - timedelta(days=days_ago),
            raw_data={"text": text},
        )
    )
    await db.commit()


class TestSources:
    def test_lists_all_rss_plus_sec(self):
        sources = list_sources()
        assert len(sources) == len(RSS_BUILTIN_SOURCES) + 1
        assert sources[-1]["key"] == SEC_SOURCE_KEY


class TestShortName:
    def test_strips_legal_suffixes(self):
        assert _short_name("NVIDIA CORP") == "NVIDIA"
        assert _short_name("Apple Inc.") == "Apple"


class TestMatches:
    def test_ticker_symbol_single_mention_matches(self):
        assert research_service._matches("Macro note", "we trimmed NVDA exposure", "NVDA", "NVIDIA")

    def test_company_name_in_title_matches(self):
        assert research_service._matches("Nvidia earnings", "", "NVDA", "NVIDIA")

    def test_passing_name_mentions_in_body_are_filtered(self):
        # 正文只顺带提一两次公司名（如 Tim Cook 文章里两次对比 Nvidia）不算命中
        assert not research_service._matches(
            "An Ode to Tim Cook",
            "Apple, unlike Nvidia, focuses on restraint. Nvidia chases growth.",
            "NVDA",
            "NVIDIA",
        )

    def test_three_body_mentions_match(self):
        assert research_service._matches(
            "Trillion dollar caps",
            "Nvidia crested $5T. Nvidia margins are 53%. Nvidia revenue must hit $483B.",
            "NVDA",
            "NVIDIA",
        )


class TestResolve:
    @respx.mock
    async def test_fallback_to_sec_table(self):
        _mock_sec()
        assert await resolve_company_name("nvda") == "NVIDIA CORP"

    @respx.mock
    async def test_unknown_ticker_raises(self):
        _mock_sec()
        with pytest.raises(TickerNotFound):
            await resolve_company_name("ZZZZ")


class TestSearchSource:
    @respx.mock
    async def test_rss_source_matches_ticker_and_name(self, db):
        _mock_sec()
        await _seed_rss_item(db, title="Nvidia earnings deep dive", text="GPU", url="u1")
        await _seed_rss_item(db, title="Macro", text="Mentions NVDA", url="u2")
        await _seed_rss_item(db, title="Unrelated", text="rates", url="u3")
        await _seed_rss_item(db, title="Old Nvidia", text="", url="u4", days_ago=120)

        result = await search_source(db, "NVDA", FEED_URL)
        assert result["error"] is None
        assert {i["url"] for i in result["items"]} == {"u1", "u2"}

    @respx.mock
    async def test_sec_source_filters_window_and_forms(self, db):
        _mock_sec()
        result = await search_source(db, "NVDA", SEC_SOURCE_KEY)
        assert result["error"] is None
        assert len(result["items"]) == 1
        assert result["items"][0]["title"].startswith("10-Q")
        assert result["items"][0]["url"].startswith("https://www.sec.gov/Archives/")

    @respx.mock
    async def test_sec_unreachable_returns_error_not_raise(self, db):
        import httpx as _httpx

        respx.get(research_service.FMP_SEARCH_URL).mock(
            return_value=Response(200, json=[{"symbol": "NVDA", "name": "NVIDIA Corporation"}])
        )
        respx.get(research_service.COMPANY_TICKERS_URL).mock(
            side_effect=_httpx.ConnectTimeout("timeout")
        )
        result = await search_source(db, "NVDA", SEC_SOURCE_KEY)
        assert result["items"] == []
        assert "不可达" in result["error"]


class TestResearchApi:
    async def test_sources_requires_auth(self, client: AsyncClient):
        assert (await client.get("/api/research/sources")).status_code == 401

    async def test_sources_returns_all(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/research/sources", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == len(RSS_BUILTIN_SOURCES) + 1

    async def test_resolve_404_on_unknown(self, client: AsyncClient, auth_headers):
        with patch(
            "app.api.research.resolve_company_name",
            new_callable=AsyncMock,
            side_effect=TickerNotFound("未找到"),
        ):
            resp = await client.get(
                "/api/research/resolve", params={"ticker": "ZZZZ"}, headers=auth_headers
            )
        assert resp.status_code == 404

    async def test_search_unknown_source_404(self, client: AsyncClient, auth_headers):
        resp = await client.get(
            "/api/research/search",
            params={"ticker": "NVDA", "source_key": "nope"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_search_returns_result(self, client: AsyncClient, auth_headers):
        fake = {"items": [{"title": "t", "url": "u", "meta": "2026-06-01", "published_at": None}], "error": None}
        with patch(
            "app.api.research.search_source", new_callable=AsyncMock, return_value=fake
        ):
            resp = await client.get(
                "/api/research/search",
                params={"ticker": "NVDA", "source_key": FEED_URL},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        assert resp.json()["items"][0]["title"] == "t"
