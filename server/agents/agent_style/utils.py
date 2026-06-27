import sys
import os
import io
import json
import re
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

import warnings

from langchain_core.documents import Document
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

# 优先使用 lxml（C 扩展，比默认 html.parser 快 3~5 倍）。若环境里未安装 lxml，
# 自动降级回内置 html.parser，保持兼容。
try:
    import lxml  # noqa: F401
    _EPUB_PARSER = "lxml"
except Exception:
    _EPUB_PARSER = "html.parser"

# epub 章节正文实际是 XHTML，但用 HTML parser 解析也能正确取出 get_text()，
# 性能上不必切换为 xml parser；这里只静音 BeautifulSoup 4.13+ 抛出的一次性提示。
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# 添加父目录到 Python 路径以支持导入 matchbox
# 假设当前文件在 server/agents/agent_style/utils.py
# 我们需要 server/ 目录在 path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from llm.agen_matchbox import matchbox
from core.utils import USERDATA_ROOT, get_project_path

# 设置stdout编码为UTF-8，避免替换 pytest/ASGI 捕获用的底层 buffer。
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

# ==================== 配置与初始化 ====================

# 初始化模型 (Deprecated: Agents should use get_style_llm with user_id)
# llm = AIManager().get_user_llm()
# We keep it for backward compatibility if any script uses it directly, but agents should avoid it.
# [Refactored] Use None to avoid eager DB init at persistent module level
llm = None

def get_style_llm(user_id: str):
    """
    获取 Style Agent 专用的 LLM 实例。
    
    Style Agent 使用 invoke() 调用，流式/非流式由调用方式决定，不需传入 streaming 参数。
    """
    return matchbox().get_user_llm(user_id, agent_name="agent_style")

_embedding_cache = {}


def get_style_embeddings(user_id: str = None):
    """获取 Style Agent 使用的 Embedding 实例（按用户缓存）"""
    cache_key = str(user_id) if user_id is not None else "_default"
    if cache_key in _embedding_cache:
        return _embedding_cache[cache_key]

    emb = matchbox().get_user_embedding(user_id=user_id)
    _embedding_cache[cache_key] = emb
    return emb


# 默认 Embedding（兼容旧代码，保持惰性初始化）
embeddings = None

# 向量库路径配置 (存储在 test 目录下，保持与原脚本一致的相对位置)
# 原脚本在 server/agent_test/agent_style.py，数据在 server/test/author_style_db
# 新脚本在 server/agents/agent_style/utils.py
# 我们需要指向 server/test/ 目录
_SERVER_DIR = Path(__file__).resolve().parent.parent.parent
_AGENT_TEST_DIR = _SERVER_DIR / "test"
_AGENT_TEST_DIR.mkdir(exist_ok=True) # 确保 test 目录存在

# Legacy paths for backward compatibility
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
        
        print(f"✓ Semantic chunking complete: {len(chunks)} chunks")
        if chunks:
            print(f"  - Avg chunk size: {sum(c.metadata['char_count'] for c in chunks) // len(chunks)} chars")
            print(f"  - Avg sentence count: {sum(c.metadata['sentence_count'] for c in chunks) / len(chunks):.1f} sentences/chunk")
        
        return chunks


# ==================== 路径与加载工具函数 ====================

def get_user_style_dir(user_id: str) -> Path:
    """获取用户专属的风格文件目录"""
    if not user_id:
        return LEGACY_STYLE_FILES_PATH
    path = Path(USERDATA_ROOT) / f"uid_{user_id}" / "styles"
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_style_filepath(author_id: str, user_id: str = None) -> Path:
    """构建作者风格文件的路径"""
    return get_user_style_dir(user_id) / f"{author_id}.json"


def normalize_style_name(style_name: Any, fallback: str = "") -> str:
    """规范化风格名称，避免导入/导出文件名穿越用户风格目录。"""
    raw = str(style_name or "").strip()
    if not raw:
        raw = fallback
    raw = str(raw or "").strip()
    # Windows 文件名非法字符与路径分隔符统一替换，保留中文、空格与常见标点。
    normalized = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "-", raw)
    normalized = re.sub(r"\s+", " ", normalized).strip(" .")
    if not normalized:
        normalized = str(fallback or "").strip(" .")
    return normalized[:120].strip(" .")


def make_unique_style_name(user_id: str, preferred_name: str) -> str:
    """基于期望名称生成用户风格库内不冲突的风格名。"""
    base = normalize_style_name(preferred_name, fallback="导入风格") or "导入风格"
    candidate = base
    index = 2
    while get_style_filepath(candidate, user_id).exists():
        candidate = normalize_style_name(f"{base}-{index}", fallback=f"导入风格-{index}") or f"导入风格-{index}"
        index += 1
    return candidate


