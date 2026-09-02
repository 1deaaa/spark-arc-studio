"""
ARC Format Parser (Server-side)

将 .arc 格式的剧本文本解析为内部数据结构（导出 .story JSON 格式）
"""

import json
import re
from typing import List, Dict, Any, Optional, Tuple


SYSTEM_SPEAKER_ID_TO_NAME = {-1: "旁白", -2: "?"}
SYSTEM_SPEAKER_NAME_TO_ID = {name: cid for cid, name in SYSTEM_SPEAKER_ID_TO_NAME.items()}
_SPEAKER_MARKER_RE = re.compile(r'^\[([^\]\r\n]+)\]$')
_NUMERIC_MARKER_RE = re.compile(r'^-?\d+$')


def _normalize_chr_map(chr_map: Optional[Dict[Any, Any]]) -> Dict[int, str]:
    """把角色映射整理为 ``{角色ID: 角色名}``，兼容字符串 key。"""
    normalized: Dict[int, str] = {}
    if not isinstance(chr_map, dict):
        return normalized
    for raw_id, raw_name in chr_map.items():
        try:
            cid = int(raw_id)
        except (TypeError, ValueError):
            continue
        if isinstance(raw_name, dict):
            name = str(raw_name.get("name") or raw_name.get("title") or "").strip()
        else:
            name = str(raw_name or "").strip()
        if not name and cid in SYSTEM_SPEAKER_ID_TO_NAME:
            name = SYSTEM_SPEAKER_ID_TO_NAME[cid]
        if name:
            normalized[cid] = name
    return normalized


def _build_name_to_id(chr_map: Optional[Dict[Any, Any]]) -> Dict[str, int]:
    mapping = {name: cid for cid, name in SYSTEM_SPEAKER_ID_TO_NAME.items()}
    for cid, name in _normalize_chr_map(chr_map).items():
        if name:
            mapping[name] = cid
    return mapping


def is_speaker_marker_line(line: str) -> bool:
    """判断一行是否为 ARC 说话人标记。正式格式为 ``[角色名]``。"""
    return bool(_SPEAKER_MARKER_RE.match(str(line or "").strip()))


def parse_speaker_marker(line: str, chr_map: Optional[Dict[Any, Any]] = None) -> Tuple[Any, str]:
    """解析 ``[说话人]`` 行，返回 ``(chr, speaker)``。

    新规范中 ``speaker`` 是创作层真相；``chr`` 仅在能解析出隐藏绑定 ID 时
    保留给导出和资源绑定。纯数字标记只作为边界脏输入兜底，不是正式写法。
    """
    match = _SPEAKER_MARKER_RE.match(str(line or "").strip())
    if not match:
        raise ValueError(f"不是有效的 ARC 说话人标记: {line!r}")

    marker = match.group(1).strip()
    id_to_name = _normalize_chr_map(chr_map)
    name_to_id = _build_name_to_id(chr_map)

    if _NUMERIC_MARKER_RE.match(marker):
        cid = int(marker)
        speaker = id_to_name.get(cid) or SYSTEM_SPEAKER_ID_TO_NAME.get(cid) or ""
        return cid, speaker

    cid = name_to_id.get(marker)
    if cid is not None:
        return cid, marker
    return marker, marker


def format_speaker_marker(chr_value: Any = None, speaker: str = "", chr_map: Optional[Dict[Any, Any]] = None) -> str:
    """把内部角色字段格式化为正式 ARC 说话人标记。"""
    speaker_text = str(speaker or "").strip()
    if speaker_text:
        return f"[{speaker_text}]"

    try:
        cid = int(chr_value)
    except (TypeError, ValueError):
        marker = str(chr_value or "").strip()
        return f"[{marker or '旁白'}]"

    name = _normalize_chr_map(chr_map).get(cid) or SYSTEM_SPEAKER_ID_TO_NAME.get(cid)
    return f"[{name or cid}]"


