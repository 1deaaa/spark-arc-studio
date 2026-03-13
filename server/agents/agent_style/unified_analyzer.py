"""
统一风格分析器

取代原有的7个并行Agent，改为串行分析文本块：
1. 每块输出七个维度的分析结果
2. 每块结尾附带简要上下文摘要传递给下一块
3. 最后一块输出完整的风格档案
"""

import json
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from .text_splitter import TextChunk
from .utils import get_style_llm, extract_json_from_response


@dataclass
class ChunkAnalysisResult:
    """单块分析结果"""
    chunk_index: int
    total_chunks: int
    analysis: Dict[str, Any]  # 七维度分析
    context_summary: str       # 剧情概括（给下一块）
    success: bool
    error: Optional[str] = None


class UnifiedStyleAnalyzer:
    """
    统一风格分析器
    
    串行分析文本块，每块输出：
    - 七个维度的风格分析
    - 简要剧情概括（传递给下一块）
    
    最后一块汇总所有分析结果，输出完整风格档案。
    """
    
    def __init__(self, user_id: str = None):
        """
        初始化分析器
        
        Args:
            user_id: 用户ID，用于获取绑定的LLM
        """
        self.user_id = user_id
        self.llm = get_style_llm(user_id)
        self._config = None
    
    def _load_config(self) -> Dict:
        """加载配置"""
        if self._config is not None:
            return self._config
        
        config_path = Path(__file__).resolve().parent / "prompts" / "style_analysis.yaml"
        if not config_path.exists():
            self._config = {}
            return self._config
        
        with open(config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)
        return self._config
    
    def _get_unified_prompt(self) -> str:
        """获取统一分析提示词"""
        config = self._load_config()
        prompt = config.get("unified_analysis", {}).get("prompt", "")
        if not prompt:
            raise ValueError("style_analysis.yaml 缺少 unified_analysis.prompt 配置")
        return prompt
    
    def _get_final_synthesis_prompt(self) -> str:
        """获取最终汇总提示词"""
        config = self._load_config()
        prompt = config.get("final_synthesis", {}).get("prompt", "")
        if not prompt:
            raise ValueError("style_analysis.yaml 缺少 final_synthesis.prompt 配置")
        return prompt

    def _get_common_schema(self) -> str:
        """获取通用JSON Schema"""
        config = self._load_config()
        schema = config.get("common_style_schema", "")
        if not schema:
            raise ValueError("style_analysis.yaml 缺少 common_style_schema 配置")
        return schema
    
    def analyze_chunk(
        self,
        chunk: TextChunk,
        previous_context: Optional[str] = None,
        accumulated_analyses: Optional[List[Dict]] = None
    ) -> ChunkAnalysisResult:
        """
        分析单个文本块
        
        Args:
            chunk: 文本块
            previous_context: 上一块的剧情概括
            accumulated_analyses: 之前所有块的分析结果列表
            
        Returns:
            ChunkAnalysisResult 包含分析和上下文
        """
        try:
            is_last = chunk.index == chunk.total - 1
            
            # 构建上下文信息
            context_info = ""
            if previous_context:
                context_info += f"【前文概括】\n{previous_context}\n\n"
            if chunk.previous_tail:
                context_info += f"【上一段末尾】\n...{chunk.previous_tail}\n\n"
            
            # 选择提示词
            if is_last and chunk.total > 1:
                # 最后一块：需要汇总所有分析
                prompt = self._build_final_prompt(
                    chunk.text, 
                    context_info,
                    accumulated_analyses or []
                )
            else:
                # 普通块
                prompt = self._build_chunk_prompt(
                    chunk.text,
                    context_info,
                    chunk.index + 1,
                    chunk.total
                )
            
            # 调用LLM
            print(f"  📝 分析第 {chunk.index + 1}/{chunk.total} 块 ({chunk.estimated_tokens} tokens)...")
            response = self.llm.invoke(prompt)
            content = extract_json_from_response(response.content)
            result = json.loads(content)
            
            # 提取分析和上下文
            analysis = result.get("style_analysis", result)
            context_summary = result.get("context_summary", "")
            
            print(f"  ✓ 第 {chunk.index + 1}/{chunk.total} 块分析完成")
            
            return ChunkAnalysisResult(
                chunk_index=chunk.index,
                total_chunks=chunk.total,
                analysis=analysis,
                context_summary=context_summary,
                success=True
            )
            
        except Exception as e:
            print(f"  ✗ 第 {chunk.index + 1}/{chunk.total} 块分析失败: {e}")
            return ChunkAnalysisResult(
                chunk_index=chunk.index,
                total_chunks=chunk.total,
                analysis={},
                context_summary="",
                success=False,
                error=str(e)
            )
    
    def _build_chunk_prompt(
        self,
        text: str,
        context_info: str,
        current: int,
        total: int
    ) -> str:
        """构建单块分析提示词"""
        prompt_template = self._get_unified_prompt()
        
        return prompt_template.format(
            context=context_info,
            text=text,
            current=current,
            total=total,
            json_schema=self._get_common_schema()
        )
    
    def _build_final_prompt(
        self,
        text: str,
        context_info: str,
        accumulated_analyses: List[Dict]
    ) -> str:
        """构建最终汇总提示词"""
        prompt_template = self._get_final_synthesis_prompt()
        
        # 格式化之前的分析结果
        prev_analyses_text = ""
        if accumulated_analyses:
            for i, analysis in enumerate(accumulated_analyses):
                prev_analyses_text += f"\n--- 第{i+1}块分析摘要 ---\n"
                prev_analyses_text += json.dumps(analysis, ensure_ascii=False, indent=2)[:2000]  # 限制长度
                prev_analyses_text += "\n"
        
        # 累积的剧情概括
        context_summaries = ""
        
        return prompt_template.format(
            context=context_info,
            text=text,
            previous_analyses=prev_analyses_text,
            context_summaries=context_summaries,
            json_schema=self._get_common_schema()
        )
    
    def analyze_full_text(
        self,
        chunks: List[TextChunk]
    ) -> Tuple[Dict, List[ChunkAnalysisResult]]:
        """
        分析完整文本（所有块）
        
        Args:
            chunks: 切分后的文本块列表
            
        Returns:
            (final_profile, all_results)
        """
        if not chunks:
            return {}, []
        
        all_results: List[ChunkAnalysisResult] = []
        accumulated_analyses: List[Dict] = []
        previous_context = ""
        
        print(f"\n=== 开始串行风格分析 ===")
        print(f"共 {len(chunks)} 个文本块\n")
        
        for chunk in chunks:
            result = self.analyze_chunk(
                chunk,
                previous_context=previous_context,
                accumulated_analyses=accumulated_analyses
            )
            
            all_results.append(result)
            
            if result.success:
                accumulated_analyses.append(result.analysis)
                # 累积剧情概括
                if result.context_summary:
                    previous_context = (previous_context + "\n" + result.context_summary).strip()
                    # 控制长度，保留最近的概括
                    if len(previous_context) > 3000:
                        previous_context = previous_context[-3000:]
        
        # 获取最终档案（来自最后一块的分析）
        final_profile = {}
        if all_results and all_results[-1].success:
            final_profile = all_results[-1].analysis
        
        print(f"\n=== 风格分析完成 ===\n")
        
        return final_profile, all_results
