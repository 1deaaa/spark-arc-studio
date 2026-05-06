"""
项目级向量索引服务

使用 Chroma 持久化向量库 + matchbox 云端 embedding。
支持懒构建、哈希增量更新、元数据过滤查询。
"""

import hashlib
import json
import os
import shutil
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from core.utils import get_project_path
from llm.agen_matchbox import matchbox
from story.project_files import collect_project_files
from story.semantic_chunker import SemanticChunker, SemanticChunk


_build_state_registry: dict[str, dict] = {}
_build_state_lock = threading.Lock()


# ==================== 辅助函数 ====================

def _safe_collection_name(user_id: str, project_name: str) -> str:
    """生成 Chroma 合法的 collection name。

    Chroma 要求 name 仅含 [a-zA-Z0-9._-]，长度 3-512。
    中文项目名通过 MD5 哈希转换为合法标识符。
    """
    import re
    raw = f"p_{user_id}_{project_name}"
    if re.fullmatch(r'[a-zA-Z0-9._-]{3,512}', raw):
        return raw
    # 含非 ASCII 字符，用 MD5 哈希
    digest = hashlib.md5(raw.encode("utf-8")).hexdigest()[:32]
    return f"p_{user_id}_{digest}"


def _build_task_key(user_id: str, project_name: str) -> str:
    return f"{user_id}:{project_name}"


# ==================== 数据类 ====================

@dataclass
class SearchHit:
    """向量检索命中结果"""
    index: int               # 全局序号
    file_path: str           # 绝对路径
    rel_path: str            # 相对路径
    format_key: str          # 文件格式键
    start_line: int          # 起始行
    end_line: int            # 结束行
    narrative_ref: str       # 叙事定位
    match_text: str          # 命中文本片段
    score: float             # 相似度分数
    source_type: str = "project"   # 'project' | 'attachment'，用于上层区分项目正文和附件
    attachment_id: str = ""        # source_type=attachment 时携带
    attachment_filename: str = ""  # source_type=attachment 时携带
    attachment_chunk_index: int = 0  # source_type=attachment 时携带


class IndexBuildNotReadyError(RuntimeError):
    def __init__(self, status_payload: dict):
        super().__init__("语义索引尚未就绪")
        self.status_payload = status_payload


# ==================== 向量索引服务 ====================

