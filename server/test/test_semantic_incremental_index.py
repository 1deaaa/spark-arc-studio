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


def test_vector_index_service_skips_rebuild_when_no_files_changed(monkeypatch):
    """第一点保障：项目内容完全没变时，build_index 不应触发任何 add/delete。"""
    user_id = f'test_vector_noop_{uuid.uuid4().hex[:8]}'
    project_name = f'project_{uuid.uuid4().hex[:8]}'
    project_path = _prepare_project(user_id, project_name)

    monkeypatch.setattr('agents.vector_index.service.Chroma', _FakeChroma)
    monkeypatch.setattr(VectorIndexService, '_get_embeddings', lambda self: object())

    try:
        service = VectorIndexService(user_id=user_id, project_name=project_name)
        first_meta = service.build_index(force_rebuild=True)
        # 首次构建：所有文件都视作 added_files
        assert first_meta['change_summary']['added_files'] >= 1

        _FakeChroma.operations.clear()
        second_meta = service.build_index(force_rebuild=False)

        # 复用语义命中：仅返回旧 metadata，未触发任何向量库写入
        assert second_meta.get('reused') is True
        assert _FakeChroma.operations == [], '无变化时不应触发任何 add/delete'
    finally:
        _FakeChroma.stores.clear()
        _FakeChroma.operations.clear()
        shutil.rmtree(project_path, ignore_errors=True)


def test_vector_index_service_only_reembeds_changed_chunks_within_file(monkeypatch):
    """第二点保障：文件内多个分块时，仅改变的分块被重 embed，未变分块保持原样。"""
    user_id = f'test_vector_chunk_{uuid.uuid4().hex[:8]}'
    project_name = f'project_{uuid.uuid4().hex[:8]}'
    project_path = Path(get_project_path(user_id, project_name))
    project_path.mkdir(parents=True, exist_ok=True)

    # HeadingChunkStrategy 会把每个 # 标题之前累积的内容做成一个 chunk
    # 因此下面这份"世界观.txt"会被切成 2 个语义分块
    initial_world = (
        "# 第一章 火种城\n"
        "火种城有一座永不熄灭的灯塔。\n"
        "\n"
        "# 第二章 灰湖\n"
        "灰湖深处住着记忆守墓人。\n"
    )
    (project_path / '世界观.txt').write_text(initial_world, encoding='utf-8')
    (project_path / '梗概.txt').write_text(
        '@title 测试\n\n林夏在火种城寻找失落的航线。', encoding='utf-8'
    )

    monkeypatch.setattr('agents.vector_index.service.Chroma', _FakeChroma)
    monkeypatch.setattr(VectorIndexService, '_get_embeddings', lambda self: object())

    try:
        service = VectorIndexService(user_id=user_id, project_name=project_name)
        first_meta = service.build_index(force_rebuild=True)

        first_world_ids = list(first_meta['file_doc_ids']['世界观.txt'])
        first_synopsis_ids = list(first_meta['file_doc_ids']['梗概.txt'])
        # 至少切出两个 chunk 才能验证 chunk 级行为
        assert len(first_world_ids) >= 2, (
            f'测试样本应切出多块 chunk，否则无法验证 chunk 级增量；'
            f'实际切出 {len(first_world_ids)} 块'
        )

        # 仅改第一章内容，第二章原文不动；分块边界不变 ⇒ 仅第一个 chunk 的 chunk_id 改变
        updated_world = (
            "# 第一章 火种城\n"
            "火种城的灯塔开始吞噬人的记忆。\n"
            "\n"
            "# 第二章 灰湖\n"
            "灰湖深处住着记忆守墓人。\n"
        )
        (project_path / '世界观.txt').write_text(updated_world, encoding='utf-8')

        _FakeChroma.operations.clear()
        second_meta = service.build_index(force_rebuild=False)

        new_world_ids = list(second_meta['file_doc_ids']['世界观.txt'])
        assert second_meta['file_doc_ids']['梗概.txt'] == first_synopsis_ids
        assert len(new_world_ids) == len(first_world_ids)

        # 关键：第一个 chunk 的 id 变了，第二个仍然完全一致（因其文本和元数据未变）
        changed_chunk_ids = set(first_world_ids) ^ set(new_world_ids)
        reused_chunk_ids = set(first_world_ids) & set(new_world_ids)
        assert reused_chunk_ids, '至少应有一个 chunk 完全保留，不该全部重 embed'
        assert changed_chunk_ids, '至少应有一个 chunk 因文本变化而获得新 chunk_id'

        delete_ops = [op for op in _FakeChroma.operations if op[0] == 'delete']
        add_ops = [op for op in _FakeChroma.operations if op[0] == 'add']

        assert delete_ops, '应至少触发一次 delete'
        all_deleted_ids = {cid for op in delete_ops for cid in op[2]}
        all_added_ids = {cid for op in add_ops for cid in op[2]}

        # 删除/新增的 ids 必须严格等于 chunk_id 差集，不能波及未变 chunk
        assert all_deleted_ids == set(first_world_ids) - set(new_world_ids), (
            '只能删除那些 chunk_id 不再存在的旧分块'
        )
        assert all_added_ids == set(new_world_ids) - set(first_world_ids), (
            '只能 embed 那些是真正新出现的分块'
        )
        # 未变的 chunk_id 既不在删除集合，也不在新增集合
        for reused_id in reused_chunk_ids:
            assert reused_id not in all_deleted_ids
            assert reused_id not in all_added_ids
    finally:
        _FakeChroma.stores.clear()
        _FakeChroma.operations.clear()
        shutil.rmtree(project_path, ignore_errors=True)


