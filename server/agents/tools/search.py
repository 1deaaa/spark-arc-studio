from __future__ import annotations

import bisect
import os
import re
from typing import Any

from langchain.tools import tool
from pydantic import BaseModel, Field

from core.request_context import current_user_id, get_current_project_name
from core.utils import get_project_path

from .common import _apply_patch


class SearchProjectInput(BaseModel):
    pattern: str = Field(description="正则表达式模式，用于搜索全项目文本文件。例如 '张三' 或 '哭泣|泪水'")
    case_sensitive: bool = Field(default=False, description="是否区分大小写")


class SemanticSearchInput(BaseModel):
    query: str = Field(description="自然语言查询，用于语义搜索全项目文本。例如 '女主角哭的地方' 或 '主角与反派的对峙'")
    scope: list[str] | None = Field(default=None, description="搜索范围过滤，限定格式类型。可选值：outline, synopsis, beats, worldview, character, arc, novel, chrbind。例如 ['arc', 'outline'] 只搜剧本和大纲")
    k: int = Field(default=8, description="返回结果数量上限")


class ReplaceFromSearchInput(BaseModel):
    indices: list[int] = Field(description="要替换的搜索结果序号列表（从上次搜索结果中选取）")
    replacement: str = Field(description="替换文本。正则搜索时为正则替换字符串（可使用 \\1 等捕获组），语义搜索时为完整替换文本")


_search_results_cache: dict[str, list[dict]] = {}


def _get_search_cache_key() -> str:
    return f"{current_user_id.get()}:{get_current_project_name()}"


def _store_search_results(results: list[dict]) -> None:
    key = _get_search_cache_key()
    _search_results_cache[key] = results


def _get_search_results() -> list[dict]:
    return _search_results_cache.get(_get_search_cache_key(), [])


def _build_line_starts(text: str) -> list[int]:
    line_starts = [0]
    for idx, ch in enumerate(text):
        if ch == "\n":
            line_starts.append(idx + 1)
    return line_starts


def _line_no_from_offset(line_starts: list[int], offset: int) -> int:
    if not line_starts:
        return 1
    return max(1, bisect.bisect_right(line_starts, max(offset, 0)))


def _build_match_context(text: str, start: int, end: int, radius: int = 40) -> str:
    context_start = max(0, start - radius)
    context_end = min(len(text), end + radius)
    context = text[context_start:context_end]
    if context_start > 0:
        context = "..." + context
    if context_end < len(text):
        context = context + "..."
    return context


def _regex_flags(case_sensitive: bool = False) -> int:
    flags = re.MULTILINE
    if not case_sensitive:
        flags |= re.IGNORECASE
    return flags


def _fallback_locate_match(
    text: str,
    compiled: re.Pattern,
    hit: dict,
) -> re.Match | None:
    """当 file_span_start/file_span_end 不可用时，通过 match_text 在全文中定位匹配。

    适用场景：chunk 文本经过策略转换（JSON 重序列化、conception 移除等），
    导致 _locate_chunk_positions 无法定位，但匹配文本本身仍存在于原始文件中。
    """
    match_text = hit.get("match_text", "")
    if not match_text:
        return None

    # 在全文中查找所有正则匹配
    all_matches = list(compiled.finditer(text))

    # 筛选匹配文本完全相同的
    candidates = [m for m in all_matches if m.group(0) == match_text]

    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    # 多个候选，用 start_line 辅助定位最近的那个
    target_line = hit.get("start_line", 0)
    if target_line > 0:
        line_starts = _build_line_starts(text)
        return min(
            candidates,
            key=lambda m: abs(_line_no_from_offset(line_starts, m.start()) - target_line),
        )

    return candidates[0]


