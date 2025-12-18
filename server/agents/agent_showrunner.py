"""
导演助理 - 剧情大纲生成

生成可视化的树状剧情大纲，包含：
- 节点（可嵌套）
- 每个节点有标题、描述、类型、子节点等
"""
import json
from langchain_core.messages import HumanMessage, SystemMessage
from llm.llm_mgr import LLM_Manager
from agents.agent_utils import load_prompt


class ShowrunnerAgent:
    def __init__(self, user_id):
        self.user_id = user_id
        self.llm = LLM_Manager.get_user_llm(user_id, agent_name="agent_showrunner", streaming=False, temperature=0.7)

    def generate_outline(self, context: str, worldview: str, roles: str, guidance: str, chapter_count: int = 5) -> dict:
        """
        生成可视化剧情大纲（树状结构）
        
        Args:
            context: 当前剧情上下文
            worldview: 世界观设定
            roles: 角色设定
            guidance: 用户指导意图
            chapter_count: 章节数量，默认5章
        
        返回格式：
        {
            "title": "故事标题",
            "summary": "整体概述",
            "totalChapters": 5,
            "nodes": [...]
        }
        """
        # 从 YAML 加载提示词（generate_outline 子模板）
        prompts = load_prompt(
            'showrunner',
            'generate_outline',
            worldview=worldview if worldview else "（未提供，请创建一个原创世界观）",
            roles=roles if roles else "（未提供，请创建合适的角色）",
            context=context if context else "这是一个全新的故事",
            guidance=guidance if guidance else f"请生成一个包含{chapter_count}个章节的故事大纲",
            chapter_count=chapter_count
        )

        messages = [
            SystemMessage(content=prompts['system']),
            HumanMessage(content=prompts['user'])
        ]

        try:
            response = self.llm.invoke(messages)
            content = response.content
            content = self._clean_json_block(content)
            outline = json.loads(content)
            
            # 确保必要字段存在
            if 'nodes' not in outline:
                outline['nodes'] = []
            if 'title' not in outline:
                outline['title'] = '新故事大纲'
            if 'totalChapters' not in outline:
                outline['totalChapters'] = len(outline.get('nodes', []))
                
            return outline
        except Exception as e:
            print(f"[Showrunner] Error generating outline: {e}")
            # 返回基础模板
            return self._get_fallback_outline(chapter_count)

    def plan_scene(self, context: str, worldview: str, roles: str, guidance: str, segment_count: int = 3) -> dict:
        """
        生成场景级别的 Beat Sheet（保留兼容性）
        """
        # 处理 segment_count 为 0 的情况
        planning_instruction = ""
        if segment_count <= 0:
            planning_instruction = "Plan a complete scene sequence that reaches a logical conclusion or transition. Include as many beats as necessary to fully flesh out the scene."
        else:
            planning_instruction = "List 3-5 specific plot points or emotional moments that must happen."

        # 从 YAML 加载提示词（plan_scene 子模板）
        prompts = load_prompt(
            'showrunner',
            'plan_scene',
            worldview=worldview,
            roles=roles,
            context=context,
            guidance=guidance,
            planning_instruction=planning_instruction
        )

        messages = [
            SystemMessage(content=prompts['system']),
            HumanMessage(content=prompts['user'])
        ]

        try:
            response = self.llm.invoke(messages)
            content = response.content
            content = self._clean_json_block(content)
            beat_sheet = json.loads(content)
            return beat_sheet
        except Exception as e:
            print(f"[Showrunner] Error generating beat sheet: {e}")
            return {
                "summary": "剧情继续发展",
                "pacing": "Normal",
                "tension_level": "Medium",
                "mood": "Neutral",
                "key_beats": ["角色继续当前的对话或行动"],
                "director_notes": "保持当前氛围"
            }

    def _clean_json_block(self, text: str) -> str:
        """Extract JSON from potential markdown code blocks."""
        text = text.strip()
        if text.startswith("```"):
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline + 1:]
            if text.endswith("```"):
                text = text[:-3]
        return text.strip()

    def _get_fallback_outline(self, chapter_count: int = 5) -> dict:
        """返回一个基础的大纲模板"""
        # 根据章节数量生成默认章节
        chapter_titles = [
            ("开端", "故事的开始，建立背景和角色，引入主要人物和世界观设定。", "平静", "low"),
            ("发展", "情节逐渐展开，主角开始面对挑战，冲突初现端倪。", "紧张", "medium"),
            ("转折", "故事出现重大转折，主角遭遇危机或获得重要线索。", "惊险", "high"),
            ("高潮", "冲突达到顶点，主角与对手正面交锋，命运的关键时刻。", "激烈", "high"),
            ("结局", "故事收尾，矛盾得到解决，角色完成成长。", "感慨", "medium"),
        ]
        
        nodes = []
        for i in range(min(chapter_count, len(chapter_titles))):
            title, desc, mood, tension = chapter_titles[i]
            nodes.append({
                "id": f"chapter_{i+1}",
                "title": f"第{i+1}章：{title}",
                "type": "chapter",
                "chapter": i + 1,
                "description": desc,
                "mood": mood,
                "tension": tension,
                "children": [
                    {
                        "id": f"scene_{i+1}_1",
                        "title": "场景一",
                        "type": "scene",
                        "description": "",
                        "mood": mood,
                        "tension": tension,
                        "children": []
                    }
                ]
            })
        
        # 如果需要更多章节，继续生成
        for i in range(len(chapter_titles), chapter_count):
            nodes.append({
                "id": f"chapter_{i+1}",
                "title": f"第{i+1}章",
                "type": "chapter",
                "chapter": i + 1,
                "description": "请填写本章剧情概述...",
                "mood": "",
                "tension": "medium",
                "children": [
                    {
                        "id": f"scene_{i+1}_1",
                        "title": "场景一",
                        "type": "scene",
                        "description": "",
                        "mood": "",
                        "tension": "medium",
                        "children": []
                    }
                ]
            })
        
        return {
            "title": "新故事大纲",
            "summary": "请在左侧输入上下文和指导，生成详细大纲",
            "totalChapters": chapter_count,
            "estimatedScenes": chapter_count * 2,
            "mainTheme": "",
            "nodes": nodes
        }