def rename_speaker_markers_in_arc_text(arc_text: str, old_name: str, new_name: str) -> Tuple[str, int]:
    """重命名 ARC 正文里的独立说话人标记行，不替换普通正文提及。"""
    old_marker = f"[{str(old_name or '').strip()}]"
    new_marker = f"[{str(new_name or '').strip()}]"
    if old_marker == "[]" or new_marker == "[]" or old_marker == new_marker:
        return arc_text, 0

    changed = 0
    output_lines: List[str] = []
    for raw_line in str(arc_text or "").splitlines(keepends=True):
        if raw_line.endswith("\r\n"):
            body, line_ending = raw_line[:-2], "\r\n"
        elif raw_line.endswith("\n"):
            body, line_ending = raw_line[:-1], "\n"
        else:
            body, line_ending = raw_line, ""

        leading_len = len(body) - len(body.lstrip(" \t"))
        trailing_len = len(body) - len(body.rstrip(" \t"))
        leading = body[:leading_len]
        trailing = body[len(body) - trailing_len:] if trailing_len else ""
        marker = body[leading_len: len(body) - trailing_len if trailing_len else len(body)]
        if marker == old_marker:
            output_lines.append(f"{leading}{new_marker}{trailing}{line_ending}")
            changed += 1
        else:
            output_lines.append(raw_line)

    return "".join(output_lines), changed


def parse_arc(arc_text: str, chr_map: Optional[Dict[Any, Any]] = None) -> List[Dict[str, Any]]:
    """
    解析 .arc 文本为场景数组
    
    Args:
        arc_text: .arc 格式的原始文本
        
    Returns:
        解析后的场景数组，兼容 .story JSON 格式
    """
    scenes = []
    id_counter = [1]
    
    # 按场景标题分割（# 开头的行）
    scene_blocks = _split_by_scenes(arc_text)
    
    for block in scene_blocks:
        scene = _parse_scene_block(block, id_counter, chr_map=chr_map)
        if scene:
            scenes.append(scene)
    
    return scenes


def parse_arc_to_dialogues(arc_text: str, chr_map: Optional[Dict[Any, Any]] = None) -> List[Dict[str, Any]]:
    """
    解析 .arc 文本，仅返回对话数组（不包含场景信息）
    用于续写功能，直接插入到现有场景中
    
    Args:
        arc_text: .arc 格式的原始文本（可能不包含场景标题）
        
    Returns:
        对话节点数组
    """
    # 移除 <conception> 块
    cleaned_text = re.sub(r'<conception>[\s\S]*?</conception>', '', arc_text)
    
    # 解析对话内容
    dialogues = _parse_dialogue_content(cleaned_text, chr_map=chr_map)
    
    return dialogues


def _split_by_scenes(text: str) -> List[str]:
    """将文本按场景标题分割"""
    lines = text.split('\n')
    blocks = []
    current_block = []
    
    for line in lines:
        if re.match(r'^#\s+', line) and current_block:
            blocks.append('\n'.join(current_block))
            current_block = [line]
        else:
            current_block.append(line)
    
    if current_block:
        blocks.append('\n'.join(current_block))
    
    return blocks


def _parse_scene_block(block_text: str, id_counter: List[int], chr_map: Optional[Dict[Any, Any]] = None) -> Optional[Dict[str, Any]]:
    """解析单个场景块"""
    # 提取场景名（# 标题）
    title_match = re.search(r'^#\s+(.+)$', block_text, re.MULTILINE)
    if not title_match:
        return None
    
    scene_name = title_match.group(1).strip()
    
    # 提取 @guide
    guide_match = re.search(r'^@guide\s+(.+)$', block_text, re.MULTILINE)
    guide = guide_match.group(1).strip() if guide_match else ''
    
    # 提取 <conception> 块（每个场景最多一个）
    thought_blocks = re.findall(r'<conception>([\s\S]*?)</conception>', block_text)
    if len(thought_blocks) > 1:
        raise ValueError(f"ARC 格式错误：场景 '{scene_name}' 内包含多个 <conception> 块（每个场景最多一个）。")
    thought = thought_blocks[0].strip() if thought_blocks else ''

    # 移除 <conception> 块（AI构思，解析正文时移除）
    cleaned_text = re.sub(r'<conception>[\s\S]*?</conception>', '', block_text)

    # 提取 @intro（场景引言）并从正文中移除
    intro, cleaned_text = _extract_intro_block(cleaned_text)

    metadata, cleaned_text = _extract_scene_metadata(cleaned_text)
    
    # 解析对话内容
    dia = _parse_dialogue_content(cleaned_text, id_counter, chr_map=chr_map)

    scene_payload = {
        'scene': scene_name,
        'guide': guide,
        'intro': intro or '',
        'thought': thought,
        'dia': dia
    }
    scene_payload.update(metadata)
    
    return scene_payload


