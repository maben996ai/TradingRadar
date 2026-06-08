"""remove_legacy_source_type

Revision ID: c7f0a9d2e4b1
Revises: b8d4e2f6a1c0
Create Date: 2026-06-08 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c7f0a9d2e4b1"
down_revision: Union[str, None] = "b8d4e2f6a1c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

LEGACY_SOURCE_TYPE = "BILI" "BILI"


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return

    conn.execute(
        sa.text(
            """
            DELETE FROM content_items
            WHERE data_source_id IN (
                SELECT id FROM data_sources WHERE source_type::text = :legacy_source_type
            )
            """
        ),
        {"legacy_source_type": LEGACY_SOURCE_TYPE},
    )
    conn.execute(
        sa.text(
            """
            DELETE FROM crawl_logs
            WHERE data_source_id IN (
                SELECT id FROM data_sources WHERE source_type::text = :legacy_source_type
            )
            """
        ),
        {"legacy_source_type": LEGACY_SOURCE_TYPE},
    )
    conn.execute(
        sa.text("DELETE FROM data_sources WHERE source_type::text = :legacy_source_type"),
        {"legacy_source_type": LEGACY_SOURCE_TYPE},
    )

    conn.execute(sa.text("ALTER TYPE sourcetype RENAME TO sourcetype_old"))
    conn.execute(
        sa.text(
            """
            CREATE TYPE sourcetype AS ENUM (
                'YOUTUBE',
                'TWITTER',
                'wechat_article',
                'website',
                'rss',
                'pdf'
            )
            """
        )
    )
    conn.execute(
        sa.text(
            """
            ALTER TABLE data_sources
            ALTER COLUMN source_type TYPE sourcetype
            USING source_type::text::sourcetype
            """
        )
    )
    conn.execute(sa.text("DROP TYPE sourcetype_old"))


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return

    conn.execute(sa.text("ALTER TYPE sourcetype RENAME TO sourcetype_old"))
    conn.execute(
        sa.text(
            f"""
            CREATE TYPE sourcetype AS ENUM (
                '{LEGACY_SOURCE_TYPE}',
                'YOUTUBE',
                'TWITTER',
                'wechat_article',
                'website',
                'rss',
                'pdf'
            )
            """
        )
    )
    conn.execute(
        sa.text(
            """
            ALTER TABLE data_sources
            ALTER COLUMN source_type TYPE sourcetype
            USING source_type::text::sourcetype
            """
        )
    )
    conn.execute(sa.text("DROP TYPE sourcetype_old"))
