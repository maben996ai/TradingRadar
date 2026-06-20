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
    # 关闭自动转写，专注验证下载流程
    monkeypatch.setattr(backends, "whisper_available", lambda: False)

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

    await runner.run_transcribe(text_art.id, media.id, str(audio), src.id)

    async with session_factory() as check:
        from app.models.models import AnalysisArtifact

        refreshed = await check.get(AnalysisArtifact, text_art.id)
        assert refreshed.status == ArtifactStatus.FINISHED
        assert (tmp_path / "clip.txt").read_text() == "hello world"
        assert refreshed.meta["preview"] == "hello world"
        # 默认开启转写后删源：media 产物应被删除，血缘断开
        assert await check.get(AnalysisArtifact, media.id) is None
        assert refreshed.source_artifact_id is None
        assert refreshed.meta.get("deleted_source")


# -- US-001：软删除字段 + 新增 schema 契约 --------------------------------


async def test_analysis_source_has_deleted_at_default_null(client, auth_headers, db):
    """新增 deleted_at 字段默认 NULL，向后兼容。"""
    uid = await _user_id(db)
    src = await store.get_or_create_source(db, uid, "https://youtu.be/abcdefghijk")
    assert hasattr(src, "deleted_at")
    assert src.deleted_at is None


def test_analysis_probe_response_schema():
    from app.schemas.schemas import AnalysisProbeResponse

    for state in ("logged_in", "logged_out", "inconclusive"):
        r = AnalysisProbeResponse(state=state, ok=True, message="x")
        assert r.state == state
        assert r.ok is True


def test_analysis_deleted_source_response_from_attributes():
    from datetime import datetime, timezone

    from app.models.models import AnalysisSource
    from app.schemas.schemas import AnalysisDeletedSourceResponse

    now = datetime.now(timezone.utc)
    src = AnalysisSource(
        id="s1",
        user_id="u1",
        url="https://youtu.be/abcdefghijk",
        video_id="abcdefghijk",
        title="t",
        author=None,
        created_at=now,
        deleted_at=now,
    )
    r = AnalysisDeletedSourceResponse.model_validate(src)
    assert r.id == "s1"
    assert r.deleted_at == now


def test_analysis_from_content_item_request_default_mode():
    from app.schemas.schemas import AnalysisFromContentItemRequest

    assert AnalysisFromContentItemRequest().mode == "video"
    assert AnalysisFromContentItemRequest(mode="audio").mode == "audio"


# -- US-002：cookies 活体探测 / clear_cookies / save 后并入探测 ----------------


def test_clear_cookies_idempotent(tmp_path, monkeypatch):
    """clear_cookies 文件不存在也不报错，存在则删除。"""
    from app.services.content_analysis import cookies, store

    monkeypatch.setattr(store, "base_dir", lambda: tmp_path)
    # 文件不存在：幂等，不抛
    cookies.clear_cookies()
    f = store.cookie_file()
    f.write_text("# Netscape HTTP Cookie File\n")
    assert f.exists()
    cookies.clear_cookies()
    assert not f.exists()
    # 再次调用仍幂等
    cookies.clear_cookies()


def test_live_probe_missing_file(tmp_path, monkeypatch):
    from app.services.content_analysis import cookies, store

    monkeypatch.setattr(store, "base_dir", lambda: tmp_path)
    state, msg, info = cookies.live_probe()
    assert state is False
    assert info["probe"] == "missing"


def _stub_probe_env(monkeypatch, store_mod, cookies_mod, tmp_path):
    """打桩探测依赖：cookie 文件存在、jar 加载成功（无需真实 yt-dlp）。"""
    monkeypatch.setattr(store_mod, "base_dir", lambda: tmp_path)
    store_mod.cookie_file().write_text("# Netscape HTTP Cookie File\n")
    monkeypatch.setattr(cookies_mod, "_load_cookie_jar", lambda path: object())


def test_live_probe_logged_in(tmp_path, monkeypatch):
    """YouTube 主页含 LOGGED_IN:true → True。"""
    from app.services.content_analysis import cookies, store

    _stub_probe_env(monkeypatch, store, cookies, tmp_path)
    monkeypatch.setattr(
        cookies, "_fetch_youtube_home", lambda jar, timeout: '...{"LOGGED_IN":true}...'
    )
    state, msg, info = cookies.live_probe()
    assert state is True
    assert info["probe"] == "logged_in"


def test_live_probe_logged_out(tmp_path, monkeypatch):
    from app.services.content_analysis import cookies, store

    _stub_probe_env(monkeypatch, store, cookies, tmp_path)
    monkeypatch.setattr(
        cookies, "_fetch_youtube_home", lambda jar, timeout: '..."LOGGED_IN": false ...'
    )
    state, msg, info = cookies.live_probe()
    assert state is False
    assert info["probe"] == "logged_out"


def test_live_probe_inconclusive_unreachable(tmp_path, monkeypatch):
    from app.services.content_analysis import cookies, store

    _stub_probe_env(monkeypatch, store, cookies, tmp_path)

    def boom(jar, timeout):
        raise OSError("network down")

    monkeypatch.setattr(cookies, "_fetch_youtube_home", boom)
    state, msg, info = cookies.live_probe()
    assert state is None
    assert info["probe"] == "unreachable"


