# 这是一个通用的大模型管理器，拥有一组内置的平台模型，支持三种使用情况
# 1.无用户/全局单用户模式 用于开发者为所有用户提供llm服务、私有系统或者开发调试
# 2.多用户固定平台模式 为保证模型质量 可以强制用户使用系统内置平台 不能创建自己的平台和模型 但是可以使用自己的apikey以节省成本
# 3.多用户自定义平台模式 用户可以自由拓展自己的平台
# 支持用户隐藏/显示平台以符合不同用户的需求
import os
import yaml
import re
import base64
import hashlib
from cryptography.fernet import Fernet
from typing import Dict, Any, Optional, List
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

# 当 user_id = '-1' 时，代表系统运行于无用户/全局单用户模式，也称$系统模式$
# 这是一个虚拟的系统用户，从环境变量获取apikey，不需要用户自己设置apikey
#⚠️当用户无apikey时 将尝试自动获取服务器apikey密钥
SYSTEM_USER_ID = "-1"

LLM_AUTO_KEY = True#如果为True 则当用户无apikey时 将尝试自动获取服务器apikey密钥 ⚠️所以如果不想给用户提供apikey 请保持此项为False
USE_SYS_LLM_CONFIG = True #如果为True 则所有用户均使用系统平台配置 不能创建自己的平台和模型

DEFAULT_USAGE_KEY = "main"
BUILTIN_USAGE_SLOTS = [
    {"key": DEFAULT_USAGE_KEY, "label": "主模型"},
    {"key": "fast", "label": "快速模型"},
    {"key": "reason", "label": "推理模型"},
]


class SecurityManager:
    _instance = None
    _fernet = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        key = os.environ.get("LLM_KEY")
        
        # 兜底策略: (Windows) 尝试读取注册表
        # 允许在不重启终端的情况下获取新设置的环境变量
        if not key and os.name == 'nt':
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as reg_key:
                    reg_val, _ = winreg.QueryValueEx(reg_key, "LLM_KEY")
                    if reg_val:
                        key = str(reg_val)
            except Exception:
                pass

        if not key:
            if os.name != 'nt':
                print("⚠️ 警告: 未设置环境变量 LLM_KEY。如果您刚刚设置了环境变量，请尝试重启终端。")
            else:
                print("⚠️ 警告: 未设置环境变量 LLM_KEY，将无法解密配置文件中的敏感信息。")
            self._fernet = None
        else:
            # 确保同步回环境变量，供后续子进程使用
            if "LLM_KEY" not in os.environ:
                os.environ["LLM_KEY"] = key

            # 使用 SHA256 生成 32 字节的 Key，并进行 urlsafe base64 编码以符合 Fernet 要求
            digest = hashlib.sha256(key.encode()).digest()
            fernet_key = base64.urlsafe_b64encode(digest)
            try:
                self._fernet = Fernet(fernet_key)
            except Exception as e:
                print(f"❌ 初始化加密组件失败: {e}")
                self._fernet = None
            
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
            # 同时更新环境变量，确保后续子进程或其他模块能读取
            os.environ["LLM_KEY"] = key
        except Exception as e:
            print(f"❌ SecurityManager: 密钥更新失败: {e}")
            self._fernet = None


def load_default_platform_configs() -> Dict[str, Any]:
    """从 YAML 文件加载并解析平台配置，自动处理所有环境变量"""
    config_path = os.path.join(os.path.dirname(__file__), "llm_mgr_cfg.yaml")
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"LLM_MGR:预设平台配置文件 '{config_path}' 不存在，请手动创建 llm_mgr_cfg.yaml")
        
    with open(config_path, "r", encoding="utf-8") as f:
        configs = yaml.safe_load(f)

    sec_mgr = SecurityManager.get_instance()

    # 统一处理所有配置项中的解密
    for name, cfg in configs.items():
        # api_key 处理
        if isinstance(cfg.get("api_key"), str):
            cfg["api_key"] = sec_mgr.decrypt(cfg["api_key"])
        else:
            cfg["api_key"] = None

    return configs


def _ensure_env_setup():
    """
    在加载配置前检查环境：
    1. 检查 LLM_KEY 是否存在
    2. 如果不存在且存在 GUI 工具，则启动 GUI 工具让用户设置
    """
    # 尝试获取 Key (包括从注册表)
    key = os.environ.get("LLM_KEY")
    if not key and os.name == 'nt':
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as reg_key:
                reg_val, _ = winreg.QueryValueEx(reg_key, "LLM_KEY")
                if reg_val:
                    key = str(reg_val)
                    os.environ["LLM_KEY"] = key
        except Exception:
            pass
            
    # 如果仍无 Key，且 GUI 存在，则启动 GUI
    if not key:
        gui_path = os.path.join(os.path.dirname(__file__), "llm_mgr_cfg_gui.py")
        if os.path.exists(gui_path):
            print("⚠️ 未检测到 LLM_KEY，正在启动配置工具...")
            import sys
            import subprocess
            
            env = os.environ.copy()
            server_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            if "PYTHONPATH" in env:
                env["PYTHONPATH"] = server_root + os.pathsep + env["PYTHONPATH"]
            else:
                env["PYTHONPATH"] = server_root
                
            try:
                subprocess.run([sys.executable, gui_path], env=env, check=True)
                
                # GUI 关闭后再次尝试读取 Key
                if os.name == 'nt':
                    import winreg
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as reg_key:
                        reg_val, _ = winreg.QueryValueEx(reg_key, "LLM_KEY")
                        if reg_val:
                            os.environ["LLM_KEY"] = str(reg_val)
                            print("✅ 已加载 LLM_KEY")
            except Exception as e:
                print(f"❌ 启动配置工具失败: {e}")


