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
				yield sse_event('error', {"message": "AI 返回格式不正确"})
				return

			# 角色文件与绑定
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
				try:
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

					# 立即持久化绑定，以便前端刷新列表也能看到
					with open(bind_path, 'w', encoding='utf-8') as f:
						json.dump(mapping, f, ensure_ascii=False, indent=2)

					data = {"id": char_id, "name": name, "content": content}
					created.append({"id": char_id, "name": name})
					yield sse_event('character', data)
					next_id += 1
				except Exception as ie:
					yield sse_event('error', {"message": f"单个角色写入失败: {ie}"})

			yield sse_event('done', {"count": len(created), "created": created})
		except json.JSONDecodeError:
			yield sse_event('error', {"message": "AI 返回内容无法解析为 JSON"})
		except Exception as e:
			print(f"AI 生成角色(SSE)失败: {e}")
			yield sse_event('error', {"message": f"生成失败: {e}"})

	headers = {
		'Content-Type': 'text/event-stream; charset=utf-8',
		'Cache-Control': 'no-cache',
		'Connection': 'keep-alive',
		# 允许跨源凭证（通过 Vite 代理通常同源，不一定需要）
		# 'Access-Control-Allow-Credentials': 'true',
	}
	return Response(generate(), headers=headers)
