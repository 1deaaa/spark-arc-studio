from flask import Blueprint, request, jsonify, Response
from flask import stream_with_context
from auth import require_auth
import os
import json

from langchain.schema import HumanMessage, SystemMessage
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from typing import List, Tuple, Dict, Optional
from contextvars import ContextVar
import re

from llm_mgr import AIManager
from utils import (
	get_project_worldview_path,
	ensure_project_characters_directory,
)

# --- Context Variables for Agent Tools ---
current_user_id = ContextVar('current_user_id', default=None)
current_project_name = ContextVar('current_project_name', default=None)

def set_agent_context(user_id: str, project_name: str):
    """在调用 Agent 之前设置上下文。"""
    current_user_id.set(user_id)
    current_project_name.set(project_name)
# -----------------------------------------

lorebook_bp = Blueprint('lorebook_bp', __name__)
manager = AIManager()


def _extract_json_array(text: str) -> str:
	"""从可能包含 Markdown 代码块的文本中提取 JSON 数组字符串。"""
	if not text:
		return "[]"
	s = text.strip()
	if s.startswith("```"):
		first = s.find("\n")
		if first != -1:
			s = s[first + 1 :]
		if s.endswith("```"):
			s = s[:-3]
		s = s.strip()
	l = s.find('[')
	r = s.rfind(']')
	if l != -1 and r != -1 and r > l:
		return s[l : r + 1]
	return s


def _extract_single_item(text: str):
	"""尝试从文本中解析出一个 {"name","content"} 对象。

	支持以下几种返回：
	- 纯 JSON 对象
	- JSON 数组（取第一个）
	- 包裹在 ```json 代码块中的对象或数组
	"""
	if not text:
		return None
	s = text.strip()
	# 去除 Markdown 代码块
	if s.startswith("```"):
		first = s.find("\n")
		if first != -1:
			s = s[first + 1 :]
		if s.endswith("```"):
			s = s[:-3]
		s = s.strip()
	try:
		if s.startswith('['):
			arr = json.loads(s)
			if isinstance(arr, list) and arr:
				return arr[0]
			return None
		# 默认按对象解析
		obj = json.loads(s)
		return obj
	except Exception:
		return None


@lorebook_bp.route('/api/ai/gen-characters', methods=['POST'])
@require_auth
def gen_characters_from_worldview():
	"""根据世界观自动生成角色（最多 8 个），并写入 chr.bind 与 <id>.txt。"""
	data = request.json or {}
	project_name = data.get('projectName')
	count = int(data.get('count') or 0)
	if not project_name:
		return jsonify({"error": "缺少项目名称"}), 400
	if count < 1 or count > 8:
		return jsonify({"error": "生成数量需在 1-8 之间"}), 400

	user_id = str(request.current_user['user_id'])
	try:
		# 读取世界观
		worldview_path = get_project_worldview_path(user_id, project_name)
		worldview = ''
		if os.path.exists(worldview_path):
			with open(worldview_path, 'r', encoding='utf-8') as f:
				worldview = f.read()

		system = "你是一个资深设定师，负责根据世界观生成角色。只返回JSON数组，无任何解释或额外文字。"
		user_prompt = f"""
根据以下世界观，生成 {count} 个风格各异、具有戏剧张力的角色草案。
每个角色包含：name（不超过8个中文字符），content（100字描述，包含性格、动机、矛盾、与世界观的关系）。
严格输出 JSON 数组格式：
[
  {{"name": "角色名", "content": "详细描述..."}},
  ... 共 {count} 项
]

世界观：\n{worldview}
"""
		messages = [SystemMessage(content=system), HumanMessage(content=user_prompt)]
		llm = manager.get_user_llm(user_id, streaming=False, temperature=0.6)
		completion = llm.invoke(messages)
		payload = _extract_json_array(completion.content)
		arr = json.loads(payload)
		if not isinstance(arr, list):
			return jsonify({"error": "AI 返回格式不正确"}), 500

		# 写入角色文件与绑定
		characters_path = ensure_project_characters_directory(user_id, project_name)
		bind_path = os.path.join(characters_path, 'chr.bind')
		mapping = {}
		if os.path.exists(bind_path):
			try:
				with open(bind_path, 'r', encoding='utf-8') as f:
					mapping = json.load(f) or {}
			except Exception:
				mapping = {}

		existing_ids = {int(k) for k in mapping.keys()} if mapping else set()
		next_id = 0
		created = []
		for item in arr[:count]:
			name = str(item.get('name') or '').strip() or '新角色'
			content = str(item.get('content') or '').strip()
			while next_id in existing_ids:
				next_id += 1
			char_id = next_id
			existing_ids.add(char_id)
			mapping[str(char_id)] = name

			# 写 <id>.txt
			char_file = os.path.join(characters_path, f"{char_id}.txt")
			with open(char_file, 'w', encoding='utf-8') as f:
				f.write(f"{name}\n\n{content}")
			created.append({"id": char_id, "name": name})
			next_id += 1

		# 更新绑定
		with open(bind_path, 'w', encoding='utf-8') as f:
			json.dump(mapping, f, ensure_ascii=False, indent=2)

		return jsonify({"success": True, "created": created})
	except json.JSONDecodeError:
		return jsonify({"error": "AI 返回的内容无法解析为 JSON"}), 500
	except Exception as e:
		print(f"AI 生成角色失败: {e}")
		return jsonify({"error": f"生成失败: {e}"}), 500


