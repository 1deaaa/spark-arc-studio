from __future__ import annotations

import pytest

from agents.communication import SparkBaseAgent
from agents.routes.chat_persistence import ChatStreamAccumulator
from agents.tools.web_search import (
    ExaSearchOptions,
    SearchProvider,
    TavilySearchOptions,
    WebSearchInput,
    _build_exa_arguments,
    _build_tavily_arguments,
    _call_tavily_keyless_search,
    _call_search_with_retry,
    _McpSearchClient,
    SearchRetryExhaustedError,
    SearchUpstreamUnavailableError,
    web_search,
)
from core import search_provider_settings
from core.search_provider_settings import (
    SearchProviderRuntimeConfig,
    SearchProviderUnavailableError,
)


def test_web_search_schema_exposes_provider_specific_options() -> None:
    fields = WebSearchInput.model_fields
    assert {"provider", "query", "num_results", "exa_options", "tavily_options"} <= set(fields)
    assert set(SearchProvider) == {SearchProvider.EXA, SearchProvider.TAVILY}


def test_transient_search_failure_retries_until_upstream_recovers() -> None:
    calls = []
    waits = []

    def operation() -> str:
        calls.append(len(calls) + 1)
        if len(calls) < 3:
            raise SearchUpstreamUnavailableError("上游正在启动。")
        return "recovered"

    result = _call_search_with_retry(
        "exa",
        operation,
        retry_window_seconds=60,
        retry_delays=(2, 5, 10),
        sleep=waits.append,
        monotonic=lambda: 0,
    )

    assert result == "recovered"
    assert calls == [1, 2, 3]
    assert waits == [2, 5]


def test_transient_search_failure_returns_precise_exhausted_state() -> None:
    calls = []

    def operation() -> str:
        calls.append(len(calls) + 1)
        raise SearchUpstreamUnavailableError("无法连接上游 MCP。")

    with pytest.raises(SearchRetryExhaustedError) as exc_info:
        _call_search_with_retry(
            "tavily",
            operation,
            retry_window_seconds=60,
            retry_delays=(2, 5),
            sleep=lambda _delay: None,
            monotonic=lambda: 0,
        )

    assert calls == [1, 2, 3]
    assert exc_info.value.attempts == 3
    assert exc_info.value.reason == "无法连接上游 MCP。"


def test_permanent_search_error_does_not_retry() -> None:
    calls = []

    def operation() -> str:
        calls.append(len(calls) + 1)
        raise RuntimeError("exa MCP HTTP 401")

    with pytest.raises(RuntimeError, match="401"):
        _call_search_with_retry(
            "exa",
            operation,
            retry_delays=(0, 0),
            sleep=lambda _delay: None,
            monotonic=lambda: 0,
        )

    assert calls == [1]


def test_web_search_returns_model_safe_message_after_retry_exhaustion(monkeypatch) -> None:
    monkeypatch.setattr(
        "agents.tools.web_search.get_search_provider_runtime_config",
        lambda *_args, **_kwargs: SearchProviderRuntimeConfig(
            provider="exa",
            url="https://mcp.exa.ai/mcp",
        ),
    )

    def exhausted(*_args, **_kwargs):
        raise SearchRetryExhaustedError("exa", 4, 60, "无法连接上游 MCP。")

    monkeypatch.setattr("agents.tools.web_search._call_search_with_retry", exhausted)
    result = web_search.invoke({"provider": "exa", "query": "latest news"})

    assert result.startswith("联网搜索暂时不可用（exa）")
    assert "尝试 4 次" in result
    assert "本次未能联网核验" in result
    assert "请勿编造搜索结果" in result


def test_missing_search_configuration_is_not_sent_into_retry_loop(monkeypatch) -> None:
    monkeypatch.setattr(
        "agents.tools.web_search.get_search_provider_runtime_config",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            SearchProviderUnavailableError("请配置个人 MCP URL。")
        ),
    )
    retry_calls = []
    monkeypatch.setattr(
        "agents.tools.web_search._call_search_with_retry",
        lambda *_args, **_kwargs: retry_calls.append(True),
    )

    result = web_search.invoke({"provider": "tavily", "query": "latest news"})

    assert result.startswith("联网搜索当前不可用（tavily）")
    assert "这是配置不可用" in result
    assert retry_calls == []


def test_provider_specific_arguments_keep_native_parameter_names() -> None:
    exa_tool, exa_args = _build_exa_arguments(
        "query",
        8,
        ExaSearchOptions(
            search_type="fast",
            category="news",
            include_domains=["example.com"],
            start_published_date="2026-07-01",
            enable_highlights=True,
        ),
    )
    assert exa_tool == "web_search_advanced_exa"
    assert exa_args == {
        "query": "query",
        "numResults": 8,
        "type": "fast",
        "category": "news",
        "includeDomains": ["example.com"],
        "startPublishedDate": "2026-07-01",
        "enableHighlights": True,
    }

    tavily_args = _build_tavily_arguments(
        "query",
        3,
        TavilySearchOptions(
            search_depth="advanced",
            time_range="month",
            include_domains=["example.org"],
            include_raw_content=True,
        ),
    )
    assert tavily_args == {
        "query": "query",
        "search_depth": "advanced",
        "topic": "general",
        "max_results": 5,
        "time_range": "month",
        "include_domains": ["example.org"],
        "include_raw_content": True,
    }


