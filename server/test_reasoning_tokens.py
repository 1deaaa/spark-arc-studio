"""
测试 Reasoning Content 提取功能

本脚本直接使用 LLM_Manager 获取已配置的默认模型，
分别以 invoke 和 stream 方式调用，验证：
1. 推理内容（reasoning_content）是否能被 UsageTrackingCallback 正确捕获
2. Token 用量记录是否包含推理内容的贡献
3. 原始响应中推理相关字段的位置

使用方法：确保服务器环境已配置并启动过一次（数据库已初始化）
"""

import os
import sys
import json

# 添加 server 目录到 sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from langchain_core.messages import HumanMessage, SystemMessage

# ==================== 初始化 LLM_Manager ====================

def init_manager():
    """初始化 LLM Manager（模拟服务器启动）"""
    from llm.llm_mgr import LLM_Manager
    try:
        LLM_Manager.initialize_defaults()
        print("✅ LLM_Manager 初始化成功")
    except Exception as e:
        print(f"⚠️ LLM_Manager 初始化异常（可能已初始化）: {e}")
    return LLM_Manager


def get_test_llm(manager):
    """从数据库中查找通义Plus（支持推理的模型）并创建客户端"""
    from llm.llm_mgr.config import SYSTEM_USER_ID
    from llm.llm_mgr.models import LLMPlatform, LLModels
    
    # 从数据库查找通义Plus模型
    with manager.Session() as session:
        # 查找所有可用的非 embedding 模型，打印出来方便定位
        all_models = (
            session.query(LLModels, LLMPlatform.name)
            .join(LLMPlatform, LLModels.platform_id == LLMPlatform.id)
            .filter(LLModels.is_embedding == 0)
            .all()
        )
        print("📋 数据库中所有可用的 LLM 模型：")
        for model, plat_name in all_models:
            disabled = "❌" if getattr(model, 'disable', 0) else "✅"
            print(f"   {disabled} [{plat_name}] {model.display_name} -> {model.model_name} (pid={model.platform_id}, mid={model.id})")
        
        # 精确查找通义Plus
        target_model = None
        target_plat_name = None
        for model, plat_name in all_models:
            if 'plus' in (model.display_name or '').lower() and 'qwen' in (model.model_name or '').lower():
                target_model = model
                target_plat_name = plat_name
                break
        
        if not target_model:
            print("⚠️ 未找到通义Plus模型，回退到默认模型")
            client = manager.get_user_llm(user_id=SYSTEM_USER_ID)
        else:
            print(f"\n🎯 选中模型: [{target_plat_name}] {target_model.display_name} ({target_model.model_name})")
            print(f"   platform_id={target_model.platform_id}, model_id={target_model.id}")
            client = manager.get_user_llm(
                user_id=SYSTEM_USER_ID,
                platform_id=target_model.platform_id,
                model_id=target_model.id,
            )
    
    # 打印最终使用的模型信息
    llm = client.llm
    print(f"📌 实际模型: {getattr(llm, 'model_name', 'unknown')}")
    print(f"📌 Base URL: {getattr(llm, 'openai_api_base', getattr(llm, 'base_url', 'unknown'))}")
    
    return client


# ==================== 测试1：非流式调用 (invoke) ====================

