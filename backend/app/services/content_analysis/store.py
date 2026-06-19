"""内容分析数据层：来源（AnalysisSource）与产物（AnalysisArtifact）的增删查改。

数据模型对齐源项目 yt-dlp-x：每个来源（一个 YouTube URL/视频）下挂 video/audio/text
产物，text 产物记录其来源音/视频产物（血缘）。状态持久化在 Postgres，按用户隔离。
"""

import hashlib
import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models.models import (
    AnalysisArtifact,
    AnalysisSource,
    ArtifactStage,
    ArtifactStatus,
    ArtifactType,
)

# 以 backend 目录为基准（本文件位于 backend/app/services/content_analysis/store.py）。
_BACKEND_DIR = Path(__file__).resolve().parents[3]
DEFAULT_DIR = _BACKEND_DIR / "data" / "content_analysis"

MEDIA_VIDEO_EXT = {".mp4", ".mkv", ".webm", ".flv", ".mov"}
MEDIA_AUDIO_EXT = {".mp3", ".m4a", ".wav", ".opus", ".aac"}
TEXT_EXT = {".txt", ".srt", ".vtt"}

_YT_ID_RE = re.compile(r"(?:v=|youtu\.be/|/shorts/|/embed/|/live/)([0-9A-Za-z_-]{11})")

STAGE_OF_TYPE = {
    ArtifactType.VIDEO: ArtifactStage.DOWNLOAD,
    ArtifactType.AUDIO: ArtifactStage.DOWNLOAD,
    ArtifactType.TEXT: ArtifactStage.TRANSCRIBE,
}


def base_dir() -> Path:
    configured = get_settings().content_analysis_dir
    root = Path(configured) if configured else DEFAULT_DIR
    root.mkdir(parents=True, exist_ok=True)
    return root


def cookie_file() -> Path:
    return base_dir() / "youtube_cookies.txt"


def extract_video_id(url: str) -> str | None:
    m = _YT_ID_RE.search(url or "")
    return m.group(1) if m else None


def source_key(url: str) -> str:
    vid = extract_video_id(url)
    return vid if vid else "u_" + hashlib.md5((url or "").encode()).hexdigest()[:11]


def safe_path(path: str | None) -> Path | None:
    """返回位于产物根目录内的真实路径，否则 None（防路径穿越）。"""
    if not path:
        return None
    root = base_dir().resolve()
    rp = Path(path).resolve()
    try:
        rp.relative_to(root)
    except ValueError:
        return None
    return rp


async def get_or_create_source(
    db: AsyncSession, user_id: str, url: str, title: str | None = None
) -> AnalysisSource:
    vid = source_key(url)
    src = await db.scalar(
        select(AnalysisSource).where(
            AnalysisSource.user_id == user_id, AnalysisSource.video_id == vid
        )
    )
    if src is None:
        src = AnalysisSource(user_id=user_id, url=url, video_id=vid, title=title or url)
        db.add(src)
        await db.commit()
        await db.refresh(src)
    return src


async def set_source_meta(
    db: AsyncSession, source_id: str, title: str | None = None, author: str | None = None
) -> None:
    src = await db.get(AnalysisSource, source_id)
    if src is None:
        return
    if title:
        src.title = title
    if author:
        src.author = author
    await db.commit()


async def create_artifact(
    db: AsyncSession, source_id: str, typ: ArtifactType, **fields
) -> AnalysisArtifact:
    """在来源下创建或重置某类型产物（每来源每类型至多一个）。"""
    existing = await db.scalar(
        select(AnalysisArtifact).where(
            AnalysisArtifact.source_id == source_id, AnalysisArtifact.type == typ
        )
    )
    if existing is not None:
        await db.delete(existing)
        await db.flush()
    fields.setdefault("status", ArtifactStatus.QUEUED)
    art = AnalysisArtifact(
        source_id=source_id,
        type=typ,
        stage=STAGE_OF_TYPE[typ],
        **fields,
    )
    db.add(art)
    await db.commit()
    await db.refresh(art)
    return art


async def update_artifact(db: AsyncSession, aid: str, **fields) -> AnalysisArtifact | None:
    art = await db.get(AnalysisArtifact, aid)
    if art is None:
        return None
    for key, value in fields.items():
        setattr(art, key, value)
    await db.commit()
    await db.refresh(art)
    return art


async def get_artifact_owned(
    db: AsyncSession, aid: str, user_id: str
) -> tuple[AnalysisArtifact, AnalysisSource] | tuple[None, None]:
    art = await db.get(AnalysisArtifact, aid)
    if art is None:
        return None, None
    src = await db.get(AnalysisSource, art.source_id)
    if src is None or src.user_id != user_id:
        return None, None
    return art, src


async def list_sources(
    db: AsyncSession,
    user_id: str,
    type_filter: str | None = None,
    query: str | None = None,
) -> list[AnalysisSource]:
    stmt = (
        select(AnalysisSource)
        .options(selectinload(AnalysisSource.artifacts))
        .where(AnalysisSource.user_id == user_id)
        .order_by(AnalysisSource.created_at.desc())
    )
    sources = list(await db.scalars(stmt))
    if type_filter:
        sources = [s for s in sources if any(a.type == type_filter for a in s.artifacts)]
    if query:
        kw = query.strip().lower()
        sources = [
            s
            for s in sources
            if kw in (s.title or "").lower() or kw in (s.author or "").lower()
        ]
    return sources


async def counts(db: AsyncSession, user_id: str) -> dict[str, int]:
    sources = await list_sources(db, user_id)
    c = {"video": 0, "audio": 0, "text": 0, "sources": len(sources)}
    for s in sources:
        for a in s.artifacts:
            c[a.type] = c.get(a.type, 0) + 1
    return c


def _delete_file(path: str | None) -> None:
    rp = safe_path(path)
    if rp and rp.is_file():
        try:
            rp.unlink()
        except OSError:
            pass


async def remove_artifact(
    db: AsyncSession, aid: str, user_id: str, delete_file: bool = False
) -> bool:
    art, src = await get_artifact_owned(db, aid, user_id)
    if art is None:
        return False
    if delete_file:
        _delete_file(art.filepath)
    await db.delete(art)
    await db.commit()
    return True


async def remove_source(
    db: AsyncSession, sid: str, user_id: str, delete_files: bool = False
) -> bool:
    src = await db.scalar(
        select(AnalysisSource)
        .options(selectinload(AnalysisSource.artifacts))
        .where(AnalysisSource.id == sid, AnalysisSource.user_id == user_id)
    )
    if src is None:
        return False
    if delete_files:
        for a in src.artifacts:
            _delete_file(a.filepath)
    await db.delete(src)
    await db.commit()
    return True
