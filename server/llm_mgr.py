# 这是一个通用的大模型管理器，拥有一组内置的平台模型，支持三种使用情况
# 1.无用户/全局单用户模式 用于开发者为所有用户提供llm服务、私有系统或者开发调试
# 2.多用户固定平台模式 为保证模型质量 可以强制用户使用系统内置平台 不能创建自己的平台和模型 但是可以使用自己的apikey以节省成本
# 3.多用户自定义平台模式 用户可以自由拓展自己的平台
# 支持用户隐藏/显示平台以符合不同用户的需求
import os
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

MODELSCOPE_API_KEY = os.environ.get("MODELSCOPE_API_KEY")
ALIYUN_API_KEY = os.environ.get("ALIYUN_API_KEY")#注意 这里为了好区分没有用默认的DASHSCOPE做名字
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
GEMINIX_API_KEY = os.environ.get("GEMINIX_API_KEY")


#系统内置平台模型模板 所有情况下禁止用户修改 但允许用户隐藏/显示 要修改请直接修改此处
#此处的模型简称不要重复 get_spec_sys_llm 取系统内置的某一个具体模型 依靠显示名字获取模型
DEFAULT_PLATFORM_CONFIGS: Dict[str, Any] = {
        "Google AIStudio": {
        "base_url": "http://dx.nb.s1.natgo.cn:10241/v1",
        "api_key": GEMINIX_API_KEY,
        "models": {
            "哈基米flash": "gemini-2.5-flash",
            "哈基米pro": "gemini-2.5-pro",
        },
    },
    "魔搭ModelScope": {
        "base_url": "https://api-inference.modelscope.cn/v1/",
        "api_key": MODELSCOPE_API_KEY,
        "models": {
            "通义千问3 V2507": "Qwen/Qwen3-235B-A22B-Instruct-2507",
            "DeepSeek V3.1": "deepseek-ai/DeepSeek-V3.1",
            "智谱 GLM 4.6": "ZhipuAI/GLM-4.6",
        },
    },
    "OpenRouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": OPENROUTER_API_KEY,
        "models": {
            "DeepSeek V3-0324": "deepseek/deepseek-chat-v3-0324:free",
            "DeepSeek R1-0528": "deepseek/deepseek-r1-0528:free",
        },
    },
    "阿里云百炼": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": ALIYUN_API_KEY,
        "models": {"通义千问Plus": "qwen-plus-latest", "通义千问极速版": "qwen-flash"},
    },
}


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




