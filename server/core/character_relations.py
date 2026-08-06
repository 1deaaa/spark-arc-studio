"""项目级人工角色关系存储。

人工关系与 GraphRAG 索引分开保存，重建知识图谱不会覆盖作者确认的关系。
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

from .character_store import read_character_records
from .json_state import load_json_file, save_json_file_atomic
from .utils import get_project_path


RELATIONS_FILENAME = "character_relations.json"


def _path(user_id: str, project_name: str) -> str:
    return os.path.join(get_project_path(user_id, project_name), RELATIONS_FILENAME)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    result: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source") or "").strip()
        target = str(item.get("target") or "").strip()
        relation = str(item.get("relation") or "").strip()
        if not source or not target or source == target or not relation:
            continue
        result.append({
            "id": str(item.get("id") or uuid.uuid4().hex),
            "source": source,
            "target": target,
            "relation": relation,
            "note": str(item.get("note") or "").strip(),
            "created_at": str(item.get("created_at") or _now()),
            "updated_at": str(item.get("updated_at") or item.get("created_at") or _now()),
        })
    return result


def read_character_relations(user_id: str, project_name: str) -> list[dict[str, Any]]:
    return _normalize(load_json_file(_path(user_id, project_name), list))


def _validate_character_pair(user_id: str, project_name: str, source: str, target: str) -> None:
    records = read_character_records(user_id, project_name)
    if source not in records or target not in records:
        raise ValueError("角色不存在")
    if source == target:
        raise ValueError("不能连接角色自身")
    if int(source) < 0 or int(target) < 0:
        raise ValueError("系统角色不能建立人工关系")


def create_character_relation(
    user_id: str,
    project_name: str,
    *,
    source: str,
    target: str,
    relation: str,
    note: str = "",
) -> dict[str, Any]:
    source, target, relation = str(source).strip(), str(target).strip(), str(relation).strip()
    if not relation:
        raise ValueError("关系名称不能为空")
    if len(relation) > 80:
        raise ValueError("关系名称不能超过 80 个字符")
    if len(str(note)) > 500:
        raise ValueError("关系备注不能超过 500 个字符")
    _validate_character_pair(user_id, project_name, source, target)
    relations = read_character_relations(user_id, project_name)
    pair = {source, target}
    if any(
        {item["source"], item["target"]} == pair
        and item["relation"].casefold() == relation.casefold()
        for item in relations
    ):
        raise ValueError("这两个角色之间已经存在同名人工关系")
    now = _now()
    item = {
        "id": uuid.uuid4().hex,
        "source": source,
        "target": target,
        "relation": relation,
        "note": str(note).strip(),
        "created_at": now,
        "updated_at": now,
    }
    save_json_file_atomic(_path(user_id, project_name), [*relations, item])
    return item


def update_character_relation(
    user_id: str,
    project_name: str,
    relation_id: str,
    *,
    source: str,
    target: str,
    relation: str,
    note: str = "",
) -> dict[str, Any]:
    source, target, relation = str(source).strip(), str(target).strip(), str(relation).strip()
    if not relation:
        raise ValueError("关系名称不能为空")
    if len(relation) > 80 or len(str(note)) > 500:
        raise ValueError("关系名称或备注过长")
    _validate_character_pair(user_id, project_name, source, target)
    relations = read_character_relations(user_id, project_name)
    for item in relations:
        if item["id"] != relation_id:
            continue
        pair = {source, target}
        if any(
            other["id"] != relation_id
            and {other["source"], other["target"]} == pair
            and other["relation"].casefold() == relation.casefold()
            for other in relations
        ):
            raise ValueError("这两个角色之间已经存在同名人工关系")
        item.update({"source": source, "target": target, "relation": relation, "note": str(note).strip(), "updated_at": _now()})
        save_json_file_atomic(_path(user_id, project_name), relations)
        return item
    raise KeyError("人工关系不存在")


def delete_character_relation(user_id: str, project_name: str, relation_id: str) -> bool:
    relations = read_character_relations(user_id, project_name)
    next_relations = [item for item in relations if item["id"] != relation_id]
    if len(next_relations) == len(relations):
        return False
    save_json_file_atomic(_path(user_id, project_name), next_relations)
    return True


def remove_character_relations(user_id: str, project_name: str, character_id: str) -> int:
    relations = read_character_relations(user_id, project_name)
    next_relations = [
        item for item in relations
        if item["source"] != str(character_id) and item["target"] != str(character_id)
    ]
    removed = len(relations) - len(next_relations)
    if removed:
        save_json_file_atomic(_path(user_id, project_name), next_relations)
    return removed
