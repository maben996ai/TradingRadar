"""add_calendar_events_and_tracked_tickers

Revision ID: e5b7c3a91f24
Revises: d4a9c1b73e52
Create Date: 2026-06-09 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5b7c3a91f24"
down_revision: Union[str, None] = "d4a9c1b73e52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "calendar_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_key", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("title_en", sa.String(length=255), nullable=False),
        sa.Column("country", sa.String(length=40), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("all_day", sa.Boolean(), nullable=False),
        sa.Column("importance", sa.Integer(), nullable=False),
        sa.Column("impact_assets", sa.String(length=255), nullable=True),
        sa.Column("previous", sa.Float(), nullable=True),
        sa.Column("forecast", sa.Float(), nullable=True),
        sa.Column("actual", sa.Float(), nullable=True),
        sa.Column("value_unit", sa.String(length=20), nullable=True),
        sa.Column("ticker", sa.String(length=20), nullable=True),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=60), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_key", name="uq_calendar_events_event_key"),
    )
    op.create_index(
        op.f("ix_calendar_events_event_key"), "calendar_events", ["event_key"], unique=False
    )
    op.create_index(
        op.f("ix_calendar_events_category"), "calendar_events", ["category"], unique=False
    )
    op.create_index(
        op.f("ix_calendar_events_scheduled_at"), "calendar_events", ["scheduled_at"], unique=False
    )

    op.create_table(
        "tracked_tickers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("ticker", sa.String(length=20), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "ticker", name="uq_tracked_tickers_user_ticker"),
    )
    op.create_index(
        op.f("ix_tracked_tickers_user_id"), "tracked_tickers", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_tracked_tickers_user_id"), table_name="tracked_tickers")
    op.drop_table("tracked_tickers")
    op.drop_index(op.f("ix_calendar_events_scheduled_at"), table_name="calendar_events")
    op.drop_index(op.f("ix_calendar_events_category"), table_name="calendar_events")
    op.drop_index(op.f("ix_calendar_events_event_key"), table_name="calendar_events")
    op.drop_table("calendar_events")
