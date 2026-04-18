"""
大纲分块策略

复用 outline_parser.parse_outline_markup() 获取章节/场景结构，
反向映射到行号区间产出 SemanticChunk。
"""

import re
from typing import override

from story.project_files import ProjectFile, build_narrative_ref
from story.outline_parser import parse_outline_markup
from ..base import SemanticChunk, ChunkStrategy


class OutlineChunkStrategy(ChunkStrategy):
    """大纲分块：按 ## 章节 / ### 场景分隔"""

    @property
    @override
    def format_key(self) -> str:
        return "outline"

    @override
    def chunk(self, project_file: ProjectFile, outline_data: dict) -> list[SemanticChunk]:
        lines = project_file.content.split("\n")
        chunks: list[SemanticChunk] = []

        # 先尝试用 outline_parser 获取结构
        parsed = parse_outline_markup(project_file.content)
        nodes = parsed.get("nodes", [])

        if not nodes:
            # 无章节结构，按标题行手动拆分
            return self._chunk_by_headings(project_file, outline_data)

        # 按章节/场景节点定位行号
        chapter_idx = 0
        for node in nodes:
            if node.get("type") != "chapter":
                continue
            chapter_title = node.get("title") or node.get("name") or f"第{chapter_idx + 1}章"
            children = node.get("children", [])

            if not children:
                # 章节无场景子节点：整个章节描述为一个 chunk
                start_line, end_line = self._find_chapter_line_range(lines, chapter_idx)
                if start_line > 0:
                    text = "\n".join(lines[start_line - 1:end_line]).strip()
                    if text:
                        ref = build_narrative_ref(
                            project_file.rel_path, "outline", outline_data,
                            chapter_idx=chapter_idx, chapter_title=chapter_title,
                        )
                        chunks.append(SemanticChunk(
                            text=text,
                            metadata={
                                "source": project_file.rel_path,
                                "format_key": "outline",
                                "chapter_idx": chapter_idx,
                                "chapter_title": chapter_title,
                            },
                            start_line=start_line,
                            end_line=end_line,
                            narrative_ref=ref,
                        ))
            else:
                # 按场景拆分
                for scene_idx, scene in enumerate(children):
                    scene_title = scene.get("title") or scene.get("name") or f"场景{scene_idx + 1}"
                    start_line, end_line = self._find_scene_line_range(
                        lines, chapter_idx, scene_idx
                    )
                    if start_line > 0:
                        text = "\n".join(lines[start_line - 1:end_line]).strip()
                        if text:
                            ref = build_narrative_ref(
                                project_file.rel_path, "outline", outline_data,
                                chapter_idx=chapter_idx, chapter_title=chapter_title,
                                scene_idx=scene_idx, scene_title=scene_title,
                            )
                            chunks.append(SemanticChunk(
                                text=text,
                                metadata={
                                    "source": project_file.rel_path,
                                    "format_key": "outline",
                                    "chapter_idx": chapter_idx,
                                    "scene_idx": scene_idx,
                                    "chapter_title": chapter_title,
                                    "scene_title": scene_title,
                                },
                                start_line=start_line,
                                end_line=end_line,
                                narrative_ref=ref,
                            ))

            chapter_idx += 1

        return chunks if chunks else self._chunk_by_headings(project_file, outline_data)

    def _chunk_by_headings(self, project_file: ProjectFile, outline_data: dict) -> list[SemanticChunk]:
        """回退：按 ## / ### 标题行拆分"""
        lines = project_file.content.split("\n")
        chunks: list[SemanticChunk] = []
        current_lines: list[str] = []
        start_line = 1
        current_title = ""

        for i, line in enumerate(lines, start=1):
            is_heading = bool(re.match(r'^#{1,3}\s+', line))
            if is_heading and current_lines:
                text = "\n".join(current_lines).strip()
                if text:
                    ref = build_narrative_ref(
                        project_file.rel_path, "outline", outline_data,
                    )
                    chunks.append(SemanticChunk(
                        text=text,
                        metadata={"source": project_file.rel_path, "format_key": "outline"},
                        start_line=start_line,
                        end_line=i - 1,
                        narrative_ref=ref,
                    ))
                current_lines = [line]
                start_line = i
                current_title = line.strip().lstrip("#").strip()
            else:
                current_lines.append(line)

        # 尾部
        if current_lines:
            text = "\n".join(current_lines).strip()
            if text:
                ref = build_narrative_ref(
                    project_file.rel_path, "outline", outline_data,
                )
                chunks.append(SemanticChunk(
                    text=text,
                    metadata={"source": project_file.rel_path, "format_key": "outline"},
                    start_line=start_line,
                    end_line=len(lines),
                    narrative_ref=ref,
                ))

        return chunks

    def _find_chapter_line_range(self, lines: list[str], chapter_idx: int) -> tuple[int, int]:
        """根据章节索引定位行号范围"""
        chapter_count = 0
        start_line = 0
        for i, line in enumerate(lines, start=1):
            if re.match(r'^##\s+', line):
                if chapter_count == chapter_idx:
                    start_line = i
                chapter_count += 1
                if chapter_count > chapter_idx + 1:
                    return start_line, i - 1
        if start_line > 0:
            return start_line, len(lines)
        return 0, 0

    def _find_scene_line_range(self, lines: list[str], chapter_idx: int, scene_idx: int) -> tuple[int, int]:
        """根据章节+场景索引定位行号范围"""
        chapter_count = 0
        scene_count = 0
        in_target_chapter = False
        start_line = 0

        for i, line in enumerate(lines, start=1):
            if re.match(r'^##\s+', line):
                if chapter_count == chapter_idx:
                    in_target_chapter = True
                else:
                    if in_target_chapter and start_line > 0:
                        return start_line, i - 1
                    in_target_chapter = False
                chapter_count += 1
                continue

            if in_target_chapter and re.match(r'^###\s+', line):
                if scene_count == scene_idx:
                    start_line = i
                else:
                    if scene_count > scene_idx and start_line > 0:
                        return start_line, i - 1
                scene_count += 1

        if start_line > 0:
            return start_line, len(lines)
        return 0, 0
