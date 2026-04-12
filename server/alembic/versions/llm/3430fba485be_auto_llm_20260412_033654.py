"""auto_llm_20260412_033654

Revision ID: 3430fba485be
Revises: ff19691a6f79
Create Date: 2026-04-12 03:36:55.099518

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3430fba485be'
down_revision: Union[str, None] = 'ff19691a6f79'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级数据库（空操作：前序迁移 ff19691a6f79 已直接以 Float 类型添加列）"""
    pass


def downgrade() -> None:
    """回滚数据库（空操作：对应 upgrade 为空）"""
    pass