def _extract_intro_block(text: str) -> Tuple[str, str]:
    """提取 @intro 块（支持单行与多行），并返回 (intro, text_without_intro)。"""
    lines = text.split('\n')
    output_lines: List[str] = []
    intro_lines: List[str] = []
    in_intro = False

    def is_next_element_start(trimmed: str) -> bool:
        if not trimmed:
            return False
        if trimmed.startswith('#'):
            return True
        if trimmed.startswith('@guide'):
            return True
        if trimmed.startswith('<choice'):
            return True
        if trimmed.startswith('<conception>'):
            return True
        if is_speaker_marker_line(trimmed):
            return True
        return False

    for raw in lines:
        trimmed = raw.strip()

        if not in_intro and trimmed.startswith('@intro'):
            in_intro = True
            rest = re.sub(r'^@intro\s*', '', trimmed)
            if rest:
                intro_lines.append(rest)
            continue

        if in_intro:
            if not trimmed:
                in_intro = False
                continue
            if is_next_element_start(trimmed):
                in_intro = False
                output_lines.append(raw)
                continue
            intro_lines.append(raw.strip())
            continue

        output_lines.append(raw)

    return ('\n'.join(intro_lines).strip(), '\n'.join(output_lines))


SCENE_METADATA_PATTERN = re.compile(r'^@meta\s+(\w+)\s*:\s*(.+)$')


SCENE_METADATA_PARSERS = {
    'button_text': lambda raw: str(raw).strip(),
    'trigger_event': lambda raw: str(raw).strip(),
    'once_key': lambda raw: str(raw).strip(),
    'priority': lambda raw: int(str(raw).strip() or '0'),
    'hiden': lambda raw: str(raw).strip().lower() in {'1', 'true', 'yes', 'on'},
    'hidden': lambda raw: str(raw).strip().lower() in {'1', 'true', 'yes', 'on'},
    'conditions': lambda raw: json.loads(raw),
    'effects': lambda raw: json.loads(raw),
}


def _extract_scene_metadata(text: str) -> Tuple[Dict[str, Any], str]:
    lines = text.split('\n')
    output_lines: List[str] = []
    metadata: Dict[str, Any] = {}

    for raw in lines:
        trimmed = raw.strip()
        match = SCENE_METADATA_PATTERN.match(trimmed)
        if not match:
            output_lines.append(raw)
            continue

        key = match.group(1).strip()
        value = match.group(2).strip()
        parser = SCENE_METADATA_PARSERS.get(key)
        if not parser:
            output_lines.append(raw)
            continue

        try:
            parsed = parser(value)
            if key == 'hidden':
                metadata['hiden'] = parsed
            else:
                metadata[key] = parsed
        except Exception:
            output_lines.append(raw)

    return metadata, '\n'.join(output_lines)


