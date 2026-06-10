"""SEC EDGAR 适配器：下载美股公司披露文件（10-K/10-Q/8-K/13F 等）。

SEC EDGAR 免费、无需 API key，但要求请求带 User-Agent（``公司名 邮箱``）。
未配置 User-Agent 时跳过（``skipped=True``），不发起请求。
"""

import logging
from pathlib import Path

import httpx

from app.core.config import get_settings
from app.services.fundamentals.base import (
    BaseFundamentalsAdapter,
    DownloadedArtifact,
    DownloadOutcome,
)

logger = logging.getLogger(__name__)

COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"
REQUEST_TIMEOUT = 30.0

DEFAULT_FORMS = ("10-K", "10-Q", "8-K", "13F-HR")


def _safe_segment(value: str) -> str:
    """把 form 等用于路径的片段中的分隔符替换掉。"""
    return value.replace("/", "_").replace("\\", "_")


class SecEdgarAdapter(BaseFundamentalsAdapter):
    name = "sec_edgar"

    def __init__(
        self,
        user_agent: str | None = None,
        forms: list[str] | tuple[str, ...] | None = None,
        limit_per_form: int = 2,
    ) -> None:
        self._user_agent = user_agent
        self._forms = tuple(forms) if forms is not None else DEFAULT_FORMS
        self._limit_per_form = limit_per_form

    def _resolve_user_agent(self) -> str:
        if self._user_agent is not None:
            return self._user_agent
        return get_settings().sec_edgar_user_agent

    async def download(self, ticker: str, dest_dir: Path) -> DownloadOutcome:
        user_agent = self._resolve_user_agent()
        if not user_agent:
            return DownloadOutcome(
                source=self.name,
                skipped=True,
                message="SEC_EDGAR_USER_AGENT 未配置（SEC 要求请求携带 User-Agent）",
            )

        ticker = ticker.strip().upper()
        headers = {"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, headers=headers) as client:
            cik = await self._resolve_cik(client, ticker)
            if cik is None:
                return DownloadOutcome(
                    source=self.name,
                    message=f"未在 SEC EDGAR 找到代码 {ticker} 对应的 CIK",
                )

            filings = await self._list_filings(client, cik)
            artifacts: list[DownloadedArtifact] = []
            base = Path(dest_dir) / self.name
            for filing in filings:
                artifact = await self._download_filing(client, cik, filing, base)
                if artifact is not None:
                    artifacts.append(artifact)

        return DownloadOutcome(
            source=self.name,
            artifacts=artifacts,
            message=None if artifacts else "目标披露类型在该公司近期申报中未找到",
        )

    async def _resolve_cik(self, client: httpx.AsyncClient, ticker: str) -> str | None:
        resp = await client.get(COMPANY_TICKERS_URL)
        resp.raise_for_status()
        payload = resp.json()
        for entry in payload.values():
            if str(entry.get("ticker", "")).upper() == ticker:
                return f"{int(entry['cik_str']):010d}"
        return None

    async def _list_filings(self, client: httpx.AsyncClient, cik: str) -> list[dict]:
        resp = await client.get(SUBMISSIONS_URL.format(cik=cik))
        resp.raise_for_status()
        recent = resp.json().get("filings", {}).get("recent", {})

        forms = recent.get("form", [])
        accessions = recent.get("accessionNumber", [])
        documents = recent.get("primaryDocument", [])
        filing_dates = recent.get("filingDate", [])
        report_dates = recent.get("reportDate", [])
        descriptions = recent.get("primaryDocDescription", [])

        target = set(self._forms)
        counts: dict[str, int] = {}
        selected: list[dict] = []
        # recent 数组按申报时间倒序，直接顺序遍历即为最新优先
        for i, form in enumerate(forms):
            if form not in target:
                continue
            if counts.get(form, 0) >= self._limit_per_form:
                continue
            document = documents[i] if i < len(documents) else ""
            if not document:
                continue
            counts[form] = counts.get(form, 0) + 1
            selected.append(
                {
                    "form": form,
                    "accession": accessions[i] if i < len(accessions) else "",
                    "document": document,
                    "filing_date": filing_dates[i] if i < len(filing_dates) else "",
                    "report_date": report_dates[i] if i < len(report_dates) else "",
                    "description": descriptions[i] if i < len(descriptions) else "",
                }
            )
        return selected

    async def _download_filing(
        self,
        client: httpx.AsyncClient,
        cik: str,
        filing: dict,
        base: Path,
    ) -> DownloadedArtifact | None:
        accession_nodash = filing["accession"].replace("-", "")
        url = ARCHIVE_URL.format(
            cik=int(cik),  # archive 路径用去前导零的 CIK
            accession=accession_nodash,
            document=filing["document"],
        )
        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("SEC EDGAR 下载失败 %s: %s", url, exc)
            return None

        form = filing["form"]
        out_dir = base / _safe_segment(form)
        out_dir.mkdir(parents=True, exist_ok=True)
        file_path = out_dir / f"{accession_nodash}_{filing['document']}"
        content = resp.content
        file_path.write_bytes(content)

        period = filing.get("report_date") or filing.get("filing_date") or None
        return DownloadedArtifact(
            source=self.name,
            doc_type=form,
            file_path=str(file_path),
            title=f"{form} {period or ''}".strip(),
            url=url,
            period=period,
            bytes_written=len(content),
            raw_meta={
                "accession_number": filing["accession"],
                "filing_date": filing.get("filing_date"),
                "description": filing.get("description"),
            },
        )
