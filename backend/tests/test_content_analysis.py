"""内容分析模块测试：下载/转写以打桩后端跑通状态流转，不真打外网/不加载模型。"""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.models import ArtifactStatus, ArtifactType
from app.services.content_analysis import runner, store


@pytest.fixture
def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def _user_id(db: AsyncSession) -> str:
    from sqlalchemy import select

    from app.models.models import User

    return await db.scalar(select(User.id))


# -- store 层 ---------------------------------------------------------------


async def test_get_or_create_source_dedup(client, auth_headers, db):
    uid = await _user_id(db)
    url = "https://www.youtube.com/watch?v=abcdefghijk"
    s1 = await store.get_or_create_source(db, uid, url)
    s2 = await store.get_or_create_source(db, uid, url)
    assert s1.id == s2.id
    assert s1.video_id == "abcdefghijk"


async def test_create_artifact_replaces_same_type(client, auth_headers, db):
    uid = await _user_id(db)
    src = await store.get_or_create_source(db, uid, "https://youtu.be/abcdefghijk")
    a1 = await store.create_artifact(db, src.id, ArtifactType.VIDEO)
    a2 = await store.create_artifact(db, src.id, ArtifactType.VIDEO)
    assert a1.id != a2.id
    sources = await store.list_sources(db, uid)
    videos = [a for s in sources for a in s.artifacts if a.type == ArtifactType.VIDEO]
    assert len(videos) == 1


async def test_safe_path_guard(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "base_dir", lambda: tmp_path)
    inside = tmp_path / "a.txt"
    inside.write_text("x")
    assert store.safe_path(str(inside)) is not None
    assert store.safe_path("/etc/passwd") is None


# -- API 层（下载/转写后台任务打桩） ---------------------------------------