def _parse_dialogue_content(
    text: str,
    id_counter: List[int] = None,
    chr_map: Optional[Dict[Any, Any]] = None,
) -> List[Dict[str, Any]]:
    """解析对话内容（包括选项分支）"""
    if id_counter is None:
        id_counter = [1]
    dialogues = []
    
    # 先处理选项块，替换为占位符
    processed_text, choice_blocks = _extract_choice_blocks(text)
    
    # 按行解析
    lines = processed_text.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        # 跳过空行、标题行、@guide/@intro行
        if not line or line.startswith('#') or line.startswith('@guide') or line.startswith('@intro') or line.startswith('<conception>'):
            i += 1
            continue
        
        # 检查是否是选项占位符
        choice_placeholder = re.match(r'^__CHOICE_(\d+)__$', line)
        if choice_placeholder:
            choice_index = int(choice_placeholder.group(1))
            if choice_index < len(choice_blocks):
                choice_block = choice_blocks[choice_index]
                # 解析选项块并附加到上一个对话节点
                options = _parse_choice_block(choice_block, id_counter, chr_map=chr_map)
                if dialogues:
                    dialogues[-1]['opt'] = options
            i += 1
            continue
        
        # 匹配对话/旁白标识符 [说话人]。正式格式为角色名，数字仅作开发期容错。
        chr_match = _SPEAKER_MARKER_RE.match(line)
        
        if chr_match:
            chr_id, speaker = parse_speaker_marker(line, chr_map=chr_map)
            
            dialogue_lines = []
            next_target = None
            act_commands = {}
            presentation_commands = {}
            thought = ''
            i += 1
            
            while i < len(lines):
                next_line = lines[i].strip()
                # 遇到下一个命令或新场景时停止
                if is_speaker_marker_line(next_line) or next_line.startswith('__CHOICE_') or next_line.startswith('# '):
                    break
                
                # 提取 thought
                thought_match = re.match(r'<conception>([\s\S]*?)</conception>', next_line)
                if thought_match:
                    thought = thought_match.group(1).strip()
                    i += 1
                    continue

                # 检查 @next (允许后面跟标签并忽略)
                next_match = re.match(r'^@next\s+([^\s<]+)', next_line)
                if next_match:
                    next_target = next_match.group(1).strip()
                    i += 1
                    continue
                
                # 检查 @act。旧视觉键只做容错消费，不再迁移到演出字段。
                act_match = re.match(r'^@act\s+(\w+):([^<]+)', next_line)
                if act_match:
                    key = act_match.group(1).strip()
                    value = act_match.group(2).strip()
                    if ',' in value:
                        value = [v.strip() for v in value.split(',')]
                    if key.lower() not in {"bg", "sprite"}:
                        act_commands[key] = value
                    i += 1
                    continue

                # Web 专用演出提示使用 @show 协议，不与 Unity 通用行为节点混用。
                show_match = re.match(
                    r'^@show\s+(\w+):([^<]+)',
                    next_line,
                    re.IGNORECASE,
                )
                if show_match:
                    key = show_match.group(1).strip().lower()
                    value = show_match.group(2).strip()
                    if key not in {'img', 'illustration_prompt'} and ',' in value:
                        value = [v.strip() for v in value.split(',')]
                    presentation_commands[key] = value
                    i += 1
                    continue

                # 旧的 @presentation 指令直接忽略，确保兼容不报错且不混入对白
                if re.match(r'^@presentation\b', next_line, re.IGNORECASE):
                    i += 1
                    continue

                # 未识别或已废弃的指令静默忽略，禁止混入对白正文。
                if next_line.startswith('@'):
                    i += 1
                    continue
                
                # 过滤掉行内残留的标签
                clean_line = re.sub(r'<\/?choice>|<\/?opt(\s+text="[^"]+")?>', '', next_line).strip()
                if clean_line:
                    dialogue_lines.append(clean_line)
                i += 1
            
            if dialogue_lines:
                for idx, line_text in enumerate(dialogue_lines):
                    node = {
                        'id': id_counter[0],
                        'chr': chr_id,
                        'txt': line_text
                    }
                    if speaker:
                        node['speaker'] = speaker
                    id_counter[0] += 1
                    
                    if idx == 0:
                        if presentation_commands:
                            node['presentation'] = presentation_commands
                            node['show'] = presentation_commands
                        if act_commands:
                            node['act'] = act_commands
                        if thought:
                            node['thought'] = thought
                    
                    if idx == len(dialogue_lines) - 1:
                        if next_target:
                            node['next'] = next_target
                    
                    dialogues.append(node)
            elif presentation_commands or act_commands or next_target or thought:
                # 处理只有行为、跳转或思维链而没有文本内容的节点
                node = {
                    'id': id_counter[0],
                    'chr': chr_id,
                    'txt': ''
                }
                if speaker:
                    node['speaker'] = speaker
                id_counter[0] += 1
                if presentation_commands:
                    node['presentation'] = presentation_commands
                    node['show'] = presentation_commands
                if act_commands:
                    node['act'] = act_commands
                if next_target:
                    node['next'] = next_target
                if thought:
                    node['thought'] = thought
                dialogues.append(node)
            continue
        
        i += 1
    
    return dialogues


