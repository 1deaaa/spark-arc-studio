from __future__ import annotations

import json
import uuid

from langchain.tools import tool
from pydantic import BaseModel, Field

from agents.communication import (
    HANDOFF_COMPLETION_REPORT_TO_USER,
    HANDOFF_CONFIRMATION_PENDING,
    HANDOFF_DELIVERY_DIRECT_TO_USER,
    get_global_context,
    normalize_handoff_payload,
)
from agents.registry import AGENT_REGISTRY
from core.request_context import current_user_id, get_current_export_format, get_current_project_name

from .common import ToolExecutionContext


class DelegateTaskInput(BaseModel):
    target_agent: str = Field(description="目标专家 Agent 的 ID，可选值: agent_scriptwriter, agent_showrunner, agent_lorebook, agent_muse, agent_critic")
    task_description: str = Field(description="需要委派给该专家的具体任务描述，应包含足够的上下文信息")
    delivery_mode: str = Field(default=HANDOFF_DELIVERY_DIRECT_TO_USER, description="交付模式。direct_to_user=专家结果直接交付用户；return_to_director=专家结果回到导演继续复核/汇总")
    completion_mode: str = Field(default=HANDOFF_COMPLETION_REPORT_TO_USER, description="子任务完成后的即时行为。report_to_user=当前子任务完成后可直接面向用户交付；return_to_director=完成后回导演等待复核/汇总；silent_continue=完成后静默回导演并继续后续流水线，不单独向用户汇报")
    return_to: str = Field(default="agent_director", description="当需要复核或汇总时，结果应返回给哪个 Agent。默认 agent_director")
    grant_baton_to: str = Field(default="", description="本次委派后由哪个 Agent 接过旗帜（接力棒）。留空时默认授予 target_agent")
    requires_review: bool = Field(default=False, description="是否要求专家完成后必须回到导演复核。为 true 时会强制采用 return_to_director")
    user_confirmation_state: str = Field(default=HANDOFF_CONFIRMATION_PENDING, description="用户确认状态。already_confirmed=上游已确认可直接执行；needs_confirmation=仍需确认；not_required=本任务无需确认")


@tool(args_schema=DelegateTaskInput)
def delegate_task(
    target_agent: str,
    task_description: str,
    delivery_mode: str = HANDOFF_DELIVERY_DIRECT_TO_USER,
    completion_mode: str = HANDOFF_COMPLETION_REPORT_TO_USER,
    return_to: str = "agent_director",
    grant_baton_to: str = "",
    requires_review: bool = False,
    user_confirmation_state: str = HANDOFF_CONFIRMATION_PENDING,
) -> str:
    """将任务委派给指定专家 Agent。"""
    from agents.agent_factory import create_agent_instance

    user_id = current_user_id.get()
    project_name = get_current_project_name()
    if not user_id:
        return "委派任务失败：缺少用户上下文。"

    valid_agents = {a["key"] for a in AGENT_REGISTRY if a["key"] != "agent_director"}
    if target_agent not in valid_agents:
        return f"委派任务失败：未知的 Agent '{target_agent}'。可选: {', '.join(sorted(valid_agents))}"

    context = get_global_context()
    target_inst = create_agent_instance(target_agent, str(user_id), project_name or "")
    context.register(target_inst)
    target_inst.open_beacon()

    handoff_payload = normalize_handoff_payload(
        {
            "task_id": uuid.uuid4().hex,
            "target_agent": target_agent,
            "task_description": task_description,
            "delivery_mode": delivery_mode,
            "completion_mode": completion_mode,
            "return_to": return_to,
            "grant_baton_to": grant_baton_to,
            "requires_review": requires_review,
            "user_confirmation_state": user_confirmation_state,
            "delegated_by": "agent_director",
            "project_name": project_name,
            "export_format": get_current_export_format(),
        },
        sender_id="agent_director",
    )

    try:
        payload_str = json.dumps(handoff_payload, ensure_ascii=False)
        return f"__DELEGATE__:{payload_str}"
    except Exception as e:
        import traceback

        traceback.print_exc()
        return f"委派任务给 {target_agent} 失败: {e}"