def test_invoke(client):
    """测试非流式调用，检查响应中的 reasoning 字段"""
    print("\n" + "="*60)
    print("测试1：非流式调用 (invoke)")
    print("="*60)
    
    messages = [
        SystemMessage(content="你是一个数学助手。"),
        HumanMessage(content="请计算 17 × 23 等于多少？请先思考再回答。")
    ]
    
    response = client.invoke(messages)
    
    # 检查响应内容
    print(f"\n📝 回复内容 (content):")
    if isinstance(response.content, str):
        print(f"   {response.content[:500]}")
    elif isinstance(response.content, list):
        print(f"   [content 是列表, 共 {len(response.content)} 个块]")
        for i, block in enumerate(response.content):
            if isinstance(block, dict):
                print(f"   块 {i}: type={block.get('type')}, 长度={len(str(block.get('text', block.get('reasoning', ''))))}")
            else:
                print(f"   块 {i}: {type(block).__name__} = {str(block)[:100]}")
    
    # 检查 additional_kwargs
    kwargs = getattr(response, 'additional_kwargs', {})
    print(f"\n🔍 additional_kwargs 的键: {list(kwargs.keys())}")
    
    reasoning = kwargs.get('reasoning_content') or kwargs.get('reasoning')
    if reasoning:
        if isinstance(reasoning, str):
            print(f"   ✅ 发现 reasoning_content (字符串, {len(reasoning)} 字符)")
            print(f"   前200字: {reasoning[:200]}")
        elif isinstance(reasoning, dict):
            print(f"   ✅ 发现 reasoning_content (字典)")
            print(f"   键: {list(reasoning.keys())}")
            print(f"   内容: {json.dumps(reasoning, ensure_ascii=False)[:300]}")
        else:
            print(f"   ✅ 发现 reasoning_content (类型: {type(reasoning).__name__})")
    else:
        print("   ❌ 未发现 reasoning_content / reasoning 字段")
    
    # 检查 usage_metadata
    usage_meta = getattr(response, 'usage_metadata', None)
    if usage_meta:
        print(f"\n📊 usage_metadata:")
        if isinstance(usage_meta, dict):
            for k, v in usage_meta.items():
                print(f"   {k}: {v}")
        else:
            print(f"   {usage_meta}")
    else:
        print("\n📊 usage_metadata: 无")
    
    # 检查 response_metadata
    resp_meta = getattr(response, 'response_metadata', None)
    if resp_meta:
        print(f"\n📋 response_metadata 的键: {list(resp_meta.keys()) if isinstance(resp_meta, dict) else type(resp_meta)}")
        if isinstance(resp_meta, dict):
            usage_in_meta = resp_meta.get('token_usage') or resp_meta.get('usage')
            if usage_in_meta:
                print(f"   token_usage: {usage_in_meta}")
    
    return response


# ==================== 测试2：流式调用 (stream) ====================

def test_stream(client):
    """测试流式调用，检查每个 chunk 中的 reasoning 字段"""
    print("\n" + "="*60)
    print("测试2：流式调用 (stream)")
    print("="*60)
    
    messages = [
        SystemMessage(content="你是一个逻辑推理助手。"),
        HumanMessage(content="如果所有猫都是动物，所有动物都会呼吸，那么所有猫都会呼吸吗？请推理。")
    ]
    
    content_parts = []
    reasoning_parts = []
    chunk_count = 0
    first_chunk_with_reasoning = None
    
    for chunk in client.stream(messages):
        chunk_count += 1
        
        # 检查常规 content
        content = getattr(chunk, 'content', '')
        if isinstance(content, str) and content:
            content_parts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    if block.get('type') == 'reasoning':
                        reasoning_parts.append(block.get('reasoning', ''))
                        if first_chunk_with_reasoning is None:
                            first_chunk_with_reasoning = chunk_count
                    elif block.get('type') == 'text':
                        content_parts.append(block.get('text', ''))
        
        # 检查 additional_kwargs 中的 reasoning
        kwargs = getattr(chunk, 'additional_kwargs', {}) or {}
        r_content = kwargs.get('reasoning_content') or kwargs.get('reasoning')
        if r_content:
            if isinstance(r_content, str) and r_content:
                reasoning_parts.append(r_content)
                if first_chunk_with_reasoning is None:
                    first_chunk_with_reasoning = chunk_count
        
        # 只打印前5个和最后一个 chunk 的详细信息
        if chunk_count <= 3:
            print(f"\n   chunk #{chunk_count}:")
            print(f"     content 类型: {type(getattr(chunk, 'content', None)).__name__}")
            print(f"     content 值: {str(getattr(chunk, 'content', ''))[:80]}")
            ak = getattr(chunk, 'additional_kwargs', {}) or {}
            if ak:
                print(f"     additional_kwargs 键: {list(ak.keys())}")
    
    # 汇总结果
    full_content = "".join(content_parts)
    full_reasoning = "".join(reasoning_parts)
    
    print(f"\n📊 流式统计:")
    print(f"   总 chunk 数: {chunk_count}")
    print(f"   正文内容长度: {len(full_content)} 字符")
    print(f"   推理内容长度: {len(full_reasoning)} 字符")
    
    if full_reasoning:
        print(f"   ✅ 成功捕获推理内容！首次出现在 chunk #{first_chunk_with_reasoning}")
        print(f"   推理内容前300字: {full_reasoning[:300]}")
    else:
        print(f"   ❌ 未捕获到任何推理内容")
    
    print(f"\n   回复前200字: {full_content[:200]}")
    
    return full_content, full_reasoning


