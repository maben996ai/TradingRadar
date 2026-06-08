from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.models import TrackedTicker, User
from app.schemas.schemas import (
    CalendarEventListResponse,
    CalendarEventResponse,
    CalendarRefreshResponse,
    TrackedTickerCreate,
    TrackedTickerResponse,
)
from app.services.calendar.service import list_events, refresh_all

router = APIRouter()


@router.get("/events", response_model=CalendarEventListResponse)
async def get_events(
    start: datetime = Query(...),
    end: datetime = Query(...),
    categories: list[str] | None = Query(default=None),
    importance: int | None = Query(default=None, ge=1, le=3),
    kind: str | None = Query(default=None),
    tracked_only: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CalendarEventListResponse:
    rows = await list_events(
        db,
        start,
        end,
        categories=categories,
        importance_min=importance,
        kind=kind,
        user_id=current_user.id,
        tracked_only=tracked_only,
    )
    return CalendarEventListResponse(
        events=[CalendarEventResponse.model_validate(r) for r in rows]
    )


@router.post("/refresh", response_model=CalendarRefreshResponse)
async def refresh_calendar(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CalendarRefreshResponse:
    inserted = await refresh_all(db)
    return CalendarRefreshResponse(inserted=inserted)


@router.get("/tracked-tickers", response_model=list[TrackedTickerResponse])
async def list_tracked_tickers(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TrackedTicker]:
    rows = await db.scalars(
        select(TrackedTicker).where(TrackedTicker.user_id == current_user.id)
    )
    return list(rows)


@router.post("/tracked-tickers", response_model=TrackedTickerResponse, status_code=201)
async def create_tracked_ticker(
    payload: TrackedTickerCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TrackedTicker:
    ticker = payload.ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker required")
    existing = await db.scalar(
        select(TrackedTicker).where(
            TrackedTicker.user_id == current_user.id, TrackedTicker.ticker == ticker
        )
    )
    if existing is not None:
        return existing
    row = TrackedTicker(
        user_id=current_user.id, ticker=ticker, company_name=payload.company_name
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.delete("/tracked-tickers/{ticker_id}", status_code=204)
async def delete_tracked_ticker(
    ticker_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    row = await db.scalar(
        select(TrackedTicker).where(
            TrackedTicker.id == ticker_id, TrackedTicker.user_id == current_user.id
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Tracked ticker not found")
    await db.delete(row)
    await db.commit()
