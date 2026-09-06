"""长文档滑窗底座回归：地图稳定、线索账本、带线索折叠。"""

from __future__ import annotations


def test_source_manifest_render_is_stable() -> None:
    from agents.longread import SourceManifest

    manifest = SourceManifest(
        source_id="att-1",
        filename="长篇.txt",
        chunk_count=3,
        total_tokens=90000,
        entries=("开头", "中段", "结尾"),
    )
    first = manifest.render()
    assert "共 3 个窗口" in first
    assert "窗口 0" in first and "窗口 2" in first
    assert manifest.render() == first


def test_ledger_is_append_only_and_capped() -> None:
    from agents.longread import ClueLedger, WindowClue

    ledger = ClueLedger(max_entries=2)
    ledger.add(WindowClue(source_id="att-1", chunk_index=0, clue="线索A"))
    ledger.add(WindowClue(source_id="att-1", chunk_index=1, clue="线索B"))
    ledger.add(WindowClue(source_id="att-1", chunk_index=2, clue="线索C"))

    assert [item.clue for item in ledger.entries] == ["线索B", "线索C"]
    rendered = ledger.render()
    assert "只追加" in rendered
    assert "线索C" in rendered


def test_collapse_keeps_clues_and_rejump_pointer() -> None:
    from langchain_core.messages import HumanMessage, ToolMessage

    from agents.longread import ClueLedger, WindowClue, collapse_longread_tool_history

    ledger = ClueLedger()
    ledger.add(WindowClue(
        source_id="att-1",
        chunk_index=0,
        clue="开头埋了玉佩伏笔",
        evidence="“玉佩落地”",
    ))
    messages = [
        HumanMessage(content="查伏笔"),
        ToolMessage(
            content='[source_id="att-1" chunk_index=0]\n玉佩落地，众人沉默……',
            tool_call_id="old-window",
            name="read_attachment_chunk",
        ),
        HumanMessage(content="继续"),
        ToolMessage(
            content='[source_id="att-1" chunk_index=1]\n中段正文……',
            tool_call_id="fresh-window",
            name="read_attachment_chunk",
        ),
    ]

    collapsed = collapse_longread_tool_history(
        messages, fresh_call_ids={"fresh-window"}, ledger=ledger,
    )

    assert collapsed == 1
    assert "玉佩" in messages[1].content
    assert 'chunk_index=0' in messages[1].content
    assert messages[3].content.startswith('[source_id="att-1" chunk_index=1]')


def test_collapse_never_rewrites_middle_of_active_task() -> None:
    """本轮新读窗口原文必须完整保留，只折旧轮。"""
    from langchain_core.messages import HumanMessage, ToolMessage

    from agents.longread import collapse_longread_tool_history

    messages = [
        HumanMessage(content="本轮问题"),
        ToolMessage(
            content='[source_id="att-1" chunk_index=2]\n本轮刚读的原文',
            tool_call_id="current-window",
            name="read_longread_window",
        ),
    ]

    assert collapse_longread_tool_history(
        messages, fresh_call_ids={"current-window"},
    ) == 0
    assert "本轮刚读的原文" in messages[1].content


def test_ledger_store_roundtrip_and_room_isolation(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))

    from agents.longread import ClueLedger, LedgerStore, WindowClue, ledger_key

    project_path = tmp_path / "uid_7" / "projects" / "demo"
    project_path.mkdir(parents=True)

    ledger = ClueLedger()
    ledger.add(WindowClue(source_id="att-1", chunk_index=0, clue="线索A"))
    key = ledger_key("7", "demo", "agent_director", "global")
    LedgerStore.save("7", "demo", key, ledger)

    restored = LedgerStore.load("7", "demo", key)
    assert [item.clue for item in restored.entries] == ["线索A"]

    other = LedgerStore.load("7", "demo", ledger_key("7", "demo", "agent_director", "other"))
    assert other.entries == []
