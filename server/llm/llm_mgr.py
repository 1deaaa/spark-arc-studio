import os
import yaml
import re
import base64
import hashlib
import json
import threading
from cryptography.fernet import Fernet
from typing import Dict, Any, Optional, List, Tuple, Union
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from sqlalchemy import (
    create_engine,
    Column,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import (
    declarative_base,
    sessionmaker,
    relationship,
    selectinload,
)

# ---------------- 配置常量 ----------------

# 当 user_id = '-1' 时，代表系统运行于无用户/全局单用户模式，也称$系统模式$
# 这是一个虚拟的系统用户，从环境变量获取apikey，不需要用户自己设置apikey
SYSTEM_USER_ID = "-1"

# 如果为True 则当用户无apikey时 将尝试自动获取服务器apikey密钥
LLM_AUTO_KEY = True 
# 如果为True 则所有用户均使用系统平台配置 不能创建自己的平台和模型
USE_SYS_LLM_CONFIG = True 

DEFAULT_USAGE_KEY = "main"
BUILTIN_USAGE_SLOTS = [
    {"key": DEFAULT_USAGE_KEY, "label": "主模型"},
    {"key": "fast", "label": "快速模型"},
    {"key": "reason", "label": "推理模型"},
]

# ---------------- 安全与配置管理 ----------------

class SecurityManager:
    _instance = None
    _fernet = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        if SecurityManager._instance is not None:
             # 防止重复初始化，虽然单例模式主要靠 get_instance 保证
            pass

        key = os.environ.get("LLM_KEY")
        
        # 兜底策略: (Windows) 尝试读取注册表
        if not key and os.name == 'nt':
            key = self.get_win_registry_key()

        if not key:
            if os.name != 'nt':
                print("⚠️ 警告: 未设置环境变量 LLM_KEY。如果您刚刚设置了环境变量，请尝试重启终端。")
            else:
                print("⚠️ 警告: 未设置环境变量 LLM_KEY，将无法解密配置文件中的敏感信息。")
            self._fernet = None
        else:
            if "LLM_KEY" not in os.environ:
                os.environ["LLM_KEY"] = key

            digest = hashlib.sha256(key.encode()).digest()
            fernet_key = base64.urlsafe_b64encode(digest)
            try:
                self._fernet = Fernet(fernet_key)
            except Exception as e:
                print(f"❌ 初始化加密组件失败: {e}")
                self._fernet = None

    @staticmethod
    def get_win_registry_key() -> Optional[str]:
        """从 Windows 注册表读取 LLM_KEY"""
        if os.name != 'nt':
            return None
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as reg_key:
                reg_val, _ = winreg.QueryValueEx(reg_key, "LLM_KEY")
                return str(reg_val) if reg_val else None
        except Exception:
            return None
            
    def encrypt(self, text: str) -> str:
        if not text: return text
        if not self._fernet:
            raise ValueError("未设置 LLM_KEY，无法执行加密操作")
        try:
            return "ENC:" + self._fernet.encrypt(text.encode()).decode()
        except Exception as e:
            print(f"❌ 加密失败: {e}")
            return text
        
    def decrypt(self, text: str) -> str:
        if not text or not isinstance(text, str): return text
        if not text.startswith("ENC:"): return text
        
        if not self._fernet:
            print("⚠️ 警告: 遇到加密数据但未设置 LLM_KEY，无法解密")
            return text 
            
        try:
            ciphertext = text[4:]
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except Exception as e:
            print(f"❌ 解密失败: {e}")
            return text

    def set_key(self, key: str):
        """运行时更新密钥"""
        if not key:
            self._fernet = None
            return
        
        digest = hashlib.sha256(key.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(digest)
        try:
            self._fernet = Fernet(fernet_key)
            os.environ["LLM_KEY"] = key
        except Exception as e:
            print(f"❌ SecurityManager: 密钥更新失败: {e}")
            self._fernet = None


def load_default_platform_configs() -> Dict[str, Any]:
    """从 YAML 文件加载并解析平台配置"""
    config_path = os.path.join(os.path.dirname(__file__), "llm_mgr_cfg.yaml")
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"LLM_MGR:预设平台配置文件 '{config_path}' 不存在，请手动创建 llm_mgr_cfg.yaml")
        
    with open(config_path, "r", encoding="utf-8") as f:
        configs = yaml.safe_load(f)

    sec_mgr = SecurityManager.get_instance()
    placeholder_re = re.compile(r"^\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}$")
    
    for name, cfg in configs.items():
        api_val = cfg.get("api_key")
        if not isinstance(api_val, str) or api_val.strip() == "":
            cfg["api_key"] = None
            continue

        api_val = api_val.strip()
        # 情况1: 已加密值
        if api_val.startswith("ENC:"):
            cfg["api_key"] = sec_mgr.decrypt(api_val)
            continue

        # 情况2: 占位符 {ENV_VAR}
        m = placeholder_re.match(api_val)
        if m:
            env_name = m.group(1)
            env_val = os.environ.get(env_name)
            if env_val:
                if env_val.startswith("ENC:"):
                    cfg["api_key"] = sec_mgr.decrypt(env_val)
                else:
                    cfg["api_key"] = env_val
            else:
                cfg["api_key"] = None
            continue

        # 情况3: 纯明文
        cfg["api_key"] = api_val

    return configs


def _ensure_env_setup():
    """在加载配置前检查环境"""
    # GUI/配置工具启动时允许缺少 LLM_KEY：否则会出现“用于配置密钥的工具本身无法启动”的循环依赖
    # 由 llm_mgr_cfg_gui.py 在 import 前设置该临时环境变量
    allow_no_key = str(os.environ.get("LLM_MGR_ALLOW_NO_KEY", "")).strip().lower() in ("1", "true", "yes")

    key = os.environ.get("LLM_KEY")
    if not key and os.name == 'nt':
        key = SecurityManager.get_win_registry_key()
        if key:
            os.environ["LLM_KEY"] = key
            
    if not key:
        if allow_no_key:
            # 仅提示，不中断 import；后续在需要 encrypt 时仍会抛错
            print("⚠️ 正在配置中......")
            return
        gui_path = os.path.join(os.path.dirname(__file__), "llm_mgr_cfg_gui.py")
        if os.path.exists(gui_path):
            import sys
            print("\n" + "="*60)
            print("⚠️ 错误：未检测到环境变量 LLM_KEY。")
            print("这是用于加解密 系统以及用户自定义API密钥 的主密码，必须进行设置。")
            print("\n请运行以下命令来启动配置工具进行设置：")
            print(f"   python \"{os.path.normpath(gui_path)}\"")
            print("="*60 + "\n")
            raise ValueError("缺少用于加解密系统及用户密钥的 环境变量 LLM_KEY ，请运行llm_mgr_cfg_gui.py进行设置。")

_ensure_env_setup()
DEFAULT_PLATFORM_CONFIGS = load_default_platform_configs()

# ---------------- 工具函数 ----------------

def probe_platform_models(
    base_url: str,
    api_key: str,
    timeout: float = 8.0,
    raise_on_error: bool = False,
) -> List[Dict[str, Any]]:
    """探测 OpenAI 兼容平台的可用模型列表"""
    try:
        import requests
    except ImportError as e:
        msg = "缺少 requests 库，无法执行远程探测"
        if raise_on_error: raise ImportError(msg) from e
        print(f"[probe_platform_models] {msg}")
        return []
    
    if not base_url or not api_key:
        msg = "base_url 和 api_key 不能为空"
        if raise_on_error: raise ValueError(msg)
        print(f"[probe_platform_models] {msg}")
        return []
    
    url = base_url.rstrip("/")
    if not url.endswith("/models"):
        url = f"{url}/models" if url.endswith("/v1") else f"{url}/v1/models"

    headers = {"Authorization": f"Bearer {api_key}"}
    
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 401:
            if raise_on_error: raise PermissionError("鉴权失败 (401)")
            return []
        
        if not resp.ok:
            if raise_on_error: raise RuntimeError(f"HTTP {resp.status_code}")
            return []
        
        js = resp.json()
        items = js.get('data') if isinstance(js, dict) else None
        if not isinstance(items, list):
            return []
        
        out: List[Dict[str, Any]] = []
        for it in items:
            if isinstance(it, dict) and 'id' in it:
                out.append({'id': it['id'], 'raw': it})
        return out
        
    except Exception as e:
        msg = f"探测失败: {e}"
        print(f"[probe_platform_models] {msg}")
        if raise_on_error: raise
        return []

# ---------------- 数据库模型 ----------------

Base = declarative_base()

class LLMPlatform(Base):
    __tablename__ = "llm_platforms"
    id = Column(Integer, primary_key=True)
    name = Column(String(80), default="未命名平台", index=True)
    user_id = Column(String(255), nullable=True, index=True)
    base_url = Column(String(255), nullable=False)
    api_key = Column(String(512), nullable=True)
    is_sys = Column(Integer, default=0) 
    hide = Column(Integer, default=0) 
    models = relationship("LLModels", backref="platform", cascade="all, delete-orphan")


class LLMSysPlatformKey(Base):
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
    hide = Column(Integer, default=0)
    platform = relationship("LLMPlatform", backref="sys_keys")


class LLModels(Base):
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


class UserModelUsage(Base):
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


# ---------------- 核心管理器 ----------------

class AIManager:
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
        self.initialize_defaults()

    def initialize_defaults(self):
        """同步默认平台并初始化默认ID"""
        self._sync_default_platforms()
        
        with self.Session() as session:
            default_platform_name = next(iter(DEFAULT_PLATFORM_CONFIGS))
            default_platform_config = DEFAULT_PLATFORM_CONFIGS[default_platform_name]
            default_model_display_name = next(iter(default_platform_config["models"]))
            
            # 这里可能会有问题：如果 sync 时平台名字被改了（因为 base_url 匹配），名字可能不匹配
            # 但既然 sync 逻辑强制恢复名字，应该没问题
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
    ) -> tuple[UserModelUsage, bool]:
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
        for slot in slots:
            try:
                # 优化：传入已加载的对象
                resolved = self._resolve_user_choice(
                    session,
                    user_id,
                    slot.selected_platform_id,
                    slot.selected_model_id,
                    usage_slot=slot,
                    raise_on_missing_key=False,
                    platform_obj=slot.platform,
                    model_obj=slot.model
                )
                payload = self._build_usage_payload(resolved, slot)
                if not resolved.get("api_key"):
                    payload["missing_key"] = True
                    payload["error"] = "API Key 未配置"
                details.append(payload)
            except ValueError as e:
                details.append({
                    "usage_key": slot.usage_key,
                    "usage_label": slot.usage_label,
                    "error": str(e),
                    "missing_key": True,
                    "platform": "Unknown",
                    "model_display_name": "Unknown",
                    "api_key_set": False,
                })
        return details

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
            if session.query(LLMPlatform).filter_by(base_url=base_url, is_sys=1).first():
                raise ValueError("该 base_url 对应的系统平台已存在")
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
            
            if session.query(LLModels).filter_by(platform_id=plat.id, model_name=model_name).first():
                raise ValueError(f"模型ID '{model_name}' 已存在于该平台")
            
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

    def _collect_platform_views(self, session, user_id: str) -> List[Dict[str, Any]]:
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
                }
                for view in views
                for model in view["models"]
            ]
            return items
                
    def ensure_user_has_config(self, session, user_id: str) -> UserModelUsage:
        """确保用户至少拥有内置用途槽位，并返回默认用途(main)槽位。"""
        user_id = str(user_id)

        if self._default_platform_id is None or self._default_model_id is None:
            raise RuntimeError("AIManager 未正确初始化，默认平台或模型 ID 缺失")

        created = self._ensure_default_usage_slots(session, user_id)
        main_slot = self._get_usage_slot(session, user_id, self._default_usage_key)
        if not main_slot:
            # 理论上 _ensure_default_usage_slots 会创建 main；这里做一次兜底。
            main_slot, added = self._ensure_usage_slot(session, user_id, self._default_usage_key)
            created = created or added

        if created:
            session.commit()

        return main_slot

    def save_user_selection(
        self,
        user_id: str,
        platform_id: int,
        model_id: int,
        usage_key: Optional[str] = None,
    ) -> bool:
        normalized_usage = self._normalize_usage_key(usage_key) if usage_key is not None else self._default_usage_key

        with self.Session() as session:
            self.ensure_user_has_config(session, user_id)
            usage_slot = self._get_usage_slot(session, user_id, normalized_usage)
            if not usage_slot:
                raise ValueError(f"未找到用途 '{normalized_usage}'，请先创建选中模型")

            self._resolve_user_choice(
                session,
                user_id,
                platform_id,
                model_id,
                auto_fix=False,
            )

            usage_slot.selected_platform_id = platform_id
            usage_slot.selected_model_id = model_id

            session.commit()
            return True

    def create_user_usage_slot(
        self,
        user_id: str,
        usage_key: str,
        usage_label: Optional[str] = None,
        platform_id: Optional[int] = None,
        model_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        if not usage_key:
            raise ValueError("usage_key 不能为空")

        normalized_usage = self._normalize_usage_key(usage_key)
        label = (usage_label or usage_key).strip() or usage_key

        with self.Session() as session:
            user_id = str(user_id)
            main_slot = self.ensure_user_has_config(session, user_id)

            if self._get_usage_slot(session, user_id, normalized_usage):
                raise ValueError(f"用途 '{normalized_usage}' 已存在")

            if (platform_id is None) ^ (model_id is None):
                raise ValueError("platform_id 与 model_id 需要同时提供或同时省略")

            if platform_id is None:
                platform_id = main_slot.selected_platform_id
                model_id = main_slot.selected_model_id
            else:
                self._resolve_user_choice(
                    session,
                    user_id,
                    platform_id,
                    model_id,
                    auto_fix=False,
                )

            slot, _ = self._ensure_usage_slot(
                session,
                user_id,
                normalized_usage,
                usage_label=label,
                platform_id=platform_id,
                model_id=model_id,
            )

            resolved = self._resolve_user_choice(
                session,
                user_id,
                slot.selected_platform_id,
                slot.selected_model_id,
                usage_slot=slot,
            )

            session.commit()
            return self._build_usage_payload(resolved, slot)

    def rename_user_usage_slot(self, user_id: str, usage_key: str, new_usage_key: Optional[str] = None, new_label: Optional[str] = None) -> Dict[str, Any]:
        if not usage_key:
            raise ValueError("usage_key 不能为空")

        normalized = self._normalize_usage_key(usage_key)
        new_normalized = self._normalize_usage_key(new_usage_key) if new_usage_key is not None else None

        with self.Session() as session:
            slot = self._get_usage_slot(session, user_id, normalized)
            if not slot:
                raise ValueError(f"用途 '{normalized}' 不存在")

            if new_normalized and new_normalized != normalized:
                existing = self._get_usage_slot(session, user_id, new_normalized)
                if existing:
                    raise ValueError(f"用途 '{new_normalized}' 已存在，无法重命名")
                slot.usage_key = new_normalized

            if new_label is not None:
                slot.usage_label = new_label.strip() or slot.usage_label

            session.commit()

            resolved = self._resolve_user_choice(
                session,
                user_id,
                slot.selected_platform_id,
                slot.selected_model_id,
                usage_slot=slot,
            )
            return self._build_usage_payload(resolved, slot)

    def delete_user_usage_slot(self, user_id: str, usage_key: str) -> bool:
        if not usage_key:
            raise ValueError("usage_key 不能为空")

        normalized = self._normalize_usage_key(usage_key)

        if normalized in self._builtin_usage_map:
            raise ValueError(f"禁止删除内置用途 '{normalized}'")

        with self.Session() as session:
            slot = self._get_usage_slot(session, user_id, normalized)
            if not slot:
                raise ValueError(f"用途 '{normalized}' 不存在")

            session.delete(slot)
            session.commit()
            return True

    def list_user_usage_selections(self, user_id: str) -> List[Dict[str, Any]]:
        with self.Session() as session:
            user_id = str(user_id)
            self.ensure_user_has_config(session, user_id)
            details = self._collect_usage_payloads(session, user_id)
            session.commit()
            return details

    def update_platform_config(
        self, user_id: str, platform_id: int, api_key: str
    ) -> bool:
        encrypted_key = None
        if api_key:
            encrypted_key = SecurityManager.get_instance().encrypt(api_key)

        with self.Session() as session:
            target_plat = session.query(LLMPlatform).filter_by(id=platform_id).first()
            if not target_plat:
                raise ValueError("平台不存在")

            if target_plat.is_sys:
                cred = (
                    session.query(LLMSysPlatformKey)
                    .filter_by(user_id=user_id, platform_id=target_plat.id)
                    .first()
                )
                if not cred:
                    cred = LLMSysPlatformKey(
                        user_id=user_id,
                        platform_id=target_plat.id,
                    )
                    session.add(cred)
                cred.api_key = encrypted_key or None
                with self._cache_lock:
                    self._sys_platforms_cache = None
            elif target_plat.user_id == user_id:
                if self.use_sys_llm_config:
                    raise ValueError("当前处于系统配置模式，不支持修改用户私有平台")
                target_plat.api_key = encrypted_key
            else:
                raise ValueError("无权修改该平台")

            session.commit()
            return True

    def delete_platform(self, user_id: str, platform_id: int) -> bool:
        self._ensure_mutable()
        with self.Session() as session:
            plat = (
                session.query(LLMPlatform)
                .filter_by(id=platform_id, user_id=user_id, is_sys=0)
                .first()
            )
            if not plat:
                raise ValueError("平台不存在或无权删除")
            session.delete(plat)
            session.commit()
            return True

    def update_platform_details(self, user_id: str, platform_id: int, new_name: str, new_base_url: str) -> bool:
        self._ensure_mutable()
        if not new_name or not new_base_url:
            raise ValueError("平台名称和 Base URL 不能为空")
            
        with self.Session() as session:
            plat = session.query(LLMPlatform).filter_by(id=platform_id).first()
            if not plat:
                raise ValueError("平台不存在")
            
            if plat.is_sys:
                raise ValueError("系统平台不能被修改，请直接修改 DEFAULT_PLATFORM_CONFIGS")
            
            if plat.user_id != user_id:
                raise ValueError("无权修改该平台")
            
            if plat.name != new_name:
                if new_name in DEFAULT_PLATFORM_CONFIGS:
                    raise ValueError("新平台名称与系统平台冲突")
                if (
                    session.query(LLMPlatform)
                    .filter_by(name=new_name, user_id=user_id, is_sys=0)
                    .first()
                ):
                    raise ValueError("您已有同名平台")
            
            if plat.base_url != new_base_url:
                if session.query(LLMPlatform).filter_by(base_url=new_base_url, is_sys=1).first():
                    raise ValueError("该 Base URL 对应的系统平台已存在")
                if session.query(LLMPlatform).filter_by(base_url=new_base_url, user_id=user_id, is_sys=0).first():
                    raise ValueError("您已创建过使用该 Base URL 的平台")

            plat.name = new_name
            plat.base_url = new_base_url
            session.commit()
            return True

    def delete_model(self, user_id: str, model_id: int) -> bool:
        self._ensure_mutable()
        with self.Session() as session:
            model = (
                session.query(LLModels)
                .join(LLMPlatform, LLModels.platform_id == LLMPlatform.id)
                .filter(
                    LLModels.id == model_id,
                    LLMPlatform.user_id == user_id,
                    LLMPlatform.is_sys == 0,
                )
                .first()
            )
            if not model:
                raise ValueError("模型不存在或无权删除")
            session.delete(model)
            session.commit()
            return True

    def update_model(
        self,
        user_id: str,
        model_id: int,
        new_display_name: Optional[str] = None,
        new_extra_body: Optional[Dict[str, Any]] = None,
    ) -> bool:
        self._ensure_mutable()
        if not new_display_name and new_extra_body is None:
            raise ValueError("必须提供新的显示名称或新的 extra_body")

        with self.Session() as session:
            model = (
                session.query(LLModels)
                .join(LLMPlatform, LLModels.platform_id == LLMPlatform.id)
                .filter(
                    LLModels.id == model_id,
                    LLMPlatform.user_id == user_id,
                    LLMPlatform.is_sys == 0,
                )
                .first()
            )
            if not model:
                raise ValueError("模型不存在或无权修改")

            if new_display_name:
                user_platforms = session.query(LLMPlatform).filter_by(user_id=user_id, is_sys=0).all()
                user_platform_ids = [p.id for p in user_platforms]
                dup = session.query(LLModels).filter(
                    LLModels.platform_id.in_(user_platform_ids),
                    LLModels.display_name == new_display_name,
                    LLModels.id != model_id 
                ).first()
                
                if dup:
                    dup_plat = session.query(LLMPlatform).filter_by(id=dup.platform_id).first()
                    raise ValueError(f"模型显示名称 '{new_display_name}' 已存在于您的平台 '{dup_plat.name}'")
                
                model.display_name = new_display_name
            
            if new_extra_body is not None:
                model.extra_body = json.dumps(new_extra_body) if new_extra_body else None

            session.commit()
            return True

    def toggle_platform_visibility(self, user_id: str, platform_id: int, hide: bool) -> bool:
        with self.Session() as session:
            plat = session.query(LLMPlatform).filter_by(id=platform_id).first()
            if not plat:
                raise ValueError("平台不存在")
            
            if plat.is_sys:
                cred = (
                    session.query(LLMSysPlatformKey)
                    .filter_by(user_id=user_id, platform_id=platform_id)
                    .first()
                )
                if not cred:
                    cred = LLMSysPlatformKey(
                        user_id=user_id,
                        platform_id=platform_id,
                    )
                    session.add(cred)
                cred.hide = self._bool_to_int(hide)
                with self._cache_lock:
                    self._sys_platforms_cache = None
            else:
                if plat.user_id != user_id:
                    raise ValueError("无权修改该平台")
                plat.hide = self._bool_to_int(hide)
            
            session.commit()
            return True

    def _get_fallback_platform_model(self, session, user_id: str) -> tuple[int, int]:
        self._get_sys_config(session)
        sys_platforms = self._sys_platforms_cache
        
        for plat in sys_platforms:
            if not plat.models:
                continue
            api_key = self._get_effective_api_key(session, user_id, plat)
            if api_key:
                return plat.id, plat.models[0].id
        
        if sys_platforms and sys_platforms[0].models:
            return sys_platforms[0].id, sys_platforms[0].models[0].id
        
        raise ValueError("系统中没有可用的默认平台和模型，请检查系统配置")

    def _resolve_user_choice(
        self,
        session,
        user_id: str,
        platform_id: int,
        model_id: int,
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
        original_platform_id = platform_id
        original_model_id = model_id
        config_invalid = False
        
        # 1. 尝试获取模型对象
        if not model_obj:
            model_obj = session.query(LLModels).filter_by(id=model_id).first()
        elif model_obj.id != model_id:
            # 传入的对象ID不匹配，重新查询
            model_obj = session.query(LLModels).filter_by(id=model_id).first()

        if not model_obj:
            config_invalid = True
            if auto_fix:
                print(f"[AIManager] 用户 {user_id} 的模型ID '{model_id}' 不存在，尝试使用备用配置")
            else:
                raise ValueError(f"模型ID '{model_id}' 不存在")
        
        # 2. 验证模型归属
        if model_obj and model_obj.platform_id != platform_id:
            config_invalid = True
            if auto_fix:
                print(f"[AIManager] 用户 {user_id} 的模型ID '{model_id}' 不属于平台ID '{platform_id}'，尝试使用备用配置")
            else:
                raise ValueError(f"模型ID '{model_id}' 不属于平台ID '{platform_id}'")
        
        # 3. 尝试获取平台对象
        # 注意：先使用传入的 platform_obj（如果有），避免未定义局部变量 'plat'
        plat = platform_obj if platform_obj is not None else None
        if not plat or plat.id != platform_id:
            plat = session.query(LLMPlatform).filter_by(id=platform_id).first()

        if not plat:
            config_invalid = True
            if auto_fix:
                print(f"[AIManager] 用户 {user_id} 的平台ID '{platform_id}' 不存在，尝试使用备用配置")
            else:
                raise ValueError(f"平台ID '{platform_id}' 不存在")
        
        # 4. 验证权限
        if plat and not plat.is_sys and plat.user_id != user_id:
            config_invalid = True
            if auto_fix:
                print(f"[AIManager] 用户 {user_id} 无权访问平台ID '{platform_id}'，尝试使用备用配置")
            else:
                raise ValueError(f"无权访问平台ID '{platform_id}'")
        
        # 5. 自动修复
        if config_invalid and auto_fix:
            try:
                platform_id, model_id = self._get_fallback_platform_model(session, user_id)

                if usage_slot:
                    usage_slot.selected_platform_id = platform_id
                    usage_slot.selected_model_id = model_id
                    print(f"[AIManager] 已同步用途 {usage_slot.usage_key} 的选中模型")
                
                plat = session.query(LLMPlatform).filter_by(id=platform_id).first()
                model_obj = session.query(LLModels).filter_by(id=model_id).first()
                
            except Exception as e:
                raise ValueError(f"用户配置无效且无法自动修复：{e}")
        
        api_key = self._get_effective_api_key(session, user_id, plat)
        
        if not api_key and raise_on_missing_key:
            if user_id == SYSTEM_USER_ID:
                raise ValueError(
                    f"平台 '{plat.name}' 的 API Key 未配置（系统模式）。\n"
                    f"请运行 llm_mgr_cfg_gui.py 配置该平台的 API Key。"
                )
            else:
                raise ValueError(
                    f"平台 '{plat.name}' 的 API Key 未配置。\n"
                    f"请在 AI 设置中为该平台配置您的 API Key。"
                )
        
        return {
            "platform": plat,
            "model": model_obj,
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
    ) -> BaseChatModel:
        """
        获取并返回一个为指定用户准备的 LLM 客户端实例（ChatOpenAI）。

        参数优先级：
        1. agent_name: 业务首选。从数据库查询该 Agent 的绑定配置。
        2. platform_id & model_id: 直接指定特定的平台和模型 ID。
        3. usage_key: 明确指定用途槽位（如 'main', 'fast'）。
        4. 默认值: 如果以上均未提供，使用 'main' 用途。
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

            if 'streaming' not in kwargs:
                kwargs['streaming'] = True
            
            return ChatOpenAI(
                base_url=base_url,
                api_key=api_key,
                model_name=model_obj.model_name,
                **kwargs,
            )

    def get_user_selection_detail(self, user_id: str, usage_key: Optional[str] = None) -> Dict[str, Any]:
        normalized_usage = self._normalize_usage_key(usage_key) if usage_key is not None else self._default_usage_key
        user_id = str(user_id)

        with self.Session() as session:
            self.ensure_user_has_config(session, user_id)
            usage_slot = self._get_usage_slot(session, user_id, normalized_usage)
            if not usage_slot:
                raise ValueError(f"未找到用途 '{normalized_usage}' 的模型配置")

            try:
                # 这里我们不传预加载对象，因为是单条查询，开销可控
                resolved = self._resolve_user_choice(
                    session,
                    user_id,
                    usage_slot.selected_platform_id,
                    usage_slot.selected_model_id,
                    usage_slot=usage_slot,
                    raise_on_missing_key=False,
                )
                current_detail = self._build_usage_payload(resolved, usage_slot)
                if not resolved.get("api_key"):
                    current_detail["missing_key"] = True
                    current_detail["error"] = "API Key 未配置"
            except ValueError as e:
                current_detail = {
                    "usage_key": usage_slot.usage_key,
                    "usage_label": usage_slot.usage_label,
                    "error": str(e),
                    "missing_key": True,
                    "platform": "Unknown",
                    "model_display_name": "Unknown",
                    "api_key_set": False,
                }

            usage_details = self._collect_usage_payloads(session, user_id)

            session.commit()

            current_detail["usage_selections"] = usage_details
            return current_detail

    def get_spec_sys_llm(
        self,
        platform_name: str,
        model_display_name: str,
        user_id: Optional[str] = None,
        **kwargs: Any
    ) -> BaseChatModel:
        """
        获取特定的系统预设模型。
        注意：现在支持传入 user_id 以便使用用户自定义的 API Key 覆盖。
        """
        effective_user_id = user_id if user_id is not None else SYSTEM_USER_ID
        
        with self.Session() as session:
            # 查找对应的系统平台
            plat = session.query(LLMPlatform).filter_by(name=platform_name, is_sys=1).first()
            if not plat:
                raise ValueError(f"系统平台 '{platform_name}' 不存在")
            
            # 查找对应的模型
            model_obj = session.query(LLModels).filter_by(platform_id=plat.id, display_name=model_display_name).first()
            if not model_obj:
                raise ValueError(f"平台 '{platform_name}' 下不存在模型 '{model_display_name}'")
            
            # 利用统一的解析逻辑获取 API Key（处理用户覆盖）
            resolved = self._resolve_user_choice(
                session,
                effective_user_id,
                plat.id,
                model_obj.id,
            )
            
            api_key = resolved["api_key"]
            base_url = resolved["base_url"]
            
            kwargs = self._apply_model_params(model_obj, kwargs)
            if 'streaming' not in kwargs:
                kwargs['streaming'] = True
                
            return ChatOpenAI(
                base_url=base_url,
                api_key=api_key,
                model_name=model_obj.model_name,
                **kwargs,
            )

    # --- Agent 绑定管理 ---

    def get_agent_bindings(self, user_id: str) -> List[Dict[str, Any]]:
        with self.Session() as session:
            bindings = session.query(AgentModelBinding).filter_by(user_id=user_id).all()
            return [
                {
                    "agent_name": b.agent_name,
                    "target_type": b.target_type,
                    "usage_key": b.usage_key,
                    "platform_id": b.platform_id,
                    "model_id": b.model_id
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
        with self.Session() as session:
            binding = session.query(AgentModelBinding).filter_by(
                user_id=user_id, agent_name=agent_name
            ).first()
            if binding:
                session.delete(binding)
                session.commit()
                return True
            return False


def get_decrypted_api_key(platform_name: str = None, base_url: str = None) -> Optional[str]:
    """
    获取系统平台配置中的 API Key（已解密）。
    支持通过 平台名称 或 Base URL 查找。
    供外部工具或 Agent 脚本直接获取特定平台的 Key，也供 AIManager 内部使用。
    """
    # 优先匹配 Base URL (因为 URL 更具体)
    if base_url:
        for cfg in DEFAULT_PLATFORM_CONFIGS.values():
            if cfg.get("base_url") == base_url:
                return cfg.get("api_key")
    
    # 其次匹配名称
    if platform_name:
        cfg = DEFAULT_PLATFORM_CONFIGS.get(platform_name)
        if cfg:
            return cfg.get("api_key")
            
    return None


LLM_Manager = AIManager()

def init_default_llm():
    print("正在执行 AI 管理器的启动初始化...")
    LLM_Manager.initialize_defaults()
    print("AI 管理器初始化完成。")
