"""
文案策划 - 剧情大纲生成

生成可视化的树状剧情大纲，包含：
- 节点（可嵌套）
- 每个节点有标题、描述、类型、子节点等
"""
import json
import os
from typing import Any
from llm.agen_matchbox import matchbox
from llm.agen_matchbox.reasoning_compat import (
    PrefixReasoningStreamParser,
    extract_visible_text_from_plain_text,
)
from agents.agent_utils import load_prompt, build_length_hint_str, SparkAgentExecutor
from agents.agent_style.utils import format_style_profile_for_prompt
from agents.prompt_layout import build_prompt_messages
from story.outline_parser import parse_beat_sheet_markup, parse_outline_markup
from .communication import SparkBaseAgent


SHOWRUNNER_STYLE_FALLBACK = "用户未提供参考风格档案。请根据故事主题、世界观氛围和角色特质，自行选择最合适的文笔风格进行创作。"


class ShowrunnerAgent(SparkBaseAgent, SparkAgentExecutor):
    def __init__(self, user_id):
        super().__init__(agent_id="agent_showrunner", user_id=user_id)
        self.llm = matchbox().get_user_llm(str(user_id), agent_name="agent_showrunner")

    def _stringify_style_profile(self, style_profile: object = None) -> str:
        """把风格档案转成规划阶段也能执行的提示块。"""
        return format_style_profile_for_prompt(
            style_profile,
            fallback=SHOWRUNNER_STYLE_FALLBACK,
        )

    def _invoke_visible_text(self, messages) -> str:
        """后台/非流式生成直接走 invoke，并剥离兼容推理标签。"""
        response = self.llm.invoke(messages)
        raw_content = response.content if isinstance(response.content, str) else str(response.content)
        return extract_visible_text_from_plain_text(raw_content)

    def build_context(self, operation: str, **kwargs) -> dict:
        """把梗概/节拍/大纲请求整理成统一上下文。"""
        return {"operation": operation, **kwargs}

    def execute(self, context: dict, *args, **kwargs) -> Any:
        """按统一上下文执行业务生成，并根据 `stream` 决定是否流式返回。"""
        operation = context.get("operation")
        stream = kwargs.get("stream", False)
        if operation == "synopsis":
            return self.generate_synopsis_stream(**{k: v for k, v in context.items() if k != "operation"}) if stream else self.generate_synopsis(**{k: v for k, v in context.items() if k != "operation"})
        if operation == "beat_sheet":
            return self.generate_beat_sheet_stream(**{k: v for k, v in context.items() if k != "operation"}) if stream else self.generate_beat_sheet(**{k: v for k, v in context.items() if k != "operation"})
        if operation == "outline":
            return self.generate_outline_stream(**{k: v for k, v in context.items() if k != "operation"}) if stream else self.generate_outline(**{k: v for k, v in context.items() if k != "operation"})
        raise ValueError(f"不支持的 Showrunner operation: {operation}")

    def write_result(self, result: Any, *args, **kwargs) -> None:
        """把梗概、节拍或大纲写回项目文件与历史记录（Markup 纯文本）。"""
        from core.utils import get_project_path
        from agents.routes.schemas import _save_outline_to_history, _save_project_outline
        from agents.routes.schemas import _save_project_synopsis, _save_project_beat_sheet

        operation = kwargs.get("operation")
        user_id = str(kwargs.get("user_id") or self.user_id)
        project_name = kwargs.get("project_name")
        if not project_name:
            return None

        if operation == "synopsis" and result is not None:
            # result 可能是 dict（旧调用方）或 str（Markup 文本）
            if isinstance(result, str):
                markup_text = result
            else:
                from story.outline_parser import serialize_synopsis_to_markup
                markup_text = serialize_synopsis_to_markup(result)
            _save_project_synopsis(user_id, project_name, markup_text)
            return None

        if operation == "beat_sheet" and result is not None:
            if isinstance(result, str):
                markup_text = result
            else:
                from story.outline_parser import serialize_beat_sheet_to_markup
                markup_text = serialize_beat_sheet_to_markup(result)
            _save_project_beat_sheet(user_id, project_name, markup_text)
            return None

        if operation == "outline" and result is not None:
            if isinstance(result, str):
                markup_text = result
            else:
                from story.outline_parser import serialize_outline_to_markup
                markup_text = serialize_outline_to_markup(result)
            if kwargs.get("save_to_project", True):
                _save_project_outline(user_id, project_name, markup_text)
            if kwargs.get("save_to_history", False):
                _save_outline_to_history(user_id, project_name, markup_text)
            return None

        return None

    def generate_synopsis(self, logline: str, worldview: str, roles: str, guidance: str, style_profile: object = None, length_hint: str = None, story_tags: str = "") -> str:
        """
        生成故事梗概 (Synopsis)，返回 Synopsis Markup 文本。
        """
        style_profile_text = self._stringify_style_profile(style_profile)

        prompts = load_prompt(
            'showrunner',
            'generate_synopsis',
            logline=logline,
            worldview=worldview or "（未提供）",
            roles=roles or "（未提供）",
            guidance=guidance or "请生成一个吸引人的故事梗概",
            style_profile=style_profile_text,
            length_hint=build_length_hint_str(length_hint),
            story_tags=story_tags or "",
        )

        messages = build_prompt_messages(system_prompt=prompts['system'], user_prompt=prompts['user'])

        try:
            # 不再强制解析 JSON，直接返回 Markup 文本
            return self._invoke_visible_text(messages).strip()
        except Exception as e:
            raise RuntimeError(f"[Showrunner] 生成梗概失败: {e}")

    def generate_synopsis_stream(self, logline: str, worldview: str, roles: str, guidance: str, style_profile: object = None, length_hint: str = None, story_tags: str = ""):
        """
        流式生成故事梗概 (Synopsis)
        """
        style_profile_text = self._stringify_style_profile(style_profile)

        prompts = load_prompt(
            'showrunner',
            'generate_synopsis',
            logline=logline,
            worldview=worldview or "（未提供）",
            roles=roles or "（未提供）",
            guidance=guidance or "请生成一个吸引人的故事梗概",
            style_profile=style_profile_text,
            length_hint=build_length_hint_str(length_hint),
            story_tags=story_tags or "",
        )

        messages = build_prompt_messages(system_prompt=prompts['system'], user_prompt=prompts['user'])

        full_content = ""
        parser = PrefixReasoningStreamParser()
        for chunk in self.llm.stream(messages):
            content = getattr(chunk, "content", "")
            if content:
                _, visible = parser.push(content)
                if not visible:
                    continue
                full_content += visible
                yield {
                    'type': 'chunk',
                    'content': visible,
                    'total_chars': len(full_content)
                }
        _, trailing_visible = parser.flush()
        if trailing_visible:
            full_content += trailing_visible
            yield {
                'type': 'chunk',
                'content': trailing_visible,
                'total_chars': len(full_content)
            }
        
        # 不再强制解析 JSON，直接返回 Markup 文本
        yield {
            'type': 'done',
            'synopsis': full_content.strip(),
            'total_chars': len(full_content)
        }

    def generate_beat_sheet(self, synopsis: str, worldview: str, roles: str, guidance: str, style_profile: object = None, length_hint: str = None, story_tags: str = "") -> dict:
        """
        生成节拍表 (Beat Sheet)
        """
        style_profile_text = self._stringify_style_profile(style_profile)

        prompts = load_prompt(
            'showrunner',
            'generate_beat_sheet',
            synopsis=synopsis,
            worldview=worldview or "（未提供）",
            roles=roles or "（未提供）",
            guidance=guidance or "请将梗概拆解为具有情感张力的节拍",
            style_profile=style_profile_text,
            length_hint=build_length_hint_str(length_hint),
            story_tags=story_tags or "",
        )

        messages = build_prompt_messages(system_prompt=prompts['system'], user_prompt=prompts['user'])

        try:
            content = self._clean_json_block(self._invoke_visible_text(messages))
            return parse_beat_sheet_markup(content)
        except Exception as e:
            raise RuntimeError(f"[Showrunner] 生成节拍表失败: {e}")

    def generate_outline(self, context: str, worldview: str, roles: str, guidance: str, chapter_count: int = 5, scene_count_per_chapter: int = 3, beat_sheet: any = "", style_profile: object = None, story_tags: str = "") -> dict:
        """
        生成可视化剧情大纲（树状结构）
        
        Args:
            context: 当前剧情上下文
            worldview: 世界观设定
            roles: 角色设定
            guidance: 用户指导意图
            chapter_count: 章节数量，默认5章
            beat_sheet: 节拍表内容 (JSON 对象或字符串)
            style_profile: 风格档案
        
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

        style_profile_text = self._stringify_style_profile(style_profile)

        # 从 YAML 加载提示词（generate_outline 子模板）
        prompts = load_prompt(
            'showrunner',
            'generate_outline',
            worldview=worldview if worldview else "（未提供，请创建一个原创世界观）",
            roles=roles if roles else "（未提供，请创建合适的角色）",
            context=context if context else "这是一个全新的故事",
            beat_sheet=beat_sheet_str if beat_sheet_str else "（未提供）",
            guidance=guidance if guidance else f"请生成一个章节数尽量贴合 {chapter_count} 章目标的大纲；场景数量按剧情节奏弹性安排",
            chapter_count=chapter_count,
            scene_count_per_chapter=scene_count_per_chapter,
            style_profile=style_profile_text,
            story_tags=story_tags or "",
        )

        messages = build_prompt_messages(system_prompt=prompts['system'], user_prompt=prompts['user'])

        try:
            content = self._clean_markdown_block(self._invoke_visible_text(messages))
            outline = parse_outline_markup(content)
            
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

    def generate_beat_sheet_stream(self, synopsis: str, worldview: str, roles: str, guidance: str, style_profile: object = None, length_hint: str = None, story_tags: str = ""):
        """
        流式生成节拍表 (Beat Sheet)
        """
        style_profile_text = self._stringify_style_profile(style_profile)

        prompts = load_prompt(
            'showrunner',
            'generate_beat_sheet',
            synopsis=synopsis,
            worldview=worldview or "（未提供）",
            roles=roles or "（未提供）",
            guidance=guidance or "请将梗概拆解为具有情感张力的节拍",
            style_profile=style_profile_text,
            length_hint=build_length_hint_str(length_hint),
            story_tags=story_tags or "",
        )

        messages = build_prompt_messages(system_prompt=prompts['system'], user_prompt=prompts['user'])

        full_content = ""
        parser = PrefixReasoningStreamParser()
        for chunk in self.llm.stream(messages):
            content = getattr(chunk, "content", "")
            if content:
                _, visible = parser.push(content)
                if not visible:
                    continue
                full_content += visible
                yield {
                    'type': 'chunk',
                    'content': visible,
                    'total_chars': len(full_content)
                }
        _, trailing_visible = parser.flush()
        if trailing_visible:
            full_content += trailing_visible
            yield {
                'type': 'chunk',
                'content': trailing_visible,
                'total_chars': len(full_content)
            }
        
        try:
            content = self._clean_markdown_block(full_content)
            beat_sheet = parse_beat_sheet_markup(content)
            yield {
                'type': 'done',
                'beat_sheet': beat_sheet,
                'total_chars': len(full_content)
            }
        except Exception as e:
            yield {
                'type': 'error',
                'message': f"解析节拍表 Markup 失败: {e}"
            }

    def generate_outline_stream(self, context: str, worldview: str, roles: str, guidance: str, chapter_count: int = 5, scene_count_per_chapter: int = 3, beat_sheet: any = "", style_profile: object = None, story_tags: str = ""):
        """
        流式生成可视化剧情大纲（树状结构）
        """
        beat_sheet_str = beat_sheet
        if isinstance(beat_sheet, (dict, list)):
            beat_sheet_str = json.dumps(beat_sheet, ensure_ascii=False, indent=2)

        style_profile_text = self._stringify_style_profile(style_profile)

        prompts = load_prompt(
            'showrunner',
            'generate_outline',
            worldview=worldview if worldview else "（未提供，请创建一个原创世界观）",
            roles=roles if roles else "（未提供，请创建合适的角色）",
            context=context if context else "这是一个全新的故事",
            beat_sheet=beat_sheet_str if beat_sheet_str else "（未提供）",
            guidance=guidance if guidance else f"请生成一个章节数尽量贴合 {chapter_count} 章目标的大纲；场景数量按剧情节奏弹性安排",
            chapter_count=chapter_count,
            scene_count_per_chapter=scene_count_per_chapter,
            style_profile=style_profile_text,
            story_tags=story_tags or "",
        )

        messages = build_prompt_messages(system_prompt=prompts['system'], user_prompt=prompts['user'])

        full_content = ""
        parser = PrefixReasoningStreamParser()
        for chunk in self.llm.stream(messages):
            content = getattr(chunk, "content", "")
            if content:
                _, visible = parser.push(content)
                if not visible:
                    continue
                full_content += visible
                yield {
                    'type': 'chunk',
                    'content': visible,
                    'total_chars': len(full_content)
                }
        _, trailing_visible = parser.flush()
        if trailing_visible:
            full_content += trailing_visible
            yield {
                'type': 'chunk',
                'content': trailing_visible,
                'total_chars': len(full_content)
            }
        
        try:
            content = self._clean_markdown_block(full_content)
            
            yield {
                'type': 'done',
                'outline': content.strip(),
                'total_chars': len(full_content)
            }
        except Exception as e:
            yield {
                'type': 'error',
                'message': f"解析大纲 Markup 失败: {e}"
            }

    def _clean_markdown_block(self, text: str) -> str:
        """Extract content from potential markdown code blocks."""
        text = text.strip()
        if text.startswith("```"):
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline + 1:]
            if text.endswith("```"):
                text = text[:-3]
        return text.strip()

    def _clean_json_block(self, text: str) -> str:
        """提取 JSON 文本，兼容 markdown 代码块包裹。"""
        cleaned = self._clean_markdown_block(text)
        start = cleaned.find('{')
        end = cleaned.rfind('}')
        if start != -1 and end != -1 and end >= start:
            return cleaned[start:end + 1]
        return cleaned

    # tool_rules 已迁入 showrunner.yaml 的 tool_rules 字段，
    # 基类 _build_tool_system_prompt 会自动加载并追加，无需再重写此方法。

    def _get_tool_prompt_references(self) -> dict[str, list[dict]]:
        return {
            "rewrite_synopsis": [{"prompt_key": "generate_synopsis", "field": "system"}],
            "rewrite_beat_sheet": [{"prompt_key": "generate_beat_sheet", "field": "system"}],
            "rewrite_outline": [{"prompt_key": "generate_outline", "field": "system"}],
        }

    def _get_tool_prompt_reference_values(self) -> dict[str, dict[str, str]]:
        return {
            "generate_synopsis": {
                "logline": "（由当前对话任务决定）",
                "worldview": "（由当前项目与上下文提供）",
                "roles": "（由当前项目与上下文提供）",
                "guidance": "（由用户当前修改要求决定）",
                "style_profile": "（未提供）",
                "length_hint": "",
            },
            "generate_beat_sheet": {
                "synopsis": "（由当前项目与上下文提供）",
                "worldview": "（由当前项目与上下文提供）",
                "roles": "（由当前项目与上下文提供）",
                "guidance": "（由用户当前修改要求决定）",
                "style_profile": "（未提供）",
                "length_hint": "",
            },
            "generate_outline": {
                "worldview": "（由当前项目与上下文提供）",
                "roles": "（由当前项目与上下文提供）",
                "context": "（由当前项目与上下文提供）",
                "beat_sheet": "（由当前项目与上下文提供）",
                "guidance": "（由用户当前修改要求决定）",
                "style_profile": "（未提供）",
                "chapter_count": "按实际任务决定，尽量贴合章节目标",
                "scene_count_per_chapter": "按实际任务决定，仅作为场景密度参考",
            },
        }

    def _execute_tool_calls(self, tool_calls: list) -> str:
        """执行工具调用并返回结果。"""
        return super()._execute_tool_calls(tool_calls)

    def chat(self, user_message: str, history: list = None, active_context: str = None) -> str:
        """支持工具调用的对话入口。LLM 自主决定是否调用修改工具。"""
        return super().chat(user_message, history=history, active_context=active_context)

    def chat_stream(self, user_message: str, history: list = None, active_context: str = None, **kwargs):
        """支持工具调用的流式对话入口。"""
        yield from super().chat_stream(user_message, history=history, active_context=active_context, **kwargs)
