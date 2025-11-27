"""
ARC Format Parser (Server-side)

将 .arc 格式的剧本文本解析为内部数据结构（兼容现有 .story JSON 格式）
"""

import re
from typing import List, Dict, Any, Optional, Tuple


def parse_arc(arc_text: str) -> List[Dict[str, Any]]:
    """
    解析 .arc 文本为场景数组
    
    Args:
        arc_text: .arc 格式的原始文本
        
    Returns:
        解析后的场景数组，兼容 .story JSON 格式
    """
    scenes = []
    
    # 按场景标题分割（# 开头的行）
    scene_blocks = _split_by_scenes(arc_text)
    
    for block in scene_blocks:
        scene = _parse_scene_block(block)
        if scene:
            scenes.append(scene)
    
    return scenes


def parse_arc_to_dialogues(arc_text: str) -> List[Dict[str, Any]]:
    """
    解析 .arc 文本，仅返回对话数组（不包含场景信息）
    用于续写功能，直接插入到现有场景中
    
    Args:
        arc_text: .arc 格式的原始文本（可能不包含场景标题）
        
    Returns:
        对话节点数组
    """
    # 移除 <thought> 块
    cleaned_text = re.sub(r'<thought>[\s\S]*?</thought>', '', arc_text)
    
    # 解析对话内容
    dialogues = _parse_dialogue_content(cleaned_text)
    
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


def _parse_scene_block(block_text: str) -> Optional[Dict[str, Any]]:
    """解析单个场景块"""
    # 提取场景名（# 标题）
    title_match = re.search(r'^#\s+(.+)$', block_text, re.MULTILINE)
    if not title_match:
        return None
    
    scene_name = title_match.group(1).strip()
    
    # 提取 @cap
    cap_match = re.search(r'^@cap\s+(.+)$', block_text, re.MULTILINE)
    cap = cap_match.group(1).strip() if cap_match else ''
    
    # 移除 <thought> 块（AI思维链，不进入最终数据）
    cleaned_text = re.sub(r'<thought>[\s\S]*?</thought>', '', block_text)
    
    # 解析对话内容
    dia = _parse_dialogue_content(cleaned_text)
    
    return {
        'scene': scene_name,
        'cap': cap,
        'dia': dia
    }


def _parse_dialogue_content(text: str) -> List[Dict[str, Any]]:
    """解析对话内容（包括选项分支）"""
    dialogues = []
    id_counter = [1]  # 使用列表以便在嵌套函数中修改
    
    # 先处理选项块，替换为占位符
    processed_text, choice_blocks = _extract_choice_blocks(text)
    
    # 按行解析
    lines = processed_text.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        # 跳过空行、标题行、@cap行
        if not line or line.startswith('#') or line.startswith('@cap') or line.startswith('<thought>'):
            i += 1
            continue
        
        # 检查是否是选项占位符
        choice_placeholder = re.match(r'^__CHOICE_(\d+)__$', line)
        if choice_placeholder:
            choice_index = int(choice_placeholder.group(1))
            if choice_index < len(choice_blocks):
                choice_block = choice_blocks[choice_index]
                # 解析选项块并附加到上一个对话节点
                options, id_counter[0] = _parse_choice_block(choice_block, id_counter[0])
                if dialogues:
                    dialogues[-1]['opt'] = options
            i += 1
            continue
        
        # 旁白
        if line == '(旁白)':
            narration_lines = []
            i += 1
            while i < len(lines):
                next_line = lines[i].strip()
                if not next_line or re.match(r'^\[\d+\]$', next_line) or next_line == '(旁白)' or next_line.startswith('__CHOICE_'):
                    break
                narration_lines.append(next_line)
                i += 1
            
            if narration_lines:
                dialogues.append({
                    'id': id_counter[0],
                    'chr': -1,  # -1 表示旁白
                    'txt': '\n'.join(narration_lines)
                })
                id_counter[0] += 1
            continue
        
        # 角色对话 [数字]
        chr_match = re.match(r'^\[(\d+)\]$', line)
        if chr_match:
            chr_id = int(chr_match.group(1))
            dialogue_lines = []
            next_target = None
            act_commands = {}
            i += 1
            
            while i < len(lines):
                next_line = lines[i].strip()
                if not next_line or re.match(r'^\[\d+\]$', next_line) or next_line == '(旁白)' or next_line.startswith('__CHOICE_'):
                    break
                
                # 检查 @next
                next_match = re.match(r'^@next\s+(.+)$', next_line)
                if next_match:
                    next_target = next_match.group(1).strip()
                    i += 1
                    continue
                
                # 检查 @act（虽然AI不生成，但解析器要支持人工添加的）
                act_match = re.match(r'^@act\s+(\w+):(.+)$', next_line)
                if act_match:
                    key = act_match.group(1).strip()
                    value = act_match.group(2).strip()
                    # 尝试解析为数组或保持字符串
                    if ',' in value:
                        value = [v.strip() for v in value.split(',')]
                    act_commands[key] = value
                    i += 1
                    continue
                
                dialogue_lines.append(next_line)
                i += 1
            
            if dialogue_lines:
                node = {
                    'id': id_counter[0],
                    'chr': chr_id,
                    'txt': '\n'.join(dialogue_lines)
                }
                id_counter[0] += 1
                
                if next_target:
                    node['next'] = next_target
                if act_commands:
                    node['act'] = act_commands
                
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


