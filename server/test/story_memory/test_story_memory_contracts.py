from __future__ import annotations

import asyncio
import inspect
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from agents.story_memory import StoryMemoryFacade
from agents.tools.registry import get_tools_for_agent


def test_story_memory_job_propagates_request_context(monkeypatch) -> None:
    from core.request_context import current_llm_usage_context
    from agents.story_memory import jobs

    usage_token = current_llm_usage_context.set("story-memory-context-test")
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            monkeypatch.setattr(jobs, "_executor", lambda: executor)
            future = jobs._submit(
                "上下文测试",
                lambda: current_llm_usage_context.get(),
            )
            assert future.result(timeout=2) == "story-memory-context-test"
    finally:
        current_llm_usage_context.reset(usage_token)


def test_story_memory_serializes_same_project_updates(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    (tmp_path / "uid_31" / "projects" / "demo").mkdir(parents=True)

    original_extract = StoryMemoryFacade.extract_state_delta
    active = 0
    max_active = 0
    counter_lock = threading.Lock()

    def slow_extract(self, *args, **kwargs):
        nonlocal active, max_active
        with counter_lock:
            active += 1
            max_active = max(max_active, active)
        try:
            time.sleep(0.03)
            return original_extract(self, *args, **kwargs)
        finally:
            with counter_lock:
                active -= 1

    monkeypatch.setattr(StoryMemoryFacade, "extract_state_delta", slow_extract)

    def record(scene_index: int) -> None:
        StoryMemoryFacade("31", "demo").record_scene_write(
            scene_text=f"第 {scene_index + 1} 场正文。",
            chapter_index=0,
            scene_index=scene_index,
            scene_title=f"场景 {scene_index + 1}",
            use_llm_extractor=False,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(record, index) for index in range(2)]
        for future in futures:
            future.result(timeout=2)

    state = StoryMemoryFacade("31", "demo").load_state()
    assert max_active == 1
    assert [scene["scene_id"] for scene in state["scenes"]] == ["ch001-sc001", "ch001-sc002"]
    assert not list((tmp_path / "uid_31" / "projects" / "demo" / ".story_memory").glob("*.tmp"))


def test_story_memory_records_scene_and_builds_task_pack(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    project_path = tmp_path / "uid_7" / "projects" / "demo"
    project_path.mkdir(parents=True)

    facade = StoryMemoryFacade("7", "demo")
    delta = facade.record_scene_write(
        scene_text="# 钟楼交易\n[-1] 沈棠把旧钥匙交给林烬，并提醒他不要相信档案室的记录。",
        chapter_index=0,
        scene_index=1,
        chapter_title="一 · 开端",
        scene_title="钟楼交易",
        scene_description="沈棠与林烬交换线索，埋下档案室秘密伏笔。",
        guidance="本场需要埋下档案室秘密线索。",
        source_path="一 · 开端/钟楼交易.arc",
        chr_map={1: "沈棠", 2: "林烬"},
        scene_characters=["沈棠", "林烬"],
        use_llm_extractor=False,
    )

    assert delta["scene"]["scene_id"] == "ch001-sc002"
    state = facade.load_state()
    assert len(state["scenes"]) == 1
    assert state["character_states"]["沈棠"]["last_seen_scene"] == "ch001-sc002"
    assert state["relationships"]["林烬|沈棠"]["co_presence_count"] == 1
    assert state["threads"][0]["status"] == "open"

    pack = facade.compose_scene_task_pack(
        chapter_index=0,
        scene_index=2,
        chapter_title="一 · 开端",
        scene_title="档案室",
        scene_description="林烬独自查档案室。",
        scene_characters=["林烬"],
        chr_map={1: "沈棠", 2: "林烬"},
    )
    text = pack["text"]
    assert "当前场景事实包" in text
    assert "林烬" in text
    assert "钟楼交易" in text
    assert "档案室秘密" in text


def test_story_memory_resolves_arc_character_ids_from_chr_map(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    project_path = tmp_path / "uid_17" / "projects" / "demo"
    project_path.mkdir(parents=True)

    facade = StoryMemoryFacade("17", "demo")
    facade.record_scene_write(
        scene_text="\n".join(
            [
                "# 钟楼交易",
                "[1]",
                "把钥匙收好。",
                "[2]",
                "我会查清楚。",
                "[-1]",
                "雨声吞没了脚步。",
                "[-2]",
                "别回头。",
            ]
        ),
        chapter_index=0,
        scene_index=0,
        scene_title="钟楼交易",
        chr_map={-1: "旁白", -2: "?", 1: "沈棠", 2: "林烬"},
        use_llm_extractor=False,
    )

    state = facade.load_state()
    assert state["scenes"][0]["characters"] == ["沈棠", "林烬"]
    assert "沈棠" in state["character_states"]
    assert "林烬" in state["character_states"]
    assert "旁白" not in state["character_states"]
    assert "?" not in state["character_states"]


def test_story_memory_llm_delta_feeds_scene_task_pack(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    project_path = tmp_path / "uid_8" / "projects" / "demo"
    project_path.mkdir(parents=True)

    def fake_extract(*args, **kwargs):
        return {
            "summary": "沈棠向林烬交付旧钥匙，并明确档案室记录被篡改。",
            "events": [
                {"summary": "旧钥匙交接", "participants": ["沈棠", "林烬"], "evidence": "沈棠把旧钥匙交给林烬"}
            ],
            "character_updates": [
                {"character": "林烬", "status": "获得旧钥匙", "goal": "查档案室", "emotion": "警惕", "knowledge": "档案室记录可能被篡改", "evidence": "不要相信档案室的记录"}
            ],
            "relationship_changes": [
                {"characters": ["沈棠", "林烬"], "state": "临时结盟", "why": "双方交换线索", "evidence": "旧钥匙交接"}
            ],
            "foreshadows": [
                {"description": "档案室记录被篡改", "status": "open", "related_characters": ["林烬"], "evidence": "不要相信档案室的记录"}
            ],
            "fact_claims": [
                {"claim": "林烬持有旧钥匙", "entities": ["林烬"], "evidence": "沈棠把旧钥匙交给林烬"}
            ],
            "conflict_risks": [
                {"risk": "后续若写林烬没有钥匙会冲突", "severity": "high", "evidence": "旧钥匙交接"}
            ],
        }

    monkeypatch.setattr(StoryMemoryFacade, "_extract_state_delta_with_llm", fake_extract)
    facade = StoryMemoryFacade("8", "demo")
    facade.record_scene_write(
        scene_text="# 钟楼交易\n[-1] 沈棠把旧钥匙交给林烬，并提醒他不要相信档案室的记录。",
        chapter_index=0,
        scene_index=0,
        scene_title="钟楼交易",
        chr_map={1: "沈棠", 2: "林烬"},
        scene_characters=["沈棠", "林烬"],
        use_llm_extractor=True,
    )

    state = facade.load_state()
    assert state["events"][0]["summary"] == "旧钥匙交接"
    assert state["fact_claims"][0]["claim"] == "林烬持有旧钥匙"
    assert state["relationships"]["林烬|沈棠"]["relation_hint"] == "临时结盟"
    assert state["character_states"]["林烬"]["current_status"]["goal"] == "查档案室"

    task_pack = facade.compose_scene_task_pack(
        chapter_index=0,
        scene_index=1,
        scene_title="档案室",
        scene_description="林烬进入档案室。",
        scene_characters=["林烬"],
    )["text"]
    assert "旧钥匙交接" in task_pack
    assert "林烬持有旧钥匙" in task_pack
    assert "后续若写林烬没有钥匙会冲突" in task_pack


def test_story_memory_schema_is_in_stable_system_prefix(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    captured_messages = []

    class FakeLlm:
        def invoke(self, messages):
            captured_messages.extend(messages)
            return type("Response", (), {"content": "{}"})()

    class FakeMatchbox:
        @staticmethod
        def get_user_llm(*_args, **_kwargs):
            return FakeLlm()

    monkeypatch.setattr("llm.agen_matchbox.matchbox", lambda: FakeMatchbox())
    facade = StoryMemoryFacade("cache-user", "cache-project")
    facade._extract_state_delta_with_llm(
        scene_text="MARK_DYNAMIC_SCENE_TEXT",
        scene_card={
            "scene_id": "scene-1",
            "chapter_title": "第一章",
            "scene_title": "第一场",
            "description": "场景描述",
            "guidance": "写作指导",
        },
        characters=["林烬"],
        chr_map={1: "林烬"},
    )

    assert isinstance(captured_messages[0], SystemMessage)
    assert isinstance(captured_messages[1], HumanMessage)
    assert "【输出 JSON schema】" in captured_messages[0].content
    assert "【抽取判定协议】" in captured_messages[0].content
    assert "【输出 JSON schema】" not in captured_messages[1].content
    assert "【抽取判定协议】" not in captured_messages[1].content
    assert "MARK_DYNAMIC_SCENE_TEXT" not in captured_messages[0].content
    assert "MARK_DYNAMIC_SCENE_TEXT" in captured_messages[1].content


def test_story_memory_extraction_keeps_each_scene_independent(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    snapshots = []
    responses = [
        '{"summary":"第一场事实"}',
        '{"summary":"第二场事实"}',
    ]

    class FakeLlm:
        def invoke(self, messages):
            snapshots.append(list(messages))
            return type("Response", (), {"content": responses.pop(0)})()

    class FakeMatchbox:
        @staticmethod
        def get_user_llm(*_args, **_kwargs):
            return FakeLlm()

    monkeypatch.setattr("llm.agen_matchbox.matchbox", lambda: FakeMatchbox())
    facade = StoryMemoryFacade("cache-history-user", "cache-history-project")
    first = facade._extract_state_delta_with_llm(
        scene_text="第一场完整正文标记",
        scene_card={"scene_id": "scene-1", "scene_title": "第一场"},
        characters=["林烬"],
    )
    second = facade._extract_state_delta_with_llm(
        scene_text="第二场完整正文标记",
        scene_card={"scene_id": "scene-2", "scene_title": "第二场"},
        characters=["林烬"],
    )

    assert first["summary"] == "第一场事实"
    assert second["summary"] == "第二场事实"
    assert len(snapshots[0]) == 2
    assert len(snapshots[1]) == 2
    assert snapshots[1][0].content == snapshots[0][0].content
    assert "第二场完整正文标记" in snapshots[1][1].content
    assert "第一场完整正文标记" not in snapshots[1][1].content
    assert '{"summary":"第一场事实"}' not in snapshots[1][1].content


def test_story_memory_extraction_includes_only_compact_relevant_prior_state(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    captured_messages = []

    class FakeLlm:
        def invoke(self, messages):
            captured_messages.extend(messages)
            return type("Response", (), {"content": "{}"})()

    class FakeMatchbox:
        @staticmethod
        def get_user_llm(*_args, **_kwargs):
            return FakeLlm()

    monkeypatch.setattr("llm.agen_matchbox.matchbox", lambda: FakeMatchbox())
    facade = StoryMemoryFacade("compact-history-user", "compact-history-project")
    facade.record_scene_write(
        scene_text="# 1-1 钟楼\n[-1] 林烬拿到旧钥匙。完整旧正文不应重放。",
        chapter_index=0,
        scene_index=0,
        scene_title="1-1 钟楼",
        scene_characters=["林烬"],
        precomputed_delta={
            "source": "llm",
            "summary": "林烬拿到旧钥匙。",
            "events": [{"summary": "林烬拿到旧钥匙", "participants": ["林烬"], "evidence": "拿到旧钥匙"}],
            "character_updates": [{"character": "林烬", "status": "持有旧钥匙", "evidence": "拿到旧钥匙"}],
            "relationship_changes": [],
            "foreshadows": [{
                "description": "旧钥匙能打开档案室",
                "status": "open",
                "related_characters": ["林烬"],
                "evidence": "旧钥匙",
            }],
            "fact_claims": [{"claim": "林烬持有旧钥匙", "entities": ["林烬"], "evidence": "拿到旧钥匙"}],
            "conflict_risks": [],
        },
    )

    facade._extract_state_delta_with_llm(
        scene_text="# 1-2 档案室\n[-1] 林烬用旧钥匙开门。",
        scene_card={
            "scene_id": "ch001-sc002",
            "chapter_index": 0,
            "scene_index": 1,
            "scene_title": "1-2 档案室",
        },
        characters=["林烬"],
    )

    user_prompt = captured_messages[1].content
    assert "【相关历史状态】" in user_prompt
    assert "林烬持有旧钥匙" in user_prompt
    assert "旧钥匙能打开档案室" in user_prompt
    assert "完整旧正文不应重放" not in user_prompt
    assert "它不是本场原文，禁止把它写入 evidence" in user_prompt


def test_story_memory_extraction_history_excludes_future_scene_state(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    facade = StoryMemoryFacade("future-filter-user", "future-filter-project")
    facade.record_scene_write(
        scene_text="# 1-2 未来场景\n[-1] 林烬已经销毁旧钥匙。",
        chapter_index=0,
        scene_index=1,
        scene_title="1-2 未来场景",
        scene_characters=["林烬"],
        precomputed_delta={
            "source": "llm",
            "summary": "林烬已经销毁旧钥匙。",
            "events": [{"summary": "林烬销毁旧钥匙", "participants": ["林烬"], "evidence": "销毁旧钥匙"}],
            "character_updates": [{"character": "林烬", "status": "旧钥匙已销毁", "evidence": "销毁旧钥匙"}],
            "relationship_changes": [],
            "foreshadows": [],
            "fact_claims": [{"claim": "旧钥匙已被销毁", "entities": ["林烬"], "evidence": "销毁旧钥匙"}],
            "conflict_risks": [],
        },
    )

    context = facade._build_extraction_history_context(
        scene_card={
            "scene_id": "ch001-sc001",
            "chapter_index": 0,
            "scene_index": 0,
            "scene_title": "1-1 较早场景",
        },
        characters=["林烬"],
    )

    assert context == ""


def test_story_memory_enrichment_jobs_are_fifo_within_project(monkeypatch) -> None:
    from agents.story_memory import jobs

    first_started = threading.Event()
    release_first = threading.Event()
    second_started = threading.Event()
    order: list[str] = []

    def fake_record_scene_write_job(_user_id, _project_name, payload, _label):
        order.append(f"start-{payload['index']}")
        if payload["index"] == 1:
            first_started.set()
            assert release_first.wait(timeout=2)
        else:
            second_started.set()
        order.append(f"end-{payload['index']}")

    fake_record_scene_write_job.__name__ = "_record_scene_write_job"
    with ThreadPoolExecutor(max_workers=2) as executor:
        monkeypatch.setattr(jobs, "_executor", lambda: executor)
        first_future = jobs._submit(
            "第一场",
            fake_record_scene_write_job,
            "fifo-user",
            "fifo-project",
            {"index": 1},
            "第一场",
        )
        assert first_started.wait(timeout=1)
        second_future = jobs._submit(
            "第二场",
            fake_record_scene_write_job,
            "fifo-user",
            "fifo-project",
            {"index": 2},
            "第二场",
        )
        assert not second_started.wait(timeout=0.1)
        release_first.set()
        first_future.result(timeout=2)
        second_future.result(timeout=2)

    assert order == ["start-1", "end-1", "start-2", "end-2"]


def test_scriptwriter_receives_story_memory_read_tool() -> None:
    tool_names = {tool.name for tool in get_tools_for_agent("agent_scriptwriter")}
    assert "story_memory_tool" in tool_names


def test_director_receives_story_memory_read_tool() -> None:
    tool_names = {tool.name for tool in get_tools_for_agent("agent_director")}
    assert "story_memory_tool" in tool_names


def test_explicit_story_save_absorb_records_novel_story_memory(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    project_path = tmp_path / "uid_21" / "projects" / "demo"
    stories_path = project_path / "stories"
    chapter_path = stories_path / "一 · 开端"
    chapter_path.mkdir(parents=True)
    file_path = chapter_path / "钟楼交易.md"
    content = "沈棠把旧钥匙交给林烬。"
    file_path.write_text(content, encoding="utf-8")

    calls = []

    def fake_record(self, **kwargs):
        calls.append(kwargs)
        return {"scene": {"scene_title": kwargs.get("scene_title")}}

    monkeypatch.setattr(StoryMemoryFacade, "record_scene_write", fake_record)

    from story.routes_files import _record_story_memory_after_story_save

    future = _record_story_memory_after_story_save(
        user_id="21",
        project_name="demo",
        stories_path=str(stories_path),
        file_path=str(file_path),
        content=content,
        file_format="novel",
    )
    assert future is not None
    future.result(timeout=2)

    assert len(calls) == 1
    assert calls[0]["scene_text"] == content
    assert calls[0]["chapter_title"] == "一 · 开端"
    assert calls[0]["scene_title"] == "钟楼交易"
    assert calls[0]["source_path"] == "一 · 开端/钟楼交易.md"
    assert calls[0]["export_format"] == "novel"


def test_explicit_story_save_absorb_records_each_arc_scene(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    project_path = tmp_path / "uid_22" / "projects" / "demo"
    stories_path = project_path / "stories"
    chapter_path = stories_path / "一 · 开端"
    chapter_path.mkdir(parents=True)
    file_path = chapter_path / "合流.__spark__chap=001.scene=003.arc"
    content = "\n".join(
        [
            "# 钟楼交易",
            "@guide 保留旧钥匙伏笔。",
            "@intro 沈棠与林烬交换线索。",
            "[-1]",
            "沈棠把旧钥匙交给林烬。",
            "# 档案室",
            "[-1]",
            "林烬确认档案室记录被篡改。",
        ]
    )
    file_path.write_text(content, encoding="utf-8")

    calls = []

    def fake_record(self, **kwargs):
        calls.append(kwargs)
        return {"scene": {"scene_title": kwargs.get("scene_title")}}

    monkeypatch.setattr(StoryMemoryFacade, "record_scene_write", fake_record)

    from story.routes_files import _record_story_memory_after_story_save

    future = _record_story_memory_after_story_save(
        user_id="22",
        project_name="demo",
        stories_path=str(stories_path),
        file_path=str(file_path),
        content=content,
        file_format="arc",
    )
    assert future is not None
    future.result(timeout=2)

    assert [call["scene_title"] for call in calls] == ["钟楼交易", "档案室"]
    assert [call["scene_index"] for call in calls] == [2, 3]
    assert all(call["chapter_index"] == 0 for call in calls)
    assert calls[0]["guidance"] == "保留旧钥匙伏笔。"
    assert calls[0]["scene_description"] == "沈棠与林烬交换线索。"
    assert "# 档案室" not in calls[0]["scene_text"]
    assert calls[1]["source_path"] == "一 · 开端/合流.__spark__chap=001.scene=003.arc"
    assert calls[1]["export_format"] == "arc"


def test_manual_save_story_does_not_implicitly_absorb_story_memory(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    calls = []

    def fake_absorb(**kwargs):
        calls.append(kwargs)
        raise AssertionError("普通保存接口不应隐式触发 StoryMemory")

    monkeypatch.setattr("story.routes_files._record_story_memory_after_story_save", fake_absorb)

    from story.routes_files import StoryData, save_story

    result = asyncio.run(
        save_story(
            StoryData(
                projectName="demo",
                filename="一 · 开端/钟楼交易.arc",
                data="# 钟楼交易\n[-1]\n沈棠把旧钥匙交给林烬。",
            ),
            user={"user_id": "23"},
        )
    )

    assert result["success"] is True
    assert calls == []


def test_explicit_absorb_story_memory_endpoint_enqueues_job(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    stories_path = tmp_path / "uid_24" / "projects" / "demo" / "stories"
    chapter_path = stories_path / "一 · 开端"
    chapter_path.mkdir(parents=True)
    file_path = chapter_path / "钟楼交易.arc"
    file_path.write_text("# 钟楼交易\n[-1]\n沈棠把旧钥匙交给林烬。", encoding="utf-8")

    calls = []

    def fake_enqueue(**kwargs):
        calls.append(kwargs)
        return object()

    monkeypatch.setattr("agents.story_memory.enqueue_story_content_memory_write", fake_enqueue)

    from story.routes_files import StoryMemoryAbsorbData, absorb_story_memory

    result = asyncio.run(
        absorb_story_memory(
            StoryMemoryAbsorbData(projectName="demo", filename="一 · 开端/钟楼交易.arc"),
            user={"user_id": "24"},
        )
    )

    assert result["success"] is True
    assert result["queued"] is True
    assert len(calls) == 1
    assert calls[0]["project_name"] == "demo"
    assert calls[0]["file_path"].endswith("钟楼交易.arc")
    assert calls[0]["file_format"] == "arc"


def test_reabsorbing_same_scene_replaces_old_story_memory_contributions(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    (tmp_path / "uid_25" / "projects" / "demo").mkdir(parents=True)

    facade = StoryMemoryFacade("25", "demo")
    facade.record_scene_write(
        scene_text="沈棠把旧钥匙交给林烬。",
        chapter_index=0,
        scene_index=0,
        scene_title="钟楼交易",
        scene_characters=["沈棠", "林烬"],
        use_llm_extractor=False,
    )
    first_state = facade.load_state()
    assert len(first_state["scenes"]) == 1
    assert len(first_state["relationships"]) == 1
    assert len(first_state["events"]) == 1

    facade.record_scene_write(
        scene_text="沈棠独自收起旧钥匙。",
        chapter_index=0,
        scene_index=0,
        scene_title="钟楼交易",
        scene_characters=["沈棠"],
        use_llm_extractor=False,
    )
    state = facade.load_state()

    assert len(state["scenes"]) == 1
    assert state["scenes"][0]["summary"] == "沈棠独自收起旧钥匙。"
    assert set(state["character_states"].keys()) == {"沈棠"}
    assert state["relationships"] == {}
    assert len(state["events"]) == 1
    assert state["events"][0]["summary"] == "沈棠独自收起旧钥匙。"


def test_scriptwriter_memory_write_call_sites_use_unified_memory_pipeline() -> None:
    from agents.routes import auto_write, production
    from agents.tools import scriptwriter

    auto_write_source = inspect.getsource(auto_write.generate_script_stream)
    production_source = inspect.getsource(production._record_story_memory_from_story_file)
    tool_source = inspect.getsource(scriptwriter.create_or_rewrite_script.func)

    assert "previous_scene_context" not in auto_write_source
    assert "run_autonomous_scriptwriter_creation" in auto_write_source
    assert "enqueue_scene_memory_write" not in auto_write_source
    assert "record_scene_write(" not in auto_write_source

    assert "enqueue_story_file_memory_write" in production_source
    assert "record_scene_write(" not in production_source

    assert "enqueue_scene_memory_write" in tool_source
    assert "record_scene_write(" not in tool_source


def test_story_memory_records_quality_review_and_feeds_task_pack(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    project_path = tmp_path / "uid_9" / "projects" / "demo"
    project_path.mkdir(parents=True)

    facade = StoryMemoryFacade("9", "demo")
    tickets = facade.record_quality_review(
        review={
            "decision": "REVISE",
            "overall_grade": "B",
            "rewrite_required": True,
            "rewrite_brief": "压低解释腔，让沈棠和林烬的对白更像互相试探。",
            "fix_tickets": [
                {
                    "target": "林烬与沈棠的对白",
                    "edit_goal": "减少完整解释句，增加停顿、误解和信息遮掩。",
                    "must_keep": ["旧钥匙已经交给林烬"],
                    "operations": ["拆短句", "删掉总结句", "保留档案室线索"],
                }
            ],
        },
        review_target="钟楼交易",
        scene_name="钟楼交易",
        source_path="一 · 开端/钟楼交易.arc",
    )

    assert len(tickets) == 1
    state = facade.load_state()
    assert state["quality_memory"][0]["status"] == "open"
    assert "林烬与沈棠" in state["quality_memory"][0]["target"]

    task_pack = facade.compose_scene_task_pack(
        chapter_index=0,
        scene_index=1,
        scene_title="钟楼交易返修",
        scene_description="重写林烬与沈棠的对白。",
        scene_characters=["林烬", "沈棠"],
    )
    text = task_pack["text"]
    assert "未关闭修订工单" in text
    assert "减少完整解释句" in text
    assert "旧钥匙已经交给林烬" in text
    assert task_pack["pack"]["quality_tickets"]

    status = facade.format_status()
    assert "开放修订工单数: 1" in status

    query = facade.query_text("林烬对白修订")
    assert "开放修订工单" in query
    assert "减少完整解释句" in query


def test_story_memory_closes_quality_tickets_after_passing_review(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    project_path = tmp_path / "uid_13" / "projects" / "demo"
    project_path.mkdir(parents=True)

    facade = StoryMemoryFacade("13", "demo")
    facade.record_quality_review(
        review={
            "decision": "REVISE",
            "overall_grade": "B",
            "rewrite_required": True,
            "rewrite_brief": "沈棠和林烬的对白仍有解释腔。",
            "fix_tickets": [
                {
                    "target": "沈棠和林烬的对白",
                    "edit_goal": "减少解释腔，增加试探感。",
                    "operations": ["删掉总结句"],
                }
            ],
        },
        review_target="钟楼交易",
        scene_name="钟楼交易",
        source_path="一 · 开端/钟楼交易.arc",
    )
    assert "开放修订工单数: 1" in facade.format_status()

    facade.record_quality_review(
        review={
            "decision": "PASS",
            "overall_grade": "A",
            "rewrite_required": False,
            "fix_tickets": [],
        },
        review_target="钟楼交易",
        scene_name="钟楼交易",
        source_path="一 · 开端/钟楼交易.arc",
    )

    state = facade.load_state()
    assert state["quality_memory"][0]["status"] == "resolved"
    assert state["quality_memory"][0]["resolution"] == "critic_pass"
    assert "开放修订工单数: 0" in facade.format_status()

    task_pack = facade.compose_scene_task_pack(
        scene_title="钟楼交易",
        scene_description="继续处理沈棠和林烬。",
        scene_characters=["沈棠", "林烬"],
    )["text"]
    assert "减少解释腔" not in task_pack
    assert "暂无命中的开放修订工单" in task_pack


def test_story_memory_advances_and_resolves_existing_threads(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    project_path = tmp_path / "uid_15" / "projects" / "demo"
    project_path.mkdir(parents=True)

    deltas = [
        {
            "summary": "林烬发现档案室记录被篡改。",
            "events": [],
            "character_updates": [],
            "relationship_changes": [],
            "foreshadows": [
                {
                    "description": "档案室记录被篡改的真相",
                    "status": "open",
                    "related_characters": ["林烬"],
                    "evidence": "不要相信档案室的记录",
                }
            ],
            "fact_claims": [],
            "conflict_risks": [],
        },
        {
            "summary": "林烬拿到篡改记录的原始账册。",
            "events": [],
            "character_updates": [],
            "relationship_changes": [],
            "foreshadows": [
                {
                    "description": "档案室记录被篡改的真相已经被原始账册证实",
                    "status": "resolved",
                    "related_characters": ["林烬"],
                    "evidence": "原始账册证明档案被改过",
                }
            ],
            "fact_claims": [],
            "conflict_risks": [],
        },
    ]

    def fake_extract(self, *args, **kwargs):
        return deltas.pop(0)

    monkeypatch.setattr(StoryMemoryFacade, "_extract_state_delta_with_llm", fake_extract)
    facade = StoryMemoryFacade("15", "demo")
    facade.record_scene_write(
        scene_text="# 钟楼交易\n[-1] 不要相信档案室的记录。",
        chapter_index=0,
        scene_index=0,
        scene_title="钟楼交易",
        scene_characters=["林烬"],
        use_llm_extractor=True,
    )
    facade.record_scene_write(
        scene_text="# 档案室\n[-1] 原始账册证明档案被改过。",
        chapter_index=0,
        scene_index=1,
        scene_title="档案室",
        scene_characters=["林烬"],
        use_llm_extractor=True,
    )

    state = facade.load_state()
    assert len(state["threads"]) == 1
    thread = state["threads"][0]
    assert thread["status"] == "resolved"
    assert thread["resolved_title"] == "档案室"
    assert len(thread["history"]) == 1

    task_pack = facade.compose_scene_task_pack(
        scene_title="后续追查",
        scene_description="林烬继续调查档案室后续。",
        scene_characters=["林烬"],
    )["text"]
    assert "档案室记录被篡改的真相" not in task_pack
    assert "暂无命中的开放线索" in task_pack
    assert "开放线索数: 0" in facade.format_status()


def test_critic_receives_story_memory_read_tool() -> None:
    tool_names = {tool.name for tool in get_tools_for_agent("agent_critic")}
    assert "story_memory_tool" in tool_names


def test_production_context_pack_injects_story_memory_quality_tickets(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    project_path = tmp_path / "uid_10" / "projects" / "demo"
    (project_path / "stories").mkdir(parents=True)

    facade = StoryMemoryFacade("10", "demo")
    facade.record_quality_review(
        review={
            "decision": "REVISE",
            "overall_grade": "B",
            "rewrite_required": True,
            "rewrite_brief": "沈棠和林烬的对白需要更像互相试探。",
            "fix_tickets": [
                {
                    "target": "沈棠和林烬的对白",
                    "edit_goal": "减少解释腔，保留旧钥匙和档案室线索。",
                    "must_keep": ["旧钥匙已经交到林烬手里"],
                    "operations": ["删掉段尾总结", "增加误解与停顿"],
                }
            ],
        },
        review_target="钟楼交易",
        scene_name="钟楼交易",
    )

    from agents.routes.production import build_scriptwriter_context_pack

    pack = build_scriptwriter_context_pack(
        user_id="10",
        project_name="demo",
        operation="continue",
        scene_name="钟楼交易",
        guidance="重写沈棠和林烬的对白。",
    )

    assert "当前场景事实包" in pack["context"]
    assert "未关闭修订工单" in pack["context"]
    assert "减少解释腔" in pack["context"]
    assert "旧钥匙已经交到林烬手里" in pack["context"]


def test_auto_write_review_records_quality_memory(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    project_path = tmp_path / "uid_14" / "projects" / "demo"
    project_path.mkdir(parents=True)

    class FakeCritic:
        def evaluate(self, **kwargs):
            return {
                "decision": "REVISE",
                "overall_grade": "B",
                "overall_summary": "对白仍有任务式说明。",
                "dimension_grades": {},
                "hits": [],
                "fix_tickets": [
                    {
                        "target": "当前对白组",
                        "edit_goal": "降低说明感，增加现场迟疑。",
                        "must_keep": ["旧钥匙仍然交出"],
                        "operations": ["删去解释句", "加入打断"],
                    }
                ],
                "rewrite_required": True,
                "rewrite_brief": "优先修改当前对白组。",
                "status": "APPROVE",
                "critique": "需要小修。",
                "specific_feedback": "对白太完整。",
            }

    from agents.routes.auto_write import record_auto_write_scene_review
    from agents.routes.auto_write_state import load_auto_write_state

    review = record_auto_write_scene_review(
        user_id="14",
        project_name="demo",
        critic=FakeCritic(),
        scene_text="# 钟楼交易\n[-1] 雨声落下。",
        context_text="前文",
        guidance_text="写钟楼交易",
        scene_title="钟楼交易",
        source_rel_path="一 · 开端/1-1 钟楼交易.arc",
        worldview="世界观",
        roles="角色",
        style_profile={},
        story_tags_block="",
    )

    assert review and review["decision"] == "REVISE"

    state_path = project_path / ".story_memory" / "narrative_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    ticket = state["quality_memory"][0]
    assert ticket["status"] == "open"
    assert ticket["scene_name"] == "钟楼交易"
    assert ticket["source_path"] == "一 · 开端/1-1 钟楼交易.arc"
    assert "降低说明感" in ticket["edit_goal"]

    aw_state = load_auto_write_state("14", "demo")
    assert aw_state["lastReviewDecision"] == "REVISE"
    assert aw_state["lastReviewGrade"] == "B"
    assert aw_state["lastReviewTicketCount"] == 1


def test_story_memory_prefers_recent_relevant_scenes_after_twelve_writes(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    project_path = tmp_path / "uid_41" / "projects" / "demo"
    project_path.mkdir(parents=True)

    facade = StoryMemoryFacade("41", "demo")
    for scene_index in range(12):
        facade.record_scene_write(
            scene_text=f"# 1-{scene_index + 1} 场景\n[旁白]\n共同线索推进到第 {scene_index + 1} 步。",
            chapter_index=0,
            scene_index=scene_index,
            scene_title=f"1-{scene_index + 1} 场景",
            scene_characters=["林烬"],
            use_llm_extractor=False,
        )

    result = facade.query_text("共同线索", max_items=4)
    related_scenes = result.split("[相关场景]", 1)[1]

    assert related_scenes.index("1-12 场景") < related_scenes.index("1-11 场景")
    assert "1-1 场景" not in related_scenes


def test_scene_task_pack_excludes_future_memory_when_rewriting_earlier_scene(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    project_path = tmp_path / "uid_42" / "projects" / "demo"
    project_path.mkdir(parents=True)

    facade = StoryMemoryFacade("42", "demo")
    for scene_index in range(12):
        facade.record_scene_write(
            scene_text=f"# 1-{scene_index + 1} 场景\n[旁白]\n林烬记录第 {scene_index + 1} 次钟声。",
            chapter_index=0,
            scene_index=scene_index,
            scene_title=f"1-{scene_index + 1} 场景",
            scene_characters=["林烬"],
            use_llm_extractor=False,
        )

    payload = facade.compose_scene_task_pack(
        chapter_index=0,
        scene_index=5,
        scene_title="1-6 场景",
        scene_description="重写第六场。",
        scene_characters=["林烬"],
    )

    assert [item["scene_title"] for item in payload["pack"]["recent_scenes"]] == [
        "1-4 场景",
        "1-5 场景",
    ]
    assert "第 12 次钟声" not in payload["text"]
    assert "1-12 场景" not in payload["text"]


def test_enqueued_scene_memory_is_visible_before_async_enrichment(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    project_path = tmp_path / "uid_43" / "projects" / "demo"
    project_path.mkdir(parents=True)
    submitted: list[dict] = []

    def fake_submit(_label, _fn, _user_id, _project_name, payload, _job_label):
        submitted.append(payload)
        return None

    monkeypatch.setattr("agents.story_memory.jobs._submit", fake_submit)

    from agents.story_memory.jobs import enqueue_scene_memory_write

    enqueue_scene_memory_write(
        user_id="43",
        project_name="demo",
        scene_text="# 1-1 初遇\n[旁白]\n林烬在钟楼醒来。",
        chapter_index=0,
        scene_index=0,
        scene_title="1-1 初遇",
        scene_characters=["林烬"],
    )

    state = StoryMemoryFacade("43", "demo").load_state()
    assert state["scenes"][0]["scene_title"] == "1-1 初遇"
    assert state["scenes"][0]["state_delta_source"] == "heuristic"
    assert submitted[0]["use_llm_extractor"] is True
    assert submitted[0]["require_current_source_hash"] is True


def test_slow_enrichment_does_not_block_new_snapshot_or_overwrite_it(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    project_path = tmp_path / "uid_45" / "projects" / "demo"
    project_path.mkdir(parents=True)
    facade = StoryMemoryFacade("45", "demo")
    facade.record_scene_write(
        scene_text="# 1-1 初遇\n[旁白]\n旧版本。",
        chapter_index=0,
        scene_index=0,
        scene_title="1-1 初遇",
        use_llm_extractor=False,
    )

    enrichment_started = threading.Event()
    release_enrichment = threading.Event()

    def slow_enrichment(self, **_payload):
        enrichment_started.set()
        assert release_enrichment.wait(timeout=3)
        return {
            "source": "llm",
            "summary": "旧版本的迟到抽取。",
            "events": [],
            "character_updates": [],
            "relationship_changes": [],
            "foreshadows": [],
            "fact_claims": [],
            "conflict_risks": [],
        }

    monkeypatch.setattr(StoryMemoryFacade, "prepare_scene_enrichment", slow_enrichment)
    from agents.story_memory.jobs import _record_scene_write_job

    payload = {
        "scene_text": "# 1-1 初遇\n[旁白]\n旧版本。",
        "chapter_index": 0,
        "scene_index": 0,
        "scene_title": "1-1 初遇",
        "use_llm_extractor": True,
        "require_current_source_hash": True,
    }
    worker = threading.Thread(
        target=_record_scene_write_job,
        args=("45", "demo", payload, "测试抽取"),
    )
    worker.start()
    assert enrichment_started.wait(timeout=1)

    facade.record_scene_write(
        scene_text="# 1-1 初遇\n[旁白]\n新版本。",
        chapter_index=0,
        scene_index=0,
        scene_title="1-1 初遇",
        use_llm_extractor=False,
    )
    release_enrichment.set()
    worker.join(timeout=3)

    state = facade.load_state()
    assert state["scenes"][0]["summary"] == "1-1 初遇 新版本。"
    assert state["scenes"][0]["state_delta_source"] == "heuristic"
