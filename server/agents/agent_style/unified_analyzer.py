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
        return config.get("unified_analysis", {}).get("prompt", "")
    
    def _get_final_synthesis_prompt(self) -> str:
        """获取最终汇总提示词"""
        config = self._load_config()
        return config.get("final_synthesis", {}).get("prompt", "")

    def _get_common_schema(self) -> str:
        """获取通用JSON Schema"""
        config = self._load_config()
        return config.get("common_style_schema", "")
    
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
        
        if not prompt_template:
            # 使用默认模板
            prompt_template = self._default_unified_prompt()
        
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
        
        if not prompt_template:
            prompt_template = self._default_final_prompt()
        
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
    
    def _default_unified_prompt(self) -> str:
        """默认的统一分析提示词"""
        return '''你是专业的文学风格分析师。请分析以下文本片段（第{current}/{total}部分），从七个维度提取作者的风格特征。

{context}

【待分析文本】
{text}

请输出JSON格式：
{{
  "style_analysis": {{
    "dialogue": {{
      "rhythm": "对话节奏特点",
      "speech_pattern": "说话模式",
      "subtext": "潜台词技巧",
      "tags_style": "对话标签风格"
    }},
    "monologue": {{
      "thought_structure": "思维结构",
      "inner_voice": "内心声音色调",
      "memory_flashback": "记忆闪回方式"
    }},
    "narrative": {{
      "perspective": "叙述视角",
      "scene_construction": "场景构建",
      "detail_craftsmanship": "细节刻画"
    }},
    "character": {{
      "portrayal": "角色塑造方式",
      "plot_technique": "情节技巧"
    }},
    "language": {{
      "linguistic_texture": "语言质感",
      "rhetoric_devices": "修辞手法",
      "imagery_system": "意象系统"
    }},
    "structure": {{
      "rhythm_control": "节奏控制",
      "information_flow": "信息流动",
      "tension_mechanics": "张力机制"
    }},
    "emotion": {{
      "progression": "情感推进",
      "theme_tendency": "主题倾向",
      "subtext_layer": "潜台词层次"
    }}
  }},
  "context_summary": "用简要的语言概括这一段的主要剧情和重要信息，以便接续分析后文"
}}

注意：
1. 分析要具体、基于文本实际表现
2. context_summary 简要概括剧情要点即可
3. 如果某个维度在当前片段中不明显，可以标注"待后续片段补充"'''
    
    def _default_final_prompt(self) -> str:
        """默认的最终汇总提示词"""
        return '''你是专业的文学风格分析师。现在你已经分析了这位作者作品的所有片段，请基于：
1. 之前各片段的分析结果
2. 最后一个片段的内容
3. 累积的剧情概括

汇总输出这位作者的**完整风格档案**。

⚠️注意：你需要清洗掉风格档案中，具体的人名、详细设定、过于详细的情节，以避免克隆原作！

{context}

【最后一段文本】
{text}

【之前的分析结果】
{previous_analyses}

请输出最终的风格档案JSON：
{{
  "dialogue_system": {{
    "dialogue_rhythm": "对话节奏",
    "speech_pattern": "说话模式",
    "subtext_technique": "潜台词技巧",
    "silence_usage": "沉默运用",
    "dialogue_tags": "对话标签风格",
    "examples": ["典型对话片段"]
  }},
  "monologue_system": {{
    "thought_structure": "思维结构",
    "inner_voice_tone": "内心声音色调",
    "memory_flashback": "记忆闪回方式",
    "examples": ["典型独白片段"]
  }},
  "narrative_system": {{
    "perspective": "叙述视角",
    "scene_construction": "场景构建技巧",
    "detail_craftsmanship": "细节刻画",
    "temporal_architecture": "时间处理",
    "examples": ["典型叙事片段"]
  }},
  "character_plot": {{
    "character_portrayal": "角色塑造方式",
    "plot_technique": "情节技巧",
    "foreshadowing": "伏笔布置",
    "conflict_escalation": "冲突升级",
    "examples": ["典型片段"]
  }},
  "language_rhetoric": {{
    "linguistic_texture": "语言质感",
    "rhetoric_devices": "修辞手法库",
    "imagery_system": "核心意象群",
    "vocabulary_signature": "词汇指纹",
    "examples": ["典型语句", "高频词汇"]
  }},
  "structure_rhythm": {{
    "rhythm_control": "节奏控制",
    "information_flow": "信息流",
    "white_space_use": "留白艺术",
    "tension_mechanics": "张力机制"
  }},
  "emotion_theme": {{
    "emotional_progression": "情感推进方式",
    "theme_tendency": "主题倾向",
    "value_orientation": "价值取向",
    "subtext_layer": "潜台词层次"
  }},
  "signature_style": {{
    "core_features": ["最能代表作者的10-15个独特风格要素"],
    "innovation_points": ["独特创新之处"],
    "negative_constraints": ["作者绝对不会用的表达方式"],
    "distinctive_summary": "用3-5句话概括这位作者最与众不同的地方"
  }},
  "plot_summary": "整部作品的主要剧情概括"
}}

注意：
1. 这是最终档案，要全面、具体、可操作
2. 基于所有分析结果汇总，不要遗漏重要特征
3. negative_constraints 很重要，要明确标注作者"绝对不用"的表达'''
    
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
