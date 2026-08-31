from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from .utils import (
    SYSTEM_CHARACTER_DESCRIPTIONS,
    SYSTEM_CHARACTER_IDS,
    SYSTEM_CHARACTER_NAMES,
    get_project_characters_path,
)


CHARACTER_STORE_FILENAME = "characters.json"
LEGACY_CHARACTER_BIND_FILENAME = "chr.bind"
SYSTEM_CHARACTER_NARRATOR_ID = -1
SYSTEM_CHARACTER_UNKNOWN_ID = -2
_STORE_LOCK = threading.RLock()


def get_character_store_path(user_id: str, project_name: str) -> str:
    return os.path.join(get_project_characters_path(user_id, project_name), CHARACTER_STORE_FILENAME)


def get_character_store_path_from_project_root(project_root: str) -> str:
    return os.path.join(project_root, "chr", CHARACTER_STORE_FILENAME)


def _system_records() -> dict[str, dict[str, str]]:
    return {
        str(character_id): {
            "name": SYSTEM_CHARACTER_NAMES[character_id],
            "content": SYSTEM_CHARACTER_DESCRIPTIONS[character_id],
        }
        for character_id in (SYSTEM_CHARACTER_NARRATOR_ID, SYSTEM_CHARACTER_UNKNOWN_ID)
    }


def _normalize_records(data: Any) -> dict[str, dict[str, str]]:
    if not isinstance(data, dict):
        raise ValueError("角色文件顶层必须是 JSON 对象")
    records: dict[str, dict[str, str]] = {}
    for raw_id, raw_record in data.items():
        character_id = str(int(raw_id))
        if not isinstance(raw_record, dict):
            raise ValueError(f"角色 {character_id} 必须是 JSON 对象")
        name = str(raw_record.get("name") or "").strip()
        content = str(raw_record.get("content") or "")
        if not name:
            raise ValueError(f"角色 {character_id} 缺少姓名")
        records[character_id] = {"name": name, "content": content}
    return records


