from __future__ import annotations

from agents.tools.attachment import read_attachment_chunk
from agents.tools.chat_history import search_chat_history
from agents.tools.automation import (
    check_scriptwriter_status,
    trigger_auto_write,
    update_project_story_tags,
    work_tracker,
)
from agents.tools.delegation import delegate_task
from agents.tools.lorebook import patch_worldview, rewrite_all_characters, rewrite_worldview, update_character
from agents.tools.muse import (
    bind_inspiration_to_current_project,
    capture_inspiration,
    list_inspirations,
    read_inspiration,
    rewrite_inspiration,
)
from agents.tools.research import graph_rag_tool
from agents.tools.scriptwriter import (
    create_chapter,
    create_or_rewrite_script,
    organize_scenes_to_chapter,
    patch_script,
    prepare_script_creation,
    read_beat_sheet,
    read_character,
    read_synopsis,
    read_worldview,
)
from agents.tools.search import replace_from_search, search_project, semantic_search
from agents.tools.shared_read import list_chapters, read_chapter_outline_raw, read_chapter_scene
from agents.tools.skill_packs import read_skill, read_skill_reference, search_skills
from agents.tools.showrunner import (
    patch_beat_sheet,
    patch_outline,
    patch_synopsis,
    rewrite_beat_sheet,
    rewrite_outline,
    rewrite_synopsis,
)
from agents.tools.story_memory import story_memory_tool
from agents.tools.web_search import web_search
from core.request_context import current_user_id, get_current_chat_session

MCP_ONLY_TOOLS = [capture_inspiration]
EXTERNAL_SEARCH_TOOLS = [web_search]
OPTIONAL_RESEARCH_TOOLS = [story_memory_tool, graph_rag_tool]
SHARED_SKILL_TOOLS = [search_skills, read_skill, read_skill_reference]
SHARED_CHAT_HISTORY_TOOLS = [search_chat_history]
SKILL_CAPABLE_AGENT_IDS = {
    "agent_director",
    "agent_muse",
    "agent_lorebook",
    "agent_showrunner",
    "agent_scriptwriter",
    "agent_critic",
}

MUSE_BASE_TOOLS = [
    rewrite_inspiration,
    list_inspirations,
    read_inspiration,
    bind_inspiration_to_current_project,
    web_search,
]
LOREBOOK_BASE_TOOLS = [
    rewrite_worldview,
    rewrite_all_characters,
    update_character,
    patch_worldview,
    *EXTERNAL_SEARCH_TOOLS,
]
SHOWRUNNER_BASE_TOOLS = [
    rewrite_synopsis,
    rewrite_beat_sheet,
    rewrite_outline,
    patch_synopsis,
    patch_beat_sheet,
    patch_outline,
    read_chapter_outline_raw,
]
SCRIPTWRITER_BASE_TOOLS = [
    prepare_script_creation,
    create_chapter,
    create_or_rewrite_script,
    organize_scenes_to_chapter,
    patch_script,
    read_worldview,
    read_character,
    read_synopsis,
    read_beat_sheet,
    work_tracker,
    update_project_story_tags,
    *OPTIONAL_RESEARCH_TOOLS,
]
SHARED_READ_TOOLS = [list_chapters, read_chapter_scene, read_chapter_outline_raw]
DIRECTOR_BASE_TOOLS = SHARED_READ_TOOLS + [
    delegate_task,
    organize_scenes_to_chapter,
    work_tracker,
    trigger_auto_write,
    check_scriptwriter_status,
    update_project_story_tags,
    search_project,
    semantic_search,
    replace_from_search,
    *OPTIONAL_RESEARCH_TOOLS,
    web_search,
    read_attachment_chunk,
]
CRITIC_BASE_TOOLS = SHARED_READ_TOOLS + OPTIONAL_RESEARCH_TOOLS


def _resolve_user_id(user_id: str | int | None = None) -> str:
    if user_id is not None and str(user_id).strip():
        return str(user_id).strip()
    ctx_user_id = current_user_id.get()
    return str(ctx_user_id).strip() if ctx_user_id else ""


