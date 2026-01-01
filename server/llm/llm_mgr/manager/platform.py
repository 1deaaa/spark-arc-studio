"""
平台管理 Mixin
处理平台的增删改查
"""

from typing import Optional, Dict, Any, List

from sqlalchemy.orm import selectinload

from ..models import LLMPlatform, LLModels, LLMSysPlatformKey
from ..config import DEFAULT_PLATFORM_CONFIGS, SYSTEM_USER_ID
from ..security import SecurityManager


class PlatformMixin:
    """平台管理功能"""

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
        
        if api_key:
            api_key = SecurityManager.get_instance().encrypt(api_key)
        
        with self.Session() as session:
            if name in DEFAULT_PLATFORM_CONFIGS:
                raise ValueError("平台名称与系统平台冲突")
            # 允许与系统平台 base_url 重复，但不允许与用户自己的其他自定义平台重复
            if session.query(LLMPlatform).filter_by(base_url=base_url, user_id=user_id, is_sys=0).first():
                raise ValueError("您已创建过使用该base_url的平台")
            if session.query(LLMPlatform).filter_by(name=name, user_id=user_id, is_sys=0).first():
                raise ValueError(f"您已创建过一个名为 '{name}' 的平台")
            
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
        
        with self.Session() as session:
            plat = session.query(LLMPlatform).filter_by(id=platform_id, user_id=user_id, is_sys=0).first()
            if not plat:
                raise ValueError("平台不存在或无权修改")
            
            # 名称唯一性检查（排除自己）
            if new_name in DEFAULT_PLATFORM_CONFIGS:
                raise ValueError("平台名称与系统平台冲突")
            existing_name = session.query(LLMPlatform).filter(
                LLMPlatform.name == new_name,
                LLMPlatform.user_id == user_id,
                LLMPlatform.is_sys == 0,
                LLMPlatform.id != platform_id
            ).first()
            if existing_name:
                raise ValueError(f"您已有一个名为 '{new_name}' 的平台")
                
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
