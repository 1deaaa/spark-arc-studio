from __future__ import annotations

import re


_FORBIDDEN_AI_DIRECTIVE_RE = re.compile(
    r"^\s*(?:@next\b.*|@act\b.*|@(?:web|presentation)\b.*)$",
    re.IGNORECASE,
)


def sanitize_arc_for_ai_context(text: str) -> str:
    """清理传给 AI 的历史 ARC 片段，避免模型模仿运行时控制节点。

    解析器仍兼容历史手写文件中的 ``@next`` / ``@act`` / ``@web``；
    这里仅构造 Scriptwriter 可见的干净上下文视图，不改写用户原文件。
    """
    if not text:
        return ""

    kept_lines: list[str] = []
    for line in str(text).splitlines():
        if _FORBIDDEN_AI_DIRECTIVE_RE.match(line):
            continue
        kept_lines.append(line)
    return "\n".join(kept_lines).strip()
