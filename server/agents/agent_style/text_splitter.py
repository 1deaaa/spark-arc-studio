"""
风格分析专用文本切分器

设计原则：
1. 按token数切分（默认30k，可配置8k-120k）
2. 保持句子边界完整，不截断句子
3. 使用现有 estimate_tokens 接口进行精确计算
"""

import re
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
    风格分析专用文本切分器
    
    特点：
    - 按token数切分，使用通用标准计算
    - 保持句子完整，在句号/问号/叹号处切分
    - 支持中英文标点
    - 每块附带上一段末尾100字便于上下文连接
    """
    
    # 句子结束标点（中英文）
    SENTENCE_ENDINGS = re.compile(r'[。！？.!?]["\'」』）\)]*')
    
    # 上一段末尾字符数
    TAIL_CHARS = 100
    
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
    
    def _find_sentence_boundaries(self, text: str) -> List[int]:
        """
        找到所有句子边界位置
        
        Returns:
            句子结束位置的索引列表（包含标点）
        """
        boundaries = []
        for match in self.SENTENCE_ENDINGS.finditer(text):
            boundaries.append(match.end())
        return boundaries
    
    def _split_at_boundaries(self, text: str, boundaries: List[int]) -> List[str]:
        """
        在句子边界处切分文本，每块不超过 chunk_tokens
        """
        if not boundaries:
            # 没有句子边界，作为单块返回
            return [text] if text.strip() else []
        
        chunks = []
        current_start = 0
        current_end = 0
        
        for boundary in boundaries:
            # 检查加入这个句子后是否超过限制
            potential_chunk = text[current_start:boundary]
            potential_tokens = self._estimate_tokens(potential_chunk)
            
            if potential_tokens > self.chunk_tokens:
                # 当前块已满，保存并开始新块
                if current_end > current_start:
                    chunk_text = text[current_start:current_end].strip()
                    if chunk_text:
                        chunks.append(chunk_text)
                    current_start = current_end
                
                # 如果单个句子就超过限制，强制保存（这是极端情况）
                if self._estimate_tokens(text[current_start:boundary]) > self.chunk_tokens:
                    chunk_text = text[current_start:boundary].strip()
                    if chunk_text:
                        chunks.append(chunk_text)
                    current_start = boundary
                    current_end = boundary
                    continue
            
            current_end = boundary
        
        # 保存最后一块
        if current_start < len(text):
            remaining = text[current_start:].strip()
            if remaining:
                remaining_tokens = self._estimate_tokens(remaining)
                # 如果剩余部分太短且有前一块，考虑合并
                if chunks and remaining_tokens < self.chunk_tokens * 0.2:
                    last_chunk = chunks[-1]
                    combined_tokens = self._estimate_tokens(last_chunk + "\n" + remaining)
                    if combined_tokens < self.chunk_tokens * 1.2:
                        chunks[-1] = last_chunk + "\n" + remaining
                    else:
                        chunks.append(remaining)
                else:
                    chunks.append(remaining)
        
        return chunks
    
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

