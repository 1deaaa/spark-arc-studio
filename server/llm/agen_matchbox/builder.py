"""
LLM 客户端构建 Mixin
负责解析用户选择并构建 LLM 客户端实例

返回值说明
----------
get_user_llm() 和 get_spec_sys_llm() 均返回 LLMClient 对象：
    - llm：原生 LangChain 客户端，完全兼容 OpenAI 协议，已注入用量追踪 Callback
    - usage：轻量句柄，提供 get_usage_last_24h() 等用量查询方法
    - max_context_tokens / max_output_tokens：当前模型的上下文上限与单次输出上限

get_user_llm()：生产环境首选，自动解析用户绑定/默认模型。
get_spec_sys_llm()：轻量入口，按显示名称直接指定系统模型，适用于本地测试、调试脚本、无需用户系统的一次性调用。

关于 streaming 参数
-------------------
⚠️ 不要传入 streaming 参数。
流式/非流式由调用方式决定，不由构造参数控制：
  - 非流式：llm.invoke() / llm.ainvoke()
  - 流式：  llm.stream() / llm.astream() / llm.astream_events()
"""
from __future__ import annotations

from typing import Optional, Dict, Any
import json

from .models import (
    LLMPlatform,
    LLModels,
    UserModelUsage,
    AgentModelBinding,
    UserEmbeddingSelection,
    DEFAULT_MAX_CONTEXT_TOKENS,
    DEFAULT_MAX_OUTPUT_TOKENS,
    get_model_capabilities,
    is_chat_model,
    is_embedding_model,
    is_image_generation_model,
)
from .config import SYSTEM_USER_ID, DEFAULT_USAGE_KEY
from .image_adapters import (
    DEFAULT_IMAGE_GENERATION_ADAPTER,
    extract_legacy_image_generation_adapter,
    normalize_image_generation_adapter,
    strip_internal_image_generation_fields,
)


DIRECTOR_DEFAULT_USAGE_KEY = "reason"


def _load_chat_runtime():
    """延迟加载 LLM 运行时重依赖，避免阻塞服务启动。"""
    from .gateway import ChatUniversal
    from .tracked_model import UsageTrackingCallback, LLMUsage, LLMClient

    return ChatUniversal, UsageTrackingCallback, LLMUsage, LLMClient


