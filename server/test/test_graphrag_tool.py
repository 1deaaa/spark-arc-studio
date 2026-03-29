import shutil
import sys
import uuid
from pathlib import Path

from langchain_core.messages import AIMessage

SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from agents.agent_tools import graph_rag_tool
from agents.graphrag.service import GraphRAGService
from core.request_context import current_agent_id, current_project_name, current_user_id
from core.utils import get_project_path


class _FakeLLM:
    def invoke(self, messages):
        full_text = "\n".join(getattr(msg, "content", str(msg)) for msg in messages)

        if "[TASK:TRIPLET_EXTRACTION]" in full_text:
            return AIMessage(
                content='[{"subject":"林夏","relation":"是好友","object":"陈墨"},{"subject":"陈墨","relation":"居住在","object":"火种城"}]'
            )

        if "[TASK:ENTITY_EXTRACTION]" in full_text:
            if "夏夏" in full_text:
                return AIMessage(content='["夏夏", "陈墨"]')
            return AIMessage(content='["林夏", "陈墨"]')

        return AIMessage(content="根据图谱，林夏与陈墨是好友，且陈墨居住在火种城。")


class _FakeManager:
    def __init__(self):
        self.calls = []

    def get_user_llm(self, *args, **kwargs):
        self.calls.append(kwargs)
        return _FakeLLM()


def _prepare_project(user_id: str, project_name: str) -> Path:
    project_path = Path(get_project_path(user_id, project_name))
    chr_path = project_path / "chr"
    stories_path = project_path / "stories"

    stories_path.mkdir(parents=True, exist_ok=True)
    chr_path.mkdir(parents=True, exist_ok=True)

    (project_path / "世界观.txt").write_text("火种城靠记忆蒸馏塔维持运转。", encoding="utf-8")
    (project_path / "synopsis.json").write_text('{"synopsis_text":"林夏与陈墨在火种城调查记忆污染。"}', encoding="utf-8")
    (project_path / "outline.json").write_text('{"title":"测试","nodes":[]}', encoding="utf-8")
    (chr_path / "chr.bind").write_text('{"1":"林夏","2":"陈墨"}', encoding="utf-8")
    (chr_path / "1.txt").write_text("林夏\n别名：夏夏\n\n调查员", encoding="utf-8")
    (chr_path / "2.txt").write_text("陈墨\n\n工程师", encoding="utf-8")
    (stories_path / "01.arc").write_text("林夏在火种城与陈墨会面。", encoding="utf-8")

    return project_path


def test_graphrag_service_build_and_query(monkeypatch):
    user_id = f"test_graphrag_{uuid.uuid4().hex[:8]}"
    project_name = f"project_{uuid.uuid4().hex[:8]}"
    project_path = _prepare_project(user_id, project_name)

    try:
        fake_manager = _FakeManager()
        monkeypatch.setattr("agents.graphrag.service.matchbox", lambda: fake_manager)

        service = GraphRAGService(user_id=user_id, project_name=project_name)
        build_info = service.build_index(force_rebuild=True)

        assert build_info["nodes"] >= 2
        assert build_info["edges"] >= 1
        assert build_info["triplets"] >= 1

        result = service.query(question="林夏和陈墨是什么关系？", query_mode="drift")
        assert result["mode"] == "drift"
        assert "林夏" in result["matched_entities"]
        assert result["answer"]

        # 建图阶段固定 fast；直接 service.query 且无调用者时不透传 agent_name。
        assert any(call.get("usage_key") == "fast" for call in fake_manager.calls)
        assert any("agent_name" not in call for call in fake_manager.calls)

        status = service.get_status()
        assert status["graph_ready"] is True
        assert int((status.get("metadata") or {}).get("alias_count", 0)) >= 2
    finally:
        shutil.rmtree(project_path, ignore_errors=True)


def test_graphrag_tool_wrapper(monkeypatch):
    user_id = f"test_graphrag_{uuid.uuid4().hex[:8]}"
    project_name = f"project_{uuid.uuid4().hex[:8]}"
    project_path = _prepare_project(user_id, project_name)

    user_token = current_user_id.set(user_id)
    project_token = current_project_name.set(project_name)
    agent_token = current_agent_id.set("agent_scriptwriter")

    try:
        fake_manager = _FakeManager()
        monkeypatch.setattr("agents.graphrag.service.matchbox", lambda: fake_manager)

        build_output = graph_rag_tool.invoke({"action": "build", "force_rebuild": True})
        assert "GraphRAG 构建完成" in build_output

        query_output = graph_rag_tool.invoke(
            {
                "action": "query",
                "query_mode": "drift",
                "question": "林夏和陈墨是什么关系？",
            }
        )
        assert "GraphRAG 查询结果" in query_output
        assert "林夏" in query_output

        guardrails_output = graph_rag_tool.invoke(
            {
                "action": "query",
                "query_mode": "drift",
                "response_mode": "writing_guardrails",
                "question": "夏夏和陈墨的关系要保持什么？",
            }
        )
        assert "GraphRAG 写作约束" in guardrails_output
        assert "必须保持事实" in guardrails_output
        assert "林夏" in guardrails_output

        status_output = graph_rag_tool.invoke({"action": "status"})
        assert "graph_ready: True" in status_output

        # 通过工具调用 query 时，应跟随调用者 agent 绑定。
        assert any(call.get("usage_key") == "fast" for call in fake_manager.calls)
        assert any(call.get("agent_name") == "agent_scriptwriter" for call in fake_manager.calls)
    finally:
        current_agent_id.reset(agent_token)
        current_user_id.reset(user_token)
        current_project_name.reset(project_token)
        shutil.rmtree(project_path, ignore_errors=True)
