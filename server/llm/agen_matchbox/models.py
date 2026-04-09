"""
数据库模型模块
定义所有 SQLAlchemy ORM 模型
"""

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Float,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import (
    declarative_base,
    relationship,
)

Base = declarative_base()


DEFAULT_MAX_CONTEXT_TOKENS = 200_000
DEFAULT_MAX_OUTPUT_TOKENS = 64_000


class LLMPlatform(Base):
    """LLM 平台模型"""
    __tablename__ = "llm_platforms"
    id = Column(Integer, primary_key=True)
    name = Column(String(80), default="未命名平台", index=True)
    user_id = Column(String(255), nullable=True, index=True)
    base_url = Column(String(255), nullable=False)
    api_key = Column(String(512), nullable=True)
    is_sys = Column(Integer, default=0) 
    disable = Column(Integer, default=0)
    sort_order = Column(Integer, default=0)
    # 系统平台默认点数价格：每 1M token 消耗多少点，仅 sys_paid 生效。
    sys_credit_price_per_million_tokens = Column(Integer, nullable=True)
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
    disable = Column(Integer, default=0)
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
    temperature = Column(Float, nullable=True)
    # 模型上下文上限与单次输出上限，供业务侧在发起调用前进行长度校验。
    max_context_tokens = Column(
        Integer,
        nullable=False,
        default=DEFAULT_MAX_CONTEXT_TOKENS,
        server_default=text(str(DEFAULT_MAX_CONTEXT_TOKENS)),
    )
    max_output_tokens = Column(
        Integer,
        nullable=False,
        default=DEFAULT_MAX_OUTPUT_TOKENS,
        server_default=text(str(DEFAULT_MAX_OUTPUT_TOKENS)),
    )
    # 模型专属点数价格：为空时继承平台默认价格。
    sys_credit_price_per_million_tokens = Column(Integer, nullable=True)
    disable = Column(Integer, default=0, index=True)
    is_embedding = Column(Integer, default=0, index=True)
    sort_order = Column(Integer, default=0)


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


class UserQuotaPolicy(Base):
    """用户配额策略（字段均允许为空，便于渐进式迁移和按需启用）"""
    __tablename__ = "user_quota_policies"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_quota_policy"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), nullable=False, index=True)

    # sys_paid：系统平台 + 站长托管 key
    sys_paid_window_hours = Column(Integer, nullable=True)
    sys_paid_window_token_limit = Column(Integer, nullable=True)
    sys_paid_window_request_limit = Column(Integer, nullable=True)
    sys_paid_total_token_limit = Column(Integer, nullable=True)
    sys_paid_total_request_limit = Column(Integer, nullable=True)

    # self_paid：用户自己的 key（系统平台 override key + 自定义平台 key）
    self_paid_window_hours = Column(Integer, nullable=True)
    self_paid_window_token_limit = Column(Integer, nullable=True)
    self_paid_window_request_limit = Column(Integer, nullable=True)
    self_paid_total_token_limit = Column(Integer, nullable=True)
    self_paid_total_request_limit = Column(Integer, nullable=True)


class UserCreditAccount(Base):
    """用户系统点数账户。仅对系统托管调用生效。"""
    __tablename__ = "user_credit_accounts"
    __table_args__ = (
        UniqueConstraint("user_id", "billing_scope", name="uq_user_credit_account_user_scope"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), nullable=False, index=True)
    billing_scope = Column(String(32), nullable=False, default="sys_paid", index=True)
    credit_balance = Column(Integer, nullable=False, default=0)
    credit_total_granted = Column(Integer, nullable=False, default=0)
    credit_total_used = Column(Integer, nullable=False, default=0)
    status = Column(String(32), nullable=False, default="active", index=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class UserCreditLedger(Base):
    """用户点数流水。"""
    __tablename__ = "user_credit_ledger"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), nullable=False, index=True)
    billing_scope = Column(String(32), nullable=False, default="sys_paid", index=True)
    delta_credit = Column(Integer, nullable=False)
    balance_after = Column(Integer, nullable=False)
    reason_type = Column(String(32), nullable=False, index=True)
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
    usage_log_id = Column(
        Integer,
        ForeignKey("usage_log_entries.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    operator_user_id = Column(String(255), nullable=True, index=True)
    remark = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=func.now(), index=True)

    platform = relationship("LLMPlatform")
    model = relationship("LLModels")


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
    # 计费/限额范围：sys_paid=消耗站长托管额度；self_paid=消耗用户自己的 Key。
    # 允许为空，兼容历史日志与外部迁移工具的渐进式加列。
    quota_scope = Column(String(32), nullable=True, index=True)
    # 若本次调用为系统托管调用，可记录本次实际扣减点数；self_paid 为空。
    credit_cost = Column(Integer, nullable=True, index=True)
    
    # 时间戳
    created_at = Column(DateTime, default=func.now(), index=True)
    
    # 关系
    model = relationship("LLModels")
