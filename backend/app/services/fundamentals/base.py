"""个股分析（fundamentals）数据源适配器基类与下载产物模型。

沿用 crawlers 的适配器架构：每个数据源一个适配器，统一在 registry 注册。
适配器职责是「拉取原始披露 / 报表文件并落盘」，返回落盘清单 ``DownloadOutcome``。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DownloadedArtifact:
    """单个落盘文件的元信息。"""

    source: str  # 数据源 key，如 sec_edgar / fmp
    doc_type: str  # 文档类型，如 10-K / income-statement
    file_path: str  # 落盘绝对路径
    title: str  # 人类可读标题
    url: str | None = None  # 原始来源 URL（如有）
    period: str | None = None  # 报告期 / 申报日（如有）
    bytes_written: int = 0
    raw_meta: dict = field(default_factory=dict)


@dataclass
class DownloadOutcome:
    """单个数据源一次下载的汇总结果。"""

    source: str
    artifacts: list[DownloadedArtifact] = field(default_factory=list)
    skipped: bool = False  # 因缺少 API key / User-Agent 等被跳过
    message: str | None = None


class BaseFundamentalsAdapter(ABC):
    """个股分析数据源适配器基类。"""

    name: str

    @abstractmethod
    async def download(self, ticker: str, dest_dir: Path) -> DownloadOutcome:
        """拉取 ``ticker`` 的原始文件落盘到 ``dest_dir``，返回落盘清单。"""
        raise NotImplementedError
