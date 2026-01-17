
import os
import sys

# 将 server 目录添加到路径
sys.path.append(os.path.join(os.getcwd(), "server"))

from langchain_openai import OpenAIEmbeddings
from llm.llm_mgr.config import get_decrypted_api_key

def test_generic_embedding():
    print("=== 测试通用 OpenAI 兼容 Embedding ===")
    
    api_key = get_decrypted_api_key("阿里云百炼")
    base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    
    if not api_key:
        print("错误：未找到阿里云百炼的 API Key")
        return

    print(f"使用 Base URL: {base_url}")
    print(f"使用 API Key: {api_key[:8]}***")

    test_text = "你好，这是一段测试文本。"

    #修正后的 LangChain 调用
    try:
        print(f"\n[2] 尝试修正配置后的 LangChain (禁用 tiktoken 校验)...")
        embeddings_fixed = OpenAIEmbeddings(
            model="text-embedding-v4",
            api_key=api_key,
            base_url=base_url,
            check_embedding_ctx_length=False 
        )
        vector = embeddings_fixed.embed_query(test_text)
        print(f"成功！维度: {len(vector)}")
    except Exception as e:
        print(f"失败: {e}")

if __name__ == "__main__":
    test_generic_embedding()
