"""add_disable_to_llmodels

Revision ID: 998aa87bdfde
Revises: faac9856d485
Create Date: 2026-02-13 15:16:53.590038

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '998aa87bdfde'
down_revision: Union[str, None] = 'faac9856d485'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级数据库"""
    with op.batch_alter_table('llm_platform_models', schema=None) as batch_op:
        batch_op.add_column(sa.Column('disable', sa.Integer(), nullable=False, server_default='0'))
        batch_op.create_index(batch_op.f('ix_llm_platform_models_disable'), ['disable'], unique=False)


def downgrade() -> None:
    """回滚数据库"""
    with op.batch_alter_table('llm_platform_models', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_llm_platform_models_disable'))
        batch_op.drop_column('disable')
