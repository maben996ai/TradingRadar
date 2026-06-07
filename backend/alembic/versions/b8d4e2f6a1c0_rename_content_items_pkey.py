"""rename_content_items_pkey

重命名表后遗留的主键约束名（PostgreSQL 重命名表不会自动改主键约束名）：
videos_pkey -> content_items_pkey

Revision ID: b8d4e2f6a1c0
Revises: a7c3f1e29b84
Create Date: 2026-06-08 00:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b8d4e2f6a1c0"
down_revision: Union[str, None] = "a7c3f1e29b84"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        conn.execute(
            sa.text("ALTER INDEX IF EXISTS videos_pkey RENAME TO content_items_pkey")
        )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        conn.execute(
            sa.text("ALTER INDEX IF EXISTS content_items_pkey RENAME TO videos_pkey")
        )