class VectorIndexService:
    """项目级向量索引服务（Chroma + matchbox embedding）"""

    def __init__(self, user_id: str, project_name: str):
        self.user_id = str(user_id)
        self.project_name = project_name
        self._project_path = get_project_path(user_id, project_name)
        self._persist_dir = os.path.join(self._project_path, ".vector_index")
        self._meta_path = os.path.join(self._persist_dir, "meta.json")
        # Chroma collection name 仅允许 [a-zA-Z0-9._-]，中文项目名需哈希化
        self._collection_name = _safe_collection_name(user_id, project_name)

    # ==================== Embedding ====================

    def _get_embeddings(self) -> OpenAIEmbeddings:
        """通过 matchbox 获取用户配置的云端 embedding 模型"""
        return matchbox().get_user_embedding(self.user_id)

    def start_background_build(self, force_rebuild: bool = False) -> dict:
        task_key = _build_task_key(self.user_id, self.project_name)
        now = datetime.now(timezone.utc).isoformat()
        with _build_state_lock:
            current = dict(_build_state_registry.get(task_key) or {})
            if current.get("status") in {"queued", "building"}:
                return current
            current.update({
                "status": "queued",
                "stage": "queued",
                "error": "",
                "started_at": now,
                "finished_at": "",
                "progress": {
                    "total_files": 0,
                    "done_files": 0,
                    "total_chunks": 0,
                    "embedded_chunks": 0,
                    "changed_files": 0,
                    "removed_files": 0,
                    "reused_files": 0,
                },
            })
            _build_state_registry[task_key] = current

        def _run() -> None:
            try:
                self.build_index(force_rebuild=force_rebuild)
            except Exception:
                pass

        thread = threading.Thread(
            target=_run,
            daemon=True,
            name=f"semantic_index_build_{task_key}",
        )
        thread.start()
        return self.get_build_state()

    def get_build_state(self) -> dict:
        task_key = _build_task_key(self.user_id, self.project_name)
        with _build_state_lock:
            stored = dict(_build_state_registry.get(task_key) or {})
        if stored:
            stored["progress"] = dict(stored.get("progress") or {})
            return stored
        metadata = self._load_meta() if os.path.isdir(self._persist_dir) else {}
        if os.path.isdir(self._persist_dir):
            return {
                "status": "ready",
                "stage": "ready",
                "error": "",
                "started_at": metadata.get("built_at", ""),
                "finished_at": metadata.get("built_at", ""),
                "progress": {
                    "total_files": len(metadata.get("file_hashes", {})),
                    "done_files": len(metadata.get("file_hashes", {})),
                    "total_chunks": int(metadata.get("chunk_count", 0) or 0),
                    "embedded_chunks": int(metadata.get("chunk_count", 0) or 0),
                },
            }
        return {
            "status": "not_built",
            "stage": "idle",
            "error": "",
            "started_at": "",
            "finished_at": "",
            "progress": {
                "total_files": 0,
                "done_files": 0,
                "total_chunks": 0,
                "embedded_chunks": 0,
            },
        }

    def _set_build_state(self, **fields) -> dict:
        task_key = _build_task_key(self.user_id, self.project_name)
        with _build_state_lock:
            current = dict(_build_state_registry.get(task_key) or {})
            if "progress" in fields:
                fields["progress"] = dict(fields.get("progress") or {})
            current.update(fields)
            _build_state_registry[task_key] = current
            return dict(current)

    # ==================== 索引构建 ====================

    def build_index(self, force_rebuild: bool = False) -> dict:
        """
        构建/更新向量索引。

        真增量更新策略：
        - 首次调用时全量构建
        - 后续调用仅删除变更文件对应的旧分块，并为变更文件重新编码
        - 未变更文件直接复用已有向量与分块缓存
        - force_rebuild=True 时强制全量重建
        """
        if not os.path.isdir(self._project_path):
            raise FileNotFoundError(f"项目不存在: {self._project_path}")

        started_at = datetime.now(timezone.utc).isoformat()
        self._set_build_state(
            status="building",
            stage="prepare",
            error="",
            started_at=started_at,
            finished_at="",
            progress={
                "total_files": 0,
                "done_files": 0,
                "total_chunks": 0,
                "embedded_chunks": 0,
                "changed_files": 0,
                "removed_files": 0,
                "reused_files": 0,
            },
        )

        try:
            metadata = self._load_meta() if os.path.isdir(self._persist_dir) else {}
            chunker = SemanticChunker()
            chunk_state = chunker.chunk_project_state(self.user_id, self.project_name, use_cache=True)
            chunks_by_file = {
                str(rel_path): list(file_chunks)
                for rel_path, file_chunks in dict(chunk_state.get("chunks_by_file") or {}).items()
            }
            all_chunks = list(chunk_state.get("chunks") or [])
            current_hashes = {
                str(rel_path): str(file_hash or "")
                for rel_path, file_hash in dict(chunk_state.get("file_hashes") or {}).items()
            }

            # 合并附件 chunks（受 per-project 开关控制，默认开）
            try:
                from core.project_settings import is_attachment_index_enabled

                if is_attachment_index_enabled(self.user_id, self.project_name):
                    att_chunks_by_file, att_hashes = self._collect_attachment_chunks()
                    if att_chunks_by_file:
                        chunks_by_file.update(att_chunks_by_file)
                        for rel_path, file_chunks in att_chunks_by_file.items():
                            all_chunks.extend(file_chunks)
                        current_hashes.update(att_hashes)
            except Exception as exc:  # 附件扫描失败不应阻断项目正文索引
                import logging
                logging.getLogger("vector_index").warning(
                    "[vector_index] 收集附件 chunks 失败：%s", exc
                )

            total_files = len(current_hashes)
            delta = self._compute_index_delta(metadata, current_hashes)
            metadata_supported = self._supports_incremental_meta(metadata)
            full_rebuild = (
                force_rebuild
                or not os.path.isdir(self._persist_dir)
                or not metadata_supported
            )
            file_doc_ids = self._normalize_file_doc_ids(metadata.get("file_doc_ids", {}))

            if not full_rebuild and not (
                delta["added_files"] or delta["changed_files"] or delta["removed_files"]
            ) and metadata:
                metadata["reused"] = True
                self._set_build_state(
                    status="ready",
                    stage="ready",
                    error="",
                    started_at=metadata.get("built_at", started_at),
                    finished_at=metadata.get("built_at", started_at),
                    progress={
                        "total_files": len(metadata.get("file_hashes", {})),
                        "done_files": len(metadata.get("file_hashes", {})),
                        "total_chunks": int(metadata.get("chunk_count", 0) or 0),
                        "embedded_chunks": int(metadata.get("chunk_count", 0) or 0),
                        "changed_files": 0,
                        "removed_files": 0,
                        "reused_files": len(metadata.get("file_hashes", {})),
                    },
                )
                return metadata

            if not all_chunks:
                raise RuntimeError("未找到可用于构建向量索引的项目文本。")

            embeddings = self._get_embeddings()
            target_files = list(dict.fromkeys([*delta["added_files"], *delta["changed_files"]]))
            removed_files = list(delta["removed_files"])
            target_chunk_total = len(all_chunks) if full_rebuild else sum(
                len(chunks_by_file.get(rel_path, [])) for rel_path in target_files
            )
            self._set_build_state(
                status="building",
                stage="syncing",
                progress={
                    "total_files": total_files if full_rebuild else len(target_files) + len(removed_files),
                    "done_files": 0,
                    "total_chunks": target_chunk_total,
                    "embedded_chunks": 0,
                    "changed_files": len(target_files),
                    "removed_files": len(removed_files),
                    "reused_files": max(0, total_files - len(target_files)),
                },
            )

            batch_size = 10
            if full_rebuild:
                if os.path.isdir(self._persist_dir):
                    shutil.rmtree(self._persist_dir)

                vector_store: Chroma | None = None
                rebuilt_doc_ids: dict[str, list[str]] = {}
                processed_files = 0
                embedded_chunks = 0

                for rel_path, file_chunks in chunks_by_file.items():
                    ids, documents = self._file_chunks_to_documents(rel_path, file_chunks)
                    rebuilt_doc_ids[rel_path] = ids

                    if documents:
                        if vector_store is None:
                            first_batch = documents[:batch_size]
                            first_ids = ids[:batch_size]
                            vector_store = Chroma.from_documents(
                                documents=first_batch,
                                embedding=embeddings,
                                ids=first_ids,
                                collection_name=self._collection_name,
                                persist_directory=self._persist_dir,
                            )
                            embedded_chunks += len(first_batch)
                            for i in range(batch_size, len(documents), batch_size):
                                batch_documents = documents[i:i + batch_size]
                                batch_ids = ids[i:i + batch_size]
                                vector_store.add_documents(batch_documents, ids=batch_ids)
                                embedded_chunks += len(batch_documents)
                        else:
                            for i in range(0, len(documents), batch_size):
                                batch_documents = documents[i:i + batch_size]
                                batch_ids = ids[i:i + batch_size]
                                vector_store.add_documents(batch_documents, ids=batch_ids)
                                embedded_chunks += len(batch_documents)

                    processed_files += 1
                    self._set_build_state(
                        status="building",
                        stage="embedding",
                        progress={
                            "total_files": total_files,
                            "done_files": processed_files,
                            "total_chunks": target_chunk_total,
                            "embedded_chunks": embedded_chunks,
                            "changed_files": total_files,
                            "removed_files": 0,
                            "reused_files": 0,
                        },
                    )

                if vector_store is None:
                    raise RuntimeError("未找到可用于构建向量索引的项目文本。")

                file_doc_ids = rebuilt_doc_ids
            else:
                vector_store = Chroma(
                    collection_name=self._collection_name,
                    embedding_function=embeddings,
                    persist_directory=self._persist_dir,
                )
                delete_ids: list[str] = []
                for rel_path in [*removed_files, *delta["changed_files"]]:
                    delete_ids.extend(file_doc_ids.get(rel_path, []))
                if delete_ids:
                    vector_store.delete(ids=delete_ids)

                for rel_path in removed_files:
                    file_doc_ids.pop(rel_path, None)

                processed_files = len(removed_files)
                embedded_chunks = 0
                if removed_files:
                    self._set_build_state(
                        status="building",
                        stage="embedding",
                        progress={
                            "total_files": len(target_files) + len(removed_files),
                            "done_files": processed_files,
                            "total_chunks": target_chunk_total,
                            "embedded_chunks": embedded_chunks,
                            "changed_files": len(target_files),
                            "removed_files": len(removed_files),
                            "reused_files": max(0, total_files - len(target_files)),
                        },
                    )

                for rel_path in target_files:
                    ids, documents = self._file_chunks_to_documents(rel_path, chunks_by_file.get(rel_path, []))
                    for i in range(0, len(documents), batch_size):
                        batch_documents = documents[i:i + batch_size]
                        batch_ids = ids[i:i + batch_size]
                        vector_store.add_documents(batch_documents, ids=batch_ids)
                        embedded_chunks += len(batch_documents)
                        self._set_build_state(
                            status="building",
                            stage="embedding",
                            progress={
                                "total_files": len(target_files) + len(removed_files),
                                "done_files": processed_files,
                                "total_chunks": target_chunk_total,
                                "embedded_chunks": embedded_chunks,
                                "changed_files": len(target_files),
                                "removed_files": len(removed_files),
                                "reused_files": max(0, total_files - len(target_files)),
                            },
                        )
                    file_doc_ids[rel_path] = ids
                    processed_files += 1
                    self._set_build_state(
                        status="building",
                        stage="embedding",
                        progress={
                            "total_files": len(target_files) + len(removed_files),
                            "done_files": processed_files,
                            "total_chunks": target_chunk_total,
                            "embedded_chunks": embedded_chunks,
                            "changed_files": len(target_files),
                            "removed_files": len(removed_files),
                            "reused_files": max(0, total_files - len(target_files)),
                        },
                    )

            meta = {
                "version": "2.0",
                "built_at": datetime.now(timezone.utc).isoformat(),
                "project": self.project_name,
                "user_id": self.user_id,
                "chunk_count": sum(len(ids) for ids in file_doc_ids.values()),
                "file_hashes": current_hashes,
                "file_doc_ids": file_doc_ids,
                "change_summary": {
                    "added_files": len(delta["added_files"]),
                    "changed_files": len(delta["changed_files"]),
                    "removed_files": len(delta["removed_files"]),
                    "reused_files": max(0, total_files - len(target_files)),
                },
                "reused": False,
            }
            self._save_meta(meta)
            self._set_build_state(
                status="ready",
                stage="ready",
                error="",
                started_at=started_at,
                finished_at=meta["built_at"],
                progress={
                    "total_files": total_files,
                    "done_files": total_files,
                    "total_chunks": int(meta.get("chunk_count", 0) or 0),
                    "embedded_chunks": int(meta.get("chunk_count", 0) or 0),
                    "changed_files": len(target_files),
                    "removed_files": len(removed_files),
                    "reused_files": max(0, total_files - len(target_files)),
                },
            )
            return meta
        except Exception as e:
            self._set_build_state(
                status="error",
                stage="error",
                error=str(e),
                finished_at=datetime.now(timezone.utc).isoformat(),
            )
            raise

    # ==================== 查询 ====================

    def query(
        self,
        query_text: str,
        k: int = 8,
        filter: Optional[dict] = None,
        score_threshold: float = 0.0,
    ) -> list[SearchHit]:
        """
        语义相似度搜索。

        Args:
            query_text: 自然语言查询
            k: 返回结果数量
            filter: Chroma 元数据过滤条件，如 {"format_key": "arc"}
            score_threshold: 最低相似度分数阈值（0.0 = 不过滤）
        """
        if not os.path.isdir(self._persist_dir):
            self.start_background_build(force_rebuild=False)
            raise IndexBuildNotReadyError(self.get_status())

        embeddings = self._get_embeddings()
        vector_store = Chroma(
            collection_name=self._collection_name,
            embedding_function=embeddings,
            persist_directory=self._persist_dir,
        )

        # 执行搜索
        search_kwargs = {"k": k}
        if filter:
            search_kwargs["filter"] = filter

        results = vector_store.similarity_search_with_score(query_text, **search_kwargs)

        # 组装 SearchHit
        hits: list[SearchHit] = []
        for idx, (doc, score) in enumerate(results):
            if score_threshold > 0 and score < score_threshold:
                continue
            source = doc.metadata.get("source", "")
            abs_path = os.path.join(self._project_path, source) if source else ""
            source_type = str(doc.metadata.get("source_type") or "project")
            hits.append(SearchHit(
                index=idx,
                file_path=abs_path,
                rel_path=source,
                format_key=doc.metadata.get("format_key", ""),
                start_line=doc.metadata.get("start_line", 0),
                end_line=doc.metadata.get("end_line", 0),
                narrative_ref=doc.metadata.get("narrative_ref", ""),
                match_text=doc.page_content,
                score=float(score),
                source_type=source_type,
                attachment_id=str(doc.metadata.get("attachment_id") or ""),
                attachment_filename=str(doc.metadata.get("attachment_filename") or ""),
                attachment_chunk_index=int(doc.metadata.get("attachment_chunk_index") or 0),
            ))

        return hits

    # ==================== 状态管理 ====================

    def get_status(self, check_freshness: bool = True) -> dict:
        """索引状态"""
        exists = os.path.isdir(self._persist_dir)
        metadata = self._load_meta() if exists else {}
        build_state = self.get_build_state()
        needs_rebuild = False
        if exists and metadata and not self._supports_incremental_meta(metadata):
            needs_rebuild = True
            if build_state.get("status") not in {"queued", "building", "error"}:
                build_state = {
                    **build_state,
                    "status": "stale",
                    "stage": "reindex",
                }
        elif check_freshness and exists and metadata and build_state.get("status") not in {"queued", "building", "error"}:
            try:
                needs_rebuild = self._needs_rebuild(metadata)
            except Exception:
                needs_rebuild = False
            if needs_rebuild:
                build_state = {
                    **build_state,
                    "status": "stale",
                    "stage": "stale",
                }
        return {
            "project": self.project_name,
            "user_id": self.user_id,
            "exists": exists,
            "persist_dir": self._persist_dir,
            "metadata": metadata,
            "needs_rebuild": needs_rebuild,
            "build_state": build_state,
        }

    def reset(self) -> dict:
        """删除索引"""
        removed = False
        if os.path.isdir(self._persist_dir):
            shutil.rmtree(self._persist_dir)
            removed = True
        return {
            "project": self.project_name,
            "user_id": self.user_id,
            "removed": removed,
        }

    # ==================== 内部方法 ====================

    def _collect_attachment_chunks(self) -> tuple[dict[str, list[SemanticChunk]], dict[str, str]]:
        """扫描项目 .attachments/ 下所有附件，转换为 SemanticChunk。

        返回：
        - chunks_by_file: ``{rel_path: [SemanticChunk, ...]}``，rel_path 形如
          ``.attachments/{attachment_id}/full.txt``。
        - file_hashes: ``{rel_path: hash}``，hash 直接复用 attachment_id（已是
          sha256 前 16 位，足够稳定 + 可比较）。

        附件分片 → SemanticChunk 映射：
        - text = chunk 正文
        - metadata.source_type = 'attachment'
        - metadata.format_key = 'attachment'
        - metadata.source = rel_path
        - metadata.attachment_id / attachment_filename / attachment_chunk_index
        - narrative_ref = '附件 > {filename} > 第 K 部分（共 N）'
        """
        try:
            from agents.attachment.storage import (
                ATTACHMENTS_DIR_NAME,
                get_attachment_meta,
                load_chunks,
            )
        except Exception:
            return {}, {}

        attachments_root = os.path.join(self._project_path, ATTACHMENTS_DIR_NAME)
        if not os.path.isdir(attachments_root):
            return {}, {}

        chunks_by_file: dict[str, list[SemanticChunk]] = {}
        file_hashes: dict[str, str] = {}

        for entry in sorted(os.listdir(attachments_root)):
            attachment_dir = os.path.join(attachments_root, entry)
            if not os.path.isdir(attachment_dir):
                continue
            attachment_id = entry

            meta = get_attachment_meta(self.user_id, self.project_name, attachment_id)
            if meta is None:
                continue

            try:
                raw_chunks = load_chunks(self.user_id, self.project_name, attachment_id)
            except Exception:
                continue

            if not raw_chunks:
                continue

            rel_path = f"{ATTACHMENTS_DIR_NAME}/{attachment_id}/full.txt".replace("\\", "/")
            total = len(raw_chunks)
            semantic_chunks: list[SemanticChunk] = []
            for chunk_index, chunk_text in enumerate(raw_chunks):
                text = (chunk_text or "").strip()
                if not text:
                    continue
                narrative_ref = f"附件 > {meta.filename} > 第 {chunk_index + 1} 部分（共 {total}）"
                semantic_chunks.append(SemanticChunk(
                    text=text,
                    metadata={
                        "source": rel_path,
                        "source_type": "attachment",
                        "format_key": "attachment",
                        "attachment_id": attachment_id,
                        "attachment_filename": meta.filename,
                        "attachment_chunk_index": chunk_index,
                        "narrative_ref": narrative_ref,
                    },
                    start_line=0,
                    end_line=0,
                    narrative_ref=narrative_ref,
                ))

            if not semantic_chunks:
                continue

            chunks_by_file[rel_path] = semantic_chunks
            # attachment_id 本身已是 sha256[:16]，作为内容指纹完全够用
            file_hashes[rel_path] = attachment_id

        return chunks_by_file, file_hashes

    def _chunks_to_documents(self, chunks: list[SemanticChunk]) -> list[Document]:
        """将 SemanticChunk 列表转换为 LangChain Document"""
        documents: list[Document] = []
        for chunk in chunks:
            meta = {
                **chunk.metadata,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "narrative_ref": chunk.narrative_ref,
            }
            documents.append(Document(
                page_content=chunk.text,
                metadata=meta,
            ))
        return documents

    def _file_chunks_to_documents(self, rel_path: str, chunks: list[SemanticChunk]) -> tuple[list[str], list[Document]]:
        """将单文件分块转换为 Document，并生成稳定文档 ID。"""
        ids: list[str] = []
        documents: list[Document] = []
        for idx, chunk in enumerate(chunks):
            meta = {
                **chunk.metadata,
                "source": rel_path,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "narrative_ref": chunk.narrative_ref,
            }
            documents.append(Document(
                page_content=chunk.text,
                metadata=meta,
            ))
            ids.append(self._build_chunk_id(rel_path, chunk, idx))
        return ids, documents

    def _build_chunk_id(self, rel_path: str, chunk: SemanticChunk, ordinal: int) -> str:
        """为向量库生成稳定的 chunk 文档 ID。"""
        raw = json.dumps(
            {
                "rel_path": rel_path,
                "ordinal": ordinal,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "narrative_ref": chunk.narrative_ref,
                "sub_chunk_idx": chunk.metadata.get("sub_chunk_idx"),
                "text_hash": hashlib.md5(chunk.text.encode("utf-8")).hexdigest(),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        digest = hashlib.md5(f"{self.user_id}:{self.project_name}:{raw}".encode("utf-8")).hexdigest()
        return f"chunk_{digest}"

    def _normalize_file_doc_ids(self, raw: dict | None) -> dict[str, list[str]]:
        """规范化文件到文档 ID 的映射。"""
        if not isinstance(raw, dict):
            return {}
        normalized: dict[str, list[str]] = {}
        for rel_path, ids in raw.items():
            if not isinstance(ids, list):
                continue
            normalized[str(rel_path)] = [str(item) for item in ids if item]
        return normalized

    def _supports_incremental_meta(self, metadata: dict) -> bool:
        """判断元数据是否具备增量更新所需的信息。"""
        return bool(
            isinstance(metadata, dict)
            and isinstance(metadata.get("file_hashes"), dict)
            and isinstance(metadata.get("file_doc_ids"), dict)
        )

    def _compute_file_hashes(self) -> dict[str, str]:
        """计算项目所有文本文件的 MD5 哈希"""
        hashes: dict[str, str] = {}
        files = collect_project_files(self.user_id, self.project_name)
        for pf in files:
            try:
                hashes[pf.rel_path] = hashlib.md5(pf.content.encode("utf-8")).hexdigest()
            except Exception:
                hashes[pf.rel_path] = ""
        return hashes

    def _compute_index_delta(self, metadata: dict, current_hashes: dict[str, str]) -> dict[str, list[str]]:
        """基于索引元数据与当前文件哈希，计算增量更新差异。"""
        stored_hashes = metadata.get("file_hashes", {}) if isinstance(metadata, dict) else {}
        if not isinstance(stored_hashes, dict):
            stored_hashes = {}

        added_files = sorted(
            rel_path for rel_path in current_hashes.keys()
            if rel_path not in stored_hashes
        )
        removed_files = sorted(
            rel_path for rel_path in stored_hashes.keys()
            if rel_path not in current_hashes
        )
        changed_files = sorted(
            rel_path
            for rel_path, current_hash in current_hashes.items()
            if rel_path in stored_hashes and stored_hashes.get(rel_path) != current_hash
        )
        return {
            "added_files": added_files,
            "changed_files": changed_files,
            "removed_files": removed_files,
        }

    def _needs_rebuild(self, metadata: dict) -> bool:
        """比对文件哈希判断是否需要重建"""
        if not self._supports_incremental_meta(metadata):
            return True
        current_hashes = self._compute_file_hashes()
        delta = self._compute_index_delta(metadata, current_hashes)
        return bool(delta["added_files"] or delta["changed_files"] or delta["removed_files"])

    def _load_meta(self) -> dict:
        """加载索引元数据"""
        if not os.path.exists(self._meta_path):
            return {}
        try:
            with open(self._meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_meta(self, metadata: dict) -> None:
        """保存索引元数据"""
        os.makedirs(self._persist_dir, exist_ok=True)
        try:
            with open(self._meta_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
