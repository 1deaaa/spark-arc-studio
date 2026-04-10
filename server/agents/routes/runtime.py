"""
Runtime API - Agent 运行态管理
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from core.auth import get_current_user
from core.request_context import get_current_locale
from agents.registry import get_agent_registry

from .schemas import AgentSignalToggleRequest

runtime_router = APIRouter()


@runtime_router.get('/api/agents/registry')
async def get_registry_api(user: dict = Depends(get_current_user)):
    """返回所有可用 Agent 的注册信息（按当前 locale 展开多语言字段）"""
    locale = get_current_locale()
    return get_agent_registry(locale)


_FORCED_OPEN_BEACON_AGENTS = {'agent_director'}
_FORCED_HORN_AGENTS = {'agent_director'}


def _serialize_runtime_signal_state(agent) -> dict:
    return {
        "isBeaconOpen": agent.signals.is_beacon_open,
        "hasHorn": agent.signals.has_horn,
        "hasBaton": agent.signals.has_baton,
        "allowedIntents": [],
        "beaconLocked": agent.agent_id in _FORCED_OPEN_BEACON_AGENTS,
        "hornLocked": agent.agent_id in _FORCED_HORN_AGENTS,
    }


def _ensure_runtime_agent(namespace: dict, agent_id: str, user_id: str):
    if agent_id not in namespace:
        if agent_id == 'agent_director':
            from agents.agent_director import DirectorAgent
            namespace[agent_id] = DirectorAgent(user_id=user_id, project_name='')
        else:
            from agents.communication import SparkBaseAgent
            namespace[agent_id] = SparkBaseAgent(agent_id, user_id)

    agent = namespace[agent_id]
    if agent_id in _FORCED_OPEN_BEACON_AGENTS:
        agent.open_beacon()
    if agent_id in _FORCED_HORN_AGENTS:
        agent.raise_horn()
    return agent


@runtime_router.get('/api/agents/runtime/signals')
async def get_runtime_signals(user: dict = Depends(get_current_user)):
    """获取所有 Agent 的信标 / 号角 / 旗帜 运行态。"""
    from agents.communication import get_global_context
    
    user_id = str(user['user_id'])
    ctx = get_global_context()
    
    registry = get_agent_registry(get_current_locale())
    if user_id not in ctx._user_namespaces:
        ctx._user_namespaces[user_id] = {}
        
    namespace = ctx._user_namespaces[user_id]
    for agent_info in registry:
        aid = agent_info['key']
        _ensure_runtime_agent(namespace, aid, user_id)

    result = {}
    for aid, agent in namespace.items():
        result[aid] = _serialize_runtime_signal_state(agent)
    return result


@runtime_router.post('/api/agents/runtime/beacon/toggle')
async def toggle_agent_beacon(data: AgentSignalToggleRequest, user: dict = Depends(get_current_user)):
    """切换 Agent 的信标状态（接收权）"""
    from agents.communication import get_global_context
    user_id = str(user['user_id'])
    ctx = get_global_context()
    
    namespace = ctx._user_namespaces.get(user_id)
    if not namespace or data.agent_id not in namespace:
        return JSONResponse(status_code=404, content={"error": "Agent 实例未找到"})
    
    agent = namespace[data.agent_id]
    if data.agent_id in _FORCED_OPEN_BEACON_AGENTS:
        return JSONResponse(status_code=403, content={"error": "该 Agent 的信标为系统强制开启，不能关闭"})
    if data.active:
        agent.open_beacon()
    else:
        agent.close_beacon()

    return _serialize_runtime_signal_state(agent)


@runtime_router.post('/api/agents/runtime/horn/toggle')
async def toggle_agent_horn(data: AgentSignalToggleRequest, user: dict = Depends(get_current_user)):
    """切换 Agent 的号角状态（主动通信权）"""
    from agents.communication import get_global_context
    user_id = str(user['user_id'])
    ctx = get_global_context()
    
    namespace = ctx._user_namespaces.get(user_id)
    if not namespace or data.agent_id not in namespace:
        return JSONResponse(status_code=404, content={"error": "Agent 实例未找到"})
    
    agent = namespace[data.agent_id]
    if data.agent_id in _FORCED_HORN_AGENTS:
        return JSONResponse(status_code=403, content={"error": "该 Agent 的号角为系统强制开启，不能关闭"})
    if data.active:
        agent.raise_horn()
    else:
        agent.lower_horn()

    return _serialize_runtime_signal_state(agent)


