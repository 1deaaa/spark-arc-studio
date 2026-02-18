"""
LLM 客户端构建 Mixin
负责解析用户选择并构建 LLM 客户端实例

返回的 LLM 对象是 TrackedChatModel，自动追踪用量。
"""

from typing import Optional, Dict, Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from .models import LLMPlatform, LLModels, UserModelUsage, AgentModelBinding, UserEmbeddingSelection
from .config import SYSTEM_USER_ID, DEFAULT_USAGE_KEY
from .tracked_model import TrackedChatModel


class LLMBuilderMixin:
    """LLM 客户端构建功能"""

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
                if not m.is_embedding and not self._is_model_disabled(m):
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
                    model = next((m for m in plat.models if not m.is_embedding and not self._is_model_disabled(m)), None)
                    if not model:
                        raise ValueError(f"平台 '{plat.name}' 没有可用的 LLM 模型")
                    if usage_slot:
                        usage_slot.selected_model_id = model.id
                else:
                    raise ValueError(f"平台 '{plat.name}' 没有可用模型")
            else:
                raise ValueError(f"模型 '{model.display_name}' 不属于平台 '{plat.name}'")

        # 防止 embedding 模型进入 LLM 解析
        if model.is_embedding:
            if auto_fix:
                fallback = next((m for m in plat.models if not m.is_embedding and not self._is_model_disabled(m)), None)
                if not fallback:
                    raise ValueError(f"平台 '{plat.name}' 没有可用的 LLM 模型")
                model = fallback
                if usage_slot:
                    usage_slot.selected_model_id = model.id
            else:
                raise ValueError("Embedding 模型不可用于 LLM")

        if self._is_model_disabled(model):
            if auto_fix:
                fallback = next((m for m in plat.models if not m.is_embedding and not self._is_model_disabled(m)), None)
                if not fallback:
                    raise ValueError(f"平台 '{plat.name}' 没有可用的 LLM 模型")
                model = fallback
                if usage_slot:
                    usage_slot.selected_model_id = model.id
            else:
                raise ValueError("模型已禁用")
        
        # 获取 API Key
        api_key = self._get_effective_api_key(session, user_id, plat)
        
        if raise_on_missing_key and not api_key:
            raise ValueError(
                f"平台 '{plat.name}' 的 API Key 未设置。请在 AI 设置中填写或配置服务器环境变量。"
            )
        
        return {
            "platform": plat,
            "model": model,
            "api_key": api_key,
            "base_url": plat.base_url,
        }

    def get_user_llm(
        self,
        user_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        platform_id: Optional[int] = None,
        model_id: Optional[int] = None,
        usage_key: Optional[str] = None,
        **kwargs: Any,
    ) -> TrackedChatModel:
        """
        获取并返回一个为指定用户准备的 LLM 客户端实例。支持跟踪用量。
        - 为兼容 LangChain 1.0，构建底层 ChatOpenAI 时不会透传 streaming 参数。
        - 非流式请使用 llm.invoke()/llm.ainvoke()。
        - 流式请使用 llm.stream()。
        流式调用请使用:
            for chunk in llm.stream(messages):
                print(chunk.content)
        参数优先级：
        1. agent_name: 业务首选。从数据库查询该 Agent 的绑定配置。
        2. platform_id & model_id: 直接指定特定的平台和模型 ID。
        3. usage_key: 明确指定用途槽位（如 'main', 'fast'）。
        4. 默认值: 如果以上均未提供，使用 'main' 用途。
        用法示例:
            # 流式调用 (默认)
            llm = manager.get_user_llm(user_id, agent_name="agent_muse")
            for chunk in llm.stream(messages):
                print(chunk.content)
            
            # 非流式调用 (invoke，自动使用非流式)
            llm = manager.get_user_llm(user_id)
            result = llm.invoke(messages)
            
            # 查询用量
            usage = llm.get_usage_last_24h()
            print(f"过去24小时: {usage['tokens']} tokens")
        """
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
                normalized_usage = self._normalize_usage_key(usage_key)

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
            
            session.commit()

            platform_obj = resolved["platform"]
            model_obj = resolved["model"]
            api_key = resolved["api_key"]
            base_url = resolved.get("base_url", platform_obj.base_url)

            if not api_key:
                raise ValueError(f"平台 '{platform_obj.name}' 的 API Key 未设置。请在 AI 设置中填写或配置服务器环境变量。")

            kwargs = self._apply_model_params(model_obj, kwargs)

            # LangChain 1.0 兼容：避免将 streaming 参数透传到底层 OpenAI SDK。
            # 流式输出统一通过 llm.stream(...) 路径触发。
            kwargs.pop('streaming', None)
            
            # 构建内部 ChatOpenAI
            inner_llm = ChatOpenAI(
                base_url=base_url,
                api_key=api_key,
                model_name=model_obj.model_name,
                **kwargs,
            )
            
            # 包装为 TrackedChatModel
            return TrackedChatModel(
                inner_llm=inner_llm,
                user_id=effective_user_id,
                model_id=model_obj.id,
                platform_id=platform_obj.id,
                model_name=model_obj.model_name,
                platform_name=platform_obj.name,
                session_maker=self.Session,
                agent_name=agent_name,
            )

    def get_user_embedding(
        self,
        user_id: Optional[str] = None,
        platform_id: Optional[int] = None,
        model_id: Optional[int] = None,
        **kwargs: Any,
    ) -> OpenAIEmbeddings:
        """获取用户 Embedding 实例。优先使用用户选择，否则回退到首个可用 embedding。"""
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

            if not plat or not model or not model.is_embedding:
                # 回退：找第一个可用的 embedding
                plat = None
                model = None
                platforms = session.query(LLMPlatform).all()
                for p in platforms:
                    for m in p.models:
                        if m.is_embedding and not self._is_model_disabled(m):
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

            return OpenAIEmbeddings(
                model=model.model_name,
                api_key=api_key,
                base_url=plat.base_url,
                check_embedding_ctx_length=False,
                **kwargs,
            )

    def get_spec_sys_llm(
        self,
        platform_name: str,
        model_display_name: str,
        user_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        **kwargs: Any
    ) -> TrackedChatModel:
        """
        获取特定的系统预设模型。此方法为方便输入，依赖平台名称和模型显示名称定位模型。
        ⚠️ 警告：此方法会随着模型名更改而更改，所以当决定使用这个方法的时候禁止修改对应平台的显示名，否则会找不到模型而报错。
        注意：现在支持传入 user_id 以便使用用户自定义的 API Key 覆盖。
        调用说明：构建底层 ChatOpenAI 时不会透传 streaming；流式请调用 llm.stream()。
        """
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
            
            api_key = self._get_effective_api_key(session, effective_user_id, plat)
            if not api_key:
                raise ValueError(f"平台 '{platform_name}' 的 API Key 未设置")
            
            kwargs = self._apply_model_params(model, kwargs)

            # LangChain 1.0 兼容：避免将 streaming 参数透传到底层 OpenAI SDK。
            kwargs.pop('streaming', None)
            
            inner_llm = ChatOpenAI(
                base_url=plat.base_url,
                api_key=api_key,
                model_name=model.model_name,
                **kwargs,
            )
            
            return TrackedChatModel(
                inner_llm=inner_llm,
                user_id=effective_user_id,
                model_id=model.id,
                platform_id=plat.id,
                model_name=model.model_name,
                platform_name=plat.name,
                session_maker=self.Session,
                agent_name=agent_name,
            )
