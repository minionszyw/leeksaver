"""add_trading_calendar_table

Revision ID: da293a543f93
Revises: 9ea5074f1d61
Create Date: 2026-01-01 01:39:48.653782

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "da293a543f93"
down_revision: Union[str, None] = "9ea5074f1d61"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table("trading_calendar",
    sa.Column("trade_date", sa.Date(), nullable=False, comment="交易日期"),
    sa.Column("is_open", sa.Boolean(), nullable=False, comment="是否开市"),
    sa.PrimaryKeyConstraint("trade_date", name=op.f("pk_trading_calendar"))
    )


def downgrade() -> None:
    op.drop_table("trading_calendar")
