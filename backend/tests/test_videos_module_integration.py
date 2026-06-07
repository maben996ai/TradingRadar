from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

from app.api.content_items import list_content_items
from app.models.models import DataSource, SourceType, User, ContentItem


async def _seed_user(db) -> User:
    user = User(
        email="integration@example.com",
        password_hash="hashed",
        display_name="Integration Tester",
    )
    db.add(user)
    await db.flush()
    return user


async def _seed_data_source(db, user_id: str) -> DataSource:
    source = DataSource(
        user_id=user_id,
        source_type=SourceType.BILIBILI,
        external_id="integration_uid",
        name="Integration Creator",
        profile_url="https://space.bilibili.com/integration_uid",
    )
    db.add(source)
    await db.flush()
    return source


async def _seed_videos(db, source: DataSource, count: int) -> None:
    base = datetime(2024, 1, 1, tzinfo=UTC)
    for index in range(count):
        db.add(
            ContentItem(
                data_source_id=source.id,
                platform_id=f"BV{index}",
                title=f"Video {index}",
                content_url=f"https://www.bilibili.com/video/BV{index}",
                published_at=base + timedelta(hours=index),
            )
        )
    await db.commit()


class TestVideosModuleIntegration:
    async def test_list_videos_paginates_with_cursor_directly(self, db):
        user = await _seed_user(db)
        source = await _seed_data_source(db, user.id)
        await _seed_videos(db, source, 6)

        first_page = await list_content_items(
            source_type=None, cursor=None, limit=3, current_user=user, db=db
        )
        second_page = await list_content_items(
            source_type=None,
            cursor=first_page.next_cursor,
            limit=3,
            current_user=user,
            db=db,
        )

        first_ids = {item.id for item in first_page.items}
        second_ids = {item.id for item in second_page.items}

        assert len(first_page.items) == 3
        assert len(second_page.items) == 3
        assert first_ids.isdisjoint(second_ids)
        assert second_page.has_more is False

    async def test_list_videos_raises_400_for_invalid_cursor_directly(self, db):
        user = await _seed_user(db)

        with pytest.raises(HTTPException) as exc_info:
            await list_content_items(source_type=None, cursor="invalid", limit=3, current_user=user, db=db)

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Invalid cursor"
