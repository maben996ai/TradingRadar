"""财经日历数据 provider（可插拔）。

- ``SeedProvider``：用精选发布日程在滚动窗口生成事件，过去宏观事件的 actual/previous 由 FRED 回填。
- ``TradingEconomicsProvider`` / ``FmpProvider``：真实拉取；未配置 API key 时返回空列表，便于平滑切换。
"""

import logging
from abc import ABC, abstractmethod
from calendar import monthrange
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from app.services.calendar.events import (
    DEFAULT_COMPANIES,
    FOMC_DECISION_DATES_2026,
    FOMC_PROJECTION_DATES_2026,
    MACRO_EVENTS,
    MacroEventDef,
)
from app.services.macro.fred_client import fetch_observations

logger = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")


def _to_utc(d: date, hour: int, minute: int) -> datetime:
    return datetime(d.year, d.month, d.day, hour, minute, tzinfo=ET).astimezone(UTC)


def _iter_months(start: date, end: date):
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        m += 1
        if m > 12:
            m, y = 1, y + 1


def _shift_to_weekday(d: date) -> date:
    while d.weekday() >= 5:  # 周六/周日顺延到下一工作日
        d += timedelta(days=1)
    return d


def _nth_weekday(year: int, month: int, weekday: int, nth: int) -> date:
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + (nth - 1) * 7)


def _day_of_month(year: int, month: int, day: int) -> date:
    last = monthrange(year, month)[1]
    return _shift_to_weekday(date(year, month, min(day, last)))


def _generate_dates(d: MacroEventDef, ws: date, we: date) -> list[date]:
    out: list[date] = []
    if d.schedule_kind == "nth_weekday":
        for y, m in _iter_months(ws, we):
            day = _nth_weekday(y, m, d.schedule_arg, d.schedule_nth)
            if ws <= day <= we:
                out.append(day)
    elif d.schedule_kind == "dom":
        for y, m in _iter_months(ws, we):
            day = _day_of_month(y, m, d.schedule_arg)
            if ws <= day <= we:
                out.append(day)
    elif d.schedule_kind == "quarterly_dom":
        for y, m in _iter_months(ws, we):
            if m in (1, 4, 7, 10):
                day = _day_of_month(y, m, d.schedule_arg)
                if ws <= day <= we:
                    out.append(day)
    elif d.schedule_kind == "weekly":
        cur = ws + timedelta(days=(d.schedule_arg - ws.weekday()) % 7)
        while cur <= we:
            out.append(cur)
            cur += timedelta(days=7)
    return out


def _explicit_dates(key: str) -> list[date]:
    if key in ("fomc_decision", "fomc_presser", "fomc_dots"):
        src = FOMC_PROJECTION_DATES_2026 if key == "fomc_dots" else FOMC_DECISION_DATES_2026
        return [date(2026, m, dd) for m, dd in src]
    if key == "fomc_minutes":
        return [date(2026, m, dd) + timedelta(days=21) for m, dd in FOMC_DECISION_DATES_2026]
    return []


DEFAULT_COMPANY_IMPORTANCE = {c.ticker: c.importance for c in DEFAULT_COMPANIES}


class CalendarProvider(ABC):
    @abstractmethod
    async def fetch_macro(self, start: datetime, end: datetime) -> list[dict]: ...

    @abstractmethod
    async def fetch_earnings(
        self, start: datetime, end: datetime, symbols: dict[str, str]
    ) -> list[dict]: ...


class SeedProvider(CalendarProvider):
    def __init__(self, fred_api_key: str = "") -> None:
        self._fred_api_key = fred_api_key

    async def fetch_macro(self, start: datetime, end: datetime) -> list[dict]:
        ws, we = start.date(), end.date()
        now = datetime.now(UTC)
        events: list[dict] = []
        by_def: dict[str, list[dict]] = {}

        for d in MACRO_EVENTS:
            dates = (
                _explicit_dates(d.key)
                if d.schedule_kind == "explicit"
                else _generate_dates(d, ws, we)
            )
            instances = []
            for day in dates:
                if not (ws <= day <= we):
                    continue
                ev = {
                    "event_key": f"{d.key}_{day.isoformat()}",
                    "kind": "macro",
                    "category": d.category,
                    "title": d.title,
                    "title_en": d.title_en,
                    "country": "US",
                    "scheduled_at": _to_utc(day, d.hour_et, d.minute_et),
                    "all_day": False,
                    "importance": d.importance,
                    "impact_assets": d.impact_assets,
                    "previous": None,
                    "forecast": None,
                    "actual": None,
                    "value_unit": d.value_unit,
                    "ticker": None,
                    "company_name": None,
                    "source": "精选",
                }
                instances.append(ev)
            by_def[d.key] = instances
            events.extend(instances)

        # 过去宏观事件用 FRED 回填真实 actual/previous
        if self._fred_api_key:
            for d in MACRO_EVENTS:
                await self._backfill(d, by_def[d.key], now)

        return events

    async def _backfill(self, d: MacroEventDef, instances: list[dict], now: datetime) -> None:
        if not d.fred_series:
            return
        try:
            obs = await fetch_observations(
                series_id=d.fred_series,
                units=d.fred_units,
                observation_start=(now.date() - timedelta(days=900)).isoformat(),
                api_key=self._fred_api_key,
            )
        except Exception as exc:  # 回填失败不阻塞日历生成
            logger.warning("Calendar FRED backfill failed for %s: %s", d.key, exc)
            return
        if not obs:
            return
        past = sorted((e for e in instances if e["scheduled_at"] < now), key=lambda e: e["scheduled_at"])
        for i, ev in enumerate(reversed(past)):  # i=0 为最近一次发布，对齐最新观测
            ai = len(obs) - 1 - i
            if ai < 0:
                break
            ev["actual"] = obs[ai][1]
            ev["source"] = "FRED"
            if ai >= 1:
                ev["previous"] = obs[ai - 1][1]

    async def fetch_earnings(
        self, start: datetime, end: datetime, symbols: dict[str, str] | None = None
    ) -> list[dict]:
        ws, we = start.date(), end.date()
        span = max((we - ws).days, 1)
        n = len(DEFAULT_COMPANIES)
        events: list[dict] = []
        for i, c in enumerate(DEFAULT_COMPANIES):
            day = _shift_to_weekday(ws + timedelta(days=int(span * (i + 1) / (n + 1))))
            events.append(
                {
                    "event_key": f"earnings_{c.ticker}_{day.isoformat()}",
                    "kind": "earnings",
                    "category": "earnings",
                    "title": f"{c.name} 财报",
                    "title_en": f"{c.ticker} Earnings",
                    "country": "US",
                    "scheduled_at": _to_utc(day, 16, 0),  # 美东盘后
                    "all_day": False,
                    "importance": c.importance,
                    "impact_assets": c.ticker,
                    "previous": None,
                    "forecast": None,
                    "actual": None,
                    "value_unit": None,
                    "ticker": c.ticker,
                    "company_name": c.name,
                    "source": "精选",
                }
            )
        return events


