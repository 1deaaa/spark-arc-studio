from flask import Blueprint, request, jsonify, Response
from flask import stream_with_context
from auth import require_auth
import os
import json

from langchain.schema import HumanMessage, SystemMessage
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from typing import List, Tuple, Dict, Optional
import re

from llm_mgr import AIManager
from request_context import get_current_info, current_user_id, current_project_name, set_agent_context
from utils import (
	get_project_worldview_path,
	get_project_lorebook_path,
	ensure_project_characters_directory,
)

# 工具上下文变量统一迁移至 request_context 模块

lorebook_bp = Blueprint('lorebook_bp', __name__)
manager = AIManager()


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
				system = (
					"你是一个资深设定师，负责根据世界观与已有角色生成新的角色。\n"
					"严格输出一个JSON对象且不要附加任何说明或Markdown。\n"
					"JSON 字段顺序固定为 name 然后 content：{\"name\":\"...\",\"content\":\"...\"}"
				)
				user_prompt = f"""
世界观：\n{worldview}

已有角色（供参考，避免重复或冲突）：
{existing_block}

请在不重复已有角色的前提下，生成一个新角色：
- name：不超过8个中文字符；
- content：200-400字，描述性格、动机、矛盾、与世界观的关系。
{f"额外要求：{prompt}" if prompt else ""}
只输出 JSON 对象，且字段顺序为 name 后 content。
"""

				messages = [SystemMessage(content=system), HumanMessage(content=user_prompt)]
				llm = manager.get_user_llm(user_id, streaming=True, temperature=0.6)

				# 增量解析器状态
				full = ""
				name_val = None
				name_sent = False
				content_key_pos = -1
				content_start = -1  # 内容字符串起始（去掉开引号）
				content_last_emit = -1
				content_closed = False
				final_content = ""

				def find_name_value(text: str):
					try:
						m = re.search(r'"name"\s*:\s*"(.*?)"', text, re.S)
						return m.group(1) if m else None
					except Exception:
						return None

				def find_content_start(text: str, start_from: int = 0) -> int:
					idx = text.find('"content"', start_from)
					if idx == -1:
						return -1
					# 找到冒号后的首个引号
					colon = text.find(':', idx)
					if colon == -1:
						return -1
					q = text.find('"', colon)
					return q + 1 if q != -1 else -1

				def find_content_close(text: str, start_index: int) -> int:
					# 从 start_index 起寻找未转义的引号
					i = start_index
					while i < len(text):
						ch = text[i]
						if ch == '"':
							# 统计连续反斜杠数量，奇数代表转义
							bs = 0
							j = i - 1
							while j >= start_index - 1 and j >= 0 and text[j] == '\\':
								bs += 1
								j -= 1
							if bs % 2 == 0:
								return i
						i += 1
					return -1

				# 先推送一个 start 事件（名称可能随后才出现）
				yield sse_event('character-start', {"id": char_id, "name": ""})

				# 移除复杂的解析和保存逻辑，只负责流式传输
				full_content = ""
				final_name = "新角色"
				try:
					for chunk in llm.stream(messages):
						if not chunk or not getattr(chunk, 'content', None):
							continue
						full_content += chunk.content
						# 简单地逐块发送 delta
						yield sse_event('character-delta', {"id": char_id, "delta": chunk.content})

					# 流结束后，尝试从完整内容中解析最终名称和内容
					try:
						# 找到第一个 { 和最后一个 } 之间的内容
						start_idx = full_content.find('{')
						end_idx = full_content.rfind('}')
						if start_idx != -1 and end_idx != -1:
							json_str = full_content[start_idx:end_idx+1]
							data = json.loads(json_str)
							final_name = data.get('name', '新角色').strip()
							final_content = data.get('content', '').strip()
						else:
							# 如果无法解析JSON，则将整个输出作为内容
							final_content = full_content.strip()
					except Exception:
						# 解析失败，仍使用完整内容
						final_content = full_content.strip()

					# 更新 chr.bind 文件
					mapping[str(char_id)] = final_name
					with open(bind_path, 'w', encoding='utf-8') as f:
						json.dump(mapping, f, ensure_ascii=False, indent=2)

					# 发送最终的 character-end 事件，由前端负责保存
					yield sse_event('character-end', {"id": char_id, "name": final_name, "content": final_content})
					created_count += 1
					
					# 更新上下文，为下一个角色做准备
					snippet = final_content if len(final_content) <= 400 else final_content[:400] + '…'
					existing_block += f"\n- {final_name}: {snippet}"

				except Exception as e:
					print(f"角色生成流中发生错误: {e}")
					# 即使出错，也发送一个结束事件，让前端知道此角色已结束
					yield sse_event('character-end', {"id": char_id, "name": "生成失败", "content": ""})
	
			yield sse_event('done', {"count": created_count})


		except Exception as e:
			print(f"AI 生成角色(SSE)失败: {e}")
			# 即使在异常情况下，也尝试保存已接收到的部分内容
			if not content_closed and content_start != -1 and full:
				try:
					# 尝试从 full 中提取 content 内容
					# 查找 "content": " 之后的内容
					content_key_pos = full.find('"content"')
					if content_key_pos != -1:
						colon_pos = full.find(':', content_key_pos)
						if colon_pos != -1:
							# 查找开始引号
							start_quote_pos = full.find('"', colon_pos)
							if start_quote_pos != -1:
								# 提取从开始引号之后到字符串末尾的内容
								partial_content = full[start_quote_pos + 1:]
								# 移除可能的末尾引号
								if partial_content.endswith('"'):
									partial_content = partial_content[:-1]
								
								# 确保 content 以句号结尾
								if partial_content and not partial_content.endswith('。'):
									partial_content += '。'
	
								# 使用已知的 name_val 或默认名称
								final_name = str(name_val or '新角色').strip()
								final_content = partial_content
	
								# 回写角色文件
								char_file = os.path.join(characters_path, f"{char_id}.txt")
								with open(char_file, 'w', encoding='utf-8') as f:
									f.write(f"{final_name}\n\n{final_content}")
								
								# 绑定中再次确保名称
								mapping[str(char_id)] = final_name
								with open(bind_path, 'w', encoding='utf-8') as f:
									json.dump(mapping, f, ensure_ascii=False, indent=2)
								
								# 结束事件
								yield sse_event('character-end', {"id": char_id, "name": final_name, "content": final_content})
								created_count += 1
				except Exception as save_e:
					print(f"在异常处理中保存部分角色内容时出错: {save_e}")
					# 即使保存部分数据出错，也继续
					pass
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