"""
Agent Context Provider

统一的上下文加载器，为各类创作 Agent 提供其所需的业务数据上下文。
"""

import os
import json
from typing import Optional, List, Dict, Any

from core.utils import get_project_path, get_project_stories_path
from agents.routes.context_builder import build_story_tags_hint, load_project_context_bundle
from core.project_settings import get_project_story_tags
from story.file_naming import resolve_story_file_path


class AgentContextProvider:
    """
    根据 Agent 类型，加载并格式化相关业务数据作为对话上下文。
    """

    def __init__(self, user_id: str, project_name: str):
        self.user_id = str(user_id)
        self.project_name = project_name
        self.project_path = get_project_path(user_id, project_name) if project_name else None
        self._bundle_cache: Optional[Dict[str, Any]] = None

    def _bundle(self) -> Dict[str, Any]:
        if self._bundle_cache is None:
            if not self.project_name:
                self._bundle_cache = {}
            else:
                self._bundle_cache = load_project_context_bundle(self.user_id, self.project_name)
        return self._bundle_cache or {}

    # ==================== Muse Agent ====================

    def get_inspirations_context(self, limit: int = 5) -> str:
        """获取与当前项目相关的灵感列表作为上下文。

        关键策略（详见 mcp_server/spark_inspiration/logic.py 顶部注释）：
        - 仅返回 project_links 命中当前项目的灵感，**草稿绝不进 prompt**；
        - 当前项目命中 0 条 / 无项目上下文 → 返回空字符串，不注入任何灵感；
        - 跨项目串台问题在这里被消除：切到项目 B 时，绝不会把项目 A 的灵感塞给 LLM；
        - 用户希望看到草稿/全部灵感时，应通过 list_inspirations 工具主动检索。
        """
        if not self.project_name:
            # 无项目语境时，灵感库一律不进 prompt（保持 Muse 在“项目外聊天”时的中立性）
            return ""

        try:
            from mcp_server.spark_inspiration.logic import get_inspirations_for_project
            inspirations = get_inspirations_for_project(self.user_id, self.project_name)
            if not inspirations:
                return ""

            inspirations = inspirations[:limit]
            lines = [f"### 项目「{self.project_name}」已绑定的灵感"]
            for i, insp in enumerate(inspirations, 1):
                source = (insp.get("source") or "")[:100]
                content = (insp.get("content") or "")[:300]
                timestamp = (insp.get("timestamp") or "")[:10]

                # 提取核心概念（如果有）
                logline = ""
                if content:
                    for line in content.split("\n"):
                        if "核心概念" in line or "Logline" in line:
                            logline = line.split(":", 1)[-1].strip()[:150]
                            break

                entry = f"{i}. [{timestamp}] 源: \"{source}\""
                if logline:
                    entry += f" → {logline}"
                lines.append(entry)

            lines.append(
                "（如需查看用户的草稿或其他项目灵感，请主动调用 list_inspirations 工具，"
                "默认仅展示当前项目已绑定的灵感。）"
            )
            return "\n".join(lines)
        except Exception as e:
            print(f"[ContextProvider] Error loading inspirations: {e}")
            return ""

    # ==================== Showrunner Agent ====================

    def get_synopsis_context(self) -> str:
        """获取梗概上下文"""
        data = self._bundle().get("synopsis_data") or {}
        if not data:
            return ""
        title = data.get("title", "未命名")
        logline = data.get("logline", "")
        themes = data.get("themes", [])

        parts = [f"【梗概】{title}"]
        if logline:
            parts.append(f"核心概念: {logline[:200]}")
        if themes:
            parts.append(f"主题: {', '.join(themes[:5])}")

        return "\n".join(parts)

    def get_beat_sheet_context(self) -> str:
        """获取节拍表上下文"""
        data = self._bundle().get("beats_data") or {}
        beats = data.get("beats", []) if isinstance(data, dict) else []
        if not beats:
            return ""

        beat_names = [b.get("name") or b.get("type") or f"Beat{i+1}" for i, b in enumerate(beats)]
        return f"【节拍表】共{len(beats)}个节拍: {', '.join(beat_names)}"

    def get_outline_summary(self) -> str:
        """获取大纲摘要（章节 + 场景层级，与 list_chapters 工具输出格式一致）"""
        data = self._bundle().get("outline_data") or {}
        nodes = data.get("nodes", []) if isinstance(data, dict) else []
        if not nodes:
            return ""

        lines = [f"【大纲】共 {len(nodes)} 个章节"]
        for i, node in enumerate(nodes):
            title = node.get("title") or node.get("name") or f"章节{i+1}"
            children = node.get("children", [])
            desc = node.get("description") or ""
            lines.append(f"  [{i}] {title}  ({len(children)} 个场景)")
            if desc:
                lines.append(f"    摘要: {desc}")
            for j, scene in enumerate(children):
                scene_title = scene.get("title") or scene.get("name") or f"场景{j+1}"
                lines.append(f"    - [{i}-{j}] {scene_title}")

        return "\n".join(lines)

    def get_outline_full(self) -> str:
        """获取完整大纲（JSON 格式，用于深度分析）"""
        data = self._bundle().get("outline_data") or {}
        if not data:
            return ""
        try:
            return json.dumps(data, ensure_ascii=False, indent=2)
        except Exception:
            return ""

    # ==================== Scriptwriter Agent ====================

    def get_scene_list(self) -> str:
        """获取场景列表概览"""
        if not self.project_path:
            return ""
        try:
            stories_path = get_project_stories_path(self.user_id, self.project_name)
            if not os.path.exists(stories_path):
                return ""
            
            lines = ["### 当前场景文件"]
            
            def scan_dir(path, prefix=""):
                items = []
                for item in sorted(os.listdir(path)):
                    if item.startswith("."):
                        continue
                    item_path = os.path.join(path, item)
                    if os.path.isdir(item_path):
                        items.append(f"{prefix}📁 {item}/")
                        items.extend(scan_dir(item_path, prefix + "  "))
                    elif item.lower().endswith((".arc", ".md")):
                        display_name, _ = os.path.splitext(item)
                        items.append(f"{prefix}📄 {display_name}")
                return items
            
            file_list = scan_dir(stories_path)
            if not file_list:
                return ""
            
            lines.extend(file_list)
            
            return "\n".join(lines)
        except Exception as e:
            print(f"[ContextProvider] Error listing scenes: {e}")
            return ""

    def get_scene_content(self, file_path: str) -> str:
        """获取指定场景文件内容"""
        if not self.project_path or not file_path:
            return ""
        try:
            stories_path = get_project_stories_path(self.user_id, self.project_name)
            full_path, file_format, _ = resolve_story_file_path(stories_path, file_path)
            if not full_path or not file_format or not os.path.exists(full_path):
                return ""
            
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()

            code_language = "markdown" if file_format == "novel" else "arc"
            return f"### 场景内容: {file_path}\n```{code_language}\n{content}\n```"
        except Exception as e:
            print(f"[ContextProvider] Error loading scene: {e}")
            return ""

    def get_worldview_context(self) -> str:
        """获取世界观上下文"""
        content = self._bundle().get("worldview") or ""
        if not content.strip():
            return ""
        return f"### 世界观设定\n{content}"

    def get_characters_context(self) -> str:
        """获取角色列表及简要描述"""
        return self._bundle().get("characters_summary") or ""

    def _build_story_tags_block(self) -> str:
        """从项目设置读取 story tags，并通过统一格式化入口注入上下文。"""
        if not self.project_name:
            return ""
        
        try:
            tags = get_project_story_tags(self.user_id, self.project_name)
        except Exception as e:
            print(f"[ContextProvider] Error loading story tags: {e}")
            tags = {}

        return build_story_tags_hint(tags)

    # ==================== Lorebook Agent ====================

    def get_all_characters_summary(self) -> str:
        """获取所有角色的详细摘要（用于设定专家）"""
        return self._bundle().get("characters_detailed_summary") or ""

    # ==================== Context Dispatcher ====================

    def build_context_for_agent(self, agent_id: str, extra_context: str = "") -> str:
        """
        根据 Agent 类型构建完整的上下文字符串。
        
        Args:
            agent_id: Agent 标识符
            extra_context: 额外的上下文（如前端传入的 activeContext）
        
        Returns:
            格式化的上下文字符串
        """
        parts: List[str] = []

        # 所有 Agent 统一注入项目级 story tags（含 POV 醒目优化），除了风格和工具 Agent
        if agent_id not in ("agent_style", "agent_utility"):
            story_tags_block = self._build_story_tags_block()
            if story_tags_block:
                parts.append(story_tags_block)

        if agent_id == "agent_muse":
            # Muse: 灵感列表
            insp = self.get_inspirations_context(limit=5)
            if insp:
                parts.append(insp)
        
        elif agent_id == "agent_showrunner":
            # Showrunner: 故事结构
            synopsis = self.get_synopsis_context()
            beats = self.get_beat_sheet_context()
            outline = self.get_outline_summary()
            
            if synopsis or beats or outline:
                parts.append("### 当前故事结构")
                if synopsis:
                    parts.append(synopsis)
                if beats:
                    parts.append(beats)
                if outline:
                    parts.append(outline)
        
        elif agent_id == "agent_scriptwriter":
            # ScriptWriter：通过 context_builder 加载全量数据
            # 全量世界观 / 全量角色档案 / 完整大纲 / 叙事记忆
            # 对话链路（chat / 导演委派）与批量链路（compose / auto_write）统一数据来源
            try:
                bundle = self._bundle()
                worldview = bundle.get("worldview", "")
                roles = bundle.get("roles", "")
                full_outline = bundle.get("full_outline", "")
                narrative_memory = bundle.get("narrative_memory", "")

                if worldview:
                    parts.append(f"### 世界观设定\n{worldview}")
                if roles:
                    parts.append(f"### 角色详细档案（全量）\n{roles}")
                if full_outline:
                    parts.append(f"### 全局大纲\n{full_outline}")
                if narrative_memory:
                    parts.append(f"### 叙事记忆（梗概 + 节拍表）\n{narrative_memory}")
                # 场景文件列表仍保留（供导演了解当前写作进度）
                scenes = self.get_scene_list()
                if scenes:
                    parts.append(scenes)
            except Exception as e:
                print(f"[ContextProvider] Error loading full scriptwriter context: {e}")
                # Fallback：退回摘要级上下文，避免服务中断
                worldview = self.get_worldview_context()
                characters = self.get_characters_context()
                outline = self.get_outline_summary()
                scenes = self.get_scene_list()
                if worldview:
                    parts.append(worldview)
                if characters:
                    parts.append(characters)
                if outline:
                    parts.append(outline)
                if scenes:
                    parts.append(scenes)

        
        elif agent_id == "agent_lorebook":
            # Lorebook: 世界观 + 角色详情
            worldview = self.get_worldview_context()
            characters = self.get_all_characters_summary()
            
            if worldview:
                parts.append(worldview)
            if characters:
                parts.append(characters)
        
        elif agent_id == "agent_director":
            # 导演：需要感知项目实时整体状态，以便正确调度专家、判断哪些步骤已完成
            try:
                bundle = self._bundle()
                worldview = (bundle.get("worldview") or "").strip()
                roles = (bundle.get("roles") or "").strip()
                synopsis = self.get_synopsis_context()
                beats = self.get_beat_sheet_context()
                outline = self.get_outline_summary()
                scenes = self.get_scene_list()  # 仅返回文件名目录结构，不包含剧本内容

                status_parts = []
                if worldview:
                    status_parts.append(f"【已有】世界观（{len(worldview)}字）：\n{worldview}")
                if roles:
                    status_parts.append(f"【已有】角色档案（{len(roles)}字）")
                if synopsis:
                    status_parts.append(synopsis)
                if beats:
                    status_parts.append(beats)
                if outline:
                    status_parts.append(outline)
                if scenes:
                    status_parts.append(scenes)

                if status_parts:
                    parts.append("### 📋 当前项目实时状态")
                    parts.extend(status_parts)
            except Exception as e:
                print(f"[ContextProvider] Error loading director context: {e}")

        elif agent_id == "agent_critic":
            # Critic：需要比普通摘要更完整的上下文，既支持聊天态审稿，也支持导演委派。
            try:
                bundle = self._bundle()
                worldview = bundle.get("worldview", "")
                roles = bundle.get("roles", "")
                full_outline = bundle.get("full_outline", "")
                narrative_memory = bundle.get("narrative_memory", "")

                if worldview:
                    parts.append(f"### 世界观设定\n{worldview}")
                if roles:
                    parts.append(f"### 角色档案\n{roles}")
                if full_outline:
                    parts.append(f"### 全局大纲\n{full_outline}")
                if narrative_memory:
                    parts.append(f"### 叙事记忆（梗概 + 节拍表）\n{narrative_memory}")
                scenes = self.get_scene_list()
                if scenes:
                    parts.append(scenes)
            except Exception as e:
                print(f"[ContextProvider] Error loading critic context: {e}")
                worldview = self.get_worldview_context()
                characters = self.get_characters_context()
                outline = self.get_outline_summary()
                scenes = self.get_scene_list()
                if worldview:
                    parts.append(worldview)
                if characters:
                    parts.append(characters)
                if outline:
                    parts.append(outline)
                if scenes:
                    parts.append(scenes)
        
        # 添加额外上下文（如前端传入的当前编辑内容）
        if extra_context and extra_context.strip():
            parts.append(f"### 当前编辑内容\n{extra_context.strip()}")
        
        return "\n\n".join(parts)


def get_agent_context(user_id: str, project_name: str, agent_id: str, extra_context: str = "") -> str:
    """
    便捷函数：获取指定 Agent 的上下文。
    """
    provider = AgentContextProvider(user_id, project_name)
    return provider.build_context_for_agent(agent_id, extra_context)
