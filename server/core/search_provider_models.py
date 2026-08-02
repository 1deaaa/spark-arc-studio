"""SparkArc 联网搜索功能的用户覆盖配置模型。

该表继续存放在 LLM 数据库中，但模型所有权属于 SparkArc。Matchbox 只提供
通用的 SQLAlchemy Base 和密钥轮换回调，不再知道 Exa、Tavily 等业务概念。
"""

from __future__ import annotations

from sqlalchemy import Column, Integer, String, UniqueConstraint

from llm.agen_matchbox.models import Base


class SearchProviderUserConfig(Base):
    """用户对 SparkArc 搜索提供商的 URL 与密钥覆盖。"""

    __tablename__ = "search_provider_user_configs"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_search_provider_user_provider"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), nullable=False, index=True)
    provider = Column(String(32), nullable=False, index=True)
    url = Column(String(1024), nullable=False)
    api_key = Column(String(1024), nullable=True)
