"""守护 AI 异常友好化逻辑的公共归属、兼容入口和既有文案。"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from agents.error_formatting import format_ai_error
from agents.routes import schemas


SERVER_ROOT = Path(__file__).resolve().parents[2]
CORE_MODULES = (
    "agents/agent_style_chat.py",
    "agents/auto_write_service.py",
    "agents/communication.py",
    "agents/director_graph.py",
)


def test_route_schema_keeps_only_a_compatibility_reexport() -> None:
    """旧路径与公共实现保持同一函数对象，避免调用方行为分叉。"""
    assert schemas.format_ai_error is format_ai_error
    assert not hasattr(schemas, "_llm_error_mappings")


@pytest.mark.parametrize("module_path", CORE_MODULES)
def test_core_modules_import_error_formatter_without_route_schema_dependency(module_path: str) -> None:
    """核心 Agent 层不得通过路由 Schema 反向获取异常格式化能力。"""
    tree = ast.parse((SERVER_ROOT / module_path).read_text(encoding="utf-8"))
    imports = {
        (node.module or "", alias.name)
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }

    assert ("agents.routes.schemas", "format_ai_error") not in imports
    assert ("agents.error_formatting", "format_ai_error") in imports


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "Error code: 400 - Invalid request content: Schema validation failed: "
            '[standard_violation] /required: null is not of type "array"',
            "请求参数未通过提供商的 Schema 校验。请检查工具定义、结构化输出、Extra Body 和厂商特定参数是否符合该端点要求。",
        ),
        (
            "400 content_filter policy violation",
            "请求因内容安全策略被提供商拒绝。请根据原始信息检查提示词或输入内容。",
        ),
        (
            "Error code: 400 - unsupported parameter",
            "模型提供商认为请求无效。请根据原始信息检查模型名称、端点协议、工具或结构化输出 Schema、Extra Body 及厂商特定参数。",
        ),
    ],
)
def test_public_formatter_preserves_existing_messages(monkeypatch, raw: str, expected: str) -> None:
    """公共实现必须保持既有友好文案和原始错误尾注。"""
    monkeypatch.setattr("core.request_context.get_current_locale", lambda: "zh-CN")

    assert format_ai_error(RuntimeError(raw)) == f"{expected} (原始信息: {raw})"
