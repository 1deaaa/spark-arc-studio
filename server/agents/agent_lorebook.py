from flask import Blueprint, request, jsonify, Response
from flask import stream_with_context
from core.auth import require_auth
import os
import json

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from typing import List, Tuple, Dict, Optional
import re

from llm.llm_mgr import LLM_Manager
from core.request_context import get_current_info, current_user_id, current_project_name, set_agent_context
from core.utils import (
	get_project_worldview_path,
	get_project_lorebook_path,
	ensure_project_characters_directory,
)

# 工具上下文变量统一迁移至 request_context 模块

lorebook_bp = Blueprint('lorebook_bp', __name__)
manager = LLM_Manager


@lorebook_bp.route('/api/lorebooks/<project_name>/<file_name>', methods=['GET'])
@require_auth
def get_lorebook(project_name, file_name):
    user_id = str(request.current_user['user_id'])
    lorebook_path = get_project_lorebook_path(user_id, project_name, file_name)
    if not os.path.exists(lorebook_path):
        return jsonify({"content": ""})
    
    with open(lorebook_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    return jsonify({"content": content})

@lorebook_bp.route('/api/lorebooks', methods=['POST'])
@require_auth
def save_lorebook():
    data = request.get_json()
    project_name = data.get('projectName')
    file_name = data.get('fileName')
    content = data.get('content')

    if not project_name or not file_name:
        return jsonify({"error": "Missing project name or file name"}), 400

    user_id = str(request.current_user['user_id'])
    lorebook_path = get_project_lorebook_path(user_id, project_name, file_name)
    
    try:
        with open(lorebook_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@lorebook_bp.route('/api/ai/gen-characters/stream', methods=['GET'])
@require_auth
@get_current_info
def gen_characters_stream():
	"""SSE 流式生成角色：逐字推送 content，事件包括 character-start/character-delta/character-end。"""
	# 项目名由上下文注入（SSE 多为 GET）
	project_name = current_project_name.get() or request.args.get('projectName')
	try:
		count = int(request.args.get('count', '0'))
	except Exception:
		count = 0
	prompt = request.args.get('prompt', '')
	if not project_name:
		return jsonify({"error": "缺少项目名称"}), 400
	if count < 1 or count > 8:
		return jsonify({"error": "生成数量需在 1-8 之间"}), 400

	user_id = current_user_id.get() or str(request.current_user['user_id'])

	@stream_with_context
	def generate():
		def sse_event(event: str, data: dict):
			payload = json.dumps(data, ensure_ascii=False)
			return f"event: {event}\ndata: {payload}\n\n"

		def load_all_existing_characters(uid: str, proj: str) -> Tuple[Dict[str, str], str]:
			"""返回 (id->name) 映射 与 文本块(包含所有角色的名称与设定)."""
			characters_path = ensure_project_characters_directory(uid, proj)
			bind_path = os.path.join(characters_path, 'chr.bind')
			mapping = {}
			if os.path.exists(bind_path):
				try:
					with open(bind_path, 'r', encoding='utf-8') as f:
						mapping = json.load(f) or {}
				except Exception:
					mapping = {}
			# 组装文本，避免过长，这里每个角色截断到 400 字
			lines = []
			for cid, name in mapping.items():
				try:
					char_file = os.path.join(characters_path, f"{cid}.txt")
					content = ''
					if os.path.exists(char_file):
						with open(char_file, 'r', encoding='utf-8') as f:
							text = f.read()
							# 文件格式为: 第一行名称, 空行, 然后正文
							parts = text.split('\n', 2)
							if len(parts) >= 3:
								content = parts[2]
							else:
								content = text
					content = (content or '').strip()
					if len(content) > 400:
						content = content[:400] + '…'
					lines.append(f"- {name}: {content}")
				except Exception:
					continue
			return mapping, ("\n".join(lines) if lines else '')

		def next_available_id(existing_ids: set) -> int:
			nx = 0
			while nx in existing_ids:
				nx += 1
			return nx

		try:
			# 读取世界观
			worldview_path = get_project_worldview_path(user_id, project_name)
			worldview = ''
			if os.path.exists(worldview_path):
				with open(worldview_path, 'r', encoding='utf-8') as f:
					worldview = f.read()
			# 角色目录与绑定
			characters_path = ensure_project_characters_directory(user_id, project_name)
			bind_path = os.path.join(characters_path, 'chr.bind')
			mapping, existing_block = load_all_existing_characters(user_id, project_name)
			existing_ids = {int(k) for k in mapping.keys()} if mapping else set()
			created_count = 0

			# 循环逐个生成，逐字推送
			for _ in range(count):
				# 分配一个新ID（先占位，名称可能稍后才能知道）
				char_id = next_available_id(existing_ids)
				existing_ids.add(char_id)
				mapping[str(char_id)] = mapping.get(str(char_id), "生成中...")
				with open(bind_path, 'w', encoding='utf-8') as f:
					json.dump(mapping, f, ensure_ascii=False, indent=2)

				# 构造提示，明确要求 name 在前，content 在后，以便更早拿到名字
				# 构造提示，要求纯文本格式
				system = (
					"你是一个资深设定师，负责根据世界观与已有角色生成新的角色。\n"
					"你的输出必须严格遵循以下格式，不要附加任何说明或Markdown：\n"
					"第一行是角色名，然后是一个空行，然后是角色设定内容。\n"
					"例如：\n"
					"角色名\n\n"
					"这是角色的详细设定..."
				)
				user_prompt = f"""
世界观：\n{worldview}

已有角色（供参考，避免角色重复！）：
{existing_block}

请在不重复已有角色的前提下，生成一个新角色：
- 角色名：不超过8个中文字符；
- 角色设定：200-400字，描述性格、动机、矛盾、与世界观的关系。
{f"额外要求：{prompt}" if prompt else ""}
"""

				messages = [SystemMessage(content=system), HumanMessage(content=user_prompt)]
				llm = manager.get_user_llm(user_id)  # streaming 默认为 True

				# 流式解析状态
				buffer = ""
				name_sent = False
				final_name = "新角色"
				final_content = ""

				# 先推送一个 start 事件
				yield sse_event('character-start', {"id": char_id, "name": ""})

				try:
					for chunk in llm.stream(messages):
						if not chunk or not getattr(chunk, 'content', None):
							continue
						
						buffer += chunk.content
						
						# 尝试在流中实时提取名字
						if not name_sent:
							separator_pos = buffer.find('\n\n')
							if separator_pos != -1:
								name = buffer[:separator_pos].strip()
								if name:
									final_name = name
									# 立即更新占位的角色名
									yield sse_event('character-streamed', {"id": char_id, "name": final_name})
									name_sent = True
						
						# 无论是否提取出名字，都实时推送内容delta
						yield sse_event('character-delta', {"id": char_id, "delta": chunk.content})

					# 流结束后，进行最终解析
					separator_pos = buffer.find('\n\n')
					if separator_pos != -1:
						final_name = buffer[:separator_pos].strip() or "新角色"
						final_content = buffer[separator_pos + 2:].strip()
					else:
						# 如果没有分隔符，整个输出都作为内容
						final_content = buffer.strip()

					# 更新 chr.bind 文件
					mapping[str(char_id)] = final_name
					with open(bind_path, 'w', encoding='utf-8') as f:
						json.dump(mapping, f, ensure_ascii=False, indent=2)

					# 发送最终的 character-end 事件
					yield sse_event('character-end', {"id": char_id, "name": final_name, "content": final_content})
					created_count += 1
					
					# 更新上下文，为下一个角色做准备
					snippet = final_content if len(final_content) <= 400 else final_content[:400] + '…'
					existing_block += f"\n- {final_name}: {snippet}"

				except Exception as e:
					print(f"角色生成流中发生错误: {e}")
					yield sse_event('character-end', {"id": char_id, "name": "生成失败", "content": ""})
	
			yield sse_event('done', {"count": created_count})

		except Exception as e:
			print(f"AI 生成角色(SSE)失败: {e}")
			yield sse_event('error', {"message": f"生成失败: {e}"})
	headers = {
		'Content-Type': 'text/event-stream; charset=utf-8',
		'Cache-Control': 'no-cache',
		'Connection': 'keep-alive',
		'X-Accel-Buffering': 'no',
	}
	return Response(generate(), headers=headers)



def get_all_characters() -> list[str]:
    """
    获取当前上下文项目的所有角色名称列表。
    作为 LangChain Tool 使用。
    """
    user_id = current_user_id.get()
    project_name = current_project_name.get()
    if not user_id or not project_name:
        return ["错误：无法获取用户或项目上下文。"]
    
    try:
        characters_path = ensure_project_characters_directory(user_id, project_name)
        bind_path = os.path.join(characters_path, 'chr.bind')

        if not os.path.exists(bind_path):
            return []

        with open(bind_path, 'r', encoding='utf-8') as f:
            mapping = json.load(f)
        
        return list(mapping.values())
    except Exception as e:
        print(f"Error getting all characters: {e}")
        return [f"获取角色列表时出错: {e}"]


def get_character_info(character_name: str) -> str:
    """
    获取当前上下文项目中指定角色的详细设定信息。
    作为 LangChain Tool 使用。
    """
    user_id = current_user_id.get()
    project_name = current_project_name.get()
    if not user_id or not project_name:
        return "错误：无法获取用户或项目上下文。"
    
    try:
        characters_path = ensure_project_characters_directory(user_id, project_name)
        bind_path = os.path.join(characters_path, 'chr.bind')

        if not os.path.exists(bind_path):
            return "角色绑定文件不存在。"

        with open(bind_path, 'r', encoding='utf-8') as f:
            mapping = json.load(f)
        
        char_id = None
        for cid, name in mapping.items():
            if name == character_name:
                char_id = cid
                break
        
        if char_id is None:
            return f"未找到名为 '{character_name}' 的角色。"

        char_file_path = os.path.join(characters_path, f"{char_id}.txt")
        if not os.path.exists(char_file_path):
            return f"找到了角色 '{character_name}' 但其设定文件丢失。"

        with open(char_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return content
    except Exception as e:
        print(f"Error getting character info for '{character_name}': {e}")
        return f"获取角色 '{character_name}' 信息时发生错误。"