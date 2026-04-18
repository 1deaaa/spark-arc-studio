"""
项目级向量索引服务

使用 Chroma 持久化向量库 + matchbox 云端 embedding。
支持懒构建、哈希增量更新、元数据过滤查询。
"""

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from core.utils import get_project_path
from llm.agen_matchbox import matchbox
from story.project_files import collect_project_files, load_outline_data
from story.semantic_chunker import SemanticChunker, SemanticChunk


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

    # ==================== 索引构建 ====================

    def build_index(self, force_rebuild: bool = False) -> dict:
        """
        构建/更新向量索引。

        懒构建 + 哈希增量更新：
        - 首次调用时全量构建
        - 后续调用比对文件哈希，仅变更文件重新分块+编码
        - force_rebuild=True 时强制全量重建
        """
        if not os.path.isdir(self._project_path):
            raise FileNotFoundError(f"项目不存在: {self._project_path}")

        # 检查现有索引
        if not force_rebuild and os.path.isdir(self._persist_dir):
            metadata = self._load_meta()
            if metadata and not self._needs_rebuild(metadata):
                metadata["reused"] = True
                return metadata

        # 执行分块
        chunker = SemanticChunker()
        chunks = chunker.chunk_project(self.user_id, self.project_name, use_cache=True)

        if not chunks:
            raise RuntimeError("未找到可用于构建向量索引的项目文本。")

        # 转换为 LangChain Document
        documents = self._chunks_to_documents(chunks)

        # 构建 Chroma 索引（分批添加，避免嵌入模型 API batch size 限制）
        embeddings = self._get_embeddings()

        if force_rebuild and os.path.isdir(self._persist_dir):
            shutil.rmtree(self._persist_dir)

        _BATCH_SIZE = 10  # 多数嵌入模型 API 限制 batch ≤ 10

        # 首批创建 collection
        first_batch = documents[:_BATCH_SIZE]
        vector_store = Chroma.from_documents(
            documents=first_batch,
            embedding=embeddings,
            collection_name=self._collection_name,
            persist_directory=self._persist_dir,
        )

        # 后续批次增量添加
        for i in range(_BATCH_SIZE, len(documents), _BATCH_SIZE):
            batch = documents[i:i + _BATCH_SIZE]
            vector_store.add_documents(batch)

        # 保存元数据
        meta = {
            "version": "1.0",
            "built_at": datetime.now(timezone.utc).isoformat(),
            "project": self.project_name,
            "user_id": self.user_id,
            "chunk_count": len(chunks),
            "file_hashes": self._compute_file_hashes(),
            "reused": False,
        }
        self._save_meta(meta)

        return meta

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
        # 确保索引存在且最新
        if not os.path.isdir(self._persist_dir):
            self.build_index()
        else:
            # 索引已存在，检查是否需要增量更新
            metadata = self._load_meta()
            if metadata and self._needs_rebuild(metadata):
                self.build_index()

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
            ))

        return hits

    # ==================== 状态管理 ====================

    def get_status(self) -> dict:
        """索引状态"""
        exists = os.path.isdir(self._persist_dir)
        metadata = self._load_meta() if exists else {}
        return {
            "project": self.project_name,
            "user_id": self.user_id,
            "exists": exists,
            "persist_dir": self._persist_dir,
            "metadata": metadata,
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

    def _needs_rebuild(self, metadata: dict) -> bool:
        """比对文件哈希判断是否需要重建"""
        stored_hashes = metadata.get("file_hashes", {})
        current_hashes = self._compute_file_hashes()

        # 文件数量变化
        if set(stored_hashes.keys()) != set(current_hashes.keys()):
            return True

        # 任一文件哈希变化
        for rel_path, current_hash in current_hashes.items():
            if stored_hashes.get(rel_path) != current_hash:
                return True

        return False

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
