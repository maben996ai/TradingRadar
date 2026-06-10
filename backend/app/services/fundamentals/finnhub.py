"""Finnhub 适配器：下载分析师推荐趋势与目标价，作分析师预期备选源。

未配置 ``FINNHUB_API_KEY`` 时跳过（``skipped=True``）。单个 endpoint 失败或空数据不影响其余。
"""

import json
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

BASE_URL = "https://finnhub.io/api/v1"
REQUEST_TIMEOUT = 20.0

# (落盘名, endpoint 路径, 标题)
ENDPOINTS = (
    ("recommendation", "stock/recommendation", "分析师推荐趋势"),
    ("price-target", "stock/price-target", "目标价"),
)


class FinnhubAdapter(BaseFundamentalsAdapter):
    name = "finnhub"

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key

    def _resolve_api_key(self) -> str:
        if self._api_key is not None:
            return self._api_key
        return get_settings().finnhub_api_key

    async def download(self, ticker: str, dest_dir: Path) -> DownloadOutcome:
        api_key = self._resolve_api_key()
        if not api_key:
            return DownloadOutcome(
                source=self.name,
                skipped=True,
                message="FINNHUB_API_KEY 未配置",
            )

        ticker = ticker.strip().upper()
        out_dir = Path(dest_dir) / self.name
        out_dir.mkdir(parents=True, exist_ok=True)

        artifacts: list[DownloadedArtifact] = []
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            for name, endpoint, title in ENDPOINTS:
                artifact = await self._download_endpoint(
                    client, name, endpoint, title, api_key, out_dir, ticker
                )
                if artifact is not None:
                    artifacts.append(artifact)

        return DownloadOutcome(source=self.name, artifacts=artifacts)

    async def _download_endpoint(
        self,
        client: httpx.AsyncClient,
        name: str,
        endpoint: str,
        title: str,
        api_key: str,
        out_dir: Path,
        ticker: str,
    ) -> DownloadedArtifact | None:
        try:
            resp = await client.get(
                f"{BASE_URL}/{endpoint}",
                params={"symbol": ticker, "token": api_key},
            )
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Finnhub %s 拉取失败 %s: %s", endpoint, ticker, exc)
            return None

        # recommendation 返回 list，price-target 返回 dict；二者皆需非空
        if not data:
            return None

        content = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        file_path = out_dir / f"{name}.json"
        file_path.write_bytes(content)

        records = len(data) if isinstance(data, list) else 1
        return DownloadedArtifact(
            source=self.name,
            doc_type=name,
            file_path=str(file_path),
            title=f"{ticker} {title}",
            url=f"{BASE_URL}/{endpoint}?symbol={ticker}",
            bytes_written=len(content),
            raw_meta={"records": records},
        )
