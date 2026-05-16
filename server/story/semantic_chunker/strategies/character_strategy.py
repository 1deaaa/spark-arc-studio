"""
角色档案分块策略

整文件 = 一个 chunk，从 chr.bind 或文件名推断角色名。
"""

import os
from typing import override

from story.project_files import (
    ProjectFile,
    build_narrative_ref,
    load_character_id_name_map_from_bind_path,
)
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
        """通过统一工具 load_character_id_name_map_from_bind_path 解析角色名。"""
        bind_path = os.path.join(os.path.dirname(project_file.abs_path), "chr.bind")
        id_to_name = load_character_id_name_map_from_bind_path(bind_path)
        name = id_to_name.get(str(character_id), "")
        if name:
            return name

        # 回退：从文件内容的第一行提取（兼容用户手写、且 chr.bind 缺失的项目）
        first_line = project_file.content.split("\n", 1)[0].strip()
        if first_line.startswith("#"):
            return first_line.lstrip("#").strip()

        return character_id
