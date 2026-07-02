"""
数据库模型模块
定义所有 SQLAlchemy ORM 模型
"""

import json
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Index,
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


DEFAULT_MAX_CONTEXT_TOKENS = 256_000
DEFAULT_MAX_OUTPUT_TOKENS = 64_000

CAP_TEXT_GENERATION = "text_generation"
CAP_VISION_INPUT = "vision_input"
CAP_EMBEDDING = "embedding"
CAP_IMAGE_GENERATION = "image_generation"
CAP_IMAGE_REFERENCE_INPUT = "image_reference_input"
CAP_IMAGE_EDIT = "image_edit"

MODEL_CAPABILITY_ORDER = (
    CAP_TEXT_GENERATION,
    CAP_VISION_INPUT,
    CAP_EMBEDDING,
    CAP_IMAGE_GENERATION,
    CAP_IMAGE_REFERENCE_INPUT,
    CAP_IMAGE_EDIT,
)
MODEL_CAPABILITIES = set(MODEL_CAPABILITY_ORDER)
DEFAULT_MODEL_CAPABILITIES = (CAP_TEXT_GENERATION,)
EMBEDDING_MODEL_CAPABILITIES = (CAP_EMBEDDING,)

_CAPABILITY_ALIASES = {
    "text": CAP_TEXT_GENERATION,
    "chat": CAP_TEXT_GENERATION,
    "llm": CAP_TEXT_GENERATION,
    "vision": CAP_VISION_INPUT,
    "vision_text": CAP_VISION_INPUT,
    "multimodal": CAP_VISION_INPUT,
    "embedding": CAP_EMBEDDING,
    "embeddings": CAP_EMBEDDING,
    "image": CAP_IMAGE_GENERATION,
    "image_generation": CAP_IMAGE_GENERATION,
    "text_to_image": CAP_IMAGE_GENERATION,
    "image_reference": CAP_IMAGE_REFERENCE_INPUT,
    "image_reference_input": CAP_IMAGE_REFERENCE_INPUT,
    "image_edit": CAP_IMAGE_EDIT,
    "image_editing": CAP_IMAGE_EDIT,
}


def _capability_tokens(raw_capabilities):
    """把数据库、YAML、API 入参中的能力值拆成候选 token。"""
    if raw_capabilities is None:
        return []
    if isinstance(raw_capabilities, (list, tuple, set)):
        return list(raw_capabilities)
    if isinstance(raw_capabilities, dict):
        raw_capabilities = raw_capabilities.get("capabilities", [])
        return _capability_tokens(raw_capabilities)
    if isinstance(raw_capabilities, str):
        value = raw_capabilities.strip()
        if not value:
            return []
        if value[0] in "[{":
            try:
                return _capability_tokens(json.loads(value))
            except Exception:
                pass
        return [part for part in value.replace(";", ",").replace("|", ",").split(",") if part.strip()]
    return [raw_capabilities]


def normalize_model_capabilities(raw_capabilities=None, *, legacy_is_embedding=None):
    """规范化模型能力集合，作为模型类型的唯一业务真相源。"""
    capabilities = set()
    for token in _capability_tokens(raw_capabilities):
        key = str(token).strip().lower()
        if not key:
            continue
        capability = _CAPABILITY_ALIASES.get(key, key)
        if capability in MODEL_CAPABILITIES:
            capabilities.add(capability)

    if not capabilities:
        if legacy_is_embedding:
            capabilities.add(CAP_EMBEDDING)
        else:
            capabilities.update(DEFAULT_MODEL_CAPABILITIES)

    if CAP_EMBEDDING in capabilities:
        capabilities = {CAP_EMBEDDING}

    if CAP_VISION_INPUT in capabilities:
        capabilities.add(CAP_TEXT_GENERATION)

    if CAP_IMAGE_REFERENCE_INPUT in capabilities or CAP_IMAGE_EDIT in capabilities:
        capabilities.add(CAP_IMAGE_GENERATION)

    if CAP_IMAGE_EDIT in capabilities:
        capabilities.add(CAP_IMAGE_REFERENCE_INPUT)

    return [cap for cap in MODEL_CAPABILITY_ORDER if cap in capabilities]


def serialize_model_capabilities(raw_capabilities=None, *, legacy_is_embedding=None):
    """序列化能力集合，供数据库与 YAML 写入使用。"""
    return json.dumps(
        normalize_model_capabilities(raw_capabilities, legacy_is_embedding=legacy_is_embedding),
        ensure_ascii=False,
    )


def get_model_capabilities(model):
    """读取模型能力集合；历史 is_embedding 只作为旧数据回退。"""
    return normalize_model_capabilities(
        getattr(model, "capabilities", None),
        legacy_is_embedding=bool(getattr(model, "is_embedding", 0)),
    )


def set_model_capabilities(model, raw_capabilities=None, *, legacy_is_embedding=None):
    """写入模型能力集合，并同步旧列以便本地旧库平滑迁移。"""
    capabilities = normalize_model_capabilities(raw_capabilities, legacy_is_embedding=legacy_is_embedding)
    model.capabilities = json.dumps(capabilities, ensure_ascii=False)
    if hasattr(model, "is_embedding"):
        model.is_embedding = 1 if CAP_EMBEDDING in capabilities else 0
    return capabilities


def model_has_capability(model, capability: str) -> bool:
    return capability in get_model_capabilities(model)


def is_chat_model(model) -> bool:
    return model_has_capability(model, CAP_TEXT_GENERATION)


def is_embedding_model(model) -> bool:
    return model_has_capability(model, CAP_EMBEDDING)


