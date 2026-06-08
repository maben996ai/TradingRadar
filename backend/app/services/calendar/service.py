"""财经日历服务：刷新事件、按筛选列出事件。"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.models import CalendarEvent, TrackedTicker
from app.services.calendar.events import DEFAULT_COMPANIES
from app.services.calendar.provider import (
    FmpProvider,
    SeedProvider,
    TradingEconomicsProvider,
)

logger = logging.getLogger(__name__)

WINDOW_PAST_DAYS = 30
WINDOW_FUTURE_DAYS = 60
# FMP 免费版约 250 请求/天；每次刷新对每个代码 1 次调用，故限制单次拉取的代码数
MAX_EARNINGS_SYMBOLS = 120


async def _earnings_symbols(db: AsyncSession) -> dict[str, str]:
    """默认重点公司 ∪ 用户已关注代码 → {ticker: 展示名}；按上限截断以保护 FMP 免费额度。

    默认重点公司优先保留，其余关注代码按先到先得补足到 ``MAX_EARNINGS_SYMBOLS``。
    """
    symbols = {c.ticker: c.name for c in DEFAULT_COMPANIES}
    rows = await db.execute(
        select(TrackedTicker.ticker, TrackedTicker.company_name).order_by(
            TrackedTicker.created_at.asc()
        )
    )
    for ticker, name in rows.all():
        if len(symbols) >= MAX_EARNINGS_SYMBOLS:
            break
        symbols.setdefault(ticker, name or ticker)
    return symbols


async def refresh_all(db: AsyncSession) -> int:
    """按可用 key 选择 provider，重建窗口内事件，返回事件总数。

    采用「删除窗口内旧事件 + 重新插入」策略，避免占位/改期产生重复或残留。
    """
    settings = get_settings()
    now = datetime.now(UTC)
    start = now - timedelta(days=WINDOW_PAST_DAYS)
    end = now + timedelta(days=WINDOW_FUTURE_DAYS)

    seed = SeedProvider(fred_api_key=settings.fred_api_key)
    macro_provider = (
        TradingEconomicsProvider(settings.trading_economics_api_key)
        if settings.trading_economics_api_key
        else seed
    )
    earnings_provider = FmpProvider(settings.fmp_api_key) if settings.fmp_api_key else seed

    symbols = await _earnings_symbols(db)
    events = await macro_provider.fetch_macro(start, end)
    events += await earnings_provider.fetch_earnings(start, end, symbols)

    # 去掉同批次重复 event_key（避免唯一约束冲突）
    deduped: dict[str, dict] = {}
    for e in events:
        deduped[e["event_key"]] = e
    events = list(deduped.values())

    # 删除窗口略放宽，确保本批将重建的事件先被清掉（避免 event_key 唯一冲突）
    await db.execute(
        delete(CalendarEvent).where(
            CalendarEvent.scheduled_at >= start - timedelta(days=2),
            CalendarEvent.scheduled_at <= end + timedelta(days=2),
        )
    )
    for e in events:
        db.add(CalendarEvent(**e))
    await db.commit()
    return len(events)


async def list_events(
    db: AsyncSession,
    start: datetime,
    end: datetime,
    *,
    categories: list[str] | None = None,
    importance_min: int | None = None,
    kind: str | None = None,
    user_id: str | None = None,
    tracked_only: bool = False,
) -> list[CalendarEvent]:
    stmt = (
        select(CalendarEvent)
        .where(CalendarEvent.scheduled_at >= start, CalendarEvent.scheduled_at <= end)
        .order_by(CalendarEvent.scheduled_at.asc())
    )
    if categories:
        stmt = stmt.where(CalendarEvent.category.in_(categories))
    if importance_min:
        stmt = stmt.where(CalendarEvent.importance >= importance_min)
    if kind:
        stmt = stmt.where(CalendarEvent.kind == kind)

    rows = list(await db.scalars(stmt))

    if tracked_only and user_id:
        tracked = set(
            await db.scalars(
                select(TrackedTicker.ticker).where(TrackedTicker.user_id == user_id)
            )
        )
        rows = [r for r in rows if r.kind != "earnings" or r.ticker in tracked]

    return rows
