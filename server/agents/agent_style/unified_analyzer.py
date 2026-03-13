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
        return '''你是专业的文学风格分析师。请分析以下文本片段（第{current}/{total}部分），提取作者的行文习惯与风格底色。

{context}

【待分析文本】
{text}

请输出JSON格式：
{{
  "style_analysis": {{
    "sentence_texture": {{
      "rhythm_and_length": "句子呼吸感（长短句交错规律/单句长度/是否存在频繁的断句或连长句）",
      "syntactic_structure": "句法惯性（偏好倒装句/排比铺陈/繁复的修饰语/主谓宾极简直白）",
      "vocabulary_temperature": "词汇温度（偏向冷硬书面语/日常大白话/古典雅致/粗俗生动）",
      "sensory_preference": "感官调用偏好（写作时第一本能是描绘视觉的光影、听觉的嘈杂、还是通感的比喻）"
    }},
    "dialogue_mechanics": {{
      "exchange_pace": "交锋节奏（一问一答的快节奏乒乓球式/大段演讲式/答非所问的错位感）",
      "speech_tags_habit": "对话标签习惯（是否省略'说'字/偏好用大量环境动作代替'某某说'/语气词的使用密度）",
      "subtext_density": "潜台词密度（角色是直抒胸臆还是习惯性阴阳怪气/顾左右而言他）"
    }},
    "narrative_camera": {{
      "focus_distance": "叙事镜头距离（是贴着人物头皮的内耗式视角/还是冷眼旁观的上帝视角/像电影镜头般注重物理站位）",
      "scene_transition": "场景与时间剪辑（怎样跳过无聊的时间段/偏好生硬切分还是用某个物件平滑过渡）",
      "detail_magnification": "细节放大镜（最爱花笔墨描绘什么：是人物脸上的微表情、房间里的灰尘、还是心理活动的百转千回）"
    }},
    "emotional_palette": {{
      "base_tone": "行文底色调（文字天然带着忧郁/神经质的欢脱/沉滞的压抑/轻盈的虚无感）",
      "tension_building": "张力构建法（如何把一个平淡的场景写得令人窒息/靠沉默还是靠语言的冲突）",
      "climax_processing": "情绪爆发点（高潮时是爆发式的大段咆哮/还是极致的留白与突然的平静）"
    }}
  }}
}}

注意：
1. 你现在的目标是提取“作者的底色与习惯”，也就是：如果这位作者明天去写一篇与当前文章【题材完全无关、剧情完全不同】的新作品，他依然会保留的那些“行文习惯”。
2. 🚨 【终极红线】：**绝对禁止**你的 JSON 产物中出现任何本篇小说的具体名词（人名、特有设定名、书籍名、招式名等），以及剧透任何具体的发生了什么事。如果他用“吃掉胰脏”比喻深爱，你提取的必须是“惯用带有生理不适感的生化词汇来进行极端的情感反差比喻”。
3. 如果某个维度在当前片段中不明显，可以直接填"无显著特征"。'''
    
    def _default_final_prompt(self) -> str:
        """默认的最终汇总提示词"""
        return '''你是专业的文学风格分析师。现在你已经分析了这位作者作品的所有片段，请基于：
1. 之前各片段的分析结果
2. 最后一个片段的内容

汇总输出这位作者的**完整风格档案**。

{context}

【最后一段文本】
{text}

【之前的分析结果】
{previous_analyses}

请输出最终的风格档案JSON：
{{
  "sentence_texture": {{
    "rhythm_and_length": "...",
    "syntactic_structure": "...",
    "vocabulary_temperature": "...",
    "sensory_preference": "..."
  }},
  "dialogue_mechanics": {{
    "exchange_pace": "...",
    "speech_tags_habit": "...",
    "subtext_density": "..."
  }},
  "narrative_camera": {{
    "focus_distance": "...",
    "scene_transition": "...",
    "detail_magnification": "..."
  }},
  "emotional_palette": {{
    "base_tone": "...",
    "tension_building": "...",
    "climax_processing": "..."
  }},
  "coordinator": {{
    "mimic_instruction": "给大模型的最高指令（如果下一个AI要模仿这位作者写一篇【全新设定】的网文，请给它写一段最核心的 Prompt 指引，强调它必须坚持的文风底线，用祈使句）",
    "distinctive_summary": "作者画像（用3-5句话描述这位作家的气质：是喋喋不休的神经质、是冷酷剥骨的旁观者、还是词藻华丽的浪漫诗人）",
    "negative_constraints": ["绝对不能出现的写法"]
  }}
}}

注意：
1. 这是最终档案，它【只是一份写作手法的说明书】，就像一个作家的DNA测序报告。
2. 🚨 【脱水警告】：再次扫描，确保没有残留任何上文的具体剧情词汇！一切具体的人、事、物都必须已经被粉碎并抽象为了“句子”、“修辞”、“口癖”、“视角”。'''
    
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