@lorebook_bp.route('/api/ai/gen-characters/stream', methods=['GET'])
@require_auth
def gen_characters_stream():
	"""SSE 流式生成角色：逐字推送 content，事件包括 character-start/character-delta/character-end。"""
	project_name = request.args.get('projectName')
	try:
		count = int(request.args.get('count', '0'))
	except Exception:
		count = 0
	if not project_name:
		return jsonify({"error": "缺少项目名称"}), 400
	if count < 1 or count > 8:
		return jsonify({"error": "生成数量需在 1-8 之间"}), 400

	user_id = str(request.current_user['user_id'])

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

				for chunk in llm.stream(messages):
					if not chunk or not getattr(chunk, 'content', None):
						continue
					full += chunk.content

					# 尝试抓取 name（只抓一次）
					if name_val is None:
						name_val = find_name_value(full)
						if name_val is not None and not name_sent:
							# 更新绑定文件中的名称
							mapping[str(char_id)] = name_val.strip() or "新角色"
							with open(bind_path, 'w', encoding='utf-8') as f:
								json.dump(mapping, f, ensure_ascii=False, indent=2)
							# 通知前端名称
							yield sse_event('character-start', {"id": char_id, "name": mapping[str(char_id)]})
							name_sent = True

					# 寻找 content 开始位置
					if content_start == -1:
						content_start = find_content_start(full)
						if content_start != -1:
							content_last_emit = content_start

					# 逐字增量推送 content 片段
					if content_start != -1 and not content_closed:
						close_idx = find_content_close(full, content_start)
						end_for_emit = close_idx if close_idx != -1 else len(full)
						if end_for_emit > content_last_emit:
							delta = full[content_last_emit:end_for_emit]
							if delta:
								yield sse_event('character-delta', {"id": char_id, "delta": delta})
								content_last_emit = end_for_emit
						if close_idx != -1:
							# 完整内容已闭合
							content_closed = True
							# 解析最终 JSON 对象，得到最终内容（解码转义）
							try:
								obj_text_start = full.find('{')
								obj_text_end = full.find('}', close_idx)
								if obj_text_start != -1 and obj_text_end != -1:
									obj_text = full[obj_text_start:obj_text_end+1]
									obj = json.loads(obj_text)
									final_name = str(obj.get('name') or (name_val or '新角色')).strip()
									final_content = str(obj.get('content') or '')
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
									# 更新已有角色块，便于后续去重与风格一致
									snippet = final_content if len(final_content) <= 400 else final_content[:400] + '…'
									existing_block = (existing_block + ("\n" if existing_block else "") + f"- {final_name}: {snippet}")
									break
							except Exception:
								# 即便解析失败，也继续等待更多流直到结束
								continue

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