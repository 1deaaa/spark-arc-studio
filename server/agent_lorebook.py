from flask import Blueprint, request, jsonify, Response
from flask import stream_with_context
from auth import require_auth
import os
import json

from langchain.schema import HumanMessage, SystemMessage

from llm_mgr import AIManager
from utils import (
	get_project_worldview_path,
	ensure_project_characters_directory,
)

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
每个角色包含：name（不超过8个中文字符），content（200-400字描述，包含性格、动机、矛盾、与世界观的关系）。
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
	"""SSE 流式生成角色：每生成1个就立刻推送给前端。"""
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

		try:
			# 读取世界观
			worldview_path = get_project_worldview_path(user_id, project_name)
			worldview = ''
			if os.path.exists(worldview_path):
				with open(worldview_path, 'r', encoding='utf-8') as f:
					worldview = f.read()

			# 角色文件与绑定（先加载一次）
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

			# 每次仅请求 1 个角色，生成后立刻推送，避免前端长时间无输出
			llm = manager.get_user_llm(user_id, streaming=False, temperature=0.6)
			for i in range(count):
				try:
					# 给出当前已有名称，尽量避免重复
					existing_names = ", ".join(list(mapping.values())[:20]) if mapping else ""
					system = "你是一个资深设定师，负责根据世界观生成角色。只返回JSON对象，无任何解释或额外文字。"
					user_prompt = f"""
根据以下世界观，生成 1 个风格鲜明、具有戏剧张力的角色草案。
要求：
- 字段：name（不超过8个中文字符），content（200-400字，包含性格、动机、矛盾、与世界观的关系）。
- 严格输出一个 JSON 对象：{{"name":"角色名","content":"详细描述..."}}
- 不要输出任何额外文本（如“好的”或解释）。
{('已有角色名称（避免重复）：'+existing_names) if existing_names else ''}

世界观：\n{worldview}
"""
					messages = [SystemMessage(content=system), HumanMessage(content=user_prompt)]
					completion = llm.invoke(messages)
					item = _extract_single_item(completion.content)
					if not isinstance(item, dict):
						yield sse_event('error', {"message": "AI 返回格式不正确（不是对象）"})
						continue

					name = str(item.get('name') or '').strip() or '新角色'
					content = str(item.get('content') or '').strip()
					while next_id in existing_ids:
						next_id += 1
					char_id = next_id
					existing_ids.add(char_id)
					mapping[str(char_id)] = name

					# 写入角色文件
					char_file = os.path.join(characters_path, f"{char_id}.txt")
					with open(char_file, 'w', encoding='utf-8') as f:
						f.write(f"{name}\n\n{content}")

					# 立即持久化绑定
					with open(bind_path, 'w', encoding='utf-8') as f:
						json.dump(mapping, f, ensure_ascii=False, indent=2)

					data = {"id": char_id, "name": name, "content": content}
					created.append({"id": char_id, "name": name})
					yield sse_event('character', data)
					next_id += 1
				except json.JSONDecodeError:
					yield sse_event('error', {"message": "AI 返回内容无法解析为 JSON"})
				except Exception as ie:
					yield sse_event('error', {"message": f"单个角色生成失败: {ie}"})

			yield sse_event('done', {"count": len(created), "created": created})
		except Exception as e:
			print(f"AI 生成角色(SSE)失败: {e}")
			yield sse_event('error', {"message": f"生成失败: {e}"})

	headers = {
		'Content-Type': 'text/event-stream; charset=utf-8',
		'Cache-Control': 'no-cache',
		'Connection': 'keep-alive',
		# 在某些反向代理（如 Nginx）下，显式关闭缓冲
		'X-Accel-Buffering': 'no',
		# 允许跨源凭证（通过 Vite 代理通常同源，不一定需要）
		# 'Access-Control-Allow-Credentials': 'true',
	}
	return Response(generate(), headers=headers)



def get_all_characters(user_id: str, project_name: str) -> list[str]:
    """
    获取指定项目的所有角色名称列表。

    Args:
        user_id: 用户ID。
        project_name: 项目名称。

    Returns:
        一个包含所有角色名称的字符串列表。
    """
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
        return []

def get_character_info(user_id: str, project_name: str, character_name: str) -> str:
    """
    获取指定角色的详细设定信息。

    Args:
        user_id: 用户ID。
        project_name: 项目名称。
        character_name: 角色名称。

    Returns:
        角色的详细设定信息字符串，如果找不到则返回提示信息。
    """
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