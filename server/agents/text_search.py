"""文本正则搜索的公共安全底座。"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import regex


MAX_REGEX_PATTERN_CHARS = 1000
DEFAULT_REGEX_TIMEOUT_SECONDS = 0.2


class RegexPatternError(ValueError):
    """正则模式无效或超过系统限制。"""


class RegexSearchTimeoutError(TimeoutError):
    """正则匹配超过单段文本的执行时限。"""


def compile_search_pattern(pattern: str, *, case_sensitive: bool = False) -> Any:
    """编译搜索表达式，并限制模型或用户提交的超长模式。"""
    text = str(pattern or "")
    if not text:
        raise RegexPatternError("正则表达式不能为空")
    if len(text) > MAX_REGEX_PATTERN_CHARS:
        raise RegexPatternError(f"正则表达式不能超过 {MAX_REGEX_PATTERN_CHARS} 个字符")

    flags = regex.MULTILINE
    if not case_sensitive:
        flags |= regex.IGNORECASE
    try:
        return regex.compile(text, flags)
    except regex.error as exc:
        raise RegexPatternError(str(exc)) from exc


def iter_search_matches(
    compiled: Any,
    text: str,
    *,
    timeout_seconds: float = DEFAULT_REGEX_TIMEOUT_SECONDS,
) -> Iterator[Any]:
    """迭代正则命中；每段文本超时后终止，避免灾难性回溯阻塞 Agent。"""
    try:
        yield from compiled.finditer(str(text or ""), timeout=max(float(timeout_seconds), 0.001))
    except TimeoutError as exc:
        raise RegexSearchTimeoutError("正则搜索超时，请缩小表达式范围或改用普通关键词") from exc


def search_first_match(
    compiled: Any,
    text: str,
    *,
    pos: int = 0,
    endpos: int | None = None,
    timeout_seconds: float = DEFAULT_REGEX_TIMEOUT_SECONDS,
) -> Any | None:
    """返回首个正则命中，并应用与批量搜索相同的超时保护。"""
    source = str(text or "")
    try:
        if endpos is None:
            return compiled.search(source, pos=max(int(pos), 0), timeout=max(float(timeout_seconds), 0.001))
        return compiled.search(
            source,
            pos=max(int(pos), 0),
            endpos=max(int(endpos), 0),
            timeout=max(float(timeout_seconds), 0.001),
        )
    except TimeoutError as exc:
        raise RegexSearchTimeoutError("正则搜索超时，请缩小表达式范围或改用普通关键词") from exc


def escape_search_literal(value: str) -> str:
    """把普通文本转义为正则字面量。"""
    return regex.escape(str(value or ""))
