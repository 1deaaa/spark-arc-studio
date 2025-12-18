"""
Bridge Agent - 场景过渡生成

连接两个场景，生成平滑的过渡对话
"""
import json
from langchain_core.messages import HumanMessage, SystemMessage
from llm.llm_mgr import LLM_Manager
from agents.agent_utils import load_prompt


class BridgeAgent:
    """
    Bridge Agent - 连接场景，生成过渡对话
    
    根据：
    - 上一场景结尾
    - 下一场景开头
    - 世界观设定
    - 角色信息
    - 节奏/氛围信息
    - 用户指导
    
    生成平滑的过渡对话节点
    """
    
    def __init__(self, user_id):
        self.user_id = user_id
        self.llm = LLM_Manager.get_user_llm(user_id, agent_name="agent_bridge", streaming=False, temperature=0.6)

    def bridge_scenes(
        self, 
        prev_scene: dict,
        next_scene: dict, 
        worldview: str = "",
        characters: list = None,
        pacing: str = "normal",
        mood: str = "",
        guidance: str = ""
    ) -> dict:
        """
        生成两个场景之间的过渡内容
        
        Args:
            prev_scene: 上一场景数据 {scene, cap, dia}
            next_scene: 下一场景数据 {scene, cap, dia}
            worldview: 世界观设定
            characters: 涉及的角色列表 [{id, name, desc}]
            pacing: 节奏 (slow/normal/fast)
            mood: 目标氛围
            guidance: 用户指导文本
            
        Returns:
            {
                "transition": [对话节点列表],
                "summary": "过渡总结",
                "suggested_cap": "建议的场景标题"
            }
        """
        # 提取场景文本
        prev_text = self._extract_scene_text(prev_scene)
        next_text = self._extract_scene_text(next_scene)
        
        # 构建角色信息
        char_info = "（未提供角色信息）"
        if characters:
            char_lines = []
            for c in characters:
                char_lines.append(f"- [{c.get('id', '?')}] {c.get('name', '未知')}: {c.get('desc', '')}")
            char_info = "\n".join(char_lines)

        # 从 YAML 加载提示词
        prompts = load_prompt(
            'bridge',
            worldview=worldview if worldview else "（未提供）",
            characters=char_info,
            prev_scene_name=prev_scene.get('scene', '未知'),
            prev_scene_cap=prev_scene.get('cap', ''),
            prev_scene_text=prev_text[-600:] if prev_text else "（场景开始）",
            next_scene_name=next_scene.get('scene', '未知'),
            next_scene_cap=next_scene.get('cap', ''),
            next_scene_text=next_text[:600] if next_text else "（场景结束）",
            pacing=pacing,
            mood=mood if mood else "自然过渡",
            guidance=guidance if guidance else "请生成自然的过渡对话"
        )

        messages = [
            SystemMessage(content=prompts['system']),
            HumanMessage(content=prompts['user'])
        ]

        try:
            response = self.llm.invoke(messages)
            result = self._extract_json(response.content)
            
            # 确保结果格式正确
            if isinstance(result, list):
                # 旧格式兼容
                result = {
                    "transition": result,
                    "summary": "场景过渡",
                    "suggested_cap": ""
                }
            
            if "transition" not in result:
                result["transition"] = []
                
            return result
        except Exception as e:
            print(f"[Bridge] Error: {e}")
            return {
                "transition": [],
                "summary": "生成失败",
                "suggested_cap": ""
            }

    def _extract_scene_text(self, scene: dict) -> str:
        """从场景数据中提取文本"""
        if not scene:
            return ""
        
        texts = []
        dia = scene.get('dia', [])
        
        for d in dia:
            txt = d.get('txt', '')
            if txt:
                texts.append(txt)
        
        return "\n".join(texts)

    def _extract_json(self, text):
        """从响应中提取 JSON"""
        import re
        
        # 尝试提取 ```json 块
        match = re.search(r'```json\s*([\s\S]*?)\s*```', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass
        
        # 尝试直接解析
        text = text.strip()
        
        # 找到 JSON 对象
        start_obj = text.find('{')
        end_obj = text.rfind('}')
        if start_obj != -1 and end_obj != -1:
            try:
                return json.loads(text[start_obj:end_obj+1])
            except:
                pass
        
        # 找到 JSON 数组
        start_arr = text.find('[')
        end_arr = text.rfind(']')
        if start_arr != -1 and end_arr != -1:
            try:
                return json.loads(text[start_arr:end_arr+1])
            except:
                pass
        
        return {"transition": [], "summary": "", "suggested_cap": ""}
