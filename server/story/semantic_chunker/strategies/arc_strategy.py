"""
剧本分块策略

复用 arc_parser._split_by_scenes() 按场景分割，
文件名通过 file_naming.parse_story_filename() 解析章节/场景索引。
"""

import re
from typing import override

from story.project_files import ProjectFile, build_narrative_ref
from story.file_naming import parse_story_filename
from ..base import SemanticChunk, ChunkStrategy


class ArcChunkStrategy(ChunkStrategy):
    """剧本分块：按 # 场景标题分隔"""

    @property
    @override
    def format_key(self) -> str:
        return "arc"

    @override
    def chunk(self, project_file: ProjectFile, outline_data: dict) -> list[SemanticChunk]:
        raw_lines = project_file.content.split("\n")
        first_scene_idx = next(
            (idx for idx, line in enumerate(raw_lines) if re.match(r'^#\s+', line)),
            0,
        )
        context_prefix = "\n".join(raw_lines[:first_scene_idx]).strip()
        lines = raw_lines[first_scene_idx:] if first_scene_idx else raw_lines
        chunks: list[SemanticChunk] = []

        # 从文件名解析章节/场景索引
        file_meta = parse_story_filename(project_file.filename)
        chapter_idx = file_meta.get("chapter_num") if file_meta else None
        scene_idx = file_meta.get("scene_num") if file_meta else None
        display_name = file_meta.get("display_name", "") if file_meta else ""

        # 按 # 场景标题拆分
        current_lines: list[str] = []
        start_line = 1
        scene_title = display_name  # 首个场景块用文件名作为标题

        for i, line in enumerate(lines, start=1):
            is_scene_heading = bool(re.match(r'^#\s+', line))
            if is_scene_heading and not current_lines:
                scene_title = line.strip().lstrip("#").strip() or scene_title
                start_line = i

            if is_scene_heading and current_lines:
                # 保存上一个场景块
                text = self._clean_scene_text("\n".join(current_lines))
                if text:
                    text = self._prepend_context_prefix(text, context_prefix)
                    ref = build_narrative_ref(
                        project_file.rel_path, "arc", outline_data,
                        chapter_idx=chapter_idx, scene_idx=scene_idx,
                        scene_title=scene_title,
                    )
                    chunks.append(SemanticChunk(
                        text=text,
                        metadata={
                            "source": project_file.rel_path,
                            "format_key": "arc",
                            "chapter_idx": chapter_idx,
                            "scene_idx": scene_idx,
                            "scene_title": scene_title,
                        },
                        start_line=start_line,
                        end_line=i - 1,
                        narrative_ref=ref,
                    ))
                # 开始新场景
                scene_title = line.strip().lstrip("#").strip()
                current_lines = [line]
                start_line = i
                # 后续场景的 scene_idx 递增
                if scene_idx is not None:
                    scene_idx += 1
            else:
                current_lines.append(line)

        # 尾部
        if current_lines:
            text = self._clean_scene_text("\n".join(current_lines))
            if text:
                text = self._prepend_context_prefix(text, context_prefix)
                ref = build_narrative_ref(
                    project_file.rel_path, "arc", outline_data,
                    chapter_idx=chapter_idx, scene_idx=scene_idx,
                    scene_title=scene_title,
                )
                chunks.append(SemanticChunk(
                    text=text,
                    metadata={
                        "source": project_file.rel_path,
                        "format_key": "arc",
                        "chapter_idx": chapter_idx,
                        "scene_idx": scene_idx,
                        "scene_title": scene_title,
                    },
                    start_line=start_line,
                    end_line=len(lines),
                    narrative_ref=ref,
                ))

        return chunks

    @staticmethod
    def _clean_scene_text(text: str) -> str:
        """移除 <conception> 块，保留正文"""
        text = re.sub(r'<conception>[\s\S]*?</conception>', '', text)
        return text.strip()

    @staticmethod
    def _prepend_context_prefix(text: str, context_prefix: str) -> str:
        """把角色索引等模型可见前缀附到每个场景块，避免单独成块。"""
        prefix = (context_prefix or "").strip()
        if not prefix:
            return text
        return f"{prefix}\n\n{text}"
