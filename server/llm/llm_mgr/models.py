"""
数据库模型模块
定义所有 SQLAlchemy ORM 模型
"""

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import (
    declarative_base,
    relationship,
)

Base = declarative_base()


class LLMPlatform(Base):
    """LLM 平台模型"""
    __tablename__ = "llm_platforms"
    id = Column(Integer, primary_key=True)
    name = Column(String(80), default="未命名平台", index=True)
    user_id = Column(String(255), nullable=True, index=True)
    base_url = Column(String(255), nullable=False)
    api_key = Column(String(512), nullable=True)
    is_sys = Column(Integer, default=0) 
    hide = Column(Integer, default=0) 
    models = relationship("LLModels", backref="platform", cascade="all, delete-orphan")


class LLMSysPlatformKey(Base):
    """系统平台用户密钥模型（用户为系统平台设置的自定义 API Key）"""
    __tablename__ = "llm_sys_platform_keys"
    __table_args__ = (
        UniqueConstraint("user_id", "platform_id", name="uq_sys_platform_key_user_platform"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), nullable=False, index=True)
    platform_id = Column(
        Integer,
        ForeignKey("llm_platforms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    api_key = Column(String(512), nullable=True)
    hide = Column(Integer, default=0)
    platform = relationship("LLMPlatform", backref="sys_keys")


class LLModels(Base):
    """LLM 模型配置"""
    __tablename__ = "llm_platform_models"
    id = Column(Integer, primary_key=True)
    platform_id = Column(
        Integer,
        ForeignKey("llm_platforms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    model_name = Column(String(120), nullable=False, index=True)
    display_name = Column(String(120), nullable=True)
    extra_body = Column(String(1024), nullable=True)
    is_embedding = Column(Integer, default=0, index=True)


class UserEmbeddingSelection(Base):
    """用户 Embedding 选择配置（单用户单配置）"""
    __tablename__ = "user_embedding_selections"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_embedding_selection"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), nullable=False, index=True)
    platform_id = Column(
        Integer,
        ForeignKey("llm_platforms.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    model_id = Column(
        Integer,
        ForeignKey("llm_platform_models.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    platform = relationship("LLMPlatform")
    model = relationship("LLModels")


class UserModelUsage(Base):
    """用户模型用途配置（如：主模型、快速模型、推理模型）"""
    __tablename__ = "user_model_usages"
    __table_args__ = (
        UniqueConstraint("user_id", "usage_key", name="uq_user_usage_key"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), nullable=False, index=True)
    usage_key = Column(String(64), nullable=False, index=True)
    usage_label = Column(String(120), nullable=False)
    selected_platform_id = Column(
        Integer,
        ForeignKey("llm_platforms.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    selected_model_id = Column(
        Integer,
        ForeignKey("llm_platform_models.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # 添加关系以支持 selectinload (解决 N+1 问题)
    platform = relationship("LLMPlatform")
    model = relationship("LLModels")


class AgentModelBinding(Base):
    """Agent 模型绑定配置"""
    __tablename__ = "agent_model_bindings"
    __table_args__ = (
        UniqueConstraint("user_id", "agent_name", name="uq_user_agent_binding"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), nullable=False, index=True)
    agent_name = Column(String(120), nullable=False, index=True)
    target_type = Column(String(32), default="usage")  # 'usage' or 'direct'
    usage_key = Column(String(64), nullable=True)
    platform_id = Column(Integer, nullable=True)
    model_id = Column(Integer, nullable=True)


class ModelUsageStats(Base):
    """
    [已废弃] 累加汇总型统计表。
    请使用 UsageLogEntry 进行时序查询。
    保留此表仅为兼容旧数据，新代码不应再使用。
    """
    __tablename__ = "model_usage_stats"
    __table_args__ = (
        UniqueConstraint("user_id", "model_id", name="uq_user_model_stats"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), nullable=False, index=True)
    model_id = Column(
        Integer,
        ForeignKey("llm_platform_models.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Token 统计
    prompt_tokens = Column(Integer, default=0)       # 输入 token 总数
    completion_tokens = Column(Integer, default=0)   # 输出 token 总数
    total_tokens = Column(Integer, default=0)        # 总 token 数
    # 调用统计
    call_count = Column(Integer, default=0)          # 调用次数
    success_count = Column(Integer, default=0)       # 成功次数
    error_count = Column(Integer, default=0)         # 失败次数
    # 关系
    model = relationship("LLModels")


class UsageLogEntry(Base):
    """
    单次 LLM 调用的详细日志（时序数据）。
    用于支持时间范围查询，如"过去24小时的用量"。
    """
    __tablename__ = "usage_log_entries"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), nullable=False, index=True)
    model_id = Column(
        Integer,
        ForeignKey("llm_platform_models.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Token 详情
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    
    # 调用状态 (1=成功, 0=失败)
    success = Column(Integer, default=1)
    
    # 上下文信息（便于审计和调试）
    agent_name = Column(String(120), nullable=True, index=True)
    context_key = Column(String(255), nullable=True)
    
    # 时间戳
    created_at = Column(DateTime, default=func.now(), index=True)
    
    # 关系
    model = relationship("LLModels")