async def test_download_creates_queued_artifact(client, auth_headers, monkeypatch):
    monkeypatch.setattr(runner, "run_download", AsyncMock())
    resp = await client.post(
        "/api/content-analysis/download",
        json={"url": "https://www.youtube.com/watch?v=abcdefghijk", "mode": "audio"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "audio"
    assert body["status"] == "queued"


async def test_download_requires_url(client, auth_headers):
    resp = await client.post(
        "/api/content-analysis/download", json={"url": "  "}, headers=auth_headers
    )
    assert resp.status_code == 400


async def test_download_requires_auth(client):
    resp = await client.post("/api/content-analysis/download", json={"url": "https://youtu.be/x"})
    assert resp.status_code == 401


async def test_transcribe_unavailable_backend(client, auth_headers, db, monkeypatch):
    from app.services.content_analysis import backends

    monkeypatch.setattr(backends, "whisper_available", lambda: False)
    uid = await _user_id(db)
    src = await store.get_or_create_source(db, uid, "https://youtu.be/abcdefghijk")
    media = await store.create_artifact(
        db,
        src.id,
        ArtifactType.AUDIO,
        status=ArtifactStatus.FINISHED,
        filepath="/tmp/x.mp3",
    )
    resp = await client.post(
        f"/api/content-analysis/artifacts/{media.id}/transcribe", headers=auth_headers
    )
    assert resp.status_code == 400


async def test_transcribe_missing_artifact(client, auth_headers):
    resp = await client.post(
        "/api/content-analysis/artifacts/nope/transcribe", headers=auth_headers
    )
    assert resp.status_code == 404


async def test_list_artifacts_grouped(client, auth_headers, db, monkeypatch):
    monkeypatch.setattr(runner, "run_download", AsyncMock())
    await client.post(
        "/api/content-analysis/download",
        json={"url": "https://www.youtube.com/watch?v=abcdefghijk"},
        headers=auth_headers,
    )
    resp = await client.get("/api/content-analysis/artifacts", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["counts"]["sources"] == 1
    assert body["counts"]["video"] == 1
    assert len(body["sources"]) == 1


async def test_delete_artifact_and_source(client, auth_headers, db, monkeypatch):
    monkeypatch.setattr(runner, "run_download", AsyncMock())
    r = await client.post(
        "/api/content-analysis/download",
        json={"url": "https://www.youtube.com/watch?v=abcdefghijk"},
        headers=auth_headers,
    )
    aid = r.json()["id"]
    d = await client.delete(f"/api/content-analysis/artifacts/{aid}", headers=auth_headers)
    assert d.status_code == 200 and d.json()["ok"] is True
    d2 = await client.delete(f"/api/content-analysis/artifacts/{aid}", headers=auth_headers)
    assert d2.status_code == 404


async def test_status_endpoint(client, auth_headers, monkeypatch):
    from app.services.content_analysis import backends, cookies

    monkeypatch.setattr(backends, "whisper_available", lambda: True)
    monkeypatch.setattr(backends, "active_model_label", lambda: "mlx:test")
    monkeypatch.setattr(cookies, "cookies_present", lambda: False)
    resp = await client.get("/api/content-analysis/status", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["transcribe_available"] is True
    assert body["transcribe_backend"] == "mlx:test"
    assert body["youtube_logged_in"] is False


async def test_file_artifact_not_found(client, auth_headers, db, monkeypatch):
    monkeypatch.setattr(runner, "run_download", AsyncMock())
    r = await client.post(
        "/api/content-analysis/download",
        json={"url": "https://www.youtube.com/watch?v=abcdefghijk"},
        headers=auth_headers,
    )
    aid = r.json()["id"]  # 无 filepath
    resp = await client.get(f"/api/content-analysis/artifacts/{aid}/file", headers=auth_headers)
    assert resp.status_code == 403  # filepath 为空 → safe_path None → 越界


# -- runner 层（后台任务用打桩后端跑通状态流转） ---------------------------


async def test_run_download_success(
    client, auth_headers, db, session_factory, tmp_path, monkeypatch
):
    from app.services.content_analysis import backends

    monkeypatch.setattr(runner, "AsyncSessionLocal", session_factory)
    monkeypatch.setattr(store, "base_dir", lambda: tmp_path)

    media_file = tmp_path / "video.mp4"
    media_file.write_bytes(b"fakevideo")

    def fake_download(url, kind, dest, cookie, cb):
        cb(50.0)
        cb(100.0)
        return str(media_file), "Real Title", "Some Author"

    monkeypatch.setattr(backends, "download_media", fake_download)

    uid = await _user_id(db)
    src = await store.get_or_create_source(db, uid, "https://youtu.be/abcdefghijk")
    art = await store.create_artifact(db, src.id, ArtifactType.VIDEO)

    await runner.run_download(art.id, src.id, src.url, "video")

    async with session_factory() as check:
        from app.models.models import AnalysisArtifact, AnalysisSource

        refreshed = await check.get(AnalysisArtifact, art.id)
        assert refreshed.status == ArtifactStatus.FINISHED
        assert refreshed.progress == 100.0
        assert refreshed.filename == "video.mp4"
        src_row = await check.get(AnalysisSource, src.id)
        assert src_row.title == "Real Title"
        assert src_row.author == "Some Author"


async def test_run_download_failure(
    client, auth_headers, db, session_factory, tmp_path, monkeypatch
):
    from app.services.content_analysis import backends

    monkeypatch.setattr(runner, "AsyncSessionLocal", session_factory)
    monkeypatch.setattr(store, "base_dir", lambda: tmp_path)

    def boom(*args, **kwargs):
        raise RuntimeError("download exploded")

    monkeypatch.setattr(backends, "download_media", boom)

    uid = await _user_id(db)
    src = await store.get_or_create_source(db, uid, "https://youtu.be/abcdefghijk")
    art = await store.create_artifact(db, src.id, ArtifactType.VIDEO)

    await runner.run_download(art.id, src.id, src.url, "video")

    async with session_factory() as check:
        from app.models.models import AnalysisArtifact

        refreshed = await check.get(AnalysisArtifact, art.id)
        assert refreshed.status == ArtifactStatus.ERROR
        assert "download exploded" in refreshed.error


async def test_run_transcribe_success(
    client, auth_headers, db, session_factory, tmp_path, monkeypatch
):
    from app.services.content_analysis import backends

    monkeypatch.setattr(runner, "AsyncSessionLocal", session_factory)
    monkeypatch.setattr(store, "base_dir", lambda: tmp_path)
    monkeypatch.setattr(backends, "transcribe_audio", lambda path: "hello world")
    monkeypatch.setattr(backends, "active_model_label", lambda: "mlx:test")

    audio = tmp_path / "clip.mp3"
    audio.write_bytes(b"audio")

    uid = await _user_id(db)
    src = await store.get_or_create_source(db, uid, "https://youtu.be/abcdefghijk")
    media = await store.create_artifact(
        db, src.id, ArtifactType.AUDIO, status=ArtifactStatus.FINISHED, filepath=str(audio)
    )
    text_art = await store.create_artifact(
        db, src.id, ArtifactType.TEXT, source_artifact_id=media.id
    )

    await runner.run_transcribe(text_art.id, str(audio), src.id)

    async with session_factory() as check:
        from app.models.models import AnalysisArtifact

        refreshed = await check.get(AnalysisArtifact, text_art.id)
        assert refreshed.status == ArtifactStatus.FINISHED
        assert (tmp_path / "clip.txt").read_text() == "hello world"
        assert refreshed.meta["preview"] == "hello world"
