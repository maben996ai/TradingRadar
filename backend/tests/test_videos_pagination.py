"""
TDD: 视频流 API — 游标分页 + 状态更新
Round 1: GET /api/content-items 返回分页结构 {items, next_cursor, has_more}，支持 limit
"""

from datetime import UTC, datetime, timedelta


from app.models.models import DataSource, SourceType, ContentItem


# ── seed helpers ──────────────────────────────────────────────────────────────


async def _seed_data_source(db, user_id: str, suffix: str = "1") -> DataSource:
    source = DataSource(
        user_id=user_id,
        source_type=SourceType.BILIBILI,
        external_id=f"uid_{suffix}",
        name=f"Creator {suffix}",
        profile_url=f"https://space.bilibili.com/{suffix}",
    )
    db.add(source)
    await db.flush()
    return source


async def _seed_videos(
    db, source: DataSource, n: int, base_dt: datetime | None = None
) -> list[ContentItem]:
    base = base_dt or datetime(2024, 1, 1, tzinfo=UTC)
    videos = []
    for i in range(n):
        v = ContentItem(
            data_source_id=source.id,
            platform_id=f"BV{source.external_id}_{i}",
            title=f"Video {i}",
            content_url=f"https://www.bilibili.com/video/BV{i}",
            published_at=base + timedelta(hours=i),
        )
        db.add(v)
        videos.append(v)
    await db.commit()
    return videos


# ── Round 1: 分页响应结构 ─────────────────────────────────────────────────────


