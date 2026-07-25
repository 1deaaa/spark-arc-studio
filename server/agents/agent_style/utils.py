import sys
import os
import re
import uuid
from pathlib import Path
from typing import Any

import warnings
import yaml

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
from core.json_state import json_state_lock, load_json_file, save_json_file_atomic

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

STYLE_PROFILE_FORMAT_VERSION = 3


# ==================== 路径与加载工具函数 ====================

def get_user_style_dir(user_id: str) -> Path:
    """获取用户专属的风格文件目录"""
    if not user_id:
        return LEGACY_STYLE_FILES_PATH
    path = Path(USERDATA_ROOT) / f"uid_{user_id}" / "styles"
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_style_filepath(style_name: str, user_id: str = None) -> Path:
    """根据展示名称构建风格档案路径，展示名称不再充当唯一标识。"""
    safe_name = normalize_style_name(style_name)
    if not safe_name:
        raise ValueError("风格名称不能为空")
    return get_user_style_dir(user_id) / f"{safe_name}.md"


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


def _normalize_identity(value: Any, prefix: str) -> str | None:
    """只接受本系统生成的稳定标识，避免名称再次混入 ID 字段。"""
    normalized = str(value or "").strip().lower()
    if re.fullmatch(rf"{re.escape(prefix)}_[0-9a-f]{{32}}", normalized):
        return normalized
    return None


def _new_identity(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _split_style_document(raw: str) -> tuple[dict[str, Any], str]:
    """用 YAML 解析 frontmatter，并返回元数据与 Markdown 正文。"""
    text = str(raw or "").lstrip("\ufeff").strip()
    if not text.startswith("---"):
        return {}, text

    rest = text[3:]
    separator_index = rest.find("\n---")
    if separator_index == -1:
        return {}, text

    header = rest[:separator_index]
    body = rest[separator_index + 4 :].lstrip("\r\n")
    try:
        metadata = yaml.safe_load(header) or {}
    except Exception:
        metadata = {}
    return (metadata if isinstance(metadata, dict) else {}), body.strip()


def parse_style_profile_document(raw: str) -> tuple[dict[str, Any], str]:
    """供导入链路复用的结构化 frontmatter 解析入口。"""
    return _split_style_document(raw)


def _build_style_document(metadata: dict[str, Any], body: str) -> str:
    ordered_metadata = {
        "style_id": metadata["style_id"],
        "style_name": metadata["style_name"],
        "created_at": metadata["created_at"],
        "format_version": STYLE_PROFILE_FORMAT_VERSION,
    }
    if metadata.get("source_chunks") is not None:
        ordered_metadata["source_chunks"] = metadata["source_chunks"]
    header = yaml.safe_dump(
        ordered_metadata,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    ).strip()
    return f"---\n{header}\n---\n\n{body.strip()}\n"


def _read_style_record_from_path(path: Path, user_id: str | None) -> dict[str, Any] | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception as exc:
        print(f"Failed to load style from {path}: {exc}")
        return None

    metadata, body = _split_style_document(raw)
    if not body:
        return None

    style_name = normalize_style_name(metadata.get("style_name"), fallback=path.stem) or path.stem
    style_id = _normalize_identity(metadata.get("style_id"), "style")
    if not style_id:
        return None
    return {
        "style_id": style_id,
        "style_name": style_name,
        "style_profile": body,
        "path": path,
    }


def load_style_profile_record(style_id: str, user_id: str = None) -> dict[str, Any] | None:
    """严格按唯一 style_id 加载风格档案。"""
    normalized_style_id = _normalize_identity(style_id, "style")
    if not normalized_style_id:
        return None

    style_dir = get_user_style_dir(user_id)
    for path in sorted(style_dir.glob("*.md")):
        record = _read_style_record_from_path(path, user_id)
        if record and record["style_id"] == normalized_style_id:
            return record
    return None


def find_style_profile_by_name(style_name: str, user_id: str = None) -> dict[str, Any] | None:
    """按展示名称查找风格，仅用于用户输入匹配和同名档案更新。"""
    safe_name = normalize_style_name(style_name)
    if not safe_name:
        return None
    path = get_style_filepath(safe_name, user_id)
    if not path.exists():
        return None
    record = _read_style_record_from_path(path, user_id)
    if record and record["style_name"] == safe_name:
        return record
    return None


def list_style_profiles(user_id: str = None) -> list[dict[str, str]]:
    """列出风格库的稳定身份摘要，style_id 是前后端唯一比较键。"""
    summaries: list[dict[str, str]] = []
    seen_style_ids: set[str] = set()
    for path in sorted(get_user_style_dir(user_id).glob("*.md")):
        record = _read_style_record_from_path(path, user_id)
        if not record or record["style_id"] in seen_style_ids:
            continue
        seen_style_ids.add(record["style_id"])
        summaries.append(
            {
                "style_id": record["style_id"],
                "style_name": record["style_name"],
            }
        )
    return summaries


def style_profile_summary(record: dict[str, Any] | None) -> dict[str, str] | None:
    """从内部档案记录提取可安全用于 API/事件的身份摘要。"""
    if not record:
        return None
    return {
        "style_id": str(record["style_id"]),
        "style_name": str(record["style_name"]),
    }


def _write_style_document_atomic(filepath: Path, content: str) -> None:
    """原子替换风格档案，避免分析完成时读取方看到半写入内容。"""
    temporary_path = filepath.with_name(f".{filepath.name}.{uuid.uuid4().hex}.tmp")
    try:
        with open(temporary_path, "w", encoding="utf-8") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, filepath)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def save_style_profile_to_file(
    style_name: str,
    style_profile: str,
    user_id: str = None,
    *,
    style_id: str | None = None,
    source_chunks: int | None = None,
    use_embedded_identity: bool = True,
) -> Path:
    """保存风格档案，并保证 style_id 是唯一且稳定的身份。"""
    if not isinstance(style_profile, str):
        raise ValueError("风格档案内容必须为 Markdown 字符串")

    safe_name = normalize_style_name(style_name, fallback="导入风格")
    if not safe_name:
        raise ValueError("风格名称不能为空")

    incoming_metadata, body = _split_style_document(style_profile)
    if not body:
        raise ValueError("风格档案内容为空")

    existing_record = find_style_profile_by_name(safe_name, user_id=user_id)
    resolved_style_id = (
        _normalize_identity(style_id, "style")
        or (
            _normalize_identity(incoming_metadata.get("style_id"), "style")
            if use_embedded_identity
            else None
        )
        or (existing_record or {}).get("style_id")
        or _new_identity("style")
    )
    identity_owner = load_style_profile_record(resolved_style_id, user_id=user_id)
    filepath = get_style_filepath(safe_name, user_id)
    if identity_owner and Path(identity_owner["path"]) != filepath:
        raise ValueError("style_id 已绑定到另一份风格档案")

    from datetime import datetime

    metadata = {
        "style_id": resolved_style_id,
        "style_name": safe_name,
        "created_at": str(
            incoming_metadata.get("created_at")
            or datetime.now().isoformat(timespec="seconds")
        ),
        "source_chunks": source_chunks
        if source_chunks is not None
        else incoming_metadata.get("source_chunks"),
    }
    filepath.parent.mkdir(parents=True, exist_ok=True)
    _write_style_document_atomic(filepath, _build_style_document(metadata, body))
    return filepath

