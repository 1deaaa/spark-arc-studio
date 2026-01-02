"""
AIManager 核心实现
集成所有管理功能模块
"""

import os
import json
import threading
from typing import Dict, Any, Optional, List

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, selectinload

from .models import (
    Base, LLMPlatform, LLModels, LLMSysPlatformKey,
    UserModelUsage, AgentModelBinding, ModelUsageStats
)
from .config import (
    DEFAULT_PLATFORM_CONFIGS, SYSTEM_USER_ID, DEFAULT_USAGE_KEY,
    BUILTIN_USAGE_SLOTS, USE_SYS_LLM_CONFIG, LLM_AUTO_KEY,
    get_decrypted_api_key
)
from .security import SecurityManager

from .admin import AdminMixin
from .user_services import UserServicesMixin
from .builder import LLMBuilderMixin
from .usage_services import UsageServicesMixin


class AIManagerBase:
    """AIManager 基础类：数据库连接和初始化"""
    
    def __init__(self, db_name: str = "llm_config.db"):
        base_dir = os.path.abspath(os.path.dirname(__file__))
        db_path = os.path.join(base_dir, db_name)
        db_url = f"sqlite:///{db_path}"
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self._sys_platforms_cache = None 
        self._cache_lock = threading.Lock()
        self.use_sys_llm_config = USE_SYS_LLM_CONFIG
        self._default_platform_id = None
        self._default_model_id = None
        self._builtin_usage_map = {slot["key"]: slot for slot in BUILTIN_USAGE_SLOTS}
        self._default_usage_key = DEFAULT_USAGE_KEY

    def initialize_defaults(self):
        """同步默认平台并初始化默认ID"""
        self._sync_default_platforms()
        
        with self.Session() as session:
            default_platform_name = next(iter(DEFAULT_PLATFORM_CONFIGS))
            default_platform_config = DEFAULT_PLATFORM_CONFIGS[default_platform_name]
            default_model_display_name = next(iter(default_platform_config["models"]))
            
            default_plat = session.query(LLMPlatform).filter_by(name=default_platform_name, is_sys=1).first()
            if default_plat:
                self._default_platform_id = default_plat.id
                default_model = session.query(LLModels).filter_by(
                    platform_id=default_plat.id, 
                    display_name=default_model_display_name
                ).first()
                if default_model:
                    self._default_model_id = default_model.id
                else:
                    raise ValueError(f"默认模型 '{default_model_display_name}' 未找到")
            else:
                raise ValueError(f"默认平台 '{default_platform_name}' 未找到")
        
        with self.Session() as session:
            self.ensure_user_has_config(session, SYSTEM_USER_ID)

    def _sync_default_platforms(self):
        """同步系统平台配置，保持使用 base_url 作为唯一索引"""
        with self.Session() as session:
            config_base_urls = {cfg["base_url"] for cfg in DEFAULT_PLATFORM_CONFIGS.values()}  
            all_sys_platforms = session.query(LLMPlatform).filter_by(is_sys=1).all()   
            
            for plat in all_sys_platforms:
                if plat.base_url not in config_base_urls:
                    print(f"删除已移除的系统平台: {plat.name} ({plat.base_url})")
                    session.delete(plat)
            
            session.flush()
            
            for name, cfg in DEFAULT_PLATFORM_CONFIGS.items():
                base_url = cfg["base_url"]
                plat = session.query(LLMPlatform).filter_by(base_url=base_url, is_sys=1).first()
                if not plat:
                    plat = LLMPlatform(
                        name=name,
                        base_url=base_url,
                        api_key=None,
                        user_id=SYSTEM_USER_ID,
                        is_sys=1,
                    )
                    session.add(plat)
                    session.flush()
                    print(f"添加新系统平台: {name}")
                else:
                    if plat.name != name:
                        print(f"恢复系统平台名称: {plat.name} -> {name}")
                    plat.name = name
                    plat.api_key = None 
                
                # 同步模型
                existing_models = {m.display_name: m for m in plat.models}
                for display_name, model_config in cfg.get("models", {}).items():
                    if isinstance(model_config, str):
                        model_name = model_config
                        extra_body = None
                    else:
                        model_name = model_config.get("model_name")
                        extra_body = model_config.get("extra_body")

                    extra_body_json = json.dumps(extra_body) if extra_body else None

                    if display_name in existing_models:
                        model_to_update = existing_models[display_name]
                        if model_to_update.model_name != model_name:
                            model_to_update.model_name = model_name
                        if model_to_update.extra_body != extra_body_json:
                            model_to_update.extra_body = extra_body_json
                        del existing_models[display_name]
                    else:
                        new_model = LLModels(
                            platform_id=plat.id,
                            model_name=model_name,
                            display_name=display_name,
                            extra_body=extra_body_json,
                        )
                        session.add(new_model)
                
                for model_to_delete in existing_models.values():
                    session.delete(model_to_delete)

            session.commit()
            with self._cache_lock:
                self._sys_platforms_cache = None

    def _get_sys_config(self, session):
        if self._sys_platforms_cache is None:
            with self._cache_lock:
                if self._sys_platforms_cache is None:
                    self._sys_platforms_cache = (
                        session.query(LLMPlatform)
                        .options(selectinload(LLMPlatform.models))
                        .filter_by(is_sys=1)
                        .all()
                    )

    def _ensure_mutable(self):
        if self.use_sys_llm_config:
            raise ValueError("当前处于 USE_SYS_LLM_CONFIG 模式，请直接修改 DEFAULT_PLATFORM_CONFIGS 或环境变量。")

    @staticmethod
    def _bool_to_int(value: bool) -> int:
        return 1 if value else 0
    
    @staticmethod
    def _int_to_bool(value: int) -> bool:
        return bool(value)

    @staticmethod
    def _apply_model_params(model_obj: 'LLModels', kwargs: Dict[str, Any]) -> Dict[str, Any]:
        if model_obj and model_obj.extra_body:
            try:
                model_extra_params = json.loads(model_obj.extra_body)
                if model_extra_params:
                    model_kwargs = kwargs.get("model_kwargs", {})
                    existing_extra_body = kwargs.get("extra_body", model_kwargs.get("extra_body", {}))
                    merged_extra_body = {**existing_extra_body, **model_extra_params}
                    kwargs["extra_body"] = merged_extra_body
            except json.JSONDecodeError:
                pass
        return kwargs

    @staticmethod
    def _normalize_usage_key(usage_key: Optional[str]) -> str:
        if usage_key is None:
            return DEFAULT_USAGE_KEY
        normalized = str(usage_key).strip().lower()
        return normalized or DEFAULT_USAGE_KEY

    def _get_usage_slot(self, session, user_id: str, usage_key: str) -> Optional[UserModelUsage]:
        return (
            session.query(UserModelUsage)
            .filter_by(user_id=user_id, usage_key=usage_key)
            .first()
        )

    def _ensure_usage_slot(
        self,
        session,
        user_id: str,
        usage_key: str,
        usage_label: Optional[str] = None,
        platform_id: Optional[int] = None,
        model_id: Optional[int] = None,
    ) -> tuple:
        slot = self._get_usage_slot(session, user_id, usage_key)
        if slot:
            return slot, False

        if platform_id is None:
            platform_id = self._default_platform_id
        if model_id is None:
            model_id = self._default_model_id
        if platform_id is None or model_id is None:
            raise RuntimeError("默认平台或模型尚未初始化")

        label = usage_label or self._builtin_usage_map.get(usage_key, {}).get("label") or usage_key

        slot = UserModelUsage(
            user_id=user_id,
            usage_key=usage_key,
            usage_label=label,
            selected_platform_id=platform_id,
            selected_model_id=model_id,
        )
        session.add(slot)
        session.flush()
        return slot, True

    def _ensure_default_usage_slots(self, session, user_id: str) -> bool:
        created = False
        for slot_cfg in BUILTIN_USAGE_SLOTS:
            _, added = self._ensure_usage_slot(
                session,
                user_id,
                slot_cfg["key"],
                slot_cfg.get("label"),
            )
            created = created or added
        return created

    def _get_default_platform_api_key(self, platform_name: str = None, base_url: str = None) -> Optional[str]:
        return get_decrypted_api_key(platform_name, base_url)
    
    def _get_effective_api_key(self, session, user_id: str, platform: LLMPlatform) -> Optional[str]:
        api_key = None
        sec_mgr = SecurityManager.get_instance()
        
        if platform.is_sys:
            cred = session.query(LLMSysPlatformKey).filter_by(
                user_id=user_id, platform_id=platform.id
            ).first()
            
            if cred and cred.api_key:
                api_key = sec_mgr.decrypt(cred.api_key)
            
            if not api_key and (user_id == SYSTEM_USER_ID or LLM_AUTO_KEY):
                api_key = self._get_default_platform_api_key(platform_name=platform.name, base_url=platform.base_url)
        else:
            api_key = sec_mgr.decrypt(platform.api_key)
            if not api_key and user_id == SYSTEM_USER_ID:
                api_key = self._get_default_platform_api_key(platform_name=platform.name, base_url=platform.base_url)
        
        return api_key

    def ensure_user_has_config(self, session, user_id: str) -> UserModelUsage:
        """确保用户至少拥有内置用途槽位，并返回默认用途(main)槽位。"""
        user_id = str(user_id)

        if self._default_platform_id is None or self._default_model_id is None:
            raise RuntimeError("AIManager 未正确初始化，默认平台或模型 ID 缺失")

        created = self._ensure_default_usage_slots(session, user_id)
        main_slot = self._get_usage_slot(session, user_id, self._default_usage_key)
        if not main_slot:
            main_slot, added = self._ensure_usage_slot(session, user_id, self._default_usage_key)
            created = created or added

        if created:
            session.commit()

        return main_slot


class AIManager(
    AIManagerBase,
    AdminMixin,
    UserServicesMixin,
    LLMBuilderMixin,
    UsageServicesMixin,
):
    """
    AI 模型管理器
    
    集成 AdminMixin, UserServicesMixin, UsageServicesMixin, LLMBuilderMixin
    """
    
    def __init__(self, db_name: str = "llm_config.db"):
        super().__init__(db_name)
        self.initialize_defaults()
