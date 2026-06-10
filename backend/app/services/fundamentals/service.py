"""个股分析下载编排：按数据源逐个落盘到 ``<base_dir>/<TICKER>/<source>/`` 下。"""

from pathlib import Path

from app.core.config import get_settings
from app.services.fundamentals.base import DownloadOutcome
from app.services.fundamentals.registry import FundamentalsRegistry, fundamentals_registry

# 以 backend 目录为基准（本文件位于 backend/app/services/fundamentals/service.py）。
# 这样本地与 Docker（./backend 挂载到 /app）下都落在 backend/data 卷内，可持久化。
_BACKEND_DIR = Path(__file__).resolve().parents[3]
DEFAULT_DIR = _BACKEND_DIR / "data" / "fundamentals"


def _resolve_base_dir(base_dir: str | Path | None) -> Path:
    if base_dir:
        return Path(base_dir)
    configured = get_settings().fundamentals_dir
    return Path(configured) if configured else DEFAULT_DIR


def fundamentals_base_dir() -> Path:
    """落盘根目录（用于文件下发时校验路径在此目录内）。"""
    return _resolve_base_dir(None)


async def download_fundamentals(
    ticker: str,
    sources: list[str] | None = None,
    base_dir: str | Path | None = None,
    registry: FundamentalsRegistry | None = None,
) -> list[DownloadOutcome]:
    """对 ``ticker`` 逐个数据源下载原始文件，返回每个数据源的落盘结果。"""
    normalized = ticker.strip().upper()
    if not normalized:
        raise ValueError("ticker 不能为空")

    registry = registry or fundamentals_registry
    names = tuple(sources) if sources else registry.names()
    dest = _resolve_base_dir(base_dir) / normalized

    outcomes: list[DownloadOutcome] = []
    for name in names:
        adapter = registry.get(name)
        outcomes.append(await adapter.download(normalized, dest))
    return outcomes
