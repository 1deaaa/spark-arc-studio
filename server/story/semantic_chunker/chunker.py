"""
项目级语义分块器

策略注册模式：按注册的 ChunkStrategy 分块，超长段自动二次切分。
支持分块缓存，避免每次搜索都重新分块。
"""

import hashlib
import json
import os
from typing import Any, Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter

from core.utils import get_project_path
from story.project_files import (
    ProjectFile,
    collect_project_files,
    load_outline_data,
    build_narrative_ref,
)
from .base import SemanticChunk, get_strategy


SEMANTIC_CHUNKER_CACHE_VERSION = "3.0"


class SemanticChunker:
    """项目级语义分块器（策略注册模式）"""

    def __init__(
        self,
        max_chunk_tokens: int = 800,
        sub_chunk_size: int = 600,
        sub_chunk_overlap: int = 100,
    ):
        self._max_tokens = max_chunk_tokens
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=sub_chunk_size,
            chunk_overlap=sub_chunk_overlap,
        )

    def chunk_project(
        self,
        user_id: str,
        project_name: str,
        use_cache: bool = True,
        max_source_chars: int = 600_000,
    ) -> list[SemanticChunk]:
        """
        对整个项目执行语义分块。

        启用缓存时，仅对新增/变更文件重新分块，未变更文件直接复用缓存。
        """
        state = self.chunk_project_state(
            user_id,
            project_name,
            use_cache=use_cache,
            max_source_chars=max_source_chars,
        )
        return list(state.get("chunks") or [])

    def chunk_project_state(
        self,
        user_id: str,
        project_name: str,
        use_cache: bool = True,
        max_source_chars: int = 600_000,
    ) -> dict[str, Any]:
        """返回项目分块结果及增量缓存状态。"""
        project_path = get_project_path(user_id, project_name)
        cache_path = os.path.join(project_path, ".chunks_cache.json")
        files = collect_project_files(
            user_id,
            project_name,
            max_source_chars=max_source_chars,
        )
        outline_data = load_outline_data(user_id, project_name)
        outline_hash = self._compute_outline_hash(outline_data)
        file_hashes = {
            pf.rel_path: hashlib.md5(pf.content.encode("utf-8")).hexdigest()
            for pf in files
        }

        cached_payload = None
        if use_cache and os.path.exists(cache_path):
            cached_payload = self._load_cache(cache_path)
        cached_files = self._extract_cached_files(cached_payload)

        full_rechunk = (
            not use_cache
            or not cached_files
            or str((cached_payload or {}).get("outline_hash", "") or "") != outline_hash
        )
        removed_files = [
            rel_path
            for rel_path in cached_files.keys()
            if rel_path not in file_hashes
        ]
        changed_files: list[str] = []
        reused_files: list[str] = []
        next_cache_files: dict[str, dict[str, Any]] = {}

        for pf in files:
            rel_path = pf.rel_path
            current_hash = file_hashes.get(rel_path, "")
            cached_entry = cached_files.get(rel_path)

            if not full_rechunk and cached_entry and cached_entry.get("file_hash", "") == current_hash:
                next_cache_files[rel_path] = cached_entry
                reused_files.append(rel_path)
                continue

            file_chunks = self.chunk_file(pf, outline_data)
            next_cache_files[rel_path] = self._serialize_file_chunks(file_chunks, current_hash)
            changed_files.append(rel_path)

        if use_cache:
            self._save_cache(
                cache_path,
                {
                    "version": SEMANTIC_CHUNKER_CACHE_VERSION,
                    "outline_hash": outline_hash,
                    "files": next_cache_files,
                },
            )

        chunks_by_file: dict[str, list[SemanticChunk]] = {}
        all_chunks: list[SemanticChunk] = []
        for pf in files:
            rel_path = pf.rel_path
            entry = next_cache_files.get(rel_path, {"file_hash": file_hashes.get(rel_path, ""), "chunks": []})
            file_chunks = [
                self._deserialize_chunk(item)
                for item in entry.get("chunks", [])
                if isinstance(item, dict)
            ]
            chunks_by_file[rel_path] = file_chunks
            all_chunks.extend(file_chunks)

        return {
            "chunks": all_chunks,
            "chunks_by_file": chunks_by_file,
            "file_hashes": file_hashes,
            "outline_hash": outline_hash,
            "changed_files": changed_files,
            "removed_files": removed_files,
            "reused_files": reused_files,
        }

    def chunk_file(
        self,
        project_file: ProjectFile,
        outline_data: dict,
    ) -> list[SemanticChunk]:
        """按注册的策略分块，超长段自动二次切分"""
        strategy = get_strategy(project_file.format_key)
        if strategy:
            chunks = strategy.chunk(project_file, outline_data)
        else:
            chunks = self._fallback_chunk(project_file, outline_data)

        # 二次切分超长块
        return self.split_oversized(chunks)

    # ==================== 内部方法 ====================

    def _do_chunk_project(self, user_id: str, project_name: str) -> list[SemanticChunk]:
        """执行项目分块"""
        files = collect_project_files(user_id, project_name)
        outline_data = load_outline_data(user_id, project_name)
        all_chunks: list[SemanticChunk] = []
        for pf in files:
            chunks = self.chunk_file(pf, outline_data)
            all_chunks.extend(chunks)
        return all_chunks

    def split_oversized(self, chunks: list[SemanticChunk]) -> list[SemanticChunk]:
        """超过 ``max_tokens`` 的块用 ``RecursiveCharacterTextSplitter`` 拆分。

        对项目文件分块、附件入索都是同一个“超长块二次切分”入口，避免多处重写。
        外部调用者（如 ``VectorIndexService._collect_attachment_chunks``）可直接复用。
        """
        # 粗略估算：1 token ≈ 1.5 中文字符
        max_chars = self._max_tokens * 2
        result: list[SemanticChunk] = []
        for chunk in chunks:
            if len(chunk.text) <= max_chars:
                result.append(chunk)
                continue

            # 拆分
            sub_texts = self._splitter.split_text(chunk.text)
            for sub_idx, sub_text in enumerate(sub_texts):
                sub_meta = {**chunk.metadata, "sub_chunk_idx": sub_idx}
                result.append(SemanticChunk(
                    text=sub_text,
                    metadata=sub_meta,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    narrative_ref=chunk.narrative_ref,
                ))
        return result

    def _fallback_chunk(self, project_file: ProjectFile, outline_data: dict) -> list[SemanticChunk]:
        """未知格式的回退策略：按空行分隔"""
        lines = project_file.content.split("\n")
        chunks: list[SemanticChunk] = []
        current_lines: list[str] = []
        start_line = 1

        for i, line in enumerate(lines, start=1):
            if line.strip() == "" and current_lines:
                text = "\n".join(current_lines).strip()
                if text:
                    ref = build_narrative_ref(
                        project_file.rel_path, project_file.format_key, outline_data
                    )
                    chunks.append(SemanticChunk(
                        text=text,
                        metadata={"source": project_file.rel_path, "format_key": project_file.format_key},
                        start_line=start_line,
                        end_line=i - 1,
                        narrative_ref=ref,
                    ))
                current_lines = []
                start_line = i + 1
            else:
                current_lines.append(line)

        # 尾部
        if current_lines:
            text = "\n".join(current_lines).strip()
            if text:
                ref = build_narrative_ref(
                    project_file.rel_path, project_file.format_key, outline_data
                )
                chunks.append(SemanticChunk(
                    text=text,
                    metadata={"source": project_file.rel_path, "format_key": project_file.format_key},
                    start_line=start_line,
                    end_line=len(lines),
                    narrative_ref=ref,
                ))

        return chunks

    # ==================== 缓存 ====================

    def _compute_outline_hash(self, outline_data: dict) -> str:
        """计算大纲快照哈希，用于跨文件叙事定位失效检测。"""
        try:
            payload = json.dumps(outline_data or {}, ensure_ascii=False, sort_keys=True)
        except Exception:
            payload = "{}"
        return hashlib.md5(payload.encode("utf-8")).hexdigest()

    def _extract_cached_files(self, cached_payload: Any) -> dict[str, dict[str, Any]]:
        """兼容新旧缓存格式，统一转换为按文件分组的缓存结构。"""
        if not isinstance(cached_payload, dict):
            return {}
        if cached_payload.get("version") != SEMANTIC_CHUNKER_CACHE_VERSION:
            return {}

        raw_files = cached_payload.get("files")
        if isinstance(raw_files, dict):
            normalized: dict[str, dict[str, Any]] = {}
            for rel_path, entry in raw_files.items():
                if not isinstance(entry, dict):
                    continue
                chunks = entry.get("chunks", [])
                normalized[str(rel_path)] = {
                    "file_hash": str(entry.get("file_hash", "") or ""),
                    "chunks": chunks if isinstance(chunks, list) else [],
                }
            return normalized

        raw_chunks = cached_payload.get("chunks")
        if not isinstance(raw_chunks, list):
            return {}

        legacy_grouped: dict[str, dict[str, Any]] = {}
        for item in raw_chunks:
            if not isinstance(item, dict):
                continue
            metadata = item.get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}
            rel_path = str(metadata.get("source", "") or "")
            if not rel_path:
                continue
            file_hash = str(metadata.get("file_hash", "") or "")
            entry = legacy_grouped.setdefault(
                rel_path,
                {"file_hash": file_hash, "chunks": []},
            )
            if not entry.get("file_hash") and file_hash:
                entry["file_hash"] = file_hash
            entry["chunks"].append(item)
        return legacy_grouped

    def _deserialize_chunk(self, item: dict[str, Any]) -> SemanticChunk:
        """将缓存项恢复为 SemanticChunk。"""
        return SemanticChunk(
            text=str(item.get("text", "") or ""),
            metadata=item.get("metadata", {}) if isinstance(item.get("metadata", {}), dict) else {},
            start_line=int(item.get("start_line", 0) or 0),
            end_line=int(item.get("end_line", 0) or 0),
            narrative_ref=str(item.get("narrative_ref", "") or ""),
            char_count=int(item.get("char_count", 0) or 0),
        )

    def _serialize_file_chunks(self, chunks: list[SemanticChunk], file_hash: str) -> dict[str, Any]:
        """按文件序列化分块结果。"""
        serialized_chunks: list[dict[str, Any]] = []
        for chunk in chunks:
            metadata = {**chunk.metadata, "file_hash": file_hash}
            serialized_chunks.append({
                "text": chunk.text,
                "metadata": metadata,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "narrative_ref": chunk.narrative_ref,
                "char_count": chunk.char_count,
            })
        return {
            "file_hash": file_hash,
            "chunks": serialized_chunks,
        }

    def _load_cache(self, cache_path: str) -> Optional[dict[str, Any]]:
        """从磁盘加载分块缓存"""
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return None
            return data
        except Exception:
            return None

    def _save_cache(
        self,
        cache_path: str,
        payload: dict[str, Any],
    ) -> None:
        """将分块结果保存到磁盘"""
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=1)
        except Exception:
            pass  # 缓存写入失败不影响主流程
