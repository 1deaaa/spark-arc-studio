from __future__ import annotations

import json
import uuid
from typing import Literal

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
    target_agent: Literal[
        "agent_scriptwriter",
        "agent_showrunner",
        "agent_lorebook",
        "agent_muse",
        "agent_critic",
    ] = Field(description="唯一的目标专家 ID。必须从枚举中选择一个，不要填写专家中文名。")
    task_description: str = Field(
        min_length=1,
        description="专家可独立执行的完整任务说明，写清目标、范围、已有事实和交付要求；不要在这里重复工具参数。",
    )
    tracker_item_id: str | None = Field(
        default=None,
        description=(
            "当前委派对应的导演进度板条目 ID。存在进度板时优先逐字复制当前条目的真实 id；"
            "省略时系统仅会在唯一进行中条目等无歧义场景自动绑定。"
        ),
    )
    completion_mode: Literal[
        "report_to_user",
        "return_to_director",
        "silent_continue",
    ] = Field(
        default=HANDOFF_COMPLETION_REPORT_TO_USER,
        description=(
            "完成后的控制流：单步任务用 report_to_user；需要导演复核后统一回复用 return_to_director；"
            "还有后续委派步骤时必须用 silent_continue。"
        ),
    )
    chapter_name: str | None = Field(default=None, description="仅委派编剧写具体正文时填写：章节可读标题，不含自行编造的编号。其他专家不要传。")
    scene_name: str | None = Field(default=None, description="仅委派编剧写具体正文时填写：场景可读标题，不含自行编造的编号。其他专家不要传。")
    scene_file_path: str | None = Field(default=None, description="仅委派编剧且已有目标文件时填写：stories 下的相对路径。没有可靠路径就省略。")
    scene_guidance: str | None = Field(default=None, description="仅委派编剧时填写：当前场景必须落实的导演指引。没有额外指引就省略。")
    scene_characters: list[str] | None = Field(default=None, description="仅委派编剧时填写：当前场景确定登场的角色名数组。未知时省略，不要传字符串。")


@tool(args_schema=DelegateTaskInput)
def delegate_task(
    target_agent: str,
    task_description: str,
    tracker_item_id: str | None = None,
    delivery_mode: str = HANDOFF_DELIVERY_DIRECT_TO_USER,
    completion_mode: str = HANDOFF_COMPLETION_REPORT_TO_USER,
    return_to: str = "agent_director",
    grant_baton_to: str = "",
    requires_review: bool = False,
    user_confirmation_state: str = HANDOFF_CONFIRMATION_PENDING,
    chapter_name: str | None = None,
    scene_name: str | None = None,
    scene_file_path: str | None = None,
    scene_guidance: str | None = None,
    scene_characters: list[str] | None = None,
) -> str:
    """将一个任务委派给一位专家。

    最小调用只传 target_agent 和 task_description。单步交付可省略
    completion_mode；多步骤流水线的中间委派将其设为 silent_continue。
    存在导演任务板时传 tracker_item_id 关联当前条目。chapter_name 等场景字段
    只属于 agent_scriptwriter，其他专家不要传。
    """
    from agents.agent_factory import create_agent_instance

    user_id = current_user_id.get()
    project_name = get_current_project_name()
    if not user_id:
        return "委派任务失败：缺少用户上下文。"

    valid_agents = {
        a["key"]
        for a in AGENT_REGISTRY
        if a["key"] != "agent_director"
        and a.get("participatesInBeaconBus") is not False
        and a.get("visibleInChat") is not False
    }
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
            "tracker_item_id": tracker_item_id or "",
            "delivery_mode": delivery_mode,
            "completion_mode": completion_mode,
            "return_to": return_to,
            "grant_baton_to": grant_baton_to,
            "requires_review": requires_review,
            "user_confirmation_state": user_confirmation_state,
            "delegated_by": "agent_director",
            "project_name": project_name,
            "export_format": get_current_export_format(),
            "chapter_name": chapter_name or "",
            "scene_name": scene_name or "",
            "scene_file_path": scene_file_path or "",
            "scene_guidance": scene_guidance or "",
            "scene_characters": scene_characters or [],
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