def is_image_generation_model(model) -> bool:
    return model_has_capability(model, CAP_IMAGE_GENERATION)


class LLMPlatform(Base):
    """LLM 平台模型"""
    __tablename__ = "llm_platforms"
    id = Column(Integer, primary_key=True)
    name = Column(String(80), default="未命名平台", index=True)
    user_id = Column(String(255), nullable=True, index=True)
    base_url = Column(String(255), nullable=False)
    # 平台充值入口；为空时前端不显示低频充值按钮。
    recharge_url = Column(String(512), nullable=True)
    api_key = Column(String(512), nullable=True)
    is_sys = Column(Integer, default=0) 
    disable = Column(Integer, default=0)
    sort_order = Column(Integer, default=0)
    # 系统平台火柴预算；NULL 表示无限，0 表示额度耗尽。
    sys_credit_balance = Column(Float, nullable=True)
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
    image_generation_adapter = Column(String(64), nullable=True)
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
    # 模型专属点数价格：输入/输出分别定价，每 1M token 消耗多少点。0 表示免费。
    sys_credit_input_price_per_million = Column(Float, nullable=True)
    # 模型专属缓存命中输入点数价格：每 1M 命中缓存的输入 token 消耗多少点。
    sys_credit_cached_input_price_per_million = Column(Float, nullable=True)
    sys_credit_output_price_per_million = Column(Float, nullable=True)
    disable = Column(Integer, default=0, index=True)
    capabilities = Column(String(512), nullable=True)
    # 旧数据迁移辅助列。业务判断必须使用 capabilities 及上方 helper。
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
    credit_balance = Column(Float, nullable=False, default=0)
    credit_total_granted = Column(Float, nullable=False, default=0)
    credit_total_used = Column(Float, nullable=False, default=0)
    status = Column(String(32), nullable=False, default="active", index=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class UserCreditLedger(Base):
    """用户点数流水。"""
    __tablename__ = "user_credit_ledger"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), nullable=False, index=True)
    billing_scope = Column(String(32), nullable=False, default="sys_paid", index=True)
    delta_credit = Column(Float, nullable=False)
    balance_after = Column(Float, nullable=False)
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
    __table_args__ = (
        Index("idx_usage_user_context", "user_id", "context_key"),
        Index("idx_usage_user_created", "user_id", "created_at"),
        Index("idx_usage_user_model_created", "user_id", "model_id", "created_at"),
        Index("idx_usage_user_scope_created", "user_id", "quota_scope", "created_at"),
    )

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
    # 输入侧命中的提示词缓存 token 数。0 表示未命中或上游未返回该统计。
    cached_prompt_tokens = Column(Integer, default=0)
    # 输入侧未命中的提示词缓存 token 数；仅在上游提供真实缓存统计时记录。
    cache_miss_prompt_tokens = Column(Integer, nullable=True)
    # token 用量来源：upstream / mixed / estimated。
    usage_source = Column(String(32), nullable=True)
    # 缓存统计来源；当前仅记录 upstream，缺失时保持 NULL。
    cache_source = Column(String(32), nullable=True)
    
    # 调用状态 (1=成功, 0=失败)
    success = Column(Integer, default=1)
    
    # 上下文信息（便于审计和调试）
    agent_name = Column(String(120), nullable=True, index=True)
    context_key = Column(String(255), nullable=True)
    # 计费/限额范围：sys_paid=消耗站长托管额度；self_paid=消耗用户自己的 Key。
    # 允许为空，兼容历史日志与外部迁移工具的渐进式加列。
    quota_scope = Column(String(32), nullable=True, index=True)
    # 若本次调用为系统托管调用，可记录本次实际扣减点数；self_paid 为空。
    credit_cost = Column(Float, nullable=True, index=True)
    
    # 时间戳
    created_at = Column(DateTime, default=func.now(), index=True)
    
    # 关系
    model = relationship("LLModels")


# ==================== 兑换码系统 ====================

class RedeemCode(Base):
    """兑换码"""
    __tablename__ = "redeem_codes"

    id = Column(Integer, primary_key=True)
    # 兑换码字符串，唯一
    code = Column(String(64), nullable=False, unique=True, index=True)
    # 可兑换的点数额度
    credit_amount = Column(Float, nullable=False)
    # 兑换码类型：single = 一次性（用完即废）；per_user = 每用户可用一次（全服福利）
    code_type = Column(String(32), nullable=False, default="single", index=True)
    # 状态：active / revoked / exhausted
    status = Column(String(32), nullable=False, default="active", index=True)
    # 创建者（管理员 user_id）
    created_by = Column(String(255), nullable=True, index=True)
    # 备注
    remark = Column(String(255), nullable=True)
    # 时间戳
    created_at = Column(DateTime, default=func.now(), index=True)
    revoked_at = Column(DateTime, nullable=True)

    # 关系
    usages = relationship("RedeemCodeUsage", backref="redeem_code", cascade="all, delete-orphan")


class RedeemCodeUsage(Base):
    """兑换码使用记录"""
    __tablename__ = "redeem_code_usages"

    id = Column(Integer, primary_key=True)
    # 关联兑换码
    redeem_code_id = Column(
        Integer,
        ForeignKey("redeem_codes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 使用者 user_id
    user_id = Column(String(255), nullable=False, index=True)
    # 兑换时的点数变动
    delta_credit = Column(Float, nullable=False)
    # 兑换后余额快照
    balance_after = Column(Float, nullable=False)
    # 时间戳
    used_at = Column(DateTime, default=func.now(), index=True)
