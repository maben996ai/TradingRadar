"""标的研报检索 API（按源粒度，前端逐源调用以展示进度）。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.models import User
from app.schemas.schemas import (
    ResearchItem,
    ResearchResolveResponse,
    ResearchSource,
    ResearchSourceResult,
)
from app.services.research.service import (
    LOOKBACK_DAYS,
    TickerNotFound,
    list_sources,
    resolve_company_name,
    search_source,
)

router = APIRouter()


@router.get("/sources", response_model=list[ResearchSource])
async def get_sources(current_user: User = Depends(get_current_user)) -> list[ResearchSource]:
    return [ResearchSource(**s) for s in list_sources()]


@router.get("/resolve", response_model=ResearchResolveResponse)
async def resolve_ticker(
    ticker: str = Query(..., min_length=1, max_length=10),
    current_user: User = Depends(get_current_user),
) -> ResearchResolveResponse:
    try:
        name = await resolve_company_name(ticker)
    except TickerNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ResearchResolveResponse(
        ticker=ticker.strip().upper(), company_name=name, lookback_days=LOOKBACK_DAYS
    )


@router.get("/search", response_model=ResearchSourceResult)
async def search_one_source(
    ticker: str = Query(..., min_length=1, max_length=10),
    source_key: str = Query(..., min_length=1),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResearchSourceResult:
    if source_key not in {s["key"] for s in list_sources()}:
        raise HTTPException(status_code=404, detail="Unknown source")
    try:
        result = await search_source(db, ticker, source_key)
    except TickerNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ResearchSourceResult(
        items=[ResearchItem(**item) for item in result["items"]],
        error=result["error"],
    )
