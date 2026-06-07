import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import AsyncSessionLocal, get_db
from app.models.models import ContentType, CrawlLog, CrawlLogStatus, DataSource, User
from app.schemas.schemas import DataSourceCreate, DataSourceResponse, DataSourceUpdate
from app.services.resolver import resolve_source
from app.services.scheduler import crawl_source

router = APIRouter()
logger = logging.getLogger(__name__)


async def _run_initial_crawl(data_source_id: str) -> None:
    """后台任务：独立加载 DataSource，再执行首次抓取。"""
    async with AsyncSessionLocal() as db:
        source = await db.get(DataSource, data_source_id)
    if source is None:
        return
    try:
        await crawl_source(source)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Initial crawl failed for data_source=%s: %s", data_source_id, exc)
        # 记录失败日志，便于「控制中心」展示初始化失败原因（否则只会一直显示「初始化中」）
        async with AsyncSessionLocal() as db:
            db.add(
                CrawlLog(
                    data_source_id=data_source_id,
                    status=CrawlLogStatus.FAILED,
                    message=str(exc),
                    items_found=0,
                )
            )
            await db.commit()


@router.get("", response_model=list[DataSourceResponse])
async def list_data_sources(
    starred: bool | None = Query(default=None),
    content_type: ContentType | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DataSource]:
    stmt = (
        select(DataSource)
        .where(DataSource.user_id == current_user.id)
        .order_by(DataSource.created_at.desc())
    )
    if starred is not None:
        stmt = stmt.where(DataSource.starred == starred)
    if content_type is not None:
        stmt = stmt.where(DataSource.content_type == content_type)
    result = await db.scalars(stmt)
    return list(result)


@router.post("", response_model=DataSourceResponse, status_code=status.HTTP_201_CREATED)
async def create_data_source(
    payload: DataSourceCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DataSource:
    try:
        source_type, resolved = await resolve_source(payload.url)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    existing = await db.scalar(
        select(DataSource).where(
            DataSource.user_id == current_user.id,
            DataSource.source_type == source_type,
            DataSource.external_id == resolved.platform_id,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Data source already exists",
        )

    source = DataSource(
        user_id=current_user.id,
        source_type=source_type,
        external_id=resolved.platform_id,
        name=resolved.name,
        profile_url=resolved.profile_url,
        avatar_url=resolved.avatar_url,
        note=payload.note,
        content_type=payload.content_type,
        source_config=payload.source_config,
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)

    background_tasks.add_task(_run_initial_crawl, source.id)
    return source


@router.patch("/{data_source_id}", response_model=DataSourceResponse)
async def update_data_source(
    data_source_id: str,
    payload: DataSourceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DataSource:
    source = await db.scalar(
        select(DataSource).where(
            DataSource.id == data_source_id,
            DataSource.user_id == current_user.id,
        )
    )
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data source not found")

    source.note = payload.note
    source.category = payload.category
    if payload.starred is not None:
        source.starred = payload.starred
    if payload.content_type is not None:
        source.content_type = payload.content_type
    if payload.source_config is not None:
        source.source_config = payload.source_config
    await db.commit()
    await db.refresh(source)
    return source


@router.delete("/{data_source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_data_source(
    data_source_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    source = await db.scalar(
        select(DataSource).where(
            DataSource.id == data_source_id,
            DataSource.user_id == current_user.id,
        )
    )
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data source not found")

    await db.delete(source)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
