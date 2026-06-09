"""个股分析（fundamentals）适配器、注册表与编排 service 单元测试。

所有网络请求均用 respx mock，API key/User-Agent 通过构造函数注入（不读真实 .env）。
"""

import json

import pytest
import respx
from httpx import Response

from app.services.fundamentals.base import (
    BaseFundamentalsAdapter,
    DownloadedArtifact,
    DownloadOutcome,
)
from app.services.fundamentals.finnhub import FinnhubAdapter
from app.services.fundamentals.fmp import FmpAdapter
from app.services.fundamentals.quartr import QuartrAdapter
from app.services.fundamentals.registry import FundamentalsRegistry
from app.services.fundamentals.sec_edgar import SecEdgarAdapter
from app.services.fundamentals.service import download_fundamentals

# ---------------------------------------------------------------------------
# SEC EDGAR mock 数据
# ---------------------------------------------------------------------------

COMPANY_TICKERS = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft Corporation"},
}

SUBMISSIONS = {
    "cik": "320193",
    "name": "Apple Inc.",
    "filings": {
        "recent": {
            "accessionNumber": [
                "0000320193-24-000123",
                "0000320193-24-000099",
                "0000320193-24-000077",
                "0000320193-24-000050",
            ],
            "form": ["10-K", "10-Q", "8-K", "4"],
            "filingDate": ["2024-11-01", "2024-08-02", "2024-07-15", "2024-06-01"],
            "reportDate": ["2024-09-28", "2024-06-29", "", ""],
            "primaryDocument": [
                "aapl-20240928.htm",
                "aapl-20240629.htm",
                "ea0203.htm",
                "form4.xml",
            ],
            "primaryDocDescription": ["10-K", "10-Q", "8-K", "FORM 4"],
        }
    },
}


def _mock_sec_routes() -> None:
    respx.get("https://www.sec.gov/files/company_tickers.json").mock(
        return_value=Response(200, json=COMPANY_TICKERS)
    )
    respx.get(url__regex=r"https://data\.sec\.gov/submissions/CIK\d+\.json").mock(
        return_value=Response(200, json=SUBMISSIONS)
    )
    respx.get(url__regex=r"https://www\.sec\.gov/Archives/edgar/data/.*").mock(
        return_value=Response(200, content=b"<html>filing document</html>")
    )


class TestSecEdgarAdapter:
    @respx.mock
    async def test_downloads_target_forms_to_disk(self, tmp_path):
        _mock_sec_routes()
        adapter = SecEdgarAdapter(
            user_agent="TradingRader test@example.com",
            forms=["10-K", "10-Q", "8-K", "13F-HR"],
            limit_per_form=1,
        )

        outcome = await adapter.download("aapl", tmp_path)

        assert isinstance(outcome, DownloadOutcome)
        assert outcome.source == "sec_edgar"
        assert outcome.skipped is False
        # 命中 10-K/10-Q/8-K 各 1 篇（form 4 不在目标集合，13F-HR 本期无）
        assert len(outcome.artifacts) == 3
        forms = {a.doc_type for a in outcome.artifacts}
        assert forms == {"10-K", "10-Q", "8-K"}

        from pathlib import Path

        for art in outcome.artifacts:
            assert isinstance(art, DownloadedArtifact)
            assert Path(art.file_path).exists()
            assert Path(art.file_path).read_bytes() == b"<html>filing document</html>"
            assert art.bytes_written == len(b"<html>filing document</html>")
            assert art.source == "sec_edgar"

    @respx.mock
    async def test_archive_url_uses_padded_cik_and_dashless_accession(self, tmp_path):
        _mock_sec_routes()
        adapter = SecEdgarAdapter(
            user_agent="TradingRader test@example.com",
            forms=["10-K"],
            limit_per_form=1,
        )

        outcome = await adapter.download("AAPL", tmp_path)

        tenk = outcome.artifacts[0]
        assert tenk.url == (
            "https://www.sec.gov/Archives/edgar/data/320193/" "000032019324000123/aapl-20240928.htm"
        )
        assert tenk.period == "2024-09-28"

    @respx.mock
    async def test_limit_per_form_caps_count(self, tmp_path):
        # 追加一篇更早的 10-K，验证 limit_per_form=1 只取最近一篇
        submissions = json.loads(json.dumps(SUBMISSIONS))
        recent = submissions["filings"]["recent"]
        recent["accessionNumber"].append("0000320193-23-000010")
        recent["form"].append("10-K")
        recent["filingDate"].append("2023-11-03")
        recent["reportDate"].append("2023-09-30")
        recent["primaryDocument"].append("aapl-20230930.htm")
        recent["primaryDocDescription"].append("10-K")

        respx.get("https://www.sec.gov/files/company_tickers.json").mock(
            return_value=Response(200, json=COMPANY_TICKERS)
        )
        respx.get(url__regex=r"https://data\.sec\.gov/submissions/CIK\d+\.json").mock(
            return_value=Response(200, json=submissions)
        )
        respx.get(url__regex=r"https://www\.sec\.gov/Archives/edgar/data/.*").mock(
            return_value=Response(200, content=b"doc")
        )

        adapter = SecEdgarAdapter(user_agent="UA", forms=["10-K"], limit_per_form=1)
        outcome = await adapter.download("AAPL", tmp_path)
        assert len(outcome.artifacts) == 1
        assert outcome.artifacts[0].period == "2024-09-28"

    @respx.mock
    async def test_unknown_ticker_returns_empty_outcome(self, tmp_path):
        _mock_sec_routes()
        adapter = SecEdgarAdapter(user_agent="UA")
        outcome = await adapter.download("NOPE", tmp_path)
        assert outcome.artifacts == []
        assert outcome.message is not None

    async def test_missing_user_agent_skips(self, tmp_path):
        adapter = SecEdgarAdapter(user_agent="")
        outcome = await adapter.download("AAPL", tmp_path)
        assert outcome.skipped is True
        assert outcome.artifacts == []


