import os
from typing import Dict, Any, Optional

from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy import create_engine, Column, Integer, String, DateTime, func, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker

# --- 1. 安全的密钥管理 ---
# 建议使用环境变量存储 API 密钥。
MODELSCOPE_API_KEY = os.environ.get("MODELSCOPE_API_KEY")
ALIYUN_API_KEY = os.environ.get("ALIYUN_API_KEY")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
GEMINIX_API_KEY = os.environ.get("GEMINIX_API_KEY")


# --- 2. 平台与模型配置中心 取第一个平台的第一个模型作为默认 ---
PLATFORM_CONFIGS: Dict[str, Any] = {
    "魔搭社区": {
        "base_url": "https://api-inference.modelscope.cn/v1/",
        "api_key": MODELSCOPE_API_KEY,
        "models": {
            "Qwen3 2507": "Qwen/Qwen3-235B-A22B-Instruct-2507",
            "DeepSeek V3.1": "deepseek-ai/DeepSeek-V3.1"
        }
    },
    "OpenRouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": OPENROUTER_API_KEY,
        "models": {
            "DeepSeek V3-0324": "deepseek/deepseek-chat-v3-0324:free",
            "DeepSeek V3.1": "deepseek/deepseek-chat-v3.1:free"
        }
    },
    "阿里云百炼": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": ALIYUN_API_KEY,
        "models": {
            "通义千问-Plus-最新版": "qwen-plus-latest",
            "通义千问-Flash-最新版": "qwen-flash"
        }
    },
    "谷歌AIStudio": {
        "base_url": "http://dx.nb.s1.natgo.cn:10240/v1",
        "api_key": GEMINIX_API_KEY,
        "models": {
            "哈基米flash版": "gemini-2.5-flash",
            "哈基米pro版": "gemini-2.5-pro"
        }
    }
}


default_platform = next(iter(PLATFORM_CONFIGS))#取第一个平台作为默认
default_model    = next(iter(PLATFORM_CONFIGS[default_platform]["models"]))#取该平台的第一个模型作为默认



# --- 3. 独立的 SQLAlchemy 模型定义 ---
# 这个 Base 和 UserAIConfig 模型只属于这个文件，不与外部项目冲突。
LLMConfig = declarative_base()

class UserAIConfig(LLMConfig):
    """用于存储用户AI平台和模型配置的数据库模型。"""
    __tablename__ = 'user_ai_configs'

    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), unique=True, nullable=False, index=True)
    selected_platform = Column(String(50), nullable=False)
    selected_model = Column(String(100), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return (
            f"<UserAIConfig(user_id='{self.user_id}', "
            f"platform='{self.selected_platform}', model='{self.selected_model}')>"
        )

class UserAPIKey(LLMConfig):
    """按平台存储用户自定义 API Key（可选）。"""
    __tablename__ = 'user_api_keys'

    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), nullable=False, index=True)
    platform = Column(String(50), nullable=False)
    api_key = Column(String(512), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('user_id', 'platform', name='uq_user_platform_api_key'),
    )