def save_style_profile_to_file(style_name: str, style_profile: Dict, user_id: str = None) -> Path:
    """保存风格档案 JSON，并返回写入路径。"""
    safe_name = normalize_style_name(style_name, fallback="导入风格")
    if not safe_name:
        raise ValueError("风格名称不能为空")
    if not isinstance(style_profile, dict) or not style_profile:
        raise ValueError("风格档案内容为空或格式不正确")
    filepath = get_style_filepath(safe_name, user_id)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(style_profile, f, ensure_ascii=False, indent=2)
    return filepath

def get_project_style_binding_path(user_id: str, project_name: str) -> Path:
    """获取项目风格绑定文件路径"""
    project_path = Path(get_project_path(user_id, project_name))
    project_path.mkdir(parents=True, exist_ok=True)
    return project_path / "style_binding.json"


def save_project_style_binding(user_id: str, project_name: str, style_name: str) -> None:
    """保存项目绑定的风格名称"""
    binding_path = get_project_style_binding_path(user_id, project_name)
    with open(binding_path, "w", encoding="utf-8") as f:
        json.dump({"style_name": style_name}, f, ensure_ascii=False, indent=2)


def load_project_style_binding(user_id: str, project_name: str) -> str | None:
    """读取项目绑定的风格名称"""
    binding_path = get_project_style_binding_path(user_id, project_name)
    if not binding_path.exists():
        return None
    try:
        with open(binding_path, "r", encoding="utf-8") as f:
            payload = json.load(f) or {}
        style_name = str(payload.get("style_name") or "").strip()
        return style_name or None
    except Exception as e:
        print(f"Failed to read project style binding: {e}")
        return None


def resolve_project_style_author_id(user_id: str, project_name: str) -> str | None:
    """解析项目当前生效的风格 author_id（优先级：项目绑定 > 用户级默认 > 旧版兼容 > None）"""
    # 1. 项目级绑定（最高优先级）
    bound_style_name = load_project_style_binding(user_id, project_name)
    if bound_style_name:
        bound_profile = load_style_profile_from_file(bound_style_name, user_id=user_id)
        if bound_profile is not None:
            return bound_style_name

    # 2. 用户级默认风格
    default_style_name = load_user_default_style_binding(user_id)
    if default_style_name:
        default_profile = load_style_profile_from_file(default_style_name, user_id=user_id)
        if default_profile is not None:
            return default_style_name

    # 3. 旧版兼容（项目副本风格）
    legacy_author_id = f"{user_id}_{project_name}"
    legacy_profile = load_style_profile_from_file(legacy_author_id, user_id=user_id)
    if legacy_profile is not None:
        return legacy_author_id

    return None


def load_project_style_profile(user_id: str, project_name: str) -> Dict | None:
    """读取项目当前生效的风格档案"""
    author_id = resolve_project_style_author_id(user_id, project_name)
    if not author_id:
        return None
    return load_style_profile_from_file(author_id, user_id=user_id)


