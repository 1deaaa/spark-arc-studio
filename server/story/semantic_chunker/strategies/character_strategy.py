"""
角色档案分块策略

整文件 = 一个 chunk，从 chr.bind 或文件名推断角色名。
"""

import json
import os
from typing import override

from story.project_files import ProjectFile, build_narrative_ref
from ..base import SemanticChunk, ChunkStrategy


class CharacterChunkStrategy(ChunkStrategy):
    """角色档案分块：整文件 = 一个 chunk"""

    @property
    @override
    def format_key(self) -> str:
        return "character"

    @override
    def chunk(self, project_file: ProjectFile, outline_data: dict) -> list[SemanticChunk]:
        # 从文件名推断角色 ID
        character_id = os.path.splitext(project_file.filename)[0]
        character_name = self._lookup_character_name(project_file, character_id)

        ref = build_narrative_ref(
            project_file.rel_path, "character", outline_data,
            character_id=character_id, character_name=character_name,
        )

        chunk = SemanticChunk(
            text=project_file.content.strip(),
            metadata={
                "source": project_file.rel_path,
                "format_key": "character",
                "character_id": character_id,
                "character_name": character_name,
            },
            start_line=1,
            end_line=project_file.content.count("\n") + 1,
            narrative_ref=ref,
        )
        return [chunk]

    @staticmethod
    def _lookup_character_name(project_file: ProjectFile, character_id: str) -> str:
        """从 chr.bind 查找角色名"""
        # 尝试从同目录的 chr.bind 读取
        bind_path = os.path.join(os.path.dirname(project_file.abs_path), "chr.bind")
        if os.path.exists(bind_path):
            try:
                with open(bind_path, "r", encoding="utf-8") as f:
                    mapping = json.load(f)
                entry = mapping.get(character_id)
                if isinstance(entry, dict):
                    return entry.get("name", character_id)
                elif isinstance(entry, str):
                    return entry
            except Exception:
                pass

        # 回退：从文件内容的第一行提取
        first_line = project_file.content.split("\n", 1)[0].strip()
        if first_line.startswith("#"):
            return first_line.lstrip("#").strip()

        return character_id
