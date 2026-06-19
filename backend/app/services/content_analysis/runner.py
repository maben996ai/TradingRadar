"""后台任务编排：下载/转写在线程中执行，进度与取消用内存登记，状态回写数据库。

下载/转写为阻塞型调用（yt-dlp / Whisper），通过 ``asyncio.to_thread`` 执行以不阻塞
事件循环；进度由线程内回调写入内存登记表，``GET /artifacts`` 时叠加到响应；取消通过
内存集合实现（下载可中途中断，转写无法中途杀死，只丢弃结果）。
"""

import asyncio
import os
import traceback
from datetime import datetime, timezone

from app.core.database import AsyncSessionLocal
from app.models.models import ArtifactStatus
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
    finally:
        _clear(artifact_id)


async def run_transcribe(text_aid: str, media_path: str, source_id: str) -> None:
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
