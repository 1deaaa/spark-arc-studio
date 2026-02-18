import json
import os
import time
from typing import Dict, Any, List, Optional
from pathlib import Path
import sys

SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))


def _normalize_base_url(raw: str) -> str:
    value = (raw or "").strip().rstrip("/")
    if not value:
        return ""
    if value.endswith("/v1"):
        return value
    return value + "/v1"


def _to_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump()
        except Exception:
            pass
    if hasattr(value, "dict"):
        try:
            return value.dict()
        except Exception:
            pass
    try:
        return dict(value)
    except Exception:
        return {}


def _parse_scales(raw: str) -> List[int]:
    values = []
    for part in (raw or "1,2").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            num = int(part)
            if num > 0:
                values.append(num)
        except Exception:
            pass
    return values or [1]


def _parse_extra_body() -> Dict[str, Any]:
    raw = os.getenv("OPENAI_EXTRA_BODY_JSON", "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        print(f"[WARN] OPENAI_EXTRA_BODY_JSON 解析失败: {exc}")
        return {}


def _pick_worldview_file() -> Optional[Path]:
    override = os.getenv("OPENAI_TEST_WORLDVIEW_PATH", "").strip()
    if override:
        p = Path(override)
        if p.exists() and p.is_file():
            return p

    project_name = os.getenv("OPENAI_TEST_PROJECT_NAME", "项目").strip() or "项目"
    preferred = SERVER_ROOT / "_userdata" / "uid_1" / "projects" / project_name / "世界观.txt"
    if preferred.exists() and preferred.is_file():
        return preferred

    root = SERVER_ROOT / "_userdata"
    candidates = list(root.glob("uid_*/projects/*/世界观.txt")) if root.exists() else []
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_size)


def _load_worldview_text() -> str:
    path = _pick_worldview_file()
    if path and path.exists():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore").strip()
            if text:
                print(f"[INFO] 使用世界观文件: {path}")
                print(f"[INFO] 基础文本长度(字符): {len(text)}")
                return text
        except Exception as exc:
            print(f"[WARN] 读取世界观文件失败: {exc}")

    fallback = (
        "### 世界观设定\n"
        "火种城位于旧大陆断裂带边缘，城市依赖记忆蒸馏塔运行。\n"
        "科技与魔法共存，但所有法术都需要以真实记忆作为燃料。\n"
        "主冲突是记忆污染：伪造记忆会在群体中扩散并改写现实感知。\n"
    ) * 20
    print(f"[WARN] 未找到世界观文件，使用 fallback 文本，长度(字符): {len(fallback)}")
    return fallback


def _build_openai_messages(overwrite_content: str) -> list:
    return [
        {
            "role": "system",
            "content": (
                "你是测试助手。必须调用 rewrite_worldview 工具，"
                "并把 overwrite_content 填入完整文本。不要输出普通自然语言。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请立刻调用 rewrite_worldview 工具，"
                "overwrite_content 使用下面完整文本：\n" + overwrite_content
            ),
        },
    ]


def _build_langchain_messages(overwrite_content: str) -> list:
    from langchain_core.messages import SystemMessage, HumanMessage

    return [
        SystemMessage(
            content=(
                "你是测试助手。必须调用 rewrite_worldview 工具，"
                "并把 overwrite_content 填入完整文本。不要输出普通自然语言。"
            )
        ),
        HumanMessage(
            content=(
                "请立刻调用 rewrite_worldview 工具，"
                "overwrite_content 使用下面完整文本：\n" + overwrite_content
            )
        ),
    ]


def _run_openai_sdk_probe(client, model: str, tools: list, overwrite_content: str, scale: int) -> None:
    print(f"\n=== OpenAI SDK Stream Probe | scale={scale} | payload_chars={len(overwrite_content)} ===")

    first_chunk_ms = None
    first_tool_field_ms = None
    first_tool_name_ms = None
    first_tool_args_ms = None
    chunk_count = 0
    arguments_buffer = ""
    function_name = ""

    req_kwargs = {
        "model": model,
        "messages": _build_openai_messages(overwrite_content),
        "tools": tools,
        "tool_choice": {"type": "function", "function": {"name": "rewrite_worldview"}},
        "temperature": 0,
        "stream": True,
    }
    extra_body = _parse_extra_body()
    if extra_body:
        req_kwargs["extra_body"] = extra_body

    t0 = time.perf_counter()
    retried_auto = False

    while True:
        try:
            stream = client.chat.completions.create(**req_kwargs)
            for chunk in stream:
                chunk_count += 1
                dt_ms = int((time.perf_counter() - t0) * 1000)
                if first_chunk_ms is None:
                    first_chunk_ms = dt_ms

                chunk_dict = _to_dict(chunk)
                choices = chunk_dict.get("choices") or []
                if not choices:
                    continue

                delta = (choices[0] or {}).get("delta") or {}
                tool_calls = delta.get("tool_calls") or []

                if tool_calls and first_tool_field_ms is None:
                    first_tool_field_ms = dt_ms

                for tool_call in tool_calls:
                    fn = ((tool_call or {}).get("function") or {})
                    name_piece = fn.get("name") or ""
                    args_piece = fn.get("arguments") or ""

                    if name_piece and first_tool_name_ms is None:
                        first_tool_name_ms = dt_ms
                    if args_piece and first_tool_args_ms is None:
                        first_tool_args_ms = dt_ms

                    if name_piece:
                        function_name += name_piece
                    if args_piece:
                        arguments_buffer += args_piece
            break
        except Exception as exc:
            err = str(exc)
            if not retried_auto and ("tool_choice" in err or "thinking mode" in err):
                print(f"[WARN] forced tool_choice 流式失败，降级为 auto 重试: {err}")
                req_kwargs.pop("tool_choice", None)
                retried_auto = True
                continue
            raise

    print(f"first_chunk_ms={first_chunk_ms}")
    print(f"first_tool_field_ms={first_tool_field_ms}")
    print(f"first_tool_name_ms={first_tool_name_ms}")
    print(f"first_tool_args_ms={first_tool_args_ms}")
    print(f"function_name={function_name}")
    print(f"arguments_buffer_len={len(arguments_buffer)}")