def get_project_style_binding_path(user_id: str, project_name: str) -> Path:
    """获取项目风格绑定文件路径"""
    project_path = Path(get_project_path(user_id, project_name))
    project_path.mkdir(parents=True, exist_ok=True)
    return project_path / "style_binding.json"


def _style_binding_payload(record: dict[str, Any]) -> dict[str, str]:
    """项目绑定持久化只保存唯一标识，名称始终从风格档案解析。"""
    return {"style_id": str(record["style_id"])}


def save_project_style_binding(user_id: str, project_name: str, style_id: str) -> dict[str, Any]:
    """保存项目唯一显式风格绑定；同一项目始终只有这一份绑定文件。"""
    record = load_style_profile_record(style_id, user_id=user_id)
    if not record:
        raise ValueError("风格档案不存在")
    payload = _style_binding_payload(record)
    save_json_file_atomic(str(get_project_style_binding_path(user_id, project_name)), payload)
    return payload


def clear_project_style_binding(user_id: str, project_name: str) -> None:
    """取消项目应用；删除后该项目不再注入任何风格上下文。"""
    binding_path = get_project_style_binding_path(user_id, project_name)
    with json_state_lock(str(binding_path)):
        if binding_path.exists():
            binding_path.unlink()


def load_project_style_binding_record(user_id: str, project_name: str) -> dict[str, Any] | None:
    """读取项目当前唯一风格绑定，并返回可展示的风格摘要。"""
    binding_path = get_project_style_binding_path(user_id, project_name)
    payload = load_json_file(str(binding_path), dict)
    if not isinstance(payload, dict):
        return None
    style_id = _normalize_identity(payload.get("style_id"), "style")
    record = load_style_profile_record(style_id or "", user_id=user_id)
    return style_profile_summary(record)


def resolve_project_style_binding(user_id: str, project_name: str) -> dict[str, Any] | None:
    """解析项目当前应用的唯一风格；未绑定时返回 None。"""
    return load_project_style_binding_record(user_id, project_name)


def resolve_project_style_id(user_id: str, project_name: str) -> str | None:
    binding = resolve_project_style_binding(user_id, project_name)
    return str(binding["style_id"]) if binding else None


def load_project_style_profile(user_id: str, project_name: str) -> str | None:
    """读取项目当前生效的风格档案"""
    binding = resolve_project_style_binding(user_id, project_name)
    if not binding:
        return None
    return load_style_profile_from_file(binding["style_id"], user_id=user_id)


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


def load_style_profile_from_file(style_id: str, user_id: str = None) -> str | None:
    """按唯一 style_id 加载 Markdown 正文。"""
    record = load_style_profile_record(style_id, user_id=user_id)
    return str(record["style_profile"]) if record else None


def _read_markdown_profile(path: Path) -> str | None:
    """兼容旧内部调用：只读取 Markdown 正文。"""
    record = _read_style_record_from_path(path, None)
    return str(record["style_profile"]) if record else None

def delete_style_profile(style_id: str, user_id: str = None) -> bool:
    """按唯一 style_id 删除风格档案。"""
    record = load_style_profile_record(style_id, user_id=user_id)
    if not record:
        print(f"No style file found for: {style_id}")
        return False

    try:
        style_file = Path(record["path"])
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
