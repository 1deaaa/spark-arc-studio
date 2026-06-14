"""
项目级向量索引服务

使用 LanceDB 持久化向量库 + matchbox 云端 embedding。
支持懒构建、哈希增量更新、元数据过滤查询。
"""

import hashlib
import json
import math
import os
import shutil
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from core.utils import get_project_path
from llm.agen_matchbox import matchbox
from story.project_files import collect_project_files
from story.semantic_chunker import SemanticChunker, SemanticChunk
from .embedding_contract import (
    QWEN3_EMBEDDING_BATCH_SIZE,
    build_query_text,
    embedding_contract_metadata,
    embedding_extra_body,
)


_build_state_registry: dict[str, dict] = {}
_build_state_lock = threading.Lock()


# ==================== 辅助函数 ====================

def _safe_collection_name(user_id: str, project_name: str) -> str:
    """生成 LanceDB 合法的表名。

    LanceDB 表名保持 ASCII，中文项目名通过 MD5 哈希转换为稳定标识符。
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


class IndexBuildCancelledError(RuntimeError):
    """索引构建被上游高优先级操作取消。"""


_ACTIVE_BUILD_STATUSES = {"queued", "building", "cancelling"}


# ==================== 向量索引服务 ====================

class VectorIndexService:
    """项目级向量索引服务（LanceDB + matchbox embedding）"""

    def __init__(self, user_id: str, project_name: str):
        self.user_id = str(user_id)
        self.project_name = project_name
        self._project_path = get_project_path(user_id, project_name)
        self._persist_dir = os.path.join(self._project_path, ".vector_index_lancedb")
        self._meta_path = os.path.join(self._persist_dir, "meta.json")
        self._collection_name = _safe_collection_name(user_id, project_name)

    # ==================== Embedding ====================

    def _get_embeddings(self) -> OpenAIEmbeddings:
        """通过 matchbox 获取用户配置的 embedding 模型。"""
        try:
            from core.system_settings import get_local_embedding_enabled
            from agents.vector_index.local_embedding import (
                LOCAL_EMBEDDING_API_KEY,
                LOCAL_EMBEDDING_BASE_URL,
                is_local_embedding_alive,
            )

            if get_local_embedding_enabled() and is_local_embedding_alive(timeout=1.0):
                return OpenAIEmbeddings(
                    model=embedding_contract_metadata()["model"],
                    api_key=LOCAL_EMBEDDING_API_KEY,
                    base_url=LOCAL_EMBEDDING_BASE_URL,
                    check_embedding_ctx_length=False,
                    extra_body=embedding_extra_body(),
                )
        except Exception:
            pass

        return matchbox().get_user_embedding(
            self.user_id,
            extra_body=embedding_extra_body(),
        )

    def _connect_db(self):
        """连接当前项目的 LanceDB 本地库。"""
        import lancedb

        os.makedirs(self._persist_dir, exist_ok=True)
        return lancedb.connect(self._persist_dir)

    @staticmethod
    def _list_tables(db: Any) -> set[str]:
        """读取 LanceDB 表名，兼容新旧 Python API。"""
        list_tables = getattr(db, "list_tables", None)
        if callable(list_tables):
            response = list_tables()
            tables = getattr(response, "tables", response)
            return {str(name) for name in tables}
        table_names = getattr(db, "table_names", None)
        if callable(table_names):
            return {str(name) for name in table_names()}
        return set()

    def _open_table(self):
        db = self._connect_db()
        try:
            return db.open_table(self._collection_name)
        except Exception as exc:
            raise IndexBuildNotReadyError(self.get_status(check_freshness=False)) from exc

    def _table_exists(self) -> bool:
        if not os.path.isdir(self._persist_dir):
            return False
        try:
            db = self._connect_db()
            return self._collection_name in self._list_tables(db)
        except Exception:
            return False

    @staticmethod
    def _escape_lance_sql(value: str) -> str:
        return str(value).replace("'", "''")

    @staticmethod
    def _build_filter_expression(filter_payload: Optional[dict]) -> str | None:
        """把工具层的简单 metadata filter 转成 LanceDB where 表达式。"""
        if not filter_payload:
            return None
        format_value = filter_payload.get("format_key")
        if isinstance(format_value, str):
            return f"format_key = '{VectorIndexService._escape_lance_sql(format_value)}'"
        if isinstance(format_value, dict) and "$in" in format_value:
            values = [
                f"'{VectorIndexService._escape_lance_sql(str(item))}'"
                for item in (format_value.get("$in") or [])
                if str(item)
            ]
            if values:
                return f"format_key IN ({', '.join(values)})"
        return None

    @staticmethod
    def _embed_documents(embeddings: OpenAIEmbeddings, documents: list[Document]) -> list[list[float]]:
        texts = [doc.page_content for doc in documents]
        return [VectorIndexService._normalize_vector(vector) for vector in embeddings.embed_documents(texts)]

    @staticmethod
    def _embed_query(embeddings: OpenAIEmbeddings, query_text: str) -> list[float]:
        return VectorIndexService._normalize_vector(embeddings.embed_query(build_query_text(query_text)))

    @staticmethod
    def _normalize_vector(vector: list[float]) -> list[float]:
        """把嵌入向量归一化到单位长度。"""
        values = [float(value) for value in vector]
        norm = math.sqrt(sum(value * value for value in values))
        if norm <= 0:
            return values
        return [value / norm for value in values]

    @staticmethod
    def _is_embedding_contract_compatible(metadata: dict) -> bool:
        """判断已有索引是否符合当前嵌入契约。"""
        expected = embedding_contract_metadata()
        stored = metadata.get("embedding") if isinstance(metadata, dict) else None
        if not isinstance(stored, dict):
            return False
        keys = ("version", "model", "dimensions", "metric", "query_instruction")
        return all(stored.get(key) == expected.get(key) for key in keys)

    def _documents_to_rows(
        self,
        ids: list[str],
        documents: list[Document],
        vectors: list[list[float]],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for doc_id, doc, vector in zip(ids, documents, vectors):
            meta = dict(doc.metadata or {})
            rows.append({
                "id": str(doc_id),
                "vector": [float(value) for value in vector],
                "text": doc.page_content,
                "source": str(meta.get("source") or ""),
                "format_key": str(meta.get("format_key") or ""),
                "source_type": str(meta.get("source_type") or "project"),
                "start_line": int(meta.get("start_line") or 0),
                "end_line": int(meta.get("end_line") or 0),
                "narrative_ref": str(meta.get("narrative_ref") or ""),
                "attachment_id": str(meta.get("attachment_id") or ""),
                "attachment_filename": str(meta.get("attachment_filename") or ""),
                "attachment_chunk_index": int(meta.get("attachment_chunk_index") or 0),
                "metadata_json": json.dumps(meta, ensure_ascii=False),
            })
        return rows

    def _create_or_add_rows(self, rows: list[dict[str, Any]], *, overwrite: bool = False) -> None:
        if not rows:
            return
        db = self._connect_db()
        if overwrite or self._collection_name not in self._list_tables(db):
            db.create_table(self._collection_name, data=rows, mode="overwrite")
            return
        table = db.open_table(self._collection_name)
        table.add(rows)

    def _delete_ids(self, ids: list[str]) -> None:
        if not ids or not self._table_exists():
            return
        quoted = ", ".join(f"'{self._escape_lance_sql(item)}'" for item in ids if item)
        if not quoted:
            return
        table = self._open_table()
        table.delete(f"id IN ({quoted})")

    def _public_build_state(self, payload: dict | None) -> dict:
        state = {
            key: value
            for key, value in dict(payload or {}).items()
            if not str(key).startswith("_")
        }
        state["progress"] = dict(state.get("progress") or {})
        return state

    def start_background_build(self, force_rebuild: bool = False) -> dict:
        task_key = _build_task_key(self.user_id, self.project_name)
        now = datetime.now(timezone.utc).isoformat()
        cancel_event = threading.Event()
        with _build_state_lock:
            current = dict(_build_state_registry.get(task_key) or {})
            if current.get("status") in _ACTIVE_BUILD_STATUSES:
                current["_pending_refresh"] = True
                current["_pending_force_rebuild"] = bool(current.get("_pending_force_rebuild")) or bool(force_rebuild)
                _build_state_registry[task_key] = current
                return self._public_build_state(current)
            current.update({
                "status": "queued",
                "stage": "queued",
                "error": "",
                "started_at": now,
                "finished_at": "",
                "_pending_refresh": False,
                "_pending_force_rebuild": False,
                "_cancel_event": cancel_event,
                "_thread": None,
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
            next_force_rebuild = force_rebuild
            while True:
                try:
                    self.build_index(force_rebuild=next_force_rebuild)
                except IndexBuildCancelledError:
                    pass
                except Exception:
                    pass
                with _build_state_lock:
                    latest = dict(_build_state_registry.get(task_key) or {})
                    cancelled = bool(cancel_event.is_set())
                    rerun = bool(latest.get("_pending_refresh")) and not cancelled
                    next_force_rebuild = bool(latest.get("_pending_force_rebuild"))
                    latest["_pending_refresh"] = False
                    latest["_pending_force_rebuild"] = False
                    if cancelled and latest.get("status") not in {"cancelled", "error"}:
                        latest.update({
                            "status": "cancelled",
                            "stage": "cancelled",
                            "error": "向量索引构建已取消",
                            "finished_at": datetime.now(timezone.utc).isoformat(),
                        })
                    _build_state_registry[task_key] = latest
                if not rerun:
                    break

        thread = threading.Thread(
            target=_run,
            daemon=True,
            name=f"semantic_index_build_{task_key}",
        )
        thread.start()
        with _build_state_lock:
            latest = dict(_build_state_registry.get(task_key) or {})
            if latest.get("_cancel_event") is cancel_event:
                latest["_thread"] = thread
                _build_state_registry[task_key] = latest
        return self.get_build_state()

    def ensure_background_build_started(self, check_freshness: bool = True) -> dict:
        status = self.get_status(check_freshness=check_freshness)
        build_state = dict(status.get("build_state") or {})
        if build_state.get("status") in _ACTIVE_BUILD_STATUSES:
            return status
        if not status.get("exists") or status.get("needs_rebuild"):
            build_state = self.start_background_build(force_rebuild=False)
            return {
                **status,
                "build_state": build_state,
            }
        return status

    def get_build_state(self) -> dict:
        task_key = _build_task_key(self.user_id, self.project_name)
        with _build_state_lock:
            stored = dict(_build_state_registry.get(task_key) or {})
        if stored:
            return self._public_build_state(stored)
        exists = self._table_exists()
        metadata = self._load_meta() if exists else {}
        if exists:
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

    def _get_cancel_event(self) -> threading.Event | None:
        task_key = _build_task_key(self.user_id, self.project_name)
        with _build_state_lock:
            event = (_build_state_registry.get(task_key) or {}).get("_cancel_event")
        return event if isinstance(event, threading.Event) else None

    def _check_cancelled(self) -> None:
        event = self._get_cancel_event()
        if event and event.is_set():
            raise IndexBuildCancelledError("向量索引构建已取消")

    @staticmethod
    def release_process_resources() -> None:
        """保留资源释放入口，供删除项目流程调用。"""
        return None

    def cancel_background_build(self, wait_timeout: float = 5.0) -> dict:
        """请求取消后台索引构建，并在限定时间内等待线程主动退出。"""
        task_key = _build_task_key(self.user_id, self.project_name)
        with _build_state_lock:
            current = dict(_build_state_registry.get(task_key) or {})
            status = current.get("status")
            event = current.get("_cancel_event")
            thread = current.get("_thread")
            if status not in _ACTIVE_BUILD_STATUSES or not isinstance(event, threading.Event):
                return self._public_build_state(current)
            event.set()
            current.update({
                "status": "cancelling",
                "stage": "cancelling",
                "error": "正在取消向量索引构建",
                "_pending_refresh": False,
                "_pending_force_rebuild": False,
            })
            _build_state_registry[task_key] = current

        if isinstance(thread, threading.Thread) and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=max(0.0, float(wait_timeout)))

        self.release_process_resources()
        return self.get_build_state()

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
            self._check_cancelled()
            metadata = self._load_meta() if self._table_exists() else {}
            chunker = SemanticChunker()
            chunk_state = chunker.chunk_project_state(self.user_id, self.project_name, use_cache=True)
            self._check_cancelled()
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
            embedding_supported = self._is_embedding_contract_compatible(metadata)
            full_rebuild = (
                force_rebuild
                or not self._table_exists()
                or not metadata_supported
                or not embedding_supported
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

            self._check_cancelled()
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

            batch_size = QWEN3_EMBEDDING_BATCH_SIZE
            if full_rebuild:
                if os.path.isdir(self._persist_dir):
                    shutil.rmtree(self._persist_dir)

                rebuilt_doc_ids: dict[str, list[str]] = {}
                processed_files = 0
                embedded_chunks = 0

                for rel_path, file_chunks in chunks_by_file.items():
                    self._check_cancelled()
                    ids, documents = self._file_chunks_to_documents(rel_path, file_chunks)
                    rebuilt_doc_ids[rel_path] = ids

                    if documents:
                        for i in range(0, len(documents), batch_size):
                            self._check_cancelled()
                            batch_documents = documents[i:i + batch_size]
                            batch_ids = ids[i:i + batch_size]
                            vectors = self._embed_documents(embeddings, batch_documents)
                            rows = self._documents_to_rows(batch_ids, batch_documents, vectors)
                            self._create_or_add_rows(
                                rows,
                                overwrite=(embedded_chunks == 0 and processed_files == 0),
                            )
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

                file_doc_ids = rebuilt_doc_ids
            else:
                # ---- chunk 级增量：基于 chunk_id 做 diff ----
                # _build_chunk_id 已把 chunk 文本的 MD5 编码进 id，
                # 所以「id 相同」就等价于「分块文本完全一致」，可以原样复用旧向量。
                delete_ids: list[str] = []
                # 1) 文件被删除：该文件下所有旧 chunk 全删
                for rel_path in removed_files:
                    self._check_cancelled()
                    delete_ids.extend(file_doc_ids.get(rel_path, []))

                # 2) added_files：旧里没有这个文件，所有 chunk 都需新 embed
                # 3) changed_files：按 chunk_id 取差集，仅 embed 真正变化或新增的分块
                embed_pairs_by_file: dict[str, list[tuple[str, Document]]] = {}
                final_doc_ids_by_file: dict[str, list[str]] = {}
                reused_chunk_count = 0

                for rel_path in delta["added_files"]:
                    self._check_cancelled()
                    new_ids, new_documents = self._file_chunks_to_documents(
                        rel_path, chunks_by_file.get(rel_path, [])
                    )
                    final_doc_ids_by_file[rel_path] = list(new_ids)
                    embed_pairs_by_file[rel_path] = list(zip(new_ids, new_documents))

                for rel_path in delta["changed_files"]:
                    self._check_cancelled()
                    new_ids, new_documents = self._file_chunks_to_documents(
                        rel_path, chunks_by_file.get(rel_path, [])
                    )
                    old_ids = list(file_doc_ids.get(rel_path, []))
                    old_id_set = set(old_ids)
                    new_id_set = set(new_ids)

                    # 仅删除：旧里有、新里没有
                    obsolete_ids = [cid for cid in old_ids if cid not in new_id_set]
                    delete_ids.extend(obsolete_ids)

                    # 仅 embed：新里有、旧里没有
                    pairs_to_embed = [
                        (cid, doc)
                        for cid, doc in zip(new_ids, new_documents)
                        if cid not in old_id_set
                    ]
                    final_doc_ids_by_file[rel_path] = list(new_ids)
                    embed_pairs_by_file[rel_path] = pairs_to_embed
                    reused_chunk_count += len(old_id_set & new_id_set)

                if delete_ids:
                    self._check_cancelled()
                    self._delete_ids(delete_ids)

                # 同步元数据中的 file_doc_ids：删除文件清掉条目，其他覆盖为最新完整 id 列表
                for rel_path in removed_files:
                    file_doc_ids.pop(rel_path, None)
                for rel_path, ids in final_doc_ids_by_file.items():
                    file_doc_ids[rel_path] = ids

                # 重新计算待 embed 的 chunk 总数（区别于"target_files 全部 chunk 总数"）
                target_chunk_total = sum(
                    len(pairs) for pairs in embed_pairs_by_file.values()
                )

                processed_files = len(removed_files)
                embedded_chunks = 0
                if removed_files or reused_chunk_count:
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
                    self._check_cancelled()
                    pairs = embed_pairs_by_file.get(rel_path, [])
                    if pairs:
                        chunk_ids = [cid for cid, _ in pairs]
                        documents = [doc for _, doc in pairs]
                        for i in range(0, len(documents), batch_size):
                            self._check_cancelled()
                            batch_documents = documents[i:i + batch_size]
                            batch_ids = chunk_ids[i:i + batch_size]
                            vectors = self._embed_documents(embeddings, batch_documents)
                            rows = self._documents_to_rows(batch_ids, batch_documents, vectors)
                            self._create_or_add_rows(rows)
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
                "embedding": embedding_contract_metadata(),
                "reused": False,
            }
            self._check_cancelled()
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
        except IndexBuildCancelledError as e:
            self._set_build_state(
                status="cancelled",
                stage="cancelled",
                error=str(e),
                finished_at=datetime.now(timezone.utc).isoformat(),
            )
            raise
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
            filter: 元数据过滤条件，如 {"format_key": "arc"}
            score_threshold: 最大向量距离阈值（0.0 = 不过滤）
        """
        status = self.get_status(check_freshness=True)
        if not status.get("exists"):
            raise IndexBuildNotReadyError(status)

        embeddings = self._get_embeddings()
        table = self._open_table()
        query_vector = self._embed_query(embeddings, query_text)
        query = table.search(query_vector)
        where_expr = self._build_filter_expression(filter)
        if where_expr:
            query = query.where(where_expr, prefilter=True)
        results = query.limit(k).to_list()

        # 组装 SearchHit
        hits: list[SearchHit] = []
        for idx, row in enumerate(results):
            score = row.get("_distance", row.get("_score", 0.0))
            if score_threshold > 0 and score > score_threshold:
                continue
            source = str(row.get("source") or "")
            abs_path = os.path.join(self._project_path, source) if source else ""
            source_type = str(row.get("source_type") or "project")
            hits.append(SearchHit(
                index=idx,
                file_path=abs_path,
                rel_path=source,
                format_key=str(row.get("format_key") or ""),
                start_line=int(row.get("start_line") or 0),
                end_line=int(row.get("end_line") or 0),
                narrative_ref=str(row.get("narrative_ref") or ""),
                match_text=str(row.get("text") or ""),
                score=float(score),
                source_type=source_type,
                attachment_id=str(row.get("attachment_id") or ""),
                attachment_filename=str(row.get("attachment_filename") or ""),
                attachment_chunk_index=int(row.get("attachment_chunk_index") or 0),
            ))

        return hits

    # ==================== 状态管理 ====================

    def get_status(self, check_freshness: bool = True) -> dict:
        """索引状态"""
        exists = self._table_exists()
        metadata = self._load_meta() if exists else {}
        build_state = self.get_build_state()
        needs_rebuild = False
        if exists and metadata and not self._supports_incremental_meta(metadata):
            needs_rebuild = True
            if build_state.get("status") not in (_ACTIVE_BUILD_STATUSES | {"error"}):
                build_state = {
                    **build_state,
                    "status": "stale",
                    "stage": "reindex",
                }
        elif exists and metadata and not self._is_embedding_contract_compatible(metadata):
            needs_rebuild = True
            if build_state.get("status") not in (_ACTIVE_BUILD_STATUSES | {"error"}):
                build_state = {
                    **build_state,
                    "status": "stale",
                    "stage": "embedding_contract",
                }
        elif check_freshness and exists and metadata and build_state.get("status") not in (_ACTIVE_BUILD_STATUSES | {"error"}):
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
            "backend": "lancedb",
            "metadata": metadata,
            "needs_rebuild": needs_rebuild,
            "build_state": build_state,
        }

    def reset(self) -> dict:
        """删除索引"""
        self.cancel_background_build(wait_timeout=2.0)
        removed = False
        if os.path.isdir(self._persist_dir):
            shutil.rmtree(self._persist_dir)
            removed = True
        task_key = _build_task_key(self.user_id, self.project_name)
        with _build_state_lock:
            _build_state_registry.pop(task_key, None)
        return {
            "project": self.project_name,
            "user_id": self.user_id,
            "removed": removed,
            "backend": "lancedb",
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

            # 二次切分：附件 chunk 单片可达 64K token，远超 embedding API 上限（如阿里通义 8K）。
            # 复用项目分块器的"超长块二次切分"统一入口，确保单个 sub-chunk 不会撑爆 embedding API。
            attachment_chunker = SemanticChunker()
            semantic_chunks = attachment_chunker.split_oversized(semantic_chunks)

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
        """计算当前索引输入源的内容哈希。

        除项目正文文件外，若项目开启了附件入索，也必须把附件哈希纳入，
        否则上传/删除附件后 ``_needs_rebuild`` 无法感知变更，
        会导致 ``semantic_search(scope=["attachment"])`` 命中旧索引甚至查不到附件。
        """
        hashes: dict[str, str] = {}
        files = collect_project_files(self.user_id, self.project_name)
        for pf in files:
            try:
                hashes[pf.rel_path] = hashlib.md5(pf.content.encode("utf-8")).hexdigest()
            except Exception:
                hashes[pf.rel_path] = ""

        try:
            from core.project_settings import is_attachment_index_enabled

            if is_attachment_index_enabled(self.user_id, self.project_name):
                _, attachment_hashes = self._collect_attachment_chunks()
                hashes.update({str(rel_path): str(file_hash or "") for rel_path, file_hash in attachment_hashes.items()})
        except Exception:
            pass
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
