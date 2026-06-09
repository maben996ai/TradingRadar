"""FMP（Financial Modeling Prep）适配器：下载三大报表 / 估值比率 / 关键指标 / 分析师预期 JSON 落盘。

按「每个数据源一个适配器」，FMP 统一在此适配器，通过 ``datasets`` 选择数据集分组：
- ``statements``：利润表 / 资产负债表 / 现金流量表
- ``metrics``：财务比率（PE/PS/毛利率等）/ 关键指标（EV-EBITDA/ROIC/FCF 等）
- ``estimates``：分析师预期（营收/EPS 等）

未配置 ``FMP_API_KEY`` 时跳过（``skipped=True``）。单个 endpoint 失败或空数据不影响其余。
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

BASE_URL = "https://financialmodelingprep.com/stable"
REQUEST_TIMEOUT = 20.0

# 数据集分组 -> endpoint 列表（保持顺序）
DATASETS: dict[str, tuple[str, ...]] = {
    "statements": (
        "income-statement",
        "balance-sheet-statement",
        "cash-flow-statement",
    ),
    "metrics": ("ratios", "key-metrics"),
    "estimates": ("analyst-estimates",),
}
DEFAULT_DATASETS = tuple(DATASETS.keys())

ENDPOINT_TITLES = {
    "income-statement": "利润表",
    "balance-sheet-statement": "资产负债表",
    "cash-flow-statement": "现金流量表",
    "ratios": "财务比率",
    "key-metrics": "关键指标",
    "analyst-estimates": "分析师预期",
}


class FmpAdapter(BaseFundamentalsAdapter):
    name = "fmp"

    def __init__(
        self,
        api_key: str | None = None,
        period: str = "annual",
        limit: int = 5,
        datasets: list[str] | tuple[str, ...] | None = None,
    ) -> None:
        self._api_key = api_key
        self._period = period
        self._limit = limit
        selected = tuple(datasets) if datasets is not None else DEFAULT_DATASETS
        self._endpoints = [ep for group in selected for ep in DATASETS.get(group, ())]

    def _resolve_api_key(self) -> str:
        if self._api_key is not None:
            return self._api_key
        return get_settings().fmp_api_key

    async def download(self, ticker: str, dest_dir: Path) -> DownloadOutcome:
        api_key = self._resolve_api_key()
        if not api_key:
            return DownloadOutcome(
                source=self.name,
                skipped=True,
                message="FMP_API_KEY 未配置",
            )

        ticker = ticker.strip().upper()
        out_dir = Path(dest_dir) / self.name
        out_dir.mkdir(parents=True, exist_ok=True)
        params = {
            "symbol": ticker,
            "period": self._period,
            "limit": self._limit,
            "apikey": api_key,
        }

        artifacts: list[DownloadedArtifact] = []
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            for endpoint in self._endpoints:
                artifact = await self._download_endpoint(client, endpoint, params, out_dir, ticker)
                if artifact is not None:
                    artifacts.append(artifact)

        return DownloadOutcome(source=self.name, artifacts=artifacts)

    async def _download_endpoint(
        self,
        client: httpx.AsyncClient,
        endpoint: str,
        params: dict,
        out_dir: Path,
        ticker: str,
    ) -> DownloadedArtifact | None:
        try:
            resp = await client.get(f"{BASE_URL}/{endpoint}", params=params)
            resp.raise_for_status()
            rows = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("FMP %s 拉取失败 %s: %s", endpoint, ticker, exc)
            return None

        if not isinstance(rows, list) or not rows:
            return None

        content = json.dumps(rows, ensure_ascii=False, indent=2).encode("utf-8")
        file_path = out_dir / f"{endpoint}.json"
        file_path.write_bytes(content)

        return DownloadedArtifact(
            source=self.name,
            doc_type=endpoint,
            file_path=str(file_path),
            title=f"{ticker} {ENDPOINT_TITLES.get(endpoint, endpoint)}",
            url=f"{BASE_URL}/{endpoint}?symbol={ticker}",
            period=self._period,
            bytes_written=len(content),
            raw_meta={"records": len(rows)},
        )