def _locate_chunk_positions(user_id: str, project_name: str, chunks: list[Any]) -> list[dict | None]:
    from story.project_files import collect_project_files

    project_files = collect_project_files(user_id, project_name)
    file_contents = {pf.rel_path: pf.content for pf in project_files}
    line_starts_map = {rel_path: _build_line_starts(content) for rel_path, content in file_contents.items()}
    locate_cursors: dict[str, int] = {}
    positions: list[dict | None] = []

    for chunk in chunks:
        source = str(chunk.metadata.get("source", "") or "")
        file_content = file_contents.get(source, "")
        if not source or not file_content or not chunk.text:
            positions.append(None)
            continue

        line_starts = line_starts_map.get(source, [0])
        approx_line_idx = min(max(chunk.start_line - 1, 0), max(len(line_starts) - 1, 0))
        approx_offset = line_starts[approx_line_idx] if line_starts else 0
        chunk_start = -1
        for candidate in (locate_cursors.get(source, 0), max(0, approx_offset - 2000), 0):
            chunk_start = file_content.find(chunk.text, candidate)
            if chunk_start >= 0:
                break

        if chunk_start < 0:
            positions.append(None)
            continue

        locate_cursors[source] = chunk_start + 1
        positions.append(
            {
                "source": source,
                "content": file_content,
                "line_starts": line_starts,
                "chunk_start": chunk_start,
                "chunk_end": chunk_start + len(chunk.text),
            }
        )

    return positions


@tool(args_schema=SearchProjectInput)
def search_project(pattern: str, case_sensitive: bool = False) -> str:
    """按正则搜索项目文本。"""
    user_id = current_user_id.get()
    project_name = get_current_project_name()
    if not user_id or not project_name:
        return "错误：缺少用户或项目上下文。"

    try:
        flags = _regex_flags(case_sensitive)
        compiled = re.compile(pattern, flags)
    except re.error as e:
        return f"正则表达式语法错误：{e}"

    from story.project_files import build_narrative_ref, collect_project_files, load_outline_data

    project_files = collect_project_files(user_id, project_name, max_source_chars=1_000_000_000)
    outline_data = load_outline_data(user_id, project_name)
    project_path = get_project_path(user_id, project_name)

    results: list[dict] = []
    for project_file in project_files:
        rel_path = project_file.rel_path
        try:
            with open(project_file.abs_path, "r", encoding="utf-8", errors="ignore") as f:
                file_text = f.read()
        except Exception:
            file_text = project_file.content or ""
        if not file_text:
            continue

        line_starts = _build_line_starts(file_text)
        narrative_ref = build_narrative_ref(rel_path, project_file.format_key, outline_data)
        for match in compiled.finditer(file_text):
            if match.start() == match.end():
                continue
            exact_start_line = _line_no_from_offset(line_starts, match.start())
            exact_end_line = _line_no_from_offset(line_starts, max(match.end() - 1, match.start()))
            context = _build_match_context(file_text, match.start(), match.end())
            results.append(
                {
                    "index": len(results),
                    "file_path": project_file.abs_path or (os.path.join(project_path, rel_path) if rel_path else ""),
                    "rel_path": rel_path,
                    "format_key": project_file.format_key,
                    "start_line": exact_start_line,
                    "end_line": exact_end_line,
                    "narrative_ref": narrative_ref,
                    "match_text": match.group(0),
                    "context": context,
                    "score": 1.0,
                    "chunk_text": match.group(0),
                    "pattern": pattern,
                    "case_sensitive": case_sensitive,
                    "file_span_start": match.start(),
                    "file_span_end": match.end(),
                }
            )

    # 去重：相同文件、相同字节位置的重复命中（来自重叠分块）只保留第一条
    # 重叠分块（RecursiveCharacterTextSplitter chunk_overlap=100）会导致落在
    # 重叠区的匹配在相邻两个 sub-chunk 中各被 finditer 一次，产生位置完全
    # 相同的两条结果。替换时第一条成功，第二条因文本已变化而失败。
    seen_pos: set[tuple[str, int, int]] = set()
    deduped: list[dict] = []
    for r in results:
        fss = r["file_span_start"]
        fse = r["file_span_end"]
        if fss is not None and fse is not None:
            pos_key = (r["rel_path"], int(fss), int(fse))
            if pos_key in seen_pos:
                continue
            seen_pos.add(pos_key)
        r["index"] = len(deduped)
        deduped.append(r)
    results = deduped

    _store_search_results(results)

    if not results:
        return f"正则搜索 \"{pattern}\" 未找到匹配。"

    lines = [f"正则搜索 \"{pattern}\" 找到 {len(results)} 处匹配：\n"]
    for r in results:
        loc = f"{r['rel_path']}:{r['start_line']}"
        lines.append(f"[{r['index']}] {r['narrative_ref']} ({loc})")
        lines.append(f"  {r['context']}")
        lines.append("")

    return "\n".join(lines)


