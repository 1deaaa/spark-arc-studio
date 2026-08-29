"""
统一风格分析器(Markdown 版)

串行分析文本块:
1. 每块输出 5 个维度的 Markdown 段落 + `## 上下文摘要`(给下一块)
2. 最后一块输出完整的风格档案 Markdown(含「风格执行卡」)

生产链路由 ``stream_save_style_profile`` 逐块调用 ``analyze_chunk``,
进度以 SSE 事件流式输出。

设计变更(2026-06):
- 抛弃 JSON 输出,改用 Markdown 标题结构作为解析锚点
- analysis 字段从 Dict 变为 str(markdown 字符串)
- 单块解析依据 `## 上下文摘要` 作为切分点
- 最终汇总直接产出一段完整 Markdown,可被下游 system prompt 直接拼接
"""

import re
import yaml
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from .text_splitter import TextChunk
from .utils import get_style_llm


# 用于切分单块输出中"## 上下文摘要"之前(风格分析)与之后(剧情摘要)
_CONTEXT_SUMMARY_HEADING = re.compile(
    r'^\s*#{1,3}\s*上下文摘要\s*$',
    re.MULTILINE,
)


@dataclass
class ChunkAnalysisResult:
    """单块分析结果

    analysis:           本块的风格分析 Markdown 段落(不含上下文摘要)
                        最后一块时,这里是完整的风格档案 Markdown
    context_summary:    本块剧情概括,仅用于传给下一块
    """
    chunk_index: int
    total_chunks: int
    analysis: str
    context_summary: str
    success: bool
    error: Optional[str] = None