def _ordered_records(records: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    return {character_id: records[character_id] for character_id in sorted(records, key=lambda value: int(value))}


def _legacy_character_name(value: Any) -> str:
    """从旧版 chr.bind 条目中提取角色名。"""
    if isinstance(value, dict):
        return str(value.get("name") or "").strip()
    return str(value or "").strip()


def _legacy_character_content(character_path: Path, character_name: str) -> str:
    """读取旧版角色正文，并去掉文件首行重复的角色名。"""
    if not character_path.is_file():
        return ""
    try:
        text = character_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    if not text or not character_name:
        return text

    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != character_name:
        return text
    return "".join(lines[1:]).lstrip("\r\n")


def _read_legacy_character_records(store_path: str) -> dict[str, dict[str, str]]:
    """只读解析旧版 chr.bind 与数字角色文件，供新仓库过渡兼容。"""
    character_dir = Path(store_path).parent
    bind_path = character_dir / LEGACY_CHARACTER_BIND_FILENAME
    if not bind_path.is_file():
        return {}
    try:
        data = json.loads(bind_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}

    records: dict[str, dict[str, str]] = {}
    for raw_id, raw_record in data.items():
        try:
            character_id = str(int(raw_id))
        except (TypeError, ValueError):
            continue
        if int(character_id) in SYSTEM_CHARACTER_IDS:
            continue
        name = _legacy_character_name(raw_record)
        if not name:
            continue
        records[character_id] = {
            "name": name,
            "content": _legacy_character_content(
                character_dir / f"{character_id}.txt",
                name,
            ),
        }
    return records


def read_character_records_from_path(store_path: str) -> dict[str, dict[str, str]]:
    canonical_path = Path(store_path)
    if canonical_path.is_file():
        with open(canonical_path, "r", encoding="utf-8") as handle:
            records = _normalize_records(json.load(handle))
    else:
        records = {}

    legacy_records = _read_legacy_character_records(store_path)
    if not canonical_path.is_file() and not legacy_records:
        raise FileNotFoundError(store_path)
    for character_id, record in legacy_records.items():
        records.setdefault(character_id, record)
    for character_id, record in _system_records().items():
        records.setdefault(character_id, record)
    return _ordered_records(records)


def read_character_records(user_id: str, project_name: str) -> dict[str, dict[str, str]]:
    store_path = ensure_character_store(user_id, project_name)
    with _STORE_LOCK:
        return read_character_records_from_path(store_path)


def _write_records_to_path(store_path: str, records: dict[str, dict[str, str]]) -> None:
    normalized = _ordered_records(_normalize_records(records))
    target = Path(store_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(normalized, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temporary, target)


def ensure_character_store(user_id: str, project_name: str) -> str:
    store_path = get_character_store_path(user_id, project_name)
    with _STORE_LOCK:
        if not os.path.isfile(store_path):
            _write_records_to_path(store_path, _system_records())
            return store_path
        records = read_character_records_from_path(store_path)
        missing_system = {
            character_id: record
            for character_id, record in _system_records().items()
            if character_id not in records
        }
        if missing_system:
            records.update(missing_system)
            _write_records_to_path(store_path, records)
    return store_path


def write_character_records(user_id: str, project_name: str, records: dict[str, dict[str, str]]) -> None:
    store_path = ensure_character_store(user_id, project_name)
    with _STORE_LOCK:
        next_records = _normalize_records(records)
        for character_id, record in _system_records().items():
            next_records[character_id] = record
        _write_records_to_path(store_path, next_records)


def upsert_character(user_id: str, project_name: str, character_id: int | str, *, name: str, content: str) -> None:
    cid = str(int(character_id))
    with _STORE_LOCK:
        records = read_character_records(user_id, project_name)
        records[cid] = {"name": str(name).strip(), "content": str(content or "")}
        write_character_records(user_id, project_name, records)


def delete_character_record(user_id: str, project_name: str, character_id: int | str) -> bool:
    cid = str(int(character_id))
    if int(cid) in SYSTEM_CHARACTER_IDS:
        raise ValueError("系统角色不能删除")
    with _STORE_LOCK:
        records = read_character_records(user_id, project_name)
        existed = records.pop(cid, None) is not None
        if existed:
            write_character_records(user_id, project_name, records)
        return existed


def replace_regular_characters(user_id: str, project_name: str, characters: list[tuple[str, str]]) -> int:
    records = _system_records()
    for character_id, (name, content) in enumerate(characters):
        records[str(character_id)] = {"name": str(name).strip(), "content": str(content or "").strip()}
    write_character_records(user_id, project_name, records)
    return len(characters)


def upsert_regular_characters(user_id: str, project_name: str, characters: list[tuple[str, str]]) -> tuple[int, int]:
    """按角色名原子更新一批普通角色，并为新角色分配稳定 ID。"""
    with _STORE_LOCK:
        records = read_character_records(user_id, project_name)
        name_to_id = {
            str(record.get("name") or "").strip(): character_id
            for character_id, record in records.items()
            if int(character_id) >= 0
        }
        next_id = next_character_id(records)
        created = 0
        updated = 0
        for name, content in characters:
            normalized_name = str(name).strip()
            character_id = name_to_id.get(normalized_name)
            if character_id is None:
                character_id = str(next_id)
                next_id += 1
                name_to_id[normalized_name] = character_id
                created += 1
            else:
                updated += 1
            records[character_id] = {
                "name": normalized_name,
                "content": str(content or "").strip(),
            }
        write_character_records(user_id, project_name, records)
        return created, updated


def reset_regular_characters(user_id: str, project_name: str) -> None:
    write_character_records(user_id, project_name, _system_records())


def next_character_id(records: dict[str, dict[str, str]]) -> int:
    regular_ids = [int(character_id) for character_id in records if int(character_id) >= 0]
    return max(regular_ids, default=-1) + 1


def load_character_id_name_map(user_id: str, project_name: str, *, include_narrator: bool = True, include_system: bool = True) -> dict[str, str]:
    result: dict[str, str] = {}
    for character_id, record in read_character_records(user_id, project_name).items():
        numeric_id = int(character_id)
        if numeric_id == SYSTEM_CHARACTER_NARRATOR_ID and not include_narrator:
            continue
        if numeric_id in SYSTEM_CHARACTER_IDS and numeric_id != SYSTEM_CHARACTER_NARRATOR_ID and not include_system:
            continue
        result[character_id] = record["name"]
    return result
