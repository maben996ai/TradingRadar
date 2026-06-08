"""宏观看板服务：刷新 FRED 观测、构建看板数据。"""

import logging
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.models import MacroObservation
from app.services.macro.fred_client import fetch_observations
from app.services.macro.indicators import INDICATORS, MacroIndicator

logger = logging.getLogger(__name__)

# 拉取/保留约 3.2 年，覆盖前端 3Y 区间并为「前值」留缓冲
LOOKBACK_DAYS = 365 * 3 + 90


def _observation_start() -> str:
    return (datetime.now(UTC).date() - timedelta(days=LOOKBACK_DAYS)).isoformat()


async def _upsert_indicator(
    db: AsyncSession, indicator: MacroIndicator, points: list[tuple[date, float]]
) -> int:
    existing = {
        row.date: row
        for row in await db.scalars(
            select(MacroObservation).where(MacroObservation.indicator_key == indicator.key)
        )
    }
    inserted = 0
    for obs_date, value in points:
        row = existing.get(obs_date)
        if row is None:
            db.add(
                MacroObservation(indicator_key=indicator.key, date=obs_date, value=value)
            )
            inserted += 1
        elif row.value != value:
            row.value = value
    return inserted


async def refresh_all(db: AsyncSession) -> int:
    """从 FRED 拉取所有指标观测并入库，返回新增观测条数。"""
    api_key = get_settings().fred_api_key
    observation_start = _observation_start()
    total_inserted = 0
    for indicator in INDICATORS:
        points = await fetch_observations(
            series_id=indicator.series_id,
            units=indicator.units,
            observation_start=observation_start,
            api_key=api_key,
        )
        if not points:
            logger.warning("FRED 指标 %s 无观测返回", indicator.key)
            continue
        total_inserted += await _upsert_indicator(db, indicator, points)
    await db.commit()
    return total_inserted


async def build_dashboard(db: AsyncSession) -> list[dict]:
    """构建看板：每指标的最新值/前值/变化/判断/理由 + 完整序列。"""
    window_start = datetime.now(UTC).date() - timedelta(days=365 * 3)
    dashboard: list[dict] = []
    for indicator in INDICATORS:
        rows = list(
            await db.scalars(
                select(MacroObservation)
                .where(
                    MacroObservation.indicator_key == indicator.key,
                    MacroObservation.date >= window_start,
                )
                .order_by(MacroObservation.date.asc())
            )
        )
        if not rows:
            continue

        latest_row = rows[-1]
        previous_row = rows[-2] if len(rows) >= 2 else None
        latest = latest_row.value

        if previous_row is None:
            judgment = "neutral"
            change_abs = None
            change_pct = None
            previous = None
        else:
            previous = previous_row.value
            change_abs = latest - previous
            change_pct = (change_abs / abs(previous) * 100) if previous != 0 else None
            judgment = indicator.judge(latest, previous)

        dashboard.append(
            {
                "key": indicator.key,
                "category": indicator.category,
                "name": indicator.name,
                "name_en": indicator.name_en,
                "unit_label": indicator.unit_label,
                "decimals": indicator.decimals,
                "source": indicator.source,
                "explanation": indicator.explanation,
                "latest": latest,
                "previous": previous,
                "change_abs": change_abs,
                "change_pct": change_pct,
                "updated_at": latest_row.date,
                "judgment": judgment,
                "reason": indicator.reason(judgment),
                "high": indicator.high,
                "low": indicator.low,
                "high_note": indicator.high_note,
                "low_note": indicator.low_note,
                "zone": indicator.zone(latest),
                "forecast": indicator.forecast,
                "forecast_label": indicator.forecast_label,
                "forecast_source": indicator.forecast_source,
                "series": [{"date": r.date, "value": r.value} for r in rows],
            }
        )
    return dashboard
