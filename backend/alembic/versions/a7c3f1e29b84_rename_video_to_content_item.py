"""rename_video_to_content_item

将「视频」专用模型泛化为通用内容模型：
- 表 videos -> content_items
- 列 platform_video_id -> platform_id，video_url -> content_url
- crawl_logs.videos_found -> items_found
- 同步重命名约束与索引

Revision ID: a7c3f1e29b84
Revises: e6b4a21c9d33
Create Date: 2026-06-08 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7c3f1e29b84"
down_revision: Union[str, None] = "e6b4a21c9d33"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    is_pg = conn.dialect.name == "postgresql"

    # 1. 重命名列
    op.alter_column("videos", "platform_video_id", new_column_name="platform_id")
    op.alter_column("videos", "video_url", new_column_name="content_url")
    op.alter_column("crawl_logs", "videos_found", new_column_name="items_found")

    # 2. 重命名约束与索引（PostgreSQL 专用 DDL）
    if is_pg:
        conn.execute(
            sa.text(
                "ALTER TABLE videos RENAME CONSTRAINT "
                "uq_videos_data_source_platform_video TO uq_content_items_data_source_platform"
            )
        )
        conn.execute(
            sa.text(
                "ALTER TABLE videos RENAME CONSTRAINT "
                "fk_videos_data_source TO fk_content_items_data_source"
            )
        )
        conn.execute(
            sa.text("ALTER INDEX IF EXISTS ix_videos_creator_id RENAME TO ix_content_items_data_source_id")
        )
        conn.execute(
            sa.text(
                "ALTER INDEX IF EXISTS ix_videos_platform_video_id "
                "RENAME TO ix_content_items_platform_id"
            )
        )
        conn.execute(
            sa.text("ALTER INDEX IF EXISTS ix_videos_notified_at RENAME TO ix_content_items_notified_at")
        )

    # 3. 重命名表
    op.rename_table("videos", "content_items")


def downgrade() -> None:
    conn = op.get_bind()
    is_pg = conn.dialect.name == "postgresql"

    op.rename_table("content_items", "videos")

    if is_pg:
        conn.execute(
            sa.text("ALTER INDEX IF EXISTS ix_content_items_notified_at RENAME TO ix_videos_notified_at")
        )
        conn.execute(
            sa.text(
                "ALTER INDEX IF EXISTS ix_content_items_platform_id "
                "RENAME TO ix_videos_platform_video_id"
            )
        )
        conn.execute(
            sa.text("ALTER INDEX IF EXISTS ix_content_items_data_source_id RENAME TO ix_videos_creator_id")
        )
        conn.execute(
            sa.text(
                "ALTER TABLE videos RENAME CONSTRAINT "
                "fk_content_items_data_source TO fk_videos_data_source"
            )
        )
        conn.execute(
            sa.text(
                "ALTER TABLE videos RENAME CONSTRAINT "
                "uq_content_items_data_source_platform TO uq_videos_data_source_platform_video"
            )
        )

    op.alter_column("crawl_logs", "items_found", new_column_name="videos_found")
    op.alter_column("videos", "content_url", new_column_name="video_url")
    op.alter_column("videos", "platform_id", new_column_name="platform_video_id")
