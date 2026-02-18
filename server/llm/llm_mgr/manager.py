"""
AIManager 核心实现
集成所有管理功能模块
"""

import os
import json
import threading
import time
from typing import Dict, Any, Optional, List

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, selectinload

from .models import (
    Base, LLMPlatform, LLModels, LLMSysPlatformKey,
    UserModelUsage, AgentModelBinding, ModelUsageStats, UserEmbeddingSelection
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
from .utils import probe_platform_models, test_platform_chat, stream_speed_test, test_platform_embedding


class AIManagerBase:
    """AIManager 基础类：数据库连接和初始化"""
    
    def __init__(self, db_name: str = "llm_config.db"):
        base_dir = os.path.abspath(os.path.dirname(__file__))
        db_path = os.path.join(base_dir, db_name)
        db_url = f"sqlite:///{db_path}"
        self.engine = create_engine(db_url)
        # 注意：表创建现由 Alembic 迁移管理
        # 首次部署时运行: cd server && alembic upgrade head -x db=llm
        # 保留 create_all 以确保向后兼容（无 Alembic 环境时自动创建表）
        # [FIX] 在 Alembic 运行时调用的 import 链中会导致死锁/占用，故注释掉。
        # Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        self._sys_platforms_cache = None 
        self._cache_lock = threading.Lock()
        self._sys_platforms_cache_at = 0.0
        self._sys_platforms_cache_ttl = float(os.getenv("LLM_SYS_PLATFORM_CACHE_TTL", "5"))
        self.use_sys_llm_config = USE_SYS_LLM_CONFIG
        self.llm_auto_key = LLM_AUTO_KEY
        self._default_platform_id = None
        self._default_model_id = None
        self._builtin_usage_map = {slot["key"]: slot for slot in BUILTIN_USAGE_SLOTS}
        self._default_usage_key = DEFAULT_USAGE_KEY
        
        self.state_file = os.path.join(base_dir, "llm_mgr_state.json")
        self._load_state()

    def _load_state(self):
        """加载运行时状态"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    # 仅覆盖允许动态修改的配置
                    if "use_sys_llm_config" in state:
                        self.use_sys_llm_config = state["use_sys_llm_config"]
                    if "llm_auto_key" in state:
                        self.llm_auto_key = state["llm_auto_key"]
            except Exception as e:
                print(f"加载状态失败: {e}")

    def _save_state(self):
        """保存运行时状态"""
        try:
            state = {
                "use_sys_llm_config": self.use_sys_llm_config,
                "llm_auto_key": self.llm_auto_key
            }
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            print(f"保存状态失败: {e}")

    def initialize_defaults(self):
        """同步默认平台并初始化默认ID"""
        self._sync_default_platforms()
        
        with self.Session() as session:
            default_platform_name = next(iter(DEFAULT_PLATFORM_CONFIGS))
            default_platform_config = DEFAULT_PLATFORM_CONFIGS[default_platform_name]
            default_model_display_name = None
            for display_name, model_cfg in default_platform_config.get("models", {}).items():
                if isinstance(model_cfg, dict) and model_cfg.get("is_embedding"):
                    continue
                default_model_display_name = display_name
                break
            if not default_model_display_name:
                raise ValueError("默认平台未配置可用的 LLM 模型")
            
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

    def _sync_default_platforms(self, force_reset: bool = False):
        """
        同步系统平台配置（仅初始化模式）
        
        ⚠️ 数据源说明：
        - YAML 文件 (llm_mgr_cfg.yaml): 初始化模板，便于配置分享和版本控制
        - 数据库 (llm_config.db): 运行时权威数据源 (Authority)，修改即时生效。
        
        同步策略 (三种触发时机):
        1. 首次启动 (First Initialization):
           - 触发：数据库为空。
           - 行为：YAML 配置完整初始化到数据库。
        
        2. 增量同步 (Incremental Sync):
           - 触发：后续启动 (默认)。
           - 行为：仅添加 YAML 中新增的平台和模型，**不覆盖、不删除**数据库中已有的配置。
           - 目的：保护管理员在数据库模式下所做的自定义修改。
           
        3. 强制重置 (Force Reset):
           - 触发：GUI "从 YAML 重置" 或 API 调用。
           - 行为：以 YAML 为准覆盖数据库（保留用户 API Key）。
        
        参数:
            force_reset: 是否强制从 YAML 重置（会覆盖数据库中的所有系统平台配置）
        """
        def _encrypt_if_possible(value: Optional[str]) -> Optional[str]:
            if not value:
                return None
            try:
                return SecurityManager.get_instance().encrypt(value)
            except Exception:
                return None

        with self.Session() as session:
            config_base_urls = {cfg["base_url"] for cfg in DEFAULT_PLATFORM_CONFIGS.values() if isinstance(cfg, dict) and "base_url" in cfg}
            all_sys_platforms = session.query(LLMPlatform).filter_by(is_sys=1).all()
            # 已被管理员禁用的平台 base_url 集合（增量同步时跳过）
            disabled_base_urls = {p.base_url for p in all_sys_platforms if p.disable}

            # 检查是否为首次初始化（数据库中没有任何系统平台）
            is_first_init = len(all_sys_platforms) == 0

            if force_reset:
                # 强制重置模式：禁用所有不在 YAML 中的平台（软禁用，不硬删除）
                for plat in all_sys_platforms:
                    if plat.base_url not in config_base_urls:
                        print(f"[YAML重置] 禁用已移除的系统平台: {plat.name} ({plat.base_url})")
                        plat.disable = 1
                session.flush()
            
            # 已存在的平台 base_url 集合
            existing_base_urls = {p.base_url for p in all_sys_platforms}
            
            for name, cfg in DEFAULT_PLATFORM_CONFIGS.items():
                if not isinstance(cfg, dict) or "base_url" not in cfg:
                    continue
                base_url = cfg["base_url"]
                plat = session.query(LLMPlatform).filter_by(base_url=base_url, is_sys=1).first()
                
                if not plat and base_url not in disabled_base_urls:
                    # 新平台：添加到数据库（跳过已被管理员禁用的）
                    api_key_plain = cfg.get("api_key")
                    encrypted_key = _encrypt_if_possible(api_key_plain)
                    plat = LLMPlatform(
                        name=name,
                        base_url=base_url,
                        api_key=encrypted_key,  # YAML 中若有密钥则加密写入
                        user_id=SYSTEM_USER_ID,
                        is_sys=1,
                    )
                    session.add(plat)
                    session.flush()
                    print(f"[初始化] 添加新系统平台: {name}")
                    
                    # 新平台：添加所有模型
                    for display_name, model_config in cfg.get("models", {}).items():
                        if isinstance(model_config, str):
                            model_name = model_config
                            extra_body = None
                            temperature = None
                            is_embedding = 0
                        else:
                            model_name = model_config.get("model_name")
                            extra_body = model_config.get("extra_body")
                            temperature = model_config.get("temperature")
                            is_embedding = 1 if model_config.get("is_embedding") else 0
                        
                        extra_body_json = json.dumps(extra_body) if extra_body else None
                        new_model = LLModels(
                            platform_id=plat.id,
                            model_name=model_name,
                            display_name=display_name,
                            extra_body=extra_body_json,
                            temperature=temperature,
                            is_embedding=is_embedding,
                        )
                        session.add(new_model)
                
                elif force_reset or is_first_init:
                    # 强制重置或首次初始化：更新平台名称和同步模型
                    if plat.name != name:
                        print(f"[YAML重置] 恢复系统平台名称: {plat.name} -> {name}")
                        plat.name = name

                    # 若 YAML 提供 API Key，则更新平台默认 Key（加密写入）
                    api_key_plain = cfg.get("api_key")
                    if api_key_plain:
                        encrypted_key = _encrypt_if_possible(api_key_plain)
                        if encrypted_key:
                            plat.api_key = encrypted_key
                    
                    # 同步模型（覆盖模式）
                    existing_models = {m.display_name: m for m in plat.models}
                    for display_name, model_config in cfg.get("models", {}).items():
                        if isinstance(model_config, str):
                            model_name = model_config
                            extra_body = None
                            temperature = None
                            is_embedding = 0
                        else:
                            model_name = model_config.get("model_name")
                            extra_body = model_config.get("extra_body")
                            temperature = model_config.get("temperature")
                            is_embedding = 1 if model_config.get("is_embedding") else 0

                        extra_body_json = json.dumps(extra_body) if extra_body else None

                        if display_name in existing_models:
                            model_to_update = existing_models[display_name]
                            if model_to_update.model_name != model_name:
                                model_to_update.model_name = model_name
                            if model_to_update.extra_body != extra_body_json:
                                model_to_update.extra_body = extra_body_json
                            if model_to_update.temperature != temperature:
                                model_to_update.temperature = temperature
                            if model_to_update.is_embedding != is_embedding:
                                model_to_update.is_embedding = is_embedding
                            del existing_models[display_name]
                        else:
                            new_model = LLModels(
                                platform_id=plat.id,
                                model_name=model_name,
                                display_name=display_name,
                                extra_body=extra_body_json,
                                temperature=temperature,
                                is_embedding=is_embedding,
                            )
                            session.add(new_model)
                    
                    # 删除 YAML 中已移除的模型
                    for model_to_delete in existing_models.values():
                        session.delete(model_to_delete)
                
                else:
                    # 正常启动模式：已存在的平台不做任何修改
                    # 仅添加 YAML 中新增的模型（不覆盖已有模型）
                    existing_model_names = {m.display_name for m in plat.models}
                    for display_name, model_config in cfg.get("models", {}).items():
                        if display_name not in existing_model_names:
                            if isinstance(model_config, str):
                                model_name = model_config
                                extra_body = None
                                temperature = None
                                is_embedding = 0
                            else:
                                model_name = model_config.get("model_name")
                                extra_body = model_config.get("extra_body")
                                temperature = model_config.get("temperature")
                                is_embedding = 1 if model_config.get("is_embedding") else 0
                            
                            extra_body_json = json.dumps(extra_body) if extra_body else None
                            new_model = LLModels(
                                platform_id=plat.id,
                                model_name=model_name,
                                display_name=display_name,
                                extra_body=extra_body_json,
                                temperature=temperature,
                                is_embedding=is_embedding,
                            )
                            session.add(new_model)
                            print(f"[增量同步] 平台 {name} 添加新模型: {display_name}")

            session.commit()
            self._invalidate_sys_platforms_cache()

    def _invalidate_sys_platforms_cache(self):
        with self._cache_lock:
            self._sys_platforms_cache = None
            self._sys_platforms_cache_at = 0.0

    def _is_sys_platforms_cache_expired(self) -> bool:
        if self._sys_platforms_cache is None:
            return True
        if self._sys_platforms_cache_ttl <= 0:
            return False
        return (time.time() - self._sys_platforms_cache_at) > self._sys_platforms_cache_ttl

    def admin_reload_from_yaml(self) -> bool:
        """
        管理员：从 YAML 文件强制重新加载系统平台配置
        
        ⚠️ 警告：此操作会覆盖数据库中的系统平台配置
        - 删除 YAML 中不存在的平台
        - 更新已存在平台的名称和模型
        - API Key 不受影响（YAML 中的 api_key 字段被忽略）
        """
        from .config import reload_default_platform_configs
        reload_default_platform_configs()
        self._sync_default_platforms(force_reset=True)
        return True

    def admin_export_to_yaml(self) -> str:
        """
        管理员：将数据库中的系统平台配置导出并覆盖 llm_mgr_cfg.yaml
        """
        import yaml
        import os
        from .models import LLMPlatform

        config_path = os.path.join(os.path.dirname(__file__), "llm_mgr_cfg.yaml")
        export_data = {}

        with self.Session() as session:
            platforms = (
                session.query(LLMPlatform)
                .options(selectinload(LLMPlatform.models))
                .filter_by(is_sys=1)
                .all()
            )

            for plat in platforms:
                if bool(plat.disable):
                    continue

                plat_config = {
                    "base_url": plat.base_url,
                    "models": {}
                }
                
                # 导出 API Key (如果存在且已加密，保持加密字符串)
                if plat.api_key:
                    plat_config["api_key"] = plat.api_key

                for model in plat.models:
                    if self._is_model_disabled(model):
                        continue
                    
                    if not model.extra_body and not model.is_embedding:
                        # 尝试使用简单形式： DisplayName: ModelID
                        plat_config["models"][model.display_name] = model.model_name
                    else:
                        entry = {"model_name": model.model_name}
                        if model.extra_body:
                            try:
                                entry["extra_body"] = json.loads(model.extra_body)
                            except:
                                pass
                        if model.temperature is not None:
                            entry["temperature"] = model.temperature
                        if model.is_embedding:
                            entry["is_embedding"] = True
                        
                        plat_config["models"][model.display_name] = entry

                export_data[plat.name] = plat_config

        # 写入文件
        # allow_unicode=True 确保中文正常显示
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(export_data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
            
        return config_path

    def _get_sys_config(self, session):
        if self._is_sys_platforms_cache_expired():
            with self._cache_lock:
                if self._is_sys_platforms_cache_expired():
                    self._sys_platforms_cache = (
                        session.query(LLMPlatform)
                        .options(selectinload(LLMPlatform.models))
                        .filter_by(is_sys=1)
                        .filter(LLMPlatform.disable == 0)
                        .order_by(LLMPlatform.sort_order)
                        .all()
                    )
                    self._sys_platforms_cache_at = time.time()

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
        if model_obj is not None and getattr(model_obj, "temperature", None) is not None and "temperature" not in kwargs:
            kwargs["temperature"] = float(model_obj.temperature)

        if model_obj and model_obj.extra_body:
            try:
                model_extra_params = json.loads(model_obj.extra_body)
                if model_extra_params:
                    model_kwargs = kwargs.get("model_kwargs", {})
                    existing_extra_body = kwargs.get("extra_body", model_kwargs.get("extra_body", {}))
                    merged_extra_body = {**existing_extra_body, **model_extra_params}
                    # ⚠️ 如果 extra_body 配置中错误包含了 streaming 字段，此处将其删除。
                    # 流式/非流式由调用方式（invoke/stream）自动决定，不应通过 extra_body 控制。
                    merged_extra_body.pop("streaming", None)
                    if merged_extra_body:
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
            
            if not api_key and (user_id == SYSTEM_USER_ID or self.llm_auto_key):
                api_key = self._get_default_platform_api_key(platform_name=platform.name, base_url=platform.base_url)
        else:
            api_key = sec_mgr.decrypt(platform.api_key)
            if not api_key and user_id == SYSTEM_USER_ID:
                api_key = self._get_default_platform_api_key(platform_name=platform.name, base_url=platform.base_url)
        
        return api_key

    def _is_platform_disabled(self, session, user_id: str, platform: LLMPlatform) -> bool:
        if platform.is_sys:
            cred = session.query(LLMSysPlatformKey).filter_by(
                user_id=user_id, platform_id=platform.id
            ).first()
            return bool(platform.disable) or bool(cred and cred.disable)
        return bool(platform.disable)

    def _is_model_disabled(self, model: Optional[LLModels]) -> bool:
        if not model:
            return True
        return bool(getattr(model, "disable", 0))

    def _set_model_disabled(self, model: LLModels, disabled: bool) -> None:
        model.disable = 1 if disabled else 0

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

            session.commit()

        return main_slot

    def proxy_list_models(self, user_id: str, platform_id: int) -> List[str]:
        """代理调用远程平台获取模型列表"""
        user_id = str(user_id)
        with self.Session() as session:
            plat = session.query(LLMPlatform).filter_by(id=platform_id).first()
            if not plat:
                raise ValueError("平台不存在")

            if self._is_platform_disabled(session, user_id, plat):
                raise ValueError("平台已禁用")
            
            # 权限检查：系统平台或者用户自己的平台
            if not plat.is_sys and plat.user_id != user_id:
                raise ValueError("无权访问此平台")
            
            api_key = self._get_effective_api_key(session, user_id, plat)
            base_url = plat.base_url
            
            if not api_key:
                raise ValueError(f"平台 {plat.name} 未配置 API Key")
        
        # 调用 utils 中的通用探测逻辑
        try:
            models_data = probe_platform_models(base_url, api_key, raise_on_error=True)
            return [m["id"] for m in models_data]
        except Exception as e:
            raise ValueError(f"获取模型列表失败: {e}")

    def proxy_test_chat(self, user_id: str, platform_id: int, model_name: str, extra_body_override: Dict[str, Any] = None) -> str:
        """测试模型连接 (发送简单的 Hello)"""
        user_id = str(user_id)
        extra_body = extra_body_override
        with self.Session() as session:
            plat = session.query(LLMPlatform).filter_by(id=platform_id).first()
            if not plat:
                raise ValueError("平台不存在")

            if self._is_platform_disabled(session, user_id, plat):
                raise ValueError("平台已禁用")
            
            if not plat.is_sys and plat.user_id != user_id:
                raise ValueError("无权访问此平台")
            
            # 如果没有覆盖，则尝试从数据库查找模型配置以获取 extra_body
            if extra_body is None:
                model_obj = session.query(LLModels).filter_by(platform_id=platform_id, model_name=model_name).first()
                if model_obj and model_obj.extra_body:
                    try:
                        extra_body = json.loads(model_obj.extra_body)
                    except:
                        pass

            api_key = self._get_effective_api_key(session, user_id, plat)
            base_url = plat.base_url
            
            if not api_key:
                raise ValueError(f"平台 {plat.name} 未配置 API Key")
        
        # 调用 utils 中的通用测试逻辑
        try:
            return test_platform_chat(base_url, api_key, model_name, extra_body=extra_body)
        except Exception as e:
            raise ValueError(f"测试失败: {e}")

    def proxy_speed_test(self, user_id: str, platform_id: int, model_name: str):
        """流式测速代理"""
        user_id = str(user_id)
        extra_body = None
        with self.Session() as session:
            plat = session.query(LLMPlatform).filter_by(id=platform_id).first()
            if not plat:
                raise ValueError("平台不存在")

            if self._is_platform_disabled(session, user_id, plat):
                raise ValueError("平台已禁用")
            
            if not plat.is_sys and plat.user_id != user_id:
                raise ValueError("无权访问此平台")

            # 尝试查找模型配置以获取 extra_body
            model_obj = session.query(LLModels).filter_by(platform_id=platform_id, model_name=model_name).first()
            if model_obj and model_obj.extra_body:
                try:
                    extra_body = json.loads(model_obj.extra_body)
                except:
                    pass
            
            api_key = self._get_effective_api_key(session, user_id, plat)
            base_url = plat.base_url
            
            if not api_key:
                raise ValueError(f"平台 {plat.name} 未配置 API Key")

        return stream_speed_test(base_url, api_key, model_name, extra_body=extra_body)

    def proxy_test_embedding(self, user_id: str, platform_id: int, model_name: str) -> Dict[str, Any]:
        """测试 Embedding 连接"""
        user_id = str(user_id)
        with self.Session() as session:
            plat = session.query(LLMPlatform).filter_by(id=platform_id).first()
            if not plat:
                raise ValueError("平台不存在")

            if self._is_platform_disabled(session, user_id, plat):
                raise ValueError("平台已禁用")

            if not plat.is_sys and plat.user_id != user_id:
                raise ValueError("无权访问此平台")

            api_key = self._get_effective_api_key(session, user_id, plat)
            base_url = plat.base_url

            if not api_key:
                raise ValueError(f"平台 {plat.name} 未配置 API Key")

        try:
            return test_platform_embedding(base_url, api_key, model_name)
        except Exception as e:
            raise ValueError(f"测试失败: {e}")

    def get_system_config(self) -> Dict[str, bool]:
        """获取系统级配置 (LLM_AUTO_KEY, USE_SYS_LLM_CONFIG)"""
        return {
            "llm_auto_key": self.llm_auto_key,
            "use_sys_llm_config": self.use_sys_llm_config
        }

    def set_system_config(self, use_sys_llm_config: bool = None, llm_auto_key: bool = None) -> bool:
        """设置系统级配置"""
        changed = False
        if use_sys_llm_config is not None:
            if self.use_sys_llm_config != use_sys_llm_config:
                self.use_sys_llm_config = use_sys_llm_config
                changed = True
        
        if llm_auto_key is not None:
            if self.llm_auto_key != llm_auto_key:
                self.llm_auto_key = llm_auto_key
                changed = True
        
        if changed:
            self._save_state()
            # Cache invalidation might be needed if behaviour depends on this flag heavily
            # accessing self.use_sys_llm_config is direct, so it should be fine.
        
        return True


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
        # ⚠️ 不要在这里调用 initialize_defaults()
        # 这会导致 Import 时建立 DB 连接，从而在启动迁移时造成 SQLite 死锁。
        # 请务必在 app.py 的 lifespan 中显式调用 LLM_Manager.initialize_defaults()
        # self.initialize_defaults()