def has_effective_skill_tools(user_id: str | int | None = None) -> bool:
    resolved_user_id = _resolve_user_id(user_id)
    if not resolved_user_id:
        return False
    try:
        from agents.skill_packs import list_effective_skills

        return bool(list_effective_skills(resolved_user_id))
    except Exception:
        return False


def _with_skill_tools(agent_id: str, base_tools: list, user_id: str | int | None = None) -> list:
    tools = list(base_tools)
    if agent_id in SKILL_CAPABLE_AGENT_IDS and has_effective_skill_tools(user_id):
        tools.extend(SHARED_SKILL_TOOLS)
    return tools


def _with_contextual_tools(agent_id: str, base_tools: list, user_id: str | int | None = None) -> list:
    tools = _with_skill_tools(agent_id, base_tools, user_id)
    room_agent_id, context_key = get_current_chat_session()
    if room_agent_id and context_key:
        tools.extend(SHARED_CHAT_HISTORY_TOOLS)
    return tools


MUSE_TOOLS = MUSE_BASE_TOOLS + SHARED_SKILL_TOOLS
LOREBOOK_TOOLS = LOREBOOK_BASE_TOOLS + SHARED_SKILL_TOOLS
SHOWRUNNER_TOOLS = SHOWRUNNER_BASE_TOOLS + SHARED_SKILL_TOOLS
SCRIPTWRITER_TOOLS = SCRIPTWRITER_BASE_TOOLS + SHARED_SKILL_TOOLS
DIRECTOR_TOOLS = DIRECTOR_BASE_TOOLS + SHARED_SKILL_TOOLS
CRITIC_TOOLS = CRITIC_BASE_TOOLS + SHARED_SKILL_TOOLS
ALL_TOOLS = (
    MUSE_TOOLS
    + LOREBOOK_TOOLS
    + SHOWRUNNER_TOOLS
    + SCRIPTWRITER_TOOLS
    + SHARED_READ_TOOLS
    + [
        delegate_task,
        trigger_auto_write,
        check_scriptwriter_status,
        update_project_story_tags,
        search_project,
        semantic_search,
        replace_from_search,
        read_attachment_chunk,
    ]
    + SHARED_SKILL_TOOLS
    + SHARED_CHAT_HISTORY_TOOLS
    + EXTERNAL_SEARCH_TOOLS
    + OPTIONAL_RESEARCH_TOOLS
)
TOOLS_BY_NAME = {}
for tool in ALL_TOOLS:
    TOOLS_BY_NAME.setdefault(tool.name, tool)


def get_tools_for_agent(agent_id: str, user_id: str | int | None = None) -> list:
    tool_map = {
        "agent_muse": MUSE_BASE_TOOLS,
        "agent_lorebook": LOREBOOK_BASE_TOOLS,
        "agent_showrunner": SHOWRUNNER_BASE_TOOLS,
        "agent_scriptwriter": SCRIPTWRITER_BASE_TOOLS + SHARED_READ_TOOLS,
        "agent_director": DIRECTOR_BASE_TOOLS,
        "agent_critic": CRITIC_BASE_TOOLS,
        "agent_style": [],
    }
    return _with_contextual_tools(agent_id, tool_map.get(agent_id, []), user_id)


# MCP 远程操控暴露的纯查询工具白名单（P0 第二层）
# 这些工具只读不写，安全无副作用，适合 MCP 远程调用。
# 写盘工具不在此列——写盘操作走 MCP 导演工单，经内部 Agent 委派完成，
# 让 SparkArc 自己的 Agent 生成内容并落盘，受 prompt 规范约束。
# 外部依赖型工具（web_search/graph_rag_tool）和需要附件上下文的工具（read_attachment_chunk）不纳入。
MCP_EXPOSED_QUERY_TOOL_NAMES = frozenset({
    "list_chapters",
    "read_chapter_scene",
    "read_chapter_outline_raw",
    "read_worldview",
    "read_character",
    "read_synopsis",
    "read_beat_sheet",
    "search_project",
    "semantic_search",
    "list_inspirations",
    "read_inspiration",
    "check_scriptwriter_status",
})
