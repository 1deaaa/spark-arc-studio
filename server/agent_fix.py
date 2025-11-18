"""
使用方式（示例）
>>> from fix_agent import repair_story_file
>>> ok, out_path_or_err = repair_story_file('path/to/bad.story')

依赖：langchain_openai 已在项目中使用（参见 ai.py）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple, Union, Optional
import json
import os
import re

# LangChain / LLM 与 ai.py 保持一致
# 注意：为避免仅做校验时依赖 LLM 包，这里延迟导入 LangChain 相关模块。
ChatOpenAI = None  # type: ignore
SystemMessage = None  # type: ignore
HumanMessage = None  # type: ignore


# === 校验工具 ===

JsonPath = str


def _type_name(v: Any) -> str:
	return type(v).__name__


def _is_int_like(v: Any) -> bool:
	return isinstance(v, int) and not isinstance(v, bool)


def _collect_errors_for_node(node: Any, path: JsonPath, errors: List[str]) -> None:
	"""校验单个对话节点：必须包含 id(int), chr(int), txt(str)；
	可选：opt(list), act(dict), next(str)。
	并递归校验 opt 下的子节点。
	"""
	if not isinstance(node, dict):
		errors.append(f"{path}: 对话节点必须为对象，实际为 {_type_name(node)}")
		return

	# 必填字段
	if "id" not in node:
		errors.append(f"{path}.id: 缺少必填字段 id")
	elif not _is_int_like(node["id"]):
		errors.append(f"{path}.id: 必须为整数，实际为 {_type_name(node['id'])}")

	if "chr" not in node:
		errors.append(f"{path}.chr: 缺少必填字段 chr")
	elif not _is_int_like(node["chr"]):
		errors.append(f"{path}.chr: 必须为整数，实际为 {_type_name(node['chr'])}")

	if "txt" not in node:
		errors.append(f"{path}.txt: 缺少必填字段 txt")
	elif not isinstance(node["txt"], str):
		errors.append(f"{path}.txt: 必须为字符串，实际为 {_type_name(node['txt'])}")

	# 可选字段
	if "next" in node and not (node["next"] is None or isinstance(node["next"], str)):
		errors.append(f"{path}.next: 若存在必须为字符串，实际为 {_type_name(node['next'])}")

	if "act" in node and not isinstance(node["act"], dict):
		errors.append(f"{path}.act: 若存在必须为对象，实际为 {_type_name(node['act'])}")

	if "opt" in node:
		opt = node["opt"]
		if not isinstance(opt, list):
			errors.append(f"{path}.opt: 若存在必须为数组，实际为 {_type_name(opt)}")
		else:
			for i, opt_item in enumerate(opt):
				ipath = f"{path}.opt[{i}]"
				if not isinstance(opt_item, dict):
					errors.append(f"{ipath}: 选项项必须为对象，实际为 {_type_name(opt_item)}")
					continue
				if "optn" not in opt_item:
					errors.append(f"{ipath}.optn: 缺少必填字段 optn（选项名字）")
				elif not isinstance(opt_item["optn"], str):
					errors.append(f"{ipath}.optn: 必须为字符串，实际为 {_type_name(opt_item['optn'])}")
				if "dia" not in opt_item:
					errors.append(f"{ipath}.dia: 缺少必填字段 dia（选项内对话数组）")
				elif not isinstance(opt_item["dia"], list):
					errors.append(f"{ipath}.dia: 必须为数组，实际为 {_type_name(opt_item['dia'])}")
				else:
					for j, sub in enumerate(opt_item["dia"]):
						_collect_errors_for_node(sub, f"{ipath}.dia[{j}]", errors)


def check_story_data(data: Any) -> Tuple[bool, List[str]]:
	"""校验 story 数据结构是否符合规范。
	返回 (合格?, 错误列表)。
	错误位置采用 JSONPath 风格，如 [0].dia[1].opt[0].dia[2].txt
	"""
	errors: List[str] = []

	if not isinstance(data, list):
		return False, [f"$: 顶层必须为数组，实际为 {_type_name(data)}"]

	for sidx, scene in enumerate(data):
		spath = f"[{sidx}]"
		if not isinstance(scene, dict):
			errors.append(f"{spath}: 场景必须为对象，实际为 {_type_name(scene)}")
			continue
		# 必填字段 scene, cap, dia
		if "scene" not in scene:
			errors.append(f"{spath}.scene: 缺少必填字段 scene（场景名）")
		elif not isinstance(scene["scene"], str):
			errors.append(f"{spath}.scene: 必须为字符串，实际为 {_type_name(scene['scene'])}")

		if "cap" not in scene:
			errors.append(f"{spath}.cap: 缺少必填字段 cap（小标题）")
		elif not isinstance(scene["cap"], str):
			errors.append(f"{spath}.cap: 必须为字符串，实际为 {_type_name(scene['cap'])}")

		if "dia" not in scene:
			errors.append(f"{spath}.dia: 缺少必填字段 dia（对话数组）")
		elif not isinstance(scene["dia"], list):
			errors.append(f"{spath}.dia: 必须为数组，实际为 {_type_name(scene['dia'])}")
		else:
			for didx, node in enumerate(scene["dia"]):
				_collect_errors_for_node(node, f"{spath}.dia[{didx}]", errors)

	return (len(errors) == 0), errors


def check_story_file(file_path: str) -> Tuple[bool, Union[str, List[str]]]:
	"""检查 .story 文件是否合格。
	返回 (True, "合格") 或 (False, [错误信息...])。
	"""
	try:
		with open(file_path, "r", encoding="utf-8") as f:
			data = json.load(f)
	except Exception as e:
		return False, [f"文件读取/解析失败: {e}"]

	ok, errs = check_story_data(data)
	return (ok, "合格" if ok else errs)


# === 修复 Agent ===

MODEL = "Qwen/Qwen3-235B-A22B-Instruct-2507"
_BASE_URL = "https://api-inference.modelscope.cn/v1"
_API_KEY = "ms-474fd0f2-79e5-4683-b908-cf3b228e151d"


def _clean_json_text(s: str) -> str:
	s = s.strip()
	# 去除可能的 Markdown 代码块包裹
	if s.startswith("```"):
		# 常见模式 ```json ... ``` 或 ``` ... ```
		parts = s.split("```")
		# 代码块内容通常在第 2 段
		if len(parts) >= 3:
			body = "```".join(parts[1:])  # 去头
			# 再次尝试定位 json 标记
			if body.startswith("json\n"):
				body = body[len("json\n"):]
			# 去掉最后一个 ```
			if body.endswith("```"):
				body = body[: -len("```")]
			return body.strip()
	return s


def _fix_json_with_fbj(raw: str, debug: bool = False) -> Optional[str]:
	"""使用 fix-busted-json 官方 API 修复 JSON。
	- 优先用 largest_json/first_json 从混合文本里提取最大/第一个 JSON；
	- 然后用 repair_json 进行修复；
	- 返回可被 json.loads 的 JSON 字符串，失败返回 None。
	"""
	s = _clean_json_text(raw)
	is_array_like = s.strip().startswith('[') and s.strip().endswith(']')

	try:
		from fix_busted_json import repair_json, largest_json, first_json  # type: ignore
	except Exception as e:
		if debug:
			print(f"[校验] 未安装 fix-busted-json 或导入失败: {e}")
		return None

	# 尝试从混合文本中抽出候选 JSON 片段
	candidates: List[str] = [s]
	try:
		j = largest_json(s)
		if isinstance(j, str) and j.strip():
			candidates.insert(0, j)
	except Exception:
		pass
	try:
		j2 = first_json(s)
		if isinstance(j2, str) and j2.strip() and j2 not in candidates:
			candidates.append(j2)
	except Exception:
		pass

	for cand in candidates:
		try:
			if debug:
				print(f"[校验] 使用 fix-busted-json.repair_json 尝试修复候选片段...")
			fixed = repair_json(cand)
			# 官方 repair_json 可能返回非字符串
			if not isinstance(fixed, str):
				try:
					fixed = json.dumps(fixed, ensure_ascii=False, indent=2)
				except Exception:
					fixed = str(fixed)
			
			parsed_fixed = json.loads(fixed)

			# 新增逻辑：如果原始输入像数组，且修复的是提取出的片段（非原始全文），
			# 并且修复结果是对象，则重新包裹成数组
			if is_array_like and cand != s and isinstance(parsed_fixed, dict):
				if debug:
					print("[校验] 原始输入疑似数组，将修复后的对象重新包裹为数组。")
				fixed = f"[{fixed}]"
				# 再次校验最终结果的合法性
				json.loads(fixed)

			return fixed
		except Exception as e:
			if debug:
				print(f"[校验] repair_json 修复或后处理失败: {e}")

	return None


def _build_system_prompt(example_format_text: str) -> str:
	return (
		"你是一个严谨的剧本脚本修复助手。你只能输出一个严格可解析的 JSON 数组，无任何解释或 Markdown。\n"
		"你必须将用户提供的错误剧本修复为'剧本示例'同款格式，且保持所有对话文本字段 txt 的内容逐字不变。\n"
		"可选字段：对话节点下的 opt（选项数组）与 act（行为对象）可以不存在；若存在则必须满足示例规则。\n"
		"剧本规范格式(仅作格式参考，不要复述)：\n"
		f"{example_format_text}\n\n"
		"输出要求：\n"
		"- 仅输出最终 JSON 数组，无任何额外文字；\n"
		"- 确保 JSON 语法正确、键名正确、类型正确；\n"
		"- 最好只修改数据结构，禁止更改任何实际文本内容；\n"
		"- 但当文本很明显是被截断的时候，允许把这句话补全。"
	)


def _build_user_prompt(input_text: str, last_errors: Optional[List[str]] = None) -> str:
	base = (
		"以下是待修复的剧本（可能不是合法 JSON 或结构不规范）。请修复为标准格式。\n"
		"【待修复内容】\n"
		f"{input_text}\n"
	)
	if last_errors:
		base += (
			"\n【上轮校验未通过，错误摘要】\n"
			+ "\n".join(f"- {e}" for e in last_errors[:50])
			+ "\n请仅修正上述问题，切勿改动任何 txt 文本内容。"
		)
	return base


##（已移除）分场景对象提取逻辑


def repair_story_text(
	input_text: str,
	example_file: Optional[str] = None,
	max_iters: int = 5,
	temperature: float = 0.2,
	debug: bool = False,
) -> Tuple[bool, Union[str, List[str]]]:
	"""修复一段剧情脚本文本。优先执行“仅修复出错节点”的本地化修复；
	若输入非 JSON 则回退为整段修复（不做严格 txt 校验）。
	返回 (True, fixed_json_text) 或 (False, 错误信息列表)。"""

	example_text = ""
	if example_file and os.path.exists(example_file):
		try:
			with open(example_file, "r", encoding="utf-8") as f:
				example_text = f.read()
		except Exception:
			example_text = ""

	# 尝试解析原始文本；若失败，先用 fix-busted-json 修复后再试
	parsed_ok = True
	try:
		current_data = json.loads(input_text)
	except Exception as e_init:
		parsed_ok = False
		if debug:
			print(f"[校验] 初次 JSON 解析失败: {e_init}")

	if not parsed_ok:
		# 使用 fix-busted-json 尝试修复解析
		fixed_json_text = _fix_json_with_fbj(input_text, debug=debug)
		if fixed_json_text is not None:
			try:
				current_data = json.loads(fixed_json_text)
				parsed_ok = True
				input_text = fixed_json_text  # 后续若需要作为参考，使用修复后的文本
				if debug:
					print("[校验] 通过 fix-busted-json 修复并解析 JSON 成功")
			except Exception as e_pre2:
				parsed_ok = False
				if debug:
					print(f"[校验] fix-busted-json 修复结果再次 json.loads 失败: {e_pre2}")

	# 若已可解析，则先做一次规范校验；通过则直接返回
	if parsed_ok:
		ok0, errs0 = check_story_data(current_data)
		if ok0:
			return True, json.dumps(current_data, ensure_ascii=False, indent=2)
		elif debug:
			print("[校验] 预修复后结构校验不通过（进入局部/分场景修复前）:\n" + "\n".join(errs0))

	# 延迟导入，避免仅调用校验接口时要求安装 langchain_openai
	global ChatOpenAI, SystemMessage, HumanMessage
	if ChatOpenAI is None:
		try:
			from langchain_openai import ChatOpenAI as _ChatOpenAI
			from langchain_core.messages import SystemMessage as _SystemMessage, HumanMessage as _HumanMessage
			ChatOpenAI = _ChatOpenAI
			SystemMessage = _SystemMessage
			HumanMessage = _HumanMessage
		except Exception as e:
			return False, [
				"缺少运行修复所需依赖: langchain_openai/langchain.schema",
				f"请安装后重试，错误: {e}",
			]

	llm = ChatOpenAI(
		temperature=temperature,
		model=MODEL,
		base_url=_BASE_URL,
		api_key=_API_KEY,
		streaming=False,
	)

	last_errors: Optional[List[str]] = None
	last_output_raw: Optional[str] = None

	if not parsed_ok:
		# 回退：整段修复（不做严格 txt 校验）
		last_errors = None
		for _ in range(max_iters):
			messages = [
				SystemMessage(content=_build_system_prompt(example_text)),
				HumanMessage(content=_build_user_prompt(input_text, last_errors)),
			]
			if debug:
				try:
					print("[LLM] 整段回退 输入片段 ->\n" + (input_text if isinstance(input_text, str) else str(input_text)))
				except Exception:
					pass
			try:
				completion = llm.invoke(messages)
				raw = completion.content or ""
			except Exception as e:
				return False, [f"LLM 调用失败: {e}"]

			if debug:
				print("[LLM] 整段回退 原始输出 ->\n" + (raw if isinstance(raw, str) else str(raw)))
			cleaned = _clean_json_text(raw)
			try:
				data = json.loads(cleaned)
			except Exception as e:
				last_errors = [f"生成内容非合法 JSON: {e}"]
				continue

			ok, errs = check_story_data(data)
			if ok:
				try:
					fixed_text = json.dumps(data, ensure_ascii=False, indent=2)
				except Exception:
					fixed_text = cleaned
				return True, fixed_text
			last_errors = errs
			if debug and last_errors:
				print("[校验] 整段回退结果的结构校验不通过:\n" + "\n".join(last_errors))
		return False, last_errors or ["修复失败：达到最大迭代次数"]

	# 本地化修复：仅修补报错的节点
	ok, errs = check_story_data(current_data)
	if ok:
		return True, json.dumps(current_data, ensure_ascii=False, indent=2)

	def parse_tokens(path: str):
		# 解析如 [0].dia[1].opt[0].dia 为 token 列表
		tokens = []
		i = 0
		while i < len(path):
			if path[i] == '[':
				j = path.find(']', i)
				if j == -1:
					break
				idx_str = path[i+1:j]
				try:
					tokens.append(('idx', int(idx_str)))
				except Exception:
					pass
				i = j + 1
			elif path[i] == '.':
				i += 1
				k = i
				while k < len(path) and path[k] not in '.[':
					k += 1
				key = path[i:k]
				if key:
					tokens.append(('key', key))
				i = k
			else:
				# skip others
				i += 1
		return tokens

	def get_deepest_dict_path(data_obj: Any, path_str: str) -> str:
		"""给定一条错误路径，返回沿途遇到的“最深的字典对象”的路径字符串。
		例如 [0].dia[1].opt[0].dia[2].txt，若 [0].dia[1] 是一个字典对象，
		则返回到该字典的路径，如 [0].dia[1]。若根本没有遇到字典，则返回 '$'。"""
		tokens = parse_tokens(path_str)
		cur = data_obj
		taken: List[Tuple[str, Union[int, str]]] = []
		deepest_path_tokens: List[Tuple[str, Union[int, str]]] = []
		for ttype, tval in tokens:
			# 记录进入下一步前，若当前节点是 dict，则这是目前最深的 dict 路径
			if isinstance(cur, dict):
				deepest_path_tokens = taken.copy()
			if ttype == 'idx':
				if isinstance(cur, list) and 0 <= tval < len(cur):
					cur = cur[tval]
					taken.append((ttype, tval))
				else:
					break
			else:  # key
				if isinstance(cur, dict) and tval in cur:
					cur = cur[tval]
					taken.append((ttype, tval))
				else:
					break
		# 循环结束后，若最终节点仍为 dict，则以最终节点为最深路径
		if isinstance(cur, dict):
			deepest_path_tokens = taken
		# 拼接路径字符串
		s = ''
		for ttype, tval in deepest_path_tokens:
			if ttype == 'idx':
				s += f'[{tval}]'
			else:
				s += f'.{tval}'
		return s if s else '$'  # $ 表示根

	def get_node_by_path(data_obj: Any, path_str: str) -> Any:
		if path_str == '$':
			return data_obj
		tokens = parse_tokens(path_str)
		cur = data_obj
		for ttype, tval in tokens:
			if ttype == 'idx':
				cur = cur[tval]
			else:
				cur = cur[tval]
		return cur

	def set_node_by_path(data_obj: Any, path_str: str, new_val: Any) -> bool:
		# 根路径的整体替换需在外部处理（无法在函数内原地替换不同类型根对象）
		if path_str == '$':
			return False
		tokens = parse_tokens(path_str)
		cur = data_obj
		for i, (ttype, tval) in enumerate(tokens):
			if i == len(tokens) - 1:
				if ttype == 'idx':
					cur[tval] = new_val
				else:
					cur[tval] = new_val
				return True
			if ttype == 'idx':
				cur = cur[tval]
			else:
				cur = cur[tval]
		return False

	def group_errors(err_list: List[str]) -> Dict[str, List[str]]:
		groups: Dict[str, List[str]] = {}
		for e in err_list:
			# e.g., "[0].dia[1].opt[0].dia: 必须为数组..."
			if ':' in e:
				path_part = e.split(':', 1)[0].strip()
			else:
				path_part = e.strip()
			node_path = get_deepest_dict_path(current_data, path_part)
			groups.setdefault(node_path, []).append(e)
		return groups

	example_text = example_text or ""

	for _ in range(max_iters):
		ok, errs = check_story_data(current_data)
		if ok:
			return True, json.dumps(current_data, ensure_ascii=False, indent=2)

		if debug and errs:
			print("[校验] 局部修复轮次 - 当前错误列表:\n" + "\n".join(errs))

		groups = group_errors(errs)
		nodes_payload = []
		for node_path, es in groups.items():
			try:
				node_obj = get_node_by_path(current_data, node_path)
			except Exception:
				continue
			nodes_payload.append({
				"path": node_path,
				"node": node_obj,
				"errors": es[:10]
			})

		sys_prompt = (
			"你是一个 JSON 片段修复助手。只修复用户给定 path 对应的节点对象，使其满足示例格式；\n"
			"输出严格的 JSON 对象：键为 path 字符串，值为修正后的节点对象；不要输出其它文字或多余键。\n"
			"注意：\n"
			"- 节点对象是对话节点或选项对象或场景对象；\n"
			"- 若节点内 opt/act 出现且有问题请一并修正；\n"
			"- 不要随意改动无关字段；\n"
			"- 输出必须可被 json 解析。\n\n"
			"示例格式（仅供参考，不要复述）：\n"
			f"{example_text}"
		)

		user_prompt = (
			"请根据以下待修复节点列表，返回 { path: 修正后的节点 } 的 JSON：\n"
			+ json.dumps({"nodes": nodes_payload}, ensure_ascii=False)
		)

		messages = [
			SystemMessage(content=sys_prompt),
			HumanMessage(content=user_prompt),
		]
		if debug:
			try:
				# 仅输出传给 LLM 的错误片段（节点列表）
				print("[LLM] 局部修复 节点负载 ->\n" + json.dumps({"nodes": nodes_payload}, ensure_ascii=False, indent=2))
			except Exception:
				pass

		try:
			completion = llm.invoke(messages)
			raw = completion.content or ""
		except Exception as e:
			return False, [f"LLM 调用失败: {e}"]

		cleaned = _clean_json_text(raw)
		if debug:
			print("[LLM] 局部修复 原始输出 ->\n" + (raw if isinstance(raw, str) else str(raw)))
		try:
			patches = json.loads(cleaned)
		except Exception as e:
			# 如果模型没有返回对象，继续下一轮
			continue

		if not isinstance(patches, dict):
			# 期待返回 { path: node }
			continue

		# 应用补丁（单独处理根路径 '$'）
		for pth, new_node in patches.items():
			try:
				if pth == '$':
					if isinstance(new_node, list):
						current_data = new_node
						if debug:
							print("[修补] 已用补丁替换根为数组")
					else:
						# 若根不是数组，忽略该补丁
						if debug:
							print("[修补] 忽略根补丁：根必须为数组")
					continue
				# 获取原始节点路径
				original_node = get_node_by_path(current_data, pth)
				# 确保修复后的节点保留原始节点中的所有文本内容
				if isinstance(original_node, dict) and isinstance(new_node, dict):
					# 保留原始节点中的所有文本字段
					for key, value in original_node.items():
						if key == 'txt' or (isinstance(value, str) and not key in ['id', 'chr', 'next']):
							new_node[key] = value
				success = set_node_by_path(current_data, pth, new_node)
			except Exception:
				# 跳过无法设置的路径
				continue

	# 达到迭代上限仍未通过
	ok, errs = check_story_data(current_data)
	if ok:
		return True, json.dumps(current_data, ensure_ascii=False, indent=2)
	return False, errs


def repair_story_file(
	in_path: str,
	out_path: Optional[str] = None,
	example_file: Optional[str] = None,
	max_iters: int = 5,
) -> Tuple[bool, str]:
	"""修复指定 .story 文件。成功返回 (True, 输出文件路径)；失败返回 (False, 错误说明)。"""
	if not os.path.exists(in_path):
		return False, f"输入文件不存在: {in_path}"
	try:
		with open(in_path, "r", encoding="utf-8") as f:
			content = f.read()
	except Exception as e:
		return False, f"读取失败: {e}"

	ok, res = repair_story_text(content, example_file=example_file, max_iters=max_iters)
	if not ok:
		return False, "\n".join(res if isinstance(res, list) else [str(res)])

	# 写出
	out_path = out_path or in_path
	try:
		with open(out_path, "w", encoding="utf-8") as f:
			f.write(res if isinstance(res, str) else str(res))
	except Exception as e:
		return False, f"写出失败: {e}"

	return True, out_path


# 便捷函数：仅返回“合格/不合格+错误位置”文本
def quick_check_result(file_path: str) -> str:
	ok, info = check_story_file(file_path)
	if ok:
		return "合格"
	if isinstance(info, list):
		return "不合格\n" + "\n".join(info)
	return f"不合格\n{info}"


if __name__ == "__main__":
	import argparse

	parser = argparse.ArgumentParser(description="剧情脚本修复与校验")
	parser.add_argument("file", help="待校验/修复的 .story 文件路径")
	parser.add_argument("--fix", action="store_true", help="执行自动修复（原地覆盖）")
	parser.add_argument("--example", default=os.path.join(os.path.dirname(__file__), "剧本示例.story"), help="示例格式文件路径")
	parser.add_argument("--iters", type=int, default=5, help="最大修复迭代次数")
	args = parser.parse_args()

	if not args.fix:
		print(quick_check_result(args.file))
	else:
		ok, msg = repair_story_file(args.file, example_file=args.example, max_iters=args.iters)
		if ok:
			print(f"修复完成: {msg}")
			print(quick_check_result(args.file))
		else:
			print("修复失败：")
			print(msg)