def test_live_probe_inconclusive_unknown(tmp_path, monkeypatch):
    """页面拿到但无 LOGGED_IN 标记 → None。"""
    from app.services.content_analysis import cookies, store

    _stub_probe_env(monkeypatch, store, cookies, tmp_path)
    monkeypatch.setattr(cookies, "_fetch_youtube_home", lambda jar, timeout: "<html>no flag</html>")
    state, msg, info = cookies.live_probe()
    assert state is None
    assert info["probe"] == "unknown"


def test_save_text_cookies_merges_probe(tmp_path, monkeypatch):
    """保存成功后并入活体探测信息；探测不可达不回滚已保存 cookies。"""
    from app.services.content_analysis import cookies, store

    import sys
    import types

    # 注入最小 yt_dlp.cookies 桩，避免依赖真实安装
    if "yt_dlp.cookies" not in sys.modules:
        ytm = types.ModuleType("yt_dlp")
        cm = types.ModuleType("yt_dlp.cookies")
        cm.YoutubeDLCookieJar = object
        ytm.cookies = cm
        monkeypatch.setitem(sys.modules, "yt_dlp", ytm)
        monkeypatch.setitem(sys.modules, "yt_dlp.cookies", cm)

    monkeypatch.setattr(store, "base_dir", lambda: tmp_path)
    # 打桩校验通过（避免依赖真实 yt-dlp 解析）
    monkeypatch.setattr(cookies, "validate_cookie_file", lambda path=None: (True, "ok"))
    monkeypatch.setattr(
        cookies, "live_probe", lambda: (None, "活体探测无法完成", {"probe": "unreachable"})
    )
    text = "\t".join([".youtube.com", "TRUE", "/", "TRUE", "9999999999", "LOGIN_INFO", "x"])
    ok, msg = cookies.save_text_cookies(text)
    assert ok is True  # 探测不可达不回滚
    assert store.cookie_file().exists()
    assert "活体探测" in msg


# -- US-002：软删除 / 还原 / 彻底清除 / 回收站 / 越权 -------------------------


async def test_soft_delete_keeps_source_clears_artifacts(
    client, auth_headers, db, tmp_path, monkeypatch
):
    monkeypatch.setattr(store, "base_dir", lambda: tmp_path)
    uid = await _user_id(db)
    src = await store.get_or_create_source(db, uid, "https://youtu.be/abcdefghijk")
    media = tmp_path / "v.mp4"
    media.write_bytes(b"x")
    await store.create_artifact(
        db, src.id, ArtifactType.VIDEO, status=ArtifactStatus.FINISHED, filepath=str(media)
    )
    ok = await store.soft_delete_source(db, src.id, uid)
    assert ok is True
    assert not media.exists()  # 磁盘文件删除
    # 来源条目保留、deleted_at 置位、产物清空
    from app.models.models import AnalysisSource

    refreshed = await db.get(AnalysisSource, src.id)
    assert refreshed is not None
    assert refreshed.deleted_at is not None
    # list_sources 默认排除
    assert all(s.id != src.id for s in await store.list_sources(db, uid))
    # 出现在回收站
    deleted = await store.deleted_sources(db, uid)
    assert any(s.id == src.id for s in deleted)


async def test_restore_source(client, auth_headers, db, tmp_path, monkeypatch):
    monkeypatch.setattr(store, "base_dir", lambda: tmp_path)
    uid = await _user_id(db)
    src = await store.get_or_create_source(db, uid, "https://youtu.be/abcdefghijk")
    await store.soft_delete_source(db, src.id, uid)
    ok = await store.restore_source(db, src.id, uid)
    assert ok is True
    assert any(s.id == src.id for s in await store.list_sources(db, uid))
    assert all(s.id != src.id for s in await store.deleted_sources(db, uid))


async def test_purge_source_removes_record(client, auth_headers, db, tmp_path, monkeypatch):
    monkeypatch.setattr(store, "base_dir", lambda: tmp_path)
    uid = await _user_id(db)
    src = await store.get_or_create_source(db, uid, "https://youtu.be/abcdefghijk")
    media = tmp_path / "v2.mp4"
    media.write_bytes(b"x")
    await store.create_artifact(db, src.id, ArtifactType.VIDEO, filepath=str(media))
    ok = await store.purge_source(db, src.id, uid)
    assert ok is True
    assert not media.exists()
    from app.models.models import AnalysisSource

    assert await db.get(AnalysisSource, src.id) is None


async def test_store_methods_reject_other_user(client, auth_headers, db, tmp_path, monkeypatch):
    monkeypatch.setattr(store, "base_dir", lambda: tmp_path)
    uid = await _user_id(db)
    src = await store.get_or_create_source(db, uid, "https://youtu.be/abcdefghijk")
    other = "not-the-owner"
    assert await store.soft_delete_source(db, src.id, other) is False
    assert await store.restore_source(db, src.id, other) is False
    assert await store.purge_source(db, src.id, other) is False
    # deleted_sources 仅返回本人
    assert await store.deleted_sources(db, other) == []
