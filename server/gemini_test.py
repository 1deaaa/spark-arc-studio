import os
from llm_mgr import AIManager

# --- 确保环境变量已设置 ---
# 在实际应用中，您应该在运行环境里设置好这个变量
if "GEMINIX_API_KEY" not in os.environ:
    print("警告：环境变量 GEMINIX_API_KEY 未设置，将使用占位符。")
    os.environ["GEMINIX_API_KEY"] = "sk-your-real-key"


def test_aimanager_with_gemini():
    """
    使用 AIManager 测试 gemini-flash 模型的流式输出。
    """
    print("--- 开始使用 AIManager 测试 Gemini Flash 模型 ---")

    try:
        # 1. 初始化 AIManager
        # 它会自动在 llm_mgr.py 旁边创建或连接 llm_config.db
        ai_manager = AIManager()
        print("\n[步骤 1] AIManager 初始化成功。")

        # 2. 使用 create_llm 方法直接获取 gemini-flash 实例
        # 这是最直接的测试方式
        print("\n[步骤 2] 正在创建 'gemini/gemini-flash' LLM 实例...")
        llm = ai_manager.create_llm(platform="gemini", model="gemini-flash")
        
        print("\n[成功] LLM 实例创建成功！")
        print(f"   - LLM 类型: {type(llm)}")

    except Exception as e:
        print(f"\n[错误] LLM 实例创建失败: {e}")
        return

    try:
        print("\n[步骤 3] 正在发送一个流式测试请求...")
        
        prompt = "写个超长散文"
        stream = llm.stream(prompt)
        
        print("\n[成功] 已成功从您的服务器接收到响应流！")
        print("-" * 20)
        print("模型回复内容 (流式):")
        full_response = ""
        for chunk in stream:
            if chunk.content is not None:
                print(chunk.content, end="", flush=True)
                full_response += chunk.content
        print("\n" + "-" * 20)
        
        if "gemini-2.5-flash" in full_response.lower():
             print("\n[验证成功] 模型在回复中确认了自己是 gemini-2.5-flash。")
        else:
             print("\n[验证提示] 模型回复中未明确提及 'gemini-2.5-flash'，请根据内容判断是否正确。")

        print("\n[成功] 流式输出测试完成！")

    except Exception as e:
        print(f"\n[错误] 调用模型失败: {e}")

if __name__ == "__main__":
    test_aimanager_with_gemini()