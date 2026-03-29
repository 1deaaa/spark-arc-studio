"""
配置管理模块
负责加载 YAML 配置文件和管理常量
"""

from copy import deepcopy
from pathlib import Path
import os
import re
import shutil
import yaml
from typing import Dict, Any, Optional

from .env_utils import load_env, get_env_var
from .paths import get_config_file_path, get_packaged_config_template_path, ensure_mgr_home_exists
from .security import SecurityManager


_API_KEY_PLACEHOLDER_RE = re.compile(r"^\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}$")


# ---------------- 配置常量 ----------------

# 当 user_id = '-1' 时，代表系统运行于无用户/全局单用户模式，也称$系统模式$
# 这是一个虚拟的系统用户，从环境变量获取apikey，不需要用户自己设置apikey
SYSTEM_USER_ID = "-1"

# 如果为True 则当用户无apikey时 将尝试自动获取服务器apikey密钥
LLM_AUTO_KEY = True 
# 如果为True 则所有用户均使用系统平台配置 不能创建自己的平台和模型
USE_SYS_LLM_CONFIG = False

DEFAULT_USAGE_KEY = "main"
BUILTIN_USAGE_SLOTS = [
    {"key": DEFAULT_USAGE_KEY, "label": "主模型"},
    {"key": "fast", "label": "快速模型"},
    {"key": "reason", "label": "推理模型"},
]


# ---------------- 配置加载 ----------------

def _safe_decrypt(sec_mgr: SecurityManager, value: str) -> Any:
    if not value:
        return None
    if value.startswith("ENC:"):
        # 注意：仓库同步下发的 YAML 中可能携带其他环境生成的 ENC 密文。
        # 这类值在新站点首次拉取后无法直接解开属于正常现象；
        # 配置加载层统一将其视为“当前不可用”，等待管理员设置本机 LLM_KEY 并重新配置托管密钥。
        return sec_mgr.decrypt(value).to_optional_plaintext()
    return value


def is_api_key_placeholder(value: Any) -> bool:
    """判断 YAML api_key 是否为 {ENV_VAR} 占位符。"""
    return isinstance(value, str) and bool(_API_KEY_PLACEHOLDER_RE.match(value.strip()))


def resolve_api_key_reference(value: Any) -> Optional[str]:
    """解析 YAML api_key 原始值；若为占位符则读取对应环境变量。"""
    if not isinstance(value, str):
        return None

    raw_value = value.strip()
    if not raw_value:
        return None

    match = _API_KEY_PLACEHOLDER_RE.match(raw_value)
    if not match:
        return raw_value

    env_name = match.group(1)
    env_val = get_env_var(env_name)
    if not isinstance(env_val, str):
        return None

    env_val = env_val.strip()
    return env_val or None


def load_default_platform_configs_raw() -> Dict[str, Any]:
    """从配置文件加载原始平台配置，保留 api_key 的原始形态。"""
    ensure_mgr_home_exists()
    config_path: Path = get_config_file_path()

    if not config_path.exists():
        template_path = get_packaged_config_template_path()
        if template_path.exists() and template_path != config_path:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(template_path, config_path)
        else:
            raise FileNotFoundError(f"LLM_MGR:预设平台配置文件 '{config_path}' 不存在，请手动创建 llm_mgr_cfg.yaml")

    with config_path.open("r", encoding="utf-8") as f:
        configs = yaml.safe_load(f) or {}

    if not isinstance(configs, dict):
        raise ValueError("llm_mgr_cfg.yaml 顶层结构必须是字典")

    return configs


def save_default_platform_configs_raw(configs: Dict[str, Any]) -> str:
    """将平台配置原样写回 YAML 文件。"""
    ensure_mgr_home_exists()
    config_path = get_config_file_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(configs, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
    return str(config_path)


def load_default_platform_configs() -> Dict[str, Any]:
    """从配置文件加载并解析平台配置（缺少 LLM_KEY 也不中断）。"""
    configs = deepcopy(load_default_platform_configs_raw())

    sec_mgr = SecurityManager.get_instance()

    for name, cfg in configs.items():
        api_val = cfg.get("api_key")
        if not isinstance(api_val, str) or api_val.strip() == "":
            cfg["api_key"] = None
            continue

        api_val = api_val.strip()
        # 情况1: 已加密值
        if api_val.startswith("ENC:"):
            cfg["api_key"] = _safe_decrypt(sec_mgr, api_val)
            continue

        # 情况2: 占位符 {ENV_VAR}
        if is_api_key_placeholder(api_val):
            env_val = resolve_api_key_reference(api_val)
            if env_val:
                cfg["api_key"] = _safe_decrypt(sec_mgr, env_val)
            else:
                cfg["api_key"] = None
            continue

        # 情况3: 纯明文
        cfg["api_key"] = api_val

    return configs


def reload_default_platform_configs() -> Dict[str, Any]:
    """重新加载平台配置，并原地更新默认配置字典"""
    global DEFAULT_PLATFORM_CONFIGS
    new_configs = load_default_platform_configs()
    if isinstance(DEFAULT_PLATFORM_CONFIGS, dict):
        DEFAULT_PLATFORM_CONFIGS.clear()
        DEFAULT_PLATFORM_CONFIGS.update(new_configs)
    else:
        DEFAULT_PLATFORM_CONFIGS = new_configs
    return DEFAULT_PLATFORM_CONFIGS


def _ensure_env_setup():
    """在加载配置前检查环境"""
    # 首先加载 .env 文件
    load_env()

    key = get_env_var("LLM_KEY")
            
    if not key:
        gui_path = os.path.join(os.path.dirname(__file__), "llm_mgr_cfg_gui.py")
        if os.path.exists(gui_path):
            print("\n" + "!"*80)
            print("【重要提示】检测到系统未配置 LLM_KEY (API 密钥主密码)")
            print("所有 API Key 均需主密码加解密，否则将无法使用。")
            print("-" * 80)
            print(f"方法一 (推荐): 运行配置工具\n   python \"{os.path.normpath(gui_path)}\"")
            print("-" * 80)
            print("方法二: 通过 /api/admin/config/llm-key 接口或管理页设置 LLM_KEY")
            print("方法三: 在前端页面初始化向导中设置（如果有前端的话）")
            print("!"*80 + "\n")
            return


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
