"""
对比原生 HTTP / OpenAI SDK / LangChain 在同一网关下的请求行为。

用途
----
这个脚本专门用于诊断一类非常隐蔽的问题：

1. 同一个 Base URL、同一个 API Key、同一个模型，`requests.post()` 可以成功；
2. 但 OpenAI Python SDK 或 LangChain `ChatOpenAI` 却立刻报
   `Your request was blocked.`；
3. 根因不是请求体，而是某些兼容网关会拦截 OpenAI SDK 默认的
   `User-Agent: OpenAI/Python x.y.z`。

脚本会输出 6 组对照实验：
1. 原生 requests 基线请求
2. 原生 requests + 被拦截的 OpenAI 默认 User-Agent
3. OpenAI SDK 默认请求
4. OpenAI SDK + 兼容 User-Agent
5. LangChain ChatOpenAI 默认请求
6. LangChain ChatOpenAI + 兼容 User-Agent

环境变量
--------
优先从以下环境变量读取：

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OPENAI_MODEL`
- `OPENAI_TEST_MESSAGE`            测试消息，默认“只回复OK”
- `OPENAI_TEST_BLOCKED_USER_AGENT` 复现拦截用 UA，默认 `OpenAI/Python 2.8.0`
- `SPARKARC_OPENAI_COMPAT_USER_AGENT`
    兼容模式使用的 UA，默认 `SparkArc/1.0`

如果前三项未提供，脚本会尝试从项目数据库读取：
- 用户 ID：`OPENAI_TEST_USER_ID`，默认 `1`
- 用途槽位：`OPENAI_TEST_USAGE_KEY`，默认 `main`

PowerShell 示例
---------------
$env:OPENAI_BASE_URL = "https://api.dwill.top/v1"
$env:OPENAI_MODEL = "gpt-5.4"
python server/test/test_sdk_user_agent_block.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import requests

SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))


def _normalize_base_url(raw: str) -> str:
    value = (raw or "").strip().rstrip("/")
    return value


def _safe_preview(text: str, limit: int = 400) -> str:
    return (text or "")[:limit]


def _print_case_result(name: str, ok: bool, detail: str) -> None:
    print(f"\n=== {name} ===")
    print("OK" if ok else "FAIL")
    print(detail)


def _resolve_target_from_project() -> Optional[Dict[str, str]]:
    try:
        from llm.llm_mgr import LLM_Manager
        from llm.llm_mgr.models import LLMPlatform, LLModels, UserModelUsage

        user_id = os.getenv("OPENAI_TEST_USER_ID", "1").strip() or "1"
        usage_key = os.getenv("OPENAI_TEST_USAGE_KEY", "main").strip() or "main"

        with LLM_Manager.Session() as session:
            slot = (
                session.query(UserModelUsage)
                .filter_by(user_id=user_id, usage_key=usage_key)
                .first()
            )
            if not slot:
                return None

            platform = session.query(LLMPlatform).filter_by(id=slot.selected_platform_id).first()
            model = session.query(LLModels).filter_by(id=slot.selected_model_id).first()
            if not platform or not model:
                return None

            api_key = LLM_Manager._get_effective_api_key(session, user_id, platform)
            if not api_key:
                return None

            return {
                "api_key": api_key,
                "base_url": platform.base_url,
                "model": model.model_name,
                "user_id": user_id,
                "usage_key": usage_key,
                "platform_name": platform.name,
                "display_name": model.display_name or model.model_name,
            }
    except Exception as exc:
        print(f"[WARN] 从项目配置自动解析测试目标失败: {exc}")
        return None


def _resolve_target() -> Dict[str, str]:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    base_url = _normalize_base_url(os.getenv("OPENAI_BASE_URL", ""))
    model = (os.getenv("OPENAI_MODEL") or "").strip()

    if api_key and base_url and model:
        return {
            "api_key": api_key,
            "base_url": base_url,
            "model": model,
            "source": "env",
        }

    resolved = _resolve_target_from_project()
    if resolved:
        resolved["source"] = "project-db"
        resolved["base_url"] = _normalize_base_url(resolved.get("base_url", ""))
        return resolved

    raise RuntimeError(
        "缺少测试目标。请设置 OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL，"
        "或确保项目数据库里已有可用的 main 模型配置。"
    )


def _run_requests_case(
    name: str,
    url: str,
    api_key: str,
    payload: Dict[str, Any],
    extra_headers: Optional[Dict[str, str]] = None,
) -> None:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)

    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    detail = (
        f"status={resp.status_code}\n"
        f"request_headers={json.dumps(headers, ensure_ascii=False)}\n"
        f"request_body={json.dumps(payload, ensure_ascii=False)}\n"
        f"response_body={_safe_preview(resp.text)}"
    )
    _print_case_result(name, resp.ok, detail)


def _run_openai_sdk_case(
    name: str,
    base_url: str,
    api_key: str,
    model: str,
    message: str,
    default_headers: Optional[Dict[str, str]] = None,
) -> None:
    try:
        from openai import OpenAI
    except Exception as exc:
        _print_case_result(name, False, f"未安装 openai SDK: {exc}")
        return

    try:
        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            default_headers=default_headers,
            timeout=60,
        )
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": message}],
        )
        detail = (
            f"default_headers={json.dumps(default_headers or {}, ensure_ascii=False)}\n"
            f"response={_safe_preview(json.dumps(resp.model_dump(), ensure_ascii=False))}"
        )
        _print_case_result(name, True, detail)
    except Exception as exc:
        detail = (
            f"default_headers={json.dumps(default_headers or {}, ensure_ascii=False)}\n"
            f"error_type={type(exc).__name__}\n"
            f"error={exc}"
        )
        _print_case_result(name, False, detail)


def _run_langchain_case(
    name: str,
    base_url: str,
    api_key: str,
    model: str,
    message: str,
    default_headers: Optional[Dict[str, str]] = None,
) -> None:
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage
    except Exception as exc:
        _print_case_result(name, False, f"未安装 langchain_openai: {exc}")
        return

    try:
        llm = ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            default_headers=default_headers,
            timeout=60,
        )
        resp = llm.invoke([HumanMessage(content=message)])
        content = getattr(resp, "content", resp)
        detail = (
            f"default_headers={json.dumps(default_headers or {}, ensure_ascii=False)}\n"
            f"response={_safe_preview(str(content))}"
        )
        _print_case_result(name, True, detail)
    except Exception as exc:
        detail = (
            f"default_headers={json.dumps(default_headers or {}, ensure_ascii=False)}\n"
            f"error_type={type(exc).__name__}\n"
            f"error={exc}"
        )
        _print_case_result(name, False, detail)


def main() -> None:
    target = _resolve_target()
    api_key = target["api_key"]
    base_url = target["base_url"]
    model = target["model"]
    message = (os.getenv("OPENAI_TEST_MESSAGE") or "只回复OK").strip() or "只回复OK"

    blocked_user_agent = (
        os.getenv("OPENAI_TEST_BLOCKED_USER_AGENT") or "OpenAI/Python 2.8.0"
    ).strip() or "OpenAI/Python 2.8.0"
    compat_user_agent = (
        os.getenv("SPARKARC_OPENAI_COMPAT_USER_AGENT") or "SparkArc/1.0"
    ).strip() or "SparkArc/1.0"

    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": message}],
    }

    print("=== SDK User-Agent block diagnose ===")
    print(f"source={target.get('source', 'unknown')}")
    print(f"base_url={base_url}")
    print(f"model={model}")
    if target.get("platform_name"):
        print(f"platform={target.get('platform_name')}")
    if target.get("display_name"):
        print(f"display_name={target.get('display_name')}")
    if target.get("user_id"):
        print(f"user_id={target.get('user_id')} usage_key={target.get('usage_key')}")
    print(f"blocked_user_agent={blocked_user_agent}")
    print(f"compat_user_agent={compat_user_agent}")

    _run_requests_case("requests_baseline", url, api_key, payload)
    _run_requests_case(
        "requests_with_blocked_user_agent",
        url,
        api_key,
        payload,
        extra_headers={"User-Agent": blocked_user_agent},
    )

    _run_openai_sdk_case("openai_sdk_default", base_url, api_key, model, message)
    _run_openai_sdk_case(
        "openai_sdk_compat_user_agent",
        base_url,
        api_key,
        model,
        message,
        default_headers={"User-Agent": compat_user_agent},
    )

    _run_langchain_case("langchain_default", base_url, api_key, model, message)
    _run_langchain_case(
        "langchain_compat_user_agent",
        base_url,
        api_key,
        model,
        message,
        default_headers={"User-Agent": compat_user_agent},
    )


if __name__ == "__main__":
    main()
