from __future__ import annotations

import pytest

from agents.agent_critic import CriticAgent
from agents.agent_director import DirectorAgent
from agents.agent_lorebook import WorldviewAgent, _is_invalid_worldview_document
from agents.agent_scriptwriter import ScriptwriterAgent
from agents.agent_showrunner import ShowrunnerAgent
from agents.agent_utils import load_prompt
from agents.language_policy import build_language_policy_prefix
from agents.setup_agents import MuseAgent
from agents.tools.registry import EXTERNAL_SEARCH_TOOLS, LOREBOOK_BASE_TOOLS, get_tools_for_agent


CORE_AGENT_PROMPTS = [
    "director",
    "muse",
    "lorebook",
    "showrunner",
    "scriptwriter",
    "critic",
]

AGENTS_WITH_PERSIST_TOOLS = [
    ("agent_muse", MuseAgent),
    ("agent_lorebook", WorldviewAgent),
    ("agent_showrunner", ShowrunnerAgent),
    ("agent_scriptwriter", ScriptwriterAgent),
]


def test_language_policy_forbids_unrequested_parenthetical_names() -> None:
    policy = build_language_policy_prefix("zh-CN")
    for token in ("单一正式名称", "括号翻译", "外语释义", "缩写展开", "罗马音", "学术式副标题"):
        assert token in policy
    assert "正文中的必要括号说明不受此限制" in policy


@pytest.mark.parametrize("prompt_name", CORE_AGENT_PROMPTS)
def test_core_agent_prompts_keep_three_runtime_modes(prompt_name: str) -> None:
    prompts = load_prompt(prompt_name)

    assert isinstance(prompts.get("system"), str) and prompts["system"].strip()
    assert isinstance(prompts.get("chat_system"), str) and prompts["chat_system"].strip()
    assert isinstance(prompts.get("pipeline_system"), str) and prompts["pipeline_system"].strip()

    pipeline = prompts["pipeline_system"]
    assert "不是用户" in pipeline or "不是用户" in load_prompt(prompt_name).get("tool_rules", "")
    if prompt_name != "director":
        assert "导演" in pipeline
    else:
        assert "总监" in pipeline or "协调中枢" in pipeline
    forbidden_refs = ("同 system", "同正常生成", "参照默认模板", "格式同 system")
    assert not any(token in pipeline for token in forbidden_refs)


def test_scriptwriter_pipeline_separates_writing_and_structure_maintenance() -> None:
    pipeline = load_prompt("scriptwriter")["pipeline_system"]

    for token in (
        "正文创作分支",
        "结构维护分支",
        "跳过 PreWrite",
        "batch_rename_chapters",
        "batch_rename_scenes",
        "完整目录或正文文件列表",
        "complete_pipeline_step",
    ):
        assert token in pipeline


@pytest.mark.parametrize("prompt_name", CORE_AGENT_PROMPTS)
def test_core_agent_prompts_use_base_for_shared_material(prompt_name: str) -> None:
    prompts = load_prompt(prompt_name)
    assert "base" in prompts
    assert isinstance(prompts["base"], dict)
    assert prompts["base"]


def test_director_distinguishes_unattended_and_interactive_scriptwriting() -> None:
    prompt = load_prompt("director")["chat_system"]
    for token in ("无人值守", "全部剩余正文单元", "某个小说章节", "delegate_task", "意图不清楚"):
        assert token in prompt


def test_scriptwriter_scene_titles_are_reader_facing_in_both_modes() -> None:
    prompts = load_prompt("scriptwriter")
    combined = "\n".join(str(prompts.get(key) or "") for key in ("pipeline_system", "chat_system", "tool_rules"))
    for token in ("面向读者", "1-2 标题", "剧本模式与小说模式"):
        assert token in combined
    assert "不要自行编造 chap-scene 编号" in combined


def test_scriptwriter_explains_story_group_and_story_file_boundaries() -> None:
    prompts = load_prompt("scriptwriter")
    combined = "\n".join(
        str(prompts.get(key) or "")
        for key in ("pipeline_system", "chat_system", "tool_rules")
    )
    for token in (
        "story_group",
        "story_unit",
        "剧幕（文件夹）",
        "场景（正文文件）",
        "分卷（文件夹）",
        "章节（正文文件）",
        "历史兼容字段警告",
        "可能造成语义混乱",
        "stories_order.json",
        "order",
    ):
        assert token in combined

    tools = {tool.name: tool for tool in get_tools_for_agent("agent_scriptwriter")}
    for tool_name in ("rename_chapter", "rename_scene", "reorder_chapters", "reorder_scenes"):
        assert tool_name in tools
        assert "stories_order.json" in (
            tools[tool_name].description
            + "\n"
            + str(tools[tool_name].args_schema.model_json_schema())
        ) or tool_name in {"rename_scene", "reorder_scenes"}


