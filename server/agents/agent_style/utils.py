import sys
import os
import io
import json
import re
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_core.documents import Document
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

# 添加父目录到 Python 路径以支持导入 llm_mgr
# 假设当前文件在 server/agents/agent_style/utils.py
# 我们需要 server/ 目录在 path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from llm.llm_mgr import AIManager,get_decrypted_api_key
from agents.agent_utils import get_agent_usage_key

# 设置stdout编码为UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ==================== 配置与初始化 ====================

# 初始化模型 (Deprecated: Agents should use get_style_llm with user_id)
# llm = AIManager().get_user_llm() 
# We keep it for backward compatibility if any script uses it directly, but agents should avoid it.
llm = AIManager().get_user_llm() 

def get_style_llm(user_id: str):
    """获取 Style Agent 专用的 LLM 实例"""
    usage_key = get_agent_usage_key(user_id, "agent_style")
    return AIManager().get_user_llm(user_id, usage_key=usage_key)

embeddings = DashScopeEmbeddings(
    dashscope_api_key=get_decrypted_api_key("阿里云百炼"),
    model="text-embedding-v4",
)

# 向量库路径配置 (存储在 test 目录下，保持与原脚本一致的相对位置)
# 原脚本在 server/agent_test/agent_style.py，数据在 server/test/author_style_db
# 新脚本在 server/agents/agent_style/utils.py
# 我们需要指向 server/test/ 目录
_SERVER_DIR = Path(__file__).resolve().parent.parent.parent
_AGENT_TEST_DIR = _SERVER_DIR / "test"
_AGENT_TEST_DIR.mkdir(exist_ok=True) # 确保 test 目录存在

VECTOR_STORE_BASE_PATH = _AGENT_TEST_DIR / "author_style_db"
VECTOR_STORE_BASE_PATH.mkdir(exist_ok=True)
STYLE_FILES_PATH = _AGENT_TEST_DIR / "author_styles"
STYLE_FILES_PATH.mkdir(exist_ok=True)


# ==================== 数据类定义 ====================

@dataclass
class ContentChunk:
    """文本块数据类"""
    text: str
    metadata: Dict[str, Any]


@dataclass
class AgentAnalysisResult:
    """Agent分析结果"""
    agent_name: str
    dimensions: List[str]
    analysis: Dict[str, Any]
    examples: List[str]
    success: bool
    error: str = None


# ==================== 智能文本分块器 (增强版) ====================

class SmartTextChunker:
    """
    语义保持型文本分块器
    策略：
    1. 保持句子完整性（3-5个完整句子为一块）
    2. 合理的chunk大小（300-500字符）
    3. 适当重叠避免上下文丢失
    4. 不做类型预判，让embedding模型自己理解
    """
    
    def __init__(self, chunk_size=400, chunk_overlap=80):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def chunk_text(self, full_text: str, author_id: str) -> List[ContentChunk]:
        """
        基于句子的语义分块
        """
        chunks = []
        
        # 按段落分割
        paragraphs = [p.strip() for p in full_text.split('\n') if p.strip()]
        
        for para_idx, paragraph in enumerate(paragraphs):
            # 按句子分割（保持完整句子，包括标点）
            sentences = re.split(r'([。！？；.!?;])', paragraph)
            sentences = [''.join(sentences[i:i+2]).strip() for i in range(0, len(sentences)-1, 2) if sentences[i].strip()]
            
            current_chunk = ""
            
            for sentence in sentences:
                # 尝试添加句子到当前chunk
                test_chunk = current_chunk + sentence
                
                # 如果超过大小限制，保存当前chunk并开始新chunk
                if len(test_chunk) > self.chunk_size and current_chunk:
                    chunks.append(ContentChunk(
                        text=current_chunk.strip(),
                        metadata={
                            "author_id": author_id,
                            "para_idx": para_idx,
                            "char_count": len(current_chunk),
                            "sentence_count": current_chunk.count('。') + current_chunk.count('！') + current_chunk.count('？')
                        }
                    ))
                    # 保留overlap部分
                    if len(current_chunk) > self.chunk_overlap:
                        overlap_text = current_chunk[-self.chunk_overlap:]
                        # 找到最近的句子边界
                        last_period = max(overlap_text.rfind('。'), overlap_text.rfind('！'), overlap_text.rfind('？'))
                        if last_period > 0:
                            current_chunk = overlap_text[last_period+1:] + sentence
                        else:
                            current_chunk = sentence
                    else:
                        current_chunk = sentence
                else:
                    current_chunk = test_chunk
            
            # 添加剩余内容
            if current_chunk.strip():
                chunks.append(ContentChunk(
                    text=current_chunk.strip(),
                    metadata={
                        "author_id": author_id,
                        "para_idx": para_idx,
                        "char_count": len(current_chunk),
                        "sentence_count": current_chunk.count('。') + current_chunk.count('！') + current_chunk.count('？')
                    }
                ))
        
        print(f"✓ 语义分块完成: {len(chunks)} 个chunks")
        if chunks:
            print(f"  - 平均chunk大小: {sum(c.metadata['char_count'] for c in chunks) // len(chunks)} 字符")
            print(f"  - 平均句子数: {sum(c.metadata['sentence_count'] for c in chunks) / len(chunks):.1f} 句/chunk")
        
        return chunks


