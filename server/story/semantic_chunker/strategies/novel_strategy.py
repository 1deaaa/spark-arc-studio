"""
小说分块策略

复用 novel_parser.parse_scene_md() 清洗文本，按空行分隔段落。
"""

from typing import override

from story.project_files import ProjectFile, build_narrative_ref
from story.novel_parser import parse_scene_md
from story.file_naming import parse_story_filename
from ..base import SemanticChunk, ChunkStrategy


class NovelChunkStrategy(ChunkStrategy):
    """小说分块：清洗后按空行分隔段落"""

    @property
    @override
    def format_key(self) -> str:
        return "novel"

    @override
    def chunk(self, project_file: ProjectFile, outline_data: dict) -> list[SemanticChunk]:
        # 清洗文本
        cleaned = parse_scene_md(project_file.content)
        lines = cleaned.split("\n")

        # 从文件名解析章节/场景索引
        file_meta = parse_story_filename(project_file.filename)
        chapter_idx = file_meta.get("chapter_num") if file_meta else None
        scene_idx = file_meta.get("scene_num") if file_meta else None
        display_name = file_meta.get("display_name", "") if file_meta else ""

        chunks: list[SemanticChunk] = []
        current_lines: list[str] = []
        start_line = 1
        para_idx = 0

        for i, line in enumerate(lines, start=1):
            if line.strip() == "" and current_lines:
                text = "\n".join(current_lines).strip()
                if text:
                    ref = build_narrative_ref(
                        project_file.rel_path, "novel", outline_data,
                        chapter_idx=chapter_idx, scene_idx=scene_idx,
                        scene_title=display_name,
                    )
                    chunks.append(SemanticChunk(
                        text=text,
                        metadata={
                            "source": project_file.rel_path,
                            "format_key": "novel",
                            "chapter_idx": chapter_idx,
                            "scene_idx": scene_idx,
                            "para_idx": para_idx,
                        },
                        start_line=start_line,
                        end_line=i - 1,
                        narrative_ref=ref,
                    ))
                    para_idx += 1
                current_lines = []
                start_line = i + 1
            else:
                current_lines.append(line)

        # 尾部
        if current_lines:
            text = "\n".join(current_lines).strip()
            if text:
                ref = build_narrative_ref(
                    project_file.rel_path, "novel", outline_data,
                    chapter_idx=chapter_idx, scene_idx=scene_idx,
                    scene_title=display_name,
                )
                chunks.append(SemanticChunk(
                    text=text,
                    metadata={
                        "source": project_file.rel_path,
                        "format_key": "novel",
                        "chapter_idx": chapter_idx,
                        "scene_idx": scene_idx,
                        "para_idx": para_idx,
                    },
                    start_line=start_line,
                    end_line=len(lines),
                    narrative_ref=ref,
                ))

        return chunks
