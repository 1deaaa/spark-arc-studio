"""
Agent Tools - 统一的工具定义模块

使用 LangChain @tool 装饰器定义所有 Agent 可调用的工具。
工具通过 model.bind_tools() 绑定到 LLM，让模型自主决策何时调用。
"""

from __future__ import annotations

# 历史实现已迁移至 agents/tools/* 子模块，本文件仅作兼容导出门面。
# 真相源：agents/tools/registry.py（注册表）、agents/tools/common.py（公共工具）、
#         agents/tools/search.py（搜索工具）、agents/tools/<域>.py（各域工具）

from agents.tools.automation import (
    CheckScriptwriterStatusInput,
    TriggerAutoWriteInput,
    WorkTrackerInput,
    check_scriptwriter_status,
    trigger_auto_write,
    work_tracker,
)
from agents.tools.common import (
    ToolExecutionContext,
    _apply_patch,
    _strip_markdown_fence,
)
from agents.tools.delegation import DelegateTaskInput, delegate_task
from agents.tools.lorebook import (
    PatchWorldviewInput,
    RewriteAllCharactersInput,
    RewriteWorldviewInput,
    UpdateCharacterInput,
    patch_worldview,
    rewrite_all_characters,
    rewrite_worldview,
    update_character,
)
from agents.tools.muse import (
    CaptureInspirationInput,
    RewriteInspirationInput,
    capture_inspiration,
    rewrite_inspiration,
)
from agents.tools.registry import (
    ALL_TOOLS,
    DIRECTOR_TOOLS,
    EXTERNAL_SEARCH_TOOLS,
    LOREBOOK_TOOLS,
    MCP_ONLY_TOOLS,
    MUSE_TOOLS,
    OPTIONAL_RESEARCH_TOOLS,
    SCRIPTWRITER_TOOLS,
    SHARED_READ_TOOLS,
    SHOWRUNNER_TOOLS,
    TOOLS_BY_NAME,
    get_tools_for_agent,
)
from agents.tools.research import GraphRagToolInput, graph_rag_tool
from agents.tools.scriptwriter import (
    CreateChapterInput,
    CreateOrRewriteScriptInput,
    PatchScriptInput,
    ReadCharacterInput,
    create_chapter,
    create_or_rewrite_script,
    patch_script,
    read_beat_sheet,
    read_character,
    read_synopsis,
    read_worldview,
)
from agents.tools.search import (
    ReplaceFromSearchInput,
    SearchProjectInput,
    SemanticSearchInput,
    _get_search_results,
    _store_search_results,
    replace_from_search,
    search_project,
    semantic_search,
)
from agents.tools.shared_read import (
    ReadChapterOutlineRawInput,
    ReadChapterSceneInput,
    list_chapters,
    read_chapter_outline_raw,
    read_chapter_scene,
)
from agents.tools.showrunner import (
    PatchBeatSheetInput,
    PatchOutlineInput,
    PatchSynopsisInput,
    RewriteBeatSheetInput,
    RewriteOutlineInput,
    RewriteSynopsisInput,
    patch_beat_sheet,
    patch_outline,
    patch_synopsis,
    rewrite_beat_sheet,
    rewrite_outline,
    rewrite_synopsis,
)
from agents.tools.web_search import WebSearchInput, web_search

__all__ = [
    "ALL_TOOLS",
    "CaptureInspirationInput",
    "CheckScriptwriterStatusInput",
    "CreateChapterInput",
    "CreateOrRewriteScriptInput",
    "DIRECTOR_TOOLS",
    "DelegateTaskInput",
    "EXTERNAL_SEARCH_TOOLS",
    "GraphRagToolInput",
    "LOREBOOK_TOOLS",
    "MCP_ONLY_TOOLS",
    "MUSE_TOOLS",
    "OPTIONAL_RESEARCH_TOOLS",
    "PatchBeatSheetInput",
    "PatchOutlineInput",
    "PatchScriptInput",
    "PatchSynopsisInput",
    "PatchWorldviewInput",
    "ReadChapterOutlineRawInput",
    "ReadChapterSceneInput",
    "ReadCharacterInput",
    "ReplaceFromSearchInput",
    "RewriteAllCharactersInput",
    "RewriteBeatSheetInput",
    "RewriteInspirationInput",
    "RewriteOutlineInput",
    "RewriteSynopsisInput",
    "RewriteWorldviewInput",
    "SCRIPTWRITER_TOOLS",
    "SHARED_READ_TOOLS",
    "SHOWRUNNER_TOOLS",
    "SearchProjectInput",
    "SemanticSearchInput",
    "TOOLS_BY_NAME",
    "ToolExecutionContext",
    "TriggerAutoWriteInput",
    "UpdateCharacterInput",
    "WorkTrackerInput",
    "WebSearchInput",
    "_apply_patch",
    "_get_search_results",
    "_store_search_results",
    "_strip_markdown_fence",
    "capture_inspiration",
    "check_scriptwriter_status",
    "create_chapter",
    "create_or_rewrite_script",
    "delegate_task",
    "get_tools_for_agent",
    "graph_rag_tool",
    "list_chapters",
    "patch_beat_sheet",
    "patch_outline",
    "patch_script",
    "patch_synopsis",
    "patch_worldview",
    "read_beat_sheet",
    "read_character",
    "read_chapter_outline_raw",
    "read_chapter_scene",
    "read_synopsis",
    "read_worldview",
    "replace_from_search",
    "rewrite_all_characters",
    "rewrite_beat_sheet",
    "rewrite_inspiration",
    "rewrite_outline",
    "rewrite_synopsis",
    "rewrite_worldview",
    "search_project",
    "semantic_search",
    "trigger_auto_write",
    "update_character",
    "work_tracker",
    "web_search",
]
