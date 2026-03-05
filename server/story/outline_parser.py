"""
Outline Markup Parser (Server-side)

将轻量级的 Outline Markup (大纲标记文本) 解析为结构化的字典/JSON树。
支持纯粹的长文本散文推演，不强制 JSON 格式。
"""

import re
from typing import Dict, Any, List

def parse_outline_markup(text: str) -> Dict[str, Any]:
    """
    解析大纲 Markup 文本。
    
    格式规范：
    @title 故事标题
    @summary 故事概述
    @theme 核心主题
    
    ## Chapter 1: 章节标题
    （章节前置推演长文本，支持多段落，直到下一个场景或下一个章节）
    
    ### 场景标题 1
    > 情绪：压抑 | 张力：high | 登场：陈探长, 神秘人
    （场景推演描述，全散文）
    @key_dialogue 核心台词预测1
    
    Returns:
        解析后的大纲字典树，兼容原 outline.json 格式。
    """
    outline_data = {
        "title": "未命名故事",
        "summary": "",
        "mainTheme": "",
        "nodes": []  # 章节节点
    }
    
    # 全局信息区
    current_chapter = None
    current_scene = None
    
    lines = text.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        # 提取全局 Meta 标签，例如 @title 故事大标题
        if not current_chapter and not current_scene and line.startswith('@'):
            match = re.match(r'^@(\w+)\s+(.+)$', line)
            if match:
                key, val = match.groups()
                key = key.strip()
                val = val.strip()
                if key == 'title':
                    outline_data['title'] = val
                elif key == 'summary':
                    outline_data['summary'] = val
                elif key == 'theme':
                    outline_data['mainTheme'] = val
            i += 1
            continue
            
        # 章节处理 (##)
        chapter_match = re.match(r'^##\s+(?:Chapter\s*\d*:?\s*)?(.+)$', line, re.IGNORECASE)
        if chapter_match:
            # 如果有前一个章节且没保存过场景，说明只有章节概述。但在我们业务里通常会带着场景一起保存
            # 无论如何，开启新章
            title = chapter_match.group(1).strip()
            current_chapter = {
                "id": _generate_id("chap"),
                "name": title,
                "type": "chapter",
                "description": "",
                "children": []
            }
            outline_data["nodes"].append(current_chapter)
            current_scene = None
            i += 1
            continue
            
        # 场景处理 (###)
        scene_match = re.match(r'^###\s+(?!Scene)(.+)$|^###\s+(?:Scene\s*\d*:?\s*)?(.+)$', line, re.IGNORECASE)
        # 支持 "### 场景标题" 或 "### Scene 1: 场景标题" 
        if scene_match:
            title = scene_match.group(1) or scene_match.group(2)
            title = title.strip()
            
            # 如果找不到挂载的章节，就建一个虚拟章节（错误兜底）
            if not current_chapter:
                current_chapter = {
                    "id": _generate_id("chap"),
                    "name": "未归类章节",
                    "type": "chapter",
                    "description": "",
                    "children": []
                }
                outline_data["nodes"].append(current_chapter)
                
            current_scene = {
                "id": _generate_id("scene"),
                "name": title,
                "type": "scene",
                "guide": "",
                "description": "",
                "characters": [],
                "mood": "",
                "tension": "",
                "key_dialogues": []
            }
            current_chapter["children"].append(current_scene)
            i += 1
            continue
            
        # 场景级元数据处理 (>)
        if current_scene and line.startswith('>'):
            # 处理例如 "> 情绪：压抑 | 张力：high | 登场：陈探长, 神秘人"
            meta_str = line[1:].strip()
            parts = meta_str.split('|')
            for part in parts:
                part = part.strip()
                if ':' in part or '：' in part:
                    # 分割键值对，最多切1次
                    kv = re.split(r':|：', part, 1)
                    if len(kv) == 2:
                        k = kv[0].strip()
                        v = kv[1].strip()
                        if '情绪' in k or 'mood' in k.lower():
                            current_scene['mood'] = v
                        elif '张力' in k or 'tension' in k.lower():
                            current_scene['tension'] = v
                        elif '出场' in k or '登场' in k or '人物' in k or '角色' in k or 'characters' in k.lower():
                            # 切分人物列表
                            chars = [c.strip() for c in re.split(r'[,，、]', v) if c.strip()]
                            current_scene['characters'] = chars
                        elif 'guide' in k.lower() or '指引' in k:
                            current_scene['guide'] = v
            i += 1
            continue
            
        # 特殊标签：key_dialogue (@key_dialogue)
        if current_scene and line.startswith('@key_dialogue'):
            val = line.replace('@key_dialogue', '', 1).strip()
            if val:
                current_scene["key_dialogues"].append(val)
            i += 1
            continue
            
        # 普通文本累加（推演心流内容）
        if line:
            # 如果有当前场景，追加到场景的 description
            if current_scene:
                if current_scene["description"]:
                    current_scene["description"] += "\n"
                current_scene["description"] += line
            # 如果没有当前场景但有当前章，这是"章节前置推演文本"
            elif current_chapter:
                if current_chapter["description"]:
                    current_chapter["description"] += "\n"
                current_chapter["description"] += line
            # 如果什么都没有，追加到开头的 summary 里
            else:
                if outline_data["summary"]:
                    outline_data["summary"] += "\n"
                outline_data["summary"] += line
                
        i += 1
        
    # 计算统计信息
    outline_data["totalChapters"] = len(outline_data["nodes"])
    outline_data["estimatedScenes"] = sum(len(c.get("children", [])) for c in outline_data["nodes"])
    
    return outline_data

