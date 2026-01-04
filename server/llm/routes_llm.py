from fastapi import APIRouter, Depends, HTTPException, Query, Body
from typing import Optional, Dict, Any
import json
from pydantic import BaseModel

from core.auth import get_current_user
from llm.llm_mgr import LLM_Manager

llm_router = APIRouter()
manager = LLM_Manager

# ==================== Pydantic Models ====================

class UserSelectionRequest(BaseModel):
    platform_id: int
    model_id: int
    usage_key: Optional[str] = None

class UsageSlotCreateRequest(BaseModel):
    usage_key: str
    usage_label: Optional[str] = None
    platform_id: Optional[int] = None
    model_id: Optional[int] = None

class UsageSlotUpdateRequest(BaseModel):
    usage_key: str
    new_usage_key: Optional[str] = None
    new_usage_label: Optional[str] = None

class UsageSlotDeleteRequest(BaseModel):
    usage_key: str

class PlatformConfigRequest(BaseModel):
    platform_id: int
    api_key: Optional[str] = None

class PlatformCreateRequest(BaseModel):
    name: str
    base_url: str
    api_key: Optional[str] = None

class PlatformUpdateRequest(BaseModel):
    id: int
    name: str
    base_url: str

class ModelCreateRequest(BaseModel):
    platform_id: int
    model_name: str
    display_name: str
    extra_body: Optional[str] = None

class ModelUpdateRequest(BaseModel):
    id: int
    display_name: Optional[str] = None
    extra_body: Optional[str] = None

class AgentBindingSaveRequest(BaseModel):
    agent_name: str
    target_type: str  # 'usage' or 'direct'
    usage_key: Optional[str] = None
    platform_id: Optional[int] = None
    model_id: Optional[int] = None

# ==================== Routes ====================

