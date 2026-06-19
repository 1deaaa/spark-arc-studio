from __future__ import annotations

import asyncio
import inspect
import json
from pathlib import Path

from agents.story_memory import StoryMemoryFacade
from agents.tools.registry import get_tools_for_agent


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
    assert "当前场景任务包" in text
    assert "林烬" in text
    assert "钟楼交易" in text
    assert "档案室秘密" in text


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


def test_scriptwriter_memory_write_call_sites_are_async() -> None:
    from agents.routes import auto_write, production
    from agents.tools import scriptwriter

    auto_write_source = inspect.getsource(auto_write.generate_script_stream)
    production_source = inspect.getsource(production._record_story_memory_from_story_file)
    tool_source = inspect.getsource(scriptwriter.create_or_rewrite_script.func)

    assert "上一场完整正文（自动写作硬上下文" in auto_write_source
    assert "previous_scene_context" in auto_write_source
    assert "enqueue_scene_memory_write" in auto_write_source
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
    assert "暂无命中的开放伏笔" in task_pack
    assert "开放线索/伏笔数: 0" in facade.format_status()


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

    assert "当前场景任务包" in pack["context"]
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
