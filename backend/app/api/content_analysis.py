"""内容分析 API：粘贴 YouTube URL 下载音/视频、Whisper 转写文本、产物管理。

移植自 yt-dlp-x 后端，遵循 TradingRadar 分层：路由仅做入口，逻辑在 services。
"""

import asyncio
import subprocess
import sys

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.models import ArtifactStatus, ArtifactType, ContentItem, DataSource, SourceType, User
from app.schemas.schemas import (
    AnalysisActionResponse,
    AnalysisArtifactResponse,
    AnalysisDeletedSourceResponse,
    AnalysisDownloadRequest,
    AnalysisFromContentItemRequest,
    AnalysisListResponse,
    AnalysisLoginBrowserRequest,
    AnalysisLoginCookiesRequest,
    AnalysisLoginResponse,
    AnalysisProbeResponse,
    AnalysisSourceResponse,
    AnalysisStatusResponse,
)
from app.services.content_analysis import backends, cookies, runner, store

# 活体探测网络超时（秒）：探测请求在线程中执行，避免阻塞事件循环。
_PROBE_TIMEOUT = 20

# live_probe 三态映射到对外 state 字符串。
_PROBE_STATE = {True: "logged_in", False: "logged_out", None: "inconclusive"}

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
    background_tasks.add_task(
        runner.run_transcribe, text_art.id, media.id, media.filepath, src.id
    )
    return _artifact_response(text_art)


@router.get("/artifacts", response_model=AnalysisListResponse)
async def list_artifacts(
    type: str | None = Query(default=None),
    q: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisListResponse:
    type_filter = type if type in ("video", "audio", "text") else None
    order = {"video": 0, "audio": 1, "text": 2}
    sources = await store.list_sources(db, current_user.id, type_filter, query=q)
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


@router.post("/artifacts/{aid}/reveal", response_model=AnalysisActionResponse)
async def reveal_artifact(
    aid: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisActionResponse:
    """在宿主机文件管理器中定位文件（仅后端跑在本机时有效）。"""
    art, _src = await store.get_artifact_owned(db, aid, current_user.id)
    if art is None:
        raise HTTPException(status_code=404, detail="产物不存在")
    rp = store.safe_path(art.filepath)
    if rp is None or not rp.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(rp)])
        elif sys.platform.startswith("win"):
            subprocess.Popen(["explorer", "/select,", str(rp)])
        else:
            subprocess.Popen(["xdg-open", str(rp.parent)])
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"无法打开文件夹：{exc}") from exc
    return AnalysisActionResponse(ok=True)


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


@router.get("/sources/deleted", response_model=list[AnalysisDeletedSourceResponse])
async def list_deleted_sources(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AnalysisDeletedSourceResponse]:
    """回收站列表：本人已软删除的来源。"""
    sources = await store.deleted_sources(db, current_user.id)
    return [AnalysisDeletedSourceResponse.model_validate(s) for s in sources]


@router.delete("/sources/{sid}", response_model=AnalysisActionResponse)
async def delete_source(
    sid: str,
    purge: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisActionResponse:
    """默认软删除（移入回收站）；purge=true 则彻底删除来源与文件。"""
    if purge:
        ok = await store.purge_source(db, sid, current_user.id)
    else:
        ok = await store.soft_delete_source(db, sid, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="来源不存在")
    return AnalysisActionResponse(ok=True)


@router.post("/sources/{sid}/restore", response_model=AnalysisActionResponse)
async def restore_source(
    sid: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisActionResponse:
    """从回收站还原来源。"""
    ok = await store.restore_source(db, sid, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="来源不存在")
    return AnalysisActionResponse(ok=True)


@router.post("/sources/{sid}/purge", response_model=AnalysisActionResponse)
async def purge_source(
    sid: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisActionResponse:
    """彻底删除来源记录及其全部产物文件。"""
    ok = await store.purge_source(db, sid, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="来源不存在")
    return AnalysisActionResponse(ok=True)


@router.post("/from-content-item/{content_item_id}", response_model=AnalysisArtifactResponse)
async def from_content_item(
    content_item_id: str,
    payload: AnalysisFromContentItemRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisArtifactResponse:
    """对某条 YouTube 信源内容一键创建下载产物，复用现有 download 链路。"""
    item = await db.get(ContentItem, content_item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="内容不存在")
    ds = await db.get(DataSource, item.data_source_id)
    # 不存在或非本人：统一 404（不泄露他人内容存在）
    if ds is None or ds.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="内容不存在")
    if ds.source_type != SourceType.YOUTUBE:
        raise HTTPException(status_code=400, detail="仅支持对 YouTube 内容创建下载产物")
    url = (item.content_url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="该内容缺少可下载的链接")
    kind = ArtifactType.AUDIO if payload.mode == "audio" else ArtifactType.VIDEO
    src = await store.get_or_create_source(db, current_user.id, url, title=item.title)
    art = await store.create_artifact(db, src.id, kind)
    background_tasks.add_task(runner.run_download, art.id, src.id, url, kind.value)
    return _artifact_response(art)


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


@router.post("/login/probe", response_model=AnalysisProbeResponse)
async def login_probe(
    current_user: User = Depends(get_current_user),
) -> AnalysisProbeResponse:
    """活体探测：实际拉取 YouTube 主页判断登录态。

    网络请求阻塞，放入线程执行以不阻塞事件循环；带超时。三态：
    logged_in / logged_out / inconclusive。
    """
    state, message, _info = await asyncio.to_thread(cookies.live_probe, _PROBE_TIMEOUT)
    return AnalysisProbeResponse(
        state=_PROBE_STATE[state],
        ok=state is True,
        message=message,
    )


@router.post("/logout", response_model=AnalysisActionResponse)
async def logout(
    current_user: User = Depends(get_current_user),
) -> AnalysisActionResponse:
    """登出：删除已保存的 YouTube cookies（幂等）。"""
    cookies.clear_cookies()
    return AnalysisActionResponse(ok=True, message="已退出 YouTube 登录")
