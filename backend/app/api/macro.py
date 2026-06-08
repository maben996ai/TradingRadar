from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.models import User
from app.schemas.schemas import MacroDashboardResponse, MacroRefreshResponse
from app.services.macro.fred_client import FredApiError
from app.services.macro.service import build_dashboard, refresh_all

router = APIRouter()


@router.get("/indicators", response_model=MacroDashboardResponse)
async def list_macro_indicators(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MacroDashboardResponse:
    indicators = await build_dashboard(db)
    return MacroDashboardResponse(indicators=indicators)


@router.post("/refresh", response_model=MacroRefreshResponse)
async def refresh_macro_indicators(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MacroRefreshResponse:
    try:
        inserted = await refresh_all(db)
    except FredApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return MacroRefreshResponse(inserted=inserted)
