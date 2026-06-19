"""内容分析 API：粘贴 YouTube URL 下载音/视频、Whisper 转写文本、产物管理。

移植自 yt-dlp-x 后端，遵循 TradingRadar 分层：路由仅做入口，逻辑在 services。
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.models import ArtifactStatus, ArtifactType, User
from app.schemas.schemas import (
    AnalysisActionResponse,
    AnalysisArtifactResponse,
    AnalysisDownloadRequest,
    AnalysisListResponse,
    AnalysisLoginBrowserRequest,
    AnalysisLoginCookiesRequest,
    AnalysisLoginResponse,
    AnalysisSourceResponse,
    AnalysisStatusResponse,
)
from app.services.content_analysis import backends, cookies, runner, store

router = APIRouter()

TEXT_EXT = store.TEXT_EXT


def _artifact_response(art) -> AnalysisArtifactResponse:
    resp = AnalysisArtifactResponse.model_validate(art)
    # 运行中的产物叠加内存里的实时进度。
    if art.status in (ArtifactStatus.RUNNING, ArtifactStatus.PROCESSING):
        live = runner.live_progress(art.id)
        if live is not None:
            resp.progress = live
    return resp


@router.post("/download", response_model=AnalysisArtifactResponse)
async def download(
    payload: AnalysisDownloadRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisArtifactResponse:
    url = payload.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="请输入视频 URL")
    kind = ArtifactType.AUDIO if payload.mode == "audio" else ArtifactType.VIDEO
    src = await store.get_or_create_source(db, current_user.id, url)
    art = await store.create_artifact(db, src.id, kind)
    background_tasks.add_task(runner.run_download, art.id, src.id, url, kind.value)
    return _artifact_response(art)


@router.post("/artifacts/{aid}/transcribe", response_model=AnalysisArtifactResponse)
async def transcribe(
    aid: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisArtifactResponse:
    media, src = await store.get_artifact_owned(db, aid, current_user.id)
    if media is None:
        raise HTTPException(status_code=404, detail="找不到可转写的产物")
    if media.type not in (ArtifactType.AUDIO, ArtifactType.VIDEO):
        raise HTTPException(status_code=400, detail="只能转写音/视频产物")
    if media.status != ArtifactStatus.FINISHED or not media.filepath:
        raise HTTPException(status_code=400, detail="该产物尚未下载完成")
    if not backends.whisper_available():
        raise HTTPException(status_code=400, detail="音频转文本未启用：未安装 Whisper 后端")
    text_art = await store.create_artifact(
        db,
        src.id,
        ArtifactType.TEXT,
        source_artifact_id=media.id,
        meta={"model": backends.active_model_label()},
    )
    background_tasks.add_task(runner.run_transcribe, text_art.id, media.filepath, src.id)
    return _artifact_response(text_art)


@router.get("/artifacts", response_model=AnalysisListResponse)
async def list_artifacts(
    type: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisListResponse:
    type_filter = type if type in ("video", "audio", "text") else None
    order = {"video": 0, "audio": 1, "text": 2}
    sources = await store.list_sources(db, current_user.id, type_filter)
    out: list[AnalysisSourceResponse] = []
    for s in sources:
        arts = [a for a in s.artifacts if not type_filter or a.type == type_filter]
        arts.sort(key=lambda a: order.get(a.type, 9))
        out.append(
            AnalysisSourceResponse(
                id=s.id,
                url=s.url,
                title=s.title,
                author=s.author,
                created_at=s.created_at,
                artifacts=[_artifact_response(a) for a in arts],
            )
        )
    return AnalysisListResponse(sources=out, counts=await store.counts(db, current_user.id))


@router.get("/artifacts/{aid}/file")
async def artifact_file(
    aid: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    art, _src = await store.get_artifact_owned(db, aid, current_user.id)
    if art is None:
        raise HTTPException(status_code=404, detail="产物不存在")
    rp = store.safe_path(art.filepath)
    if rp is None:
        raise HTTPException(status_code=403, detail="文件路径越界")
    if not rp.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    if rp.suffix.lower() in TEXT_EXT:
        return PlainTextResponse(rp.read_text(encoding="utf-8"))
    return FileResponse(rp, filename=art.filename or rp.name)


@router.post("/artifacts/{aid}/cancel", response_model=AnalysisActionResponse)
async def cancel_artifact(
    aid: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisActionResponse:
    art, _src = await store.get_artifact_owned(db, aid, current_user.id)
    if art is None:
        raise HTTPException(status_code=404, detail="产物不存在")
    if art.status not in (
        ArtifactStatus.QUEUED,
        ArtifactStatus.RUNNING,
        ArtifactStatus.PROCESSING,
    ):
        return AnalysisActionResponse(ok=False, message="该任务无法终止（可能已完成）")
    runner.request_cancel(aid)
    if art.status == ArtifactStatus.QUEUED:
        await store.update_artifact(db, aid, status=ArtifactStatus.CANCELED, error="已终止")
    return AnalysisActionResponse(ok=True)


@router.delete("/artifacts/{aid}", response_model=AnalysisActionResponse)
async def delete_artifact(
    aid: str,
    delete_file: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisActionResponse:
    ok = await store.remove_artifact(db, aid, current_user.id, delete_file=delete_file)
    if not ok:
        raise HTTPException(status_code=404, detail="产物不存在")
    return AnalysisActionResponse(ok=True)


@router.delete("/sources/{sid}", response_model=AnalysisActionResponse)
async def delete_source(
    sid: str,
    delete_files: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisActionResponse:
    ok = await store.remove_source(db, sid, current_user.id, delete_files=delete_files)
    if not ok:
        raise HTTPException(status_code=404, detail="来源不存在")
    return AnalysisActionResponse(ok=True)


@router.get("/status", response_model=AnalysisStatusResponse)
async def status(
    current_user: User = Depends(get_current_user),
) -> AnalysisStatusResponse:
    available = backends.whisper_available()
    cookie_ok = False
    if cookies.cookies_present():
        cookie_ok, _ = cookies.validate_cookie_file()
    return AnalysisStatusResponse(
        transcribe_available=available,
        transcribe_backend=backends.active_model_label(),
        youtube_logged_in=cookie_ok,
        cookies_present=cookies.cookies_present(),
    )


@router.post("/login/cookies", response_model=AnalysisLoginResponse)
async def login_cookies(
    payload: AnalysisLoginCookiesRequest,
    current_user: User = Depends(get_current_user),
) -> AnalysisLoginResponse:
    ok, message = cookies.save_text_cookies(payload.cookies)
    return AnalysisLoginResponse(ok=ok, message=message)


@router.post("/login/browser", response_model=AnalysisLoginResponse)
async def login_browser(
    payload: AnalysisLoginBrowserRequest,
    current_user: User = Depends(get_current_user),
) -> AnalysisLoginResponse:
    ok, message = cookies.import_from_browser(payload.browser, payload.profile)
    return AnalysisLoginResponse(ok=ok, message=message)
