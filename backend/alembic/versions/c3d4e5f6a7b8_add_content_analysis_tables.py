"""add_content_analysis_tables

Revision ID: c3d4e5f6a7b8
Revises: b1c2d3e4f5a6
Create Date: 2026-06-19 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analysis_sources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("video_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("author", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "video_id", name="uq_analysis_sources_user_video"
        ),
    )
    op.create_index(
        op.f("ix_analysis_sources_user_id"), "analysis_sources", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_analysis_sources_video_id"), "analysis_sources", ["video_id"], unique=False
    )

    op.create_table(
        "analysis_artifacts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.Column(
            "type", sa.Enum("video", "audio", "text", name="artifacttype"), nullable=False
        ),
        sa.Column(
            "stage",
            sa.Enum("download", "transcribe", name="artifactstage"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "running",
                "processing",
                "finished",
                "error",
                "canceled",
                name="artifactstatus",
            ),
            nullable=False,
        ),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("filename", sa.String(length=500), nullable=True),
        sa.Column("filepath", sa.Text(), nullable=True),
        sa.Column("size", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("error_log", sa.Text(), nullable=True),
        sa.Column("source_artifact_id", sa.String(length=36), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["source_id"], ["analysis_sources.id"]),
        sa.ForeignKeyConstraint(["source_artifact_id"], ["analysis_artifacts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_analysis_artifacts_source_id"),
        "analysis_artifacts",
        ["source_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_analysis_artifacts_source_id"), table_name="analysis_artifacts"
    )
    op.drop_table("analysis_artifacts")
    op.drop_index(op.f("ix_analysis_sources_video_id"), table_name="analysis_sources")
    op.drop_index(op.f("ix_analysis_sources_user_id"), table_name="analysis_sources")
    op.drop_table("analysis_sources")
    sa.Enum(name="artifacttype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="artifactstage").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="artifactstatus").drop(op.get_bind(), checkfirst=True)