def _parse_choice_block(choice_content: str, start_id: int) -> Tuple[List[Dict[str, Any]], int]:
    """解析选项块内容"""
    options = []
    id_counter = start_id
    
    # 提取所有 <opt> 块
    opt_blocks = _extract_opt_blocks(choice_content)
    
    for opt in opt_blocks:
        option_node = {
            'optn': opt['text'],
            'dia': []
        }
        
        # 递归解析选项内的内容
        inner_dialogues = _parse_dialogue_content(opt['content'])
        
        # 更新 ID
        for d in inner_dialogues:
            d['id'] = id_counter
            id_counter += 1
        
        option_node['dia'] = inner_dialogues
        options.append(option_node)
    
    return options, id_counter


def _extract_opt_blocks(content: str) -> List[Dict[str, str]]:
    """提取 <opt> 块"""
    blocks = []
    opt_start_regex = re.compile(r'<opt\s+text="([^"]+)">')
    matches = list(opt_start_regex.finditer(content))
    
    for i, match in enumerate(matches):
        text = match.group(1)
        start_pos = match.end()
        
        # 找到对应的结束位置（下一个 <opt> 或末尾）
        if i < len(matches) - 1:
            end_pos = matches[i + 1].start()
        else:
            end_pos = len(content)
        
        # 移除末尾的 </opt> 如果存在
        opt_content = content[start_pos:end_pos]
        close_opt_index = opt_content.rfind('</opt>')
        if close_opt_index != -1:
            opt_content = opt_content[:close_opt_index]
        
        blocks.append({'text': text, 'content': opt_content.strip()})
    
    return blocks


def serialize_to_arc(scenes: List[Dict[str, Any]], chr_map: Dict[int, str] = None) -> str:
    """
    将内部数据结构序列化为 .arc 格式
    
    Args:
        scenes: 场景数组
        chr_map: 角色ID到名称的映射（可选，用于注释）
        
    Returns:
        .arc 格式文本
    """
    lines = []
    
    for scene in scenes:
        # 场景标题
        lines.append(f"# {scene.get('scene', 'Untitled')}")
        
        # @cap
        if scene.get('cap'):
            lines.append(f"@cap {scene['cap']}")
        
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
        
        # 旁白
        if chr_id == -1 or chr_id is None:
            lines.append(f"{indent_str}(旁白)")
            lines.append(f"{indent_str}{d.get('txt', '')}")
            lines.append('')
        else:
            # 角色对话
            lines.append(f"{indent_str}[{chr_id}]")
            lines.append(f"{indent_str}{d.get('txt', '')}")
            
            # @next
            if d.get('next'):
                lines.append(f"{indent_str}@next {d['next']}")
            
            # @act
            if d.get('act'):
                for key, value in d['act'].items():
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
        'arc' | 'json' | 'unknown'
    """
    trimmed = content.strip()
    
    # JSON 格式以 [ 或 { 开头
    if trimmed.startswith('[') or trimmed.startswith('{'):
        try:
            import json
            json.loads(trimmed)
            return 'json'
        except:
            pass
    
    # ARC 格式以 # 开头或包含特征标记
    if trimmed.startswith('#') or '(旁白)' in trimmed or re.search(r'^\[\d+\]', trimmed, re.MULTILINE):
        return 'arc'
    
    return 'unknown'