# ---------------------------------------------------------------------------
# FMP 三大报表
# ---------------------------------------------------------------------------

INCOME = [{"date": "2024-09-28", "revenue": 391035000000, "netIncome": 93736000000}]
BALANCE = [{"date": "2024-09-28", "totalAssets": 364980000000}]
CASHFLOW = [{"date": "2024-09-28", "freeCashFlow": 108807000000}]


class TestFmpAdapter:
    @respx.mock
    async def test_downloads_three_statements(self, tmp_path):
        respx.get("https://financialmodelingprep.com/stable/income-statement").mock(
            return_value=Response(200, json=INCOME)
        )
        respx.get("https://financialmodelingprep.com/stable/balance-sheet-statement").mock(
            return_value=Response(200, json=BALANCE)
        )
        respx.get("https://financialmodelingprep.com/stable/cash-flow-statement").mock(
            return_value=Response(200, json=CASHFLOW)
        )

        adapter = FmpAdapter(api_key="test-key", period="annual", limit=5, datasets=["statements"])
        outcome = await adapter.download("aapl", tmp_path)

        assert outcome.source == "fmp"
        assert outcome.skipped is False
        assert len(outcome.artifacts) == 3
        doc_types = {a.doc_type for a in outcome.artifacts}
        assert doc_types == {
            "income-statement",
            "balance-sheet-statement",
            "cash-flow-statement",
        }

        from pathlib import Path

        income_art = next(a for a in outcome.artifacts if a.doc_type == "income-statement")
        saved = json.loads(Path(income_art.file_path).read_text())
        assert saved == INCOME

    @respx.mock
    async def test_empty_statement_is_skipped_not_written(self, tmp_path):
        respx.get("https://financialmodelingprep.com/stable/income-statement").mock(
            return_value=Response(200, json=INCOME)
        )
        respx.get("https://financialmodelingprep.com/stable/balance-sheet-statement").mock(
            return_value=Response(200, json=[])
        )
        respx.get("https://financialmodelingprep.com/stable/cash-flow-statement").mock(
            return_value=Response(200, json=CASHFLOW)
        )

        adapter = FmpAdapter(api_key="test-key", datasets=["statements"])
        outcome = await adapter.download("AAPL", tmp_path)
        doc_types = {a.doc_type for a in outcome.artifacts}
        assert "balance-sheet-statement" not in doc_types
        assert len(outcome.artifacts) == 2

    @respx.mock
    async def test_http_error_on_one_statement_does_not_abort_others(self, tmp_path):
        respx.get("https://financialmodelingprep.com/stable/income-statement").mock(
            return_value=Response(200, json=INCOME)
        )
        respx.get("https://financialmodelingprep.com/stable/balance-sheet-statement").mock(
            return_value=Response(500)
        )
        respx.get("https://financialmodelingprep.com/stable/cash-flow-statement").mock(
            return_value=Response(200, json=CASHFLOW)
        )

        adapter = FmpAdapter(api_key="test-key", datasets=["statements"])
        outcome = await adapter.download("AAPL", tmp_path)
        doc_types = {a.doc_type for a in outcome.artifacts}
        assert doc_types == {"income-statement", "cash-flow-statement"}

    async def test_missing_api_key_skips(self, tmp_path):
        adapter = FmpAdapter(api_key="")
        outcome = await adapter.download("AAPL", tmp_path)
        assert outcome.skipped is True
        assert outcome.artifacts == []

    @respx.mock
    async def test_metrics_and_estimates_datasets(self, tmp_path):
        ratios = [{"date": "2024-09-28", "priceToEarningsRatio": 30.1, "grossProfitMargin": 0.46}]
        key_metrics = [{"date": "2024-09-28", "evToEBITDA": 22.5, "returnOnInvestedCapital": 0.5}]
        estimates = [{"date": "2025-09-30", "estimatedRevenueAvg": 4.2e11}]
        respx.get("https://financialmodelingprep.com/stable/ratios").mock(
            return_value=Response(200, json=ratios)
        )
        respx.get("https://financialmodelingprep.com/stable/key-metrics").mock(
            return_value=Response(200, json=key_metrics)
        )
        respx.get("https://financialmodelingprep.com/stable/analyst-estimates").mock(
            return_value=Response(200, json=estimates)
        )

        adapter = FmpAdapter(api_key="test-key", datasets=["metrics", "estimates"])
        outcome = await adapter.download("AAPL", tmp_path)

        doc_types = {a.doc_type for a in outcome.artifacts}
        assert doc_types == {"ratios", "key-metrics", "analyst-estimates"}

        from pathlib import Path

        ratios_art = next(a for a in outcome.artifacts if a.doc_type == "ratios")
        assert json.loads(Path(ratios_art.file_path).read_text()) == ratios

    @respx.mock
    async def test_default_datasets_covers_all_groups(self, tmp_path):
        for endpoint in (
            "income-statement",
            "balance-sheet-statement",
            "cash-flow-statement",
            "ratios",
            "key-metrics",
            "analyst-estimates",
        ):
            respx.get(f"https://financialmodelingprep.com/stable/{endpoint}").mock(
                return_value=Response(200, json=[{"date": "2024-09-28", "v": 1}])
            )

        adapter = FmpAdapter(api_key="test-key")
        outcome = await adapter.download("AAPL", tmp_path)
        assert len(outcome.artifacts) == 6