@llm_router.get('/api/ai/user-platforms-models')
async def get_user_platforms_and_models(user: dict = Depends(get_current_user)):
    """获取用户所有可用平台及对应的模型列表。"""
    try:
        user_id = str(user['user_id'])
        data = manager.get_platform_models(user_id)
        return data
    except Exception as e:
        print(f"获取用户平台模型列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@llm_router.get('/api/ai/user-selection')
async def get_user_selection(
    usage_key: Optional[str] = Query(None),
    user: dict = Depends(get_current_user)
):
    """获取用户的AI模型选择。"""
    try:
        user_id = str(user['user_id'])
        selection = manager.get_user_selection_detail(user_id, usage_key=usage_key)
        return selection
    except ValueError as e:
        # 捕获 ValueError (如配置错误) 并返回 400，而不是 500
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"获取用户选择失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@llm_router.post('/api/ai/user-selection')
async def update_user_selection(
    data: UserSelectionRequest,
    user: dict = Depends(get_current_user)
):
    """更新用户的AI模型选择。"""
    user_id = str(user['user_id'])
    try:
        success = manager.save_user_selection(
            user_id,
            data.platform_id,
            data.model_id,
            usage_key=data.usage_key,
        )
        if success:
            return {"success": True}
        else:
            raise HTTPException(status_code=400, detail="保存失败")
    except Exception as e:
        print(f"保存用户选择失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# Usage Slots Management
@llm_router.post('/api/ai/user-selection/usage')
async def create_usage_slot(
    data: UsageSlotCreateRequest,
    user: dict = Depends(get_current_user)
):
    """创建用户用途槽"""
    user_id = str(user['user_id'])
    try:
        detail = manager.create_user_usage_slot(
            user_id,
            data.usage_key,
            usage_label=data.usage_label,
            platform_id=data.platform_id,
            model_id=data.model_id,
        )
        return detail
    except Exception as e:
        print(f"创建选中模型用途失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@llm_router.put('/api/ai/user-selection/usage')
async def update_usage_slot(
    data: UsageSlotUpdateRequest,
    user: dict = Depends(get_current_user)
):
    """编辑用途（重命名 key 或更改 label）"""
    user_id = str(user['user_id'])
    try:
        detail = manager.rename_user_usage_slot(
            user_id, 
            data.usage_key, 
            new_usage_key=data.new_usage_key, 
            new_label=data.new_usage_label
        )
        return detail
    except Exception as e:
        print(f"编辑用途失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@llm_router.delete('/api/ai/user-selection/usage')
async def delete_usage_slot(
    data: UsageSlotDeleteRequest,
    user: dict = Depends(get_current_user)
):
    """删除用途"""
    user_id = str(user['user_id'])
    try:
        manager.delete_user_usage_slot(user_id, data.usage_key)
        return {"success": True}
    except Exception as e:
        print(f"删除用途失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@llm_router.post('/api/ai/platform-config')
async def update_platform_config(
    data: PlatformConfigRequest,
    user: dict = Depends(get_current_user)
):
    """更新用户平台的配置，如 API Key。"""
    user_id = str(user['user_id'])
    
    try:
        success = manager.update_platform_config(user_id, data.platform_id, data.api_key)
        if success:
            return {"success": True}
        else:
            return {"success": True, "message": "No changes applied"}
    except Exception as e:
        print(f"更新平台配置失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# Platform Management
@llm_router.post('/api/ai/platform')
async def create_platform(
    data: PlatformCreateRequest,
    user: dict = Depends(get_current_user)
):
    """添加平台"""
    user_id = str(user['user_id'])
    
    try:
        plat = manager.add_platform(data.name, data.base_url, data.api_key, user_id)
        return {"success": True, "id": plat.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@llm_router.put('/api/ai/platform')
async def update_platform(
    data: PlatformUpdateRequest,
    user: dict = Depends(get_current_user)
):
    """更新平台信息（重命名 + 修改 URL）"""
    user_id = str(user['user_id'])
    try:
        manager.update_platform_details(user_id, data.id, data.name, data.base_url)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@llm_router.delete('/api/ai/platform')
async def delete_platform(
    id: int = Query(..., description="Platform ID"),
    user: dict = Depends(get_current_user)
):
    """删除平台"""
    user_id = str(user['user_id'])
    try:
        manager.delete_platform(user_id, id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Model Management
@llm_router.post('/api/ai/model')
async def create_model(
    data: ModelCreateRequest,
    user: dict = Depends(get_current_user)
):
    """添加模型"""
    user_id = str(user['user_id'])
    
    extra_body_dict = None
    if data.extra_body:
        try:
            extra_body_dict = json.loads(data.extra_body)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON in extra_body")

    try:
        model = manager.add_model(
            data.platform_id, 
            data.model_name, 
            data.display_name, 
            user_id, 
            extra_body_dict
        )
        return {"success": True, "id": model.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@llm_router.put('/api/ai/model')
async def update_model(
    data: ModelUpdateRequest,
    user: dict = Depends(get_current_user)
):
    """更新模型"""
    user_id = str(user['user_id'])
    
    # 检查字段是否在请求中显式设置
    fields_set = getattr(data, "__fields_set__", None) or getattr(data, "model_fields_set", set())
    
    display_name = data.display_name if 'display_name' in fields_set else None
    
    extra_body_dict = None
    # 只有当 extra_body 显式包含在请求中时，才进行处理
    if 'extra_body' in fields_set:
        if data.extra_body:
            try:
                extra_body_dict = json.loads(data.extra_body)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid JSON in extra_body")
        else:
            # 显式传递了 null 或空字符串，意为清空 -> 传递空字典给 admin 以触发清空逻辑
            extra_body_dict = {} 
    else:
        # 未包含在请求中，传递 None 给 admin，admin 会跳过更新
        extra_body_dict = None

    try:
        manager.update_model(user_id, data.id, display_name, extra_body_dict)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@llm_router.delete('/api/ai/model')
async def delete_model(
    id: int = Query(..., description="Model ID"),
    user: dict = Depends(get_current_user)
):
    """删除模型"""
    user_id = str(user['user_id'])
    try:
        manager.delete_model(user_id, id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Agent Bindings Management
@llm_router.get('/api/ai/agent-bindings')
async def get_agent_bindings(user: dict = Depends(get_current_user)):
    """获取用户的 Agent 绑定配置"""
    user_id = str(user['user_id'])
    try:
        return manager.get_agent_bindings(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@llm_router.post('/api/ai/agent-bindings')
async def save_agent_binding(
    data: AgentBindingSaveRequest,
    user: dict = Depends(get_current_user)
):
    """保存 Agent 绑定配置"""
    user_id = str(user['user_id'])
    try:
        success = manager.save_agent_binding(
            user_id,
            data.agent_name,
            data.target_type,
            usage_key=data.usage_key,
            platform_id=data.platform_id,
            model_id=data.model_id
        )
        return {"success": success}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ==================== Usage Statistics ====================

@llm_router.get('/api/ai/usage-stats')
async def get_usage_stats(user: dict = Depends(get_current_user)):
    """获取用户的模型使用统计"""
    user_id = str(user['user_id'])
    try:
        stats = manager.get_user_usage_stats(user_id)
        return {"stats": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@llm_router.delete('/api/ai/usage-stats')
async def reset_usage_stats(
    model_id: Optional[int] = Query(None, description="Model ID to reset, or all if not provided"),
    user: dict = Depends(get_current_user)
):
    """重置用户的模型使用统计"""
    user_id = str(user['user_id'])
    try:
        success = manager.reset_user_usage_stats(user_id, model_id)
        return {"success": success}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