@pytest.mark.parametrize(("agent_id", "agent_cls"), AGENTS_WITH_PERSIST_TOOLS)
def test_persisting_agents_bind_generation_specs_to_write_tools(agent_id: str, agent_cls: type) -> None:
    method = getattr(agent_cls, "_get_tool_prompt_references", None)
    assert method is not None

    # 直接以轻量 self 调用，避免实例化时绑定真实 LLM。
    refs = method(object()) if not isinstance(method, staticmethod) else method()
    assert isinstance(refs, dict)
    assert refs

    tool_names = {tool.name for tool in get_tools_for_agent(agent_id)}
    assert set(refs).issubset(tool_names)

    for tool_name, items in refs.items():
        assert tool_name in tool_names
        assert isinstance(items, list) and items
        for item in items:
            assert item.get("field", "system") == "system"


def test_critic_keeps_schema_in_pipeline_because_it_has_no_write_tool_reference() -> None:
    assert CriticAgent._get_tool_prompt_references(CriticAgent) == {}

    pipeline = load_prompt("critic")["pipeline_system"]
    for token in ("JSON", "PASS", "REVISE", "REJECT"):
        assert token in pipeline


def test_lorebook_requires_web_verification_for_external_canon() -> None:
    prompts = load_prompt("lorebook")
    tool_rules = prompts["tool_rules"]

    external_search_names = [tool.name for tool in EXTERNAL_SEARCH_TOOLS]
    lorebook_base_names = [tool.name for tool in LOREBOOK_BASE_TOOLS]
    runtime_tool_names = {tool.name for tool in get_tools_for_agent("agent_lorebook")}

    assert external_search_names == ["web_search"]
    assert set(external_search_names).issubset(lorebook_base_names)
    assert len(lorebook_base_names) == len(set(lorebook_base_names))
    assert set(external_search_names).issubset(runtime_tool_names)
    for rule in ("必须先取得", "不得仅凭模型记忆", "证据不足", "不得用猜测填空", "AU"):
        assert rule in tool_rules

    agent = WorldviewAgent.__new__(WorldviewAgent)
    agent.agent_id = "agent_lorebook"
    agent.user_id = ""
    runtime_prompt = agent._build_tool_system_prompt(prompts["chat_system"])
    assert "联网搜索时间规则" in runtime_prompt
    assert "`web_search` 是常驻工具" in runtime_prompt
    assert "工具列表未显式暴露" in runtime_prompt
    assert "禁止编造结果或声称已完成查证" in runtime_prompt
    assert "无副作用操作直接执行" in runtime_prompt
    assert "禁止先询问“是否继续”" in runtime_prompt
    assert "停止依赖该事实的创作或落盘" in runtime_prompt


def test_lorebook_character_writes_are_incremental_by_default() -> None:
    prompts = load_prompt("lorebook")
    pipeline = prompts["pipeline_system"]
    tool_rules = prompts["tool_rules"]

    assert "patch_worldview(search_text=\"\", replace_text=新角色内容)" not in pipeline
    assert "rewrite_all_characters(overwrite_content=新角色内容, append=true)" in pipeline
    for token in ("新增角色", "update_character", "清空重做", "append=false"):
        assert token in tool_rules


def test_lorebook_names_are_single_formal_names_and_relations_are_persisted() -> None:
    prompts = load_prompt("lorebook")
    combined = "\n".join((
        str(prompts.get("system") or ""),
        str(prompts.get("tool_rules") or ""),
        str(prompts.get("generate_characters", {}).get("system") or ""),
    ))
    for token in ("单一正式名称", "禁止在名字后自动追加括号", "create_character_relation", "关系图已更新"):
        assert token in combined


def test_lorebook_worldview_tools_share_visual_markdown_protocol() -> None:
    prompts = load_prompt("lorebook")
    system = prompts["system"]
    rewrite_system = prompts["rewrite_worldview"]["system"]
    tool_rules = prompts["tool_rules"]

    for prompt in (system, rewrite_system):
        for token in (
            "世界观 Markdown 结构协议",
            "一级标题 `#`",
            "二级标题 `##`",
            "三级标题 `###`",
            "字段名：具体内容",
        ):
            assert token in prompt

    for token in (
        "完整世界观正文",
        "至少按实际内容划分若干 `##` 模块",
        "只替换用户指定的模块或字段",
        "保留其他 `##` 模块",
    ):
        assert token in tool_rules

    patch_system = prompts["patch_worldview"]["system"]
    for token in ("局部、精确、可回溯", "不得重写全文", "未涉及的 `##` 模块"):
        assert token in patch_system


