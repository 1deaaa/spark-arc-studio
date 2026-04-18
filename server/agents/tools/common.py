from __future__ import annotations

import json
import os

from core.request_context import current_user_id, get_current_agent_id, get_current_project_name


class ToolExecutionContext:
    @staticmethod
    def get_context() -> tuple[str, str]:
        user_id = current_user_id.get()
        project_name = get_current_project_name()
        if not user_id or not project_name:
            raise RuntimeError("缺少用户或项目上下文，无法执行工具")
        return str(user_id), project_name

    @staticmethod
    def get_agent_id() -> str | None:
        return get_current_agent_id()


def _strip_markdown_fence(content: str) -> str:
    text = (content or "").strip()
    if not text.startswith("```"):
        return text

    lines = text.splitlines()
    if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return text


def _normalize_ws(text: str) -> str:
    import re

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    lines = [re.sub(r"[ \t]+", " ", line) for line in lines]
    result = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
    return result


def _apply_patch(
    file_path: str,
    search_text: str,
    replace_text: str,
    *,
    validate_json: bool = False,
    file_label: str | None = None,
) -> str:
    import re

    label = file_label or os.path.basename(file_path)

    if not os.path.exists(file_path):
        return f"局部修改失败：文件 '{label}' 不存在。"

    with open(file_path, "r", encoding="utf-8") as f:
        original = f.read()

    if search_text in original:
        new_content = original.replace(search_text, replace_text, 1)
    else:
        norm_original = _normalize_ws(original)
        norm_search = _normalize_ws(search_text)

        if norm_search not in norm_original:
            return (
                f"局部修改失败：在 '{label}' 中未找到与 search_text 匹配的内容。\n"
                "提示：请确保 search_text 取自原文的完整连续片段（建议 1‑3 句，避免过短导致误替换），"
                "且不包含额外的解释性文字。"
            )

        norm_start = norm_original.index(norm_search)
        norm_end = norm_start + len(norm_search)
        orig_clean = original.replace("\r\n", "\n").replace("\r", "\n")
        orig_lines = orig_clean.split("\n")
        orig_line_offsets: list[int] = []
        offset = 0
        for line in orig_lines:
            orig_line_offsets.append(offset)
            offset += len(line) + 1

        norm_lines_before = norm_original[:norm_start].count("\n")
        norm_lines_in = norm_search.count("\n")
        start_line_idx = norm_lines_before
        end_line_idx = norm_lines_before + norm_lines_in

        if start_line_idx >= len(orig_line_offsets):
            return "局部修改失败：行映射计算超出范围，请缩短 search_text 后重试。"

        orig_char_start = orig_line_offsets[start_line_idx]
        if end_line_idx < len(orig_line_offsets):
            orig_char_end = orig_line_offsets[end_line_idx] + len(orig_lines[end_line_idx])
        else:
            orig_char_end = len(orig_clean)

        new_content = orig_clean[:orig_char_start] + replace_text + orig_clean[orig_char_end:]

    if validate_json:
        try:
            json.loads(new_content)
        except Exception as e:
            return (
                f"局部修改失败：替换后破坏了原有的 JSON 格式（{e}）。"
                "请检查 replace_text 的引号、括号和逗号是否完整闭合。"
            )

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    return f"已成功局部更新 '{label}'。"
