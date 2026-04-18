"""
项目级语义分块器

策略注册模式：按注册的 ChunkStrategy 分块，超长段自动二次切分。
支持分块缓存，避免每次搜索都重新分块。
"""

import hashlib
import json
import os
from typing import Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter

from core.utils import get_project_path
from story.project_files import (
    ProjectFile,
    collect_project_files,
    load_outline_data,
    build_narrative_ref,
)
from .base import SemanticChunk, get_strategy


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
    ) -> list[SemanticChunk]:
        """
        对整个项目执行语义分块。

        启用缓存时，比对文件 MD5 哈希，任一文件变更则全量重新分块。
        """
        project_path = get_project_path(user_id, project_name)
        cache_path = os.path.join(project_path, ".chunks_cache.json")

        if use_cache and os.path.exists(cache_path):
            cached = self._load_cache(cache_path)
            if cached is not None and self._cache_valid(cached, user_id, project_name):
                return cached

        # 执行分块
        chunks = self._do_chunk_project(user_id, project_name)

        # 写缓存
        if use_cache:
            self._save_cache(cache_path, chunks, user_id, project_name)

        return chunks

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
        return self._split_oversized(chunks)

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

    def _split_oversized(self, chunks: list[SemanticChunk]) -> list[SemanticChunk]:
        """超过 max_tokens 的块用 RecursiveCharacterTextSplitter 拆分"""
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

    def _cache_valid(self, cached: list[SemanticChunk], user_id: str, project_name: str) -> bool:
        """比对文件哈希验证缓存有效性"""
        project_path = get_project_path(user_id, project_name)
        # 检查缓存中的每个源文件是否仍然存在且哈希一致
        seen_sources: set[str] = set()
        for chunk in cached:
            source = chunk.metadata.get("source", "")
            if not source or source in seen_sources:
                continue
            seen_sources.add(source)
            abs_path = os.path.join(project_path, source)
            if not os.path.isfile(abs_path):
                return False
            try:
                with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                current_hash = hashlib.md5(content.encode("utf-8")).hexdigest()
                stored_hash = chunk.metadata.get("file_hash", "")
                if stored_hash and current_hash != stored_hash:
                    return False
            except Exception:
                return False
        return True

    def _load_cache(self, cache_path: str) -> Optional[list[SemanticChunk]]:
        """从磁盘加载分块缓存"""
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or "chunks" not in data:
                return None
            return [
                SemanticChunk(
                    text=item["text"],
                    metadata=item.get("metadata", {}),
                    start_line=item.get("start_line", 0),
                    end_line=item.get("end_line", 0),
                    narrative_ref=item.get("narrative_ref", ""),
                    char_count=item.get("char_count", 0),
                )
                for item in data["chunks"]
            ]
        except Exception:
            return None

    def _save_cache(
        self,
        cache_path: str,
        chunks: list[SemanticChunk],
        user_id: str,
        project_name: str,
    ) -> None:
        """将分块结果保存到磁盘"""
        # 为每个 chunk 的源文件计算哈希
        project_path = get_project_path(user_id, project_name)
        file_hashes: dict[str, str] = {}

        for chunk in chunks:
            source = chunk.metadata.get("source", "")
            if source and source not in file_hashes:
                abs_path = os.path.join(project_path, source)
                try:
                    with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                        file_hashes[source] = hashlib.md5(f.read().encode("utf-8")).hexdigest()
                except Exception:
                    file_hashes[source] = ""

        # 写入缓存
        serializable_chunks = []
        for chunk in chunks:
            meta = {**chunk.metadata}
            source = meta.get("source", "")
            if source and source in file_hashes:
                meta["file_hash"] = file_hashes[source]
            serializable_chunks.append({
                "text": chunk.text,
                "metadata": meta,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "narrative_ref": chunk.narrative_ref,
                "char_count": chunk.char_count,
            })

        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump({"chunks": serializable_chunks}, f, ensure_ascii=False, indent=1)
        except Exception:
            pass  # 缓存写入失败不影响主流程
