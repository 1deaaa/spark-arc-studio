from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from .auth import require_admin
from .compliance_features import (
    is_force_public_share_review_effective,
    is_mainland_compliance_locale,
)
from .system_settings import (
    get_disable_public_share,
    get_force_public_share_review,
    set_disable_public_share,
    set_force_public_share_review,
)
from .verification import (
    VerificationConfigError,
    get_registration_verification_admin_view,
    update_registration_verification_settings,
)
from llm.agen_matchbox.config import LLM_AUTO_KEY, USE_SYS_LLM_CONFIG
from llm.agen_matchbox.env_utils import has_env_file_var
import os

admin_config_router = APIRouter(prefix="/api/admin/config", tags=["admin_config"])

class AdminConfigResponse(BaseModel):
    llm_auto_key: bool
    use_sys_llm_config: bool
    llm_key_set: bool  # LLM_KEY 是否已设置
    disable_public_share: bool
    force_public_share_review: bool
    force_public_share_review_effective: bool
    mainland_compliance_features_enabled: bool

class AdminConfigUpdate(BaseModel):
    llm_auto_key: Optional[bool] = None
    use_sys_llm_config: Optional[bool] = None
    disable_public_share: Optional[bool] = None
    force_public_share_review: Optional[bool] = None

class LLMKeyUpdate(BaseModel):
    key: str
    old_key: Optional[str] = None
    allow_clear_unrecoverable: bool = False

@admin_config_router.get("/global")
async def get_global_config(admin_user: dict = Depends(require_admin)):
    """获取全局配置状态"""
    from llm.agen_matchbox import matchbox
    try:
        # 仅以 agen_matchbox/.env 中的显式配置作为“已完成初始化”的判定依据。
        # 不能直接依赖 os.environ，因为 load_dotenv() 不会在 .env 缺失该键时自动清空
        # 已存在的进程环境变量，可能导致新环境被误判为“主密钥已设置”。
        llm_key_set = has_env_file_var("LLM_KEY")

        # 从 AIManager 获取最新状态
        sys_config = matchbox().get_system_config()
        
        return {
            "success": True,
            "data": {
                "llm_auto_key": sys_config["llm_auto_key"],
                "use_sys_llm_config": sys_config["use_sys_llm_config"],
                "llm_key_set": llm_key_set,
                "disable_public_share": get_disable_public_share(),
                "force_public_share_review": get_force_public_share_review(),
                "force_public_share_review_effective": is_force_public_share_review_effective(),
                "mainland_compliance_features_enabled": is_mainland_compliance_locale(),
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@admin_config_router.get("/public-share-state")
async def get_public_share_state():
    """公开接口：返回公开分享总开关状态。"""
    try:
        return {
            "success": True,
            "data": {
                "disable_public_share": get_disable_public_share(),
                "force_public_share_review": get_force_public_share_review(),
                "force_public_share_review_effective": is_force_public_share_review_effective(),
                "mainland_compliance_features_enabled": is_mainland_compliance_locale(),
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@admin_config_router.post("/global")
async def update_global_config(data: AdminConfigUpdate, admin_user: dict = Depends(require_admin)):
    """更新全局配置 (持久化到 matchbox_state.json)"""
    from llm.agen_matchbox import matchbox
    
    try:
        # 统一使用 AIManager.set_system_config 更新状态
        matchbox().set_system_config(
            use_sys_llm_config=data.use_sys_llm_config,
            llm_auto_key=data.llm_auto_key
        )

        if data.disable_public_share is not None:
            set_disable_public_share(bool(data.disable_public_share))

        if data.force_public_share_review is not None:
            set_force_public_share_review(bool(data.force_public_share_review))
        
    except Exception as e:
        print(f"Update AIManager state failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
    return {"success": True, "message": "配置已更新"}

@admin_config_router.post("/llm-key")
async def set_llm_key(data: LLMKeyUpdate, admin_user: dict = Depends(require_admin)):
    """设置 LLM_KEY (主密码)"""
    from llm.agen_matchbox import matchbox
    from llm.agen_matchbox.manager import MasterKeyMigrationRequiredError

    key = data.key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="密钥不能为空")
        
    try:
        # 统一走 AIManager 的主密钥迁移入口：首次设置、换密、历史密文清理都在同一条管线内完成。
        summary = matchbox().rotate_master_key(
            new_key=key,
            old_key=(data.old_key or None),
            persist=True,
            allow_clear_unrecoverable=bool(data.allow_clear_unrecoverable),
        )
        
        return {
            "success": True,
            "message": "LLM_KEY 已设置并保存到 .env 文件",
            "migration": summary,
        }
    except MasterKeyMigrationRequiredError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "master_key_migration_required",
                "message": str(e),
                "unresolved_count": e.unresolved_count,
                "sample_labels": e.sample_labels,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class RegistrationVerificationUpdate(BaseModel):
    enabled: bool
    provider: Optional[str] = None
    site_key: Optional[str] = None
    secret_key: Optional[str] = None  # None = 保持现有；空串 = 清除


def _serialize_verification_view(view) -> Dict[str, Any]:
    return {
        "enabled": view.enabled,
        "provider": view.provider,
        "site_key": view.site_key,
        "secret_key_set": view.secret_key_set,
        "supported_providers": list(view.supported_providers),
    }


@admin_config_router.get("/registration-verification")
async def get_registration_verification(admin_user: dict = Depends(require_admin)):
    """获取注册人机验证配置（admin 视角，密钥仅返回是否已设置）"""
    try:
        return {
            "success": True,
            "data": _serialize_verification_view(get_registration_verification_admin_view()),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@admin_config_router.post("/registration-verification")
async def update_registration_verification(
    data: RegistrationVerificationUpdate,
    admin_user: dict = Depends(require_admin),
):
    """开启/关闭注册人机验证；写入项目根 .env"""
    try:
        view = update_registration_verification_settings(
            enabled=bool(data.enabled),
            provider=data.provider,
            site_key=data.site_key,
            secret_key=data.secret_key,
        )
    except VerificationConfigError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "success": True,
        "message": "注册验证配置已更新",
        "data": _serialize_verification_view(view),
    }

