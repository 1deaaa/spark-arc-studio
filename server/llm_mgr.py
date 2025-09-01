# ai_manager.py

"""
自包含 AI 模型管理器 (AIManager)

该模块提供了一个完全独立的解决方案，用于管理、配置和实例化来自不同平台的大语言模型（LLM）。

核心特性:
1.  **独立数据库**: 自动创建和管理一个名为 `llm_config.db` 的 SQLite 数据库文件，
    用于持久化用户配置，不依赖于任何外部数据库。
2.  **即插即用**: 可以作为一个独立的 .py 文件被轻松集成到任何项目中。
3.  **配置与验证**: 预定义了所有可用的平台和模型，并对用户的选择进行严格验证。
4.  **简易的 LLM 实例化**: 提供简单的方法来获取和创建 LLM 实例。

所需依赖:
- sqlalchemy
- langchain-openai
- langchain-community
- greenlet (SQLAlchemy 搭配 SQLite 可能需要)

安装命令:
pip install sqlalchemy langchain-openai langchain-community "greenlet>=3.0.0"
"""

import os
from typing import Dict, Any, Optional

from langchain_openai import ChatOpenAI
from sqlalchemy import create_engine, Column, Integer, String, DateTime, func, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker

# --- 1. 安全的密钥管理 ---
# 建议使用环境变量存储 API 密钥。
DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "ms-474fd0f2-79e5-4683-b908-cf3b228e151d")
ALI_API_KEY = os.environ.get("ALI_API_KEY", "sk-c1cf2eb1c1a846e3b3f729ff656cc5a2")
OPENROUTER_API_KEY_FREE = os.environ.get("OPENROUTER_API_KEY_FREE", "OPENROUTER_API_KEY_REDACTED")


# --- 2. 平台与模型配置中心 (唯一需要更新的地方) ---
PLATFORM_CONFIGS: Dict[str, Any] = {
    "dashscope": {
        "base_url": "https://api-inference.modelscope.cn/v1/",
        "api_key": DASHSCOPE_API_KEY,
        "models": {
            "qwen": "Qwen/Qwen3-235B-A22B-Instruct-2507",
        }
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": OPENROUTER_API_KEY_FREE,
        "models": {
            "dsv3": "deepseek/deepseek-chat-v3-0324:free",
            "qwen": "qwen/qwen3-235b-a22b-07-25:free",
        }
    },
    "ali": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": ALI_API_KEY,
        "models": {
            "qwen": "qwen-plus",
        }
    }
}

# --- 3. 独立的 SQLAlchemy 模型定义 ---
# 这个 Base 和 UserAIConfig 模型只属于这个文件，不与外部项目冲突。
Base = declarative_base()

class UserAIConfig(Base):
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

class UserAPIKey(Base):
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
        Base.metadata.create_all(self.engine)  # 确保表已创建（包含 API Key 表）
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

    def create_llm(self, platform: str, model: str, user_id: Optional[str] = None, **kwargs: Any) -> ChatOpenAI:
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

        return ChatOpenAI(
            base_url=config["base_url"],
            api_key=api_key,
            model_name=model_name,
            **default_params
        )

    def get_llm_for_user(
        self,
        user_id: Optional[str] = None,
        default_platform: str = "openrouter",
        default_model: str = "dsv3",
        **kwargs: Any
    ) -> ChatOpenAI:
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
            print(f"未找到用户 '{user_id}' 的配置，使用默认: {default_platform}/{default_model}")
            return self.create_llm(default_platform, default_model, user_id=user_id, **kwargs)


# --- 5. 使用示例 ---
# 当这个文件作为主程序运行时，以下代码会被执行，用于演示和测试。
if __name__ == "__main__":
    
    # 无需任何参数，直接初始化管理器
    # 它会自动在当前目录下创建和管理 llm_config.db
    manager = AIManager()
    
    user_id_1 = "user_project_A_001"
    user_id_2 = "user_project_B_002"

    print("\n" + "="*50)
    print("1. 为用户1保存配置 (ali/qwen)...")
    manager.save_config(user_id=user_id_1, platform="ali", model="qwen")
    
    print("\n" + "="*50)
    print("2. 获取用户1的LLM...")
    llm_1 = manager.get_llm_for_user(user_id_1)
    print(f"-> 成功创建LLM实例。模型: {llm_1.model_name}, Base URL: {llm_1.client.base_url}")
    
    print("\n" + "="*50)
    print("3. 获取用户2的LLM (该用户无配置，应使用默认值)...")
    llm_2 = manager.get_llm_for_user(user_id_2)
    print(f"-> 成功创建LLM实例。模型: {llm_2.model_name}, Base URL: {llm_2.client.base_url}")

    print("\n" + "="*50)
    print("4. 更新用户1的配置...")
    manager.save_config(user_id=user_id_1, platform="openrouter", model="dsv3")
    llm_1_updated = manager.get_llm_for_user(user_id_1)
    print(f"-> 更新后成功创建LLM实例。模型: {llm_1_updated.model_name}, Base URL: {llm_1_updated.client.base_url}")
    
    print("\n" + "="*50)
    print("演示完成。检查你的文件目录，应该会有一个 'llm_config.db' 文件。")
