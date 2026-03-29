"""
用户服务 Mixin
提供用户模型配置和 Agent 绑定管理
"""

from typing import Optional, Dict, Any, List

from sqlalchemy.orm import selectinload

from .models import LLMPlatform, LLModels, UserModelUsage, AgentModelBinding, UserEmbeddingSelection
from .config import DEFAULT_USAGE_KEY, BUILTIN_USAGE_SLOTS


class UserServicesMixin:
    """用户服务配置功能"""

    # ==================== 用途槽位管理 ====================

    def _build_usage_payload(self, resolved: Dict[str, Any], slot: UserModelUsage) -> Dict[str, Any]:
        platform_obj = resolved["platform"]
        model_obj = resolved["model"]
        api_key = resolved.get("api_key")
        base_url = resolved.get("base_url", platform_obj.base_url)

        return {
            "usage_key": slot.usage_key,
            "usage_label": slot.usage_label,
            "platform": platform_obj.name,
            "platform_id": platform_obj.id,
            "platform_is_sys": bool(platform_obj.is_sys),
            "base_url": base_url,
            "model_display_name": model_obj.display_name,
            "model_id": model_obj.id,
            "model_name": model_obj.model_name,
            "api_key_set": bool(api_key),
            "needs_rebind": False,
        }

    def _build_invalid_usage_payload(self, slot: UserModelUsage, error_message: str) -> Dict[str, Any]:
        return {
            "usage_key": slot.usage_key,
            "usage_label": slot.usage_label,
            "platform": "⚠ 平台已失效，请重新选择",
            "platform_id": slot.selected_platform_id if slot.selected_platform_id is not None else -1,
            "platform_is_sys": False,
            "base_url": "",
            "model_display_name": "⚠ 模型已失效，请重新选择",
            "model_id": slot.selected_model_id if slot.selected_model_id is not None else -1,
            "model_name": "",
            "api_key_set": False,
            "missing_key": True,
            "needs_rebind": True,
            "error": error_message,
        }

    def _collect_usage_payloads(self, session, user_id: str) -> List[Dict[str, Any]]:
        # 优化：预加载 platform 和 model，避免 N+1 查询
        slots = (
            session.query(UserModelUsage)
            .options(
                selectinload(UserModelUsage.platform),
                selectinload(UserModelUsage.model)
            )
            .filter_by(user_id=user_id)
            .order_by(UserModelUsage.id.asc())
            .all()
        )
        details: List[Dict[str, Any]] = []
        has_auto_fixed = False
        for slot in slots:
            old_platform_id = slot.selected_platform_id
            old_model_id = slot.selected_model_id
            try:
                # 优化：传入已加载的对象
                resolved = self._resolve_user_choice(
                    session,
                    user_id,
                    slot.selected_platform_id,
                    slot.selected_model_id,
                    usage_slot=slot,
                    auto_fix=True,
                    raise_on_missing_key=False,
                    platform_obj=slot.platform,
                    model_obj=slot.model
                )
                if slot.selected_platform_id != old_platform_id or slot.selected_model_id != old_model_id:
                    has_auto_fixed = True
                payload = self._build_usage_payload(resolved, slot)
                if not resolved.get("api_key"):
                    payload["missing_key"] = True
                    payload["error"] = "API Key 未配置"
                details.append(payload)
            except ValueError as e:
                details.append(self._build_invalid_usage_payload(slot, str(e)))
        if has_auto_fixed:
            session.commit()
        return details

    def save_user_selection(
        self,
        user_id: str,
        platform_id: int,
        model_id: int,
        usage_key: Optional[str] = None,
    ):
        """保存用户的模型选择"""
        normalized_usage = self._normalize_usage_key(usage_key)
        user_id = str(user_id)

        with self.Session() as session:
            self.ensure_user_has_config(session, user_id)
            plat = session.query(LLMPlatform).filter_by(id=platform_id).first()
            if not plat:
                raise ValueError("平台不存在")
            if self._is_platform_disabled(session, user_id, plat):
                raise ValueError("平台已禁用")
            slot = self._get_usage_slot(session, user_id, normalized_usage)
            if not slot:
                raise ValueError(f"用途 '{normalized_usage}' 不存在")

            slot.selected_platform_id = platform_id
            slot.selected_model_id = model_id
            session.commit()
            return True

    def create_user_usage_slot(
        self,
        user_id: str,
        usage_key: str,
        usage_label: Optional[str] = None,
        platform_id: Optional[int] = None,
        model_id: Optional[int] = None,
    ):
        """创建新的用途槽位"""
        user_id = str(user_id)
        usage_key = usage_key.strip().lower()
        
        if not usage_key:
            raise ValueError("usage_key 不能为空")
        
        # 检查是否为内置槽位
        builtin_keys = {slot["key"] for slot in BUILTIN_USAGE_SLOTS}
        if usage_key in builtin_keys:
            raise ValueError(f"'{usage_key}' 是内置用途，无法重复创建")
        
        with self.Session() as session:
            self.ensure_user_has_config(session, user_id)
            
            existing = self._get_usage_slot(session, user_id, usage_key)
            if existing:
                raise ValueError(f"用途 '{usage_key}' 已存在")
            
            # 如果未指定，使用默认平台和模型
            if platform_id is None:
                platform_id = self._default_platform_id
            if model_id is None:
                model_id = self._default_model_id
            
            slot = UserModelUsage(
                user_id=user_id,
                usage_key=usage_key,
                usage_label=usage_label or usage_key,
                selected_platform_id=platform_id,
                selected_model_id=model_id,
            )
            session.add(slot)
            session.commit()
            
            return {
                "usage_key": slot.usage_key,
                "usage_label": slot.usage_label,
                "platform_id": slot.selected_platform_id,
                "model_id": slot.selected_model_id,
            }

    def rename_user_usage_slot(self, user_id: str, usage_key: str, new_usage_key: Optional[str] = None, new_label: Optional[str] = None):
        """重命名用途槽位"""
        user_id = str(user_id)
        usage_key = usage_key.strip().lower()
        
        builtin_keys = {slot["key"] for slot in BUILTIN_USAGE_SLOTS}
        if usage_key in builtin_keys:
            raise ValueError(f"'{usage_key}' 是内置用途，无法修改")
        
        with self.Session() as session:
            slot = self._get_usage_slot(session, user_id, usage_key)
            if not slot:
                raise ValueError(f"用途 '{usage_key}' 不存在")
            
            if new_usage_key:
                new_usage_key = new_usage_key.strip().lower()
                if new_usage_key in builtin_keys:
                    raise ValueError(f"'{new_usage_key}' 是内置用途名称")
                if new_usage_key != usage_key:
                    existing = self._get_usage_slot(session, user_id, new_usage_key)
                    if existing:
                        raise ValueError(f"用途 '{new_usage_key}' 已存在")
                    slot.usage_key = new_usage_key
            
            if new_label:
                slot.usage_label = new_label
            
            session.commit()
            return True

    def delete_user_usage_slot(self, user_id: str, usage_key: str):
        """删除用途槽位"""
        user_id = str(user_id)
        usage_key = usage_key.strip().lower()
        
        builtin_keys = {slot["key"] for slot in BUILTIN_USAGE_SLOTS}
        if usage_key in builtin_keys:
            raise ValueError(f"'{usage_key}' 是内置用途，无法删除")
        
        with self.Session() as session:
            slot = self._get_usage_slot(session, user_id, usage_key)
            if not slot:
                raise ValueError(f"用途 '{usage_key}' 不存在")
            
            session.delete(slot)
            session.commit()
            return True

    def list_user_usage_selections(self, user_id: str):
        """列出用户的所有用途选择"""
        user_id = str(user_id)
        with self.Session() as session:
            self.ensure_user_has_config(session, user_id)
            return self._collect_usage_payloads(session, user_id)

    def get_user_selection_detail(self, user_id: str, usage_key: Optional[str] = None) -> Dict[str, Any]:
        """获取用户特定用途的详细配置"""
        normalized_usage = self._normalize_usage_key(usage_key) if usage_key is not None else self._default_usage_key
        user_id = str(user_id)

        with self.Session() as session:
            self.ensure_user_has_config(session, user_id)
            usage_slot = self._get_usage_slot(session, user_id, normalized_usage)
            if not usage_slot:
                raise ValueError(f"未找到用途 '{normalized_usage}' 的模型配置")

            try:
                old_platform_id = usage_slot.selected_platform_id
                old_model_id = usage_slot.selected_model_id
                resolved = self._resolve_user_choice(
                    session,
                    user_id,
                    usage_slot.selected_platform_id,
                    usage_slot.selected_model_id,
                    usage_slot=usage_slot,
                    auto_fix=True,
                    raise_on_missing_key=False,
                )
                if usage_slot.selected_platform_id != old_platform_id or usage_slot.selected_model_id != old_model_id:
                    session.commit()
                current_detail = self._build_usage_payload(resolved, usage_slot)
                if not resolved.get("api_key"):
                    current_detail["missing_key"] = True
                    current_detail["error"] = "API Key 未配置"
            except ValueError as e:
                current_detail = self._build_invalid_usage_payload(usage_slot, str(e))
            
            all_details = self._collect_usage_payloads(session, user_id)
            
            return {
                "current": current_detail,
                "usage_selections": all_details,
            }

    # ==================== Embedding 选择管理 ====================

    def _build_embedding_payload(self, session, user_id: str, platform: LLMPlatform, model: LLModels) -> Dict[str, Any]:
        api_key = self._get_effective_api_key(session, user_id, platform)
        return {
            "platform_id": platform.id,
            "platform_name": platform.name,
            "base_url": platform.base_url,
            "model_id": model.id,
            "model_name": model.model_name,
            "display_name": model.display_name,
            "api_key_set": bool(api_key),
        }

    def save_user_embedding_selection(self, user_id: str, platform_id: int, model_id: int) -> Dict[str, Any]:
        user_id = str(user_id)
        with self.Session() as session:
            plat = session.query(LLMPlatform).filter_by(id=platform_id).first()
            model = session.query(LLModels).filter_by(id=model_id).first()
            if not plat or not model:
                raise ValueError("平台或模型不存在")
            if self._is_platform_disabled(session, user_id, plat):
                raise ValueError("平台已禁用")
            if model.platform_id != plat.id:
                raise ValueError("模型不属于该平台")
            if not model.is_embedding:
                raise ValueError("目标模型不是 Embedding")

            if not plat.is_sys and plat.user_id != user_id:
                raise ValueError("无权访问该平台")

            selection = session.query(UserEmbeddingSelection).filter_by(user_id=user_id).first()
            if not selection:
                selection = UserEmbeddingSelection(user_id=user_id)
                session.add(selection)

            selection.platform_id = platform_id
            selection.model_id = model_id
            session.commit()

            return self._build_embedding_payload(session, user_id, plat, model)

    def get_user_embedding_detail(self, user_id: str) -> Dict[str, Any]:
        user_id = str(user_id)
        with self.Session() as session:
            selection = session.query(UserEmbeddingSelection).filter_by(user_id=user_id).first()
            current = None

            if selection and selection.platform_id and selection.model_id:
                plat = session.query(LLMPlatform).filter_by(id=selection.platform_id).first()
                model = session.query(LLModels).filter_by(id=selection.model_id).first()
                if plat and model and model.is_embedding and not self._is_platform_disabled(session, user_id, plat):
                    current = self._build_embedding_payload(session, user_id, plat, model)

            return {
                "current": current,
            }

    # ==================== Agent 绑定管理 ====================

    def get_agent_bindings(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户的所有 Agent 绑定配置"""
        with self.Session() as session:
            bindings = session.query(AgentModelBinding).filter_by(user_id=user_id).all()
            return [
                {
                    "agent_name": b.agent_name,
                    "target_type": b.target_type,
                    "usage_key": b.usage_key,
                    "platform_id": b.platform_id,
                    "model_id": b.model_id,
                }
                for b in bindings
            ]

    def save_agent_binding(
        self,
        user_id: str,
        agent_name: str,
        target_type: str,
        usage_key: Optional[str] = None,
        platform_id: Optional[int] = None,
        model_id: Optional[int] = None
    ) -> bool:
        """保存 Agent 绑定配置"""
        if target_type not in ('usage', 'direct'):
            raise ValueError("target_type 必须是 'usage' 或 'direct'")
        
        with self.Session() as session:
            binding = session.query(AgentModelBinding).filter_by(
                user_id=user_id, agent_name=agent_name
            ).first()
            
            if not binding:
                binding = AgentModelBinding(user_id=user_id, agent_name=agent_name)
                session.add(binding)
            
            binding.target_type = target_type
            binding.usage_key = usage_key
            binding.platform_id = platform_id
            binding.model_id = model_id
            
            session.commit()
            return True

    def delete_agent_binding(self, user_id: str, agent_name: str) -> bool:
        """删除 Agent 绑定配置"""
        with self.Session() as session:
            binding = session.query(AgentModelBinding).filter_by(
                user_id=user_id, agent_name=agent_name
            ).first()
            if binding:
                session.delete(binding)
                session.commit()
                return True
            return False
