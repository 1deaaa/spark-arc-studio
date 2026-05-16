from agents.agent_utils import load_prompt
from agents.tools.registry import (
    CRITIC_TOOLS,
    DIRECTOR_TOOLS,
    SCRIPTWRITER_TOOLS,
    get_tools_for_agent,
)


def _tool_names(tools) -> set[str]:
    return {getattr(tool, "name", "") for tool in tools}


def test_graphrag_tool_is_mounted_on_target_agent_registries():
    assert "graph_rag_tool" in _tool_names(DIRECTOR_TOOLS)
    assert "graph_rag_tool" in _tool_names(SCRIPTWRITER_TOOLS)
    assert "graph_rag_tool" in _tool_names(CRITIC_TOOLS)


def test_graphrag_tool_is_visible_through_get_tools_for_agent():
    assert "graph_rag_tool" in _tool_names(get_tools_for_agent("agent_director"))
    assert "graph_rag_tool" in _tool_names(get_tools_for_agent("agent_scriptwriter"))
    assert "graph_rag_tool" in _tool_names(get_tools_for_agent("agent_critic"))


def test_target_agent_prompts_include_graphrag_guidance():
    assert "graph_rag_tool" in (load_prompt("director").get("tool_rules") or "")
    assert "graph_rag_tool" in (load_prompt("scriptwriter").get("tool_rules") or "")
    assert "graph_rag_tool" in (load_prompt("critic").get("tool_rules") or "")
