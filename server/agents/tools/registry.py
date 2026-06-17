from __future__ import annotations

from agents.tools.attachment import read_attachment_chunk
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
from agents.tools.web_search import web_search

MCP_ONLY_TOOLS = [capture_inspiration]
EXTERNAL_SEARCH_TOOLS = [web_search]
OPTIONAL_RESEARCH_TOOLS = [graph_rag_tool]
SHARED_SKILL_TOOLS = [search_skills, read_skill, read_skill_reference]
MUSE_TOOLS = [
    rewrite_inspiration,
    list_inspirations,
    read_inspiration,
    bind_inspiration_to_current_project,
    web_search,
    *SHARED_SKILL_TOOLS,
]
LOREBOOK_TOOLS = [
    rewrite_worldview,
    rewrite_all_characters,
    update_character,
    patch_worldview,
    *SHARED_SKILL_TOOLS,
]
SHOWRUNNER_TOOLS = [
    rewrite_synopsis,
    rewrite_beat_sheet,
    rewrite_outline,
    patch_synopsis,
    patch_beat_sheet,
    patch_outline,
    read_chapter_outline_raw,
    *SHARED_SKILL_TOOLS,
]
SCRIPTWRITER_TOOLS = [
    create_chapter,
    create_or_rewrite_script,
    organize_scenes_to_chapter,
    patch_script,
    read_worldview,
    read_character,
    read_synopsis,
    read_beat_sheet,
    work_tracker,
    *OPTIONAL_RESEARCH_TOOLS,
    *SHARED_SKILL_TOOLS,
]
SHARED_READ_TOOLS = [list_chapters, read_chapter_scene, read_chapter_outline_raw]
DIRECTOR_TOOLS = SHARED_READ_TOOLS + [
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
    *SHARED_SKILL_TOOLS,
]
CRITIC_TOOLS = SHARED_READ_TOOLS + OPTIONAL_RESEARCH_TOOLS + SHARED_SKILL_TOOLS
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
    + EXTERNAL_SEARCH_TOOLS
    + OPTIONAL_RESEARCH_TOOLS
)
TOOLS_BY_NAME = {}
for tool in ALL_TOOLS:
    TOOLS_BY_NAME.setdefault(tool.name, tool)


def get_tools_for_agent(agent_id: str) -> list:
    tool_map = {
        "agent_muse": MUSE_TOOLS,
        "agent_lorebook": LOREBOOK_TOOLS,
        "agent_showrunner": SHOWRUNNER_TOOLS,
        "agent_scriptwriter": SCRIPTWRITER_TOOLS + SHARED_READ_TOOLS,
        "agent_director": DIRECTOR_TOOLS,
        "agent_critic": CRITIC_TOOLS,
        "agent_style": [],
    }
    return tool_map.get(agent_id, [])


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
