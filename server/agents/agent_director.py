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
        """在标准工具提示词后追加稳定的团队成员能力概览。"""
        system = super()._build_tool_system_prompt(base_prompt, active_context, **kwargs)

        team_block = self._build_team_capability_block()
        if team_block:
            system += team_block

        return system

    def _build_team_capability_block(self) -> str:
        """从注册表构建稳定团队概览，不读取项目状态或用户工具目录。"""
        lines = ["\n\n### 团队成员能力概览"]
        lines.append("通过 `delegate_task` 委派任务时，按专家职责描述目标与交付物。\n")

        for agent in get_agent_registry('zh-CN'):
            key = agent.get("key", "")
            if key == "agent_director" or agent.get("routable") is False:
                continue
            name = agent.get("name", key)
            desc = agent.get("description", "")
            line = f"- **{name}** (`{key}`): {desc}"
            lines.append(line)

        return "\n".join(lines) + "\n"
