"""
角色档案分块策略

每个角色虚拟文件 = 一个 chunk，角色信息由项目文件元数据提供。
"""

from typing import override

from story.project_files import (
    ProjectFile,
    build_narrative_ref,
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
        character_id = str(project_file.metadata["character_id"])
        character_name = str(project_file.metadata["character_name"])

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