def _run_openai_marker_then_tool_probe(
    client,
    model: str,
    tools: list,
    overwrite_content: str,
    scale: int,
    marker_token: str,
    force_tool_choice: bool,
) -> None:
    mode = "forced-function" if force_tool_choice else "auto"
    print(
        f"\n=== Marker->Tool Probe | mode={mode} | scale={scale} | payload_chars={len(overwrite_content)} ==="
    )

    first_chunk_ms = None
    first_content_ms = None
    first_marker_ms = None
    first_tool_field_ms = None
    content_buffer = ""
    chunk_count = 0

    system_prompt = (
        "你是测试助手。严格执行两步："
        f"第1步，先输出且仅输出一段普通文本，必须包含标记 {marker_token}；"
        "第2步，立刻调用 rewrite_worldview 工具，把 overwrite_content 填入完整文本。"
        "如果你未调用工具，任务视为失败。"
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                "现在执行两步流程：先输出标记文本，再调用工具。"
                "overwrite_content 使用下面文本：\n" + overwrite_content
            ),
        },
    ]

    req_kwargs = {
        "model": model,
        "messages": messages,
        "tools": tools,
        "temperature": 0,
        "stream": True,
    }
    if force_tool_choice:
        req_kwargs["tool_choice"] = {"type": "function", "function": {"name": "rewrite_worldview"}}

    extra_body = _parse_extra_body()
    if extra_body:
        req_kwargs["extra_body"] = extra_body

    t0 = time.perf_counter()
    retried_auto = False

    while True:
        try:
            stream = client.chat.completions.create(**req_kwargs)
            for chunk in stream:
                chunk_count += 1
                dt_ms = int((time.perf_counter() - t0) * 1000)
                if first_chunk_ms is None:
                    first_chunk_ms = dt_ms

                chunk_dict = _to_dict(chunk)
                choices = chunk_dict.get("choices") or []
                if not choices:
                    continue

                delta = (choices[0] or {}).get("delta") or {}
                content_piece = delta.get("content") or ""
                tool_calls = delta.get("tool_calls") or []

                if content_piece and first_content_ms is None:
                    first_content_ms = dt_ms
                if content_piece:
                    content_buffer += content_piece
                    if marker_token in content_buffer and first_marker_ms is None:
                        first_marker_ms = dt_ms

                if tool_calls and first_tool_field_ms is None:
                    first_tool_field_ms = dt_ms
            break
        except Exception as exc:
            err = str(exc)
            if force_tool_choice and (not retried_auto) and ("tool_choice" in err or "thinking mode" in err):
                print(f"[WARN] mode=forced-function 流式失败，降级为 auto: {err}")
                req_kwargs.pop("tool_choice", None)
                retried_auto = True
                continue
            raise

    marker_before_tool = (
        first_marker_ms is not None
        and first_tool_field_ms is not None
        and first_marker_ms <= first_tool_field_ms
    )

    print(f"first_chunk_ms={first_chunk_ms}")
    print(f"first_content_ms={first_content_ms}")
    print(f"first_marker_ms={first_marker_ms}")
    print(f"first_tool_field_ms={first_tool_field_ms}")
    print(f"marker_before_tool={marker_before_tool}")
    print(f"content_preview={content_buffer[:120]}")
    print(f"chunk_count={chunk_count}")


