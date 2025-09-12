
import os
from typing import Dict, Any, Optional, List
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from sqlalchemy import create_engine, Column, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker, relationship


# 环境变量默认平台 API Key（可为空） 当不使用用户系统也就是不指定user_id的时候 使用默认平台设置 称作系统模式
MODELSCOPE_API_KEY = os.environ.get("MODELSCOPE_API_KEY")
ALIYUN_API_KEY = os.environ.get("ALIYUN_API_KEY")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
GEMINIX_API_KEY = os.environ.get("GEMINIX_API_KEY")


DEFAULT_PLATFORM_CONFIGS: Dict[str, Any] = {
    "魔搭社区": {
        "base_url": "https://api-inference.modelscope.cn/v1/",
        "api_key": MODELSCOPE_API_KEY,
        "models": {
            "Qwen3 235B 2507": "Qwen/Qwen3-235B-A22B-Instruct-2507",
            "DeepSeek V3.1": "deepseek-ai/DeepSeek-V3.1",
        },
    },
    "OpenRouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": OPENROUTER_API_KEY,
        "models": {
            "DeepSeek V3-0324": "deepseek/deepseek-chat-v3-0324:free",
            "DeepSeek V3.1": "deepseek/deepseek-chat-v3.1:free",
        },
    },
    "阿里云百炼": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": ALIYUN_API_KEY,
        "models": {"通义千问Plus": "qwen-plus-latest", "通义千问极速版": "qwen-flash"},
    },
    "Google AIStudio": {
        "base_url": "http://dx.nb.s1.natgo.cn:10240/v1",
        "api_key": GEMINIX_API_KEY,
        "models": {
            "哈基米flash版": "gemini-2.5-flash",
            "哈基米pro版": "gemini-2.5-pro",
        },
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
    # 关系：平台 -> 模型
    models = relationship("LLModels", backref="platform", cascade="all, delete-orphan")


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
        Integer, ForeignKey("llm_platforms.id"), nullable=False
    )
    selected_model_id = Column(
        Integer, ForeignKey("llm_platform_models.id"), nullable=False
    )
    platform = relationship("LLMPlatform")
    model = relationship("LLModels")


