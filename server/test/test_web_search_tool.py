from pathlib import Path
import sys


SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))


from agents.tools import web_search as web_search_module


class _Response:
    def __init__(self, text="", status_code=200, headers=None, json_payload=None):
        self.text = text
        self.status_code = status_code
        self.headers = headers or {}
        self._json_payload = json_payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._json_payload


def _sse(payload: str, headers=None):
    merged_headers = {"content-type": "text/event-stream"}
    merged_headers.update(headers or {})
    return _Response(f"event: message\ndata: {payload}\n\n", headers=merged_headers)


def test_web_search_calls_exa_mcp_streamable_http(monkeypatch):
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        if json["method"] == "initialize":
            return _sse(
                '{"result":{"protocolVersion":"2025-06-18"},"jsonrpc":"2.0","id":1}',
                headers={"mcp-session-id": "sid-1"},
            )
        if json["method"] == "notifications/initialized":
            return _Response(status_code=202, headers={"content-type": "application/json"})
        if json["method"] == "tools/call":
            return _sse(
                '{"result":{"content":[{"type":"text","text":"Title: Example\\nURL: https://example.com\\nHighlights:\\nUseful fact."}]},"jsonrpc":"2.0","id":2}'
            )
        raise AssertionError(f"unexpected MCP method: {json['method']}")

    monkeypatch.setattr(web_search_module.requests, "post", fake_post)
    monkeypatch.setattr(web_search_module, "_current_search_time_text", lambda: "2026-05-06 16:10:00 +0800")

    result = web_search_module.web_search.invoke({"query": "example topic", "num_results": 2})

    assert "联网搜索 \"example topic\"" in result
    assert "检索时间: 2026-05-06 16:10:00 +0800" in result
    assert "Useful fact." in result
    assert calls[2]["json"]["params"]["name"] == "web_search_exa"
    assert calls[2]["json"]["params"]["arguments"]["numResults"] == 2
    assert "2026-05-06 16:10:00 +0800" in calls[2]["json"]["params"]["arguments"]["query"]
    assert "example topic" in calls[2]["json"]["params"]["arguments"]["query"]
    assert calls[2]["headers"]["mcp-session-id"] == "sid-1"