class TestFinnhubAdapter:
    @respx.mock
    async def test_downloads_recommendation_and_price_target(self, tmp_path):
        recommendation = [{"period": "2026-06-01", "buy": 20, "hold": 5, "sell": 1}]
        price_target = {"targetMean": 250.0, "targetHigh": 300.0, "targetLow": 180.0}
        respx.get("https://finnhub.io/api/v1/stock/recommendation").mock(
            return_value=Response(200, json=recommendation)
        )
        respx.get("https://finnhub.io/api/v1/stock/price-target").mock(
            return_value=Response(200, json=price_target)
        )

        adapter = FinnhubAdapter(api_key="test-key")
        outcome = await adapter.download("aapl", tmp_path)

        assert outcome.source == "finnhub"
        assert outcome.skipped is False
        doc_types = {a.doc_type for a in outcome.artifacts}
        assert doc_types == {"recommendation", "price-target"}

        from pathlib import Path

        pt = next(a for a in outcome.artifacts if a.doc_type == "price-target")
        assert json.loads(Path(pt.file_path).read_text()) == price_target

    @respx.mock
    async def test_empty_payload_is_skipped(self, tmp_path):
        respx.get("https://finnhub.io/api/v1/stock/recommendation").mock(
            return_value=Response(200, json=[])
        )
        respx.get("https://finnhub.io/api/v1/stock/price-target").mock(
            return_value=Response(200, json={"targetMean": 250.0})
        )

        adapter = FinnhubAdapter(api_key="test-key")
        outcome = await adapter.download("AAPL", tmp_path)
        doc_types = {a.doc_type for a in outcome.artifacts}
        assert doc_types == {"price-target"}

    @respx.mock
    async def test_http_error_does_not_abort_others(self, tmp_path):
        respx.get("https://finnhub.io/api/v1/stock/recommendation").mock(return_value=Response(500))
        respx.get("https://finnhub.io/api/v1/stock/price-target").mock(
            return_value=Response(200, json={"targetMean": 1.0})
        )

        adapter = FinnhubAdapter(api_key="test-key")
        outcome = await adapter.download("AAPL", tmp_path)
        doc_types = {a.doc_type for a in outcome.artifacts}
        assert doc_types == {"price-target"}

    async def test_missing_api_key_skips(self, tmp_path):
        adapter = FinnhubAdapter(api_key="")
        outcome = await adapter.download("AAPL", tmp_path)
        assert outcome.skipped is True
        assert outcome.artifacts == []


