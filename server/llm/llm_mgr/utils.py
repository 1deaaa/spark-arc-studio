"""
工具函数模块
"""

from typing import Dict, Any, List


def probe_platform_models(
    base_url: str,
    api_key: str,
    timeout: float = 8.0,
    raise_on_error: bool = False,
) -> List[Dict[str, Any]]:
    """探测 OpenAI 兼容平台的可用模型列表"""
    try:
        import requests
    except ImportError as e:
        msg = "缺少 requests 库，无法执行远程探测"
        if raise_on_error: raise ImportError(msg) from e
        print(f"[probe_platform_models] {msg}")
        return []
    
    if not base_url or not api_key:
        msg = "base_url 和 api_key 不能为空"
        if raise_on_error: raise ValueError(msg)
        print(f"[probe_platform_models] {msg}")
        return []
    
    url = base_url.rstrip("/")
    if not url.endswith("/models"):
        url = f"{url}/models" if url.endswith("/v1") else f"{url}/v1/models"

    headers = {"Authorization": f"Bearer {api_key}"}
    
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 401:
            if raise_on_error: raise PermissionError("鉴权失败 (401)")
            return []
        
        if not resp.ok:
            if raise_on_error: raise RuntimeError(f"HTTP {resp.status_code}")
            return []
        
        js = resp.json()
        items = js.get('data') if isinstance(js, dict) else None
        if not isinstance(items, list):
            return []
        
        out: List[Dict[str, Any]] = []
        for it in items:
            if isinstance(it, dict) and 'id' in it:
                out.append({'id': it['id'], 'raw': it})
        return out
        
    except Exception as e:
        msg = f"探测失败: {e}"
        print(f"[probe_platform_models] {msg}")
        if raise_on_error: raise
        return []