def _extract_choice_blocks(text: str) -> Tuple[str, List[str]]:
    """提取所有 <choice> 块并用占位符替换"""
    choice_blocks = []
    processed_text = text
    
    # 递归提取，处理嵌套
    while True:
        match = _find_outermost_choice(processed_text)
        if match is None:
            break
        
        placeholder = f"__CHOICE_{len(choice_blocks)}__"
        choice_blocks.append(match['content'])
        processed_text = processed_text[:match['start']] + placeholder + processed_text[match['end']:]
    
    return processed_text, choice_blocks


def _find_outermost_choice(text: str) -> Optional[Dict[str, Any]]:
    """查找最外层的 <choice> 块"""
    start_tag = '<choice>'
    end_tag = '</choice>'
    
    start_index = text.find(start_tag)
    if start_index == -1:
        return None
    
    depth = 1
    pos = start_index + len(start_tag)
    
    while pos < len(text) and depth > 0:
        next_start = text.find(start_tag, pos)
        next_end = text.find(end_tag, pos)
        
        if next_end == -1:
            break
        
        if next_start != -1 and next_start < next_end:
            depth += 1
            pos = next_start + len(start_tag)
        else:
            depth -= 1
            if depth == 0:
                return {
                    'start': start_index,
                    'end': next_end + len(end_tag),
                    'content': text[start_index + len(start_tag):next_end]
                }
            pos = next_end + len(end_tag)
    
    return None


def _parse_choice_block(
    choice_content: str,
    id_counter: List[int],
    chr_map: Optional[Dict[Any, Any]] = None,
) -> List[Dict[str, Any]]:
    """解析选项块内容"""
    options = []
    
    # 提取所有顶层 <opt> 块
    opt_blocks = _extract_opt_blocks(choice_content)
    
    for opt in opt_blocks:
        option_node = {
            'optn': opt['text'],
            'dia': []
        }
        
        # 递归解析选项内的内容
        inner_dialogues = _parse_dialogue_content(opt['content'], id_counter, chr_map=chr_map)
        
        option_node['dia'] = inner_dialogues
        options.append(option_node)
    
    return options


def _extract_opt_blocks(content: str) -> List[Dict[str, str]]:
    """提取顶层 <opt> 块，忽略嵌套在 <choice> 中的 <opt>"""
    blocks = []
    opt_start_regex = re.compile(r'<opt\s+text="([^"]+)">')
    
    for match in opt_start_regex.finditer(content):
        start_index = match.start()
        text = match.group(1)
        content_start = match.end()
        
        # 检查此 <opt> 是否嵌套在 <choice> 中
        prefix = content[:start_index]
        open_choices = prefix.count('<choice>')
        close_choices = prefix.count('</choice>')
        
        if open_choices != close_choices:
            # 这是一个嵌套在 <choice> 内部的 <opt>，跳过它
            continue

        # 寻找匹配的 </opt>，同样需要处理嵌套
        depth = 1
        search_pos = content_start
        content_end = len(content)
        
        while search_pos < len(content):
            next_open = content.find('<opt', search_pos)
            next_close = content.find('</opt>', search_pos)
            
            if next_close == -1:
                break
            
            # 如果在下一个 </opt> 之前发现了另一个 <opt>，说明有嵌套
            if next_open != -1 and next_open < next_close:
                # 确认是一个完整的 <opt ...> 标签
                full_open_match = re.match(r'<opt\s+text="[^"]+">', content[next_open:])
                if full_open_match:
                    depth += 1
                    search_pos = next_open + len(full_open_match.group(0))
                    continue
            
            depth -= 1
            if depth == 0:
                content_end = next_close
                break
            search_pos = next_close + len('</opt>')
        
        blocks.append({
            'text': text,
            'content': content[content_start:content_end].strip()
        })
    
    return blocks