class AIManager:
    def __init__(self, db_name: str = "llm_config.db"):
        base_dir = os.path.abspath(os.path.dirname(__file__))
        db_path = os.path.join(base_dir, db_name)
        db_url = f"sqlite:///{db_path}"
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self._ensure_defaults()
        # 从硬编码的字典中获取默认平台和模型的名称作为唯一真实来源
        default_platform_name = next(iter(DEFAULT_PLATFORM_CONFIGS))
        default_model_config = DEFAULT_PLATFORM_CONFIGS[default_platform_name]["models"]
        default_model_display_name = next(iter(default_model_config))
        
        self._default_platform_name = default_platform_name
        self._default_model_name = default_model_display_name


    def _ensure_defaults(self):
        """
        同步数据库中的系统默认平台模板（user_id=None），使其与 DEFAULT_PLATFORM_CONFIGS 配置保持一致。
        """
        with self.Session() as session:
            changed = False
            config_platform_names = set(DEFAULT_PLATFORM_CONFIGS.keys())

            for name, cfg in DEFAULT_PLATFORM_CONFIGS.items():
                plat = (
                    session.query(LLMPlatform)
                    .filter_by(name=name, user_id=None)
                    .first()
                )
                if not plat:
                    plat = LLMPlatform(
                        name=name, base_url=cfg["base_url"], api_key=cfg.get("api_key")
                    )
                    session.add(plat)
                    session.flush()
                    print(f"创建新平台模板: {name}")
                    changed = True
                else:
                    if plat.base_url != cfg["base_url"] or plat.api_key != cfg.get("api_key"):
                        plat.base_url = cfg["base_url"]
                        plat.api_key = cfg.get("api_key")
                        print(f"更新平台模板属性: {name}")
                        changed = True

                db_models = {m.display_name: m.model_name for m in plat.models}
                config_models = cfg.get("models", {})
                if db_models != config_models:
                    print(f"同步平台模板模型: {name}")
                    session.query(LLModels).filter_by(platform_id=plat.id).delete()
                    for display_name, model_name in config_models.items():
                        session.add(
                            LLModels(
                                platform_id=plat.id,
                                model_name=model_name,
                                display_name=display_name,
                            )
                        )
                    changed = True
            
            db_platforms = (
                session.query(LLMPlatform).filter(LLMPlatform.user_id.is_(None)).all()
            )
            for plat in db_platforms:
                if plat.name not in config_platform_names:
                    print(f"删除过时的平台模板: {plat.name}")
                    session.delete(plat)
                    changed = True

            if changed:
                print("默认平台模板已更新，正在提交到数据库...")
                session.commit()
            else:
                print("默认平台模板与数据库一致，无需更新。")

    def _initialize_user_platforms(self, user_id: str, session):
        """
        检查用户是否已有平台，如果没有，则从系统模板复制一份。
        """
        user_has_platforms = session.query(LLMPlatform).filter_by(user_id=user_id).first()
        if user_has_platforms:
            return

        print(f"为用户 {user_id} 初始化平台配置...")
        system_platforms = session.query(LLMPlatform).filter(LLMPlatform.user_id.is_(None)).all()
        for sys_plat in system_platforms:
            # 复制平台
            user_plat = LLMPlatform(
                name=sys_plat.name,
                base_url=sys_plat.base_url,
                api_key=None,  # API Key 留空给用户填写
                user_id=user_id,
            )
            session.add(user_plat)
            session.flush()  # 获取新平台的 ID
            
            # 复制模型
            for sys_model in sys_plat.models:
                user_model = LLModels(
                    platform_id=user_plat.id,
                    model_name=sys_model.model_name,
                    display_name=sys_model.display_name,
                )
                session.add(user_model)
        session.commit()
        print(f"用户 {user_id} 平台初始化完成。")

    def add_platform(
        self,
        name: str,
        base_url: str,
        api_key: Optional[str] = None,
        user_id: str = None,
    ):
        """创建一个用户自定义平台。"""
        if not (name and base_url):
            raise ValueError("name / base_url 必填")
        if user_id is None:
            raise ValueError("用户自定义平台必须绑定 user_id")
        
        with self.Session() as session:
            self._initialize_user_platforms(user_id, session)
            # 检查用户自己的平台名称是否重复
            if session.query(LLMPlatform).filter_by(name=name, user_id=user_id).first():
                raise ValueError(f"平台名称 '{name}' 已存在")
            
            p = LLMPlatform(
                name=name, base_url=base_url, api_key=api_key, user_id=user_id
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
        """为指定平台添加模型，确保用户只能操作自己的平台"""
        if not (platform_id and model_name):
            raise ValueError("platform_id / model_name 必填")
        if user_id is None:
            raise ValueError("为模型绑定 user_id")

        with self.Session() as session:
            # 验证平台属于该用户
            plat = session.query(LLMPlatform).filter_by(id=platform_id, user_id=user_id).first()
            if not plat:
                raise ValueError("平台不存在或无权限")

            if not display_name:
                display_name = model_name
            
            if session.query(LLModels).filter_by(platform_id=plat.id, model_name=model_name).first():
                raise ValueError("模型名已存在于该平台")

            m = LLModels(
                platform_id=plat.id, model_name=model_name, display_name=display_name
            )
            session.add(m)
            session.commit()
            return m

    def _platform_dict(self, plat: LLMPlatform, session) -> Dict[str, Any]:
        models = session.query(LLModels).filter_by(platform_id=plat.id).all()
        return {
            "id": plat.id,
            "base_url": plat.base_url,
            "api_key": plat.api_key,
            "user_id": plat.user_id,
            "models": {m.display_name: m.model_name for m in models},
        }

    # ===== 用户级查询 =====
    def get_user_available_platforms(self, user_id: str) -> Dict[str, Any]:
        """获取用户可用的平台（均为用户私有）"""
        with self.Session() as session:
            self._initialize_user_platforms(user_id, session)
            platforms = session.query(LLMPlatform).filter_by(user_id=user_id).all()
            out: Dict[str, Any] = {}
            for p in platforms:
                out[p.name] = self._platform_dict(p, session)
            return out

    def get_user_platforms(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户所有平台的简要列表（ID和名称）"""
        with self.Session() as session:
            self._initialize_user_platforms(user_id, session)
            platforms = session.query(LLMPlatform.id, LLMPlatform.name).filter_by(user_id=user_id).all()
            return [{"id": p.id, "name": p.name} for p in platforms]

    def get_models_for_platform(self, platform_id: int, user_id: str) -> List[Dict[str, Any]]:
        """获取指定平台下的所有模型列表"""
        with self.Session() as session:
            # 验证平台所有权
            platform = session.query(LLMPlatform).filter_by(id=platform_id, user_id=user_id).first()
            if not platform:
                raise ValueError("平台不存在或无权限访问")
            
            models = session.query(LLModels).filter_by(platform_id=platform_id).all()
            return [
                {
                    "id": m.id,
                    "display_name": m.display_name,
                    "model_name": m.model_name,
                }
                for m in models
            ]

    def get_user_plat_models(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户可用的所有平台及对应模型列表（一次完全获取平台和对应的模型）"""
        with self.Session() as session:
            self._initialize_user_platforms(user_id, session)
            
            results = (
                session.query(
                    LLMPlatform.id.label("platform_id"),
                    LLMPlatform.name.label("platform_name"),
                    LLMPlatform.base_url,
                    LLMPlatform.api_key,
                    LLModels.id.label("model_id"),
                    LLModels.display_name,
                    LLModels.model_name,
                )
                .join(LLModels, LLMPlatform.id == LLModels.platform_id)
                .filter(LLMPlatform.user_id == user_id)
                .all()
            )

            flat: List[Dict[str, Any]] = []
            for r in results:
                flat.append(
                    {
                        "platform_id": r.platform_id,
                        "platform_name": r.platform_name,
                        "model_id": r.model_id,
                        "display_name": r.display_name,
                        "model_name": r.model_name,
                        "base_url": r.base_url,
                        "api_key_set": bool(r.api_key),
                    }
                )
            return flat

    def ensure_user_has_config(self, user_id: str) -> UserAIConfig:
        """确保用户有AI配置，并返回该配置对象"""
        with self.Session() as session:
            self._initialize_user_platforms(user_id, session)
            
            cfg = session.query(UserAIConfig).filter_by(user_id=user_id).first()
            if cfg:
                return cfg

            # 为用户创建默认配置，使用从字典缓存的名称查找平台和模型
            default_platform = session.query(LLMPlatform).filter_by(
                user_id=user_id, name=self._default_platform_name
            ).first()
            if not default_platform:
                raise RuntimeError(f"用户 {user_id} 的平台列表中未找到默认平台 '{self._default_platform_name}'。")

            default_model = session.query(LLModels).filter_by(
                platform_id=default_platform.id, display_name=self._default_model_name
            ).first()
            if not default_model:
                raise RuntimeError(f"平台 '{self._default_platform_name}' 中未找到默认模型 '{self._default_model_name}'。")

            cfg = UserAIConfig(
                user_id=user_id,
                selected_platform_id=default_platform.id,
                selected_model_id=default_model.id,
            )
            session.add(cfg)
            session.commit()
            return cfg

    def save_user_selection(
        self, user_id: str, platform_id: int, model_id: int
    ) -> bool:
        """保存用户的平台和模型选择配置"""
        try:
            with self.Session() as session:
                # 验证平台属于该用户
                platform_q = session.query(LLMPlatform).filter_by(id=platform_id, user_id=user_id).first()
                if not platform_q:
                    raise ValueError(f"平台ID {platform_id} 不存在或无权限")

                # 验证模型属于该平台
                model_q = (
                    session.query(LLModels)
                    .filter_by(id=model_id, platform_id=platform_id)
                    .first()
                )
                if not model_q:
                    raise ValueError(
                        f"模型ID {model_id} 不存在或不属于平台ID {platform_id}"
                    )

                cfg = self.ensure_user_has_config(user_id)
                cfg.selected_platform_id = platform_id
                cfg.selected_model_id = model_id
                session.commit()
                return True
        except Exception as e:
            print(f"[AIManager] 保存用户配置失败: {e}")
            return False
    
    def get_user_selection_detail(self, user_id: str) -> Dict[str, Any]:
        """返回用户当前选择的详细信息"""
        with self.Session() as session:
            cfg = self.ensure_user_has_config(str(user_id))
            
            # 确保所选的平台和模型仍然有效
            platform_obj = session.query(LLMPlatform).filter_by(id=cfg.selected_platform_id, user_id=user_id).first()
            model_obj = session.query(LLModels).filter_by(id=cfg.selected_model_id).first()

            # 如果任意对象缺失或不匹配，重置为用户的默认配置
            if not platform_obj or not model_obj or model_obj.platform_id != platform_obj.id:
                user_default_platform = session.query(LLMPlatform).filter_by(user_id=user_id, name=self._default_platform_name).first()
                if not user_default_platform:
                    user_default_platform = session.query(LLMPlatform).filter_by(user_id=user_id).order_by(LLMPlatform.id).first()
                
                user_default_model = session.query(LLModels).filter_by(platform_id=user_default_platform.id).order_by(LLModels.id).first()
                
                if user_default_platform and user_default_model:
                    cfg.selected_platform_id = user_default_platform.id
                    cfg.selected_model_id = user_default_model.id
                    session.commit()
                    platform_obj, model_obj = user_default_platform, user_default_model
                else:
                    # 极端情况，用户没有任何平台或模型了
                    return {}

            return {
                "platform": platform_obj.name,
                "platform_id": platform_obj.id,
                "base_url": platform_obj.base_url,
                "model_display_name": model_obj.display_name,
                "model_id": model_obj.id,
                "model_name": model_obj.model_name,
                "api_key_set": bool(platform_obj.api_key),
            }

    def create_llm(
        self,
        platform_id: int,
        model_id: int,
        user_id: Optional[str] = None,
        **kwargs: Any,
    ) -> BaseChatModel:
        """创建 LLM 实例（基于ID，确保权限控制）"""
        with self.Session() as session:
            if user_id:
                # 用户模式下，平台必须属于该用户
                platform_obj = session.query(LLMPlatform).filter_by(id=platform_id, user_id=user_id).first()
            else:
                # 系统模式（无用户），只能使用系统模板
                platform_obj = session.query(LLMPlatform).filter_by(id=platform_id, user_id=None).first()
                
            if not platform_obj:
                raise ValueError("平台不存在或无权限")

            model_obj = (
                session.query(LLModels)
                .filter_by(id=model_id, platform_id=platform_id)
                .first()
            )
            if not model_obj:
                raise ValueError("模型不存在或不属于该平台")

            params = {"streaming": True, **kwargs}
            
            if not platform_obj.base_url:
                raise ValueError("平台缺少 base_url")

            return ChatOpenAI(
                base_url=platform_obj.base_url,
                api_key=platform_obj.api_key,
                model_name=model_obj.model_name,
                **params,
            )

    def get_user_llm(
        self, user_id: Optional[str] = None, **kwargs: Any
    ) -> BaseChatModel:
        """获取用户配置的 LLM 实例"""
        if not user_id:
            # 系统模式，使用默认名称查找系统模板
            with self.Session() as session:
                platform_obj = session.query(LLMPlatform).filter_by(
                    user_id=None, name=self._default_platform_name
                ).first()
                if not platform_obj:
                    raise RuntimeError(f"系统模板中未找到默认平台 '{self._default_platform_name}'")
                
                model_obj = session.query(LLModels).filter_by(
                    platform_id=platform_obj.id, display_name=self._default_model_name
                ).first()
                if not model_obj:
                    raise RuntimeError(f"系统平台 '{self._default_platform_name}' 中未找到默认模型 '{self._default_model_name}'")
                
                return self.create_llm(platform_obj.id, model_obj.id, None, **kwargs)
        else:
            # 用户模式
            cfg = self.ensure_user_has_config(user_id)
            return self.create_llm(
                cfg.selected_platform_id, cfg.selected_model_id, user_id, **kwargs
            )

    # 远程探测
    def probe_platform_models(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 8.0,
        raise_on_error: bool = False,
    ) -> List[Dict[str, Any]]:
        try:
            import requests
        except ImportError:
            if raise_on_error: raise
            return []
        if not base_url:
            if raise_on_error: raise ValueError("base_url 不能为空")
            return []
        if not api_key:
            if raise_on_error: raise ValueError("api_key 不能为空")
            return []
        
        url = base_url.rstrip("/")
        if not url.endswith("/models"):
            url = f"{url.rstrip('/')}/v1/models"

        headers = {"Authorization": f"Bearer {api_key}"}
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            if resp.status_code == 401:
                if raise_on_error: raise PermissionError('鉴权失败 401')
                return []
            if not resp.ok:
                if raise_on_error: raise RuntimeError(f"探测失败 {resp.status_code} {resp.text[:120]}")
                return []
            js = resp.json(); items = js.get('data') if isinstance(js, dict) else None
            if not isinstance(items, list):
                if raise_on_error: raise ValueError('响应缺少 data 列表')
                return []
            out: List[Dict[str, Any]] = []
            for it in items:
                if isinstance(it, dict) and 'id' in it:
                    out.append({'id': it['id'], 'raw': it})
            return out
        except Exception as e:
            if raise_on_error: raise
            print(f"[AIManager] 探测失败: {e}")
            return []