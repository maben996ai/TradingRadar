"""财经日历 provider 与 service 单元测试。"""

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import func, select

from app.models.models import CalendarEvent, TrackedTicker
from app.services.calendar.provider import (
    FmpProvider,
    SeedProvider,
    _day_of_month,
    _generate_dates,
    _nth_weekday,
)
from app.services.calendar.events import DEFAULT_COMPANIES, MACRO_EVENTS_BY_KEY
from app.services.calendar import service as calendar_service
from app.services.calendar.service import _earnings_symbols, list_events, refresh_all


class TestDateHelpers:
    def test_nth_weekday_first_friday(self):
        # 2026-06 的第一个周五是 6/5
        assert _nth_weekday(2026, 6, 4, 1) == date(2026, 6, 5)

    def test_day_of_month_shifts_weekend(self):
        # 2026-06-13 是周六 → 顺延到 6/15 周一
        assert _day_of_month(2026, 6, 13) == date(2026, 6, 15)

    def test_generate_weekly(self):
        nfp = MACRO_EVENTS_BY_KEY["jobless_claims"]  # weekly Thursday
        dates = _generate_dates(nfp, date(2026, 6, 1), date(2026, 6, 30))
        assert all(d.weekday() == 3 for d in dates)
        assert len(dates) >= 4


class TestSeedProvider:
    async def test_fetch_macro_generates_events(self):
        provider = SeedProvider(fred_api_key="")
        start = datetime(2026, 6, 1, tzinfo=UTC)
        end = datetime(2026, 7, 1, tzinfo=UTC)
        events = await provider.fetch_macro(start, end)

        assert events
        assert all(e["kind"] == "macro" for e in events)
        assert all(e["scheduled_at"].tzinfo is not None for e in events)
        # FOMC 2026-06-17 决议应在窗口内
        assert any(e["event_key"] == "fomc_decision_2026-06-17" for e in events)

    async def test_fetch_earnings_default_companies(self):
        provider = SeedProvider(fred_api_key="")
        start = datetime(2026, 6, 1, tzinfo=UTC)
        end = datetime(2026, 7, 1, tzinfo=UTC)
        events = await provider.fetch_earnings(start, end)

        assert len(events) >= 7
        assert all(e["kind"] == "earnings" and e["ticker"] for e in events)
        tickers = {e["ticker"] for e in events}
        assert "AAPL" in tickers

    async def test_backfill_fills_actual_from_fred(self):
        # 用 mock 的 FRED 观测验证过去事件回填 actual/previous（窗口全部在 now 之前）
        fake_obs = [
            (date(2026, 1, 1), 3.0),
            (date(2026, 2, 1), 3.2),
            (date(2026, 3, 1), 3.4),
        ]
        with patch(
            "app.services.calendar.provider.fetch_observations",
            return_value=fake_obs,
        ):
            provider = SeedProvider(fred_api_key="key")
            events = await provider.fetch_macro(
                datetime(2025, 12, 1, tzinfo=UTC), datetime(2026, 3, 31, tzinfo=UTC)
            )

        cpi_past = [
            e for e in events if e["event_key"].startswith("cpi_") and e["actual"] is not None
        ]
        assert cpi_past
        newest = max(cpi_past, key=lambda e: e["scheduled_at"])
        assert newest["actual"] == 3.4
        assert newest["previous"] == 3.2
        assert newest["source"] == "FRED"


class TestFmpProvider:
    async def test_fetch_earnings_parses_stable_response(self):
        rows = [
            {"symbol": "AAPL", "date": "2026-06-20", "epsEstimated": 1.86, "epsActual": None},
            {"symbol": "AAPL", "date": "2020-01-01", "epsEstimated": 1.0, "epsActual": 0.9},
        ]
        response = MagicMock()
        response.json = MagicMock(return_value=rows)
        response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=response)

        with patch(
            "app.services.calendar.provider.httpx.AsyncClient", return_value=mock_client
        ):
            provider = FmpProvider(api_key="key")
            events = await provider.fetch_earnings(
                datetime(2026, 6, 1, tzinfo=UTC),
                datetime(2026, 7, 1, tzinfo=UTC),
                {"AAPL": "苹果"},
            )
        # 仅保留窗口内（2026-06-20），旧的 2020 被过滤
        assert len(events) == 1
        e = events[0]
        assert e["ticker"] == "AAPL"
        assert e["company_name"] == "苹果"
        assert e["forecast"] == 1.86
        assert e["source"] == "FMP"

    async def test_no_key_returns_empty(self):
        provider = FmpProvider(api_key="")
        events = await provider.fetch_earnings(
            datetime(2026, 6, 1, tzinfo=UTC), datetime(2026, 7, 1, tzinfo=UTC), {"AAPL": "苹果"}
        )
        assert events == []