def _run_langchain_probe(api_key: str, base_url: str, model: str, tools: list, overwrite_content: str, scale: int) -> None:
    print(f"\n=== LangChain Stream Probe | scale={scale} | payload_chars={len(overwrite_content)} ===")
    try:
        from langchain_openai import ChatOpenAI
    except Exception as exc:
        print(f"[WARN] 跳过 LangChain 对比（未安装 langchain_openai）: {exc}")
        return

    llm = ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=0,
        streaming=True,
    ).bind_tools(tools)

    first_chunk_ms = None
    first_content_ms = None
    first_tool_chunk_ms = None
    first_tool_call_final_ms = None
    chunk_count = 0
    aggregated = None

    t0 = time.perf_counter()
    for chunk in llm.stream(_build_langchain_messages(overwrite_content)):
        chunk_count += 1
        dt_ms = int((time.perf_counter() - t0) * 1000)
        if first_chunk_ms is None:
            first_chunk_ms = dt_ms

        if aggregated is None:
            aggregated = chunk
        else:
            try:
                aggregated = aggregated + chunk
            except Exception:
                pass

        content = getattr(chunk, "content", None)
        if content and first_content_ms is None:
            first_content_ms = dt_ms

        tool_call_chunks = getattr(chunk, "tool_call_chunks", None) or []
        if tool_call_chunks and first_tool_chunk_ms is None:
            first_tool_chunk_ms = dt_ms

    if aggregated is not None:
        final_tool_calls = getattr(aggregated, "tool_calls", None) or []
        if final_tool_calls:
            first_tool_call_final_ms = int((time.perf_counter() - t0) * 1000)

    print(f"first_chunk_ms={first_chunk_ms}")
    print(f"first_content_ms={first_content_ms}")
    print(f"first_tool_chunk_ms={first_tool_chunk_ms}")
    print(f"first_tool_call_final_ms={first_tool_call_final_ms}")
    print(f"chunk_count={chunk_count}")


def run_probe() -> None:
    try:
        from openai import OpenAI
    except Exception as exc:
        print(f"[ERROR] 未安装 openai SDK: {exc}")
        print("请先在当前环境安装：pip install openai")
        return

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    base_url = _normalize_base_url(os.getenv("OPENAI_BASE_URL", "https://api.xiaomimimo.com"))
    model = os.getenv("OPENAI_MODEL", "").strip()

    if not api_key or not model:
        try:
            from llm.llm_mgr.config import get_decrypted_api_key
            import yaml
            from pathlib import Path

            if not api_key:
                decrypted = get_decrypted_api_key(base_url=base_url)
                if decrypted:
                    api_key = decrypted.strip()

            if not model:
                cfg_path = Path(__file__).resolve().parents[1] / "llm" / "llm_mgr" / "llm_mgr_cfg.yaml"
                if cfg_path.exists():
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        cfg = yaml.safe_load(f) or {}
                    for plat_name, plat_cfg in cfg.items():
                        if not isinstance(plat_cfg, dict):
                            continue
                        plat_url = _normalize_base_url(str(plat_cfg.get("base_url") or ""))
                        if plat_url != base_url:
                            continue
                        models_cfg = plat_cfg.get("models") or {}
                        if isinstance(models_cfg, dict) and models_cfg:
                            first_model = next(iter(models_cfg.values()))
                            if isinstance(first_model, str):
                                model = first_model.strip()
                            elif isinstance(first_model, dict):
                                model = str(first_model.get("model_name") or "").strip()
                            if model:
                                print(f"[INFO] 使用配置中的模型: platform={plat_name}, model={model}")
                                break
        except Exception as exc:
            print(f"[WARN] 自动读取项目 LLM 配置失败: {exc}")

    if not api_key:
        print("[ERROR] 缺少 OPENAI_API_KEY 环境变量。")
        print("请先在终端设置，不要把密钥写入代码。")
        return
    if not model:
        print("[ERROR] 缺少 OPENAI_MODEL 环境变量。")
        return

    client = OpenAI(api_key=api_key, base_url=base_url)
    base_content = _load_worldview_text()
    scales = _parse_scales(os.getenv("OPENAI_TEST_SCALES", "1,2"))
    marker_token = os.getenv("OPENAI_TEST_MARKER", "<<TOOL_START>>").strip() or "<<TOOL_START>>"

    tools = [
        {
            "type": "function",
            "function": {
                "name": "rewrite_worldview",
                "description": "用 overwrite_content 完整覆盖世界观文本",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "overwrite_content": {
                            "type": "string",
                            "description": "完整覆盖内容"
                        }
                    },
                    "required": ["overwrite_content"]
                }
            }
        }
    ]

    print("=== OpenAI tool stream raw probe ===")
    print(f"base_url={base_url}")
    print(f"model={model}")
    print(f"scales={scales}")
    print(f"marker_token={marker_token}")

    for scale in scales:
        payload = base_content * scale
        _run_openai_sdk_probe(client, model, tools, payload, scale)
        _run_openai_marker_then_tool_probe(
            client,
            model,
            tools,
            payload,
            scale,
            marker_token,
            force_tool_choice=False,
        )
        _run_openai_marker_then_tool_probe(
            client,
            model,
            tools,
            payload,
            scale,
            marker_token,
            force_tool_choice=True,
        )
        _run_langchain_probe(api_key, base_url, model, tools, payload, scale)


if __name__ == "__main__":
    run_probe()
