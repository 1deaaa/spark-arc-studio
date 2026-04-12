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
        解析后的大纲字典树，兼容前端 OutlineData 格式。
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
                "title": title,
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
                    "name": "生成错误",
                    "title": "生成错误",
                    "type": "chapter",
                    "description": "",
                    "children": []
                }
                outline_data["nodes"].append(current_chapter)
                
            current_scene = {
                "id": _generate_id("scene"),
                "name": title,
                "title": title,
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


def parse_synopsis_markup(text: str) -> Dict[str, Any]:
    """
    解析梗概 Markup 文本。

    格式规范：
    @title 故事标题
    @logline 核心概念一句话
    @theme 主题1, 主题2
    @pacing 叙事节奏建议
    @chapters 预估章节数

    （梗概正文，支持多段落散文推演）

    Returns:
        兼容原 synopsis JSON 格式的字典。
    """
    result: Dict[str, Any] = {
        "title": "",
        "logline": "",
        "synopsis_text": "",
        "themes": [],
        "pacing_guide": "",
        "narrative_pov": "",
        "estimated_chapters": "",
    }

    if not text or not isinstance(text, str):
        return result

    body_lines: List[str] = []

    for raw_line in text.split('\n'):
        line = raw_line.strip()

        # 提取 @key value 元数据
        if line.startswith('@'):
            match = re.match(r'^@(\w+)\s+(.+)$', line)
            if match:
                key, val = match.group(1).strip().lower(), match.group(2).strip()
                if key == 'title':
                    result['title'] = val
                elif key == 'logline':
                    result['logline'] = val
                elif key == 'theme' or key == 'themes':
                    # 支持逗号、顿号分隔
                    result['themes'] = [t.strip() for t in re.split(r'[,，、]', val) if t.strip()]
                elif key == 'pacing':
                    result['pacing_guide'] = val
                elif key == 'pov':
                    result['narrative_pov'] = val
                elif key == 'chapters':
                    result['estimated_chapters'] = val
                continue

        # 非元数据行归入正文
        if line:
            body_lines.append(line)

    result['synopsis_text'] = '\n'.join(body_lines).strip()
    return result


# ==================== 序列化器 ====================

def serialize_outline_to_markup(outline: Dict[str, Any]) -> str:
    """
    将大纲字典序列化为 Outline Markup 文本。
    供前端编辑保存时使用。
    """
    lines: List[str] = []

    title = outline.get('title', '')
    if title:
        lines.append(f"@title {title}")

    summary = outline.get('summary', '')
    if summary:
        lines.append(f"@summary {summary}")

    main_theme = outline.get('mainTheme', '')
    if main_theme:
        lines.append(f"@theme {main_theme}")

    if any(l for l in lines):
        lines.append('')

    for ci, chapter in enumerate(outline.get('nodes', [])):
        if chapter.get('type') != 'chapter':
            continue
        ch_title = chapter.get('title') or chapter.get('name') or f'章节{ci + 1}'
        ch_num = ci + 1
        lines.append(f"## Chapter {ch_num}: {ch_title}")

        ch_desc = (chapter.get('description') or '').strip()
        if ch_desc:
            lines.append(ch_desc)

        for scene in chapter.get('children', []):
            sc_title = scene.get('title') or scene.get('name') or '未命名场景'
            lines.append(f"### {sc_title}")

            # 场景元数据
            meta_parts = []
            mood = scene.get('mood', '')
            if mood:
                meta_parts.append(f"情绪：{mood}")
            tension = scene.get('tension', '')
            if tension:
                meta_parts.append(f"张力：{tension}")
            characters = scene.get('characters', [])
            if characters:
                meta_parts.append(f"登场：{', '.join(characters)}")
            if meta_parts:
                lines.append("> " + " | ".join(meta_parts))

            sc_desc = (scene.get('description') or '').strip()
            if sc_desc:
                lines.append(sc_desc)

            for dlg in scene.get('key_dialogues', []):
                if dlg:
                    lines.append(f"@key_dialogue {dlg}")

        lines.append('')

    return '\n'.join(lines).strip()


def serialize_beat_sheet_to_markup(beats_data: Dict[str, Any]) -> str:
    """
    将节拍表字典序列化为 Beat Sheet Markup 文本。
    """
    lines: List[str] = []

    arc = beats_data.get('global_emotional_arc', '')
    if arc:
        lines.append(f"@arc {arc}")
        lines.append('')

    for beat in beats_data.get('beats', []):
        beat_id = beat.get('beat_id', 0)
        lines.append(f"---beat {beat_id}")

        meta_parts = []
        beat_type = beat.get('beat_type', '')
        if beat_type:
            meta_parts.append(f"类型：{beat_type}")
        emotional_goal = beat.get('emotional_goal', '')
        if emotional_goal:
            meta_parts.append(f"情感目标：{emotional_goal}")
        tension_level = beat.get('tension_level', '')
        if tension_level:
            meta_parts.append(f"张力：{tension_level}")
        if meta_parts:
            lines.append("> " + " | ".join(meta_parts))

        narrative = (beat.get('narrative_action') or '').strip()
        if narrative:
            lines.append(narrative)

        lines.append('')

    return '\n'.join(lines).strip()


def serialize_synopsis_to_markup(synopsis: Dict[str, Any]) -> str:
    """
    将梗概字典序列化为 Synopsis Markup 文本。
    """
    lines: List[str] = []

    title = synopsis.get('title', '')
    if title:
        lines.append(f"@title {title}")

    logline = synopsis.get('logline', '')
    if logline:
        lines.append(f"@logline {logline}")

    themes = synopsis.get('themes', [])
    if themes:
        lines.append(f"@theme {', '.join(themes)}")

    pacing = synopsis.get('pacing_guide', '')
    if pacing:
        lines.append(f"@pacing {pacing}")

    pov = synopsis.get('narrative_pov', '')
    if pov:
        lines.append(f"@pov {pov}")

    chapters = synopsis.get('estimated_chapters', '')
    if chapters:
        lines.append(f"@chapters {chapters}")

    # 元数据和正文之间加空行
    if any(l for l in lines):
        lines.append('')

    synopsis_text = (synopsis.get('synopsis_text') or '').strip()
    if synopsis_text:
        lines.append(synopsis_text)

    return '\n'.join(lines).strip()

