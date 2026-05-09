from __future__ import annotations

from agents.tools.attachment import read_attachment_chunk
from agents.tools.automation import check_scriptwriter_status, trigger_auto_write, work_tracker
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
    patch_script,
    read_beat_sheet,
    read_character,
    read_synopsis,
    read_worldview,
)
from agents.tools.search import replace_from_search, search_project, semantic_search
from agents.tools.shared_read import list_chapters, read_chapter_outline_raw, read_chapter_scene
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
MUSE_TOOLS = [
    rewrite_inspiration,
    list_inspirations,
    read_inspiration,
    bind_inspiration_to_current_project,
    web_search,
]
LOREBOOK_TOOLS = [
    rewrite_worldview,
    rewrite_all_characters,
    update_character,
    patch_worldview,
]
SHOWRUNNER_TOOLS = [
    rewrite_synopsis,
    rewrite_beat_sheet,
    rewrite_outline,
    patch_synopsis,
    patch_beat_sheet,
    patch_outline,
    read_chapter_outline_raw,
]
SCRIPTWRITER_TOOLS = [
    create_chapter,
    create_or_rewrite_script,
    patch_script,
    read_worldview,
    read_character,
    read_synopsis,
    read_beat_sheet,
    work_tracker,
]
SHARED_READ_TOOLS = [list_chapters, read_chapter_scene, read_chapter_outline_raw]
DIRECTOR_TOOLS = SHARED_READ_TOOLS + [
    delegate_task,
    work_tracker,
    trigger_auto_write,
    check_scriptwriter_status,
    search_project,
    semantic_search,
    replace_from_search,
    web_search,
    read_attachment_chunk,
]
OPTIONAL_RESEARCH_TOOLS = [graph_rag_tool]
ALL_TOOLS = (
    MUSE_TOOLS
    + LOREBOOK_TOOLS
    + SHOWRUNNER_TOOLS
    + SCRIPTWRITER_TOOLS
    + SHARED_READ_TOOLS
    + [delegate_task, trigger_auto_write, check_scriptwriter_status, search_project, semantic_search, replace_from_search, read_attachment_chunk]
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
        "agent_critic": SHARED_READ_TOOLS,
        "agent_style": [],
    }
    return tool_map.get(agent_id, [])
