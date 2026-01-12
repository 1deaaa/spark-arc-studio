import json
from typing import Dict
from .base import StyleAnalysisAgent

class ValidatorAgent(StyleAnalysisAgent):
    """风格验证Agent：基于定性评级（而非定量打分）来验证和优化风格"""
    
    def __init__(self):
        super().__init__(
            name="ValidatorAgent",
            dimensions=["similarity_level", "refinement_suggestions"],
            config_key="validator"
        )
        
    def validate_and_refine(self, style_profile: Dict, test_text: str) -> Dict:
        print("\n[ValidatorAgent] 开始回测验证...")
        
        # 1. 提取原文大意
        summary_prompt = self.get_prompt(
            key="summary_prompt",
            text=test_text
        )
        if not summary_prompt:
            summary_prompt = f"请用一句话概括这段文字的大意：\n{test_text}"
            
        summary = self.llm.invoke(summary_prompt).content.strip()
        
        # 2. 尝试模仿
        profile_str = json.dumps(style_profile, ensure_ascii=False)[:2000]
        mimic_prompt = self.get_prompt(
            key="mimic_prompt",
            profile=profile_str,
            summary=summary
        )
        if not mimic_prompt:
            mimic_prompt = f"""
请扮演该作者，基于以下风格档案，将摘要扩写为一段文字。
风格档案：{profile_str}
摘要：{summary}
要求：极度贴合作者文风，不要出现AI味，捕捉文字的呼吸感。
"""
        mimic_text = self.llm.invoke(mimic_prompt).content.strip()
        
        # 3. 评级与修正 - 深度特征版
        grading_rubric = self.get_config().get("grading_rubric", "")
        
        eval_prompt = self.get_prompt(
            key="eval_prompt",
            grading_rubric=grading_rubric,
            test_text=test_text,
            mimic_text=mimic_text
        )
        
        if not eval_prompt:
            # 回退逻辑
            eval_prompt = f"""
你是文学风格鉴赏家与数据分析师。请基于【评级标准】对模仿文进行严格的图灵测试。
...
"""
        
        response = self.llm.invoke(eval_prompt)
        content = response.content.strip().replace("```json", "").replace("```", "")
        
        try:
            response = content # alias for backward compatibility in error handling
            eval_result = json.loads(response)
            level = eval_result["similarity_level"].upper() # 确保大写
            print(f"  📊 模仿相似度评级: 【{level}】")
            print(f"  📝 评级理由: {eval_result.get('reason', '无')}")
            
            # 定义需要修正的阈值，比如 B, C, D 级都需要修正
            # 作为独立游戏开发者，你肯定熟悉这种 Tier 设计
            needs_refinement_tiers = ["B", "C", "D", "E", "F"] 
            
            if level in needs_refinement_tiers:
                suggestion = eval_result['refinement_suggestions']
                print(f"  ⚠ 评级未达标 (目标 S/A)，正在注入修正建议: {suggestion}")
                
                # 注入修正建议
                if "_meta" not in style_profile: style_profile["_meta"] = {}
                if "validator_feedback" not in style_profile["_meta"]: style_profile["_meta"]["validator_feedback"] = []
                
                # 记录建议和来源等级，方便后续权重分析
                style_profile["_meta"]["validator_feedback"].append({
                    "level_triggered": level,
                    "suggestion": suggestion
                })
                
            return style_profile
        except Exception as e:
            print(f"  ⚠ 验证解析失败: {e}")
            # 打印原始返回以便调试
            print(f"  原始返回: {response}")
            return style_profile
