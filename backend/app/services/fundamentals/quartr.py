"""Quartr 适配器：下载财报电话会转录（transcript）落盘。

流程：按 ticker 解析公司 -> 拉取财报电话会事件 -> 下载带 transcript 的事件文件。
未配置 ``QUARTR_API_KEY`` 时跳过（``skipped=True``）。单个事件下载失败不影响其余。
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

COMPANIES_URL = "https://api.quartr.com/public/v1/companies"
EVENTS_URL = "https://api.quartr.com/public/v1/companies/{company_id}/events"
REQUEST_TIMEOUT = 30.0


def _safe_segment(value: str) -> str:
    return value.replace("/", "_").replace("\\", "_").replace(" ", "_")


def _filename_from_url(url: str, default: str) -> str:
    tail = url.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1]
    return tail or default


class QuartrAdapter(BaseFundamentalsAdapter):
    name = "quartr"

    def __init__(self, api_key: str | None = None, limit: int = 4) -> None:
        self._api_key = api_key
        self._limit = limit

    def _resolve_api_key(self) -> str:
        if self._api_key is not None:
            return self._api_key
        return get_settings().quartr_api_key

    async def download(self, ticker: str, dest_dir: Path) -> DownloadOutcome:
        api_key = self._resolve_api_key()
        if not api_key:
            return DownloadOutcome(
                source=self.name,
                skipped=True,
                message="QUARTR_API_KEY 未配置",
            )

        ticker = ticker.strip().upper()
        headers = {"X-Api-Key": api_key}
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, headers=headers) as client:
            company_id = await self._resolve_company_id(client, ticker)
            if company_id is None:
                return DownloadOutcome(
                    source=self.name,
                    message=f"未在 Quartr 找到代码 {ticker} 对应公司",
                )

            events = await self._list_transcript_events(client, company_id)
            artifacts: list[DownloadedArtifact] = []
            out_dir = Path(dest_dir) / self.name
            for event in events:
                artifact = await self._download_transcript(client, event, out_dir, ticker)
                if artifact is not None:
                    artifacts.append(artifact)

        return DownloadOutcome(
            source=self.name,
            artifacts=artifacts,
            message=None if artifacts else "该公司近期无可下载的财报电话会转录",
        )

    async def _resolve_company_id(self, client: httpx.AsyncClient, ticker: str) -> int | str | None:
        resp = await client.get(COMPANIES_URL, params={"ticker": ticker})
        resp.raise_for_status()
        data = resp.json().get("data", [])
        for company in data:
            if str(company.get("ticker", "")).upper() == ticker:
                return company.get("id")
        if data:
            return data[0].get("id")
        return None

    async def _list_transcript_events(
        self, client: httpx.AsyncClient, company_id: int | str
    ) -> list[dict]:
        resp = await client.get(EVENTS_URL.format(company_id=company_id))
        resp.raise_for_status()
        events = resp.json().get("data", [])
        with_transcript = [e for e in events if e.get("transcriptUrl")]
        return with_transcript[: self._limit]

    async def _download_transcript(
        self,
        client: httpx.AsyncClient,
        event: dict,
        out_dir: Path,
        ticker: str,
    ) -> DownloadedArtifact | None:
        url = event["transcriptUrl"]
        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Quartr transcript 下载失败 %s: %s", url, exc)
            return None

        period = event.get("fiscalPeriod") or event.get("eventDate") or ""
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = _filename_from_url(url, default="transcript.pdf")
        prefix = _safe_segment(period)
        file_path = out_dir / (f"{prefix}_{filename}" if prefix else filename)
        content = resp.content
        file_path.write_bytes(content)

        return DownloadedArtifact(
            source=self.name,
            doc_type="transcript",
            file_path=str(file_path),
            title=f"{ticker} {period} 财报电话会转录".strip(),
            url=url,
            period=period or None,
            bytes_written=len(content),
            raw_meta={
                "event_id": event.get("id"),
                "event_date": event.get("eventDate"),
                "fiscal_period": event.get("fiscalPeriod"),
            },
        )
