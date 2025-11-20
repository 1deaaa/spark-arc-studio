import json
import time
from typing import List, Dict
from ..utils import llm, AgentAnalysisResult

class CoordinatorAgent:
    """协调Agent，整合各专业Agent的分析结果"""
    
    def __init__(self):
        self.llm = llm
    
    def integrate_results(self, results: List[AgentAnalysisResult]) -> Dict:
        """整合多个Agent的分析结果"""
        print("\n[CoordinatorAgent] 开始整合分析结果...")
        
        # 收集所有成功的分析
        successful_analyses = [r for r in results if r.success]
        
        if not successful_analyses:
            print("✗ 所有Agent均分析失败")
            return {}
        
        # 合并所有分析结果
        integrated = {
            "writing_style_analysis_framework": {},
            "_meta": {
                "framework_version": "3.0_multi_agent",
                "agents_used": [r.agent_name for r in successful_analyses],
                "analysis_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "applicable_genres": ["视觉小说", "游戏剧本", "互动叙事"],
                "usage_notes": [
                    "基于多Agent并行分析生成",
                    "每个维度由专业Agent独立分析",
                    "特别优化for视觉小说：对话+独白+旁白",
                    "避免AI通病：工业糖精/空降设定/情感快进"
                ]
            }
        }
        
        # 合并各Agent的分析
        for result in successful_analyses:
            integrated["writing_style_analysis_framework"].update(result.analysis)
            
        # 提取所有 negative_constraints
        all_constraints = []
        for r in successful_analyses:
            if isinstance(r.analysis, dict):
                for key, val in r.analysis.items():
                    if isinstance(val, dict) and "negative_constraints" in val:
                        all_constraints.extend(val["negative_constraints"])
        
        if all_constraints:
            integrated["writing_style_analysis_framework"]["global_negative_constraints"] = list(set(all_constraints))
        
        # 生成distinctive_features（总结性分析）
        print("\n[CoordinatorAgent] 生成总结性特征分析...")
        distinctive_features = self._synthesize_distinctive_features(results, integrated)
        if distinctive_features:
            integrated["writing_style_analysis_framework"]["distinctive_features"] = distinctive_features
        
        print(f"✓ 整合完成，包含 {len(successful_analyses)}/{len(results)} 个Agent的分析")
        
        return integrated
    
    def _synthesize_distinctive_features(self, results: List[AgentAnalysisResult], integrated_data: Dict) -> Dict:
        """基于所有Agent结果，综合生成作者的独特特征分析"""
        try:
            # 收集所有成功分析的examples
            all_examples = []
            for result in results:
                if result.success and result.examples:
                    all_examples.extend(result.examples[:3])  # 每个Agent取3个例子
            
            if not all_examples:
                return None
            
            # 构造综合分析prompt
            prompt = f"""
你是文学风格元分析专家。现在给你一份已经完成的多维度风格分析结果，请基于这些分析，提炼出作者最核心、最独特的风格特征。

【已完成的分析维度】
{json.dumps(integrated_data['writing_style_analysis_framework'], ensure_ascii=False, indent=2)[:3000]}
...(部分省略)

【代表性文本片段】
{chr(10).join([f"{i+1}. {ex[:150]}..." for i, ex in enumerate(all_examples[:15])])}

请从以下维度进行元分析，输出JSON格式：
{{
  "signature_style": "标志性特征（最能代表作者的10-15个独特风格要素：如特定句式癖好/偏爱意象/叙事习惯/语言标记等）",
  "influence_trace": "风格来源（如：可能受某流派/作家影响的痕迹/致敬/化用/反叛等，基于分析推测）",
  "innovation_point": "创新之处（如：独特的表达方式/新颖的结构尝试/突破性元素/实验性手法等）",
  "style_coherence": "风格一致性（如：各维度之间的协调度/是否形成统一风格/风格冲突点等）",
  "adaptability": "适应性分析（该风格最适合的题材/体裁/受众/创作场景等）",
  "potential_risks": "潜在风险（可能的重复套路/过度依赖/需要警惕的舒适区/易陷阱等）",
  "distinctive_summary": "独特性总结（用3-5句话概括这位作者最与众不同的地方）"
}}

注意：
1. 基于已有分析进行提炼，不要凭空创造
2. 要具体，避免"文笔优美""情感真挚"等空泛描述
3. 关注模式而非偶然
4. 给出可操作的风格指引
"""
            
            response = self.llm.invoke(prompt)
            content = response.content.strip()
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            distinctive = json.loads(content)
            
            print(f"[CoordinatorAgent] ✓ 独特特征分析完成")
            
            return distinctive
            
        except Exception as e:
            print(f"[CoordinatorAgent] ⚠ 独特特征分析失败: {e}")
            return None