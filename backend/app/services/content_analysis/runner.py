"""后台任务编排：下载/转写在线程中执行，进度与取消用内存登记，状态回写数据库。

下载/转写为阻塞型调用（yt-dlp / Whisper），通过 ``asyncio.to_thread`` 执行以不阻塞
事件循环；进度由线程内回调写入内存登记表，``GET /artifacts`` 时叠加到响应；取消通过
内存集合实现（下载可中途中断，转写无法中途杀死，只丢弃结果）。
"""

import asyncio
import os
import traceback
from datetime import datetime, timezone

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.models.models import AnalysisArtifact, ArtifactStatus, ArtifactType
from app.services.content_analysis import backends, store

# 内存登记：仅用于运行期的实时进度与取消信号（不持久化）。
_progress: dict[str, float] = {}
_cancels: set[str] = set()


class _Cancelled(Exception):
    pass


def request_cancel(aid: str) -> None:
    _cancels.add(aid)


def is_cancelled(aid: str) -> bool:
    return aid in _cancels


def live_progress(aid: str) -> float | None:
    return _progress.get(aid)


def _clear(aid: str) -> None:
    _progress.pop(aid, None)
    _cancels.discard(aid)


async def run_download(artifact_id: str, source_id: str, url: str, kind: str) -> None:
    async with AsyncSessionLocal() as db:
        await store.update_artifact(
            db,
            artifact_id,
            status=ArtifactStatus.RUNNING,
            started_at=_now(),
            error=None,
            error_log=None,
        )

    def progress_cb(pct: float) -> None:
        if is_cancelled(artifact_id):
            raise _Cancelled()
        _progress[artifact_id] = pct

    dest = store.base_dir()
    cookie = store.cookie_file()
    try:
        filepath, title, author = await asyncio.to_thread(
            backends.download_media, url, kind, dest, cookie, progress_cb
        )
        size = os.path.getsize(filepath) if os.path.exists(filepath) else None
        async with AsyncSessionLocal() as db:
            await store.set_source_meta(db, source_id, title=title, author=author)
            await store.update_artifact(
                db,
                artifact_id,
                status=ArtifactStatus.FINISHED,
                progress=100.0,
                filename=os.path.basename(filepath),
                filepath=filepath,
                size=size,
                finished_at=_now(),
            )
    except Exception as exc:  # noqa: BLE001 - 把外部错误回写为可观测状态
        await _fail(artifact_id, exc)
        return
    finally:
        _clear(artifact_id)

    # 下载视频成功后自动转写（对齐 yt-dlp-x，仅视频，且转写后端可用时）
    settings = get_settings()
    if (
        kind == ArtifactType.VIDEO
        and settings.content_analysis_auto_transcribe
        and backends.whisper_available()
    ):
        async with AsyncSessionLocal() as db:
            text_art = await store.create_artifact(
                db,
                source_id,
                ArtifactType.TEXT,
                source_artifact_id=artifact_id,
                meta={"model": backends.active_model_label()},
            )
            text_aid = text_art.id
        await run_transcribe(text_aid, artifact_id, filepath, source_id)


async def run_transcribe(
    text_aid: str, media_aid: str | None, media_path: str, source_id: str
) -> None:
    async with AsyncSessionLocal() as db:
        await store.update_artifact(
            db,
            text_aid,
            status=ArtifactStatus.RUNNING,
            started_at=_now(),
            error=None,
            error_log=None,
        )
    try:
        text = await asyncio.to_thread(backends.transcribe_audio, media_path)
        if is_cancelled(text_aid):
            return
        base = os.path.splitext(os.path.basename(media_path))[0]
        out = store.base_dir() / (base + ".txt")
        out.write_text(text, encoding="utf-8")
        meta = {"model": backends.active_model_label(), "preview": text[:500]}
        await _maybe_delete_source(text_aid, media_aid, meta)
        async with AsyncSessionLocal() as db:
            await store.update_artifact(
                db,
                text_aid,
                status=ArtifactStatus.FINISHED,
                progress=100.0,
                filename=out.name,
                filepath=str(out),
                size=out.stat().st_size,
                finished_at=_now(),
                meta=meta,
            )
    except Exception as exc:  # noqa: BLE001
        await _fail(text_aid, exc)
    finally:
        _clear(text_aid)


async def _maybe_delete_source(text_aid: str, media_aid: str | None, meta: dict) -> None:
    """转写成功后按配置删除源音/视频产物（对齐 yt-dlp-x，省磁盘）。"""
    if not media_aid or not get_settings().content_analysis_delete_source_after_transcribe:
        return
    async with AsyncSessionLocal() as db:
        media = await db.get(AnalysisArtifact, media_aid)
        if media is None:
            return
        meta["deleted_source"] = f"{media.filename or '源文件'}（{media.type}）"
        # 先断开 text 对 media 的血缘外键，避免删除时违反约束
        text = await db.get(AnalysisArtifact, text_aid)
        if text is not None:
            text.source_artifact_id = None
        store._delete_file(media.filepath)
        await db.delete(media)
        await db.commit()


async def _fail(aid: str, exc: Exception) -> None:
    canceled = isinstance(exc, _Cancelled) or is_cancelled(aid)
    async with AsyncSessionLocal() as db:
        if canceled:
            await store.update_artifact(
                db, aid, status=ArtifactStatus.CANCELED, error="已终止", finished_at=_now()
            )
        else:
            await store.update_artifact(
                db,
                aid,
                status=ArtifactStatus.ERROR,
                error=backends.annotate_error(str(exc)),
                error_log=traceback.format_exc(),
                finished_at=_now(),
            )


def _now() -> datetime:
    return datetime.now(timezone.utc)