@tool(args_schema=SemanticSearchInput)
def semantic_search(query: str, scope: list[str] | None = None, k: int = 8) -> str:
    """按语义搜索项目文本。"""
    user_id = current_user_id.get()
    project_name = get_current_project_name()
    if not user_id or not project_name:
        return "错误：缺少用户或项目上下文。"

    from core.project_settings import is_semantic_search_enabled

    if not is_semantic_search_enabled(user_id, project_name):
        return (
            "语义搜索未启用。"
            "请引导用户前往「设置 → 语义检索」中开启此功能，"
            "并确保已在「设置 → AI管理」中配置了可用的 Embedding 模型。"
        )

    try:
        from llm.agen_matchbox import matchbox

        matchbox().get_user_embedding(user_id)
    except ValueError as e:
        error_msg = str(e)
        if "未找到可用的 Embedding" in error_msg:
            return (
                "语义搜索失败：嵌入模型不可用。"
                "请引导用户前往「设置 → AI管理」中配置并选择一个可用的 Embedding 模型。"
            )
        return f"语义搜索失败：嵌入模型配置异常（{error_msg}）。请引导用户检查 Embedding 模型配置。"
    except Exception as e:
        return f"语义搜索失败：嵌入模型初始化异常（{e}）。请引导用户检查 Embedding 模型配置。"

    from agents.vector_index import VectorIndexService
    from agents.vector_index.service import IndexBuildNotReadyError

    service = VectorIndexService(user_id, project_name)
    service_status = service.get_status()
    build_state = service_status.get("build_state", {})
    if service_status.get("needs_rebuild") and build_state.get("status") not in {"queued", "building"}:
        service.start_background_build(force_rebuild=False)

    chroma_filter = None
    if scope:
        if len(scope) == 1:
            chroma_filter = {"format_key": scope[0]}
        else:
            chroma_filter = {"format_key": {"$in": scope}}

    try:
        hits = service.query(query, k=k, filter=chroma_filter)
    except IndexBuildNotReadyError as e:
        build_state = (e.status_payload or {}).get("build_state", {})
        progress = build_state.get("progress", {})
        fallback = search_project(re.escape(query), case_sensitive=False)
        progress_text = ""
        total_chunks = int(progress.get("total_chunks", 0) or 0)
        embedded_chunks = int(progress.get("embedded_chunks", 0) or 0)
        if total_chunks > 0:
            progress_text = f"当前进度：{embedded_chunks}/{total_chunks} 个分块。"
        return (
            "语义索引尚未就绪，已在后台启动首次构建。"
            f"{progress_text}"
            "先返回基于关键词的降级搜索结果：\n\n"
            f"{fallback}"
        )
    except FileNotFoundError as e:
        return f"项目不存在：{e}"
    except Exception as e:
        error_msg = str(e)
        if "未找到可用的 Embedding" in error_msg or "未配置 API Key" in error_msg:
            return (
                "语义搜索失败：嵌入模型不可用。"
                "请引导用户前往「设置 → AI管理」中检查 Embedding 模型及 API Key 配置。"
            )
        return f"语义搜索失败：{error_msg}。如果嵌入模型配置有误，请引导用户检查「设置 → AI管理」中的 Embedding 配置。"

    results: list[dict] = []
    for hit in hits:
        results.append(
            {
                "index": len(results),
                "file_path": hit.file_path,
                "rel_path": hit.rel_path,
                "format_key": hit.format_key,
                "start_line": hit.start_line,
                "end_line": hit.end_line,
                "narrative_ref": hit.narrative_ref,
                "match_text": hit.match_text[:200],
                "context": hit.match_text[:200],
                "score": hit.score,
                "chunk_text": hit.match_text,
                "pattern": None,
            }
        )

    _store_search_results(results)

    if not results:
        return f"语义搜索 \"{query}\" 未找到相关内容。"

    lines = [f"语义搜索 \"{query}\" 找到 {len(results)} 处相关内容：\n"]
    for r in results:
        loc = f"{r['rel_path']}:{r['start_line']}"
        score_str = f"相似度: {r['score']:.2f}" if r['score'] > 0 else ""
        lines.append(f"[{r['index']}] {r['narrative_ref']} ({loc}) {score_str}")
        preview = r['context'][:150]
        if len(r['context']) > 150:
            preview += "..."
        lines.append(f"  {preview}")
        lines.append("")

    return "\n".join(lines)