class TradingEconomicsProvider(CalendarProvider):
    """Trading Economics 宏观日历（需付费 key 才覆盖美国预期/实际值）。"""

    BASE = "https://api.tradingeconomics.com/calendar/country/united states"
    IMPORTANCE_MAP = {1: 1, 2: 2, 3: 3}

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def fetch_macro(self, start: datetime, end: datetime) -> list[dict]:
        if not self._api_key:
            return []
        params = {
            "c": self._api_key,
            "d1": start.date().isoformat(),
            "d2": end.date().isoformat(),
            "format": "json",
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(self.BASE, params=params)
                resp.raise_for_status()
                rows = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("TradingEconomics fetch failed: %s", exc)
            return []
        return [self._map(r) for r in rows if r.get("Date")]

    def _map(self, r: dict) -> dict:
        when = datetime.fromisoformat(r["Date"].replace("Z", "+00:00"))
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        return {
            "event_key": f"te_{r.get('CalendarId') or r['Date']}_{r.get('Event', '')}",
            "kind": "macro",
            "category": "growth",
            "title": r.get("Event", ""),
            "title_en": r.get("Event", ""),
            "country": "US",
            "scheduled_at": when.astimezone(UTC),
            "all_day": False,
            "importance": self.IMPORTANCE_MAP.get(int(r.get("Importance", 1) or 1), 1),
            "impact_assets": None,
            "previous": _to_float(r.get("Previous")),
            "forecast": _to_float(r.get("Forecast")),
            "actual": _to_float(r.get("Actual")),
            "value_unit": r.get("Unit"),
            "ticker": None,
            "company_name": None,
            "source": "Trading Economics",
        }

    async def fetch_earnings(
        self, start: datetime, end: datetime, symbols: dict[str, str] | None = None
    ) -> list[dict]:
        return []


class FmpProvider(CalendarProvider):
    """Financial Modeling Prep 财报（stable/earnings 按代码逐个拉取真实财报日与 EPS）。"""

    EARNINGS_URL = "https://financialmodelingprep.com/stable/earnings"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def fetch_macro(self, start: datetime, end: datetime) -> list[dict]:
        return []

    async def fetch_earnings(
        self, start: datetime, end: datetime, symbols: dict[str, str] | None = None
    ) -> list[dict]:
        if not self._api_key or not symbols:
            return []
        ws, we = start.date(), end.date()
        events: list[dict] = []
        async with httpx.AsyncClient(timeout=20.0) as client:
            for ticker, name in symbols.items():
                try:
                    resp = await client.get(
                        self.EARNINGS_URL,
                        params={"symbol": ticker, "apikey": self._api_key},
                    )
                    resp.raise_for_status()
                    rows = resp.json()
                except (httpx.HTTPError, ValueError) as exc:
                    logger.warning("FMP earnings fetch failed for %s: %s", ticker, exc)
                    continue
                if not isinstance(rows, list):
                    continue
                for r in rows:
                    day = r.get("date")
                    if not day:
                        continue
                    try:
                        d = date.fromisoformat(day)
                    except ValueError:
                        continue
                    if not (ws <= d <= we):
                        continue
                    events.append(
                        {
                            "event_key": f"earnings_{ticker}_{day}",
                            "kind": "earnings",
                            "category": "earnings",
                            "title": f"{name} 财报",
                            "title_en": f"{ticker} Earnings",
                            "country": "US",
                            "scheduled_at": _to_utc(d, 16, 0),
                            "all_day": False,
                            "importance": DEFAULT_COMPANY_IMPORTANCE.get(ticker, 2),
                            "impact_assets": ticker,
                            "previous": None,
                            "forecast": _to_float(r.get("epsEstimated")),
                            "actual": _to_float(r.get("epsActual")),
                            "value_unit": "EPS",
                            "ticker": ticker,
                            "company_name": name,
                            "source": "FMP",
                        }
                    )
        return events


def _to_float(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
