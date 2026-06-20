"""US-003 路由测试：probe / logout / 回收站 / from-content-item。

路由层逻辑，后台任务与活体探测均打桩，不真打外网。
"""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    ArtifactType,
    ContentItem,
    DataSource,
    SourceType,
    User,
)
from app.services.content_analysis import cookies, runner, store


async def _user_id(db: AsyncSession) -> str:
    return await db.scalar(select(User.id))


async def _make_content_item(
    db: AsyncSession,
    user_id: str,
    source_type: SourceType = SourceType.YOUTUBE,
    content_url: str = "https://www.youtube.com/watch?v=abcdefghijk",
) -> ContentItem:
    ds = DataSource(
        user_id=user_id,
        source_type=source_type,
        external_id="ext-1",
        name="某频道",
        profile_url="https://www.youtube.com/",
    )
    db.add(ds)
    await db.commit()
    await db.refresh(ds)
    item = ContentItem(
        data_source_id=ds.id,
        platform_id="abcdefghijk",
        title="某视频",
        content_url=content_url,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


# -- POST /login/probe ------------------------------------------------------


@pytest.mark.parametrize(
    "state,expected",
    [(True, "logged_in"), (False, "logged_out"), (None, "inconclusive")],
)
async def test_login_probe_three_states(client, auth_headers, monkeypatch, state, expected):
    monkeypatch.setattr(cookies, "live_probe", lambda timeout=20: (state, "msg", {}))
    resp = await client.post("/api/content-analysis/login/probe", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == expected
    assert body["ok"] is (state is True)


async def test_login_probe_requires_auth(client):
    resp = await client.post("/api/content-analysis/login/probe")
    assert resp.status_code == 401


async def test_login_probe_offloads_to_thread(client, auth_headers, monkeypatch):
    """探测应在 to_thread 中执行，不在事件循环里阻塞。"""
    called = {}

    def fake_probe(timeout=20):
        called["timeout"] = timeout
        return (True, "ok", {})

    monkeypatch.setattr(cookies, "live_probe", fake_probe)

    import app.api.content_analysis as mod

    orig_to_thread = mod.asyncio.to_thread

    async def spy_to_thread(func, *args, **kwargs):
        called["to_thread"] = True
        return await orig_to_thread(func, *args, **kwargs)

    monkeypatch.setattr(mod.asyncio, "to_thread", spy_to_thread)
    resp = await client.post("/api/content-analysis/login/probe", headers=auth_headers)
    assert resp.status_code == 200
    assert called.get("to_thread") is True
    assert called.get("timeout") == mod._PROBE_TIMEOUT


# -- POST /logout -----------------------------------------------------------


async def test_logout_clears_cookies(client, auth_headers, monkeypatch):
    calls = {"n": 0}
    monkeypatch.setattr(cookies, "clear_cookies", lambda: calls.__setitem__("n", calls["n"] + 1))
    resp = await client.post("/api/content-analysis/logout", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert calls["n"] == 1


async def test_logout_requires_auth(client):
    resp = await client.post("/api/content-analysis/logout")
    assert resp.status_code == 401


# -- DELETE /sources/{sid}（软删除 / purge）+ 回收站 -------------------------


async def test_delete_source_default_soft(client, auth_headers, db, tmp_path, monkeypatch):
    monkeypatch.setattr(store, "base_dir", lambda: tmp_path)
    uid = await _user_id(db)
    src = await store.get_or_create_source(db, uid, "https://youtu.be/abcdefghijk")
    resp = await client.delete(
        f"/api/content-analysis/sources/{src.id}", headers=auth_headers
    )
    assert resp.status_code == 200
    # 仍在回收站（软删除）
    deleted = await client.get("/api/content-analysis/sources/deleted", headers=auth_headers)
    assert any(s["id"] == src.id for s in deleted.json())


async def test_delete_source_purge_true(client, auth_headers, db, tmp_path, monkeypatch):
    monkeypatch.setattr(store, "base_dir", lambda: tmp_path)
    uid = await _user_id(db)
    src = await store.get_or_create_source(db, uid, "https://youtu.be/abcdefghijk")
    resp = await client.delete(
        f"/api/content-analysis/sources/{src.id}?purge=true", headers=auth_headers
    )
    assert resp.status_code == 200
    from app.models.models import AnalysisSource

    assert await db.get(AnalysisSource, src.id) is None
    # 回收站也不含它
    deleted = await client.get("/api/content-analysis/sources/deleted", headers=auth_headers)
    assert all(s["id"] != src.id for s in deleted.json())


async def test_delete_source_not_found(client, auth_headers):
    resp = await client.delete("/api/content-analysis/sources/nope", headers=auth_headers)
    assert resp.status_code == 404


async def test_deleted_list_empty_initially(client, auth_headers):
    resp = await client.get("/api/content-analysis/sources/deleted", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_restore_source_route(client, auth_headers, db, tmp_path, monkeypatch):
    monkeypatch.setattr(store, "base_dir", lambda: tmp_path)
    uid = await _user_id(db)
    src = await store.get_or_create_source(db, uid, "https://youtu.be/abcdefghijk")
    await store.soft_delete_source(db, src.id, uid)
    resp = await client.post(
        f"/api/content-analysis/sources/{src.id}/restore", headers=auth_headers
    )
    assert resp.status_code == 200
    # 还原后出现在正常列表，不在回收站
    listing = await client.get("/api/content-analysis/artifacts", headers=auth_headers)
    assert any(s["id"] == src.id for s in listing.json()["sources"])


async def test_restore_source_not_found(client, auth_headers):
    resp = await client.post(
        "/api/content-analysis/sources/nope/restore", headers=auth_headers
    )
    assert resp.status_code == 404


async def test_purge_source_route(client, auth_headers, db, tmp_path, monkeypatch):
    monkeypatch.setattr(store, "base_dir", lambda: tmp_path)
    uid = await _user_id(db)
    src = await store.get_or_create_source(db, uid, "https://youtu.be/abcdefghijk")
    await store.soft_delete_source(db, src.id, uid)
    resp = await client.post(
        f"/api/content-analysis/sources/{src.id}/purge", headers=auth_headers
    )
    assert resp.status_code == 200
    from app.models.models import AnalysisSource

    assert await db.get(AnalysisSource, src.id) is None


async def test_purge_source_not_found(client, auth_headers):
    resp = await client.post(
        "/api/content-analysis/sources/nope/purge", headers=auth_headers
    )
    assert resp.status_code == 404


# -- POST /from-content-item/{id} ------------------------------------------


async def test_from_content_item_youtube_creates_artifact(
    client, auth_headers, db, monkeypatch
):
    monkeypatch.setattr(runner, "run_download", AsyncMock())
    uid = await _user_id(db)
    item = await _make_content_item(db, uid, SourceType.YOUTUBE)
    resp = await client.post(
        f"/api/content-analysis/from-content-item/{item.id}",
        json={"mode": "audio"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "audio"
    assert body["status"] == "queued"
    runner.run_download.assert_called_once()


async def test_from_content_item_default_mode_video(client, auth_headers, db, monkeypatch):
    monkeypatch.setattr(runner, "run_download", AsyncMock())
    uid = await _user_id(db)
    item = await _make_content_item(db, uid, SourceType.YOUTUBE)
    resp = await client.post(
        f"/api/content-analysis/from-content-item/{item.id}",
        json={},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["type"] == ArtifactType.VIDEO


async def test_from_content_item_non_youtube_400(client, auth_headers, db, monkeypatch):
    monkeypatch.setattr(runner, "run_download", AsyncMock())
    uid = await _user_id(db)
    item = await _make_content_item(db, uid, SourceType.TWITTER, content_url="https://x.com/a/1")
    resp = await client.post(
        f"/api/content-analysis/from-content-item/{item.id}",
        json={},
        headers=auth_headers,
    )
    assert resp.status_code == 400


async def test_from_content_item_missing_404(client, auth_headers):
    resp = await client.post(
        "/api/content-analysis/from-content-item/does-not-exist",
        json={},
        headers=auth_headers,
    )
    assert resp.status_code == 404


async def test_from_content_item_other_user_404(client, auth_headers, db, monkeypatch):
    monkeypatch.setattr(runner, "run_download", AsyncMock())
    # 用别的 user_id 建 data_source（不是当前登录用户）
    other = User(
        email="other@example.com",
        password_hash="x",
        display_name="Other",
    )
    db.add(other)
    await db.commit()
    await db.refresh(other)
    item = await _make_content_item(db, other.id, SourceType.YOUTUBE)
    resp = await client.post(
        f"/api/content-analysis/from-content-item/{item.id}",
        json={},
        headers=auth_headers,
    )
    assert resp.status_code == 404


async def test_from_content_item_requires_auth(client):
    resp = await client.post("/api/content-analysis/from-content-item/x", json={})
    assert resp.status_code == 401
