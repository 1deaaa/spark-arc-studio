"""
通用标题分隔策略

按 # / ## 标题行分隔，适用于世界观、节拍表、梗概等格式。
"""

import re
from typing import override

from story.project_files import ProjectFile, build_narrative_ref
from ..base import SemanticChunk, ChunkStrategy


class HeadingChunkStrategy(ChunkStrategy):
    """通用标题分隔策略，支持 worldview / beats / synopsis"""

    def __init__(self, key: str | None = None):
        self._key = key or "worldview"

    @property
    @override
    def format_key(self) -> str:
        return self._key

    @property
    def format_keys(self) -> list[str]:
        """此策略支持的所有 format_key"""
        return ["worldview", "beats", "synopsis"]

    @override
    def chunk(self, project_file: ProjectFile, outline_data: dict) -> list[SemanticChunk]:
        lines = project_file.content.split("\n")
        chunks: list[SemanticChunk] = []
        current_lines: list[str] = []
        start_line = 1
        section_title = ""

        for i, line in enumerate(lines, start=1):
            is_heading = bool(re.match(r'^#{1,3}\s+', line))
            if is_heading and current_lines:
                text = "\n".join(current_lines).strip()
                if text:
                    ref = build_narrative_ref(
                        project_file.rel_path, self._key, outline_data,
                        section_title=section_title,
                    )
                    chunks.append(SemanticChunk(
                        text=text,
                        metadata={
                            "source": project_file.rel_path,
                            "format_key": self._key,
                            "section_title": section_title,
                        },
                        start_line=start_line,
                        end_line=i - 1,
                        narrative_ref=ref,
                    ))
                current_lines = [line]
                start_line = i
                section_title = line.strip().lstrip("#").strip()
            else:
                current_lines.append(line)

        # 尾部
        if current_lines:
            text = "\n".join(current_lines).strip()
            if text:
                ref = build_narrative_ref(
                    project_file.rel_path, self._key, outline_data,
                    section_title=section_title,
                )
                chunks.append(SemanticChunk(
                    text=text,
                    metadata={
                        "source": project_file.rel_path,
                        "format_key": self._key,
                        "section_title": section_title,
                    },
                    start_line=start_line,
                    end_line=len(lines),
                    narrative_ref=ref,
                ))

        # 如果没有标题结构，整个文件作为一个 chunk
        if not chunks:
            ref = build_narrative_ref(
                project_file.rel_path, self._key, outline_data,
            )
            chunks.append(SemanticChunk(
                text=project_file.content.strip(),
                metadata={
                    "source": project_file.rel_path,
                    "format_key": self._key,
                },
                start_line=1,
                end_line=len(lines),
                narrative_ref=ref,
            ))

        return chunks
