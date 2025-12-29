from __future__ import annotations

import json
import os
from typing import List

from langchain_core.messages import HumanMessage, SystemMessage
from llm.llm_mgr import LLM_Manager
from agents.agent_utils import load_prompt

from core.request_context import current_user_id, current_project_name
from core.utils import ensure_project_characters_directory
from .communication import SparkBaseAgent


class WorldviewAgent(SparkBaseAgent):
    """封装世界观生成逻辑，供 FastAPI 路由调用。"""

    def __init__(self, user_id: int):
        super().__init__(agent_id="agent_lorebook", user_id=str(user_id))
        self.llm = LLM_Manager.get_user_llm(user_id, agent_name="agent_lorebook", streaming=True, temperature=0.7)

    def build_worldview(self, seed: str, style_profile: object = None):
        """基于创意种子流式生成世界观文本。"""
        style_profile_text = "（未提供）"
        if style_profile is not None:
            if isinstance(style_profile, str):
                style_profile_text = style_profile.strip() or "（未提供）"
            else:
                style_profile_text = json.dumps(style_profile, ensure_ascii=False, indent=2)

        prompts = load_prompt('lorebook', seed=seed, style_profile=style_profile_text)
        
        messages = [
            SystemMessage(content=prompts['system']),
            HumanMessage(content=prompts['user']),
        ]

        for chunk in self.llm.stream(messages):
            yield chunk.content

    def generate_character(self, worldview: str, existing_characters: str, extra_guidance: str = ""):
        """基于世界观和已有角色生成新角色。"""
        prompts = load_prompt(
            'lorebook',
            'generate_characters',
            worldview=worldview,
            existing_characters=existing_characters,
            extra_guidance=f"额外要求：{extra_guidance}" if extra_guidance else ""
        )

        messages = [
            SystemMessage(content=prompts['system']),
            HumanMessage(content=prompts['user']),
        ]

        for chunk in self.llm.stream(messages):
            yield chunk


def get_all_characters() -> List[str]:
    """返回当前上下文项目的所有角色名称。"""
    user_id = current_user_id.get()
    project_name = current_project_name.get()
    if not user_id or not project_name:
        return ["错误：无法获取用户或项目上下文。"]

    try:
        characters_path = ensure_project_characters_directory(user_id, project_name)
        bind_path = os.path.join(characters_path, 'chr.bind')
        if not os.path.exists(bind_path):
            return []
        with open(bind_path, 'r', encoding='utf-8') as file:
            mapping = json.load(file)
        # 强制id为-1的角色名字显示为"旁白"
        character_names = []
        for char_id, char_name in mapping.items():
            if char_id == "-1":
                character_names.append("旁白")
            else:
                character_names.append(char_name)
        return character_names
    except Exception as exc:  # pragma: no cover - 调试日志
        print(f"获取角色列表失败: {exc}")
        return [f"获取角色列表时出错: {exc}"]


def get_character_info(character_name: str) -> str:
    """返回指定角色的详细设定文本。"""
    user_id = current_user_id.get()
    project_name = current_project_name.get()
    if not user_id or not project_name:
        return "错误：无法获取用户或项目上下文。"

    try:
        characters_path = ensure_project_characters_directory(user_id, project_name)
        bind_path = os.path.join(characters_path, 'chr.bind')
        if not os.path.exists(bind_path):
            return "角色绑定文件不存在。"

        with open(bind_path, 'r', encoding='utf-8') as file:
            mapping = json.load(file)

        char_id = next((cid for cid, name in mapping.items() if name == character_name), None)
        if not char_id:
            return f"未找到名为 '{character_name}' 的角色。"

        char_file_path = os.path.join(characters_path, f"{char_id}.txt")
        if not os.path.exists(char_file_path):
            return f"找到了角色 '{character_name}' 但其设定文件丢失。"

        with open(char_file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as exc:  # pragma: no cover - 调试日志
        print(f"获取角色 '{character_name}' 信息失败: {exc}")
        return f"获取角色 '{character_name}' 信息时发生错误。"