class UnifiedStyleAnalyzer:
    """
    统一风格分析器(Markdown 输出)

    串行分析文本块,每块输出:
    - 5 个维度的 Markdown 风格分析
    - `## 上下文摘要` 段落(传递给下一块)

    最后一块汇总所有分析结果,输出完整风格档案 + 风格执行卡。
    """

    def __init__(self, user_id: str = None):
        """
        初始化分析器

        Args:
            user_id: 用户 ID,用于获取绑定的 LLM
        """
        self.user_id = user_id
        self.llm = get_style_llm(user_id)
        self._config = None

    def _load_config(self) -> dict:
        if self._config is not None:
            return self._config

        config_path = Path(__file__).resolve().parent / "prompts" / "style_analysis.yaml"
        if not config_path.exists():
            self._config = {}
            return self._config

        with open(config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)
        return self._config

    def _get_prompt_pair(self, section_name: str) -> tuple[str, str]:
        """读取稳定 system 与动态 user；兼容旧版单 prompt 配置。"""
        config = self._load_config()
        section = config.get(section_name, {})
        if not isinstance(section, dict):
            raise ValueError(f"style_analysis.yaml 的 {section_name} 配置无效")

        system_prompt = str(section.get("system") or "").strip()
        user_prompt = str(section.get("user") or "").strip()
        if system_prompt and user_prompt:
            return system_prompt, user_prompt

        legacy_prompt = str(section.get("prompt") or "").strip()
        if legacy_prompt:
            return "", legacy_prompt
        raise ValueError(
            f"style_analysis.yaml 缺少 {section_name}.system/.user 配置"
        )

    def _get_unified_prompts(self) -> tuple[str, str]:
        return self._get_prompt_pair("unified_analysis")

    def _get_final_synthesis_prompts(self) -> tuple[str, str]:
        return self._get_prompt_pair("final_synthesis")

    def analyze_chunk(
        self,
        chunk: TextChunk,
        previous_context: Optional[str] = None,
        accumulated_analyses: Optional[List[str]] = None,
    ) -> ChunkAnalysisResult:
        """
        分析单个文本块

        Args:
            chunk: 文本块
            previous_context: 上一块的剧情概括
            accumulated_analyses: 之前所有块的分析 Markdown 列表

        Returns:
            ChunkAnalysisResult 包含 markdown 分析与上下文摘要
        """
        try:
            is_last = chunk.index == chunk.total - 1

            context_info = ""
            if previous_context:
                context_info += f"【前文概括】\n{previous_context}\n\n"
            if chunk.previous_tail:
                context_info += f"【上一段末尾】\n...{chunk.previous_tail}\n\n"

            if is_last and chunk.total > 1:
                messages = self._build_final_messages(
                    chunk.text,
                    context_info,
                    accumulated_analyses or [],
                )
            else:
                messages = self._build_chunk_messages(
                    chunk.text,
                    context_info,
                    chunk.index + 1,
                    chunk.total,
                )

            print(f"  📝 Analyzing chunk {chunk.index + 1}/{chunk.total} ({chunk.estimated_tokens} tokens)...")
            response = self.llm.invoke(messages)
            raw_content = (response.content or "").strip()

            if is_last and chunk.total > 1:
                # 最终汇总:整段都是风格档案,不再有"## 上下文摘要"
                analysis_md = self._strip_code_fence(raw_content)
                context_summary = ""
            else:
                # 单块:切分风格分析与上下文摘要
                analysis_md, context_summary = self._split_chunk_output(raw_content)

            print(f"  ✓ chunk {chunk.index + 1}/{chunk.total} analysis complete")

            return ChunkAnalysisResult(
                chunk_index=chunk.index,
                total_chunks=chunk.total,
                analysis=analysis_md,
                context_summary=context_summary,
                success=True,
            )

        except Exception as e:
            print(f"  ✗ chunk {chunk.index + 1}/{chunk.total} analysis failed: {e}")
            return ChunkAnalysisResult(
                chunk_index=chunk.index,
                total_chunks=chunk.total,
                analysis="",
                context_summary="",
                success=False,
                error=str(e),
            )

    @staticmethod
    def _build_messages(system_prompt: str, user_prompt: str) -> List[BaseMessage]:
        """构造稳定 system + 动态 user 的消息序列。"""
        messages: List[BaseMessage] = []
        if system_prompt.strip():
            messages.append(SystemMessage(content=system_prompt.strip()))
        messages.append(HumanMessage(content=user_prompt.strip()))
        return messages

    def _build_chunk_messages(
        self,
        text: str,
        context_info: str,
        current: int,
        total: int,
    ) -> List[BaseMessage]:
        system_prompt, user_template = self._get_unified_prompts()
        user_prompt = user_template.format(
            context=context_info,
            text=text,
            current=current,
            total=total,
        )
        return self._build_messages(system_prompt, user_prompt)

    def _build_final_messages(
        self,
        text: str,
        context_info: str,
        accumulated_analyses: List[str],
    ) -> List[BaseMessage]:
        system_prompt, user_template = self._get_final_synthesis_prompts()

        prev_analyses_text = ""
        if accumulated_analyses:
            for i, analysis_md in enumerate(accumulated_analyses):
                prev_analyses_text += f"\n--- 第 {i+1} 块分析摘要 ---\n"
                # 单块限制 2000 字,避免 final prompt 过长
                snippet = (analysis_md or "")[:2000]
                prev_analyses_text += snippet + "\n"

        user_prompt = user_template.format(
            context=context_info,
            text=text,
            previous_analyses=prev_analyses_text,
            context_summaries="",
        )
        return self._build_messages(system_prompt, user_prompt)

    @staticmethod
    def _split_chunk_output(raw: str) -> tuple[str, str]:
        """按 `## 上下文摘要` 切分单块输出。

        Returns:
            (analysis_markdown, context_summary)
        """
        cleaned = UnifiedStyleAnalyzer._strip_code_fence(raw)
        match = _CONTEXT_SUMMARY_HEADING.search(cleaned)
        if not match:
            # 容错:LLM 未按格式产出摘要,把全部内容当作风格分析
            return cleaned.strip(), ""
        analysis = cleaned[: match.start()].rstrip()
        summary = cleaned[match.end():].strip()
        return analysis, summary

    @staticmethod
    def _strip_code_fence(text: str) -> str:
        """剥离 LLM 偶尔包裹的 ```markdown / ``` 围栏。"""
        if not text:
            return ""
        stripped = text.strip()
        # 三反引号开头(可能带语言标识)
        if stripped.startswith("```"):
            first_newline = stripped.find("\n")
            if first_newline != -1:
                stripped = stripped[first_newline + 1:]
            if stripped.endswith("```"):
                stripped = stripped[: -3]
        return stripped.strip()
