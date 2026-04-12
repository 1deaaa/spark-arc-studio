"""auto_llm_20260412_031832

Revision ID: ff19691a6f79
Revises: 805c2aaebae9
Create Date: 2026-04-12 03:21:37.605421

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ff19691a6f79'
down_revision: Union[str, None] = '805c2aaebae9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级数据库：点数定价从平台级单列迁移到模型级输入/输出分列"""
    # llm_platform_models: 删除旧的单价列，添加输入/输出分列（Float）
    with op.batch_alter_table('llm_platform_models', schema=None) as batch_op:
        batch_op.drop_column('sys_credit_price_per_million_tokens')
        batch_op.add_column(sa.Column('sys_credit_input_price_per_million', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('sys_credit_output_price_per_million', sa.Float(), nullable=True))

    # llm_platforms: 仅删除旧的单价列（input/output 列从未在链中添加，无需 drop）
    with op.batch_alter_table('llm_platforms', schema=None) as batch_op:
        batch_op.drop_column('sys_credit_price_per_million_tokens')


def downgrade() -> None:
    """回滚数据库：恢复平台级单价列，移除模型级输入/输出分列"""
    with op.batch_alter_table('llm_platforms', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sys_credit_price_per_million_tokens', sa.INTEGER(), nullable=True))

    with op.batch_alter_table('llm_platform_models', schema=None) as batch_op:
        batch_op.drop_column('sys_credit_output_price_per_million')
        batch_op.drop_column('sys_credit_input_price_per_million')
        batch_op.add_column(sa.Column('sys_credit_price_per_million_tokens', sa.INTEGER(), nullable=True))