import uuid

def _generate_id(prefix: str = "node") -> str:
    """生成简单的短ID (模拟前端所需)"""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"

def parse_beat_sheet_markup(text: str) -> Dict[str, Any]:
    """
    解析节拍表 Markup 文本。
    
    格式规范：
    @arc 整个故事的情感弧光描述
    
    ---beat 1
    > 类型：开场 | 情感目标：不安 | 张力：Low
    （纯散文推演的节拍内容，长文本，支持多段落换行）
    
    Returns:
        兼容原 { beats: [...], global_emotional_arc: "" } 的字典
    """
    result = {
        "global_emotional_arc": "",
        "beats": []
    }
    
    current_beat = None
    lines = text.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        # 全局情感曲线
        if not current_beat and line.startswith("@arc"):
            val = line.replace("@arc", "", 1).strip()
            if val:
                result["global_emotional_arc"] += val + "\n"
            i += 1
            continue
            
        # 匹配节拍开始 (支持 "---beat 1" 或 "--- beat 1" 或 "---节拍 1")
        beat_match = re.match(r'^---\s*(?:beat|节拍)\s*(\d+)?(.*)$', line, re.IGNORECASE)
        if beat_match:
            beat_id = beat_match.group(1)
            # 新建 current_beat
            current_beat = {
                "beat_id": int(beat_id) if beat_id else len(result["beats"]) + 1,
                "beat_type": "",
                "narrative_action": "",
                "emotional_goal": "",
                "reader_experience": "",
                "tension_level": ""
            }
            result["beats"].append(current_beat)
            i += 1
            continue
            
        # 匹配元数据行 "> 类型: 开场 | 情感目标: 不安 | 张力: Low"
        if current_beat and line.startswith('>'):
            meta_str = line[1:].strip()
            parts = meta_str.split('|')
            for part in parts:
                if ':' in part or '：' in part:
                    kv = re.split(r':|：', part, 1)
                    if len(kv) == 2:
                        k = kv[0].strip().lower()
                        v = kv[1].strip()
                        if '类型' in k or 'type' in k:
                            current_beat['beat_type'] = v
                        elif '情感' in k or 'emotion' in k or '心境' in k:
                            current_beat['emotional_goal'] = v
                        elif '张力' in k or 'tension' in k:
                            current_beat['tension_level'] = v
            i += 1
            continue
            
        # 散文内容归入 narrative_action 和 reader_experience (我们把文本均塞在 narrative_action，因为去格式化后这些界限模糊，不影响供AI参考)
        if line and current_beat:
            if current_beat["narrative_action"]:
                current_beat["narrative_action"] += "\n"
            current_beat["narrative_action"] += line
            
        # 如果还在头部，归入 global_arc
        elif line and not current_beat:
            result["global_emotional_arc"] += line + "\n"
            
        i += 1
        
    result["global_emotional_arc"] = result["global_emotional_arc"].strip()
    return result

