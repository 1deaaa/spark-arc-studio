"""
使用方式（示例）
>>> from fix_agent import repair_arc_file
>>> ok, out_path_or_err = repair_arc_file('path/to/bad.arc')

依赖：langchain_openai 已在项目中使用。
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple, Union, Optional
import os
import re
from agents.language_policy import prepend_prompt_language_policy

# 导入 ARC 解析器和序列化器
try:
    from server.story.arc_parser import parse_arc, serialize_to_arc
except ImportError:
    # 兼容脚本直接运行
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    from server.story.arc_parser import parse_arc, serialize_to_arc

# LangChain / LLM 与 ai.py 保持一致
ChatOpenAI = None  # type: ignore
SystemMessage = None  # type: ignore
HumanMessage = None  # type: ignore

# === 校验工具 ===

def check_arc_data(data: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """校验 ARC 解析后的数据结构是否完整。"""
    errors: List[str] = []
    if not isinstance(data, list):
        return False, ["数据必须是场景列表"]
    
    if not data:
        return False, ["场景列表为空"]

    for i, scene in enumerate(data):
        if not scene.get('scene'):
            errors.append(f"场景 {i}: 缺少场景标题 (#)")
        if 'dia' not in scene or not isinstance(scene['dia'], list):
            errors.append(f"场景 {i}: 缺少对话内容或格式错误")
        elif not scene['dia']:
            errors.append(f"场景 {i}: 对话内容为空")

    return (len(errors) == 0), errors

def check_arc_file(file_path: str) -> Tuple[bool, Union[str, List[str]]]:
    """检查 .arc 文件是否能被正确解析且包含基本结构。"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        data = parse_arc(content)
        ok, errs = check_arc_data(data)
        return (ok, "合格" if ok else errs)
    except Exception as e:
        return False, [f"文件读取/解析失败: {e}"]

# === 修复 Agent ===

MODEL = "Qwen/Qwen3-235B-A22B-Instruct-2507"
_BASE_URL = "https://api-inference.modelscope.cn/v1"
_API_KEY = "ms-474fd0f2-79e5-4683-b908-cf3b228e151d"

def _clean_arc_text(s: str) -> str:
    s = s.strip()
    # 去除可能的 Markdown 代码块包裹
    if s.startswith("```"):
        parts = s.split("```")
        if len(parts) >= 3:
            body = "```".join(parts[1:])
            # 去除语言标记
            body = re.sub(r'^(arc|markdown|text|plain)\n', '', body, flags=re.IGNORECASE)
            # 去掉最后一个 ```
            if body.endswith("```"):
                body = body[: -len("```")]
            return body.strip()
    return s

def _build_system_prompt() -> str:
    return prepend_prompt_language_policy(
        (
        "你是一个专业的剧本修复助手。你必须将用户提供的损坏或格式不规范的 ARC 剧本修复为标准格式。\n"
        "ARC 格式规范：\n"
        "1. 场景以 # 标题 开始\n"
        "2. 可选 @intro 引言\n"
        "3. 对话使用 [角色名] 格式，旁白使用 [旁白]\n"
        "4. 选项使用 <choice> <opt text=\"...\"> ... </opt> </choice>\n"
        "5. 严禁修改任何对话或旁白的文字内容 (txt 字段对应的部分)。\n"
        "6. 严禁输出任何解释、说明或 Markdown 代码块，只输出修复后的 ARC 纯文本。"
        )
    )

def repair_arc_text(
    input_text: str,
    max_iters: int = 3,
    temperature: float = 0.2,
    debug: bool = False,
) -> Tuple[bool, Union[str, List[str]]]:
    """修复 ARC 剧本文本。"""
    
    # 尝试解析
    try:
        data = parse_arc(input_text)
        ok, errs = check_arc_data(data)
        if ok:
            return True, input_text
    except Exception:
        pass

    # 延迟导入
    global ChatOpenAI, SystemMessage, HumanMessage
    if ChatOpenAI is None:
        try:
            from langchain_openai import ChatOpenAI as _ChatOpenAI
            from langchain_core.messages import SystemMessage as _SystemMessage, HumanMessage as _HumanMessage
            ChatOpenAI = _ChatOpenAI
            SystemMessage = _SystemMessage
            HumanMessage = _HumanMessage
        except Exception as e:
            return False, [f"缺少依赖: {e}"]

    llm = ChatOpenAI(
        temperature=temperature,
        model=MODEL,
        base_url=_BASE_URL,
        api_key=_API_KEY,
    )

    current_text = input_text
    for i in range(max_iters):
        messages = [
            SystemMessage(content=_build_system_prompt()),
            HumanMessage(content=f"请修复以下 ARC 剧本：\n\n{current_text}"),
        ]
        
        try:
            completion = llm.invoke(messages)
            raw = completion.content or ""
            fixed_text = _clean_arc_text(raw)
            
            # 校验修复结果
            data = parse_arc(fixed_text)
            ok, _ = check_arc_data(data)
            if ok:
                return True, fixed_text
            current_text = fixed_text # 迭代修复
        except Exception as e:
            if debug:
                print(f"Iter {i} failed: {e}")
            continue

    return False, ["无法通过 AI 修复 ARC 格式"]

def repair_arc_file(
    in_path: str,
    out_path: Optional[str] = None,
    max_iters: int = 3,
) -> Tuple[bool, str]:
    """修复指定 .arc 文件。"""
    if not os.path.exists(in_path):
        return False, f"输入文件不存在: {in_path}"
    try:
        with open(in_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return False, f"读取失败: {e}"

    ok, res = repair_arc_text(content, max_iters=max_iters)
    if not ok:
        return False, str(res)

    out_path = out_path or in_path
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(res if isinstance(res, str) else str(res))
    except Exception as e:
        return False, f"写出失败: {e}"

    return True, out_path

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ARC 剧本修复与校验")
    parser.add_argument("file", help="待校验/修复的 .arc 文件路径")
    parser.add_argument("--fix", action="store_true", help="执行自动修复")
    args = parser.parse_args()

    if not args.fix:
        ok, info = check_arc_file(args.file)
        print("Pass" if ok else f"Fail: {info}")
    else:
        ok, msg = repair_arc_file(args.file)
        if ok:
            print(f"Fix applied: {msg}")
        else:
            print(f"Fix failed: {msg}")