# ==================== 测试3：检查 UsageTrackingCallback 的累积 ====================

def test_callback_accumulation(client):
    """通过检查 callback 内的 _stream_buffers 来验证推理内容是否被正确累积"""
    print("\n" + "="*60)
    print("测试3：UsageTrackingCallback 内部累积验证")
    print("="*60)
    
    # 获取 callback 实例
    llm = client.llm
    callbacks = getattr(llm, 'callbacks', []) or []
    
    from llm.llm_mgr.tracked_model import UsageTrackingCallback
    
    tracker = None
    for cb in callbacks:
        if isinstance(cb, UsageTrackingCallback):
            tracker = cb
            break
    
    if not tracker:
        print("   ⚠️ 未找到 UsageTrackingCallback（可能通过 config 注入而非直接 callbacks）")
        # 尝试从 config 中查找
        config = getattr(llm, 'config', None)
        if config:
            cbs = getattr(config, 'callbacks', []) or []
            for cb in cbs:
                if isinstance(cb, UsageTrackingCallback):
                    tracker = cb
                    break
        
        if not tracker:
            print("   ❌ 无法定位 UsageTrackingCallback，跳过此测试")
            return
    
    print(f"   ✅ 找到 UsageTrackingCallback")
    print(f"   模型名称: {tracker.model_name}")
    print(f"   平台名称: {tracker.platform_name}")
    print(f"   用户ID: {tracker.user_id}")
    print(f"   当前 stream_buffers 数量: {len(tracker._stream_buffers)}")
    print(f"   当前 prompt_tokens_cache 数量: {len(tracker._prompt_tokens_cache)}")
    
    # 查询最近的用量记录
    try:
        from llm.llm_mgr.tracked_model import LLMUsage
        usage_handle = LLMUsage(
            user_id=tracker.user_id,
            model_id=tracker.model_id,
            session_maker=tracker._session_maker,
        )
        recent = usage_handle.get_usage_last_24h()
        print(f"\n   📊 近24小时用量统计:")
        for k, v in recent.items():
            print(f"     {k}: {v}")
    except Exception as e:
        print(f"   ⚠️ 查询用量失败: {e}")


# ==================== 主入口 ====================

def main():
    print("🚀 开始测试 Reasoning Content 提取功能")
    print("="*60)
    
    manager = init_manager()
    client = get_test_llm(manager)
    
    # 测试1: invoke
    try:
        test_invoke(client)
    except Exception as e:
        print(f"❌ 测试1失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 测试2: stream
    try:
        test_stream(client)
    except Exception as e:
        print(f"❌ 测试2失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 测试3: callback 状态
    try:
        test_callback_accumulation(client)
    except Exception as e:
        print(f"❌ 测试3失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*60)
    print("🏁 所有测试完成")
    print("="*60)


if __name__ == "__main__":
    main()
