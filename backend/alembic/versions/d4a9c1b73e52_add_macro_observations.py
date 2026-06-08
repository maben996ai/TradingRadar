"""add_macro_observations

Revision ID: d4a9c1b73e52
Revises: c7f0a9d2e4b1
Create Date: 2026-06-08 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4a9c1b73e52"
down_revision: Union[str, None] = "c7f0a9d2e4b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "macro_observations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("indicator_key", sa.String(length=64), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("indicator_key", "date", name="uq_macro_observations_key_date"),
    )
    op.create_index(
        op.f("ix_macro_observations_indicator_key"),
        "macro_observations",
        ["indicator_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_macro_observations_indicator_key"),
        table_name="macro_observations",
    )
    op.drop_table("macro_observations")
