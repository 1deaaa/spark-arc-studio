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
    # 智能拼接 endpoint: 如果用户填写的 base_url 已经包含 /v1，则直接加 /models；否则尝试加 /models (兼容非v1) 或 /v1/models
    # 这里为了通用性，优先相信用户填写的 base_url 已经指向了 API 根路径
    # 如果 base_url 类似 https://api.openai.com/v1，则目标为 https://api.openai.com/v1/models
    # 如果 base_url 类似 https://api.openai.com，则尝试 https://api.openai.com/models (Ollama等) 或 https://api.openai.com/v1/models
    
    # 简单的策略：如果以 /v\d+ 结尾，直接拼 /models
    import re
    if re.search(r'/v\d+$', url):
        target_url = f"{url}/models"
    else:
        # 否则默认它是一个没有版本号的根，尝试加 /v1/models? 或者直接 /models?
        # 很多兼容接口虽然没有写 /v1，但也可以响应 /v1/models。
        # 但有些（如 Ollama）是 /api/tags。这里保持原有的 OpenAI 兼容逻辑
        target_url = f"{url}/models"

    headers = {"Authorization": f"Bearer {api_key}"}
    
    try:
        resp = requests.get(target_url, headers=headers, timeout=timeout)
        
        # 如果直接请求 /models 失败(404)，尝试 /v1/models
        if resp.status_code == 404 and not re.search(r'/v\d+$', url):
             target_url = f"{url}/v1/models"
             resp = requests.get(target_url, headers=headers, timeout=timeout)

        if resp.status_code == 401:
            if raise_on_error: raise PermissionError("鉴权失败 (401)")
            return []
        
        if not resp.ok:
            if raise_on_error: raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:100]}")
            return []
        
        js = resp.json()
        items = js.get('data') if isinstance(js, dict) else None
        
        # 兼容 Ollama /api/tags 格式？不，这里明确说是 "OpenAI 兼容平台"
        # 部分非标接口直接返回 list
        if isinstance(js, list):
            items = js

        if not isinstance(items, list):
            return []
        
        out: List[Dict[str, Any]] = []
        for it in items:
            if isinstance(it, dict) and 'id' in it:
                out.append({'id': it['id'], 'raw': it})
            # 兼容直接是字符串列表的情况
            elif isinstance(it, str):
                out.append({'id': it, 'raw': {}})
                
        return out
        
    except Exception as e:
        msg = f"探测失败: {e}"
        print(f"[probe_platform_models] {msg}")
        if raise_on_error: raise
        return []


def test_platform_chat(
    base_url: str,
    api_key: str,
    model_name: str,
    timeout: float = 10.0,
) -> str:
    """测试模型对话连接"""
    try:
        import requests
    except ImportError:
        raise ImportError("缺少 requests 库")
        
    url = base_url.rstrip("/")
    import re
    if re.search(r'/v\d+$', url):
        target_url = f"{url}/chat/completions"
    else:
        target_url = f"{url}/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": "Hello!"}],
        "max_tokens": 10
    }
    
    try:
        resp = requests.post(target_url, headers=headers, json=payload, timeout=timeout)
        
        # 同样的 404 重试逻辑
        if resp.status_code == 404 and not re.search(r'/v\d+$', url):
             target_url = f"{url}/v1/chat/completions"
             resp = requests.post(target_url, headers=headers, json=payload, timeout=timeout)

        if not resp.ok:
            try:
                err_msg = resp.json().get('error', {}).get('message') or resp.text
            except:
                err_msg = resp.text
            raise RuntimeError(f"HTTP {resp.status_code}: {err_msg[:200]}")
            
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
             raise RuntimeError(f"无法解析响应内容: {str(data)[:100]}")
             
    except Exception as e:
        raise RuntimeError(f"测试失败: {e}")
