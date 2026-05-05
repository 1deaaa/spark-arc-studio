"""
风格分析专用文本切分器

设计原则：
1. 按token数切分（默认30k，可配置8k-120k）
2. 保持句子边界完整，不截断句子
3. 实际切分逻辑统一委托到 core.file_ingest.chunking.TokenTextSplitter，
   本文件只负责兼容旧对外类型名/函数名与 token 上下限默认值。
"""

from typing import List, Tuple
from dataclasses import dataclass
from core.file_ingest.chunking import TokenTextSplitter

# 使用现有的 token 估算接口
try:
    from llm.agen_matchbox.estimate_tokens import estimate_tokens
except ImportError:
    # Fallback for relative imports or different environments
    try:
        from server.llm.agen_matchbox.estimate_tokens import estimate_tokens
    except ImportError:
        # Mock for local testing without full env
        print("Warning: Could not import estimate_tokens, using fallback.")
        def estimate_tokens(text, model=None):
            return len(text)



@dataclass
class TextChunk:
    """文本块数据结构"""
    text: str
    index: int
    total: int
    char_count: int
    estimated_tokens: int
    # 上一段末尾100字（用于上下文连接）
    previous_tail: str = ""


class StyleTextSplitter:
    """
    风格分析专用文本切分器（对外兼容壳）。

    实际切分行为完全由 TokenTextSplitter 完成，保留这个类主要是为了：
    - 兼容老调用点（workflow.py 等仍通过 split_text_for_style_analysis 拿 TextChunk）
    - 继续提供风格分析默认的 min/max tokens 约束
    """

    def __init__(
        self, 
        chunk_tokens: int = 30000,
        min_tokens: int = 8000,
        max_tokens: int = 120000
    ):
        """
        初始化切分器
        
        Args:
            chunk_tokens: 每块目标token数（默认30k）
            min_tokens: 最小token数（默认8k）
            max_tokens: 最大token数（默认120k）
        """
        # 边界校验
        self.chunk_tokens = max(min_tokens, min(chunk_tokens, max_tokens))
        self.min_tokens = min_tokens
        self.max_tokens = max_tokens
        self._delegate = TokenTextSplitter(
            chunk_tokens=self.chunk_tokens,
            min_tokens=min_tokens,
            max_tokens=max_tokens,
        )
    
    def _estimate_tokens(self, text: str) -> int:
        """估算文本的token数（使用通用标准）"""
        return estimate_tokens(text, model=None)  # 使用默认cl100k标准
    
    def split(self, text: str) -> List[TextChunk]:
        """
        切分文本为多个块
        
        Args:
            text: 待切分的完整文本
            
        Returns:
            TextChunk列表，每块包含文本和元数据
        """
        token_chunks = self._delegate.split(text)
        return [
            TextChunk(
                text=chunk.text,
                index=chunk.index,
                total=chunk.total,
                char_count=chunk.char_count,
                estimated_tokens=chunk.estimated_tokens,
                previous_tail=chunk.previous_tail,
            )
            for chunk in token_chunks
        ]
    
    def split_with_info(self, text: str) -> Tuple[List[TextChunk], dict]:
        """
        切分文本并返回统计信息
        
        Returns:
            (chunks, info) 其中 info 包含统计数据
        """
        chunks = self.split(text)
        
        info = {
            "total_chars": len(text),
            "total_tokens_estimated": self._estimate_tokens(text),
            "chunk_count": len(chunks),
            "chunk_tokens_target": self.chunk_tokens,
            "chunks_info": [
                {
                    "index": c.index,
                    "chars": c.char_count,
                    "tokens_est": c.estimated_tokens
                }
                for c in chunks
            ]
        }
        
        return chunks, info


# 便捷函数
def split_text_for_style_analysis(
    text: str, 
    chunk_tokens: int = 30000
) -> List[TextChunk]:
    """
    便捷函数：为风格分析切分文本
    
    Args:
        text: 待切分文本
        chunk_tokens: 每块目标token数
        
    Returns:
        TextChunk列表
    """
    splitter = StyleTextSplitter(chunk_tokens=chunk_tokens)
    return splitter.split(text)

