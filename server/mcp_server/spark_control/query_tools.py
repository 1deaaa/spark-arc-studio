"""
纯查询工具 MCP 暴露（P0 第二层）。

从 tools/registry.py 的 TOOLS_BY_NAME 真相源按白名单派生 MCP 工具。
每个 MCP wrapper 函数接受 project_name 前置参数，调用 invoke_langchain_tool 统一桥接。

白名单定义在 tools/registry.py 的 MCP_EXPOSED_QUERY_TOOL_NAMES，保持单一真相源。
所有工具只读不写，安全无副作用，适合 MCP 远程调用。
"""

from __future__ import annotations

from mcp_server.shared.tool_adapter import invoke_langchain_tool


def register_query_tools(mcp) -> None:
    """向 FastMCP 实例注册所有纯查询工具。

    每个工具自动注入 project_name 参数，通过 invoke_langchain_tool 桥接到
    tools/registry.py 的 TOOLS_BY_NAME 真相源。
    """

    @mcp.tool()
    def list_chapters(project_name: str) -> str:
        """列出项目的章节与场景结构概览。

        Args:
            project_name: 目标项目名称
        Returns:
            章节列表文本（含每章场景数与摘要）
        """
        return invoke_langchain_tool("list_chapters", project_name, {})

    @mcp.tool()
    def read_chapter_scene(
        project_name: str,
        chapter_index: int,
        scene_index: int = -1,
    ) -> str:
        """读取指定章节或场景的内容。

        Args:
            project_name: 目标项目名称
            chapter_index: 章节索引（从 0 开始）
            scene_index: 场景索引（从 0 开始）。传 -1 或不传则读取整个章节所有场景
        Returns:
            章节大纲 + 对应的 .arc 剧本文件内容
        """
        args = {"chapter_index": chapter_index}
        if scene_index >= 0:
            args["scene_index"] = scene_index
        return invoke_langchain_tool("read_chapter_scene", project_name, args)

    @mcp.tool()
    def read_chapter_outline_raw(project_name: str, chapter_index: int) -> str:
        """读取指定章节的大纲原文。

        Args:
            project_name: 目标项目名称
            chapter_index: 章节索引（从 0 开始），对应大纲.txt中 ## Chapter 的顺序
        Returns:
            该章节的大纲原文文本
        """
        return invoke_langchain_tool(
            "read_chapter_outline_raw",
            project_name,
            {"chapter_index": chapter_index},
        )

    @mcp.tool()
    def read_worldview(project_name: str) -> str:
        """读取项目的世界观全文。

        Args:
            project_name: 目标项目名称
        Returns:
            世界观设定文本
        """
        return invoke_langchain_tool("read_worldview", project_name, {})

    @mcp.tool()
    def read_character(project_name: str, character_name: str) -> str:
        """读取指定角色的设定档案。

        Args:
            project_name: 目标项目名称
            character_name: 要查阅的角色名字，例如"张三"
        Returns:
            角色设定文本
        """
        return invoke_langchain_tool(
            "read_character",
            project_name,
            {"character_name": character_name},
        )

    @mcp.tool()
    def read_synopsis(project_name: str) -> str:
        """读取项目的故事梗概。

        Args:
            project_name: 目标项目名称
        Returns:
            梗概文本
        """
        return invoke_langchain_tool("read_synopsis", project_name, {})

    @mcp.tool()
    def read_beat_sheet(project_name: str) -> str:
        """读取项目的节拍表。

        Args:
            project_name: 目标项目名称
        Returns:
            节拍表文本
        """
        return invoke_langchain_tool("read_beat_sheet", project_name, {})

    @mcp.tool()
    def search_project(
        project_name: str,
        pattern: str,
        case_sensitive: bool = False,
    ) -> str:
        """按正则表达式搜索项目内所有文本文件。

        Args:
            project_name: 目标项目名称
            pattern: 正则表达式模式，例如 '张三' 或 '哭泣|泪水'
            case_sensitive: 是否区分大小写（默认 False）
        Returns:
            匹配结果列表（含文件路径、行号、上下文）
        """
        return invoke_langchain_tool(
            "search_project",
            project_name,
            {"pattern": pattern, "case_sensitive": case_sensitive},
        )

    @mcp.tool()
    def semantic_search(
        project_name: str,
        query: str,
        scope: list[str] | None = None,
        k: int = 8,
    ) -> str:
        """按语义搜索当前项目文本与已上传附件。

        Args:
            project_name: 目标项目名称
            query: 自然语言查询，例如 '女主角哭的地方'
            scope: 搜索范围过滤。可选值：outline, synopsis, beats, worldview, character, arc, novel, attachment
            k: 返回结果数量上限（默认 8）
        Returns:
            语义匹配结果列表（含相似度评分与上下文）
        """
        return invoke_langchain_tool(
            "semantic_search",
            project_name,
            {"query": query, "scope": scope, "k": k},
        )

    @mcp.tool()
    def list_inspirations(
        project_name: str,
        scope: str = "project",
        limit: int = 20,
    ) -> str:
        """列出灵感条目。

        Args:
            project_name: 目标项目名称（scope=project 时按此过滤）
            scope: 过滤范围。all=全部, project=仅当前项目绑定, drafts=仅草稿
            limit: 返回条目数量上限（默认 20）
        Returns:
            灵感列表文本
        """
        return invoke_langchain_tool(
            "list_inspirations",
            project_name,
            {"scope": scope, "limit": limit},
        )

    @mcp.tool()
    def read_inspiration(project_name: str, inspiration_id: str) -> str:
        """读取指定灵感条目的完整内容。

        Args:
            project_name: 目标项目名称（用于上下文隔离）
            inspiration_id: 灵感条目 ID
        Returns:
            灵感原文与扩展内容
        """
        return invoke_langchain_tool(
            "read_inspiration",
            project_name,
            {"inspiration_id": inspiration_id},
        )

    @mcp.tool()
    def check_scriptwriter_status(
        project_name: str,
        export_format: str = "arc",
    ) -> str:
        """检查编剧 Agent 的工作状态与进度。

        Args:
            project_name: 目标项目名称
            export_format: 输出格式（arc=互动剧本, novel=纯文学小说）
        Returns:
            编剧状态报告
        """
        return invoke_langchain_tool(
            "check_scriptwriter_status",
            project_name,
            {"export_format": export_format},
        )
