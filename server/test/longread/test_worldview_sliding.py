"""世界观滑窗回归：超阈走地图 + 首片，未超阈保持全文。"""

from __future__ import annotations


def test_oversized_worldview_injects_map_and_first_window(monkeypatch) -> None:
    from agents.context_provider import AgentContextProvider
    from agents import worldview_source

    long_text = "世界观设定。" * 20000
    monkeypatch.setattr(worldview_source, "_load_worldview_text", lambda *_args: long_text)

    provider = AgentContextProvider("7", "demo")
    provider._bundle_cache = {"worldview": long_text}

    context = provider.get_worldview_context()

    assert "已转滑窗" in context
    assert "长文档地图" in context
    assert "read_worldview_window" in context
    assert len(context) < len(long_text)


def test_small_worldview_keeps_full_injection(monkeypatch) -> None:
    from agents.context_provider import AgentContextProvider
    from agents import worldview_source

    short_text = "小世界观：山海之间有一个村子。"
    monkeypatch.setattr(worldview_source, "_load_worldview_text", lambda *_args: short_text)

    provider = AgentContextProvider("7", "demo")
    provider._bundle_cache = {"worldview": short_text}

    assert provider.get_worldview_context() == f"### 世界观设定\n{short_text}"