# 在加载默认配置前执行环境检查
_ensure_env_setup()

DEFAULT_PLATFORM_CONFIGS = load_default_platform_configs()


def probe_platform_models(
    base_url: str,
    api_key: str,
    timeout: float = 8.0,
    raise_on_error: bool = False,
) -> List[Dict[str, Any]]:
    """
    探测 OpenAI 兼容平台的可用模型列表（独立工具函数）
    
    Args:
        base_url: 平台的基础 URL（如 https://api.openai.com/v1）
        api_key: API 密钥
        timeout: 请求超时时间（秒）
        raise_on_error: 是否在出错时抛出异常
        
    Returns:
        模型列表，每个模型包含 'id' 和 'raw' 字段
        
    Example:
        >>> models = probe_platform_models("https://api.openai.com/v1", "sk-xxx")
        >>> for model in models:
        ...     print(model['id'])
    """
    try:
        import requests
    except ImportError as e:
        msg = "缺少 requests 库，无法执行远程探测"
        if raise_on_error:
            raise ImportError(msg) from e
        print(f"[probe_platform_models] {msg}")
        return []
    
    # 参数验证
    if not base_url:
        msg = "base_url 不能为空"
        if raise_on_error:
            raise ValueError(msg)
        print(f"[probe_platform_models] {msg}")
        return []
    if not api_key:
        msg = "api_key 不能为空"
        if raise_on_error:
            raise ValueError(msg)
        print(f"[probe_platform_models] {msg}")
        return []
    
    # 构建请求 URL
    url = base_url.rstrip("/")
    if not url.endswith("/models"):
        if url.endswith("/v1"):
            url = f"{url}/models"
        else:
            url = f"{url}/v1/models"

    headers = {"Authorization": f"Bearer {api_key}"}
    
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        
        # 处理鉴权失败
        if resp.status_code == 401:
            msg = "鉴权失败 (401)，请检查 API Key 是否正确"
            if raise_on_error:
                raise PermissionError(msg)
            print(f"[probe_platform_models] {msg}")
            return []
        
        # 处理其他 HTTP 错误
        if not resp.ok:
            msg = f"探测失败 (HTTP {resp.status_code}): {resp.text[:120]}"
            if raise_on_error:
                raise RuntimeError(msg)
            print(f"[probe_platform_models] {msg}")
            return []
        
        # 解析响应
        js = resp.json()
        items = js.get('data') if isinstance(js, dict) else None
        if not isinstance(items, list):
            msg = "响应格式错误：缺少 'data' 列表字段"
            if raise_on_error:
                raise ValueError(msg)
            print(f"[probe_platform_models] {msg}")
            return []
        
        # 提取模型 ID
        out: List[Dict[str, Any]] = []
        for it in items:
            if isinstance(it, dict) and 'id' in it:
                out.append({'id': it['id'], 'raw': it})
        return out
        
    except (requests.RequestException, ValueError) as e:
        # 网络错误或 JSON 解析错误
        msg = f"探测失败: {type(e).__name__}: {e}"
        if raise_on_error:
            raise RuntimeError(msg) from e
        print(f"[probe_platform_models] {msg}")
        return []
    except Exception as e:
        # 其他未预期的错误
        msg = f"探测时发生未预期的错误: {type(e).__name__}: {e}"
        print(f"[probe_platform_models] {msg}")
        if raise_on_error:
            raise
        return []


Base = declarative_base()


class LLMPlatform(Base):
    __tablename__ = "llm_platforms"
    id = Column(Integer, primary_key=True)
    name = Column(String(80), default="未命名平台", index=True)
    user_id = Column(String(255), nullable=True, index=True)
    base_url = Column(String(255), nullable=False)
    api_key = Column(String(512), nullable=True)  # 可为空，此时依赖环境变量
    is_sys = Column(Integer, default=0) # 是否为系统默认平台（用户不能操作 仅能由系统更新）
    hide = Column(Integer, default=0) # 是否隐藏（0=显示，1=隐藏）用户可控制在前台是否显示
    # 关系：平台 -> 模型
    models = relationship("LLModels", backref="platform", cascade="all, delete-orphan")


class LLMSysPlatformKey(Base):#存储系统内置平台下 用户自己的apikey 让所有用户可以共享系统平台并使用自己的key 
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
    hide = Column(Integer, default=0)  # 用户级别的隐藏控制（0=显示，1=隐藏）

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
    model_name = Column(
        String(120), nullable=False, index=True
    )  # 实际请求用的 model id
    display_name = Column(String(120), nullable=True)  # 展示名，可为空
    extra_body = Column(String(1024), nullable=True)  # 存储自定义参数的JSON字符串