def format_style_profile_for_prompt(
    style_profile: Any,
    *,
    fallback: str = "用户未提供参考风格档案。请根据故事主题、世界观氛围和角色特质，自行选择最合适的文笔风格进行创作。",
    raw_char_limit: int = 6000,
) -> str:
    """把风格档案压成写作模型更容易执行的提示块。

    风格分析产物本身是 Author OS JSON。直接整段注入时，模型容易把它当
    静态资料读过就忘。本函数保留原始档案，同时前置一张“风格执行卡”，
    明确句子呼吸、情绪处理、感官焦点、对白机制和禁忌。
    """
    if style_profile is None:
        return fallback
    if isinstance(style_profile, str):
        return style_profile.strip() or fallback
    if not isinstance(style_profile, dict):
        try:
            raw = json.dumps(style_profile, ensure_ascii=False, indent=2)
            return raw.strip() or fallback
        except Exception:
            return fallback

    def _value(path: str) -> str:
        current: Any = style_profile
        for key in path.split("."):
            if not isinstance(current, dict):
                return ""
            current = current.get(key)
        if isinstance(current, str):
            return current.strip()
        if isinstance(current, list):
            return "；".join(str(item).strip() for item in current if str(item).strip())
        if current is None:
            return ""
        return str(current).strip()

    execution_items = [
        ("标志性手法", _value("coordinator.signature_style")),
        ("独特性摘要", _value("coordinator.distinctive_summary")),
        ("句子呼吸", _value("verbal_physicality.sentence_weight_and_breath")),
        ("修饰密度", _value("verbal_physicality.modifier_density")),
        ("修辞迁移", _value("verbal_physicality.metaphor_gene")),
        ("情绪处理", _value("emotional_processing.emotion_presentation")),
        ("高潮处理", _value("emotional_processing.climax_handling")),
        ("感官焦点", _value("sensory_and_attention.sensory_priority")),
        ("注意力偏移", _value("sensory_and_attention.focus_shifting")),
        ("对白效率", _value("interpersonal_field.dialogue_efficiency")),
        ("沉默机制", _value("interpersonal_field.silence_mechanism")),
        ("叙述距离", _value("interpersonal_field.narrator_temperature")),
    ]
    negative_constraints = _value("coordinator.negative_constraints")

    lines = ["### 风格执行卡（写作时优先执行）"]
    has_signal = False
    for label, value in execution_items:
        if value and value != "待后续补充":
            has_signal = True
            lines.append(f"- {label}：{value}")
    if negative_constraints:
        has_signal = True
        lines.append(f"- 禁止/避开：{negative_constraints}")

    if has_signal:
        lines.append("")
        lines.append("### 本次写作执行要求")
        lines.append("- 先模仿“句子呼吸、情绪处理、感官焦点、对白机制”，不要只复制表层词汇。")
        lines.append("- 对白、旁白和心理活动都要遵守风格执行卡；禁止在结尾额外升华或解释风格。")
        lines.append("- 若风格档案与当前剧情类型冲突，以当前剧情真实情绪为主，只迁移底层表达方法。")
    else:
        lines.append("- 风格档案缺少可执行字段；请只把下方原始档案作为弱参考。")

    raw = json.dumps(style_profile, ensure_ascii=False, indent=2)
    if raw_char_limit > 0 and len(raw) > raw_char_limit:
        raw = raw[:raw_char_limit].rstrip() + "\n...（原始风格档案已截断）"
    lines.append("")
    lines.append("### 原始风格档案（补充参考）")
    lines.append(raw)
    return "\n".join(lines).strip()


# ==================== 用户级默认风格 ====================

def get_user_default_style_binding_path(user_id: str) -> Path:
    """获取用户级默认风格绑定文件路径"""
    user_dir = Path(USERDATA_ROOT) / f"uid_{user_id}"
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir / "default_style.json"


def save_user_default_style_binding(user_id: str, style_name: str | None) -> None:
    """
    保存用户级默认风格绑定。
    style_name 为 None 或空字符串时，删除默认绑定（即取消默认风格）。
    """
    binding_path = get_user_default_style_binding_path(user_id)
    if not style_name or not style_name.strip():
        # 取消默认绑定：删除文件
        if binding_path.exists():
            binding_path.unlink()
        return
    with open(binding_path, "w", encoding="utf-8") as f:
        json.dump({"style_name": style_name.strip()}, f, ensure_ascii=False, indent=2)


def load_user_default_style_binding(user_id: str) -> str | None:
    """读取用户级默认风格名称，未设置则返回 None"""
    binding_path = get_user_default_style_binding_path(user_id)
    if not binding_path.exists():
        return None
    try:
        with open(binding_path, "r", encoding="utf-8") as f:
            payload = json.load(f) or {}
        style_name = str(payload.get("style_name") or "").strip()
        return style_name or None
    except Exception as e:
        print(f"Failed to read user default style binding: {e}")
        return None

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
                 print(f"Style file not found: {filepath}")
                 return None
        else:
            print(f"Style file not found: {filepath}")
            
            # Check if user has other styles available and give a hint
            if user_id:
                style_dir = get_user_style_dir(user_id)
                if style_dir.exists():
                    others = [f.stem for f in style_dir.glob("*.json") if f.name != filepath.name]
                    if others:
                        print(f"Tip: No style bound to current project. Available styles: {', '.join(others)}")
                        print(f"Please select a style in the Style Agent UI and click 'Apply to Current Project'.")

            return None
            
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Failed to load style from {filepath}: {e}")
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
        print(f"\nSaved author style list:")
        for i, author_id in enumerate(authors, 1):
            print(f"  {i}. {author_id}")
        print()
    else:
        print("No saved author styles")
    
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
            print(f"✓ Deleted style file: {style_file}")
        except Exception as e:
            print(f"✗ Failed to delete style file: {e}")
            success = False
    
    return success


# ==================== EPUB文本提取函数 ====================

def extract_text_from_epub(epub_path: str, merge_short_chapters=True, min_chunk_size=3000):
    """从epub中提取文本"""
    book = epub.read_epub(epub_path)
    raw_chapters = []

    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            # 使用 _EPUB_PARSER（优先 lxml，不可用则 html.parser）
            soup = BeautifulSoup(item.get_content(), _EPUB_PARSER)
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
