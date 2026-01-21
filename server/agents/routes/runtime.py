"""
Runtime API - Agent 运行态管理
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from core.auth import get_current_user
from agents.registry import get_agent_registry

from .schemas import BeaconToggleRequest

runtime_router = APIRouter()


@runtime_router.get('/api/agents/registry')
async def get_registry_api(user: dict = Depends(get_current_user)):
    """返回所有可用 Agent 的注册信息"""
    return get_agent_registry()


# 不参与信标机制的 Agent（用户交互层）
_USER_LAYER_AGENTS = {'agent_director', 'agent_router'}


@runtime_router.get('/api/agents/runtime/beacons')
async def get_runtime_beacons(user: dict = Depends(get_current_user)):
    """获取所有 Agent 的信标与通信权状态
    
    注意：agent_director 和 agent_router 不参与信标机制，因为它们属于用户交互层。
    信标机制仅用于专家 Agent 之间的自主通信。
    """
    from agents.communication import get_global_context, SparkBaseAgent
    
    user_id = str(user['user_id'])
    ctx = get_global_context()
    
    registry = get_agent_registry()
    if user_id not in ctx._user_namespaces:
        ctx._user_namespaces[user_id] = {}
        
    namespace = ctx._user_namespaces[user_id]
    for agent_info in registry:
        aid = agent_info['key']
        # 跳过用户交互层 Agent，它们不参与信标机制
        if aid in _USER_LAYER_AGENTS:
            continue
        if aid not in namespace:
            # 默认情况下，所有专家 Agent 的信标和通信权都是关闭的
            # 信标状态应由 Agent 在协作任务中自主控制，而非硬编码
            namespace[aid] = SparkBaseAgent(aid, user_id)

    result = {}
    for aid, agent in namespace.items():
        result[aid] = {
            "isOpen": agent.beacon.is_open,
            "hasCommunicationRight": agent.beacon.has_communication_right,
            "allowedIntents": []
        }
    return result


@runtime_router.post('/api/agents/runtime/beacon/toggle')
async def toggle_agent_beacon(data: BeaconToggleRequest, user: dict = Depends(get_current_user)):
    """切换 Agent 的信标状态（接收权）"""
    from agents.communication import get_global_context
    user_id = str(user['user_id'])
    ctx = get_global_context()
    
    namespace = ctx._user_namespaces.get(user_id)
    if not namespace or data.agent_id not in namespace:
        return JSONResponse(status_code=404, content={"error": "Agent 实例未找到"})
    
    agent = namespace[data.agent_id]
    if data.active:
        agent.open_beacon()
    else:
        agent.close_beacon()
        
    return {
        "isOpen": agent.beacon.is_open,
        "hasCommunicationRight": agent.beacon.has_communication_right,
        "allowedIntents": []
    }


@runtime_router.post('/api/agents/runtime/communication/toggle')
async def toggle_agent_communication(data: BeaconToggleRequest, user: dict = Depends(get_current_user)):
    """切换 Agent 的通信权（主动发起权）"""
    from agents.communication import get_global_context
    user_id = str(user['user_id'])
    ctx = get_global_context()
    
    namespace = ctx._user_namespaces.get(user_id)
    if not namespace or data.agent_id not in namespace:
        return JSONResponse(status_code=404, content={"error": "Agent 实例未找到"})
    
    agent = namespace[data.agent_id]
    if data.active:
        agent.open_communication_right()
    else:
        agent.close_communication_right()
        
    return {
        "isOpen": agent.beacon.is_open,
        "hasCommunicationRight": agent.beacon.has_communication_right,
        "allowedIntents": []
    }


