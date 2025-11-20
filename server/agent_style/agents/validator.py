import json
from typing import Dict
from ..utils import llm

class ValidatorAgent:
    """风格验证Agent：基于定性评级（而非定量打分）来验证和优化风格"""
    
    def __init__(self):
        self.llm = llm
        
    def validate_and_refine(self, style_profile: Dict, test_text: str) -> Dict:
        print("\n[ValidatorAgent] 开始回测验证...")
        
        # 1. 提取原文大意
        summary_prompt = f"请用一句话概括这段文字的大意：\n{test_text}"
        summary = self.llm.invoke(summary_prompt).content.strip()
        
        # 2. 尝试模仿
        profile_str = json.dumps(style_profile, ensure_ascii=False)[:2000]
        mimic_prompt = f"""
请扮演该作者，基于以下风格档案，将摘要扩写为一段文字。
风格档案：{profile_str}
摘要：{summary}
要求：极度贴合作者文风，不要出现AI味，捕捉文字的呼吸感。
"""
        mimic_text = self.llm.invoke(mimic_prompt).content.strip()
        
        # 3. 评级与修正 - 深度特征版
        # 针对 LLM 的理解逻辑，把“感觉”拆解为“维度”：
        # 1. 句法指纹 (Sentence Fingerprint): 长短句分布、标点习惯
        # 2. 词汇温度 (Lexical Temperature): 用词的生僻度、情绪色彩
        # 3. 逻辑连接 (Logical Connectivity): 是显性逻辑(首先/其次)还是隐性逻辑(流水账/意识流)
        
        grading_rubric = """
        【S级 (完美拟合 | Perfect Fit)】
        - 核心特征：隐形成文。不仅用词一致，连“思维跳跃的方式”和“留白”都完全复刻。
        - 句法表现：长短句交错的呼吸感与原文一致，没有显性的逻辑连接词（如“首先、然而”）除非原文常包含。
        - 违和感：0。读起来就像作者本人在无意识状态下的练笔。

        【A级 (高保真 | High Fidelity)】
        - 核心特征：形似度极高。准确捕捉了作者的常用词汇（口头禅）和语气助词。
        - 缺陷：在极个别复杂的长句中，稍微流露出了AI的条理性，逻辑过于严密，缺少人的“随意感”。
        - 判定标准：乍看之下无法分辨，需细读才能发现“逻辑连接”略显生硬。

        【B级 (AI味残留 | AI Residue)】
        - 核心特征：套皮感。虽然用了很多作者的词汇，但骨子里还是 AI 的“总分总”结构或“解释性”语气。
        - 缺陷：出现典型的 LLM 味道，例如喜欢升华主题、过度使用连接词（因此、此外）、说教感。
        - 判定标准：像是一个尽职的模仿秀演员，虽然穿了角色的衣服，但说话腔调还是自己的。

        【C级 (过拟合/刻板印象 | Overfitting)】
        - 核心特征：用力过猛。频繁堆砌作者的特色词汇，导致行文不通顺或显得滑稽。
        - 缺陷：捕捉到了风格特征（Feature），但丢失了语境逻辑（Context）。比如作者偶尔用一句脏话，模仿文却每句都有。
        - 判定标准：像是一个拙劣的讽刺作品，把作者的特点放大到了不自然的程度。

        【D级 (坍塌 | Collapse)】
        - 核心特征：完全偏离。退化为标准的“智能助手”语气，或者风格完全搞错（例如把严肃文风写成了欢脱文风）。
        - 判定标准：与原文毫无关系，完全是通用的 AI 回复。
        """

        eval_prompt = f"""
你是文学风格鉴赏家与数据分析师。请基于【评级标准】对模仿文进行严格的图灵测试。

【评级标准】
{grading_rubric}

【原文样本】
{test_text}

【模仿生成】
{mimic_text}

请分析并输出JSON（不要输出Markdown格式）：
{{
    "similarity_level": "S/A/B/C/D",
    "detected_ai_features": ["列出具体的AI味特征，如：'逻辑连接词过多'、'结尾强行升华'"],
    "missing_style_features": ["列出缺失的作者特征，如：'缺少短句断奏'、'形容词不够辛辣'"],
    "refinement_suggestions": "针对上述缺失/多余特征，给出一句具体的Prompt修正指令（例如：'强制禁止使用‘然而’、‘总而言之’等连接词'）"
}}
"""
        response = self.llm.invoke(eval_prompt).content.strip().replace("```json", "").replace("```", "")
        
        try:
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