def test_vector_index_service_preserves_unchanged_neighbour_chunks(monkeypatch):
    """三个分块只改中间一段：首尾两段 chunk_id/向量必须原样保留，仅中间分块被重 embed。"""
    user_id = f'test_vector_middle_{uuid.uuid4().hex[:8]}'
    project_name = f'project_{uuid.uuid4().hex[:8]}'
    project_path = Path(get_project_path(user_id, project_name))
    project_path.mkdir(parents=True, exist_ok=True)

    # 三段长度相同，避免修改时影响相邻分块的行号
    initial_world = (
        "# 第一章 火种城\n"
        "火种城有一座永不熄灭的灯塔。\n"
        "\n"
        "# 第二章 灰湖\n"
        "灰湖深处住着记忆守墓人的旧船。\n"
        "\n"
        "# 第三章 银林\n"
        "银林夜里会浮起萤火虫的雾气。\n"
    )
    (project_path / '世界观.txt').write_text(initial_world, encoding='utf-8')
    (project_path / '梗概.txt').write_text(
        '@title 测试\n\n林夏在火种城寻找失落的航线。', encoding='utf-8'
    )

    monkeypatch.setattr('agents.vector_index.service.Chroma', _FakeChroma)
    monkeypatch.setattr(VectorIndexService, '_get_embeddings', lambda self: object())

    try:
        service = VectorIndexService(user_id=user_id, project_name=project_name)
        first_meta = service.build_index(force_rebuild=True)
        first_world_ids = list(first_meta['file_doc_ids']['世界观.txt'])
        assert len(first_world_ids) >= 3, (
            f'测试样本应切出三块，否则无法验证邻接分块复用；实际 {len(first_world_ids)} 块'
        )
        first_id, middle_id, last_id = first_world_ids[0], first_world_ids[1], first_world_ids[-1]

        # 仅修改第二章内容，且**保持新内容字符数等于旧内容**，
        # 这样第三章在文件内的行号区间不变，chunk_id 必然完全保留。
        original_middle = "灰湖深处住着记忆守墓人的旧船。"
        replacement_middle = "灰湖深处仍传来失落港口的钟声。"
        assert len(original_middle) == len(replacement_middle), (
            '替换文本长度必须一致以保持后续分块的行号'
        )
        updated_world = initial_world.replace(original_middle, replacement_middle)
        (project_path / '世界观.txt').write_text(updated_world, encoding='utf-8')

        _FakeChroma.operations.clear()
        second_meta = service.build_index(force_rebuild=False)
        new_world_ids = list(second_meta['file_doc_ids']['世界观.txt'])

        delete_ops = [op for op in _FakeChroma.operations if op[0] == 'delete']
        add_ops = [op for op in _FakeChroma.operations if op[0] == 'add']
        all_deleted_ids = {cid for op in delete_ops for cid in op[2]}
        all_added_ids = {cid for op in add_ops for cid in op[2]}

        # 第一章、第三章 chunk_id 必须完全保留；中间章 chunk_id 必须更新
        assert first_id in new_world_ids, '首段未改动，chunk_id 应完全保留'
        assert last_id in new_world_ids, '末段未改动，chunk_id 应完全保留'
        assert middle_id not in new_world_ids, '中间段已改动，旧 chunk_id 必须失效'

        # 向量库写入也只能精确发生在中间分块
        assert all_deleted_ids == {middle_id}, (
            f'仅应删除中间被改动的旧 chunk_id；实际删除 {all_deleted_ids}'
        )
        # 新增的 ids 必然是 new ∖ old，且仅含新中间分块
        added_expected = set(new_world_ids) - set(first_world_ids)
        assert all_added_ids == added_expected, (
            f'仅应 embed 真正新出现的 chunk_id；实际 add {all_added_ids}'
        )
        assert len(added_expected) == 1, '中间一段应当只产生一个新 chunk_id'

        # 首尾分块绝不应进入 add/delete 集合
        for unchanged_id in (first_id, last_id):
            assert unchanged_id not in all_deleted_ids
            assert unchanged_id not in all_added_ids
    finally:
        _FakeChroma.stores.clear()
        _FakeChroma.operations.clear()
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
