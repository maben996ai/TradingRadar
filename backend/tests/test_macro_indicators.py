"""宏观看板单元测试：判断规则、FRED 解析、看板构建。"""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.models.models import MacroObservation
from app.services.macro.fred_client import (
    FredApiError,
    fetch_observations,
    parse_observations,
)
from app.services.macro.indicators import INDICATORS_BY_KEY, get_indicator
from app.services.macro.service import build_dashboard


class TestJudgeRules:
    def test_rate_rising_is_bearish(self):
        ind = get_indicator("fed_funds_rate")
        assert ind.judge(latest=5.25, previous=5.0) == "bearish"

    def test_rate_falling_is_bullish(self):
        ind = get_indicator("fed_funds_rate")
        assert ind.judge(latest=4.5, previous=5.0) == "bullish"

    def test_small_change_within_band_is_neutral(self):
        ind = get_indicator("fed_funds_rate")  # neutral_band=0.05 abs
        assert ind.judge(latest=5.01, previous=5.0) == "neutral"

    def test_employment_rising_is_bullish(self):
        ind = get_indicator("nonfarm_payrolls")  # good_when=up, band 50
        assert ind.judge(latest=150_200, previous=150_000) == "bullish"

    def test_employment_falling_is_bearish(self):
        ind = get_indicator("nonfarm_payrolls")
        assert ind.judge(latest=149_800, previous=150_000) == "bearish"

    def test_relative_band_vix(self):
        ind = get_indicator("vix")  # good_when=down, band 0.05 rel
        # 5% 内视为中性
        assert ind.judge(latest=20.5, previous=20.0) == "neutral"
        # 上行超 5% 偏空
        assert ind.judge(latest=25.0, previous=20.0) == "bearish"
        # 下行超 5% 偏多
        assert ind.judge(latest=18.0, previous=20.0) == "bullish"

    def test_zone_high_normal_low(self):
        ind = get_indicator("vix")  # high=30, low=13
        assert ind.zone(35.0) == "high"
        assert ind.zone(20.0) == "normal"
        assert ind.zone(11.0) == "low"

    def test_zone_normal_when_no_thresholds(self):
        ind = get_indicator("nonfarm_payrolls")  # high/low 未设
        assert ind.zone(159000) == "normal"

    def test_reason_matches_judgment(self):
        ind = get_indicator("fed_funds_rate")
        assert ind.reason("bearish") == ind.reason_bearish
        assert ind.reason("bullish") == ind.reason_bullish
        assert ind.reason("neutral") == ind.reason_neutral

    def test_all_indicators_have_distinct_keys_and_series(self):
        keys = [ind.key for ind in INDICATORS_BY_KEY.values()]
        assert len(keys) == len(set(keys))
        for ind in INDICATORS_BY_KEY.values():
            assert ind.series_id
            assert ind.category in {
                "rates",
                "inflation",
                "growth",
                "employment",
                "liquidity",
                "risk",
            }


class TestParseObservations:
    def test_skips_missing_values(self):
        payload = {
            "observations": [
                {"date": "2026-01-01", "value": "5.0"},
                {"date": "2026-01-02", "value": "."},
                {"date": "2026-01-03", "value": "5.25"},
            ]
        }
        points = parse_observations(payload)
        assert points == [
            (date(2026, 1, 1), 5.0),
            (date(2026, 1, 3), 5.25),
        ]

    def test_empty_payload(self):
        assert parse_observations({}) == []


class TestFetchObservations:
    async def test_raises_without_api_key(self):
        with pytest.raises(FredApiError):
            await fetch_observations("DGS10", "lin", "2020-01-01", api_key="")

    async def test_parses_http_response(self):
        response = MagicMock(spec=httpx.Response)
        response.json = MagicMock(
            return_value={"observations": [{"date": "2026-01-01", "value": "5.0"}]}
        )
        response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=response)

        with patch(
            "app.services.macro.fred_client.httpx.AsyncClient", return_value=mock_client
        ):
            points = await fetch_observations("DGS10", "lin", "2020-01-01", api_key="key")

        assert points == [(date(2026, 1, 1), 5.0)]


class TestBuildDashboard:
    async def test_dashboard_computes_change_and_judgment(self, db):
        today = date.today()
        db.add_all(
            [
                MacroObservation(
                    indicator_key="fed_funds_rate",
                    date=today - timedelta(days=30),
                    value=5.0,
                ),
                MacroObservation(
                    indicator_key="fed_funds_rate",
                    date=today,
                    value=5.25,
                ),
            ]
        )
        await db.commit()

        dashboard = await build_dashboard(db)
        item = next(d for d in dashboard if d["key"] == "fed_funds_rate")

        assert item["latest"] == 5.25
        assert item["previous"] == 5.0
        assert item["change_abs"] == pytest.approx(0.25)
        assert item["change_pct"] == pytest.approx(5.0)
        assert item["judgment"] == "bearish"
        assert item["reason"]
        assert len(item["series"]) == 2

    async def test_dashboard_skips_indicators_without_data(self, db):
        today = date.today()
        db.add(
            MacroObservation(indicator_key="vix", date=today, value=20.0)
        )
        await db.commit()

        dashboard = await build_dashboard(db)
        keys = {d["key"] for d in dashboard}
        assert "vix" in keys
        assert "fed_funds_rate" not in keys

    async def test_single_observation_is_neutral(self, db):
        db.add(
            MacroObservation(indicator_key="vix", date=date.today(), value=20.0)
        )
        await db.commit()

        dashboard = await build_dashboard(db)
        item = next(d for d in dashboard if d["key"] == "vix")
        assert item["previous"] is None
        assert item["change_abs"] is None
        assert item["judgment"] == "neutral"
