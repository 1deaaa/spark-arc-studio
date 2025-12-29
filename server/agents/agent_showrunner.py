"""
文案策划 - 剧情大纲生成

生成可视化的树状剧情大纲，包含：
- 节点（可嵌套）
- 每个节点有标题、描述、类型、子节点等
"""
import json
from langchain_core.messages import HumanMessage, SystemMessage
from llm.llm_mgr import LLM_Manager
from agents.agent_utils import load_prompt
from .communication import SparkBaseAgent


class ShowrunnerAgent(SparkBaseAgent):
    def __init__(self, user_id):
        super().__init__(agent_id="agent_showrunner", user_id=user_id)
        self.llm = LLM_Manager.get_user_llm(user_id, agent_name="agent_showrunner", streaming=True, temperature=0.7)

    def generate_synopsis(self, logline: str, worldview: str, roles: str, guidance: str) -> dict:
        """
        生成故事梗概 (Synopsis)
        """
        prompts = load_prompt(
            'showrunner',
            'generate_synopsis',
            logline=logline,
            worldview=worldview or "（未提供）",
            roles=roles or "（未提供）",
            guidance=guidance or "请生成一个吸引人的故事梗概"
        )

        messages = [
            SystemMessage(content=prompts['system']),
            HumanMessage(content=prompts['user'])
        ]

        try:
            response = self.llm.invoke(messages)
            content = self._clean_json_block(response.content)
            return json.loads(content)
        except Exception as e:
            raise RuntimeError(f"[Showrunner] 生成梗概失败: {e}")

    def generate_beat_sheet(self, synopsis: str, worldview: str, roles: str, guidance: str) -> dict:
        """
        生成节拍表 (Beat Sheet)
        """
        prompts = load_prompt(
            'showrunner',
            'generate_beat_sheet',
            synopsis=synopsis,
            worldview=worldview or "（未提供）",
            roles=roles or "（未提供）",
            guidance=guidance or "请将梗概拆解为具有情感张力的节拍"
        )

        messages = [
            SystemMessage(content=prompts['system']),
            HumanMessage(content=prompts['user'])
        ]

        try:
            response = self.llm.invoke(messages)
            content = self._clean_json_block(response.content)
            return json.loads(content)
        except Exception as e:
            raise RuntimeError(f"[Showrunner] 生成节拍表失败: {e}")

    def generate_outline(self, context: str, worldview: str, roles: str, guidance: str, chapter_count: int = 5, beat_sheet: any = "") -> dict:
        """
        生成可视化剧情大纲（树状结构）
        
        Args:
            context: 当前剧情上下文
            worldview: 世界观设定
            roles: 角色设定
            guidance: 用户指导意图
            chapter_count: 章节数量，默认5章
            beat_sheet: 节拍表内容 (JSON 对象或字符串)
        
        返回格式：
        {
            "title": "故事标题",
            "summary": "整体概述",
            "totalChapters": 5,
            "nodes": [...]
        }
        """
        # 处理 beat_sheet 序列化
        beat_sheet_str = beat_sheet
        if isinstance(beat_sheet, (dict, list)):
            beat_sheet_str = json.dumps(beat_sheet, ensure_ascii=False, indent=2)

        # 从 YAML 加载提示词（generate_outline 子模板）
        prompts = load_prompt(
            'showrunner',
            'generate_outline',
            worldview=worldview if worldview else "（未提供，请创建一个原创世界观）",
            roles=roles if roles else "（未提供，请创建合适的角色）",
            context=context if context else "这是一个全新的故事",
            beat_sheet=beat_sheet_str if beat_sheet_str else "（未提供）",
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
            raise RuntimeError(f"[Showrunner] 生成大纲失败: {e}")

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
