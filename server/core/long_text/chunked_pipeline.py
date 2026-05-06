"""
ChunkedLongTextPipeline
=======================

通用长文本"分块串行 + 末尾聚合"管线。

机制（与 UnifiedStyleAnalyzer 完全一致）：
1. 对每个 chunk 调 LLM，产出 (output, context_hint)
2. context_hint 滚动追加，限长 ``context_max_chars`` 字符
3. 若 chunk.total > 1，最后一块额外用 final_prompt 聚合前面所有 output
4. 返回：``PipelineResult(final_output, chunk_results[])``

调用方通过回调注入业务语义：
- ``build_chunk_prompt(chunk, context_info, current, total) -> str``
- ``parse_chunk_output(response_text) -> tuple[output_dict, context_hint_str]``
- ``build_final_prompt(chunk, context_info, accumulated_outputs) -> str``  (可选)
- ``parse_final_output(response_text) -> output_dict``  (可选，默认复用 parse_chunk_output)
- ``on_chunk_start / on_chunk_finish``：进度回调（可选）
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from core.file_ingest.chunking import TokenChunk


# ==================== 数据类 ====================

@dataclass
class ChunkRunResult:
    """单块运行结果"""
    chunk_index: int
    total_chunks: int
    output: dict
    context_hint: str
    success: bool
    error: Optional[str] = None


@dataclass
class PipelineResult:
    """管线最终结果"""
    final_output: dict
    chunk_results: list[ChunkRunResult]


# ==================== 回调签名 ====================

BuildChunkPrompt = Callable[[TokenChunk, str, int, int], str]
"""build_chunk_prompt(chunk, context_info, current_1based, total) -> str"""

ParseChunkOutput = Callable[[str], tuple[dict, str]]
"""parse_chunk_output(response_text) -> (output_dict, context_hint_str)"""

BuildFinalPrompt = Callable[[TokenChunk, str, list[dict]], str]
"""build_final_prompt(last_chunk, context_info, accumulated_outputs) -> str"""

ParseFinalOutput = Callable[[str], dict]
"""parse_final_output(response_text) -> output_dict"""

OnChunk = Callable[["ChunkRunResult"], None]


# ==================== 辅助 ====================

def _extract_text_from_response(response: Any) -> str:
    """从 LangChain LLM 响应中提取纯文本内容。兼容 str / AIMessage / content-list 形态。"""
    if response is None:
        return ""
    if isinstance(response, str):
        return response
    content = getattr(response, "content", None)
    if content is None:
        return str(response)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content") or ""
                if text:
                    parts.append(str(text))
        return "".join(parts)
    return str(content)


# ==================== 主类 ====================

class ChunkedLongTextPipeline:
    """分块串行 + 末尾聚合的通用管线。"""

    def __init__(
        self,
        llm,
        build_chunk_prompt: BuildChunkPrompt,
        parse_chunk_output: ParseChunkOutput,
        build_final_prompt: Optional[BuildFinalPrompt] = None,
        parse_final_output: Optional[ParseFinalOutput] = None,
        context_max_chars: int = 3000,
        on_chunk_start: Optional[Callable[[TokenChunk], None]] = None,
        on_chunk_finish: Optional[OnChunk] = None,
    ) -> None:
        self.llm = llm
        self.build_chunk_prompt = build_chunk_prompt
        self.parse_chunk_output = parse_chunk_output
        self.build_final_prompt = build_final_prompt
        self.parse_final_output = parse_final_output
        self.context_max_chars = max(0, int(context_max_chars))
        self.on_chunk_start = on_chunk_start
        self.on_chunk_finish = on_chunk_finish

    # ---------- 对外主入口 ----------

    def run(self, chunks: list[TokenChunk]) -> PipelineResult:
        """一次性跑完所有 chunks。"""
        if not chunks:
            return PipelineResult(final_output={}, chunk_results=[])

        results: list[ChunkRunResult] = []
        accumulated_outputs: list[dict] = []
        context_hint = ""

        for chunk in chunks:
            if self.on_chunk_start:
                try:
                    self.on_chunk_start(chunk)
                except Exception:
                    pass

            result = self._run_chunk(
                chunk=chunk,
                context_hint=context_hint,
                accumulated_outputs=accumulated_outputs,
            )
            results.append(result)

            if result.success:
                accumulated_outputs.append(result.output)
                if result.context_hint:
                    context_hint = (context_hint + "\n" + result.context_hint).strip()
                    if self.context_max_chars and len(context_hint) > self.context_max_chars:
                        context_hint = context_hint[-self.context_max_chars:]

            if self.on_chunk_finish:
                try:
                    self.on_chunk_finish(result)
                except Exception:
                    pass

        final_output: dict = {}
        if results and results[-1].success:
            final_output = results[-1].output

        return PipelineResult(final_output=final_output, chunk_results=results)

    # ---------- 内部 ----------

    def _run_chunk(
        self,
        chunk: TokenChunk,
        context_hint: str,
        accumulated_outputs: list[dict],
    ) -> ChunkRunResult:
        try:
            context_info = self._build_context_info(context_hint, chunk.previous_tail)

            is_last = chunk.index == chunk.total - 1
            use_final = (
                is_last
                and chunk.total > 1
                and self.build_final_prompt is not None
            )

            if use_final:
                prompt = self.build_final_prompt(chunk, context_info, accumulated_outputs)  # type: ignore[misc]
                response = self.llm.invoke(prompt)
                response_text = _extract_text_from_response(response)
                parser = self.parse_final_output or (lambda text: self.parse_chunk_output(text)[0])
                output = parser(response_text)
                context_hint_out = ""
            else:
                prompt = self.build_chunk_prompt(chunk, context_info, chunk.index + 1, chunk.total)
                response = self.llm.invoke(prompt)
                response_text = _extract_text_from_response(response)
                output, context_hint_out = self.parse_chunk_output(response_text)

            return ChunkRunResult(
                chunk_index=chunk.index,
                total_chunks=chunk.total,
                output=output if isinstance(output, dict) else {"value": output},
                context_hint=str(context_hint_out or ""),
                success=True,
            )

        except Exception as exc:
            return ChunkRunResult(
                chunk_index=chunk.index,
                total_chunks=chunk.total,
                output={},
                context_hint="",
                success=False,
                error=str(exc),
            )

    @staticmethod
    def _build_context_info(context_hint: str, previous_tail: str) -> str:
        parts: list[str] = []
        if context_hint:
            parts.append(f"【前文概括】\n{context_hint}")
        if previous_tail:
            parts.append(f"【上一段末尾】\n...{previous_tail}")
        return ("\n\n".join(parts) + "\n\n") if parts else ""
