"""
配置管理模块
负责加载 YAML 配置文件和管理常量
"""

import os
import re
import yaml
from typing import Dict, Any

from .security import SecurityManager


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


# ---------------- 配置加载 ----------------

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
    # GUI/配置工具启动时允许缺少 LLM_KEY：否则会出现"用于配置密钥的工具本身无法启动"的循环依赖
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
            print("\n" + "="*60)
            print("⚠️ 错误：未检测到环境变量 LLM_KEY。")
            print("这是用于加解密 系统以及用户自定义API密钥 的主密码，必须进行设置。")
            print("\n请运行以下命令来启动配置工具进行设置：")
            print(f"   python \"{os.path.normpath(gui_path)}\"")
            print("="*60 + "\n")
            raise ValueError("缺少用于加解密系统及用户密钥的 环境变量 LLM_KEY ，请运行llm_mgr_cfg_gui.py进行设置。")


def get_decrypted_api_key(platform_name: str = None, base_url: str = None):
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


# 模块加载时执行环境检查
_ensure_env_setup()
DEFAULT_PLATFORM_CONFIGS = load_default_platform_configs()
