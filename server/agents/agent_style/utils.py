import sys
import os
import json
import re
from pathlib import Path
from typing import List, Dict, Any

import warnings

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

def get_style_llm(user_id: str):
    """
    获取 Style Agent 专用的 LLM 实例。

    Style Agent 使用 invoke() 调用,流式/非流式由调用方式决定,不需传入 streaming 参数。
    """
    return matchbox().get_user_llm(user_id, agent_name="agent_style")


# Legacy 路径:无 user_id 时风格档案的落盘位置(已极少使用)
_SERVER_DIR = Path(__file__).resolve().parent.parent.parent
_AGENT_TEST_DIR = _SERVER_DIR / "test"
_AGENT_TEST_DIR.mkdir(exist_ok=True)
LEGACY_STYLE_FILES_PATH = _AGENT_TEST_DIR / "author_styles"
LEGACY_STYLE_FILES_PATH.mkdir(exist_ok=True)


# ==================== 路径与加载工具函数 ====================

def get_user_style_dir(user_id: str) -> Path:
    """获取用户专属的风格文件目录"""
    if not user_id:
        return LEGACY_STYLE_FILES_PATH
    path = Path(USERDATA_ROOT) / f"uid_{user_id}" / "styles"
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_style_filepath(author_id: str, user_id: str = None) -> Path:
    """构建作者风格文件的 .md 路径。"""
    return get_user_style_dir(user_id) / f"{author_id}.md"


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


def save_style_profile_to_file(style_name: str, style_profile: str, user_id: str = None) -> Path:
    """把 Markdown 风格档案写入 `{name}.md`,自动补最小化 frontmatter。"""
    if not isinstance(style_profile, str):
        raise ValueError("风格档案内容必须为 Markdown 字符串")

    safe_name = normalize_style_name(style_name, fallback="导入风格")
    if not safe_name:
        raise ValueError("风格名称不能为空")

    body = style_profile.strip()
    if not body:
        raise ValueError("风格档案内容为空")

    style_dir = get_user_style_dir(user_id)
    style_dir.mkdir(parents=True, exist_ok=True)
    filepath = style_dir / f"{safe_name}.md"

    if not body.startswith("---"):
        from datetime import datetime
        timestamp = datetime.now().isoformat(timespec="seconds")
        safe_id = safe_name.replace("'", "''")
        frontmatter = (
            "---\n"
            f"style_name: '{safe_id}'\n"
            f"created_at: '{timestamp}'\n"
            "format_version: 2\n"
            "---\n\n"
        )
        body = frontmatter + body

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(body)
        if not body.endswith("\n"):
            f.write("\n")
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
) -> str:
    """把风格档案注入下游 system prompt。

    风格档案现在统一是 Markdown 字符串(LLM 提取时已经写好「风格执行卡」),
    直接透传给下游即可,不再做任何二次拼装。

    - None / 空字符串 → fallback
    - 字符串 → strip 后返回
    - 其他类型 → fallback(防御性兜底,理论上不应出现)
    """
    if not isinstance(style_profile, str):
        return fallback
    return style_profile.strip() or fallback


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

def load_style_profile_from_file(author_id: str, user_id: str = None) -> str | None:
    """从本地文件加载作者风格内容(Markdown 字符串,已剥掉 frontmatter)。"""
    style_dir = get_user_style_dir(user_id)
    md_path = style_dir / f"{author_id}.md"

    if md_path.exists():
        return _read_markdown_profile(md_path)

    # legacy 兜底:公共目录(无 user_id 时实际上就是这条路径)
    if user_id:
        legacy_dir = get_user_style_dir(None)
        legacy_md = legacy_dir / f"{author_id}.md"
        if legacy_md.exists():
            print(f"Found style in legacy path: {legacy_md}")
            return _read_markdown_profile(legacy_md)

    print(f"Style file not found: {md_path}")
    if user_id and style_dir.exists():
        others = [f.stem for f in style_dir.glob("*.md") if f.stem != author_id]
        if others:
            print(f"Tip: No style bound to current project. Available styles: {', '.join(others)}")
            print("Please select a style in the Style Agent UI and click 'Apply to Current Project'.")
    return None


def _read_markdown_profile(path: Path) -> str | None:
    """读取 Markdown 档案,剥掉 yaml frontmatter,只返回正文。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
    except Exception as e:
        print(f"Failed to load style from {path}: {e}")
        return None

    body = raw.strip()
    if body.startswith("---"):
        rest = body[3:]
        sep_idx = rest.find("\n---")
        if sep_idx != -1:
            body = rest[sep_idx + 4:].lstrip("\n")
    return body.strip() or None

def list_all_authors(user_id: str = None) -> List[str]:
    """列出所有已保存的作者(只识别 .md)。"""
    authors: List[str] = []
    style_dir = get_user_style_dir(user_id)

    if style_dir.exists():
        for file in sorted(style_dir.glob("*.md")):
            authors.append(file.stem)

    if authors:
        print("\nSaved author style list:")
        for i, author_id in enumerate(authors, 1):
            print(f"  {i}. {author_id}")
        print()
    else:
        print("No saved author styles")

    return authors


def delete_author_style(author_id: str, user_id: str = None) -> bool:
    """删除指定作者的 Markdown 风格档案。"""
    style_file = get_user_style_dir(user_id) / f"{author_id}.md"
    if not style_file.exists():
        print(f"No style file found for: {author_id}")
        return False

    try:
        os.remove(style_file)
        print(f"✓ Deleted style file: {style_file}")
        return True
    except Exception as e:
        print(f"✗ Failed to delete style file: {e}")
        return False


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