class LLMBuilderMixin:
    """LLM 客户端构建功能"""

    @staticmethod
    def _agent_default_usage_key(agent_name: Optional[str]) -> Optional[str]:
        """返回没有显式绑定时的 Agent 默认用途。"""
        return DIRECTOR_DEFAULT_USAGE_KEY if agent_name == "agent_director" else None

    def _apply_sdk_request_compat(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """为 LangChain/OpenAI SDK 调用补充兼容参数。"""
        from .gateway import apply_sdk_request_compat

        return apply_sdk_request_compat(kwargs)

    @staticmethod
    def _resolve_model_limits(model_obj: Optional[LLModels]) -> Dict[str, int]:
        """读取模型上下文与输出上限，缺省时回退默认值。"""
        if model_obj is None:
            return {
                "max_context_tokens": DEFAULT_MAX_CONTEXT_TOKENS,
                "max_output_tokens": DEFAULT_MAX_OUTPUT_TOKENS,
            }
        return {
            "max_context_tokens": int(getattr(model_obj, "max_context_tokens", 0) or DEFAULT_MAX_CONTEXT_TOKENS),
            "max_output_tokens": int(getattr(model_obj, "max_output_tokens", 0) or DEFAULT_MAX_OUTPUT_TOKENS),
        }

    def _get_fallback_platform_model(self, session, user_id: str):
        """
        获取回退的平台和模型（失效时回退到第一个可用平台的第一个可用模型）。
        按 sort_order 排序，跳过 disable=1 的平台和模型。
        """
        if self._default_platform_id and self._default_model_id:
            plat = session.query(LLMPlatform).filter_by(id=self._default_platform_id).first()
            model = session.query(LLModels).filter_by(id=self._default_model_id).first()
            if plat and model and not self._is_platform_disabled(session, user_id, plat) and not self._is_model_disabled(model):
                return plat, model
        
        # 兜底：按 sort_order 查询第一个可用的系统平台和模型
        plats = (
            session.query(LLMPlatform)
            .filter_by(is_sys=1)
            .filter(LLMPlatform.disable == 0)
            .order_by(LLMPlatform.sort_order)
            .all()
        )
        for plat in plats:
            if self._is_platform_disabled(session, user_id, plat):
                continue
            # 按 sort_order 排序获取第一个可用模型
            sorted_models = sorted(plat.models, key=lambda m: m.sort_order)
            for m in sorted_models:
                if is_chat_model(m) and not self._is_model_disabled(m):
                    return plat, m
        
        raise RuntimeError("无法找到可用的默认平台和模型")

    def _resolve_user_choice(
        self,
        session,
        user_id: str,
        platform_id: Optional[int],
        model_id: Optional[int],
        usage_slot: Optional[UserModelUsage] = None,
        auto_fix: bool = True,
        raise_on_missing_key: bool = True,
        platform_obj: Optional[LLMPlatform] = None,
        model_obj: Optional[LLModels] = None,
    ) -> Dict[str, Any]:
        """
        核心解析器：解析用户选择的平台和模型。
        优化：支持传入已存在的对象以避免重复查询。
        """
        # 使用传入的对象，或根据 ID 查询
        plat = platform_obj
        if plat is None and platform_id:
            plat = session.query(LLMPlatform).filter_by(id=platform_id).first()
        
        model = model_obj
        if model is None and model_id:
            model = session.query(LLModels).filter_by(id=model_id).first()
        
        # 如果平台或模型无效，尝试自动修复
        if plat and self._is_platform_disabled(session, user_id, plat):
            plat = None
            model = None

        if not plat or not model:
            if auto_fix:
                plat, model = self._get_fallback_platform_model(session, user_id)
                # 更新用途槽位
                if usage_slot:
                    usage_slot.selected_platform_id = plat.id
                    usage_slot.selected_model_id = model.id
            else:
                raise ValueError("平台或模型配置无效")
        
        # 确保模型属于该平台
        if model.platform_id != plat.id:
            if auto_fix:
                # 尝试使用平台的第一个模型
                if plat.models:
                    model = next((m for m in plat.models if is_chat_model(m) and not self._is_model_disabled(m)), None)
                    if not model:
                        raise ValueError(f"平台 '{plat.name}' 没有可用的 LLM 模型")
                    if usage_slot:
                        usage_slot.selected_model_id = model.id
                else:
                    raise ValueError(f"平台 '{plat.name}' 没有可用模型")
            else:
                raise ValueError(f"模型 '{model.display_name}' 不属于平台 '{plat.name}'")

        # 防止非文本生成模型进入 LLM 解析
        if not is_chat_model(model):
            if auto_fix:
                fallback = next((m for m in plat.models if is_chat_model(m) and not self._is_model_disabled(m)), None)
                if not fallback:
                    raise ValueError(f"平台 '{plat.name}' 没有可用的 LLM 模型")
                model = fallback
                if usage_slot:
                    usage_slot.selected_model_id = model.id
            else:
                raise ValueError("该模型不可用于文本生成")

        if self._is_model_disabled(model):
            if auto_fix:
                fallback = next((m for m in plat.models if is_chat_model(m) and not self._is_model_disabled(m)), None)
                if not fallback:
                    raise ValueError(f"平台 '{plat.name}' 没有可用的 LLM 模型")
                model = fallback
                if usage_slot:
                    usage_slot.selected_model_id = model.id
            else:
                raise ValueError("模型已禁用")
        
        # 获取 API Key 与实际计费范围
        api_access = self._get_effective_api_access(session, user_id, plat)
        api_key = api_access.get("api_key")
        quota_scope = api_access.get("quota_scope")
        
        if raise_on_missing_key and not api_key:
            raise ValueError(
                f"平台 '{plat.name}' 的 API Key 未设置。请在 AI 设置中填写或配置服务器环境变量。"
            )
        
        return {
            "platform": plat,
            "model": model,
            "api_key": api_key,
            "base_url": plat.base_url,
            "quota_scope": quota_scope,
        }

    def get_user_llm(
        self,
        user_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        platform_id: Optional[int] = None,
        model_id: Optional[int] = None,
        usage_key: Optional[str] = None,
        **kwargs: Any,
    ) -> LLMClient:
        """
        获取并返回一个为指定用户准备的 LLM 客户端对象，以及对应的用量查询句柄。

                返回值：LLMClient(llm, usage)
                    - 默认当作 LLM 直接使用：client.invoke(...) / client.stream(...)
                    - 如需用量查询：client.usage.get_usage_last_24h()
                    - 如需读取模型上限：client.max_context_tokens / client.max_output_tokens

        ⚠️ 关于 streaming 参数：
        不要传入 streaming 参数，它会被静默忽略。
        流式/非流式由调用方式决定：
          - 非流式：llm.invoke() / llm.ainvoke()
          - 流式：  llm.stream() / llm.astream() / llm.astream_events()

        参数优先级：
        user_id：指定使用每位用户的模型。为空则尝试使用系统模型，如系统未开启提供服务则会报错。
        1. agent_name: 业务首选。从数据库查询该 Agent 的绑定配置。
        2. platform_id & model_id: 直接指定特定的平台和模型 ID。
        3. usage_key: 明确指定用途槽位（如 'main', 'fast'）。
        4. 默认值: 如果以上均未提供，使用 'main' 用途。

        用法示例:
            # 流式调用
            client = manager.get_user_llm(user_id, agent_name="agent_muse")
            for chunk in client.stream(messages):
                print(chunk.content)

            # 非流式调用
            client = manager.get_user_llm(user_id)
            result = client.invoke(messages)

            # 查询用量
            usage = client.usage.get_usage_last_24h()
            print(f"Last 24h: {usage['total_tokens']} tokens, {usage['requests']} requests")
        """
        ChatUniversal, UsageTrackingCallback, LLMUsage, LLMClient = _load_chat_runtime()
        effective_user_id = user_id if user_id is not None else SYSTEM_USER_ID
        
        direct_config = None
        normalized_usage = None

        with self.Session() as session:
            self.ensure_user_has_config(session, effective_user_id)

            # 1. 优先处理 agent_name 绑定逻辑
            if agent_name:
                binding = session.query(AgentModelBinding).filter_by(
                    user_id=effective_user_id, agent_name=agent_name
                ).first()
                if binding:
                    if binding.target_type == 'direct':
                        direct_config = {
                            'platform_id': binding.platform_id,
                            'model_id': binding.model_id
                        }
                    else:
                        normalized_usage = self._normalize_usage_key(binding.usage_key)

            # 2. 处理直接指定的 ID
            if not direct_config and not normalized_usage:
                if platform_id is not None and model_id is not None:
                    direct_config = {
                        'platform_id': platform_id,
                        'model_id': model_id
                    }

            # 3. 处理 usage_key (如果以上均未提供)
            if not direct_config and not normalized_usage:
                normalized_usage = self._normalize_usage_key(
                    usage_key if usage_key is not None else self._agent_default_usage_key(agent_name)
                )

            # 4. 解析最终的 platform_id 和 model_id
            usage_slot = None
            if direct_config:
                platform_id = direct_config.get('platform_id')
                model_id = direct_config.get('model_id')
                
                # 如果 direct 配置不完整，强制回退到 main 槽位以保证可用性
                if not platform_id or not model_id:
                    normalized_usage = DEFAULT_USAGE_KEY
                    usage_slot = self._get_usage_slot(session, effective_user_id, normalized_usage)
                    platform_id = usage_slot.selected_platform_id
                    model_id = usage_slot.selected_model_id
            else:
                usage_slot = self._get_usage_slot(session, effective_user_id, normalized_usage)
                if not usage_slot:
                    # 兜底：如果指定的用途不存在，回退到 main
                    normalized_usage = DEFAULT_USAGE_KEY
                    usage_slot = self._get_usage_slot(session, effective_user_id, normalized_usage)
                
                platform_id = usage_slot.selected_platform_id
                model_id = usage_slot.selected_model_id

            resolved = self._resolve_user_choice(
                session,
                effective_user_id,
                platform_id,
                model_id,
                usage_slot=usage_slot,
            )

            self.enforce_user_credit(
                session,
                effective_user_id,
                resolved["platform"].id,
                resolved["model"].id,
                resolved.get("quota_scope"),
            )
            
            session.commit()

            platform_obj = resolved["platform"]
            model_obj = resolved["model"]
            api_key = resolved["api_key"]
            base_url = resolved.get("base_url", platform_obj.base_url)
            quota_scope = resolved.get("quota_scope")
 
            if not api_key:
                raise ValueError(f"平台 '{platform_obj.name}' 的 API Key 未设置。请在 AI 设置中填写或配置服务器环境变量。")
 
            kwargs = self._apply_model_params(model_obj, kwargs)
            kwargs = self._apply_sdk_request_compat(kwargs)
 
            # ⚠️ streaming 参数由调用方式（invoke/stream）自动决定，不应手动传入。
            # 若调用方误传了 streaming 参数，此处静默忽略，避免透传到底层 SDK 引发歧义。
            kwargs.pop('streaming', None)
 
            # 构建用量追踪 Callback（精确到 user_id + model_id + 计费范围维度）
            tracking_cb = UsageTrackingCallback(
                user_id=effective_user_id,
                model_id=model_obj.id,
                platform_id=platform_obj.id,
                model_name=model_obj.model_name,
                platform_name=platform_obj.name,
                session_maker=self.Session,
                agent_name=agent_name,
                quota_scope=quota_scope,
                billing_enabled=self.billing_enabled,
            )
 
            # 构建 LLM 客户端（ChatUniversal 子类保留了第三方模型的 reasoning_content）
            llm = ChatUniversal(
                base_url=base_url,
                api_key=api_key,
                model_name=model_obj.model_name,
                callbacks=[tracking_cb],
                **kwargs,
            )
 
            # 构建用量查询句柄
            usage = LLMUsage(
                user_id=effective_user_id,
                model_id=model_obj.id,
                platform_id=platform_obj.id,
                model_name=model_obj.model_name,
                platform_name=platform_obj.name,
                session_maker=self.Session,
                agent_name=agent_name,
                quota_scope=quota_scope,
            )

            model_limits = self._resolve_model_limits(model_obj)

            return LLMClient(
                llm=llm,
                usage=usage,
                max_context_tokens=model_limits["max_context_tokens"],
                max_output_tokens=model_limits["max_output_tokens"],
            )

    def get_user_embedding(
        self,
        user_id: Optional[str] = None,
        platform_id: Optional[int] = None,
        model_id: Optional[int] = None,
        **kwargs: Any,
    ) -> OpenAIEmbeddings:
        """获取用户 Embedding 实例。优先使用用户选择，否则回退到首个可用 embedding。"""
        from langchain_openai import OpenAIEmbeddings

        effective_user_id = user_id if user_id is not None else SYSTEM_USER_ID

        with self.Session() as session:
            selection = None
            if platform_id is None or model_id is None:
                selection = session.query(UserEmbeddingSelection).filter_by(user_id=effective_user_id).first()
                if selection:
                    platform_id = selection.platform_id
                    model_id = selection.model_id

            plat = session.query(LLMPlatform).filter_by(id=platform_id).first() if platform_id else None
            model = session.query(LLModels).filter_by(id=model_id).first() if model_id else None

            if not plat or not model or not is_embedding_model(model):
                # 回退：找第一个可用的 embedding
                plat = None
                model = None
                platforms = session.query(LLMPlatform).all()
                for p in platforms:
                    for m in p.models:
                        if is_embedding_model(m) and not self._is_model_disabled(m):
                            api_key = self._get_effective_api_key(session, effective_user_id, p)
                            if api_key:
                                plat = p
                                model = m
                                break
                    if plat and model:
                        break

            if not plat or not model:
                raise ValueError("未找到可用的 Embedding 模型或未配置 API Key")

            api_key = self._get_effective_api_key(session, effective_user_id, plat)
            if not api_key:
                raise ValueError(f"平台 '{plat.name}' 的 API Key 未设置。")

            kwargs = self._apply_model_params(model, kwargs)
            kwargs = self._apply_sdk_request_compat(kwargs)
            # Embedding 接口不支持 stream_usage，避免 OpenAI SDK 报错
            kwargs.pop("stream_usage", None)

            return OpenAIEmbeddings(
                model=model.model_name,
                api_key=api_key,
                base_url=plat.base_url,
                check_embedding_ctx_length=False,
                **kwargs,
            )

    def list_user_image_generation_models(self, user_id: Optional[str] = None) -> list[dict[str, Any]]:
        """列出当前用户可见的生图模型。"""
        effective_user_id = str(user_id if user_id is not None else SYSTEM_USER_ID)
        rows: list[dict[str, Any]] = []

        with self.Session() as session:
            platforms = (
                session.query(LLMPlatform)
                .all()
            )
            for platform in sorted(platforms, key=lambda item: int(getattr(item, "sort_order", 0) or 0)):
                if self._is_platform_disabled(session, effective_user_id, platform):
                    continue
                if not platform.is_sys and str(platform.user_id) != effective_user_id:
                    continue

                api_access = self._get_effective_api_access(session, effective_user_id, platform)
                models = sorted(platform.models, key=lambda item: int(getattr(item, "sort_order", 0) or 0))
                for model in models:
                    if self._is_model_disabled(model) or not is_image_generation_model(model):
                        continue
                    rows.append({
                        "platform_id": platform.id,
                        "platform_name": platform.name,
                        "platform_is_sys": bool(platform.is_sys),
                        "base_url": platform.base_url,
                        "api_key_set": bool(api_access.get("api_key")),
                        "model_id": model.id,
                        "model_name": model.model_name,
                        "display_name": model.display_name or model.model_name,
                        "capabilities": get_model_capabilities(model),
                        "image_generation_adapter": (
                            normalize_image_generation_adapter(getattr(model, "image_generation_adapter", None))
                            or DEFAULT_IMAGE_GENERATION_ADAPTER
                        ),
                    })
        return rows

    def resolve_user_image_generation_model(
        self,
        user_id: Optional[str] = None,
        platform_id: Optional[int] = None,
        model_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """解析当前用户可用的生图模型与凭据，供图片适配层调用。"""
        effective_user_id = str(user_id if user_id is not None else SYSTEM_USER_ID)

        with self.Session() as session:
            platform = session.query(LLMPlatform).filter_by(id=platform_id).first() if platform_id else None
            model = session.query(LLModels).filter_by(id=model_id).first() if model_id else None

            if platform is not None and self._is_platform_disabled(session, effective_user_id, platform):
                raise ValueError("平台已禁用")
            if platform is not None and not platform.is_sys and str(platform.user_id) != effective_user_id:
                raise ValueError("无权访问该平台")
            if model is not None and self._is_model_disabled(model):
                raise ValueError("模型已禁用")
            if platform is not None and model is not None and model.platform_id != platform.id:
                raise ValueError("模型不属于该平台")
            if model is not None and not is_image_generation_model(model):
                raise ValueError("目标模型不具备生图能力")

            if platform is None or model is None:
                platform = None
                model = None
                platforms = (
                    session.query(LLMPlatform)
                    .all()
                )
                for candidate_platform in sorted(platforms, key=lambda item: int(getattr(item, "sort_order", 0) or 0)):
                    if self._is_platform_disabled(session, effective_user_id, candidate_platform):
                        continue
                    if not candidate_platform.is_sys and str(candidate_platform.user_id) != effective_user_id:
                        continue
                    api_access = self._get_effective_api_access(session, effective_user_id, candidate_platform)
                    if not api_access.get("api_key"):
                        continue
                    for candidate_model in sorted(candidate_platform.models, key=lambda item: int(getattr(item, "sort_order", 0) or 0)):
                        if self._is_model_disabled(candidate_model):
                            continue
                        if is_image_generation_model(candidate_model):
                            platform = candidate_platform
                            model = candidate_model
                            break
                    if platform is not None and model is not None:
                        break

            if platform is None or model is None:
                raise ValueError("未找到可用的生图模型，请先在模型设置中添加具备生图能力的模型")

            api_access = self._get_effective_api_access(session, effective_user_id, platform)
            api_key = api_access.get("api_key")
            quota_scope = api_access.get("quota_scope")
            if not api_key:
                raise ValueError(f"平台 '{platform.name}' 的 API Key 未设置")

            self.enforce_user_credit(
                session,
                effective_user_id,
                platform.id,
                model.id,
                quota_scope,
            )

            extra_body: dict[str, Any] = {}
            legacy_image_adapter = None
            if model.extra_body:
                try:
                    parsed_extra = json.loads(model.extra_body)
                    if isinstance(parsed_extra, dict):
                        legacy_image_adapter = extract_legacy_image_generation_adapter(parsed_extra)
                        extra_body = strip_internal_image_generation_fields(parsed_extra) or {}
                except json.JSONDecodeError:
                    extra_body = {}
            image_generation_adapter = (
                normalize_image_generation_adapter(getattr(model, "image_generation_adapter", None))
                or legacy_image_adapter
                or DEFAULT_IMAGE_GENERATION_ADAPTER
            )

            return {
                "user_id": effective_user_id,
                "platform_id": platform.id,
                "platform_name": platform.name,
                "base_url": platform.base_url,
                "model_id": model.id,
                "model_name": model.model_name,
                "display_name": model.display_name or model.model_name,
                "api_key": api_key,
                "quota_scope": quota_scope,
                "capabilities": get_model_capabilities(model),
                "image_generation_adapter": image_generation_adapter,
                "extra_body": extra_body,
            }

    def get_spec_sys_llm(
        self,
        platform_name: str,
        model_display_name: str,
        user_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        **kwargs: Any
    ) -> LLMClient:
        """
        按显示名称直接获取指定系统模型的轻量入口，适用于：
        - 本地快速测试、调试脚本
        - 不需要用户系统的一次性调用
        - 明确知道目标平台/模型显示名的场景

        ⚠️ 此方法通过显示名称定位平台与模型，调用期间对应显示名不可修改。
        生产环境或需要动态模型选择时，请优先使用 get_user_llm()。

        注意：支持传入 user_id 以便使用用户自定义的 API Key 覆盖。

        关于 streaming 参数：
        不要传入 streaming 参数，流式/非流式由调用方式决定：
          - 非流式：llm.invoke() / llm.ainvoke()
          - 流式：  llm.stream() / llm.astream()
        """
        ChatUniversal, UsageTrackingCallback, LLMUsage, LLMClient = _load_chat_runtime()
        effective_user_id = user_id if user_id is not None else SYSTEM_USER_ID

        with self.Session() as session:
            plat = session.query(LLMPlatform).filter_by(name=platform_name, is_sys=1).first()
            if not plat:
                raise ValueError(f"系统平台 '{platform_name}' 不存在")

            model = session.query(LLModels).filter_by(
                platform_id=plat.id, display_name=model_display_name
            ).first()
            if not model:
                raise ValueError(f"模型 '{model_display_name}' 在平台 '{platform_name}' 中不存在")

            api_access = self._get_effective_api_access(session, effective_user_id, plat)
            api_key = api_access.get("api_key")
            quota_scope = api_access.get("quota_scope")
            if not api_key:
                raise ValueError(f"平台 '{platform_name}' 的 API Key 未设置")

            self.enforce_user_credit(
                session,
                effective_user_id,
                plat.id,
                model.id,
                quota_scope,
            )

            kwargs = self._apply_model_params(model, kwargs)
            kwargs = self._apply_sdk_request_compat(kwargs)
 
            # ⚠️ streaming 参数由调用方式（invoke/stream）自动决定，不应手动传入。
            # 若调用方误传了 streaming 参数，此处静默忽略，避免透传到底层 SDK 引发歧义。
            kwargs.pop('streaming', None)
 
            # 构建用量追踪 Callback
            tracking_cb = UsageTrackingCallback(
                user_id=effective_user_id,
                model_id=model.id,
                platform_id=plat.id,
                model_name=model.model_name,
                platform_name=plat.name,
                session_maker=self.Session,
                agent_name=agent_name,
                quota_scope=quota_scope,
                billing_enabled=self.billing_enabled,
            )
 
            llm = ChatUniversal(
                base_url=plat.base_url,
                api_key=api_key,
                model_name=model.model_name,
                callbacks=[tracking_cb],
                **kwargs,
            )
 
            usage = LLMUsage(
                user_id=effective_user_id,
                model_id=model.id,
                platform_id=plat.id,
                model_name=model.model_name,
                platform_name=plat.name,
                session_maker=self.Session,
                agent_name=agent_name,
                quota_scope=quota_scope,
            )

            model_limits = self._resolve_model_limits(model)

            return LLMClient(
                llm=llm,
                usage=usage,
                max_context_tokens=model_limits["max_context_tokens"],
                max_output_tokens=model_limits["max_output_tokens"],
            )