# --- 4. 核心管理器类 ---
class AIManager:
    """
    自包含的通用AI模型管理器。
    """
    def __init__(self, db_name: str = "llm_config.db"):
        """
        初始化AIManager。默认会在当前文件目录下创建并使用 llm_config.db 数据库。
        :param db_name: SQLite数据库的文件名。如果想使用内存数据库进行测试，可以传入 ":memory:"。
        """
        # 将数据库文件创建在 ai_manager.py 旁边，而不是项目启动目录下，更稳定。
        base_dir = os.path.abspath(os.path.dirname(__file__))
        db_path = os.path.join(base_dir, db_name)
        
        db_url = f"sqlite:///{db_path}"
        
        self.engine = create_engine(db_url)
        LLMConfig.metadata.create_all(self.engine)  # 确保表已创建（包含 API Key 表）
        self.Session = sessionmaker(bind=self.engine)
        print(f"AIManager 已初始化，连接到数据库: {db_url}")


    def _validate_selection(self, platform: str, model: str):
        """验证用户选择的平台和模型是否有效。"""
        if platform not in PLATFORM_CONFIGS:
            raise ValueError(f"无效的平台: '{platform}'。可用平台: {list(PLATFORM_CONFIGS.keys())}")
        
        if model not in PLATFORM_CONFIGS[platform]["models"]:
            raise ValueError(
                f"平台 '{platform}' 不支持模型: '{model}'。"
                f"可用模型: {list(PLATFORM_CONFIGS[platform]['models'].keys())}"
            )

    def get_available_models(self) -> Dict[str, Any]:
        """返回所有可用的平台及其模型，方便前端或调用方展示。"""
        return PLATFORM_CONFIGS

    def save_config(self, user_id: str, platform: str, model: str):
        """为用户保存或更新AI配置，会先进行验证。"""
        self._validate_selection(platform, model)
        with self.Session() as session:
            config = session.query(UserAIConfig).filter_by(user_id=user_id).first()
            if config:
                config.selected_platform = platform
                config.selected_model = model
            else:
                config = UserAIConfig(user_id=user_id, selected_platform=platform, selected_model=model)
                session.add(config)
            session.commit()
            print(f"成功为用户 '{user_id}' 保存配置: platform='{platform}', model='{model}'")

    def get_config(self, user_id: str) -> Optional[UserAIConfig]:
        """获取指定用户的AI配置。"""
        with self.Session() as session:
            return session.query(UserAIConfig).filter_by(user_id=user_id).first()

    # --- 用户 API Key 管理 ---
    def set_api_key(self, user_id: str, platform: str, api_key: str) -> None:
        """为用户设置（或更新）某平台的 API Key。"""
        if platform not in PLATFORM_CONFIGS:
            raise ValueError(f"无效的平台: '{platform}'。可用平台: {list(PLATFORM_CONFIGS.keys())}")
        if not api_key:
            raise ValueError("api_key 不能为空")
        with self.Session() as session:
            row = session.query(UserAPIKey).filter_by(user_id=user_id, platform=platform).first()
            if row:
                row.api_key = api_key
            else:
                row = UserAPIKey(user_id=user_id, platform=platform, api_key=api_key)
                session.add(row)
            session.commit()

    def get_api_key(self, user_id: str, platform: str) -> Optional[str]:
        """获取用户在某平台的自定义 API Key，若无则返回 None。"""
        if platform not in PLATFORM_CONFIGS:
            return None
        with self.Session() as session:
            row = session.query(UserAPIKey).filter_by(user_id=user_id, platform=platform).first()
            return row.api_key if row else None

    def create_llm(self, platform: str, model: str, user_id: Optional[str] = None, **kwargs: Any) -> BaseChatModel:
        """根据给定的平台和模型创建一个LLM实例。"""
        self._validate_selection(platform, model)
        config = PLATFORM_CONFIGS[platform]
        model_name = config["models"][model]
        
        default_params = {"temperature": 0.6, "streaming": True}
        default_params.update(kwargs)

        # 优先使用用户自定义 API Key（如存在），否则使用平台默认 Key
        api_key = None
        if user_id:
            api_key = self.get_api_key(user_id, platform)
        api_key = api_key or config["api_key"]

        # 经过测试，ChatGoogleGenerativeAI 在使用自定义端点时存在流式输出 Bug。
        # 统一使用 ChatOpenAI，因为它能正确处理通过代理的流式请求。
        # 为了兼容性，同时检查 "base_url" 和旧的 "api_endpoint" 键。
        base_url = config.get("base_url") or config.get("api_endpoint")
        if not base_url:
            raise ValueError(f"平台 '{platform}' 的配置中缺少 'base_url' 或 'api_endpoint'。")

        return ChatOpenAI(
            base_url=base_url,
            api_key=api_key,
            model_name=model_name,
            **default_params
        )

    def get_user_llm(
        self,
        user_id: Optional[str] = None,
        default_platform: str = default_platform,
        default_model: str = default_model,
        **kwargs: Any
    ) -> BaseChatModel:
        """
        为指定用户获取LLM实例。
        如果用户有配置，则使用该配置；否则，使用提供的默认配置。
        """
        # 调试模式：允许不传入 user_id
        if not user_id:
            print(f"[AIManager] 未传入 user_id，使用默认配置 {default_platform}/{default_model}")
            return self.create_llm(default_platform, default_model, user_id=None, **kwargs)

        user_config = self.get_config(user_id)

        if user_config:
            print(f"加载用户 '{user_id}' 的配置: {user_config.selected_platform}/{user_config.selected_model}")
            return self.create_llm(user_config.selected_platform, user_config.selected_model, user_id=user_id, **kwargs)
        else:
            # 首次无配置：为该用户创建并保存默认配置，再返回对应 LLM
            try:
                self.save_config(user_id, default_platform, default_model)
                print(f"未找到用户 '{user_id}' 的配置，已为其创建默认: {default_platform}/{default_model}")
            except Exception as e:
                print(f"为用户 '{user_id}' 创建默认配置失败: {e}")
            return self.create_llm(default_platform, default_model, user_id=user_id, **kwargs)
