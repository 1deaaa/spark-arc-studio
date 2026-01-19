from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from .auth import require_admin
from llm.llm_mgr.config import LLM_AUTO_KEY, USE_SYS_LLM_CONFIG, DEFAULT_PLATFORM_CONFIGS, SYSTEM_USER_ID, get_decrypted_api_key
from llm.llm_mgr.security import SecurityManager
from llm.llm_mgr.env_utils import get_env_var, set_env_var
import os
import yaml

admin_config_router = APIRouter(prefix="/api/admin/config", tags=["admin_config"])

class AdminConfigResponse(BaseModel):
    llm_auto_key: bool
    use_sys_llm_config: bool
    llm_key_set: bool  # LLM_KEY 是否已设置

class AdminConfigUpdate(BaseModel):
    llm_auto_key: Optional[bool] = None
    use_sys_llm_config: Optional[bool] = None

class LLMKeyUpdate(BaseModel):
    key: str

@admin_config_router.get("/global")
async def get_global_config(admin_user: dict = Depends(require_admin)):
    """获取全局配置状态"""
    try:
        # 检查 LLM_KEY（从 .env 加载）
        llm_key = get_env_var("LLM_KEY")
        
        return {
            "success": True,
            "data": {
                "llm_auto_key": LLM_AUTO_KEY,
                "use_sys_llm_config": USE_SYS_LLM_CONFIG,
                "llm_key_set": bool(llm_key)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@admin_config_router.post("/global")
async def update_global_config(data: AdminConfigUpdate, admin_user: dict = Depends(require_admin)):
    """更新全局配置 (仅内存生效，重启失效，如需持久化需写入 .env 或修改 config.py 源码 - 这里简化为运行时修改)"""
    # 注意：实际上修改全局变量在多进程/多 Worker 下可能不一致，
    # 但此处假设是单进程服务或仅用于演示。
    # 若要持久化，建议引入 .env 文件管理或数据库存储配置表。
    
    # 暂时只支持运行时修改，或者我们需要修改 llm_mgr_cfg.yaml 中的某些字段？
    # 目前 config.py 中的变量是硬编码或从环境变量读取的。
    # 为了简化实现，我们假设这些配置存储在数据库或特定配置文件中会更好。
    # 鉴于现有架构，我们先尝试通过环境变量或写入 llm_mgr_cfg.yaml 的元数据部分来实现持久化（如果有的话）。
    # 但 llm_mgr_cfg.yaml 主要存平台配置。
    
    # 方案：我们在 llm_mgr_cfg.yaml 中增加一个 metadata 字段来存储这些全局开关？
    # 或者直接修改内存变量，并提示用户重启后失效。
    
    # 考虑到用户需求是"最大化利用现有端口"，我们尽量复用。
    # 这里我们简单实现为：修改 config.py 对应的内存变量，并尝试更新 llm_mgr_cfg.yaml 中的自定义字段。
    
    global LLM_AUTO_KEY, USE_SYS_LLM_CONFIG
    
    # 这里需要引用 llm.llm_mgr.config 中的全局变量，但 Python 的 import 机制导致修改局部变量不影响其他模块。
    # 必须直接修改 sys.modules 中的模块属性，或者 config.py 提供 set_xxx 方法。
    #由于 config.py 没有 set 方法，我们尝试直接修改导入的模块属性（如果在同一个进程中）。
    
    import llm.llm_mgr.config as config_module
    
    if data.llm_auto_key is not None:
        config_module.LLM_AUTO_KEY = data.llm_auto_key
        # 同时尝试持久化到 llm_mgr_cfg.yaml 的 metadata
        _update_yaml_metadata("LLM_AUTO_KEY", data.llm_auto_key)
        
    if data.use_sys_llm_config is not None:
        config_module.USE_SYS_LLM_CONFIG = data.use_sys_llm_config
        _update_yaml_metadata("USE_SYS_LLM_CONFIG", data.use_sys_llm_config)
        
    return {"success": True, "message": "配置已更新 (部分配置可能需要重启生效)"}

@admin_config_router.post("/llm-key")
async def set_llm_key(data: LLMKeyUpdate, admin_user: dict = Depends(require_admin)):
    """设置 LLM_KEY (主密码)"""
    key = data.key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="密钥不能为空")
        
    try:
        # 1. 更新 SecurityManager（会自动设置环境变量和写入 .env）
        SecurityManager.get_instance().set_key(key, persist=True)
        
        return {"success": True, "message": "LLM_KEY 已设置并保存到 .env 文件"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _update_yaml_metadata(key: str, value: Any):
    """辅助函数：将配置写入 llm_mgr_cfg.yaml 的 metadata 字段"""
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(base_dir, "llm", "llm_mgr", "llm_mgr_cfg.yaml")
        
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        else:
            data = {}
            
        if "metadata" not in data:
            data["metadata"] = {}
            
        data["metadata"][key] = value
        
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)
    except Exception as e:
        print(f"更新配置文件失败: {e}")
