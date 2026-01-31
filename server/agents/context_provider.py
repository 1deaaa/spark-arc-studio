"""
Agent Context Provider

统一的上下文加载器，为各类创作 Agent 提供其所需的业务数据上下文。
"""

import os
import json
from typing import Optional, List, Dict, Any

from core.utils import get_project_path, get_project_stories_path


class AgentContextProvider:
    """
    根据 Agent 类型，加载并格式化相关业务数据作为对话上下文。
    """

    def __init__(self, user_id: str, project_name: str):
        self.user_id = str(user_id)
        self.project_name = project_name
        self.project_path = get_project_path(user_id, project_name) if project_name else None

    # ==================== Muse Agent ====================

    def get_inspirations_context(self, limit: int = 5) -> str:
        """获取最近的灵感列表作为上下文"""
        try:
            from mcp_server.spark_inspiration.logic import get_all_inspirations
            inspirations = get_all_inspirations(self.user_id)[:limit]
            if not inspirations:
                return ""
            
            lines = ["### 你最近生成的灵感"]
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
            
            return "\n".join(lines)
        except Exception as e:
            print(f"[ContextProvider] Error loading inspirations: {e}")
            return ""

    # ==================== Showrunner Agent ====================

    def get_synopsis_context(self) -> str:
        """获取梗概上下文"""
        if not self.project_path:
            return ""
        try:
            synopsis_path = os.path.join(self.project_path, "synopsis.json")
            if not os.path.exists(synopsis_path):
                return ""
            with open(synopsis_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            title = data.get("title", "未命名")
            logline = data.get("logline", "")
            themes = data.get("themes", [])
            
            parts = [f"【梗概】{title}"]
            if logline:
                parts.append(f"核心概念: {logline[:200]}")
            if themes:
                parts.append(f"主题: {', '.join(themes[:5])}")
            
            return "\n".join(parts)
        except Exception as e:
            print(f"[ContextProvider] Error loading synopsis: {e}")
            return ""

    def get_beat_sheet_context(self) -> str:
        """获取节拍表上下文"""
        if not self.project_path:
            return ""
        try:
            beat_path = os.path.join(self.project_path, "beat_sheet.json")
            if not os.path.exists(beat_path):
                return ""
            with open(beat_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            beats = data.get("beats", [])
            if not beats:
                return ""
            
            beat_names = [b.get("name", f"Beat{i+1}") for i, b in enumerate(beats[:10])]
            return f"【节拍表】共{len(beats)}个节拍: {', '.join(beat_names)}"
        except Exception as e:
            print(f"[ContextProvider] Error loading beat sheet: {e}")
            return ""

    def get_outline_summary(self) -> str:
        """获取大纲摘要（仅标题层级）"""
        if not self.project_path:
            return ""
        try:
            outline_path = os.path.join(self.project_path, "outline.json")
            if not os.path.exists(outline_path):
                return ""
            with open(outline_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            nodes = data.get("nodes", [])
            if not nodes:
                return ""
            
            titles = []
            for node in nodes[:15]:
                title = node.get("title", "未命名章节")
                titles.append(title)
            
            return f"【大纲】共{len(nodes)}章: {', '.join(titles)}"
        except Exception as e:
            print(f"[ContextProvider] Error loading outline: {e}")
            return ""

    def get_outline_full(self) -> str:
        """获取完整大纲（JSON 格式，用于深度分析）"""
        if not self.project_path:
            return ""
        try:
            outline_path = os.path.join(self.project_path, "outline.json")
            if not os.path.exists(outline_path):
                return ""
            with open(outline_path, "r", encoding="utf-8") as f:
                return f.read()[:8000]  # 限制大小
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
                    elif item.endswith(".arc"):
                        items.append(f"{prefix}📄 {item[:-4]}")
                return items
            
            file_list = scan_dir(stories_path)
            if not file_list:
                return ""
            
            lines.extend(file_list[:30])  # 限制显示数量
            if len(file_list) > 30:
                lines.append(f"  ...及另外 {len(file_list) - 30} 个文件")
            
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
            full_path = os.path.join(stories_path, file_path)
            if not full_path.endswith(".arc"):
                full_path += ".arc"
            
            if not os.path.exists(full_path):
                return ""
            
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # 限制大小
            if len(content) > 10000:
                content = content[:10000] + "\n...(内容过长已截断)"
            
            return f"### 场景内容: {file_path}\n```arc\n{content}\n```"
        except Exception as e:
            print(f"[ContextProvider] Error loading scene: {e}")
            return ""

    def get_worldview_context(self) -> str:
        """获取世界观上下文"""
        if not self.project_path:
            return ""
        try:
            # 尝试两种可能的文件名
            for filename in ["世界观.txt", "worldview.txt"]:
                wv_path = os.path.join(self.project_path, filename)
                if os.path.exists(wv_path):
                    with open(wv_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    if content.strip():
                        # 限制大小
                        if len(content) > 5000:
                            content = content[:5000] + "\n...(内容过长已截断)"
                        return f"### 世界观设定\n{content}"
            return ""
        except Exception as e:
            print(f"[ContextProvider] Error loading worldview: {e}")
            return ""

    def get_characters_context(self) -> str:
        """获取角色列表及简要描述"""
        if not self.project_path:
            return ""
        try:
            chr_path = os.path.join(self.project_path, "chr")
            bind_path = os.path.join(chr_path, "chr.bind")
            
            if not os.path.exists(bind_path):
                return ""
            
            with open(bind_path, "r", encoding="utf-8") as f:
                mapping = json.load(f)
            
            if not mapping:
                return ""
            
            lines = ["### 角色列表"]
            for char_id, char_info in list(mapping.items())[:20]:
                if char_id == "-1":
                    continue  # 跳过旁白
                
                if isinstance(char_info, dict):
                    name = char_info.get("name", f"角色{char_id}")
                    desc = char_info.get("desc", "")[:100]
                else:
                    name = str(char_info)
                    desc = ""
                
                # 尝试读取详细设定
                if not desc:
                    detail_path = os.path.join(chr_path, f"{char_id}.txt")
                    if os.path.exists(detail_path):
                        with open(detail_path, "r", encoding="utf-8") as f:
                            desc = f.read()[:150]
                
                entry = f"- {name}"
                if desc:
                    entry += f": {desc.replace(chr(10), ' ')[:100]}..."
                lines.append(entry)
            
            return "\n".join(lines)
        except Exception as e:
            print(f"[ContextProvider] Error loading characters: {e}")
            return ""

    # ==================== Lorebook Agent ====================

    def get_all_characters_summary(self) -> str:
        """获取所有角色的详细摘要（用于设定专家）"""
        if not self.project_path:
            return ""
        try:
            chr_path = os.path.join(self.project_path, "chr")
            bind_path = os.path.join(chr_path, "chr.bind")
            
            if not os.path.exists(bind_path):
                return ""
            
            with open(bind_path, "r", encoding="utf-8") as f:
                mapping = json.load(f)
            
            if not mapping:
                return ""
            
            lines = ["### 已有角色设定"]
            for char_id, char_info in list(mapping.items())[:15]:
                if char_id == "-1":
                    continue
                
                if isinstance(char_info, dict):
                    name = char_info.get("name", f"角色{char_id}")
                else:
                    name = str(char_info)
                
                # 读取详细设定
                detail_path = os.path.join(chr_path, f"{char_id}.txt")
                detail = ""
                if os.path.exists(detail_path):
                    with open(detail_path, "r", encoding="utf-8") as f:
                        detail = f.read()[:500]
                
                lines.append(f"\n#### {name}")
                if detail:
                    lines.append(detail)
                else:
                    lines.append("(尚无详细设定)")
            
            return "\n".join(lines)
        except Exception as e:
            print(f"[ContextProvider] Error loading character summaries: {e}")
            return ""

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
            # Scriptwriter: 完整创作上下文
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
        
        elif agent_id == "agent_critic":
            # Critic: 世界观摘要 + 角色列表
            worldview = self.get_worldview_context()
            characters = self.get_characters_context()
            
            if worldview:
                # 对 Critic 只提供简化版世界观
                wv_lines = worldview.split("\n")[:20]
                parts.append("\n".join(wv_lines))
            if characters:
                parts.append(characters)
        
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
