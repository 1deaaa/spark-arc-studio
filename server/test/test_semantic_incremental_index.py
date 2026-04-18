import shutil
import sys
import uuid
from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from agents.vector_index.service import VectorIndexService
from core.utils import get_project_path
from story.semantic_chunker.chunker import SemanticChunker


class _FakeChroma:
    stores: dict[tuple[str | None, str], dict[str, object]] = {}
    operations: list[tuple[str, tuple[str | None, str], list[str]]] = []

    def __init__(self, collection_name: str, embedding_function=None, persist_directory: str | None = None, **kwargs):
        self.key = (persist_directory, collection_name)
        self.docs = self.stores.setdefault(self.key, {})

    @classmethod
    def from_documents(cls, documents, embedding=None, ids=None, collection_name: str = 'langchain', persist_directory: str | None = None, **kwargs):
        instance = cls(collection_name=collection_name, embedding_function=embedding, persist_directory=persist_directory)
        instance.add_documents(documents, ids=ids)
        return instance

    def add_documents(self, documents, ids=None, **kwargs):
        actual_ids = list(ids or kwargs.get('ids') or [])
        self.operations.append(('add', self.key, actual_ids))
        for doc_id, document in zip(actual_ids, documents):
            self.docs[doc_id] = document
        return actual_ids

    def delete(self, ids=None, **kwargs):
        actual_ids = list(ids or [])
        self.operations.append(('delete', self.key, actual_ids))
        for doc_id in actual_ids:
            self.docs.pop(doc_id, None)

    def similarity_search_with_score(self, query_text, **kwargs):
        return []


def _prepare_project(user_id: str, project_name: str) -> Path:
    project_path = Path(get_project_path(user_id, project_name))
    project_path.mkdir(parents=True, exist_ok=True)
    (project_path / '世界观.txt').write_text('火种城有一座永不熄灭的灯塔。', encoding='utf-8')
    (project_path / '梗概.txt').write_text('@title 测试\n\n林夏在火种城寻找失落的航线。', encoding='utf-8')
    return project_path


def test_semantic_chunker_only_rechunks_changed_files(monkeypatch):
    user_id = f'test_chunker_{uuid.uuid4().hex[:8]}'
    project_name = f'project_{uuid.uuid4().hex[:8]}'
    project_path = _prepare_project(user_id, project_name)

    original_chunk_file = SemanticChunker.chunk_file
    calls: list[str] = []

    def tracked_chunk_file(self, project_file, outline_data):
        calls.append(project_file.rel_path)
        return original_chunk_file(self, project_file, outline_data)

    monkeypatch.setattr(SemanticChunker, 'chunk_file', tracked_chunk_file)

    try:
        chunker = SemanticChunker()
        first_state = chunker.chunk_project_state(user_id, project_name, use_cache=True)
        assert sorted(calls) == ['世界观.txt', '梗概.txt']
        assert sorted(first_state['changed_files']) == ['世界观.txt', '梗概.txt']

        calls.clear()
        second_state = chunker.chunk_project_state(user_id, project_name, use_cache=True)
        assert calls == []
        assert second_state['changed_files'] == []
        assert sorted(second_state['reused_files']) == ['世界观.txt', '梗概.txt']

        (project_path / '世界观.txt').write_text('火种城有一座会记录记忆的灯塔。', encoding='utf-8')

        calls.clear()
        third_state = chunker.chunk_project_state(user_id, project_name, use_cache=True)
        assert calls == ['世界观.txt']
        assert third_state['changed_files'] == ['世界观.txt']
        assert third_state['reused_files'] == ['梗概.txt']
    finally:
        shutil.rmtree(project_path, ignore_errors=True)


def test_vector_index_service_only_reindexes_changed_files(monkeypatch):
    user_id = f'test_vector_{uuid.uuid4().hex[:8]}'
    project_name = f'project_{uuid.uuid4().hex[:8]}'
    project_path = _prepare_project(user_id, project_name)

    monkeypatch.setattr('agents.vector_index.service.Chroma', _FakeChroma)
    monkeypatch.setattr(VectorIndexService, '_get_embeddings', lambda self: object())

    try:
        service = VectorIndexService(user_id=user_id, project_name=project_name)
        first_meta = service.build_index(force_rebuild=True)
        first_world_ids = list(first_meta['file_doc_ids']['世界观.txt'])
        first_synopsis_ids = list(first_meta['file_doc_ids']['梗概.txt'])

        _FakeChroma.operations.clear()
        (project_path / '世界观.txt').write_text('火种城的灯塔开始吞噬人的记忆。', encoding='utf-8')

        second_meta = service.build_index(force_rebuild=False)
        delete_ops = [op for op in _FakeChroma.operations if op[0] == 'delete']
        add_ops = [op for op in _FakeChroma.operations if op[0] == 'add']

        assert second_meta['change_summary']['changed_files'] == 1
        assert second_meta['change_summary']['removed_files'] == 0
        assert second_meta['change_summary']['reused_files'] == 1
        assert second_meta['file_doc_ids']['梗概.txt'] == first_synopsis_ids
        assert second_meta['file_doc_ids']['世界观.txt'] != first_world_ids
        assert delete_ops
        assert delete_ops[0][2] == first_world_ids
        assert all(first_synopsis_id not in delete_ops[0][2] for first_synopsis_id in first_synopsis_ids)
        assert add_ops
        assert second_meta['file_doc_ids']['世界观.txt'] == add_ops[-1][2]
    finally:
        _FakeChroma.stores.clear()
        _FakeChroma.operations.clear()
        shutil.rmtree(project_path, ignore_errors=True)
