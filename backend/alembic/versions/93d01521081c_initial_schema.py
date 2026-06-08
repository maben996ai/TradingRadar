"""initial schema

Revision ID: 93d01521081c
Revises:
Create Date: 2026-04-14 00:35:57.144279

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "93d01521081c"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "user_settings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("feishu_webhook_url", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )

    op.create_table(
        "creators",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("platform", sa.Enum("YOUTUBE", name="platform"), nullable=False),
        sa.Column("platform_creator_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("profile_url", sa.Text(), nullable=False),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("notifications_enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "platform", "platform_creator_id", name="uq_creators_user_platform_creator"
        ),
    )
    op.create_index(
        op.f("ix_creators_platform_creator_id"), "creators", ["platform_creator_id"], unique=False
    )
    op.create_index(op.f("ix_creators_user_id"), "creators", ["user_id"], unique=False)

    op.create_table(
        "videos",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("creator_id", sa.String(length=36), nullable=False),
        sa.Column("platform_video_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        sa.Column("video_url", sa.Text(), nullable=False),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("raw_data", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["creator_id"], ["creators.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "creator_id", "platform_video_id", name="uq_videos_creator_platform_video"
        ),
    )
    op.create_index(op.f("ix_videos_creator_id"), "videos", ["creator_id"], unique=False)
    op.create_index(
        op.f("ix_videos_platform_video_id"), "videos", ["platform_video_id"], unique=False
    )

    op.create_table(
        "crawl_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("creator_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("videos_found", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["creator_id"], ["creators.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_crawl_logs_creator_id"), "crawl_logs", ["creator_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_crawl_logs_creator_id"), table_name="crawl_logs")
    op.drop_table("crawl_logs")
    op.drop_index(op.f("ix_videos_platform_video_id"), table_name="videos")
    op.drop_index(op.f("ix_videos_creator_id"), table_name="videos")
    op.drop_table("videos")
    op.drop_index(op.f("ix_creators_user_id"), table_name="creators")
    op.drop_index(op.f("ix_creators_platform_creator_id"), table_name="creators")
    op.drop_table("creators")
    op.drop_table("user_settings")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
