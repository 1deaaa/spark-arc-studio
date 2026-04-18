"""
角色绑定分块策略

chr.bind 是 JSON 文件，按顶层键值对各一个 chunk。
"""

import json
from typing import override

from story.project_files import ProjectFile, build_narrative_ref
from ..base import SemanticChunk, ChunkStrategy


class ChrBindChunkStrategy(ChunkStrategy):
    """角色绑定分块：JSON 顶层键值对各一个 chunk"""

    @property
    @override
    def format_key(self) -> str:
        return "chrbind"

    @override
    def chunk(self, project_file: ProjectFile, outline_data: dict) -> list[SemanticChunk]:
        try:
            data = json.loads(project_file.content)
        except (json.JSONDecodeError, TypeError):
            # JSON 解析失败，整个文件作为一个 chunk
            ref = build_narrative_ref(
                project_file.rel_path, "chrbind", outline_data,
            )
            return [SemanticChunk(
                text=project_file.content.strip(),
                metadata={"source": project_file.rel_path, "format_key": "chrbind"},
                start_line=1,
                end_line=project_file.content.count("\n") + 1,
                narrative_ref=ref,
            )]

        if not isinstance(data, dict):
            ref = build_narrative_ref(
                project_file.rel_path, "chrbind", outline_data,
            )
            return [SemanticChunk(
                text=project_file.content.strip(),
                metadata={"source": project_file.rel_path, "format_key": "chrbind"},
                start_line=1,
                end_line=project_file.content.count("\n") + 1,
                narrative_ref=ref,
            )]

        chunks: list[SemanticChunk] = []
        for character_id, value in data.items():
            character_name = value if isinstance(value, str) else str(value.get("name", character_id) if isinstance(value, dict) else character_id)
            text = json.dumps({character_id: value}, ensure_ascii=False, indent=2)
            ref = build_narrative_ref(
                project_file.rel_path, "chrbind", outline_data,
                character_id=character_id, character_name=character_name,
            )
            chunks.append(SemanticChunk(
                text=text,
                metadata={
                    "source": project_file.rel_path,
                    "format_key": "chrbind",
                    "character_id": character_id,
                    "character_name": character_name,
                },
                start_line=0,  # JSON 行号难以精确定位，标记为 0
                end_line=0,
                narrative_ref=ref,
            ))

        return chunks