class TestServiceRefreshAndList:
    async def test_refresh_all_seed_rebuilds_without_duplicates(self, db):
        empty_settings = SimpleNamespace(
            fred_api_key="", trading_economics_api_key="", fmp_api_key=""
        )
        with patch("app.services.calendar.service.get_settings", return_value=empty_settings):
            first = await refresh_all(db)
            second = await refresh_all(db)
        assert first > 0
        assert second == first  # 重建策略：重复刷新数量稳定、无残留
        total = await db.scalar(select(func.count()).select_from(CalendarEvent))
        assert total == first

    async def test_list_events_filters(self, db):
        base = datetime(2026, 6, 10, 12, 0, tzinfo=UTC)
        db.add_all(
            [
                CalendarEvent(
                    event_key="cpi_x", kind="macro", category="inflation",
                    title="CPI", title_en="CPI", country="US", scheduled_at=base,
                    all_day=False, importance=3, source="精选",
                ),
                CalendarEvent(
                    event_key="claims_x", kind="macro", category="employment",
                    title="Claims", title_en="Claims", country="US",
                    scheduled_at=base + timedelta(days=1), all_day=False,
                    importance=1, source="精选",
                ),
                CalendarEvent(
                    event_key="aapl_x", kind="earnings", category="earnings",
                    title="AAPL", title_en="AAPL", country="US",
                    scheduled_at=base + timedelta(days=2), all_day=False,
                    importance=3, ticker="AAPL", company_name="苹果", source="精选",
                ),
            ]
        )
        await db.commit()
        start = datetime(2026, 6, 1, tzinfo=UTC)
        end = datetime(2026, 7, 1, tzinfo=UTC)

        all_rows = await list_events(db, start, end)
        assert len(all_rows) == 3

        infl = await list_events(db, start, end, categories=["inflation"])
        assert [r.event_key for r in infl] == ["cpi_x"]

        high = await list_events(db, start, end, importance_min=3)
        assert {r.event_key for r in high} == {"cpi_x", "aapl_x"}

        earnings = await list_events(db, start, end, kind="earnings")
        assert [r.event_key for r in earnings] == ["aapl_x"]

    async def test_earnings_symbols_caps_for_fmp_quota(self, db):
        # 关注代码膨胀时，单次刷新对 FMP 拉取的代码数被截断，默认公司始终保留
        db.add_all([TrackedTicker(user_id="u1", ticker=f"T{i}") for i in range(10)])
        await db.commit()
        with patch.object(calendar_service, "MAX_EARNINGS_SYMBOLS", len(DEFAULT_COMPANIES) + 3):
            symbols = await _earnings_symbols(db)
        assert len(symbols) == len(DEFAULT_COMPANIES) + 3
        for c in DEFAULT_COMPANIES:
            assert c.ticker in symbols

    async def test_list_events_tracked_only(self, db):
        base = datetime(2026, 6, 10, 12, 0, tzinfo=UTC)
        db.add_all(
            [
                CalendarEvent(
                    event_key="cpi_y", kind="macro", category="inflation",
                    title="CPI", title_en="CPI", country="US", scheduled_at=base,
                    all_day=False, importance=3, source="精选",
                ),
                CalendarEvent(
                    event_key="aapl_y", kind="earnings", category="earnings",
                    title="AAPL", title_en="AAPL", country="US", scheduled_at=base,
                    all_day=False, importance=3, ticker="AAPL", source="精选",
                ),
                CalendarEvent(
                    event_key="nvda_y", kind="earnings", category="earnings",
                    title="NVDA", title_en="NVDA", country="US", scheduled_at=base,
                    all_day=False, importance=3, ticker="NVDA", source="精选",
                ),
                TrackedTicker(user_id="u1", ticker="AAPL"),
            ]
        )
        await db.commit()
        start = datetime(2026, 6, 1, tzinfo=UTC)
        end = datetime(2026, 7, 1, tzinfo=UTC)

        rows = await list_events(db, start, end, user_id="u1", tracked_only=True)
        keys = {r.event_key for r in rows}
        # 宏观保留，财报仅保留已关注的 AAPL
        assert keys == {"cpi_y", "aapl_y"}
