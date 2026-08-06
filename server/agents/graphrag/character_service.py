"""角色关系专用轻量图谱。

角色页只需要回答“世界观中角色之间是什么关系”，不应复用包含正文、章节和
多类实体的项目级 GraphRAG。该服务复用 GraphRAG 的抽取、合并和证据格式，
但只把世界观文本作为模型输入，并使用角色名目录帮助模型稳定对齐实体。
"""

from __future__ import annotations

import os
from typing import Any

from langchain_core.documents import Document

from core.character_store import read_character_records
from core.json_state import save_json_file_atomic
from core.utils import get_project_worldview_path
from core.file_ingest.chunking import TokenTextSplitter

from .service import GraphRAGService


CHARACTER_GRAPH_VERSION = "character-worldview-v1"


class CharacterGraphService(GraphRAGService):
    """项目级 GraphRAG 的角色关系轻量变体。"""

    def __init__(self, user_id: str, project_name: str):
        super().__init__(user_id, project_name, scope="character")

    @property
    def _artifacts(self):
        base_dir = os.path.join(self._project_path, ".graphrag", "character")
        # 复用 GraphRAGArtifactPaths 的统一落盘格式。
        from .service import GraphRAGArtifactPaths

        return GraphRAGArtifactPaths(
            base_dir=base_dir,
            pickle_path=os.path.join(base_dir, "graph.pkl"),
            graphml_path=os.path.join(base_dir, "graph.graphml"),
            json_path=os.path.join(base_dir, "graph.json"),
            metadata_path=os.path.join(base_dir, "meta.json"),
        )

    def _worldview_text(self) -> str:
        path = get_project_worldview_path(self.user_id, self.project_name)
        if not os.path.isfile(path):
            return ""
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            return handle.read()[: self._max_source_chars].strip()

    def _character_roster(self) -> list[str]:
        records = read_character_records(self.user_id, self.project_name)
        return [
            str(record.get("name") or "").strip()
            for character_id, record in sorted(records.items(), key=lambda item: int(item[0]))
            if int(character_id) >= 0 and str(record.get("name") or "").strip()
        ]

    def _triplet_entity_hint(self) -> str:
        roster = self._character_roster()
        if not roster:
            return ""
        return "角色目录（只用于实体对齐，不是额外事实来源）: " + "、".join(roster[:160])

    def _collect_source_documents(self) -> list[Document]:
        self._ensure_project_exists()
        worldview = self._worldview_text()
        if not worldview:
            return []

        # 世界观通常很短；超长设定才切成多个块，避免一次请求超过模型上下文。
        splitter = TokenTextSplitter(
            chunk_tokens=max(4000, min(12000, self._max_source_chars // 4)),
            min_tokens=100,
            max_tokens=12000,
        )
        chunks = splitter.split(worldview)
        return [
            Document(
                page_content=chunk.text,
                metadata={
                    "source": "世界观.txt",
                    "format_key": "worldview",
                    "narrative_ref": "世界观",
                    "start_line": 1,
                    "end_line": worldview.count("\n") + 1,
                    "chunking_strategy": CHARACTER_GRAPH_VERSION,
                },
            )
            for chunk in chunks
        ]

    def _compute_file_hashes(self) -> dict[str, str]:
        """只让世界观和角色名目录影响角色图过期判断。"""
        worldview = self._worldview_text()
        roster = "\n".join(self._character_roster())
        return {
            "世界观.txt": self._hash_text(worldview),
            "角色目录": self._hash_text(roster),
        }

    def _needs_rebuild(self, metadata: dict[str, Any]) -> bool:
        if not isinstance(metadata, dict):
            return True
        if metadata.get("character_graph_version") != CHARACTER_GRAPH_VERSION:
            return True
        stored = metadata.get("file_hashes")
        current = self._compute_file_hashes()
        if not isinstance(stored, dict) or set(stored) != set(current):
            return True
        return any(stored.get(key) != value for key, value in current.items())

    def build_index(self, force_rebuild: bool = False) -> dict[str, Any]:
        metadata = super().build_index(force_rebuild=force_rebuild)
        metadata["character_graph_version"] = CHARACTER_GRAPH_VERSION
        # super 已经落盘，此处补写版本字段，后续 freshness 可正确命中。
        self._persist_metadata(metadata)
        return metadata

    def _persist_metadata(self, metadata: dict[str, Any]) -> None:
        artifacts = self._artifacts
        save_json_file_atomic(artifacts.metadata_path, metadata)
