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
from langchain_core.documents import Document
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

# 添加父目录到 Python 路径以支持导入 llm_mgr
# 假设当前文件在 server/agents/agent_style/utils.py
# 我们需要 server/ 目录在 path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from llm.llm_mgr import AIManager
from core.utils import USERDATA_ROOT

# 设置stdout编码为UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ==================== 配置与初始化 ====================

# 初始化模型 (Deprecated: Agents should use get_style_llm with user_id)
# llm = AIManager().get_user_llm() 
# We keep it for backward compatibility if any script uses it directly, but agents should avoid it.
llm = AIManager().get_user_llm() 

def get_style_llm(user_id: str):
    """
    获取 Style Agent 专用的 LLM 实例。
    
    注意：Style Agent 使用 invoke() 而非 stream()，
    因此必须设置 streaming=False 以避免 Stream 对象错误。
    """
    return AIManager().get_user_llm(user_id, agent_name="agent_style", streaming=False)

_embedding_cache = {}


def get_style_embeddings(user_id: str = None):
    """获取 Style Agent 使用的 Embedding 实例（按用户缓存）"""
    cache_key = str(user_id) if user_id is not None else "_default"
    if cache_key in _embedding_cache:
        return _embedding_cache[cache_key]

    emb = AIManager().get_user_embedding(user_id=user_id)
    _embedding_cache[cache_key] = emb
    return emb


# 默认 Embedding（兼容旧代码）
embeddings = get_style_embeddings()

# 向量库路径配置 (存储在 test 目录下，保持与原脚本一致的相对位置)
# 原脚本在 server/agent_test/agent_style.py，数据在 server/test/author_style_db
# 新脚本在 server/agents/agent_style/utils.py
# 我们需要指向 server/test/ 目录
_SERVER_DIR = Path(__file__).resolve().parent.parent.parent
_AGENT_TEST_DIR = _SERVER_DIR / "test"
_AGENT_TEST_DIR.mkdir(exist_ok=True) # 确保 test 目录存在

# Legacy paths for backward compatibility
LEGACY_VECTOR_STORE_BASE_PATH = _AGENT_TEST_DIR / "author_style_db"
LEGACY_VECTOR_STORE_BASE_PATH.mkdir(exist_ok=True)
LEGACY_STYLE_FILES_PATH = _AGENT_TEST_DIR / "author_styles"
LEGACY_STYLE_FILES_PATH.mkdir(exist_ok=True)


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

def get_user_style_dir(user_id: str) -> Path:
    """获取用户专属的风格文件目录"""
    if not user_id:
        return LEGACY_STYLE_FILES_PATH
    path = Path(USERDATA_ROOT) / f"uid_{user_id}" / "styles"
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_user_vector_store_dir(user_id: str) -> Path:
    """获取用户专属的向量库目录"""
    if not user_id:
        return LEGACY_VECTOR_STORE_BASE_PATH
    path = Path(USERDATA_ROOT) / f"uid_{user_id}" / "style_vectors"
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_style_filepath(author_id: str, user_id: str = None) -> Path:
    """构建作者风格文件的路径"""
    return get_user_style_dir(user_id) / f"{author_id}.json"

def get_vector_store_path(author_id: str, user_id: str = None) -> Path:
    """获取作者专属向量库路径"""
    return get_user_vector_store_dir(user_id) / author_id

def load_style_profile_from_file(author_id: str, user_id: str = None) -> Dict | None:
    """从本地文件加载作者风格内容"""
    filepath = get_style_filepath(author_id, user_id)
    if not filepath.exists():
        # Try legacy path if user path fails and user_id is provided
        if user_id:
             legacy_path = get_style_filepath(author_id, None)
             if legacy_path.exists():
                 print(f"Found style in legacy path: {legacy_path}")
                 filepath = legacy_path
             else:
                 print(f"风格文件不存在: {filepath}")
                 return None
        else:
            print(f"风格文件不存在: {filepath}")
            
            # Check if user has other styles available and give a hint
            if user_id:
                style_dir = get_user_style_dir(user_id)
                if style_dir.exists():
                    others = [f.stem for f in style_dir.glob("*.json") if f.name != filepath.name]
                    if others:
                        print(f"提示: 当前项目未绑定风格。您现有可用风格: {', '.join(others)}")
                        print(f"请在 Style Agent 界面选择一个风格并点击'应用到当前项目'。")

            return None
            
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"从文件 {filepath} 加载风格失败: {e}")
        return None

def load_author_vector_store(author_id: str, user_id: str = None) -> FAISS | None:
    """加载作者专属向量库"""
    vs_path = get_vector_store_path(author_id, user_id)
    if not vs_path.exists():
        # Try legacy path
        if user_id:
            legacy_path = get_vector_store_path(author_id, None)
            if legacy_path.exists():
                vs_path = legacy_path
            else:
                return None
        else:
            return None
            
    try:
        return FAISS.load_local(str(vs_path), get_style_embeddings(user_id), allow_dangerous_deserialization=True)
    except Exception as e:
        print(f"加载向量库失败: {e}")
        return None

def list_all_authors(user_id: str = None) -> List[str]:
    """列出所有已保存的作者"""
    authors = []
    
    style_dir = get_user_style_dir(user_id)
    
    # 从风格文件目录获取
    if style_dir.exists():
        for file in style_dir.glob("*.json"):
            authors.append(file.stem)
    
    if authors:
        print(f"\n已保存的作者列表:")
        for i, author_id in enumerate(authors, 1):
            print(f"  {i}. {author_id}")
        print()
    else:
        print("暂无已保存的作者风格")
    
    return authors

def delete_author_style(author_id: str, user_id: str = None) -> bool:
    """删除指定作者的风格数据"""
    import shutil
    
    success = True
    
    # 删除风格文件
    style_file = get_style_filepath(author_id, user_id)
    if style_file.exists():
        try:
            os.remove(style_file)
            print(f"✓ 已删除风格文件: {style_file}")
        except Exception as e:
            print(f"✗ 删除风格文件失败: {e}")
            success = False
    
    # 删除向量库
    vs_path = get_vector_store_path(author_id, user_id)
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

def calculate_text_md5(text: str) -> str:
    """计算文本的MD5值"""
    import hashlib
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def extract_json_from_response(content: str) -> str:
    """从 LLM 响应中提取 JSON 内容"""
    content = content.strip()
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    return content