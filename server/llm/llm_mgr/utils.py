"""
工具函数模块
"""

from typing import Dict, Any, List


def normalize_base_url(url: str) -> str:
    """规范化 Base URL"""
    url = url.strip()
    if not url:
        return url
        
    # 移除末尾斜杠
    url = url.rstrip('/')
    
    # 如果以 /chat/completions 结尾，移除它
    if url.endswith('/chat/completions'):
        url = url[:-17]
        url = url.rstrip('/')
    
    # 自动补全 /v1
    # 如果 URL 不以 /v1 (或 v2, v3...) 结尾，则默认追加 /v1
    # 这样可以支持 https://api.deepseek.com -> https://api.deepseek.com/v1
    import re
    if not re.search(r'/v\d+$', url):
        url = f"{url}/v1"

    return url


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
    extra_body: Dict[str, Any] = None,
    return_json: bool = False,
) -> Any:
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
    if extra_body:
        payload.update(extra_body)
    
    
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
        if return_json:
            return data
            
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
             raise RuntimeError(f"无法解析响应内容: {str(data)[:100]}")
             
    except Exception as e:
        raise RuntimeError(f"测试失败: {e}")


def test_platform_embedding(
    base_url: str,
    api_key: str,
    model_name: str,
    input_text: str = "你好，这是一段测试文本。",
):
    """测试 Embedding 可用性"""
    try:
        from langchain_openai import OpenAIEmbeddings
    except ImportError as exc:
        raise ImportError("缺少 langchain_openai 库") from exc

    embeddings = OpenAIEmbeddings(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        check_embedding_ctx_length=False,
    )

    vector = embeddings.embed_query(input_text)
    return {
        "dims": len(vector) if vector else 0
    }


def stream_speed_test(
    base_url: str,
    api_key: str,
    model_name: str,
    timeout: float = 30.0,  # 增加超时，因为要等待推理完成
    extra_body: Dict[str, Any] = None,
):
    """
    流式测速逻辑
    1. 发送请求要求输出 1000 字左右文本
    2. 区分 reasoning_content（推理）和 content（正文）
    3. 首字延迟 = 从请求发送到首个正文 content 出现的时间（含推理时间）
    4. 5秒计时从首个正文 content 出现后开始
    5. 平均速度仅计算正文字符，时间从正文开始算
    """
    try:
        import requests
        import time
        import json
    except ImportError:
        raise ImportError("缺少必要库")

    url = base_url.rstrip("/")
    import re
    target_url = f"{url}/chat/completions" if re.search(r'/v\d+$', url) else f"{url}/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": "请写一篇关于未来科技的一千字左右的长篇文章，要求逻辑严密，文笔优美。请立即开始输出，不要废话。"}],
        "stream": True
    }
    if extra_body:
        payload.update(extra_body)

    request_start_time = time.time()  # 请求发送时间
    first_content_time = None  # 首个正文 content 的时间
    content_chars = 0  # 仅统计正文字符
    last_update_time = None
    is_reasoning = True  # 标记是否还在推理阶段
    
    try:
        resp = requests.post(target_url, headers=headers, json=payload, timeout=timeout, stream=True)
        
        if resp.status_code == 404 and not re.search(r'/v\d+$', url):
             target_url = f"{url}/v1/chat/completions"
             resp = requests.post(target_url, headers=headers, json=payload, timeout=timeout, stream=True)

        if not resp.ok:
            yield {"error": f"HTTP {resp.status_code}: {resp.text[:100]}"}
            return

        for line in resp.iter_lines():
            current_time = time.time()
            
            # 如果正文已经开始，检查是否超过5秒
            if first_content_time is not None:
                content_elapsed = current_time - first_content_time
                if content_elapsed >= 5.5:  # 稍微多给一点余量
                    break

            if not line:
                continue
            
            line_str = line.decode('utf-8')
            if line_str.startswith("data: "):
                data_str = line_str[6:]
                if data_str.strip() == "[DONE]":
                    break
                
                try:
                    data = json.loads(data_str)
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    
                    # 检查是否有 reasoning_content（DeepSeek 思考模式）
                    reasoning_content = delta.get("reasoning_content", "")
                    content = delta.get("content", "")
                    
                    # 如果有正文 content，说明推理阶段结束
                    if content:
                        if first_content_time is None:
                            # 首个正文出现！
                            first_content_time = current_time
                            last_update_time = current_time
                            is_reasoning = False
                            ftl = (first_content_time - request_start_time) * 1000  # 首字延迟 (ms)
                            yield {"type": "first_token", "ftl": ftl}
                        
                        content_chars += len(content)
                    
                    # 推理内容不计入速度统计，但可以发送状态更新
                    if reasoning_content and first_content_time is None:
                        # 可选：发送推理中的状态（让用户知道模型在思考）
                        pass
                        
                except:
                    continue

            # 只有在正文开始后才每秒更新速度
            if first_content_time is not None and last_update_time is not None:
                if current_time - last_update_time >= 1.0:
                    content_elapsed = current_time - first_content_time
                    avg_speed = content_chars / content_elapsed if content_elapsed > 0 else 0
                    yield {
                        "type": "update",
                        "speed": avg_speed,
                        "elapsed": int(content_elapsed),
                        "total_chars": content_chars
                    }
                    last_update_time = current_time

        # 最终结算
        end_time = time.time()
        if first_content_time is not None:
            content_elapsed = min(end_time - first_content_time, 5.0)
            final_speed = content_chars / content_elapsed if content_elapsed > 0 else 0
            ftl = (first_content_time - request_start_time) * 1000
        else:
            # 从未收到正文
            content_elapsed = 0
            final_speed = 0
            ftl = None
            
        yield {
            "type": "final",
            "speed": final_speed,
            "ftl": ftl,
            "total_chars": content_chars,
            "elapsed": content_elapsed
        }

    except Exception as e:
        yield {"error": str(e)}