class TestVideosPaginatedResponse:
    async def test_response_has_items_key(self, client, auth_headers, db):
        me = await client.get("/api/auth/me", headers=auth_headers)
        user_id = me.json()["id"]
        source = await _seed_data_source(db, user_id)
        await _seed_videos(db, source, 3)

        resp = await client.get("/api/content-items", headers=auth_headers)
        assert resp.status_code == 200
        assert "items" in resp.json()

    async def test_response_has_next_cursor_key(self, client, auth_headers, db):
        me = await client.get("/api/auth/me", headers=auth_headers)
        user_id = me.json()["id"]
        source = await _seed_data_source(db, user_id)
        await _seed_videos(db, source, 3)

        resp = await client.get("/api/content-items", headers=auth_headers)
        assert "next_cursor" in resp.json()

    async def test_response_has_has_more_key(self, client, auth_headers, db):
        me = await client.get("/api/auth/me", headers=auth_headers)
        user_id = me.json()["id"]
        source = await _seed_data_source(db, user_id)
        await _seed_videos(db, source, 3)

        resp = await client.get("/api/content-items", headers=auth_headers)
        assert "has_more" in resp.json()

    async def test_items_contain_video_fields(self, client, auth_headers, db):
        me = await client.get("/api/auth/me", headers=auth_headers)
        user_id = me.json()["id"]
        source = await _seed_data_source(db, user_id)
        await _seed_videos(db, source, 1)

        resp = await client.get("/api/content-items", headers=auth_headers)
        item = resp.json()["items"][0]
        assert "id" in item
        assert "title" in item
        assert "content_url" in item
        assert "published_at" in item
        assert "data_source_name" in item

    async def test_items_include_duration_seconds_when_present_in_raw_data(
        self, client, auth_headers, db
    ):
        me = await client.get("/api/auth/me", headers=auth_headers)
        user_id = me.json()["id"]
        source = await _seed_data_source(db, user_id)
        video = ContentItem(
            data_source_id=source.id,
            platform_id="BV_duration",
            title="Video with duration",
            content_url="https://www.bilibili.com/video/BV_duration",
            published_at=datetime(2024, 1, 1, tzinfo=UTC),
            raw_data={"length": "01:08:20"},
        )
        db.add(video)
        await db.commit()

        resp = await client.get("/api/content-items", headers=auth_headers)
        item = resp.json()["items"][0]
        assert item["duration_seconds"] == 4100

    async def test_limit_param_restricts_items(self, client, auth_headers, db):
        me = await client.get("/api/auth/me", headers=auth_headers)
        user_id = me.json()["id"]
        source = await _seed_data_source(db, user_id)
        await _seed_videos(db, source, 10)

        resp = await client.get("/api/content-items?limit=3", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 3

    async def test_has_more_true_when_more_exist(self, client, auth_headers, db):
        me = await client.get("/api/auth/me", headers=auth_headers)
        user_id = me.json()["id"]
        source = await _seed_data_source(db, user_id)
        await _seed_videos(db, source, 5)

        resp = await client.get("/api/content-items?limit=3", headers=auth_headers)
        assert resp.json()["has_more"] is True

    async def test_has_more_false_when_all_returned(self, client, auth_headers, db):
        me = await client.get("/api/auth/me", headers=auth_headers)
        user_id = me.json()["id"]
        source = await _seed_data_source(db, user_id)
        await _seed_videos(db, source, 3)

        resp = await client.get("/api/content-items?limit=10", headers=auth_headers)
        assert resp.json()["has_more"] is False

    async def test_next_cursor_is_none_when_no_more(self, client, auth_headers, db):
        me = await client.get("/api/auth/me", headers=auth_headers)
        user_id = me.json()["id"]
        source = await _seed_data_source(db, user_id)
        await _seed_videos(db, source, 2)

        resp = await client.get("/api/content-items?limit=10", headers=auth_headers)
        assert resp.json()["next_cursor"] is None

    async def test_next_cursor_is_string_when_has_more(self, client, auth_headers, db):
        me = await client.get("/api/auth/me", headers=auth_headers)
        user_id = me.json()["id"]
        source = await _seed_data_source(db, user_id)
        await _seed_videos(db, source, 5)

        resp = await client.get("/api/content-items?limit=3", headers=auth_headers)
        assert isinstance(resp.json()["next_cursor"], str)

    async def test_empty_db_returns_empty_items(self, client, auth_headers):
        resp = await client.get("/api/content-items", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["items"] == []
        assert resp.json()["has_more"] is False
        assert resp.json()["next_cursor"] is None

    async def test_requires_auth(self, client):
        resp = await client.get("/api/content-items")
        assert resp.status_code == 401


# ── Round 2: cursor 翻页 ──────────────────────────────────────────────────────


class TestVideosCursorPagination:
    async def test_second_page_has_no_overlap_with_first(self, client, auth_headers, db):
        me = await client.get("/api/auth/me", headers=auth_headers)
        user_id = me.json()["id"]
        source = await _seed_data_source(db, user_id)
        await _seed_videos(db, source, 6)

        r1 = await client.get("/api/content-items?limit=3", headers=auth_headers)
        cursor = r1.json()["next_cursor"]
        r2 = await client.get(f"/api/content-items?limit=3&cursor={cursor}", headers=auth_headers)

        ids1 = {v["id"] for v in r1.json()["items"]}
        ids2 = {v["id"] for v in r2.json()["items"]}
        assert ids1.isdisjoint(ids2)

    async def test_cursor_traversal_covers_all_videos(self, client, auth_headers, db):
        me = await client.get("/api/auth/me", headers=auth_headers)
        user_id = me.json()["id"]
        source = await _seed_data_source(db, user_id)
        await _seed_videos(db, source, 7)

        all_ids: set[str] = set()
        cursor = None
        while True:
            url = "/api/content-items?limit=3"
            if cursor:
                url += f"&cursor={cursor}"
            resp = await client.get(url, headers=auth_headers)
            body = resp.json()
            all_ids.update(v["id"] for v in body["items"])
            cursor = body["next_cursor"]
            if not body["has_more"]:
                break

        assert len(all_ids) == 7

    async def test_second_page_items_older_than_first(self, client, auth_headers, db):
        me = await client.get("/api/auth/me", headers=auth_headers)
        user_id = me.json()["id"]
        source = await _seed_data_source(db, user_id)
        await _seed_videos(db, source, 6)

        r1 = await client.get("/api/content-items?limit=3", headers=auth_headers)
        cursor = r1.json()["next_cursor"]
        r2 = await client.get(f"/api/content-items?limit=3&cursor={cursor}", headers=auth_headers)

        oldest_p1 = min(v["published_at"] for v in r1.json()["items"])
        newest_p2 = max(v["published_at"] for v in r2.json()["items"])
        assert newest_p2 <= oldest_p1

    async def test_invalid_cursor_returns_400(self, client, auth_headers):
        resp = await client.get("/api/content-items?cursor=notvalidbase64!!", headers=auth_headers)
        assert resp.status_code == 400

    async def test_cursor_page_has_correct_has_more(self, client, auth_headers, db):
        me = await client.get("/api/auth/me", headers=auth_headers)
        user_id = me.json()["id"]
        source = await _seed_data_source(db, user_id)
        await _seed_videos(db, source, 4)

        r1 = await client.get("/api/content-items?limit=3", headers=auth_headers)
        cursor = r1.json()["next_cursor"]
        r2 = await client.get(f"/api/content-items?limit=3&cursor={cursor}", headers=auth_headers)

        assert r1.json()["has_more"] is True
        assert r2.json()["has_more"] is False

    async def test_last_page_next_cursor_is_none(self, client, auth_headers, db):
        me = await client.get("/api/auth/me", headers=auth_headers)
        user_id = me.json()["id"]
        source = await _seed_data_source(db, user_id)
        await _seed_videos(db, source, 4)

        r1 = await client.get("/api/content-items?limit=3", headers=auth_headers)
        cursor = r1.json()["next_cursor"]
        r2 = await client.get(f"/api/content-items?limit=3&cursor={cursor}", headers=auth_headers)

        assert r2.json()["next_cursor"] is None

    async def test_cursor_handles_same_published_at_without_duplicates(
        self, client, auth_headers, db
    ):
        me = await client.get("/api/auth/me", headers=auth_headers)
        user_id = me.json()["id"]
        source = await _seed_data_source(db, user_id)
        same_dt = datetime(2024, 1, 1, tzinfo=UTC)
        await _seed_videos(db, source, 5, base_dt=same_dt)

        r1 = await client.get("/api/content-items?limit=3", headers=auth_headers)
        cursor = r1.json()["next_cursor"]
        r2 = await client.get(f"/api/content-items?limit=3&cursor={cursor}", headers=auth_headers)

        ids1 = {v["id"] for v in r1.json()["items"]}
        ids2 = {v["id"] for v in r2.json()["items"]}

        assert len(r1.json()["items"]) == 3
        assert len(r2.json()["items"]) == 2
        assert ids1.isdisjoint(ids2)
        assert r2.json()["has_more"] is False
        assert r2.json()["next_cursor"] is None
