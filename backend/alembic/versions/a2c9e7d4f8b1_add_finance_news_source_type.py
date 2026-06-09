"""add_finance_news_source_type

Revision ID: a2c9e7d4f8b1
Revises: e5b7c3a91f24
Create Date: 2026-06-09 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a2c9e7d4f8b1"
down_revision: Union[str, None] = "e5b7c3a91f24"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        conn.execute(sa.text("ALTER TYPE sourcetype ADD VALUE IF NOT EXISTS 'FINANCE_NEWS'"))


def downgrade() -> None:
    # PostgreSQL enum values cannot be removed safely without rebuilding the type.
    pass
