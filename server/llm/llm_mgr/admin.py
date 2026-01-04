"""
平台与模型管理 Mixin (Admin)
处理平台和模型的增删改查
"""

import json
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import selectinload

from .models import LLMPlatform, LLModels, LLMSysPlatformKey
from .config import DEFAULT_PLATFORM_CONFIGS, SYSTEM_USER_ID
from .security import SecurityManager


class AdminMixin:
    """平台与模型管理功能 (Admin)"""

    # ==================== 平台管理 ====================

    def _normalize_base_url(self, url: str) -> str:
        """规范化 Base URL"""
        url = url.strip()
        if not url:
            return url
            
        # 移除末尾斜杠
        url = url.rstrip('/')
        
        # 如果以 /chat/completions 结尾，移除它
        if url.endswith('/chat/completions'):
            url = url[:-17]
            url = url.rstrip('/')
        
        # 自动补全 /v1
        # 如果 URL 不以 /v1 (或 v2, v3...) 结尾，则默认追加 /v1
        # 这样可以支持 https://api.deepseek.com -> https://api.deepseek.com/v1
        import re
        if not re.search(r'/v\d+$', url):
            url = f"{url}/v1"

        return url

    def add_platform(
        self,
        name: str,
        base_url: str,
        api_key: Optional[str] = None,
        user_id: str = None,
    ):
        self._ensure_mutable()
        if not (name and base_url):
            raise ValueError("name / base_url 必填")
        if user_id is None or user_id == SYSTEM_USER_ID:
            raise ValueError("用户自定义平台必须绑定真实 user_id")
        
        base_url = self._normalize_base_url(base_url)
        
        if api_key:
            api_key = SecurityManager.get_instance().encrypt(api_key)
        
        with self.Session() as session:
            # 平台名称全局唯一性检查
            if name in DEFAULT_PLATFORM_CONFIGS or session.query(LLMPlatform).filter_by(name=name).first():
                raise ValueError(f"平台名称 '{name}' 已存在（系统预设或已被其他用户使用）")
            
            # 允许与系统平台 base_url 重复，但不允许与用户自己的其他自定义平台重复
            if session.query(LLMPlatform).filter_by(base_url=base_url, user_id=user_id, is_sys=0).first():
                raise ValueError("您已创建过使用该base_url的平台")
            
            p = LLMPlatform(
                name=name, base_url=base_url, api_key=api_key, user_id=user_id, is_sys=0
            )
            session.add(p)
            session.commit()
            return p

    def delete_platform(self, user_id: str, platform_id: int):
        self._ensure_mutable()
        with self.Session() as session:
            plat = session.query(LLMPlatform).filter_by(id=platform_id, user_id=user_id, is_sys=0).first()
            if not plat:
                raise ValueError("平台不存在或无权删除")
            session.delete(plat)
            session.commit()
            return True

    def update_platform_details(self, user_id: str, platform_id: int, new_name: str, new_base_url: str):
        self._ensure_mutable()
        if not (new_name and new_base_url):
            raise ValueError("name 和 base_url 都不能为空")
        
        new_base_url = self._normalize_base_url(new_base_url)
        
        with self.Session() as session:
            plat = session.query(LLMPlatform).filter_by(id=platform_id, user_id=user_id, is_sys=0).first()
            if not plat:
                raise ValueError("平台不存在或无权修改")
            
            # 名称全局唯一性检查（排除自己）
            if new_name in DEFAULT_PLATFORM_CONFIGS:
                raise ValueError("平台名称与系统平台冲突")
            existing_name = session.query(LLMPlatform).filter(
                LLMPlatform.name == new_name,
                LLMPlatform.id != platform_id
            ).first()
            if existing_name:
                raise ValueError(f"平台名称 '{new_name}' 已被使用")
                
            # base_url 唯一性检查（排除自己，仅用户自定义平台）
            existing_url = session.query(LLMPlatform).filter(
                LLMPlatform.base_url == new_base_url,
                LLMPlatform.user_id == user_id,
                LLMPlatform.is_sys == 0,
                LLMPlatform.id != platform_id
            ).first()
            if existing_url:
                raise ValueError("您已有一个使用该 base_url 的平台")
            
            plat.name = new_name
            plat.base_url = new_base_url
            session.commit()
            return True

    def update_platform_config(
        self, user_id: str, platform_id: int, api_key: str
    ):
        """更新平台的 API Key"""
        with self.Session() as session:
            plat = session.query(LLMPlatform).filter_by(id=platform_id).first()
            if not plat:
                raise ValueError("平台不存在")
            
            sec_mgr = SecurityManager.get_instance()
            encrypted_key = sec_mgr.encrypt(api_key) if api_key else None
            
            if plat.is_sys:
                # 系统平台：更新用户的密钥配置
                cred = session.query(LLMSysPlatformKey).filter_by(
                    user_id=user_id, platform_id=platform_id
                ).first()
                if not cred:
                    cred = LLMSysPlatformKey(user_id=user_id, platform_id=platform_id)
                    session.add(cred)
                cred.api_key = encrypted_key
            else:
                # 用户平台：直接更新
                if plat.user_id != user_id:
                    raise ValueError("无权修改此平台")
                plat.api_key = encrypted_key
            
            session.commit()
            return True

    def toggle_platform_visibility(self, user_id: str, platform_id: int, hide: bool):
        """切换平台的可见性"""
        with self.Session() as session:
            plat = session.query(LLMPlatform).filter_by(id=platform_id).first()
            if not plat:
                raise ValueError("平台不存在")
            
            hide_val = self._bool_to_int(hide)
            
            if plat.is_sys:
                cred = session.query(LLMSysPlatformKey).filter_by(
                    user_id=user_id, platform_id=platform_id
                ).first()
                if not cred:
                    cred = LLMSysPlatformKey(user_id=user_id, platform_id=platform_id)
                    session.add(cred)
                cred.hide = hide_val
            else:
                if plat.user_id != user_id:
                    raise ValueError("无权修改此平台")
                plat.hide = hide_val
            
            session.commit()
            return True

    def _collect_platform_views(self, session, user_id: str) -> List[Dict[str, Any]]:
        """收集用户可见的所有平台视图"""
        self._get_sys_config(session)
        sys_platforms = self._sys_platforms_cache
        sys_platform_ids = [p.id for p in sys_platforms]

        user_sys_keys: Dict[int, LLMSysPlatformKey] = {}
        if sys_platform_ids:
            creds = (
                session.query(LLMSysPlatformKey)
                .filter(
                    LLMSysPlatformKey.user_id == user_id,
                    LLMSysPlatformKey.platform_id.in_(sys_platform_ids),
                )
                .all()
            )
            user_sys_keys = {c.platform_id: c for c in creds}

        views: List[Dict[str, Any]] = []

        for plat in sys_platforms:
            cred = user_sys_keys.get(plat.id)
            api_key = self._get_effective_api_key(session, user_id, plat)
            user_hide = cred.hide if cred else 0

            views.append(
                {
                    "platform_id": plat.id,
                    "name": plat.name,
                    "base_url": plat.base_url,
                    "api_key_set": bool(api_key),
                    "user_id": plat.user_id,
                    "is_sys": True,
                    "hide": user_hide,
                    "models": list(plat.models),
                }
            )

        user_platforms = (
            session.query(LLMPlatform)
            .options(selectinload(LLMPlatform.models))
            .filter_by(user_id=user_id, is_sys=0)
            .all()
        )

        for plat in user_platforms:
            api_key = self._get_effective_api_key(session, user_id, plat)
            views.append(
                {
                    "platform_id": plat.id,
                    "name": plat.name,
                    "base_url": plat.base_url,
                    "api_key_set": bool(api_key),
                    "user_id": plat.user_id,
                    "is_sys": False,
                    "hide": plat.hide,
                    "models": list(plat.models),
                }
            )

        return views

    def get_platform_models(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户可见的所有平台和模型"""
        with self.Session() as session:
            views = self._collect_platform_views(session, user_id)
            items = [
                {
                    "platform_id": view["platform_id"],
                    "platform_name": view["name"],
                    "platform_is_sys": view["is_sys"],
                    "platform_hide": view["hide"],
                    "base_url": view["base_url"],
                    "api_key_set": view["api_key_set"],
                    "model_id": model.id,
                    "model_name": model.model_name,
                    "display_name": model.display_name,
                    "extra_body": model.extra_body,
                }
                for view in views
                for model in view["models"]
            ]
            return items

    # ==================== 模型管理 ====================

    def add_model(
        self,
        platform_id: int,
        model_name: str,
        display_name: str,
        user_id: str,
        extra_body: Optional[Dict[str, Any]] = None,
    ):
        self._ensure_mutable()
        if not (platform_id and model_name and display_name):
            raise ValueError("platform_id / model_name / display_name 必填")
        if user_id is None or user_id == SYSTEM_USER_ID:
            raise ValueError("为模型绑定真实 user_id")

        with self.Session() as session:
            plat = session.query(LLMPlatform).filter_by(id=platform_id, user_id=user_id, is_sys=0).first()
            if not plat:
                raise ValueError("平台不存在、无权限或为不可修改的系统平台")

            user_platforms = session.query(LLMPlatform).filter_by(user_id=user_id, is_sys=0).all()
            user_platform_ids = [p.id for p in user_platforms]
            existing_display = session.query(LLModels).filter(
                LLModels.platform_id.in_(user_platform_ids),
                LLModels.display_name == display_name
            ).first()
            if existing_display:
                existing_plat = session.query(LLMPlatform).filter_by(id=existing_display.platform_id).first()
                raise ValueError(f"模型显示名称 '{display_name}' 已存在于您的平台 '{existing_plat.name}'")
            
            # 允许模型ID (model_name) 重复，以便为同一模型配置不同的 extra_body (例如区分 DeepSeek 正常模式和 Thinking 模式)
            
            extra_body_json = json.dumps(extra_body) if extra_body else None

            m = LLModels(
                platform_id=plat.id,
                model_name=model_name,
                display_name=display_name,
                extra_body=extra_body_json
            )
            session.add(m)
            session.commit()
            return m

    def delete_model(self, user_id: str, model_id: int):
        self._ensure_mutable()
        with self.Session() as session:
            model = session.query(LLModels).filter_by(id=model_id).first()
            if not model:
                raise ValueError("模型不存在")
            
            plat = session.query(LLMPlatform).filter_by(id=model.platform_id).first()
            if not plat or plat.is_sys or plat.user_id != user_id:
                raise ValueError("无权删除此模型（系统模型或他人模型）")
            
            session.delete(model)
            session.commit()
            return True

    def update_model(
        self,
        user_id: str,
        model_id: int,
        new_display_name: Optional[str] = None,
        new_extra_body: Optional[Dict[str, Any]] = None,
    ):
        self._ensure_mutable()
        with self.Session() as session:
            model = session.query(LLModels).filter_by(id=model_id).first()
            if not model:
                raise ValueError("模型不存在")
            
            plat = session.query(LLMPlatform).filter_by(id=model.platform_id).first()
            if not plat or plat.is_sys or plat.user_id != user_id:
                raise ValueError("无权修改此模型（系统模型或他人模型）")
            
            if new_display_name is not None:
                # 检查显示名称唯一性
                user_platforms = session.query(LLMPlatform).filter_by(user_id=user_id, is_sys=0).all()
                user_platform_ids = [p.id for p in user_platforms]
                existing = session.query(LLModels).filter(
                    LLModels.platform_id.in_(user_platform_ids),
                    LLModels.display_name == new_display_name,
                    LLModels.id != model_id
                ).first()
                if existing:
                    raise ValueError(f"显示名称 '{new_display_name}' 已被使用")
                model.display_name = new_display_name
            
            if new_extra_body is not None:
                model.extra_body = json.dumps(new_extra_body) if new_extra_body else None
            
            session.commit()
            return True
