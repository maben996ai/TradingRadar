"""个股分析数据源注册表。"""

from app.services.fundamentals.base import BaseFundamentalsAdapter
from app.services.fundamentals.finnhub import FinnhubAdapter
from app.services.fundamentals.fmp import FmpAdapter
from app.services.fundamentals.quartr import QuartrAdapter
from app.services.fundamentals.sec_edgar import SecEdgarAdapter


class FundamentalsRegistry:
    def __init__(self, adapters: list[BaseFundamentalsAdapter] | None = None) -> None:
        if adapters is None:
            adapters = [SecEdgarAdapter(), FmpAdapter(), FinnhubAdapter(), QuartrAdapter()]
        self._adapters: dict[str, BaseFundamentalsAdapter] = {a.name: a for a in adapters}

    def get(self, name: str) -> BaseFundamentalsAdapter:
        return self._adapters[name]

    def names(self) -> tuple[str, ...]:
        return tuple(self._adapters.keys())

    def all(self) -> tuple[BaseFundamentalsAdapter, ...]:
        return tuple(self._adapters.values())


fundamentals_registry = FundamentalsRegistry()
