"""Director Agent - multi-round coordinator.

Inherits SparkBaseAgent to participate in the beacon mechanism and leverage
the standard chat()/chat_stream() pipeline with multi-round tool calling.

The Director uses bound tools to orchestrate specialist agents:
- list_chapters: understand the project's global chapter/scene structure
- read_chapter_scene: read detailed content of specific chapters/scenes
- delegate_task: dispatch tasks to specialist agents via the beacon bus

Routing decisions are made by the LLM through tool calls, replacing the
previous rule-based + LLM-JSON routing approach.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .communication import SparkBaseAgent
from .registry import get_agent_registry


class DirectorAgent(SparkBaseAgent):
    """
    导演 Agent - 用户交互层的入口，通过多轮工具调用实现协调。

    继承 SparkBaseAgent，使用标准 chat() / chat_stream() 流程。
    通过绑定的工具（list_chapters, read_chapter_scene, delegate_task）
    实现 LLM 驱动的自主路由和多轮协调。
    """

    def __init__(self, user_id: str, project_name: str = ""):
        super().__init__(agent_id="agent_director", user_id=str(user_id))
        self.project_name = project_name

    def _build_tool_system_prompt(self, base_prompt: str, active_context: str = None, **kwargs) -> str:
        """重写基类方法：在标准工具提示词基础上追加团队成员能力概览。"""
        # 先调用基类构建标准工具列表 + active_context
        system = super()._build_tool_system_prompt(base_prompt, active_context, **kwargs)

        # 追加团队成员概览（含各自的工具能力）
        team_block = self._build_team_capability_block()
        if team_block:
            system += team_block

        return system

    def _build_team_capability_block(self) -> str:
        """动态构建团队成员及其工具能力的提示词块。"""
        from .agent_tools import get_tools_for_agent

        lines = ["\n\n### 团队成员及工具能力"]
        lines.append("通过 `delegate_task` 委派任务时，了解各专家拥有的工具有助于精确描述任务。\n")

        for agent in get_agent_registry('zh-CN'):
            key = agent.get("key", "")
            if key == "agent_director" or agent.get("routable") is False:
                continue
            name = agent.get("name", key)
            desc = agent.get("description", "")
            tools = get_tools_for_agent(key)
            tool_names = [t.name for t in tools] if tools else []

            line = f"- **{name}** (`{key}`): {desc}"
            if tool_names:
                line += f"\n  工具: {', '.join(tool_names)}"
            lines.append(line)

        return "\n".join(lines) + "\n"
