"""
Outline Markup Parser (Server-side)

将轻量级的 Outline Markup (大纲标记文本) 解析为结构化的字典/JSON树。
支持纯粹的长文本散文推演，不强制 JSON 格式。

兼容说明：本模块的 ``chapter``/``scene`` 节点类型、Chapter 标题和场景
Markup 都是历史大纲协议名，不是用户界面的固定术语。项目为 script 时，
物理落盘层映射为“剧幕/场景”；项目为 novel 时映射为“分卷/章节”。
不要据内部字段名推断 UI 语义，也不要改这些协议键，否则历史大纲和前端
解析将失去兼容。
"""

import re
from typing import Dict, Any, List

def parse_outline_markup(text: str) -> Dict[str, Any]:
    """
    解析大纲 Markup 文本。

    返回的节点类型 ``chapter``/``scene`` 是历史逻辑索引协议；它们不直接
    表示物理文件夹/文件，物理称谓由项目 ``workspace_mode`` 决定。
    
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
        # 历史协议字段：chapter 节点是逻辑 story_group，scene 子节点是逻辑
        # story_unit；不要把它们直接当成用户可见的文件夹/文件称谓。
        "nodes": []
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
            
        # 历史协议中的 chapter 逻辑分组处理 (##)，不是固定的“章节”UI 称谓。
        chapter_match = re.match(
            r'^##\s+(?:Chapter\s*(\d+)\s*[:：]?\s*)?(.+)$',
            line,
            re.IGNORECASE,
        )
        if chapter_match:
            # 如果有前一个逻辑分组且没保存 story_unit，说明只有分组概述。
            # 无论如何，开启新的历史 chapter 节点。
            chapter_number = int(chapter_match.group(1)) if chapter_match.group(1) else len(outline_data["nodes"]) + 1
            title = chapter_match.group(2).strip()
            current_chapter = {
                "id": _generate_id("chap"),
                "name": title,
                "title": title,
                "type": "chapter",
                "chapter": chapter_number,
                "description": "",
                "children": []
            }
            outline_data["nodes"].append(current_chapter)
            current_scene = None
            i += 1
            continue
            
        # 历史协议中的 scene 逻辑单元处理 (###)，不是固定的“场景”UI 称谓。
        scene_match = re.match(
            r'^###\s+(?:(?:场景|Scene)\s*)?(?:(\d+)\s*[-－—_]\s*(\d+)\s*[:：]?\s*)?(.+)$',
            line,
            re.IGNORECASE,
        )
        # 编号属于结构协议，解析后不得混入用户可见标题。
        if scene_match:
            title = scene_match.group(3).strip()
            
            # 如果找不到挂载的逻辑分组，就建一个虚拟 chapter 节点（错误兜底）。
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
                "chapter_num": int(scene_match.group(1)) if scene_match.group(1) else None,
                "scene_num": int(scene_match.group(2)) if scene_match.group(2) else len(current_chapter["children"]) + 1,
                "guide": "",
                "description": "",
                "characters": [],
                "mood": "",
                "tension": "",
                "beat_refs": [],
                "key_dialogues": [],
                "location": "",
                "time": "",
                "pre_state": "",
                "objective": "",
                "conflict": "",
                "turn": "",
                "post_state": "",
                "knowledge_before": "",
                "knowledge_after": "",
                "forbidden_setup": "",
                "causal_dependencies": [],
                "setup_refs": [],
                "payoff_refs": [],
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
                    kv = re.split(r':|：', part, maxsplit=1)
                    if len(kv) == 2:
                        k = kv[0].strip()
                        v = kv[1].strip()
                        if '情绪' in k or 'mood' in k.lower():
                            current_scene['mood'] = v
                        elif '张力' in k or 'tension' in k.lower():
                            current_scene['tension'] = v
                        elif '节拍' in k or 'beat' in k.lower():
                            current_scene['beat_refs'] = _parse_beat_refs(v)
                        elif '出场' in k or '登场' in k or '人物' in k or '角色' in k or 'characters' in k.lower():
                            # 切分人物列表
                            chars = [c.strip() for c in re.split(r'[,，、]', v) if c.strip()]
                            current_scene['characters'] = chars
                        elif 'guide' in k.lower() or '指引' in k:
                            current_scene['guide'] = v
                        elif '地点' in k or 'location' in k.lower():
                            current_scene['location'] = v
                        elif '时间' in k or 'time' in k.lower():
                            current_scene['time'] = v
                        elif '前置状态' in k or '入场状态' in k or 'pre_state' in k.lower():
                            current_scene['pre_state'] = v
                        elif '目标' in k or 'objective' in k.lower():
                            current_scene['objective'] = v
                        elif '冲突' in k or 'conflict' in k.lower():
                            current_scene['conflict'] = v
                        elif '转折' in k or 'turn' in k.lower():
                            current_scene['turn'] = v
                        elif '后置状态' in k or '离场状态' in k or 'post_state' in k.lower():
                            current_scene['post_state'] = v
                        elif '知情前' in k or 'knowledge_before' in k.lower():
                            current_scene['knowledge_before'] = v
                        elif '知情后' in k or 'knowledge_after' in k.lower():
                            current_scene['knowledge_after'] = v
                        elif '禁止铺垫' in k or 'forbidden_setup' in k.lower():
                            current_scene['forbidden_setup'] = v
                        elif '因果依赖' in k or 'causal' in k.lower():
                            current_scene['causal_dependencies'] = [
                                item.strip() for item in re.split(r'[,，、;；]', v) if item.strip()
                            ]
                        elif '设置引用' in k or 'setup_refs' in k.lower():
                            current_scene['setup_refs'] = [
                                item.strip() for item in re.split(r'[,，、;；]', v) if item.strip()
                            ]
                        elif '兑现引用' in k or 'payoff_refs' in k.lower():
                            current_scene['payoff_refs'] = [
                                item.strip() for item in re.split(r'[,，、;；]', v) if item.strip()
                            ]
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
                "tension_level": "",
                "pre_state": "",
                "trigger": "",
                "choice_or_action": "",
                "post_state": "",
                "reveal": "",
                "knowledge_change": "",
                "causal_dependencies": [],
                "setup_refs": [],
                "payoff_refs": [],
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
                    kv = re.split(r':|：', part, maxsplit=1)
                    if len(kv) == 2:
                        k = kv[0].strip().lower()
                        v = kv[1].strip()
                        if '类型' in k or 'type' in k:
                            current_beat['beat_type'] = v
                        elif '情感' in k or 'emotion' in k or '心境' in k:
                            current_beat['emotional_goal'] = v
                        elif '张力' in k or 'tension' in k:
                            current_beat['tension_level'] = v
                        elif '前置状态' in k or 'pre_state' in k:
                            current_beat['pre_state'] = v
                        elif '触发' in k or 'trigger' in k:
                            current_beat['trigger'] = v
                        elif '选择' in k or '行动' in k or 'choice' in k or 'action' in k:
                            current_beat['choice_or_action'] = v
                        elif '后置状态' in k or 'post_state' in k:
                            current_beat['post_state'] = v
                        elif '揭示' in k or 'reveal' in k:
                            current_beat['reveal'] = v
                        elif '知情变化' in k or 'knowledge' in k:
                            current_beat['knowledge_change'] = v
                        elif '因果依赖' in k or 'causal' in k:
                            current_beat['causal_dependencies'] = [
                                item.strip() for item in re.split(r'[,，、;；]', v) if item.strip()
                            ]
                        elif '设置引用' in k or 'setup_refs' in k.lower():
                            current_beat['setup_refs'] = [
                                item.strip() for item in re.split(r'[,，、;；]', v) if item.strip()
                            ]
                        elif '兑现引用' in k or 'payoff_refs' in k.lower():
                            current_beat['payoff_refs'] = [
                                item.strip() for item in re.split(r'[,，、;；]', v) if item.strip()
                            ]
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

    ``## Chapter``、``chapter``、``scene`` 和 ``###`` 必须保留为历史协议
    格式；它们只表示逻辑 story_group/story_unit，不代表剧本模式或小说模式
    的用户称谓。
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

    # 这里的变量名和 type 判断沿用历史协议，不能按字面改成用户术语。
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
            beat_refs = scene.get('beat_refs', [])
            if beat_refs:
                meta_parts.append(f"对应节拍：{', '.join(str(item) for item in beat_refs)}")
            guide = scene.get('guide', '')
            if guide:
                meta_parts.append(f"指引：{guide}")
            field_labels = (
                ("地点", "location"),
                ("时间", "time"),
                ("前置状态", "pre_state"),
                ("目标", "objective"),
                ("冲突", "conflict"),
                ("转折", "turn"),
                ("后置状态", "post_state"),
                ("知情前", "knowledge_before"),
                ("知情后", "knowledge_after"),
                ("禁止铺垫", "forbidden_setup"),
            )
            for label, key in field_labels:
                value = str(scene.get(key) or "").strip()
                if value:
                    meta_parts.append(f"{label}：{value}")
            for label, key in (("因果依赖", "causal_dependencies"), ("设置引用", "setup_refs"), ("兑现引用", "payoff_refs")):
                values = scene.get(key) if isinstance(scene.get(key), list) else []
                values = [str(item).strip() for item in values if str(item).strip()]
                if values:
                    meta_parts.append(f"{label}：{', '.join(values)}")
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

        beat_fields = (
            ("前置状态", "pre_state"),
            ("触发", "trigger"),
            ("选择/行动", "choice_or_action"),
            ("后置状态", "post_state"),
            ("揭示", "reveal"),
            ("知情变化", "knowledge_change"),
        )
        for label, key in beat_fields:
            value = str(beat.get(key) or '').strip()
            if value:
                lines.append(f"> {label}：{value}")
        for label, key in (("因果依赖", "causal_dependencies"), ("设置引用", "setup_refs"), ("兑现引用", "payoff_refs")):
            values = beat.get(key) if isinstance(beat.get(key), list) else []
            values = [str(item).strip() for item in values if str(item).strip()]
            if values:
                lines.append(f"> {label}：{', '.join(values)}")

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


def _parse_beat_refs(value: str) -> list[str]:
    """解析节拍引用，避免把 ``[beat 1]`` 按空格拆成两个引用。"""
    text = str(value or "").strip()
    labeled = re.findall(
        r"(?:beat|节拍)\s*[,，:：]?\s*(\d+)",
        text,
        flags=re.IGNORECASE,
    )
    if labeled:
        return [f"Beat {number}" for number in labeled]
    text = text.strip("[]【】")
    return [item.strip() for item in re.split(r"[,，、;；]+", text) if item.strip()]