# ---------------------------------------------------------------------------
# Quartr 财报电话会转录
# ---------------------------------------------------------------------------

QUARTR_COMPANY = {"data": [{"id": 567, "ticker": "AAPL", "displayName": "Apple Inc."}]}
QUARTR_EVENTS = {
    "data": [
        {
            "id": 1,
            "eventType": "earnings",
            "fiscalPeriod": "Q2 2024",
            "eventDate": "2024-05-02",
            "transcriptUrl": "https://api.quartr.com/files/transcript-q2-2024.pdf",
        },
        {
            "id": 2,
            "eventType": "earnings",
            "fiscalPeriod": "Q1 2024",
            "eventDate": "2024-02-01",
            "transcriptUrl": "https://api.quartr.com/files/transcript-q1-2024.pdf",
        },
        {
            "id": 3,
            "eventType": "earnings",
            "fiscalPeriod": "Q4 2023",
            "eventDate": "2023-11-02",
            "transcriptUrl": None,
        },
    ]
}


def _mock_quartr_routes() -> None:
    respx.get("https://api.quartr.com/public/v1/companies").mock(
        return_value=Response(200, json=QUARTR_COMPANY)
    )
    respx.get(url__regex=r"https://api\.quartr\.com/public/v1/companies/\d+/events").mock(
        return_value=Response(200, json=QUARTR_EVENTS)
    )
    respx.get(url__regex=r"https://api\.quartr\.com/files/.*").mock(
        return_value=Response(200, content=b"%PDF earnings call transcript")
    )


