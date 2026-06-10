from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from app.api.deps import get_current_user
from app.models.models import User
from app.schemas.schemas import (
    FundamentalsArtifactResponse,
    FundamentalsDownloadRequest,
    FundamentalsDownloadResponse,
    FundamentalsSourceInfo,
    FundamentalsSourceResult,
)
from app.services.fundamentals.registry import fundamentals_registry
from app.services.fundamentals.service import download_fundamentals, fundamentals_base_dir

router = APIRouter()


@router.get("/sources", response_model=list[FundamentalsSourceInfo])
async def list_sources(
    current_user: User = Depends(get_current_user),
) -> list[FundamentalsSourceInfo]:
    return [FundamentalsSourceInfo(name=name) for name in fundamentals_registry.names()]


@router.post("/download", response_model=FundamentalsDownloadResponse)
async def download(
    payload: FundamentalsDownloadRequest,
    current_user: User = Depends(get_current_user),
) -> FundamentalsDownloadResponse:
    ticker = payload.ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker required")

    unknown = [s for s in (payload.sources or []) if s not in fundamentals_registry.names()]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown sources: {', '.join(unknown)}")

    outcomes = await download_fundamentals(ticker=ticker, sources=payload.sources)
    results = [
        FundamentalsSourceResult(
            source=o.source,
            skipped=o.skipped,
            message=o.message,
            artifacts=[FundamentalsArtifactResponse.model_validate(a) for a in o.artifacts],
        )
        for o in outcomes
    ]
    return FundamentalsDownloadResponse(ticker=ticker, results=results)


@router.get("/files")
async def get_file(
    path: str = Query(...),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    base = fundamentals_base_dir().resolve()
    target = Path(path).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        raise HTTPException(status_code=403, detail="Path outside fundamentals directory") from None
    if not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(target, filename=target.name)