# ==================== 路径与加载工具函数 ====================

def get_style_filepath(author_id: str) -> Path:
    """构建作者风格文件的路径"""
    return STYLE_FILES_PATH / f"{author_id}.json"

def get_vector_store_path(author_id: str) -> Path:
    """获取作者专属向量库路径"""
    return VECTOR_STORE_BASE_PATH / author_id

def load_style_profile_from_file(author_id: str) -> Dict | None:
    """从本地文件加载作者风格内容"""
    filepath = get_style_filepath(author_id)
    if not filepath.exists():
        print(f"风格文件不存在: {filepath}")
        return None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"从文件 {filepath} 加载风格失败: {e}")
        return None

def load_author_vector_store(author_id: str) -> FAISS | None:
    """加载作者专属向量库"""
    vs_path = get_vector_store_path(author_id)
    if not vs_path.exists():
        return None
    try:
        return FAISS.load_local(str(vs_path), embeddings, allow_dangerous_deserialization=True)
    except Exception as e:
        print(f"加载向量库失败: {e}")
        return None

def list_all_authors() -> List[str]:
    """列出所有已保存的作者"""
    authors = []
    
    # 从风格文件目录获取
    if STYLE_FILES_PATH.exists():
        for file in STYLE_FILES_PATH.glob("*.json"):
            authors.append(file.stem)
    
    if authors:
        print(f"\n已保存的作者列表:")
        for i, author_id in enumerate(authors, 1):
            print(f"  {i}. {author_id}")
        print()
    else:
        print("暂无已保存的作者风格")
    
    return authors

def delete_author_style(author_id: str) -> bool:
    """删除指定作者的风格数据"""
    import shutil
    
    success = True
    
    # 删除风格文件
    style_file = get_style_filepath(author_id)
    if style_file.exists():
        try:
            os.remove(style_file)
            print(f"✓ 已删除风格文件: {style_file}")
        except Exception as e:
            print(f"✗ 删除风格文件失败: {e}")
            success = False
    
    # 删除向量库
    vs_path = get_vector_store_path(author_id)
    if vs_path.exists():
        try:
            shutil.rmtree(vs_path)
            print(f"✓ 已删除向量库: {vs_path}")
        except Exception as e:
            print(f"✗ 删除向量库失败: {e}")
            success = False
    
    return success


# ==================== EPUB文本提取函数 ====================

def extract_text_from_epub(epub_path: str, merge_short_chapters=True, min_chunk_size=3000):
    """从epub中提取文本"""
    book = epub.read_epub(epub_path)
    raw_chapters = []

    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            text = soup.get_text()
            text = text.strip()
            if text:
                raw_chapters.append(text)
    
    if not merge_short_chapters:
        return raw_chapters
    
    # 合并短章节
    merged_chapters = []
    current_chunk = ""
    
    for chapter in raw_chapters:
        current_chunk += chapter + "\n\n"
        
        if len(current_chunk) >= min_chunk_size:
            merged_chapters.append(current_chunk.strip())
            current_chunk = ""
    
    if current_chunk.strip():
        merged_chapters.append(current_chunk.strip())
    
    return merged_chapters