class TestQuartrAdapter:
    @respx.mock
    async def test_downloads_transcripts_to_disk(self, tmp_path):
        _mock_quartr_routes()
        adapter = QuartrAdapter(api_key="test-key", limit=4)

        outcome = await adapter.download("aapl", tmp_path)

        assert outcome.source == "quartr"
        assert outcome.skipped is False
        # 仅有 transcriptUrl 的两个事件被下载（id=3 无转录被跳过）
        assert len(outcome.artifacts) == 2
        assert all(a.doc_type == "transcript" for a in outcome.artifacts)

        from pathlib import Path

        first = outcome.artifacts[0]
        assert first.period == "Q2 2024"
        assert first.url == "https://api.quartr.com/files/transcript-q2-2024.pdf"
        path = Path(first.file_path)
        assert path.exists()
        assert path.read_bytes() == b"%PDF earnings call transcript"
        assert path.name == "Q2_2024_transcript-q2-2024.pdf"

    @respx.mock
    async def test_limit_caps_transcripts(self, tmp_path):
        _mock_quartr_routes()
        adapter = QuartrAdapter(api_key="test-key", limit=1)
        outcome = await adapter.download("AAPL", tmp_path)
        assert len(outcome.artifacts) == 1
        assert outcome.artifacts[0].period == "Q2 2024"

    @respx.mock
    async def test_unknown_company_returns_empty_outcome(self, tmp_path):
        respx.get("https://api.quartr.com/public/v1/companies").mock(
            return_value=Response(200, json={"data": []})
        )
        adapter = QuartrAdapter(api_key="test-key")
        outcome = await adapter.download("NOPE", tmp_path)
        assert outcome.artifacts == []
        assert outcome.message is not None

    @respx.mock
    async def test_transcript_download_error_does_not_abort_others(self, tmp_path):
        respx.get("https://api.quartr.com/public/v1/companies").mock(
            return_value=Response(200, json=QUARTR_COMPANY)
        )
        respx.get(url__regex=r"https://api\.quartr\.com/public/v1/companies/\d+/events").mock(
            return_value=Response(200, json=QUARTR_EVENTS)
        )
        respx.get("https://api.quartr.com/files/transcript-q2-2024.pdf").mock(
            return_value=Response(500)
        )
        respx.get("https://api.quartr.com/files/transcript-q1-2024.pdf").mock(
            return_value=Response(200, content=b"ok")
        )

        adapter = QuartrAdapter(api_key="test-key", limit=4)
        outcome = await adapter.download("AAPL", tmp_path)
        assert len(outcome.artifacts) == 1
        assert outcome.artifacts[0].period == "Q1 2024"

    async def test_missing_api_key_skips(self, tmp_path):
        adapter = QuartrAdapter(api_key="")
        outcome = await adapter.download("AAPL", tmp_path)
        assert outcome.skipped is True
        assert outcome.artifacts == []


# ---------------------------------------------------------------------------
# 注册表
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_default_registry_has_adapters(self):
        registry = FundamentalsRegistry()
        assert "sec_edgar" in registry.names()
        assert "fmp" in registry.names()
        assert "finnhub" in registry.names()
        assert "quartr" in registry.names()

    def test_get_returns_adapter(self):
        registry = FundamentalsRegistry()
        assert isinstance(registry.get("sec_edgar"), BaseFundamentalsAdapter)

    def test_get_unknown_raises(self):
        registry = FundamentalsRegistry()
        with pytest.raises(KeyError):
            registry.get("nope")

    def test_custom_adapters_override(self):
        adapter = FmpAdapter(api_key="x")
        registry = FundamentalsRegistry(adapters=[adapter])
        assert registry.names() == ("fmp",)


# ---------------------------------------------------------------------------
# service 编排
# ---------------------------------------------------------------------------


class _StubAdapter(BaseFundamentalsAdapter):
    def __init__(self, name: str) -> None:
        self.name = name
        self.calls: list = []

    async def download(self, ticker, dest_dir):
        self.calls.append((ticker, dest_dir))
        return DownloadOutcome(
            source=self.name,
            artifacts=[
                DownloadedArtifact(
                    source=self.name,
                    doc_type="x",
                    file_path=str(dest_dir / f"{self.name}.txt"),
                    title="x",
                )
            ],
        )


class TestDownloadService:
    async def test_runs_all_adapters_under_ticker_dir(self, tmp_path):
        a = _StubAdapter("sec_edgar")
        b = _StubAdapter("fmp")
        registry = FundamentalsRegistry(adapters=[a, b])

        outcomes = await download_fundamentals("aapl", base_dir=tmp_path, registry=registry)

        assert [o.source for o in outcomes] == ["sec_edgar", "fmp"]
        # ticker 归一化为大写，且各 adapter 在 base/TICKER 下
        assert a.calls[0][0] == "AAPL"
        assert str(a.calls[0][1]).endswith("AAPL")

    async def test_sources_filter_selects_subset(self, tmp_path):
        a = _StubAdapter("sec_edgar")
        b = _StubAdapter("fmp")
        registry = FundamentalsRegistry(adapters=[a, b])

        outcomes = await download_fundamentals(
            "AAPL", sources=["fmp"], base_dir=tmp_path, registry=registry
        )
        assert [o.source for o in outcomes] == ["fmp"]
        assert a.calls == []

    async def test_blank_ticker_raises(self, tmp_path):
        with pytest.raises(ValueError):
            await download_fundamentals("  ", base_dir=tmp_path)