class AIManager:
    def __init__(self, db_name: str = "llm_config.db"):
        import threading
        base_dir = os.path.abspath(os.path.dirname(__file__))
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
        """
        with self.Session() as session:
            print("同步系统平台模板...")
            for name, cfg in DEFAULT_PLATFORM_CONFIGS.items():
                base_url = cfg["base_url"]
                # 优先使用 base_url 来匹配系统平台，防止名称被修改导致的问题
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
                else:
                    # 强制恢复系统平台的标准名称，修复被重命名的情况
                    plat.name = name
                    plat.base_url = base_url
                    plat.api_key = None # 确保始终为None

                # 同步模型
                existing_models = {m.display_name: m for m in plat.models}
                for display_name, model_name in cfg.get("models", {}).items():
                    if display_name in existing_models:
                        existing_models[display_name].model_name = model_name
                        del existing_models[display_name]
                    else:
                        new_model = LLModels(
                            platform_id=plat.id,
                            model_name=model_name,
                            display_name=display_name,
                        )
                        session.add(new_model)
                
                for model_to_delete in existing_models.values():
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

    def _get_env_api_key(self, platform_name: str = None, base_url: str = None) -> Optional[str]:
        """
        从环境变量配置中获取平台的 API Key
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
        优先级：用户自定义 > 系统环境变量
        """
        api_key = None
        
        if platform.is_sys:
            # 系统平台：先检查用户是否有自定义凭据
            cred = session.query(LLMSysPlatformKey).filter_by(
                user_id=user_id, platform_id=platform.id
            ).first()
            
            if cred and cred.api_key:
                api_key = cred.api_key
            
            # 如果仍无 api_key，验证是否为系统模式或启用自动获取，尝试从环境变量获取
            # 优先使用 base_url 匹配（即使平台名称被修改也能正确匹配）
            if not api_key and (user_id == SYSTEM_USER_ID or LLM_AUTO_KEY):
                api_key = self._get_env_api_key(platform_name=platform.name, base_url=platform.base_url)
        else:
            # 用户私有平台
            api_key = platform.api_key
            if not api_key and user_id == SYSTEM_USER_ID:
                api_key = self._get_env_api_key(platform_name=platform.name, base_url=platform.base_url)
        
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
        display_name: str = "",
        user_id: str = None,
    ):
        """
        为指定平台添加模型，确保用户只能操作自己的非系统平台。
        display_name 在用户的所有平台中必须唯一（用户级别防重复）。
        """
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

            m = LLModels(
                platform_id=plat.id, model_name=model_name, display_name=display_name
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
        if cfg:
            return cfg

        # 检查默认配置是否已初始化
        if self._default_platform_id is None or self._default_model_id is None:
            raise RuntimeError("AIManager 未正确初始化，默认平台或模型 ID 缺失")

        # 为新用户创建默认配置，使用数据库ID
        cfg = UserAIConfig(
            user_id=user_id,
            selected_platform_id=self._default_platform_id,
            selected_model_id=self._default_model_id,
        )
        session.add(cfg)
        
        try:
            session.commit()
        except Exception as e:
            # 处理竞态条件：可能其他请求已经创建了配置
            session.rollback()
            cfg = session.query(UserAIConfig).filter_by(user_id=user_id).first()
            if cfg:
                return cfg
            # 如果还是没有，说明是其他错误，重新抛出
            raise
        
        return cfg

    def save_user_selection(
        self, user_id: str, platform_id: int, model_id: int
    ) -> bool:
        """保存用户的平台和模型选择配置（基于平台/模型 ID）"""
        with self.Session() as session:
            plat = session.query(LLMPlatform).filter_by(id=platform_id).first()
            if not plat:
                raise ValueError("平台不存在或不可用")

            if not plat.is_sys and plat.user_id != user_id:
                raise ValueError("无权使用该平台")

            model = (
                session.query(LLModels)
                .filter_by(id=model_id, platform_id=plat.id)
                .first()
            )
            if not model:
                raise ValueError("模型不存在于所选平台")

            cfg = session.query(UserAIConfig).filter_by(user_id=user_id).first()
            if not cfg:
                cfg = UserAIConfig(user_id=user_id)
                session.add(cfg)

            cfg.selected_platform_id = platform_id
            cfg.selected_model_id = model_id

            session.commit()
            return True

    def update_platform_config(
        self, user_id: str, platform_id: int, api_key: str
    ) -> bool:
        """更新用户平台的 API Key。系统平台会在 LLMSysPlatformKey 中存储用户的 API Key，用户平台直接更新。"""
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
                cred.api_key = api_key or None
                # 系统平台相关数据可能被修改，清除缓存
                with self._cache_lock:
                    self._sys_platforms_cache = None
            elif target_plat.user_id == user_id:
                # 用户私有平台：只有在非系统配置模式下才允许修改
                if self.use_sys_llm_config:
                    raise ValueError("当前处于系统配置模式，不支持修改用户私有平台")
                target_plat.api_key = api_key
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

    def rename_model(
        self,
        user_id: str,
        model_id: int,
        new_display_name: Optional[str] = None,
    ) -> bool:
        """
        重命名模型的显示名称。
        display_name 在用户的所有平台中必须唯一（用户级别防重复）。
        """
        self._ensure_mutable()
        if not (new_display_name):
            raise ValueError("必须提供新的模型显示名")
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
                raise ValueError("模型不存在或无权重命名")
            
            if new_display_name:
                # 查重：在用户的所有平台中，display_name 必须唯一（用户级别）
                user_platforms = session.query(LLMPlatform).filter_by(user_id=user_id, is_sys=0).all()
                user_platform_ids = [p.id for p in user_platforms]
                dup = session.query(LLModels).filter(
                    LLModels.platform_id.in_(user_platform_ids),
                    LLModels.display_name == new_display_name
                ).first()
                
                if dup and dup.id != model.id:
                    dup_plat = session.query(LLMPlatform).filter_by(id=dup.platform_id).first()
                    raise ValueError(f"模型显示名称 '{new_display_name}' 已存在于您的平台 '{dup_plat.name}'")
                
                model.display_name = new_display_name
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

    def _resolve_user_choice(self, session, user_id: str, platform_id: int, model_id: int, auto_fix: bool = True) -> Dict[str, Any]:
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
                    # 注意：不在此处提交，由外部调用者统一管理事务
                    print(f"[AIManager] 已标记更新用户 {user_id} 的配置：平台ID {original_platform_id}->{platform_id}，模型ID {original_model_id}->{model_id}")
                
                # 在当前 session 中重新获取平台和模型对象
                plat = session.query(LLMPlatform).filter_by(id=platform_id).first()
                model_obj = session.query(LLModels).filter_by(id=model_id).first()
                
            except Exception as e:
                raise ValueError(f"用户配置无效且无法自动修复：{e}")
        
        # 使用统一的 API Key 解析逻辑
        api_key = self._get_effective_api_key(session, user_id, plat)
        
        # 提前验证 API Key
        if not api_key:
            raise ValueError(
                f"平台 '{plat.name}' 的 API Key 未设置。"
                f"请在 AI 设置中填写或配置服务器环境变量。"
            )
        
        return {
            "platform": plat,
            "model": model_obj,
            "api_key": api_key,
            "base_url": plat.base_url,
        }

    def get_user_llm(
        self, user_id: Optional[str] = None, **kwargs: Any
    ) -> BaseChatModel:
        """
        获取用户配置的 LLM 实例（基于ID解析）。
        """
        effective_user_id = user_id if user_id is not None else SYSTEM_USER_ID
        
        with self.Session() as session:
            cfg = self.ensure_user_has_config(session, effective_user_id)
            
            resolved = self._resolve_user_choice(
                session, effective_user_id, cfg.selected_platform_id, cfg.selected_model_id
            )
            
            # 如果 auto_fix 修改了配置，在这里提交
            session.commit()

            platform_obj = resolved["platform"]
            model_obj = resolved["model"]
            api_key = resolved["api_key"]
            base_url = resolved.get("base_url", platform_obj.base_url)

            if not api_key:
                raise ValueError(f"平台 '{platform_obj.name}' 的 API Key 未设置。请在 AI 设置中填写或配置服务器环境变量。")

            # 设置默认值，但允许通过 kwargs 覆盖
            if 'streaming' not in kwargs:
                kwargs['streaming'] = True
            
            return ChatOpenAI(
                base_url=base_url,
                api_key=api_key,
                model_name=model_obj.model_name,
                **kwargs,
            )

    def get_user_selection_detail(self, user_id: str) -> Dict[str, Any]:
        """返回用户当前选择的详细信息（基于ID解析）"""
        with self.Session() as session:
            cfg = self.ensure_user_has_config(session, str(user_id))
            
            # 在 Session 内读取所有需要的属性
            platform_id = cfg.selected_platform_id
            model_id = cfg.selected_model_id
            
            resolved = self._resolve_user_choice(
                session, user_id, platform_id, model_id
            )
            
            # 如果 auto_fix 修改了配置，在这里提交
            session.commit()
            
            platform_obj = resolved["platform"]
            model_obj = resolved["model"]
            api_key = resolved["api_key"]
            base_url = resolved.get("base_url", platform_obj.base_url)

            return {
                "platform": platform_obj.name,
                "platform_id": platform_obj.id,
                "base_url": base_url,
                "model_display_name": model_obj.display_name,
                "model_id": model_obj.id,
                "model_name": model_obj.model_name,
                "api_key_set": bool(api_key),
            }

    def get_spec_sys_llm(
            self, platform_name: str, model_display_name: str, **kwargs: Any
        ) -> BaseChatModel:
            """
            从 DEFAULT_PLATFORM_CONFIGS 依靠显示名字获取指定系统内置 LLM 实例，固定使用 SYSTEM_USER_ID。
            """
            try:
                platform_config = DEFAULT_PLATFORM_CONFIGS[platform_name]
                model_name = platform_config["models"][model_display_name]
                api_key = platform_config.get("api_key")
                base_url = platform_config.get("base_url")

                if not api_key:
                    raise ValueError(f"平台 '{platform_name}' 的 API Key 未在环境变量中配置。")
                if not base_url:
                    raise ValueError(f"平台 '{platform_name}' 的 base_url 未配置。")

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

    # 远程探测
    def probe_platform_models(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 8.0,
        raise_on_error: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        探测平台可用的模型列表
        
        Args:
            base_url: 平台的基础 URL
            api_key: API 密钥
            timeout: 请求超时时间（秒）
            raise_on_error: 是否在出错时抛出异常
            
        Returns:
            模型列表，每个模型包含 'id' 和 'raw' 字段
        """
        try:
            import requests
        except ImportError as e:
            msg = "缺少 requests 库，无法执行远程探测"
            if raise_on_error:
                raise ImportError(msg) from e
            print(f"[AIManager] {msg}")
            return []
        
        # 参数验证
        if not base_url:
            msg = "base_url 不能为空"
            if raise_on_error:
                raise ValueError(msg)
            print(f"[AIManager] {msg}")
            return []
        if not api_key:
            msg = "api_key 不能为空"
            if raise_on_error:
                raise ValueError(msg)
            print(f"[AIManager] {msg}")
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
                print(f"[AIManager] {msg}")
                return []
            
            # 处理其他 HTTP 错误
            if not resp.ok:
                msg = f"探测失败 (HTTP {resp.status_code}): {resp.text[:120]}"
                if raise_on_error:
                    raise RuntimeError(msg)
                print(f"[AIManager] {msg}")
                return []
            
            # 解析响应
            js = resp.json()
            items = js.get('data') if isinstance(js, dict) else None
            if not isinstance(items, list):
                msg = "响应格式错误：缺少 'data' 列表字段"
                if raise_on_error:
                    raise ValueError(msg)
                print(f"[AIManager] {msg}")
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
            print(f"[AIManager] {msg}")
            return []
        except Exception as e:
            # 其他未预期的错误
            msg = f"探测时发生未预期的错误: {type(e).__name__}: {e}"
            print(f"[AIManager] {msg}")
            if raise_on_error:
                raise
            return []

# 创建一个全局唯一的 AIManager 实例
LLM_Manager = AIManager()

def init_default_llm():
    """
    一个独立的、可供外部（如 apps.py）调用的启动初始化函数。
    """
    print("正在执行 AI 管理器的启动初始化...")
    LLM_Manager.initialize_defaults()
    print("AI 管理器初始化完成。")
