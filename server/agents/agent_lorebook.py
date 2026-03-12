from __future__ import annotations

import json
import os
from typing import List, Any

from langchain_core.messages import HumanMessage, SystemMessage
from llm.llm_mgr import LLM_Manager
from llm.llm_mgr.reasoning_compat import PrefixReasoningStreamParser
from agents.agent_utils import load_prompt, build_length_hint_str, SparkAgentExecutor

from core.request_context import current_user_id, current_project_name
from core.utils import (
    ensure_project_characters_directory,
    get_project_worldview_path,
    ensure_project_worldview_and_character_settings,
)
from .communication import SparkBaseAgent


class WorldviewAgent(SparkBaseAgent, SparkAgentExecutor):
    """封装世界观生成逻辑，供 FastAPI 路由调用。"""

    def __init__(self, user_id: int):
        super().__init__(agent_id="agent_lorebook", user_id=str(user_id))
        self.llm = LLM_Manager.get_user_llm(str(user_id), agent_name="agent_lorebook")

    def build_context(self, operation: str, **kwargs) -> dict:
        """把世界观/角色入口参数整理成 Lorebook 统一上下文。"""
        return {"operation": operation, **kwargs}

    def execute(self, context: dict, *args, **kwargs) -> Any:
        """按统一上下文执行世界观生成或角色生成。"""
        operation = context.get("operation")
        if operation == "worldview":
            return self.build_worldview(
                seed=context.get("seed", ""),
                style_profile=context.get("style_profile"),
                length_hint=context.get("length_hint"),
            )
        if operation == "character":
            return self.generate_character(
                worldview=context.get("worldview", ""),
                existing_characters=context.get("existing_characters", ""),
                extra_guidance=context.get("extra_guidance", ""),
            )
        raise ValueError(f"不支持的 Lorebook operation: {operation}")

    def write_result(self, result: Any, *args, **kwargs) -> None:
        """将世界观或角色结果写回项目文件。"""
        operation = kwargs.get("operation")
        user_id = str(kwargs.get("user_id") or self.user_id)
        project_name = kwargs.get("project_name") or current_project_name.get()
        if not project_name:
            return None

        if operation in {"worldview", "overwrite_worldview"}:
            content = result if isinstance(result, str) else ""
            if content:
                self._write_worldview(user_id, project_name, content)
            return None

        if operation == "overwrite_characters":
            content = (
                result
                if isinstance(result, str)
                else kwargs.get("overwrite_content", "")
            )
            if not isinstance(content, str) or not content.strip():
                return None
            return self._write_characters_overwrite(user_id, project_name, content)

        return None

    def _get_tool_prompt_references(self) -> dict[str, list[dict]]:
        return {
            "rewrite_worldview": [
                {"prompt_key": "rewrite_worldview", "field": "system"}
            ],
            "rewrite_all_characters": [
                {"prompt_key": "generate_characters", "field": "system"}
            ],
        }

    def _get_tool_prompt_reference_values(self) -> dict[str, dict[str, str]]:
        return {
            "rewrite_worldview": {
                "worldview": "（由当前项目与上下文提供）",
                "guidance": "（由用户当前修改要求决定）",
                "style_profile": "（未提供）",
            },
            "generate_characters": {
                "worldview": "（由当前项目与上下文提供）",
                "existing_characters": "（由当前项目角色列表提供）",
                "extra_guidance": "（由用户当前修改要求决定）",
            },
        }

    def _build_tool_system_prompt(
        self, base_prompt: str, active_context: str = None
    ) -> str:
        prompt = super()._build_tool_system_prompt(base_prompt, active_context)
        prompt += """

### Lorebook 工具补充规则
- 如果用户已经明确表示“直接执行 / 立即修改 / 不要只提建议 / 不需要再次确认”，你必须直接调用工具，不要再次索要确认。
- 调用 `rewrite_worldview` 时，overwrite_content 必须是完整世界观正文，不能夹带解释。
- 调用 `rewrite_all_characters` 或 `update_character` 时，overwrite_content 必须是最终可保存的角色设定正文。
"""
        return prompt

    def build_worldview(
        self, seed: str, style_profile: object = None, length_hint: str = None
    ):
        """基于创意种子流式生成世界观文本。"""
        style_profile_text = "（未提供）"
        if style_profile is not None:
            if isinstance(style_profile, str):
                style_profile_text = style_profile.strip() or "（未提供）"
            else:
                style_profile_text = json.dumps(
                    style_profile, ensure_ascii=False, indent=2
                )

        prompts = load_prompt(
            "lorebook",
            seed=seed,
            style_profile=style_profile_text,
            length_hint=build_length_hint_str(length_hint),
        )

        messages = [
            SystemMessage(content=prompts["system"]),
            HumanMessage(content=prompts["user"]),
        ]

        parser = PrefixReasoningStreamParser()
        for chunk in self.llm.stream(messages):
            content = getattr(chunk, "content", None)
            if isinstance(content, str) and content:
                _, visible = parser.push(content)
                if visible:
                    yield visible
        _, trailing_visible = parser.flush()
        if trailing_visible:
            yield trailing_visible

    def generate_character(
        self, worldview: str, existing_characters: str, extra_guidance: str = ""
    ):
        """基于世界观和已有角色生成新角色。"""
        prompts = load_prompt(
            "lorebook",
            "generate_characters",
            worldview=worldview,
            existing_characters=existing_characters,
            extra_guidance=f"额外要求：{extra_guidance}" if extra_guidance else "",
        )

        messages = [
            SystemMessage(content=prompts["system"]),
            HumanMessage(content=prompts["user"]),
        ]

        parser = PrefixReasoningStreamParser()
        for chunk in self.llm.stream(messages):
            content = getattr(chunk, "content", None)
            if isinstance(content, str) and content:
                _, visible = parser.push(content)
                if visible:
                    yield visible
        _, trailing_visible = parser.flush()
        if trailing_visible:
            yield trailing_visible

    def _write_worldview(self, user_id: str, project_name: str, content: str) -> None:
        ensure_project_worldview_and_character_settings(user_id, project_name)
        path = get_project_worldview_path(user_id, project_name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content or "")

    def _snapshot_characters(self, user_id: str, project_name: str):
        characters_path = ensure_project_characters_directory(user_id, project_name)
        bind_path = os.path.join(characters_path, "chr.bind")

        mapping = {}
        if os.path.exists(bind_path):
            try:
                with open(bind_path, "r", encoding="utf-8") as f:
                    mapping = json.load(f) or {}
            except Exception:
                mapping = {}

        lines = []
        for cid, name in mapping.items():
            try:
                char_file = os.path.join(characters_path, f"{cid}.txt")
                content = ""
                if os.path.exists(char_file):
                    with open(char_file, "r", encoding="utf-8") as f:
                        text = f.read()
                        parts = text.split("\n", 2)
                        content = parts[2] if len(parts) >= 3 else text
                content = (content or "").strip()
                if len(content) > 400:
                    content = content[:400] + "…"
                lines.append(f"- {name}: {content}")
            except Exception:
                continue

        narrator_name = mapping.get("-1") if "-1" in mapping else None
        existing_block = "\n".join(lines) if lines else ""
        return characters_path, bind_path, mapping, existing_block, narrator_name

    def _reset_characters_keep_narrator(
        self, bind_path: str, characters_path: str, narrator_name: str | None
    ):
        for filename in os.listdir(characters_path):
            if filename.endswith(".txt") and filename != "-1.txt":
                try:
                    os.remove(os.path.join(characters_path, filename))
                except Exception:
                    pass

        mapping = {}
        if narrator_name:
            mapping["-1"] = narrator_name
        with open(bind_path, "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
        return mapping

    def _parse_characters_overwrite_text(self, full_text: str) -> list[tuple[str, str]]:
        text = (full_text or "").strip()
        if not text:
            return []

        def _is_valid_name(name: str) -> bool:
            n = (name or "").strip()
            if not n:
                return False
            if n.startswith("#"):
                return False
            if n.startswith("角色设定文档") or n.startswith("角色设定"):
                return False
            if len(n) > 80:
                return False
            return True

        def _parse_block(block_text: str) -> tuple[str, str] | None:
            block = (block_text or "").strip()
            if not block:
                return None
            if "\n\n" not in block:
                return None
            name, content = block.split("\n\n", 1)
            name = name.strip()
            content = content.strip()
            if not _is_valid_name(name) or not content:
                return None
            return name, content

        try:
            payload = json.loads(text)
            if isinstance(payload, dict):
                payload = payload.get("characters", [])

            parsed = []
            if isinstance(payload, list):
                for item in payload:
                    if not isinstance(item, dict):
                        continue
                    name = str(item.get("name") or "新角色").strip() or "新角色"
                    content = str(
                        item.get("content")
                        or item.get("desc")
                        or item.get("text")
                        or ""
                    ).strip()
                    if content:
                        parsed.append((name, content))
            if parsed:
                return parsed
        except Exception:
            pass

        parsed = []
        if "\n---\n" in text or "\n\n---\n\n" in text:
            separators_normalized = text.replace("\n\n---\n\n", "\n---\n")
            blocks = [b for b in separators_normalized.split("\n---\n") if b.strip()]
            for block in blocks:
                item = _parse_block(block)
                if item:
                    parsed.append(item)
            return parsed

        single = _parse_block(text)
        return [single] if single else []

    def _write_characters_overwrite(
        self, user_id: str, project_name: str, overwrite_content: str
    ) -> str:
        characters_path, bind_path, mapping, existing_block, narrator_name = (
            self._snapshot_characters(user_id, project_name)
        )
        parsed_characters = self._parse_characters_overwrite_text(overwrite_content)
        if not parsed_characters:
            return "角色覆盖失败：overwrite_content 格式不正确。请使用 JSON characters 列表，或“角色名 + 空行 + 角色内容”并用 --- 分隔多个角色。"

        mapping = self._reset_characters_keep_narrator(
            bind_path, characters_path, narrator_name
        )

        existing_ids = {int(k) for k in mapping.keys()} if mapping else set()
        created = 0

        for name, content in parsed_characters:
            char_id = 0
            while char_id in existing_ids:
                char_id += 1
            existing_ids.add(char_id)

            safe_name = (name or "新角色").strip() or "新角色"
            safe_content = (content or "").strip()
            if not safe_content:
                continue

            mapping[str(char_id)] = safe_name
            char_file = os.path.join(characters_path, f"{char_id}.txt")
            with open(char_file, "w", encoding="utf-8") as f:
                f.write(f"{safe_name}\n\n{safe_content}")

            created += 1

        with open(bind_path, "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)

        return f"已使用工具参数中的完整文本覆盖角色设定，共写入 {created} 个角色。"


def get_all_characters() -> List[str]:
    """返回当前上下文项目的所有角色名称。"""
    user_id = current_user_id.get()
    project_name = current_project_name.get()
    if not user_id or not project_name:
        return ["错误：无法获取用户或项目上下文。"]

    try:
        characters_path = ensure_project_characters_directory(user_id, project_name)
        bind_path = os.path.join(characters_path, "chr.bind")
        if not os.path.exists(bind_path):
            return []
        with open(bind_path, "r", encoding="utf-8") as file:
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
        bind_path = os.path.join(characters_path, "chr.bind")
        if not os.path.exists(bind_path):
            return "角色绑定文件不存在。"

        with open(bind_path, "r", encoding="utf-8") as file:
            mapping = json.load(file)

        char_id = next(
            (cid for cid, name in mapping.items() if name == character_name), None
        )
        if not char_id:
            return f"未找到名为 '{character_name}' 的角色。"

        char_file_path = os.path.join(characters_path, f"{char_id}.txt")
        if not os.path.exists(char_file_path):
            return f"找到了角色 '{character_name}' 但其设定文件丢失。"

        with open(char_file_path, "r", encoding="utf-8") as file:
            return file.read()
    except Exception as exc:  # pragma: no cover - 调试日志
        print(f"获取角色 '{character_name}' 信息失败: {exc}")
        return f"获取角色 '{character_name}' 信息时发生错误。"
