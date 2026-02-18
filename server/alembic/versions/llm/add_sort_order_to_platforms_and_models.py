"""add_sort_order_to_platforms_and_models

Revision ID: b7c3e4f5a6d8
Revises: 998aa87bdfde
Create Date: 2026-02-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c3e4f5a6d8'
down_revision: Union[str, None] = '998aa87bdfde'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """为 platform 和 models 表添加 sort_order 列"""
    with op.batch_alter_table('llm_platforms', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'))

    with op.batch_alter_table('llm_platform_models', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    """回滚：移除 sort_order 列"""
    with op.batch_alter_table('llm_platform_models', schema=None) as batch_op:
        batch_op.drop_column('sort_order')

    with op.batch_alter_table('llm_platforms', schema=None) as batch_op:
        batch_op.drop_column('sort_order')