@tool(args_schema=ReplaceFromSearchInput)
def replace_from_search(indices: list[int], replacement: str) -> str:
    """基于上次搜索结果执行替换。"""
    user_id = current_user_id.get()
    project_name = get_current_project_name()
    if not user_id or not project_name:
        return "错误：缺少用户或项目上下文。"

    cached = _get_search_results()
    if not cached:
        return "错误：没有上次的搜索结果。请先执行 search_project 或 semantic_search。"

    project_path = get_project_path(user_id, project_name)
    success_count = 0
    fail_count = 0
    reports: list[str] = []
    regex_hits_by_file: dict[str, list[tuple[int, dict]]] = {}

    for idx in indices:
        if idx < 0 or idx >= len(cached):
            reports.append(f"[{idx}] 序号越界，跳过")
            fail_count += 1
            continue
        hit = cached[idx]
        pattern = hit.get("pattern")
        rel_path = hit.get("rel_path", "")
        if pattern and rel_path:
            regex_hits_by_file.setdefault(rel_path, []).append((idx, hit))

    processed_regex_indices: set[int] = set()
    for rel_path, hit_items in regex_hits_by_file.items():
        file_path = os.path.join(project_path, rel_path)
        if not os.path.isfile(file_path):
            for idx, _ in hit_items:
                reports.append(f"[{idx}] 文件不存在: {rel_path}")
                fail_count += 1
                processed_regex_indices.add(idx)
            continue

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                original = f.read()

            working = original
            local_success: list[tuple[int, dict]] = []
            local_failures: list[tuple[int, str]] = []

            for idx, hit in sorted(hit_items, key=lambda item: int(item[1].get("file_span_start") or -1), reverse=True):
                processed_regex_indices.add(idx)
                pattern = str(hit.get("pattern") or "")
                if not pattern:
                    local_failures.append((idx, f"缺少正则模式: {rel_path}"))
                    continue
                span_start = hit.get("file_span_start")
                span_end = hit.get("file_span_end")

                flags = _regex_flags(bool(hit.get("case_sensitive")))
                compiled = re.compile(pattern, flags)

                if isinstance(span_start, int) and isinstance(span_end, int) and span_start >= 0 and span_end >= span_start:
                    # 精确位置可用，在指定范围内搜索
                    match = compiled.search(working, pos=span_start, endpos=span_end)
                else:
                    # 文件位置不可用（chunk 文本经过策略转换：JSON 重序列化、
                    # conception 移除等），降级为全文 match_text 定位
                    match = _fallback_locate_match(working, compiled, hit)

                if not match:
                    local_failures.append((idx, f"替换未生效（命中已变化）: {rel_path}"))
                    continue

                replaced_text = match.expand(replacement)
                working = working[: match.start()] + replaced_text + working[match.end() :]
                local_success.append((idx, hit))

            if working != original:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(working)

            for idx, hit in sorted(local_success, key=lambda item: item[0]):
                reports.append(f"[{idx}] 已替换: {hit.get('narrative_ref', rel_path)}")
                success_count += 1
            for idx, reason in sorted(local_failures, key=lambda item: item[0]):
                reports.append(f"[{idx}] {reason}")
                fail_count += 1
        except Exception as e:
            for idx, _ in hit_items:
                if idx in processed_regex_indices:
                    continue
                processed_regex_indices.add(idx)
                reports.append(f"[{idx}] 替换失败: {e}")
                fail_count += 1

    for idx in indices:
        if idx < 0 or idx >= len(cached):
            continue
        if idx in processed_regex_indices:
            continue

        hit = cached[idx]
        rel_path = hit.get("rel_path", "")
        file_path = os.path.join(project_path, rel_path)

        if not os.path.isfile(file_path):
            reports.append(f"[{idx}] 文件不存在: {rel_path}")
            fail_count += 1
            continue

        try:
            chunk_text = hit.get("chunk_text", "")
            result = _apply_patch(
                file_path,
                chunk_text[:500],
                replacement,
                file_label=rel_path,
            )
            if result.startswith("局部修改失败"):
                reports.append(f"[{idx}] {result}")
                fail_count += 1
                continue
            reports.append(f"[{idx}] 已替换: {hit.get('narrative_ref', rel_path)}")
            success_count += 1
        except Exception as e:
            reports.append(f"[{idx}] 替换失败: {e}")
            fail_count += 1

    summary = f"替换完成：成功 {success_count} 处，失败 {fail_count} 处。"
    return summary + "\n" + "\n".join(reports)