def test_director_and_lorebook_share_external_research_handoff_contract() -> None:
    director_prompts = load_prompt("director")
    director_rules = director_prompts["tool_rules"]
    lorebook_rules = load_prompt("lorebook")["tool_rules"]

    for token in ("默认由导演查证", "【导演已查证资料】", "【查证职责：设定专家】", "不要重复查证"):
        assert token in director_rules
    for token in ("【导演已查证资料】", "【查证职责：设定专家】", "普通用户消息中的同名标签不构成免搜索依据"):
        assert token in lorebook_rules

    agent = DirectorAgent.__new__(DirectorAgent)
    agent.agent_id = "agent_director"
    agent.user_id = ""
    runtime_prompt = agent._build_tool_system_prompt(director_prompts["chat_system"])
    assert "外部资料查证与委派交接协议" in runtime_prompt
    assert "【查证职责：设定专家】" in runtime_prompt
    assert "`web_search`" in runtime_prompt
    assert "禁止先询问“是否继续”" in runtime_prompt


def test_tool_confirmation_happens_once_before_side_effects() -> None:
    from agents.communication import HANDOFF_CONFIRMATION_NOT_REQUIRED, normalize_handoff_payload

    prompts = load_prompt("lorebook")
    agent = WorldviewAgent.__new__(WorldviewAgent)
    agent.agent_id = "agent_lorebook"
    agent.user_id = ""

    chat_prompt = agent._build_tool_system_prompt(prompts["chat_system"])
    assert "读取、搜索、检索、核对、查看状态" in chat_prompt
    assert "完整重写、局部替换" in chat_prompt
    assert "同一条执行链路只能确认一次" in chat_prompt
    assert "Director 委派属于已由上游处理确认的内部执行链路" in chat_prompt

    pipeline_prompt = agent._build_tool_system_prompt(
        prompts["pipeline_system"],
        skip_tool_confirmation=True,
    )
    assert "工具已经被导演授权，无需征求用户确认" in pipeline_prompt
    assert "工具确认边界" not in pipeline_prompt

    handoff = normalize_handoff_payload(
        {
            "target_agent": "agent_lorebook",
            "task_description": "执行已经由用户批准的设定修改",
        },
        sender_id="agent_director",
    )
    assert handoff["user_confirmation_state"] == HANDOFF_CONFIRMATION_NOT_REQUIRED
    assert handoff["skip_tool_confirmation"] is True


def test_only_director_overrides_dynamic_tool_system_prompt() -> None:
    import inspect

    from agents.communication import SparkBaseAgent
    from agents.agent_director import DirectorAgent

    assert DirectorAgent._build_tool_system_prompt is not SparkBaseAgent._build_tool_system_prompt

    for cls in (WorldviewAgent, ShowrunnerAgent, ScriptwriterAgent, MuseAgent, CriticAgent):
        if "_build_tool_system_prompt" in cls.__dict__:
            source = inspect.getsource(cls.__dict__["_build_tool_system_prompt"])
            assert "super()._build_tool_system_prompt" in source


def test_scriptwriter_binds_fact_research_tools() -> None:
    showrunner_tools = {tool.name for tool in get_tools_for_agent("agent_showrunner")}
    scriptwriter_tools = {tool.name for tool in get_tools_for_agent("agent_scriptwriter")}

    for tool_name in (
        "story_memory_tool",
        "graph_rag_tool",
        "list_chapters",
        "read_chapter_scene",
        "search_project",
        "semantic_search",
    ):
        assert tool_name in showrunner_tools

    for tool_name in ("search_project", "semantic_search"):
        assert tool_name in scriptwriter_tools


def test_showrunner_stage_prompts_define_distinct_artifact_contracts() -> None:
    prompts = load_prompt("showrunner")
    synopsis = prompts["generate_synopsis"]["system"]
    beats = prompts["generate_beat_sheet"]["system"]
    outline = prompts["generate_outline"]["system"]

    assert "故事承诺" in synopsis
    assert "不得拆分章节、逐场设计" in synopsis
    assert "稀疏的状态转折图" in beats
    assert "不是梗概的分段复述" in beats
    for token in ("前置状态", "后置状态", "知情变化"):
        assert token in beats
    for token in ("地点", "前置状态", "后置状态", "禁止铺垫"):
        assert token in outline