def test_search_provider_config_preserves_keyless_access_and_masks_key(monkeypatch, tmp_path) -> None:
    env_path = tmp_path / ".env"
    monkeypatch.setenv("SPARKARC_SEARCH_PROVIDER_ENV_PATH", str(env_path))
    for key in (
        "SPARKARC_EXA_MCP_URL",
        "SPARKARC_EXA_API_KEY",
        "SPARKARC_TAVILY_MCP_URL",
        "SPARKARC_TAVILY_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)

    keyless = search_provider_settings.update_search_provider_settings(
        "tavily",
        url="https://mcp.tavily.com/mcp",
        api_key="",
    )
    runtime = search_provider_settings.get_search_provider_runtime_config("tavily")
    assert keyless.api_key_set is False
    assert runtime.request_url == "https://mcp.tavily.com/mcp"

    masked = search_provider_settings.update_search_provider_settings("tavily", api_key="secret")
    runtime = search_provider_settings.get_search_provider_runtime_config("tavily")
    assert masked.api_key_set is True
    assert "tavilyApiKey=secret" in runtime.request_url
    assert not hasattr(masked, "api_key")


def test_tavily_keyless_transport_matches_official_mcp_headers(monkeypatch) -> None:
    captured = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"results": [{"title": "ok"}]}

    def fake_post(url, *, headers, json, timeout):
        captured.update(url=url, headers=headers, json=json, timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr("agents.tools.web_search.requests.post", fake_post)
    result = _call_tavily_keyless_search({"query": "query", "max_results": 5})

    assert captured["url"] == "https://api.tavily.com/search"
    assert captured["headers"]["X-Tavily-Access-Mode"] == "keyless"
    assert captured["headers"]["X-Client-Source"] == "tavily-mcp-keyless"
    assert "Authorization" not in captured["headers"]
    assert captured["json"] == {"query": "query", "max_results": 5}
    assert '"title": "ok"' in result


def test_custom_mcp_uses_raw_authorization_header(monkeypatch) -> None:
    captured = {}

    class FakeResponse:
        status_code = 202
        text = ""
        headers = {}

        def raise_for_status(self) -> None:
            return None

    def fake_post(url, *, headers, json, timeout):
        captured.update(url=url, headers=headers, json=json, timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr("agents.tools.web_search.requests.post", fake_post)
    config = SearchProviderRuntimeConfig(
        provider="tavily",
        url="https://mcp.1dea.top/tavily",
        api_key="aideamcp1024",
        source="user",
    )
    _McpSearchClient(config).post("notifications/initialized", {})

    assert captured["url"] == "https://mcp.1dea.top/tavily"
    assert captured["headers"]["Authorization"] == "aideamcp1024"
    assert "tavilyApiKey" not in captured["url"]

    official_exa = SearchProviderRuntimeConfig(
        provider="exa",
        url="https://mcp.exa.ai/mcp",
        api_key="exa-secret",
    )
    assert "exaApiKey=exa-secret" in official_exa.request_url
    assert official_exa.request_headers == {}


def test_user_search_override_is_encrypted_and_bypasses_disabled_system_service(
    monkeypatch,
    tmp_path,
) -> None:
    import llm.agen_matchbox as matchbox_package
    from llm.agen_matchbox import create_matchbox
    from llm.agen_matchbox.models import Base, SearchProviderUserConfig
    from llm.agen_matchbox.security import SecurityManager

    monkeypatch.setenv("AGENT_MATCHBOX_HOME", str(tmp_path))
    manager = create_matchbox(str(tmp_path / "llm_config.db"))
    Base.metadata.create_all(manager.engine)
    manager.llm_auto_key = False
    monkeypatch.setattr(matchbox_package, "_manager_instance", manager)
    SecurityManager.get_instance().set_key("search-test-master-key", persist=False)

    view = search_provider_settings.update_search_provider_user_settings(
        "user-1",
        "tavily",
        url="https://mcp.1dea.top/tavily",
        api_key="aideamcp1024",
    )
    runtime = search_provider_settings.get_search_provider_runtime_config(
        "tavily",
        user_id="user-1",
    )

    assert view["providers"][1]["effective"]["source"] == "user"
    assert runtime.url == "https://mcp.1dea.top/tavily"
    assert runtime.api_key == "aideamcp1024"
    assert runtime.request_headers == {"Authorization": "aideamcp1024"}
    with manager.Session() as session:
        stored = session.query(SearchProviderUserConfig).filter_by(
            user_id="user-1",
            provider="tavily",
        ).one()
        assert stored.api_key.startswith("ENC:")
        assert "aideamcp1024" not in stored.api_key

    with pytest.raises(SearchProviderUnavailableError, match="设置 → 模型平台 → 联网搜索服务"):
        search_provider_settings.get_search_provider_runtime_config(
            "exa",
            user_id="user-1",
        )

    manager.llm_auto_key = True
    system_runtime = search_provider_settings.get_search_provider_runtime_config(
        "exa",
        user_id="user-1",
    )
    assert system_runtime.source == "system"
    assert system_runtime.url == "https://mcp.exa.ai/mcp"

    manager.engine.dispose()


def test_web_search_provider_metadata_survives_chat_persistence() -> None:
    agent = object.__new__(SparkBaseAgent)
    assert agent._tool_event_metadata("web_search", {"provider": "tavily"}) == {
        "tool_provider": "tavily"
    }

    accumulator = ChatStreamAccumulator(channel="chat", task_id="task-1")
    accumulator.append_event({
        "event": "tool_exec_started",
        "tool_name": "web_search",
        "tool_call_key": "search-1",
        "tool_provider": "tavily",
    })
    accumulator.append_event({
        "event": "tool_exec_finished",
        "tool_name": "web_search",
        "tool_call_key": "search-1",
        "tool_provider": "tavily",
    })
    snapshot = accumulator.build_snapshot(status="completed")
    assert snapshot["tool_traces"][0]["tool_provider"] == "tavily"
    tool_segment = next(segment for segment in snapshot["segments"] if segment["type"] == "tool_trace")
    assert tool_segment["tool_provider"] == "tavily"
"""联网搜索供应商配置、传输参数与持久化回归。"""