def serialize_to_arc(scenes: List[Dict[str, Any]], chr_map: Dict[int, str] = None) -> str:
    """
    将内部数据结构序列化为 .arc 格式
    
    Args:
        scenes: 场景数组
        chr_map: 角色ID到名称的映射（可选，用于把隐藏 ID 渲染成角色名）
        
    Returns:
        .arc 格式文本
    """
    lines = []
    
    for scene in scenes:
        # 场景标题
        lines.append(f"# {scene.get('scene', 'Untitled')}")
        
        # @intro (场景引言)
        if scene.get('intro'):
            intro_text = str(scene['intro']).strip()
            if intro_text:
                intro_lines = intro_text.split('\n')
                if len(intro_lines) == 1:
                    lines.append(f"@intro {intro_lines[0]}")
                else:
                    lines.append("@intro")
                    lines.extend(intro_lines)
        
        # thought
        if scene.get('thought'):
            lines.append("<conception>")
            lines.append(scene['thought'])
            lines.append("</conception>")
        
        # scene metadata
        if scene.get('button_text'):
            lines.append(f"@meta button_text:{scene['button_text']}")
        if scene.get('trigger_event'):
            lines.append(f"@meta trigger_event:{scene['trigger_event']}")
        if scene.get('priority') not in (None, 0, '0'):
            lines.append(f"@meta priority:{scene['priority']}")
        if scene.get('once_key'):
            lines.append(f"@meta once_key:{scene['once_key']}")
        if scene.get('conditions') is not None:
            lines.append(f"@meta conditions:{json.dumps(scene['conditions'], ensure_ascii=False)}")
        if scene.get('effects') is not None:
            lines.append(f"@meta effects:{json.dumps(scene['effects'], ensure_ascii=False)}")
        if scene.get('hiden') is not None:
            lines.append(f"@meta hiden:{str(bool(scene['hiden'])).lower()}")

        lines.append('')
        
        # 对话内容
        if scene.get('dia'):
            dia_lines = _serialize_dialogues(scene['dia'], chr_map, 0)
            lines.extend(dia_lines)
        
        lines.append('')
    
    return '\n'.join(lines)


def _serialize_dialogues(dialogues: List[Dict[str, Any]], chr_map: Dict[int, str], indent: int) -> List[str]:
    """序列化对话数组"""
    lines = []
    indent_str = '  ' * indent
    
    for d in dialogues:
        chr_id = d.get('chr')
        
        speaker = str(d.get('speaker') or "").strip()
        lines.append(f"{indent_str}{format_speaker_marker(chr_id, speaker=speaker, chr_map=chr_map)}")
            
        # thought
        if d.get('thought'):
            lines.append(f"{indent_str}<conception>{d['thought']}</conception>")
            
        # 文本内容
        lines.append(f"{indent_str}{d.get('txt', '')}")
        
        # Web 专用演出提示与通用行为分离，Unity SDK 会统一忽略该节点字段。
        show_payload = d.get('show') or d.get('presentation')
        if show_payload:
            for key, value in show_payload.items():
                if value in (None, ''):
                    continue
                if key == 'illustration_prompt':
                    key = 'img'
                elif key == 'illustration_pending':
                    key = 'pending'
                val_str = ','.join(value) if isinstance(value, list) else value
                lines.append(f"{indent_str}@show {key}:{val_str}")

        # @next
        if d.get('next'):
            lines.append(f"{indent_str}@next {d['next']}")
        
        # @act
        if d.get('act'):
            for key, value in d['act'].items():
                if str(key).lower() in {"bg", "sprite"}:
                    continue
                val_str = ','.join(value) if isinstance(value, list) else value
                lines.append(f"{indent_str}@act {key}:{val_str}")
        
        lines.append('')
        
        # 选项
        if d.get('opt'):
            lines.append(f"{indent_str}<choice>")
            for opt in d['opt']:
                lines.append(f"{indent_str}  <opt text=\"{opt.get('optn', '')}\">")
                if opt.get('dia'):
                    opt_lines = _serialize_dialogues(opt['dia'], chr_map, indent + 2)
                    lines.extend(opt_lines)
                lines.append(f"{indent_str}  </opt>")
            lines.append(f"{indent_str}</choice>")
            lines.append('')
    
    return lines


def detect_format(content: str) -> str:
    """
    检测文件内容是 .arc 还是 .story (JSON)
    
    Args:
        content: 文件内容
        
    Returns:
        'arc' | 'unknown'
    """
    trimmed = content.strip()
    
    # ARC 格式以 # 开头或包含说话人标记
    if trimmed.startswith('#') or re.search(r'^\[[^\]\r\n]+\]', trimmed, re.MULTILINE):
        return 'arc'
    
    return 'unknown'
