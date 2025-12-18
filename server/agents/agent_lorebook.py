"""Lorebook/Worldview 辅助逻辑（无框架依赖）。

该模块保留 FastAPI 路由复用的核心逻辑：
- WorldviewAgent：基于创意种子流式生成世界观
- get_all_characters、get_character_info：作为 LangChain Tool 的数据入口
"""

from __future__ import annotations

import json
import os
from typing import List

from langchain_core.messages import HumanMessage, SystemMessage
from llm.llm_mgr import LLM_Manager

from core.request_context import current_user_id, current_project_name
from core.utils import ensure_project_characters_directory


class WorldviewAgent:
    """封装世界观生成逻辑，供 FastAPI 路由调用。"""

    def __init__(self, user_id: int):
        self.user_id = user_id
        self.llm = LLM_Manager.get_user_llm(user_id, agent_name="agent_lorebook", streaming=True, temperature=0.7)

    def build_worldview(self, seed: str):
        """基于创意种子流式生成世界观文本。"""
        system_prompt = """你是**世界观架构师（Worldview Architect）**。
你的任务是基于提供的创意种子构建一个连贯的世界。

### 世界观文档必须涵盖：
1.  **地理与环境**：故事发生在哪里？
2.  **社会结构**：派系、等级制度、政治。
3.  **魔法/科技系统**：世界的规则。
4.  **历史**：导致当前状态的简要背景故事。
5.  **秘密**：关于这个世界的一个隐藏真相。

### 输出格式：
以清晰、结构化的文本返回结果，适合作为 "世界观.txt" 文件。
"""
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"创意种子:\n{seed}"),
        ]

        for chunk in self.llm.stream(messages):
            yield chunk.content


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
