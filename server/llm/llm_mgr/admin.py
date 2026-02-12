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
from .utils import normalize_base_url


def _parse_extra_body_for_response(extra_body_str: Optional[str]) -> Optional[Dict]:
    """将数据库中的 extra_body 字符串解析为 Python 对象，用于 API 响应。
    
    返回:
        - None: 如果输入为 None、空字符串、"null" 或 "{}"
        - dict: 解析后的 JSON 对象
    """
    if not extra_body_str:
        return None
    try:
        parsed = json.loads(extra_body_str)
        # 如果解析后是 None 或空字典，统一返回 None
        if parsed is None or parsed == {}:
            return None
        return parsed
    except (json.JSONDecodeError, TypeError):
        return None


class AdminMixin:
    """平台与模型管理功能 (Admin)"""

    # ==================== 平台管理 ====================

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
        
        user_id = str(user_id)
        base_url = normalize_base_url(base_url)
        
        if api_key:
            api_key = SecurityManager.get_instance().encrypt(api_key)
        
        with self.Session() as session:
            # 复活同名的已禁用自定义平台（避免重复建垃圾数据）
            existing_same_name = session.query(LLMPlatform).filter_by(name=name, user_id=user_id, is_sys=0).first()
            if existing_same_name and existing_same_name.disable:
                existing_same_name.base_url = base_url
                existing_same_name.api_key = api_key
                existing_same_name.disable = 0
                session.commit()
                return existing_same_name

            existing_same_url = session.query(LLMPlatform).filter_by(base_url=base_url, user_id=user_id, is_sys=0).first()
            if existing_same_url and existing_same_url.disable:
                existing_same_url.name = name
                existing_same_url.api_key = api_key
                existing_same_url.disable = 0
                session.commit()
                return existing_same_url

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
        user_id = str(user_id)
        with self.Session() as session:
            plat = session.query(LLMPlatform).filter_by(id=platform_id, user_id=user_id, is_sys=0).first()
            if not plat:
                raise ValueError("平台不存在或无权删除")
            session.delete(plat)
            session.commit()
            return True

    def admin_delete_sys_platform(self, platform_id: int):
        """管理员删除系统平台（软禁用，避免下次 YAML 增量同步自动复活）"""
        self._ensure_mutable()
        with self.Session() as session:
            plat = session.query(LLMPlatform).filter_by(id=platform_id, is_sys=1).first()
            if not plat:
                raise ValueError("系统平台不存在")

            plat.disable = 1
            session.commit()
            return True

    def update_platform_details(self, user_id: str, platform_id: int, new_name: str, new_base_url: str):
        self._ensure_mutable()
        user_id = str(user_id)
        if not (new_name and new_base_url):
            raise ValueError("name 和 base_url 都不能为空")
        
        new_base_url = normalize_base_url(new_base_url)
        
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
        user_id = str(user_id)
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

    def set_platform_disabled(self, user_id: str, platform_id: int, disabled: bool):
        """禁用/启用平台"""
        user_id = str(user_id)
        with self.Session() as session:
            plat = session.query(LLMPlatform).filter_by(id=platform_id).first()
            if not plat:
                raise ValueError("平台不存在")
            
            disable_val = self._bool_to_int(disabled)
            
            if plat.is_sys:
                cred = session.query(LLMSysPlatformKey).filter_by(
                    user_id=user_id, platform_id=platform_id
                ).first()
                if not cred:
                    cred = LLMSysPlatformKey(user_id=user_id, platform_id=platform_id)
                    session.add(cred)
                cred.disable = disable_val
            else:
                if plat.user_id != user_id:
                    raise ValueError("无权修改此平台")
                plat.disable = disable_val
            
            session.commit()
            return True

    def toggle_platform_visibility(self, user_id: str, platform_id: int, hide: bool):
        """兼容旧接口：切换平台可见性"""
        return self.set_platform_disabled(user_id, platform_id, disabled=hide)

    def _collect_platform_views(self, session, user_id: str) -> List[Dict[str, Any]]:
        """收集用户可见的所有平台视图"""
        user_id = str(user_id)
        self._get_sys_config(session)
        
        # 将缓存的系统平台对象合并到当前会话
        sys_platforms = [session.merge(p, load=False) for p in self._sys_platforms_cache]
        
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
            user_disable = cred.disable if cred else 0

            views.append(
                {
                    "platform_id": plat.id,
                    "name": plat.name,
                    "base_url": plat.base_url,
                    "api_key_set": bool(api_key),
                    "user_id": plat.user_id,
                    "is_sys": True,
                    "user_key_override": bool(cred and cred.api_key),
                    "disabled": int(bool(plat.disable) or bool(user_disable)),
                    "models": [m for m in plat.models if not self._is_model_disabled(m)],
                }
            )

        # 查询用户自定义平台（统一使用字符串类型 user_id）
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
                    "user_key_override": False,
                    "disabled": plat.disable,
                    "models": [m for m in plat.models if not self._is_model_disabled(m)],
                }
            )

        return views

    def get_platforms(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户可见的所有平台（不含模型详情，用于平台管理界面）"""
        user_id = str(user_id)
        with self.Session() as session:
            views = self._collect_platform_views(session, user_id)
            return [
                {
                    "platform_id": view["platform_id"],
                    "name": view["name"],
                    "base_url": view["base_url"],
                    "api_key_set": view["api_key_set"],
                    "is_sys": view["is_sys"],
                    "user_key_override": view.get("user_key_override", False),
                    "disabled": view["disabled"],
                    "model_count": len(view["models"]),
                }
                for view in views
                if not view["disabled"]
            ]

    def get_platforms_with_models(self, user_id: str, only_custom: bool = False) -> List[Dict[str, Any]]:
        """获取平台列表，包含嵌套的模型数组（用于模型管理界面）"""
        user_id = str(user_id)
        with self.Session() as session:
            views = self._collect_platform_views(session, user_id)
            results = []
            for view in views:
                if view["disabled"]:
                    continue
                if only_custom and view["is_sys"]:
                    continue
                results.append({
                    "platform_id": view["platform_id"],
                    "name": view["name"],
                    "base_url": view["base_url"],
                    "api_key_set": view["api_key_set"],
                    "is_sys": view["is_sys"],
                    "user_key_override": view.get("user_key_override", False),
                    "disabled": view["disabled"],
                    "models": [
                        {
                            "model_id": m.id,
                            "model_name": m.model_name,
                            "display_name": m.display_name,
                            "extra_body": _parse_extra_body_for_response(m.extra_body),
                        }
                        for m in view["models"]
                        if not m.is_embedding
                    ]
                })
            return results

    def get_platform_models(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户可见的所有平台和模型（打平结构，用于模型选择）"""
        with self.Session() as session:
            views = self._collect_platform_views(session, user_id)
            return [
                {
                    "platform_id": view["platform_id"],
                    "platform_name": view["name"],
                    "platform_is_sys": view["is_sys"],
                    "platform_disabled": view["disabled"],
                    "base_url": view["base_url"],
                    "api_key_set": view["api_key_set"],
                    "user_key_override": view.get("user_key_override", False),
                    "model_id": model.id,
                    "model_name": model.model_name,
                    "display_name": model.display_name,
                    "extra_body": _parse_extra_body_for_response(model.extra_body),
                }
                for view in views
                if not view["disabled"]
                for model in view["models"]
                if not model.is_embedding
            ]

    def get_platforms_with_embeddings(self, user_id: str, only_custom: bool = False) -> List[Dict[str, Any]]:
        """获取平台列表，包含嵌套的 Embedding 模型数组"""
        user_id = str(user_id)
        with self.Session() as session:
            views = self._collect_platform_views(session, user_id)
            results = []
            for view in views:
                if view["disabled"]:
                    continue
                if only_custom and view["is_sys"]:
                    continue
                results.append({
                    "platform_id": view["platform_id"],
                    "name": view["name"],
                    "base_url": view["base_url"],
                    "api_key_set": view["api_key_set"],
                    "is_sys": view["is_sys"],
                    "user_key_override": view.get("user_key_override", False),
                    "disabled": view["disabled"],
                    "embeddings": [
                        {
                            "model_id": m.id,
                            "model_name": m.model_name,
                            "display_name": m.display_name,
                            "extra_body": _parse_extra_body_for_response(m.extra_body),
                        }
                        for m in view["models"]
                        if m.is_embedding
                    ]
                })
            return results

    # ==================== 模型管理 ====================

    def add_model(
        self,
        platform_id: int,
        model_name: str,
        display_name: str,
        user_id: str = None,
        extra_body: Optional[Dict[str, Any]] = None,
        admin_mode: bool = False,
    ):
        """
        添加模型（统一入口）
        - admin_mode=False: 普通用户为自定义平台添加模型，需要 user_id
        - admin_mode=True: 管理员为系统平台添加模型，不需要 user_id
        """
        self._ensure_mutable()
        if not (platform_id and model_name and display_name):
            raise ValueError("platform_id / model_name / display_name 必填")

        with self.Session() as session:
            if admin_mode:
                # 管理员模式：操作系统平台
                plat = session.query(LLMPlatform).filter_by(id=platform_id, is_sys=1).first()
                if not plat:
                    raise ValueError("系统平台不存在")
                # 检查显示名称在所有系统平台中唯一
                scope_platforms = session.query(LLMPlatform).filter_by(is_sys=1).all()
            else:
                # 用户模式：操作自定义平台
                if user_id is None or user_id == SYSTEM_USER_ID:
                    raise ValueError("为模型绑定真实 user_id")
                user_id = str(user_id)
                plat = session.query(LLMPlatform).filter_by(id=platform_id, user_id=user_id, is_sys=0).first()
                if not plat:
                    raise ValueError("平台不存在、无权限或为不可修改的系统平台")
                if self._is_platform_disabled(session, user_id, plat):
                    raise ValueError("平台已禁用")
                # 检查显示名称在用户所有自定义平台中唯一
                scope_platforms = session.query(LLMPlatform).filter_by(user_id=user_id, is_sys=0).all()

            scope_platform_ids = [p.id for p in scope_platforms]
            existing_display = session.query(LLModels).filter(
                LLModels.platform_id.in_(scope_platform_ids),
                LLModels.display_name == display_name
            ).first()
            if existing_display:
                if self._is_model_disabled(existing_display):
                    existing_display.platform_id = plat.id
                    existing_display.model_name = model_name
                    existing_display.display_name = display_name
                    existing_display.is_embedding = 0
                    existing_display.extra_body = json.dumps(extra_body) if extra_body else None
                    self._set_model_disabled(existing_display, False)
                    session.commit()
                    if admin_mode:
                        with self._cache_lock:
                            self._sys_platforms_cache = None
                    return existing_display
                existing_plat = session.query(LLMPlatform).filter_by(id=existing_display.platform_id).first()
                raise ValueError(f"模型显示名称 '{display_name}' 已存在于平台 '{existing_plat.name}'")

            extra_body_json = json.dumps(extra_body) if extra_body else None

            m = LLModels(
                platform_id=plat.id,
                model_name=model_name,
                display_name=display_name,
                extra_body=extra_body_json,
                is_embedding=0,
            )
            session.add(m)
            session.commit()
            
            # 如果是系统平台模型，刷新缓存
            if admin_mode:
                with self._cache_lock:
                    self._sys_platforms_cache = None
            
            return m

    def add_embedding(
        self,
        platform_id: int,
        model_name: str,
        display_name: str,
        user_id: str = None,
        extra_body: Optional[Dict[str, Any]] = None,
        admin_mode: bool = False,
    ):
        """
        添加 Embedding（统一入口）
        - admin_mode=False: 普通用户为自定义平台添加
        - admin_mode=True: 管理员为系统平台添加
        """
        self._ensure_mutable()
        if not (platform_id and model_name and display_name):
            raise ValueError("platform_id / model_name / display_name 必填")

        with self.Session() as session:
            if admin_mode:
                plat = session.query(LLMPlatform).filter_by(id=platform_id, is_sys=1).first()
                if not plat:
                    raise ValueError("系统平台不存在")
                scope_platforms = session.query(LLMPlatform).filter_by(is_sys=1).all()
            else:
                if user_id is None or user_id == SYSTEM_USER_ID:
                    raise ValueError("为 embedding 绑定真实 user_id")
                user_id = str(user_id)
                plat = session.query(LLMPlatform).filter_by(id=platform_id, user_id=user_id, is_sys=0).first()
                if not plat:
                    raise ValueError("平台不存在、无权限或为不可修改的系统平台")
                if self._is_platform_disabled(session, user_id, plat):
                    raise ValueError("平台已禁用")
                scope_platforms = session.query(LLMPlatform).filter_by(user_id=user_id, is_sys=0).all()

            scope_platform_ids = [p.id for p in scope_platforms]
            existing_display = session.query(LLModels).filter(
                LLModels.platform_id.in_(scope_platform_ids),
                LLModels.display_name == display_name
            ).first()
            if existing_display:
                if self._is_model_disabled(existing_display):
                    existing_display.platform_id = plat.id
                    existing_display.model_name = model_name
                    existing_display.display_name = display_name
                    existing_display.is_embedding = 1
                    existing_display.extra_body = json.dumps(extra_body) if extra_body else None
                    self._set_model_disabled(existing_display, False)
                    session.commit()
                    if admin_mode:
                        with self._cache_lock:
                            self._sys_platforms_cache = None
                    return existing_display
                existing_plat = session.query(LLMPlatform).filter_by(id=existing_display.platform_id).first()
                raise ValueError(f"模型显示名称 '{display_name}' 已存在于平台 '{existing_plat.name}'")

            extra_body_json = json.dumps(extra_body) if extra_body else None

            m = LLModels(
                platform_id=plat.id,
                model_name=model_name,
                display_name=display_name,
                extra_body=extra_body_json,
                is_embedding=1,
            )
            session.add(m)
            session.commit()
            
            # 如果是系统平台 Embedding，刷新缓存
            if admin_mode:
                with self._cache_lock:
                    self._sys_platforms_cache = None
            
            return m

    def update_model(
        self,
        model_id: int,
        new_display_name: Optional[str] = None,
        new_extra_body: Optional[Dict[str, Any]] = None,
        user_id: str = None,
        admin_mode: bool = False,
    ):
        """
        更新模型（统一入口）
        - admin_mode=False: 普通用户更新自定义平台模型，需要 user_id
        - admin_mode=True: 管理员更新系统平台模型
        """
        self._ensure_mutable()
        with self.Session() as session:
            model = session.query(LLModels).filter_by(id=model_id).first()
            if not model:
                raise ValueError("模型不存在")

            plat = session.query(LLMPlatform).filter_by(id=model.platform_id).first()
            
            if admin_mode:
                if not plat or not plat.is_sys:
                    raise ValueError("此模型不属于系统平台")
                scope_platforms = session.query(LLMPlatform).filter_by(is_sys=1).all()
            else:
                user_id = str(user_id) if user_id else None
                if not plat or plat.is_sys or plat.user_id != user_id:
                    raise ValueError("无权修改此模型（系统模型或他人模型）")
                if self._is_platform_disabled(session, user_id, plat):
                    raise ValueError("平台已禁用")
                scope_platforms = session.query(LLMPlatform).filter_by(user_id=user_id, is_sys=0).all()

            if model.is_embedding:
                raise ValueError("请使用 Embedding 管理接口修改该模型")

            if new_display_name is not None:
                scope_platform_ids = [p.id for p in scope_platforms]
                existing = session.query(LLModels).filter(
                    LLModels.platform_id.in_(scope_platform_ids),
                    LLModels.display_name == new_display_name,
                    LLModels.id != model_id
                ).first()
                if existing:
                    raise ValueError(f"显示名称 '{new_display_name}' 已被使用")
                model.display_name = new_display_name

            if new_extra_body is not None:
                model.extra_body = json.dumps(new_extra_body) if new_extra_body else None

            session.commit()
            
            # 如果是系统平台模型，刷新缓存
            if admin_mode:
                with self._cache_lock:
                    self._sys_platforms_cache = None
            
            return True

    def update_embedding(
        self,
        model_id: int,
        new_display_name: Optional[str] = None,
        new_extra_body: Optional[Dict[str, Any]] = None,
        user_id: str = None,
        admin_mode: bool = False,
    ):
        """
        更新 Embedding（统一入口）
        - admin_mode=False: 普通用户更新
        - admin_mode=True: 管理员更新系统平台
        """
        self._ensure_mutable()
        with self.Session() as session:
            model = session.query(LLModels).filter_by(id=model_id).first()
            if not model:
                raise ValueError("模型不存在")

            plat = session.query(LLMPlatform).filter_by(id=model.platform_id).first()
            
            if admin_mode:
                if not plat or not plat.is_sys:
                    raise ValueError("此模型不属于系统平台")
                scope_platforms = session.query(LLMPlatform).filter_by(is_sys=1).all()
            else:
                user_id = str(user_id) if user_id else None
                if not plat or plat.is_sys or plat.user_id != user_id:
                    raise ValueError("无权修改此模型（系统模型或他人模型）")
                if self._is_platform_disabled(session, user_id, plat):
                    raise ValueError("平台已禁用")
                scope_platforms = session.query(LLMPlatform).filter_by(user_id=user_id, is_sys=0).all()

            if not model.is_embedding:
                raise ValueError("目标模型不是 Embedding")

            if new_display_name is not None:
                scope_platform_ids = [p.id for p in scope_platforms]
                existing = session.query(LLModels).filter(
                    LLModels.platform_id.in_(scope_platform_ids),
                    LLModels.display_name == new_display_name,
                    LLModels.id != model_id
                ).first()
                if existing:
                    raise ValueError(f"显示名称 '{new_display_name}' 已被使用")
                model.display_name = new_display_name

            if new_extra_body is not None:
                model.extra_body = json.dumps(new_extra_body) if new_extra_body else None

            session.commit()
            
            # 如果是系统平台 Embedding，刷新缓存
            if admin_mode:
                with self._cache_lock:
                    self._sys_platforms_cache = None
            
            return True

    def delete_model(self, model_id: int, user_id: str = None, admin_mode: bool = False):
        """
        删除模型（统一入口）
        - admin_mode=False: 普通用户删除自定义平台模型
        - admin_mode=True: 管理员删除系统平台模型
        """
        self._ensure_mutable()
        with self.Session() as session:
            model = session.query(LLModels).filter_by(id=model_id).first()
            if not model:
                raise ValueError("模型不存在")

            plat = session.query(LLMPlatform).filter_by(id=model.platform_id).first()
            
            if admin_mode:
                if not plat or not plat.is_sys:
                    raise ValueError("此模型不属于系统平台")
            else:
                user_id = str(user_id) if user_id else None
                if not plat or plat.is_sys or plat.user_id != user_id:
                    raise ValueError("无权删除此模型（系统模型或他人模型）")

            if model.is_embedding:
                raise ValueError("请使用 Embedding 管理接口删除该模型")

            if admin_mode and plat and plat.is_sys:
                self._set_model_disabled(model, True)
                session.commit()
            else:
                session.delete(model)
                session.commit()
            
            # 如果是系统平台模型，刷新缓存
            if admin_mode:
                with self._cache_lock:
                    self._sys_platforms_cache = None
            
            return True

    def delete_embedding(self, model_id: int, user_id: str = None, admin_mode: bool = False):
        """
        删除 Embedding（统一入口）
        - admin_mode=False: 普通用户删除
        - admin_mode=True: 管理员删除系统平台
        """
        self._ensure_mutable()
        with self.Session() as session:
            model = session.query(LLModels).filter_by(id=model_id).first()
            if not model:
                raise ValueError("模型不存在")

            plat = session.query(LLMPlatform).filter_by(id=model.platform_id).first()
            
            if admin_mode:
                if not plat or not plat.is_sys:
                    raise ValueError("此模型不属于系统平台")
            else:
                user_id = str(user_id) if user_id else None
                if not plat or plat.is_sys or plat.user_id != user_id:
                    raise ValueError("无权删除此模型（系统模型或他人模型）")

            if not model.is_embedding:
                raise ValueError("目标模型不是 Embedding")

            if admin_mode and plat and plat.is_sys:
                self._set_model_disabled(model, True)
                session.commit()
            else:
                session.delete(model)
                session.commit()
            
            # 如果是系统平台 Embedding，刷新缓存
            if admin_mode:
                with self._cache_lock:
                    self._sys_platforms_cache = None
            
            return True

    # 兼容性别名（保持旧API可用，后续可逐步移除）
    def admin_add_sys_model(self, platform_id, model_name, display_name, extra_body=None):
        """管理员：添加系统模型"""
        return self.add_model(platform_id, model_name, display_name, extra_body=extra_body, admin_mode=True)

    def admin_update_sys_model(self, model_id, new_display_name=None, new_extra_body=None):
        """管理员：更新系统模型"""
        return self.update_model(model_id, new_display_name, new_extra_body, admin_mode=True)

    def admin_delete_sys_model(self, model_id):
        """管理员：删除系统模型"""
        return self.delete_model(model_id, admin_mode=True)

    def admin_add_sys_embedding(self, platform_id, model_name, display_name, extra_body=None):
        """管理员：添加系统 Embedding"""
        return self.add_embedding(platform_id, model_name, display_name, extra_body=extra_body, admin_mode=True)

    def admin_update_sys_embedding(self, model_id, new_display_name=None, new_extra_body=None):
        """管理员：更新系统 Embedding"""
        return self.update_embedding(model_id, new_display_name, new_extra_body, admin_mode=True)

    def admin_delete_sys_embedding(self, model_id):
        """管理员：删除系统 Embedding"""
        return self.delete_embedding(model_id, admin_mode=True)

    # ==================== 管理员：系统平台管理 ====================
    #
    # ⚠️ 重要说明：系统平台的两种数据源
    #
    # 1. YAML 文件 (llm_mgr_cfg.yaml)
    #    - 作用：初始化模板、配置分享、备份迁移
    #    - 特点：修改后需重启服务才生效；便于版本控制和分享（不含密钥）
    #    - 适用场景：无前端环境、快速部署、配置模板分发
    #
    # 2. 数据库 (llm_config.db)
    #    - 作用：运行时的唯一数据源，所有 API 和 GUI 操作都写入数据库
    #    - 特点：修改即时生效，无需重启；支持前端和 API 管理
    #    - 适用场景：生产环境、需要动态修改配置
    #
    # 同步策略：
    #    - 首次启动时，YAML 配置初始化到数据库
    #    - 后续启动时，仅添加 YAML 中新增的平台，不覆盖已有配置
    #    - 提供 admin_reload_from_yaml() 方法手动重置为 YAML 配置
    #

    def admin_get_sys_platforms(self) -> List[Dict[str, Any]]:
        """
        获取所有系统平台列表（管理员专用）
        返回系统平台的完整信息，包含解密后的 API Key 状态
        """
        with self.Session() as session:
            platforms = session.query(LLMPlatform).filter_by(is_sys=1).all()
            
            sec_mgr = SecurityManager.get_instance()
            results = []
            
            for plat in platforms:
                # 检查是否有 API Key
                api_key_set = False
                if plat.api_key:
                    try:
                        decrypted = sec_mgr.decrypt(plat.api_key)
                        api_key_set = bool(decrypted and not decrypted.startswith("ENC:"))
                    except:
                        pass
                
                # 统计模型数量
                model_count = len([m for m in plat.models if not m.is_embedding and not self._is_model_disabled(m)])
                embedding_count = len([m for m in plat.models if m.is_embedding and not self._is_model_disabled(m)])
                
                results.append({
                    "platform_id": plat.id,
                    "name": plat.name,
                    "base_url": plat.base_url,
                    "api_key_set": api_key_set,
                    "model_count": model_count,
                    "embedding_count": embedding_count,
                })
            
            return results

    def admin_add_sys_platform(
        self,
        name: str,
        base_url: str,
        api_key: Optional[str] = None,
    ) -> LLMPlatform:
        """
        添加系统平台（管理员专用）
        直接写入数据库，即时生效，无需重启服务
        """
        if not (name and base_url):
            raise ValueError("name / base_url 必填")
        
        base_url = normalize_base_url(base_url)
        
        with self.Session() as session:
            existing_name_disabled = session.query(LLMPlatform).filter_by(name=name, is_sys=1).first()
            if existing_name_disabled and existing_name_disabled.disable:
                existing_name_disabled.base_url = base_url
                existing_name_disabled.disable = 0
                if api_key:
                    existing_name_disabled.api_key = SecurityManager.get_instance().encrypt(api_key)
                session.commit()

                with self._cache_lock:
                    self._sys_platforms_cache = None

                return existing_name_disabled

            # 同 base_url 的系统平台若已存在且被禁用，则复活
            existing_url = session.query(LLMPlatform).filter_by(base_url=base_url, is_sys=1).first()
            if existing_url and existing_url.disable:
                existing_url.name = name
                existing_url.disable = 0
                if api_key:
                    existing_url.api_key = SecurityManager.get_instance().encrypt(api_key)
                session.commit()

                with self._cache_lock:
                    self._sys_platforms_cache = None

                return existing_url

            # 检查名称是否已存在
            existing_name = session.query(LLMPlatform).filter_by(name=name).first()
            if existing_name:
                raise ValueError(f"平台名称 '{name}' 已存在")
            
            # 检查 base_url 是否已存在于系统平台
            existing_url = session.query(LLMPlatform).filter_by(base_url=base_url, is_sys=1).first()
            if existing_url:
                raise ValueError(f"已存在使用该 base_url 的系统平台: {existing_url.name}")
            
            # 加密 API Key
            encrypted_key = None
            if api_key:
                encrypted_key = SecurityManager.get_instance().encrypt(api_key)
            
            plat = LLMPlatform(
                name=name,
                base_url=base_url,
                api_key=encrypted_key,
                user_id=SYSTEM_USER_ID,
                is_sys=1,
            )
            session.add(plat)
            session.commit()
            
            # 刷新缓存
            with self._cache_lock:
                self._sys_platforms_cache = None
            
            return plat

    def admin_update_sys_platform(
        self,
        platform_id: int,
        new_name: Optional[str] = None,
        new_base_url: Optional[str] = None,
    ) -> bool:
        """
        更新系统平台信息（管理员专用）
        """
        with self.Session() as session:
            plat = session.query(LLMPlatform).filter_by(id=platform_id, is_sys=1).first()
            if not plat:
                raise ValueError("系统平台不存在")
            
            if new_name is not None:
                # 检查名称唯一性
                existing = session.query(LLMPlatform).filter(
                    LLMPlatform.name == new_name,
                    LLMPlatform.id != platform_id
                ).first()
                if existing:
                    raise ValueError(f"平台名称 '{new_name}' 已被使用")
                plat.name = new_name
            
            if new_base_url is not None:
                new_base_url = normalize_base_url(new_base_url)
                # 检查 base_url 唯一性（仅系统平台）
                existing = session.query(LLMPlatform).filter(
                    LLMPlatform.base_url == new_base_url,
                    LLMPlatform.is_sys == 1,
                    LLMPlatform.id != platform_id
                ).first()
                if existing:
                    raise ValueError(f"已存在使用该 base_url 的系统平台: {existing.name}")
                plat.base_url = new_base_url
            
            session.commit()
            
            # 刷新缓存
            with self._cache_lock:
                self._sys_platforms_cache = None
            
            return True

    def admin_update_sys_platform_api_key(
        self,
        platform_id: int,
        api_key: Optional[str],
    ) -> bool:
        """
        更新系统平台的默认 API Key（管理员专用）
        此 Key 作为系统默认 Key，当用户未设置自己的 Key 且 LLM_AUTO_KEY=True 时使用
        """
        with self.Session() as session:
            plat = session.query(LLMPlatform).filter_by(id=platform_id, is_sys=1).first()
            if not plat:
                raise ValueError("系统平台不存在")
            
            if api_key:
                plat.api_key = SecurityManager.get_instance().encrypt(api_key)
            else:
                plat.api_key = None
            
            session.commit()
            
            # 刷新缓存
            with self._cache_lock:
                self._sys_platforms_cache = None
            
            return True

    def admin_delete_sys_platform(self, platform_id: int) -> bool:
        """
        删除系统平台（管理员专用）
        实际执行软禁用，避免 YAML 增量同步在下次启动时自动重新添加。
        """
        with self.Session() as session:
            plat = session.query(LLMPlatform).filter_by(id=platform_id, is_sys=1).first()
            if not plat:
                raise ValueError("系统平台不存在")

            plat.disable = 1
            session.commit()
            
            # 刷新缓存
            with self._cache_lock:
                self._sys_platforms_cache = None
            
            return True

    def admin_set_sys_platform_default(self, platform_id: int) -> bool:
        """
        将指定平台设为默认（即在系统平台列表中排第一位）
        通过调整内部默认ID实现，重启后依赖数据库ID顺序
        注意：此方法主要用于 GUI，前端建议直接记录选中的平台ID
        """
        with self.Session() as session:
            plat = session.query(LLMPlatform).filter_by(id=platform_id, is_sys=1).first()
            if not plat:
                raise ValueError("系统平台不存在")
            
            # 更新默认平台ID
            self._default_platform_id = platform_id
            
            # 获取该平台的第一个非 embedding 模型作为默认
            first_model = session.query(LLModels).filter(
                LLModels.platform_id == platform_id,
                LLModels.is_embedding == 0
            ).first()
            
            if first_model:
                self._default_model_id = first_model.id
            
            return True


