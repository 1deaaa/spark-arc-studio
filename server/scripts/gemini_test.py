import os

# --- 确保环境变量已设置 ---
# 必须在导入 llm_mgr 之前设置，因为它在导入时会读取环境变量
if "GEMINIX_API_KEY" not in os.environ:
    print("警告：环境变量 GEMINIX_API_KEY 未设置，将使用占位符。")
    os.environ["GEMINIX_API_KEY"] = "sk-your-real-key"

from llm_mgr import AIManager


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

        # 2. 使用 get_spec_sys_llm 方法直接获取 gemini-flash 实例，并设置思考预算为0
        # 这是最直接的测试方式
        print("\n[步骤 2] 正在创建 'gemini/gemini-flash' LLM 实例 (自动快速模式)...")
        llm = ai_manager.get_spec_sys_llm(
            platform_name="Google AIStudio",
            model_display_name="哈基米flash"
        )
        
        print("\n[成功] LLM 实例创建成功！")
        print(f"   - LLM 类型: {type(llm)}")

    except Exception as e:
        print(f"\n[错误] LLM 实例创建失败: {e}")
        return

    try:
        print("\n[步骤 3] 正在发送一个流式测试请求...")
        
        prompt = "写个关于少年、少女、雨的超长散文"
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

        print("\n[成功] 流式输出测试完成！")

    except Exception as e:
        print(f"\n[错误] 调用模型失败: {e}")

if __name__ == "__main__":
    test_aimanager_with_gemini()