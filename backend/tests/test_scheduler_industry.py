from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.models import DataSource, SourceType, User
from app.services import scheduler
from app.services.research.rss_sources import RSS_BUILTIN_SOURCES


@pytest.fixture
def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class TestEnsureBuiltinRssSources:
    async def test_provisions_rss_sources_per_user(self, db, session_factory):
        db.add(User(email="rss@example.com", password_hash="x", display_name="R"))
        await db.commit()

        with patch("app.services.scheduler.AsyncSessionLocal", session_factory):
            inserted = await scheduler.ensure_builtin_rss_sources()

        assert inserted == len(RSS_BUILTIN_SOURCES)
        rows = list(
            await db.scalars(
                select(DataSource).where(DataSource.source_type == SourceType.RSS)
            )
        )
        assert len(rows) == len(RSS_BUILTIN_SOURCES)
        assert {r.external_id for r in rows} == {s["url"] for s in RSS_BUILTIN_SOURCES}

    async def test_idempotent_no_duplicate(self, db, session_factory):
        db.add(User(email="rss2@example.com", password_hash="x", display_name="R"))
        await db.commit()
        with patch("app.services.scheduler.AsyncSessionLocal", session_factory):
            await scheduler.ensure_builtin_rss_sources()
            second = await scheduler.ensure_builtin_rss_sources()
        assert second == 0