class UserAIConfig(Base):
    __tablename__ = "user_ai_configs"
    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), unique=True, nullable=False, index=True)
    selected_platform_id = Column(
        Integer,
        ForeignKey("llm_platforms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    selected_model_id = Column(
        Integer,
        ForeignKey("llm_platform_models.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    platform = relationship("LLMPlatform")
    model = relationship("LLModels")


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
        ForeignKey("llm_platforms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    selected_model_id = Column(
        Integer,
        ForeignKey("llm_platform_models.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )




class AIManager:
    def __init__(self, db_name: str = "llm_config.db"):
        import threading
        # 数据库文件放在 server/ 根目录下，而不是 server/llm/ 下
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        db_path = os.path.join(base_dir, db_name)
        db_url = f"sqlite:///{db_path}"
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self._sys_platforms_cache = None # 用于缓存系统平台
        self._cache_lock = threading.Lock()  # 用于保护缓存的线程锁
        self.use_sys_llm_config = USE_SYS_LLM_CONFIG  # 从全局常量赋值
        # 初始化默认平台和模型ID，防止未初始化错误
        self._default_platform_id = None
        self._default_model_id = None
        self._builtin_usage_map = {slot["key"]: slot for slot in BUILTIN_USAGE_SLOTS}
        self._default_usage_key = DEFAULT_USAGE_KEY
        self.initialize_defaults()

    def initialize_defaults(self):
        """
        公共方法：执行默认平台模板与数据库的同步。
        这是一个幂等操作，可以在应用启动时安全调用。
        """
        self._sync_default_platforms()
        
        # 获取默认平台和模型的数据库ID
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
        
        # 确保系统用户有配置
        with self.Session() as session:
            self.ensure_user_has_config(session, SYSTEM_USER_ID)

    def _sync_default_platforms(self):
        """
        同步 DEFAULT_PLATFORM_CONFIGS 到数据库，作为系统平台模板 (is_sys=1)。
        这些模板的 api_key 字段将始终为 None。
        使用 base_url 作为系统平台的唯一标识，确保即使名称被修改也能正确同步。
        会删除配置中已移除的系统平台和模型。
        """
        with self.Session() as session:
            # 收集配置中所有的 base_url
            config_base_urls = {cfg["base_url"] for cfg in DEFAULT_PLATFORM_CONFIGS.values()}  
            # 获取数据库中所有的系统平台
            all_sys_platforms = session.query(LLMPlatform).filter_by(is_sys=1).all()   
            # 删除配置中已移除的系统平台
            for plat in all_sys_platforms:
                if plat.base_url not in config_base_urls:
                    print(f"删除已移除的系统平台: {plat.name} ({plat.base_url})")
                    session.delete(plat)
            
            session.flush()
            
            # 同步配置中的平台和模型
            for name, cfg in DEFAULT_PLATFORM_CONFIGS.items():
                base_url = cfg["base_url"]
                # 优先使用 base_url 来匹配系统平台，防止名称被重命名导致的问题
                plat = session.query(LLMPlatform).filter_by(base_url=base_url, is_sys=1).first()
                if not plat:
                    plat = LLMPlatform(
                        name=name,
                        base_url=base_url,
                        api_key=None,  # 系统模板不存储key
                        user_id=SYSTEM_USER_ID,
                        is_sys=1,
                    )
                    session.add(plat)
                    session.flush()
                    print(f"添加新系统平台: {name}")
                else:
                    # 强制恢复系统平台的标准名称，修复被重命名的情况
                    if plat.name != name:
                        print(f"恢复系统平台名称: {plat.name} -> {name}")
                    plat.name = name
                    plat.base_url = base_url
                    plat.api_key = None # 确保始终为None
                # 同步模型
                import json
                existing_models = {m.display_name: m for m in plat.models}
                for display_name, model_config in cfg.get("models", {}).items():
                    # 兼容两种模型配置格式:
                    # 1. 简化格式（字符串）："通义flash": "qwen-flash" (只包含 model_name，没有额外参数)
                    # 2. 完整格式（字典）："哈基米flash": {model_name: "...", extra_body: {...}} (包含 model_name 和可选的 extra_body)
                    if isinstance(model_config, str):
                        # 简化格式：只包含 model_name，没有额外参数
                        model_name = model_config
                        extra_body = None
                    else:
                        # 完整格式：包含 model_name 和可选的 extra_body（自定义参数）
                        model_name = model_config.get("model_name")
                        extra_body = model_config.get("extra_body")

                    extra_body_json = json.dumps(extra_body) if extra_body else None

                    if display_name in existing_models:
                        # 更新已存在的模型
                        model_to_update = existing_models[display_name]
                        if model_to_update.model_name != model_name:
                            print(f"更新模型 {display_name}: {model_to_update.model_name} -> {model_name}")
                            model_to_update.model_name = model_name
                        if model_to_update.extra_body != extra_body_json:
                            print(f"更新模型 {display_name} 的 extra_body")
                            model_to_update.extra_body = extra_body_json
                        del existing_models[display_name]
                    else:
                        # 添加新模型
                        print(f"添加新模型: {display_name} ({model_name}) 到平台 {name}")
                        new_model = LLModels(
                            platform_id=plat.id,
                            model_name=model_name,
                            display_name=display_name,
                            extra_body=extra_body_json,
                        )
                        session.add(new_model)
                
                # 删除配置中已移除的模型
                for model_to_delete in existing_models.values():
                    print(f"删除已移除的模型: {model_to_delete.display_name} ({model_to_delete.model_name}) 从平台 {name}")
                    session.delete(model_to_delete)

            session.commit()
            print("系统平台模板同步完成。")
            with self._cache_lock:
                self._sys_platforms_cache = None


    def _get_sys_config(self, session):
        """Ensures the system platform cache is populated."""
        if self._sys_platforms_cache is None:
            with self._cache_lock:  # 使用锁保证线程安全
                # 双重检查锁定模式
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
        """统一将布尔值转换为整数（0/1）"""
        return 1 if value else 0
    
    @staticmethod
    def _int_to_bool(value: int) -> bool:
        """统一将整数（0/1）转换为布尔值"""
        return bool(value)

    @staticmethod
    def _apply_model_params(model_obj: 'LLModels', kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """
        从模型对象中解析 extra_body 并应用到 kwargs。
        """
        import json
        if model_obj and model_obj.extra_body:
            try:
                # 解析数据库中存储的JSON字符串
                model_extra_params = json.loads(model_obj.extra_body)
                
                if model_extra_params:
                    # 从 kwargs 或其子字典中安全地获取现有的 extra_body
                    model_kwargs = kwargs.get("model_kwargs", {})
                    existing_extra_body = kwargs.get("extra_body", model_kwargs.get("extra_body", {}))
                    
                    # 合并参数，模型配置优先
                    merged_extra_body = {**existing_extra_body, **model_extra_params}
                    
                    # 将合并后的 extra_body 设置为顶层参数
                    kwargs["extra_body"] = merged_extra_body
                    print(f"[AIManager] 应用模型 '{model_obj.display_name}' 的自定义参数: {merged_extra_body}")

            except json.JSONDecodeError:
                print(f"[AIManager] 警告：模型 '{model_obj.display_name}' 的 extra_body 字段不是有效的JSON，已忽略。")
        
        return kwargs

    @staticmethod
    def _normalize_usage_key(usage_key: Optional[str]) -> str:
        """标准化用途标识，缺省回退到默认主用途。"""
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
        """确保指定用途存在，返回 (slot, 是否新建)。"""
        slot = self._get_usage_slot(session, user_id, usage_key)
        if slot:
            return slot, False

        if platform_id is None:
            platform_id = self._default_platform_id
        if model_id is None:
            model_id = self._default_model_id
        if platform_id is None or model_id is None:
            raise RuntimeError("默认平台或模型尚未初始化，无法创建用途配置")

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
        """为用户初始化内置用途，返回是否有新增。"""
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
        slots = (
            session.query(UserModelUsage)
            .filter_by(user_id=user_id)
            .order_by(UserModelUsage.id.asc())
            .all()
        )
        details: List[Dict[str, Any]] = []
        for slot in slots:
            resolved = self._resolve_user_choice(
                session,
                user_id,
                slot.selected_platform_id,
                slot.selected_model_id,
                usage_slot=slot,
            )
            details.append(self._build_usage_payload(resolved, slot))
        return details


    def _get_default_platform_api_key(self, platform_name: str = None, base_url: str = None) -> Optional[str]:
        """
        从默认配置（DEFAULT_PLATFORM_CONFIGS）中获取平台的 API Key
        优先使用 base_url 匹配（更可靠），其次使用 platform_name
        """
        # 优先使用 base_url 查找（容错性更好）
        if base_url:
            for cfg in DEFAULT_PLATFORM_CONFIGS.values():
                if cfg.get("base_url") == base_url:
                    return cfg.get("api_key")
        
        # 其次使用 platform_name 查找
        if platform_name:
            cfg = DEFAULT_PLATFORM_CONFIGS.get(platform_name)
            if cfg:
                return cfg.get("api_key")
        
        return None
    
    def _get_effective_api_key(self, session, user_id: str, platform: LLMPlatform) -> Optional[str]:
        """
        获取有效的 API Key（统一的解析逻辑）
        优先级：用户自定义 > 系统默认配置
        
        Returns:
            - 有效的 API Key 字符串
            - None（如果未配置）
        """
        api_key = None
        sec_mgr = SecurityManager.get_instance()
        
        if platform.is_sys:
            # 系统平台：先检查用户是否有自定义凭据
            cred = session.query(LLMSysPlatformKey).filter_by(
                user_id=user_id, platform_id=platform.id
            ).first()
            
            if cred and cred.api_key:
                api_key = sec_mgr.decrypt(cred.api_key)
            
            # 如果仍无 api_key，验证是否为系统模式或启用自动获取，尝试从默认配置获取
            # 优先使用 base_url 匹配（即使平台名称被修改也能正确匹配）
            if not api_key and (user_id == SYSTEM_USER_ID or LLM_AUTO_KEY):
                api_key = self._get_default_platform_api_key(platform_name=platform.name, base_url=platform.base_url)
        else:
            # 用户私有平台
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
        """创建一个用户自定义平台 (is_sys=0)。"""
        self._ensure_mutable()
        if not (name and base_url):
            raise ValueError("name / base_url 必填")
        if user_id is None or user_id == SYSTEM_USER_ID:
            raise ValueError("用户自定义平台必须绑定真实 user_id")
        
        if api_key:
            api_key = SecurityManager.get_instance().encrypt(api_key)
        
        with self.Session() as session:
            # 查重：平台名称在用户的私有平台和系统平台中都必须是唯一的
            if name in DEFAULT_PLATFORM_CONFIGS:
                raise ValueError("平台名称与系统平台冲突")
            if session.query(LLMPlatform).filter_by(base_url=base_url, is_sys=1).first():
                raise ValueError("该 base_url 对应的系统平台已存在，建议直接使用系统平台并填写个人凭据")
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
        """
        为指定平台添加模型，确保用户只能操作自己的非系统平台。
        display_name 在用户的所有平台中必须唯一（用户级别防重复）。
        """
        import json
        self._ensure_mutable()
        if not (platform_id and model_name and display_name):
            raise ValueError("platform_id / model_name / display_name 必填")
        if user_id is None or user_id == SYSTEM_USER_ID:
            raise ValueError("为模型绑定真实 user_id")

        with self.Session() as session:
            plat = session.query(LLMPlatform).filter_by(id=platform_id, user_id=user_id, is_sys=0).first()
            if not plat:
                raise ValueError("平台不存在、无权限或为不可修改的系统平台")

            # 查重1：在用户的所有平台中，display_name 必须唯一（用户级别）
            user_platforms = session.query(LLMPlatform).filter_by(user_id=user_id, is_sys=0).all()
            user_platform_ids = [p.id for p in user_platforms]
            existing_display = session.query(LLModels).filter(
                LLModels.platform_id.in_(user_platform_ids),
                LLModels.display_name == display_name
            ).first()
            if existing_display:
                existing_plat = session.query(LLMPlatform).filter_by(id=existing_display.platform_id).first()
                raise ValueError(f"模型显示名称 '{display_name}' 已存在于您的平台 '{existing_plat.name}'")
            
            # 查重2：在同一个平台内，model_name 不能重复
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

    # ===== 用户级查询 =====
    def _collect_platform_views(self, session, user_id: str) -> List[Dict[str, Any]]:
        """组装用户可见的平台列表（含系统 + 私有），并计算最终 base_url / api_key 状态"""
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
            # 使用统一的 API Key 解析逻辑
            api_key = self._get_effective_api_key(session, user_id, plat)

            # 系统平台的隐藏状态从用户凭据中读取（用户级别）
            user_hide = cred.hide if cred else 0

            views.append(
                {
                    "platform_id": plat.id,
                    "name": plat.name,
                    "base_url": plat.base_url,
                    "api_key_set": bool(api_key),
                    "user_id": plat.user_id,
                    "is_sys": True,
                    "hide": user_hide,  # 使用用户级别的隐藏状态
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
            # 使用统一的 API Key 解析逻辑
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
        """返回扁平化的可选模型列表，供前端直接渲染"""
        with self.Session() as session:
            views = self._collect_platform_views(session, user_id)
            
            # 使用列表推导式优化性能，避免多次 append 调用
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
                

    def ensure_user_has_config(self, session, user_id: str) -> UserAIConfig:
        """确保用户有AI配置，并返回该配置对象（需要传入 session）"""
        cfg = session.query(UserAIConfig).filter_by(user_id=user_id).first()
        if not cfg:
            if self._default_platform_id is None or self._default_model_id is None:
                raise RuntimeError("AIManager 未正确初始化，默认平台或模型 ID 缺失")

            cfg = UserAIConfig(
                user_id=user_id,
                selected_platform_id=self._default_platform_id,
                selected_model_id=self._default_model_id,
            )
            session.add(cfg)

            try:
                session.commit()
            except Exception as e:
                session.rollback()
                cfg = session.query(UserAIConfig).filter_by(user_id=user_id).first()
                if not cfg:
                    raise

        # 确保默认用途存在
        if self._ensure_default_usage_slots(session, user_id):
            session.commit()

        return cfg

    def save_user_selection(
        self,
        user_id: str,
        platform_id: int,
        model_id: int,
        usage_key: Optional[str] = None,
    ) -> bool:
        """保存用户在特定用途下的平台和模型选择"""
        normalized_usage = self._normalize_usage_key(usage_key) if usage_key is not None else self._default_usage_key

        with self.Session() as session:
            self.ensure_user_has_config(session, user_id)
            usage_slot = self._get_usage_slot(session, user_id, normalized_usage)
            if not usage_slot:
                raise ValueError(f"未找到用途 '{normalized_usage}'，请先创建选中模型")

            # 验证平台与模型合法性，并禁止自动修复
            self._resolve_user_choice(
                session,
                user_id,
                platform_id,
                model_id,
                auto_fix=False,
            )

            usage_slot.selected_platform_id = platform_id
            usage_slot.selected_model_id = model_id

            if normalized_usage == self._default_usage_key:
                cfg = session.query(UserAIConfig).filter_by(user_id=user_id).first()
                if not cfg:
                    cfg = UserAIConfig(user_id=user_id)
                    session.add(cfg)
                cfg.selected_platform_id = platform_id
                cfg.selected_model_id = model_id

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
        """允许用户创建新的选中模型用途"""
        if not usage_key:
            raise ValueError("usage_key 不能为空")

        normalized_usage = self._normalize_usage_key(usage_key)
        label = (usage_label or usage_key).strip() or usage_key

        with self.Session() as session:
            user_id = str(user_id)
            cfg = self.ensure_user_has_config(session, user_id)

            if self._get_usage_slot(session, user_id, normalized_usage):
                raise ValueError(f"用途 '{normalized_usage}' 已存在")

            if (platform_id is None) ^ (model_id is None):
                raise ValueError("platform_id 与 model_id 需要同时提供或同时省略")

            if platform_id is None:
                platform_id = cfg.selected_platform_id
                model_id = cfg.selected_model_id
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

    def list_user_usage_selections(self, user_id: str) -> List[Dict[str, Any]]:
        """返回用户所有用途的模型绑定列表"""
        with self.Session() as session:
            user_id = str(user_id)
            self.ensure_user_has_config(session, user_id)
            details = self._collect_usage_payloads(session, user_id)
            session.commit()
            return details

    def update_platform_config(
        self, user_id: str, platform_id: int, api_key: str
    ) -> bool:
        """更新用户平台的 API Key。系统平台会在 LLMSysPlatformKey 中存储用户的 API Key，用户平台直接更新。"""
        
        encrypted_key = None
        if api_key:
            encrypted_key = SecurityManager.get_instance().encrypt(api_key)

        with self.Session() as session:
            target_plat = session.query(LLMPlatform).filter_by(id=platform_id).first()
            if not target_plat:
                raise ValueError("平台不存在")

            if target_plat.is_sys:
                # 系统平台：在 LLMSysPlatformKey 中存储用户的 API Key
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
                # 系统平台相关数据可能被修改，清除缓存
                with self._cache_lock:
                    self._sys_platforms_cache = None
            elif target_plat.user_id == user_id:
                # 用户私有平台：只有在非系统配置模式下才允许修改
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

    def rename_platform(self, user_id: str, platform_id: int, new_name: str) -> bool:
        self._ensure_mutable()
        if not new_name:
            raise ValueError("新平台名称不能为空")
        with self.Session() as session:
            # 首先检查平台是否存在
            plat = session.query(LLMPlatform).filter_by(id=platform_id).first()
            if not plat:
                raise ValueError("平台不存在")
            
            # 明确拒绝重命名系统平台
            if plat.is_sys:
                raise ValueError("系统平台不能被重命名，请直接修改 DEFAULT_PLATFORM_CONFIGS")
            
            # 检查权限（仅限用户自己的平台）
            if plat.user_id != user_id:
                raise ValueError("无权重命名该平台")
            
            # 检查新名称冲突
            if new_name in DEFAULT_PLATFORM_CONFIGS:
                raise ValueError("新平台名称与系统平台冲突")
            if (
                session.query(LLMPlatform)
                .filter_by(name=new_name, user_id=user_id, is_sys=0)
                .first()
            ):
                raise ValueError("您已有同名平台")
            
            plat.name = new_name
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
        """
        更新模型的显示名称和/或自定义参数 (extra_body)。
        """
        import json
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
                # 查重：在用户的所有平台中，display_name 必须唯一
                user_platforms = session.query(LLMPlatform).filter_by(user_id=user_id, is_sys=0).all()
                user_platform_ids = [p.id for p in user_platforms]
                dup = session.query(LLModels).filter(
                    LLModels.platform_id.in_(user_platform_ids),
                    LLModels.display_name == new_display_name,
                    LLModels.id != model_id  # 排除自身
                ).first()
                
                if dup:
                    dup_plat = session.query(LLMPlatform).filter_by(id=dup.platform_id).first()
                    raise ValueError(f"模型显示名称 '{new_display_name}' 已存在于您的平台 '{dup_plat.name}'")
                
                model.display_name = new_display_name
            
            if new_extra_body is not None:
                model.extra_body = json.dumps(new_extra_body) if new_extra_body else None

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
        """
        更新模型的显示名称和/或自定义参数 (extra_body)。
        """
        import json
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
                # 查重：在用户的所有平台中，display_name 必须唯一
                user_platforms = session.query(LLMPlatform).filter_by(user_id=user_id, is_sys=0).all()
                user_platform_ids = [p.id for p in user_platforms]
                dup = session.query(LLModels).filter(
                    LLModels.platform_id.in_(user_platform_ids),
                    LLModels.display_name == new_display_name,
                    LLModels.id != model_id  # 排除自身
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
        """切换平台的隐藏/显示状态（系统平台为用户级别，私有平台直接修改）"""
        with self.Session() as session:
            plat = session.query(LLMPlatform).filter_by(id=platform_id).first()
            if not plat:
                raise ValueError("平台不存在")
            
            if plat.is_sys:
                # 系统平台：在用户凭据表中存储隐藏状态（用户级别）
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
                # 系统平台相关数据可能被修改，清除缓存
                with self._cache_lock:
                    self._sys_platforms_cache = None
            else:
                # 用户私有平台：只能操作自己的平台
                if plat.user_id != user_id:
                    raise ValueError("无权修改该平台")
                plat.hide = self._bool_to_int(hide)
            
            session.commit()
            return True

    def _get_fallback_platform_model(self, session, user_id: str) -> tuple[int, int]:
        """
        获取备用的系统平台和模型（当用户配置的平台/模型不可用时使用）。
        返回: (platform_id, model_id)
        """
        # 优先获取第一个可用的系统平台及其第一个模型
        self._get_sys_config(session)
        sys_platforms = self._sys_platforms_cache
        
        for plat in sys_platforms:
            if not plat.models:
                continue
            
            # 使用统一的 API Key 解析逻辑检查是否有可用的 API Key
            api_key = self._get_effective_api_key(session, user_id, plat)
            
            # 如果有可用的 API Key，使用这个平台
            if api_key:
                return plat.id, plat.models[0].id
        
        # 如果没有找到有 API Key 的系统平台，返回第一个系统平台（后续会在 API Key 验证时报错）
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
    ) -> Dict[str, Any]:
        """
        核心解析器：将用户选择的平台ID和模型ID解析为具体的平台、模型和API Key。
        当配置无效时，如果 auto_fix=True，会自动切换到第一个可用的系统平台和模型。
        """
        original_platform_id = platform_id
        original_model_id = model_id
        config_invalid = False
        
        # 先获取模型对象，验证其存在性
        model_obj = session.query(LLModels).filter_by(id=model_id).first()
        if not model_obj:
            config_invalid = True
            if auto_fix:
                print(f"[AIManager] 用户 {user_id} 的模型ID '{model_id}' 不存在，尝试使用备用配置")
            else:
                raise ValueError(f"模型ID '{model_id}' 不存在")
        
        # 验证模型属于指定平台（如果模型存在的话）
        if model_obj and model_obj.platform_id != platform_id:
            config_invalid = True
            if auto_fix:
                print(f"[AIManager] 用户 {user_id} 的模型ID '{model_id}' 不属于平台ID '{platform_id}'，尝试使用备用配置")
            else:
                raise ValueError(f"模型ID '{model_id}' 不属于平台ID '{platform_id}'")
        
        # 获取平台对象
        plat = session.query(LLMPlatform).filter_by(id=platform_id).first()
        if not plat:
            config_invalid = True
            if auto_fix:
                print(f"[AIManager] 用户 {user_id} 的平台ID '{platform_id}' 不存在，尝试使用备用配置")
            else:
                raise ValueError(f"平台ID '{platform_id}' 不存在")
        
        # 如果是用户私有平台,验证权限
        if plat and not plat.is_sys and plat.user_id != user_id:
            config_invalid = True
            if auto_fix:
                print(f"[AIManager] 用户 {user_id} 无权访问平台ID '{platform_id}'，尝试使用备用配置")
            else:
                raise ValueError(f"无权访问平台ID '{platform_id}'")
        
        # 如果配置无效且启用自动修复，获取备用配置
        if config_invalid and auto_fix:
            try:
                platform_id, model_id = self._get_fallback_platform_model(session, user_id)
                
                # 在当前 session 中更新用户配置（延迟提交，由调用者决定何时提交）
                cfg = session.query(UserAIConfig).filter_by(user_id=user_id).first()
                if cfg:
                    cfg.selected_platform_id = platform_id
                    cfg.selected_model_id = model_id
                    print(f"[AIManager] 已标记更新用户 {user_id} 的配置：平台ID {original_platform_id}->{platform_id}，模型ID {original_model_id}->{model_id}")

                if usage_slot:
                    usage_slot.selected_platform_id = platform_id
                    usage_slot.selected_model_id = model_id
                    print(f"[AIManager] 已同步用途 {usage_slot.usage_key} 的选中模型")
                
                # 在当前 session 中重新获取平台和模型对象
                plat = session.query(LLMPlatform).filter_by(id=platform_id).first()
                model_obj = session.query(LLModels).filter_by(id=model_id).first()
                
            except Exception as e:
                raise ValueError(f"用户配置无效且无法自动修复：{e}")
        
        # 使用统一的 API Key 解析逻辑
        api_key = self._get_effective_api_key(session, user_id, plat)
        
        # 提前验证 API Key
        if not api_key:
            # 根据用户类型和平台类型提供不同的错误提示
            if user_id == SYSTEM_USER_ID:
                # 系统用户（服务器模式）：必须配置环境变量
                env_var_hint = ""
                if plat.is_sys:
                    cfg = DEFAULT_PLATFORM_CONFIGS.get(plat.name)
                    if cfg:
                        # 尝试从原始 YAML 推断环境变量名
                        config_path = os.path.join(os.path.dirname(__file__), "llm_mgr_cfg.yaml")
                        if os.path.exists(config_path):
                            with open(config_path, "r", encoding="utf-8") as f:
                                yaml_cfg = yaml.safe_load(f)
                                plat_cfg = yaml_cfg.get(plat.name, {})
                                raw_key = plat_cfg.get("api_key", "")
                                if raw_key and raw_key.startswith("{"):
                                    import re
                                    match = re.search(r'\{([^}]+)\}', raw_key)
                                    if match:
                                        env_var_name = match.group(1)
                                        env_var_hint = f"请设置环境变量: {env_var_name}"
                
                raise ValueError(
                    f"平台 '{plat.name}' 的 API Key 未配置（系统模式）。\n"
                    f"{env_var_hint if env_var_hint else '请在配置文件中设置 API Key 或配置环境变量。'}"
                )
            else:
                # 普通用户：可以自己配置 Key
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
        usage_key: Optional[str] = None,
        **kwargs: Any,
    ) -> BaseChatModel:
        """
        获取用户配置的 LLM 实例（基于ID解析）。
        如果 user_id 不设置，则使用 SYSTEM_USER_ID（无用户/单用户模式）。
        usage_key 用于选择具体用途，默认回退到主模型。
        额外的参数通过 kwargs 传递给 ChatOpenAI 构造函数，streaming 默认为 True。
        """
        effective_user_id = user_id if user_id is not None else SYSTEM_USER_ID
        normalized_usage = self._normalize_usage_key(usage_key) if usage_key is not None else self._default_usage_key
        
        with self.Session() as session:
            cfg = self.ensure_user_has_config(session, effective_user_id)
            usage_slot = self._get_usage_slot(session, effective_user_id, normalized_usage)
            if not usage_slot:
                raise ValueError(f"未找到用途 '{normalized_usage}' 的模型配置，请先创建选中模型。")

            if normalized_usage == self._default_usage_key:
                cfg.selected_platform_id = usage_slot.selected_platform_id
                cfg.selected_model_id = usage_slot.selected_model_id

            resolved = self._resolve_user_choice(
                session,
                effective_user_id,
                usage_slot.selected_platform_id,
                usage_slot.selected_model_id,
                usage_slot=usage_slot,
            )
            
            # 如果 auto_fix 修改了配置，在这里提交
            session.commit()

            platform_obj = resolved["platform"]
            model_obj = resolved["model"]
            api_key = resolved["api_key"]
            base_url = resolved.get("base_url", platform_obj.base_url)

            if not api_key:
                raise ValueError(f"平台 '{platform_obj.name}' 的 API Key 未设置。请在 AI 设置中填写或配置服务器环境变量。")

            # 应用模型的自定义参数
            kwargs = self._apply_model_params(model_obj, kwargs)

            # 设置默认值，但允许通过 kwargs 覆盖
            if 'streaming' not in kwargs:
                kwargs['streaming'] = True
            
            return ChatOpenAI(
                base_url=base_url,
                api_key=api_key,
                model_name=model_obj.model_name,
                **kwargs,
            )

    def get_user_selection_detail(self, user_id: str, usage_key: Optional[str] = None) -> Dict[str, Any]:
        """返回指定用途的模型选择，并附带所有用途的摘要"""
        normalized_usage = self._normalize_usage_key(usage_key) if usage_key is not None else self._default_usage_key
        user_id = str(user_id)

        with self.Session() as session:
            self.ensure_user_has_config(session, user_id)
            usage_slot = self._get_usage_slot(session, user_id, normalized_usage)
            if not usage_slot:
                raise ValueError(f"未找到用途 '{normalized_usage}' 的模型配置")

            resolved = self._resolve_user_choice(
                session,
                user_id,
                usage_slot.selected_platform_id,
                usage_slot.selected_model_id,
                usage_slot=usage_slot,
            )

            current_detail = self._build_usage_payload(resolved, usage_slot)
            usage_details = self._collect_usage_payloads(session, user_id)

            session.commit()

            current_detail["usage_selections"] = usage_details
            return current_detail

    def get_spec_sys_llm(
            self, platform_name: str, model_display_name: str, **kwargs: Any
        ) -> BaseChatModel:
            """
            从 DEFAULT_PLATFORM_CONFIGS 依靠显示名字获取指定系统内置 LLM 实例，固定使用 SYSTEM_USER_ID。
            """
            try:
                platform_config = DEFAULT_PLATFORM_CONFIGS[platform_name]
                model_config = platform_config["models"][model_display_name]

                if isinstance(model_config, dict):
                    model_name = model_config.get("model_name")
                else:
                    model_name = model_config

                if not model_name:
                    raise ValueError(f"模型 '{model_display_name}' 的 model_name 未在配置中找到")

                api_key = platform_config.get("api_key")
                base_url = platform_config.get("base_url")

                if not api_key:
                    raise ValueError(f"平台 '{platform_name}' 的 API Key 未在环境变量中配置。")
                if not base_url:
                    raise ValueError(f"平台 '{platform_name}' 的 base_url 未配置。")
                
                # 注意：此方法无法直接获取模型对象，因此无法应用 extra_body。
                # 这是一个简化的快捷方式，主要用于系统内部调用已知模型。
                # 如果需要 extra_body，应使用 get_user_llm。

                # 设置默认值，但允许通过 kwargs 覆盖
                if 'streaming' not in kwargs:
                    kwargs['streaming'] = True
                
                return ChatOpenAI(
                    base_url=base_url,
                    api_key=api_key,
                    model_name=model_name,
                    **kwargs,
                )
            except KeyError:
                raise ValueError(f"在 DEFAULT_PLATFORM_CONFIGS 中未找到平台 '{platform_name}' 或模型 '{model_display_name}'")
            except Exception as e:
                print(f"创建 specific LLM 时出错: {e}")
                raise


# 创建一个全局唯一的 AIManager 实例
LLM_Manager = AIManager()

def init_default_llm():
    """
    一个独立的、可供外部（如 apps.py）调用的启动初始化函数。
    """
    print("正在执行 AI 管理器的启动初始化...")
    LLM_Manager.initialize_defaults()
    print("AI 管理器初始化完成。")


if __name__ == "__main__":
    # 直接运行时启动图形化配置管理界面
    import sys
    import subprocess
    
    # 检查 GUI 模块是否存在
    gui_module_path = os.path.join(os.path.dirname(__file__), "llm_mgr_cfg_gui.py")
    
    if os.path.exists(gui_module_path):
        print("启动图形化配置管理界面...")
        # 使用 subprocess 运行 GUI 模块，避免导入问题
        # 注意：需要设置 PYTHONPATH 以便 GUI 模块能找到 server 包
        env = os.environ.copy()
        server_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if "PYTHONPATH" in env:
            env["PYTHONPATH"] = server_root + os.pathsep + env["PYTHONPATH"]
        else:
            env["PYTHONPATH"] = server_root
            
        result = subprocess.run([sys.executable, gui_module_path], env=env)
        sys.exit(result.returncode)
    else:
        print(f"错误: 找不到图形化界面模块 '{gui_module_path}'")
        print("请确保 llm_mgr_cfg_gui.py 与 llm_mgr.py 在同一目录下。")
        sys.exit(1)
