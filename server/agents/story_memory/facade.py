from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Iterable
from datetime import datetime, timezone
from itertools import combinations
from typing import Any, Dict, List, Optional

from core.utils import get_project_path
from core.json_state import load_json_file, save_json_file_atomic, synchronized_json_state


STATE_DIR_NAME = ".story_memory"
STATE_FILENAME = "narrative_state.json"
MAX_RECENT_SCENES = 8
MAX_RECENT_EVIDENCE = 5
SCENE_TASK_PACK_RECENT_SCENES = 2
SCENE_TASK_PACK_MAX_CHARACTERS = 8


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_text(text: str) -> str:
    return hashlib.md5((text or "").encode("utf-8")).hexdigest()


def _compact_text(text: str, limit: int = 420) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(value) <= limit:
        return value
    head = value[: max(0, limit // 2)].rstrip()
    tail = value[-max(0, limit // 2) :].lstrip()
    return f"{head} …… {tail}"


def _plain_story_text(text: str) -> str:
    value = str(text or "")
    value = re.sub(r"<conception>[\s\S]*?</conception>", "", value)
    value = re.sub(r"^#\s+", "", value, flags=re.MULTILINE)
    value = re.sub(r"^@(?:intro|guide)\b", "", value, flags=re.MULTILINE)
    value = re.sub(r"\[[^\]]+\]", "", value)
    return value.strip()


def _safe_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_character_names(values: Any) -> list[str]:
    names: list[str] = []
    if values is None:
        return names
    if isinstance(values, (str, int, float)):
        values = [values]
    if not isinstance(values, Iterable):
        return names
    for item in values:
        if isinstance(item, dict):
            raw = item.get("name") or item.get("title") or item.get("character") or ""
        else:
            raw = str(item or "")
        name = raw.strip()
        if not name or name == "旁白":
            continue
        if name not in names:
            names.append(name)
    return names


def _scan_character_names(text: str, chr_map: Optional[dict]) -> list[str]:
    if not chr_map:
        return []
    haystack = str(text or "")
    matches: list[str] = []
    for raw_name in chr_map.values():
        name = str(raw_name or "").strip()
        if not name or name == "旁白":
            continue
        if name in haystack and name not in matches:
            matches.append(name)
    return matches


def _scan_character_ids_from_arc(text: str, chr_map: Optional[dict]) -> list[str]:
    """从 ARC 的 [说话人] 行识别登场角色名，跳过旁白和未知身份系统角色。"""
    matches: list[str] = []
    for raw_marker in re.findall(r"^\s*\[([^\]\r\n]+)\](?:\s|$)", str(text or ""), flags=re.MULTILINE):
        marker = str(raw_marker or "").strip()
        if not marker or marker in {"旁白", "?"}:
            continue
        name = marker
        if chr_map:
            try:
                cid = int(marker)
            except Exception:
                cid = None
            if cid is not None:
                if cid < 0:
                    continue
                name = str(chr_map.get(cid) or chr_map.get(str(cid)) or "").strip()
        if name and name not in {"旁白", "?"} and name not in matches:
            matches.append(name)
    return matches


def _merge_unique(base: list[str], extra: list[str], limit: int = 12) -> list[str]:
    merged = list(base)
    for item in extra:
        if item and item not in merged:
            merged.append(item)
        if len(merged) >= limit:
            break
    return merged


def _scene_id(
    *,
    chapter_index: Any = None,
    scene_index: Any = None,
    chapter_title: str = "",
    scene_title: str = "",
    source_path: str = "",
) -> str:
    ch = _safe_int(chapter_index)
    sc = _safe_int(scene_index)
    if ch is not None and sc is not None and ch >= 0 and sc >= 0:
        return f"ch{ch + 1:03d}-sc{sc + 1:03d}"
    seed = "|".join([str(chapter_title or ""), str(scene_title or ""), str(source_path or "")])
    digest = _hash_text(seed)[:10] if seed.strip("|") else "unknown"
    return f"scene-{digest}"


def _scene_position(item: Dict[str, Any]) -> Optional[tuple[int, int]]:
    """尽力恢复场景的逻辑位置，避免把未来场景注入较早场景。"""
    chapter_index = _safe_int(item.get("chapter_index"))
    scene_index = _safe_int(item.get("scene_index"))
    if chapter_index is not None and scene_index is not None:
        return chapter_index, scene_index

    source = str(item.get("source_path") or "")
    metadata_match = re.search(r"chap=(\d+)\.scene=(\d+)", source, flags=re.IGNORECASE)
    if metadata_match:
        return int(metadata_match.group(1)) - 1, int(metadata_match.group(2)) - 1

    title = str(item.get("scene_title") or "")
    title_match = re.search(r"(?<!\d)(\d+)\s*[-－—]\s*(\d+)(?!\d)", title)
    if title_match:
        return int(title_match.group(1)) - 1, int(title_match.group(2)) - 1
    return None


def _scene_sort_key(item: Dict[str, Any]) -> tuple[Any, ...]:
    position = _scene_position(item)
    if position is not None:
        return 0, position[0], position[1], str(item.get("scene_id") or "")
    return (
        1,
        str(item.get("updated_at") or ""),
        str(item.get("source_path") or ""),
        str(item.get("scene_id") or ""),
    )


def _relationship_key(a: str, b: str) -> str:
    left, right = sorted([a, b])
    return f"{left}|{right}"


def _text_terms(text: str) -> set[str]:
    value = re.sub(r"\s+", "", str(text or "").lower())
    if not value:
        return set()
    terms = {value[i : i + 2] for i in range(max(0, len(value) - 1))}
    terms.update({value[i : i + 3] for i in range(max(0, len(value) - 2))})
    return {term for term in terms if term.strip()}


class StoryMemoryFacade:
    """项目级叙事状态的轻量统一入口。

    第一阶段只写项目目录下的 JSON 文件，避免引入数据库迁移和前端形态变化。
    """

    def __init__(self, user_id: str, project_name: str):
        self.user_id = str(user_id)
        self.project_name = project_name

    @property
    def project_path(self) -> str:
        return get_project_path(self.user_id, self.project_name)

    @property
    def memory_dir(self) -> str:
        return os.path.join(self.project_path, STATE_DIR_NAME)

    @property
    def state_path(self) -> str:
        return os.path.join(self.memory_dir, STATE_FILENAME)

    def _default_state(self) -> Dict[str, Any]:
        now = _utc_now_iso()
        return {
            "version": "0.1",
            "project": self.project_name,
            "created_at": now,
            "updated_at": now,
            "scenes": [],
            "events": [],
            "fact_claims": [],
            "character_states": {},
            "relationships": {},
            "threads": [],
            "conflict_risks": [],
            "quality_memory": [],
        }

    def load_state(self) -> Dict[str, Any]:
        data = load_json_file(self.state_path, self._default_state) or {}

        state = self._default_state()
        state.update(data)
        state["scenes"] = state.get("scenes") if isinstance(state.get("scenes"), list) else []
        state["events"] = state.get("events") if isinstance(state.get("events"), list) else []
        state["fact_claims"] = state.get("fact_claims") if isinstance(state.get("fact_claims"), list) else []
        state["character_states"] = state.get("character_states") if isinstance(state.get("character_states"), dict) else {}
        state["relationships"] = state.get("relationships") if isinstance(state.get("relationships"), dict) else {}
        state["threads"] = state.get("threads") if isinstance(state.get("threads"), list) else []
        state["conflict_risks"] = state.get("conflict_risks") if isinstance(state.get("conflict_risks"), list) else []
        state["quality_memory"] = state.get("quality_memory") if isinstance(state.get("quality_memory"), list) else []
        return state

    def save_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        normalized = self._default_state()
        normalized.update(state or {})
        normalized["project"] = self.project_name
        normalized["updated_at"] = _utc_now_iso()
        save_json_file_atomic(self.state_path, normalized)
        return normalized

    def _prepare_scene_write(
        self,
        *,
        scene_text: str,
        chapter_index: Any = None,
        scene_index: Any = None,
        chapter_title: str = "",
        scene_title: str = "",
        scene_description: str = "",
        guidance: str = "",
        source_path: str = "",
        export_format: str = "arc",
        chr_map: Optional[dict] = None,
        scene_characters: Any = None,
    ) -> tuple[str, str, list[str], Dict[str, Any]]:
        """构造场景卡与抽取输入；此步骤不读写状态文件。"""
        plain_text = _plain_story_text(scene_text)
        scene_id = _scene_id(
            chapter_index=chapter_index,
            scene_index=scene_index,
            chapter_title=chapter_title,
            scene_title=scene_title,
            source_path=source_path,
        )
        explicit_characters = _normalize_character_names(scene_characters)
        scanned_characters = _merge_unique(
            _scan_character_ids_from_arc(scene_text, chr_map),
            _scan_character_names(
                "\n".join([plain_text, guidance, scene_description, scene_title]),
                chr_map,
            ),
        )
        characters = _merge_unique(explicit_characters, scanned_characters)
        source_hash = _hash_text(scene_text or "")
        scene_card = {
            "scene_id": scene_id,
            "chapter_index": _safe_int(chapter_index),
            "scene_index": _safe_int(scene_index),
            "chapter_title": str(chapter_title or "").strip(),
            "scene_title": str(scene_title or "").strip() or "未命名场景",
            "description": str(scene_description or "").strip(),
            "guidance": _compact_text(guidance, 360),
            "summary": _compact_text(plain_text or scene_description or guidance, 520),
            "characters": characters,
            "source_path": source_path.replace("\\", "/") if source_path else "",
            "source_hash": source_hash,
            "export_format": export_format or "arc",
            "updated_at": _utc_now_iso(),
        }
        return scene_id, source_hash, characters, scene_card

    def prepare_scene_enrichment(self, **payload: Any) -> Dict[str, Any]:
        """在状态锁外完成耗时的 LLM 抽取，提交阶段只做快速合并。"""
        clean_payload = dict(payload)
        clean_payload.pop("use_llm_extractor", None)
        clean_payload.pop("require_current_source_hash", None)
        clean_payload.pop("precomputed_delta", None)
        _scene_id_value, _source_hash, characters, scene_card = self._prepare_scene_write(**clean_payload)
        return self.extract_state_delta(
            scene_text=str(clean_payload.get("scene_text") or ""),
            scene_card=scene_card,
            characters=characters,
            chr_map=clean_payload.get("chr_map"),
            use_llm=True,
        )

    @synchronized_json_state
    def record_scene_write(
        self,
        *,
        scene_text: str,
        chapter_index: Any = None,
        scene_index: Any = None,
        chapter_title: str = "",
        scene_title: str = "",
        scene_description: str = "",
        guidance: str = "",
        source_path: str = "",
        export_format: str = "arc",
        chr_map: Optional[dict] = None,
        scene_characters: Any = None,
        use_llm_extractor: Optional[bool] = None,
        require_current_source_hash: bool = False,
        precomputed_delta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """在场景保存成功后固定尝试吸收一次轻量叙事状态。"""
        scene_id, source_hash, characters, scene_card = self._prepare_scene_write(
            scene_text=scene_text,
            chapter_index=chapter_index,
            scene_index=scene_index,
            chapter_title=chapter_title,
            scene_title=scene_title,
            scene_description=scene_description,
            guidance=guidance,
            source_path=source_path,
            export_format=export_format,
            chr_map=chr_map,
            scene_characters=scene_characters,
        )
        if require_current_source_hash:
            current = next(
                (
                    item
                    for item in self.load_state().get("scenes") or []
                    if item.get("scene_id") == scene_id
                ),
                None,
            )
            if current is not None and current.get("source_hash") != source_hash:
                return {
                    "scene": current,
                    "characters": current.get("characters") or [],
                    "thread": None,
                    "delta": {"source": "stale_enrichment_skipped"},
                }
        delta = precomputed_delta or self.extract_state_delta(
            scene_text=scene_text,
            scene_card=scene_card,
            characters=characters,
            chr_map=chr_map,
            use_llm=use_llm_extractor,
        )
        characters = _merge_unique(characters, self._characters_from_delta(delta), limit=16)
        if delta.get("summary"):
            scene_card["summary"] = _compact_text(str(delta.get("summary") or ""), 700)
        scene_card["characters"] = characters
        scene_card["events"] = delta.get("events") or []
        scene_card["state_delta_source"] = delta.get("source") or "heuristic"

        state = self.load_state()
        self._remove_scene_contributions(state, scene_id)
        scenes = [item for item in state["scenes"] if item.get("scene_id") != scene_id]
        scenes.append(scene_card)
        state["scenes"] = sorted(scenes, key=_scene_sort_key)

        evidence = {
            "scene_id": scene_id,
            "scene_title": scene_card["scene_title"],
            "source_path": scene_card["source_path"],
            "summary": scene_card["summary"],
        }
        for name in characters:
            card = dict(state["character_states"].get(name) or {})
            recent_scene_ids = [sid for sid in card.get("recent_scene_ids", []) if sid != scene_id]
            recent_scene_ids.append(scene_id)
            recent_evidence = [item for item in card.get("recent_evidence", []) if item.get("scene_id") != scene_id]
            recent_evidence.append(evidence)
            state["character_states"][name] = {
                "name": name,
                "last_seen_scene": scene_id,
                "last_seen_title": scene_card["scene_title"],
                "current_status": self._character_status_from_delta(name, delta),
                "recent_scene_ids": recent_scene_ids[-MAX_RECENT_SCENES:],
                "recent_evidence": recent_evidence[-MAX_RECENT_EVIDENCE:],
                "updated_at": scene_card["updated_at"],
            }

        for a, b in combinations(characters[:6], 2):
            key = _relationship_key(a, b)
            rel = dict(state["relationships"].get(key) or {})
            rel_evidence = [item for item in rel.get("recent_evidence", []) if item.get("scene_id") != scene_id]
            rel_evidence.append(evidence)
            extracted_rel = self._relationship_from_delta(a, b, delta)
            state["relationships"][key] = {
                "characters": sorted([a, b]),
                "relation_hint": extracted_rel.get("state")
                or rel.get("relation_hint")
                or "同场互动，具体关系待后续抽取确认",
                "why": extracted_rel.get("why") or rel.get("why") or "",
                "last_scene": scene_id,
                "co_presence_count": int(rel.get("co_presence_count") or 0) + 1,
                "recent_evidence": rel_evidence[-MAX_RECENT_EVIDENCE:],
                "updated_at": scene_card["updated_at"],
            }

        extracted_threads = self._threads_from_delta(delta, scene_card, characters)
        fallback_thread = self._extract_thread_candidate(scene_card, characters)
        state["threads"] = self._merge_threads(
            state.get("threads") or [],
            extracted_threads + ([fallback_thread] if fallback_thread else []),
            limit=80,
        )

        state["events"] = self._merge_by_id(
            state.get("events") or [],
            self._events_from_delta(delta, scene_card, characters),
            id_key="event_id",
            limit=400,
        )
        state["fact_claims"] = self._merge_by_id(
            state.get("fact_claims") or [],
            self._fact_claims_from_delta(delta, scene_card),
            id_key="claim_id",
            limit=400,
        )
        state["conflict_risks"] = self._merge_by_id(
            state.get("conflict_risks") or [],
            self._conflict_risks_from_delta(delta, scene_card),
            id_key="risk_id",
            limit=160,
        )

        self.save_state(state)
        return {
            "scene": scene_card,
            "characters": characters,
            "thread": extracted_threads[0] if extracted_threads else fallback_thread,
            "delta": delta,
        }

    def _remove_scene_contributions(self, state: Dict[str, Any], scene_id: str) -> None:
        """重新吸收同一场景前，移除旧版本留下的可替换状态。"""
        if not scene_id:
            return

        next_character_states: dict[str, Dict[str, Any]] = {}
        for name, card in (state.get("character_states") or {}).items():
            if not isinstance(card, dict):
                continue
            recent_scene_ids = [
                sid for sid in card.get("recent_scene_ids", [])
                if sid != scene_id
            ]
            recent_evidence = [
                item for item in card.get("recent_evidence", [])
                if isinstance(item, dict) and item.get("scene_id") != scene_id
            ]
            if not recent_scene_ids and not recent_evidence:
                continue
            updated = dict(card)
            updated["recent_scene_ids"] = recent_scene_ids[-MAX_RECENT_SCENES:]
            updated["recent_evidence"] = recent_evidence[-MAX_RECENT_EVIDENCE:]
            if updated.get("last_seen_scene") == scene_id:
                fallback = recent_evidence[-1] if recent_evidence else {}
                updated["last_seen_scene"] = fallback.get("scene_id") or (recent_scene_ids[-1] if recent_scene_ids else "")
                updated["last_seen_title"] = fallback.get("scene_title") or updated.get("last_seen_scene") or ""
                updated["current_status"] = "最近状态待后续吸收确认"
            next_character_states[str(name)] = updated
        state["character_states"] = next_character_states

        next_relationships: dict[str, Dict[str, Any]] = {}
        for key, rel in (state.get("relationships") or {}).items():
            if not isinstance(rel, dict):
                continue
            old_evidence = [
                item for item in rel.get("recent_evidence", [])
                if isinstance(item, dict)
            ]
            had_scene = any(item.get("scene_id") == scene_id for item in old_evidence)
            recent_evidence = [
                item for item in old_evidence
                if item.get("scene_id") != scene_id
            ]
            co_presence_count = max(0, int(rel.get("co_presence_count") or 0) - (1 if had_scene else 0))
            if co_presence_count <= 0 and not recent_evidence:
                continue
            updated = dict(rel)
            updated["co_presence_count"] = co_presence_count
            updated["recent_evidence"] = recent_evidence[-MAX_RECENT_EVIDENCE:]
            if updated.get("last_scene") == scene_id:
                fallback = recent_evidence[-1] if recent_evidence else {}
                updated["last_scene"] = fallback.get("scene_id") or ""
            next_relationships[str(key)] = updated
        state["relationships"] = next_relationships

        for key in ("events", "fact_claims", "conflict_risks"):
            state[key] = [
                item for item in state.get(key) or []
                if not isinstance(item, dict) or item.get("scene_id") != scene_id
            ]

        next_threads: list[Dict[str, Any]] = []
        for thread in state.get("threads") or []:
            if not isinstance(thread, dict):
                continue
            if thread.get("introduced_scene") == scene_id:
                continue
            history = [
                item for item in thread.get("history") or []
                if isinstance(item, dict) and item.get("scene_id") != scene_id
            ]
            updated = dict(thread)
            if history != (thread.get("history") or []):
                updated["history"] = history[-MAX_RECENT_EVIDENCE:]
                if updated.get("last_touched_scene") == scene_id:
                    fallback = history[-1] if history else {}
                    updated["last_touched_scene"] = fallback.get("scene_id") or updated.get("introduced_scene") or ""
                    updated["last_touched_title"] = fallback.get("scene_title") or updated.get("scene_title") or ""
            next_threads.append(updated)
        state["threads"] = next_threads

    def _extract_thread_candidate(self, scene_card: Dict[str, Any], characters: list[str]) -> Optional[Dict[str, Any]]:
        source = "\n".join([
            scene_card.get("description") or "",
            scene_card.get("guidance") or "",
        ])
        if not source:
            return None
        keywords = ["伏笔", "线索", "秘密", "承诺", "约定", "谜团", "真相", "回收", "埋下"]
        if not any(word in source for word in keywords):
            return None
        thread_id = f"thread-{_hash_text(scene_card.get('scene_id', '') + source)[:10]}"
        return {
            "thread_id": thread_id,
            "status": "open",
            "introduced_scene": scene_card.get("scene_id"),
            "scene_title": scene_card.get("scene_title"),
            "description": _compact_text(source, 360),
            "related_characters": characters,
            "updated_at": scene_card.get("updated_at"),
        }

    def extract_state_delta(
        self,
        *,
        scene_text: str,
        scene_card: Dict[str, Any],
        characters: list[str],
        chr_map: Optional[dict] = None,
        use_llm: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """从保存后的场景正文抽取结构化叙事状态增量。"""
        fallback = self._heuristic_state_delta(scene_text, scene_card, characters)
        enabled = self._llm_extractor_enabled(use_llm)
        if not enabled:
            return fallback
        try:
            extracted = self._extract_state_delta_with_llm(
                scene_text=scene_text,
                scene_card=scene_card,
                characters=characters,
                chr_map=chr_map,
            )
            return self._normalize_state_delta(extracted, fallback)
        except Exception as e:
            print(f"[StoryMemory] LLM 状态抽取失败，已使用确定性回退：{e}")
            return fallback

    def _llm_extractor_enabled(self, requested: Optional[bool]) -> bool:
        if requested is not None:
            return bool(requested)
        flag = str(os.getenv("SPARKARC_STORY_MEMORY_LLM", "1")).strip().lower()
        return flag not in {"0", "false", "off", "no"}

    def _heuristic_state_delta(
        self,
        scene_text: str,
        scene_card: Dict[str, Any],
        characters: list[str],
    ) -> Dict[str, Any]:
        summary = scene_card.get("summary") or _compact_text(_plain_story_text(scene_text), 520)
        return {
            "source": "heuristic",
            "summary": summary,
            "events": [
                {
                    "event_id": f"event-{scene_card.get('scene_id')}",
                    "summary": summary,
                    "participants": characters,
                    "evidence": summary,
                }
            ] if summary else [],
            "character_updates": [
                {
                    "character": name,
                    "status": "本场出场，具体状态待后续抽取确认",
                    "goal": "",
                    "emotion": "",
                    "knowledge": "",
                    "evidence": summary,
                }
                for name in characters
            ],
            "relationship_changes": [],
            "foreshadows": [],
            "fact_claims": [],
            "conflict_risks": [],
        }

    def _extract_state_delta_with_llm(
        self,
        *,
        scene_text: str,
        scene_card: Dict[str, Any],
        characters: list[str],
        chr_map: Optional[dict] = None,
    ) -> Dict[str, Any]:
        from langchain_core.messages import HumanMessage, SystemMessage
        from llm.agen_matchbox import matchbox
        from agents.language_policy import prepend_prompt_language_policy

        usage_key = (os.getenv("SPARKARC_STORY_MEMORY_USAGE_KEY", "fast") or "fast").strip().lower()
        timeout = float(os.getenv("SPARKARC_STORY_MEMORY_TIMEOUT", "90"))
        llm = matchbox().get_user_llm(
            self.user_id,
            usage_key=usage_key,
            agent_name="agent_story_memory",
            timeout=timeout,
        )
        known_characters = "、".join(characters) or "（未识别）"
        chr_reference = ""
        if chr_map:
            names = [
                str(name)
                for name in chr_map.values()
                if str(name or "").strip() and str(name or "").strip() != "旁白"
            ]
            chr_reference = "、".join(names[:80])

        system_prompt = prepend_prompt_language_policy(
            "你是长篇小说项目的叙事状态抽取器。任务标签:[TASK:STORY_MEMORY_EXTRACT]。"
            "你只从用户提供的场景正文和场景目标中抽取事实，不补设定、不脑补隐含情节、不提供创作建议。"
            "输出必须是严格 JSON 对象，不要 Markdown，不要解释。"
        )
        user_prompt = f"""
请从以下已保存场景中抽取结构化叙事状态增量。

【场景元数据】
- scene_id: {scene_card.get("scene_id")}
- 章节: {scene_card.get("chapter_title") or "（未提供）"}
- 场景: {scene_card.get("scene_title") or "（未提供）"}
- 场景描述: {scene_card.get("description") or "（未提供）"}
- 写作指导: {scene_card.get("guidance") or "（未提供）"}
- 已识别登场角色: {known_characters}
- 项目角色表: {chr_reference or "（未提供）"}

【场景正文】
{_compact_text(scene_text, int(os.getenv("SPARKARC_STORY_MEMORY_MAX_CHARS", "12000")))}

【输出 JSON schema】
{{
  "summary": "用 1-3 句话概括本场真正发生的剧情事实",
  "events": [
    {{"summary": "事件", "participants": ["角色名"], "evidence": "原文证据短句"}}
  ],
  "character_updates": [
    {{"character": "角色名", "status": "本场结束时状态", "goal": "当前目标", "emotion": "情绪", "knowledge": "本场后知道/不知道的关键信息", "evidence": "证据短句"}}
  ],
  "relationship_changes": [
    {{"characters": ["角色A", "角色B"], "state": "本场结束时关系状态", "why": "原因", "evidence": "证据短句"}}
  ],
  "foreshadows": [
    {{"description": "正文中明确出现的开放线索、秘密、承诺或已回收线索", "status": "open|advanced|resolved", "related_characters": ["角色名"], "evidence": "证据短句"}}
  ],
  "fact_claims": [
    {{"claim": "正文已经确立、后续应核对保持的事实", "entities": ["实体名"], "evidence": "证据短句"}}
  ],
  "conflict_risks": [
    {{"risk": "仅当正文或场景目标中明确出现自相矛盾、需人工核对的信息时填写", "severity": "low|medium|high", "evidence": "证据短句"}}
  ]
}}

要求：
- 数组最多各 8 条。
- 没有就给空数组。
- 角色名尽量使用项目角色表中的名称。
- evidence 必须来自场景正文或场景指导。
- 不要推测作者意图，不要设计伏笔，不要给后续写作方案。
"""
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])
        content = getattr(response, "content", "")
        if not isinstance(content, str):
            content = str(content)
        return self._safe_json_object(content)

    def _safe_json_object(self, text: str) -> Dict[str, Any]:
        raw = str(text or "").strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        try:
            payload = json.loads(raw)
            return payload if isinstance(payload, dict) else {}
        except Exception:
            pass
        match = re.search(r"\{[\s\S]*\}", raw)
        if match:
            payload = json.loads(match.group(0))
            return payload if isinstance(payload, dict) else {}
        return {}

    def _normalize_state_delta(self, raw: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(raw, dict):
            return fallback

        def _list(key: str) -> list:
            value = raw.get(key)
            if not isinstance(value, list):
                return []
            return [item for item in value if isinstance(item, dict)][:8]

        summary = str(raw.get("summary") or fallback.get("summary") or "").strip()
        normalized = {
            "source": "llm",
            "summary": summary,
            "events": _list("events") or fallback.get("events", []),
            "character_updates": _list("character_updates") or fallback.get("character_updates", []),
            "relationship_changes": _list("relationship_changes"),
            "foreshadows": _list("foreshadows"),
            "fact_claims": _list("fact_claims"),
            "conflict_risks": _list("conflict_risks"),
        }
        return normalized

    def _character_status_from_delta(self, name: str, delta: Dict[str, Any]) -> Dict[str, str]:
        for item in delta.get("character_updates") or []:
            if str(item.get("character") or "").strip() == name:
                return {
                    "status": str(item.get("status") or "").strip(),
                    "goal": str(item.get("goal") or "").strip(),
                    "emotion": str(item.get("emotion") or "").strip(),
                    "knowledge": str(item.get("knowledge") or "").strip(),
                    "evidence": _compact_text(str(item.get("evidence") or ""), 260),
                }
        return {
            "status": "本场出场，具体状态待后续抽取确认",
            "goal": "",
            "emotion": "",
            "knowledge": "",
            "evidence": "",
        }

    def _characters_from_delta(self, delta: Dict[str, Any]) -> list[str]:
        names: list[str] = []
        for item in delta.get("character_updates") or []:
            name = str(item.get("character") or "").strip()
            if name and name != "旁白" and name not in names:
                names.append(name)
        for item in delta.get("relationship_changes") or []:
            names = _merge_unique(names, _normalize_character_names(item.get("characters")), limit=24)
        for item in delta.get("foreshadows") or []:
            names = _merge_unique(names, _normalize_character_names(item.get("related_characters")), limit=24)
        return names

    def _relationship_from_delta(self, a: str, b: str, delta: Dict[str, Any]) -> Dict[str, str]:
        pair = {a, b}
        for item in delta.get("relationship_changes") or []:
            chars = {str(name).strip() for name in item.get("characters") or [] if str(name).strip()}
            if pair.issubset(chars):
                return {
                    "state": str(item.get("state") or "").strip(),
                    "why": str(item.get("why") or "").strip(),
                    "evidence": str(item.get("evidence") or "").strip(),
                }
        return {}

    def _threads_from_delta(
        self,
        delta: Dict[str, Any],
        scene_card: Dict[str, Any],
        fallback_characters: list[str],
    ) -> list[Dict[str, Any]]:
        threads: list[Dict[str, Any]] = []
        for item in delta.get("foreshadows") or []:
            desc = str(item.get("description") or "").strip()
            if not desc:
                continue
            status = str(item.get("status") or "open").strip().lower()
            related = _normalize_character_names(item.get("related_characters")) or fallback_characters
            thread_id = f"thread-{_hash_text(scene_card.get('scene_id', '') + desc)[:10]}"
            threads.append({
                "thread_id": thread_id,
                "status": status if status in {"open", "advanced", "resolved"} else "open",
                "introduced_scene": scene_card.get("scene_id"),
                "scene_title": scene_card.get("scene_title"),
                "description": _compact_text(desc, 360),
                "related_characters": related,
                "evidence": _compact_text(str(item.get("evidence") or ""), 260),
                "updated_at": scene_card.get("updated_at"),
            })
        return threads

    def _merge_threads(
        self,
        existing: list[Dict[str, Any]],
        incoming: list[Dict[str, Any]],
        *,
        limit: int,
    ) -> list[Dict[str, Any]]:
        """合并伏笔/线索，允许后续场景推进或关闭旧线索。"""
        merged = [
            dict(item)
            for item in existing
            if isinstance(item, dict) and item.get("thread_id")
        ]
        for thread in incoming:
            if not isinstance(thread, dict) or not thread.get("thread_id"):
                continue
            matched_index = self._find_matching_thread_index(merged, thread)
            if matched_index is None:
                merged.append(thread)
                continue

            previous = dict(merged[matched_index])
            status = str(thread.get("status") or previous.get("status") or "open").strip().lower()
            if status not in {"open", "advanced", "resolved"}:
                status = str(previous.get("status") or "open").strip().lower()
            history = [
                item for item in previous.get("history") or []
                if isinstance(item, dict)
            ]
            history.append({
                "scene_id": thread.get("introduced_scene"),
                "scene_title": thread.get("scene_title"),
                "status": status,
                "description": thread.get("description") or "",
                "evidence": thread.get("evidence") or "",
                "updated_at": thread.get("updated_at") or _utc_now_iso(),
            })
            related = _merge_unique(
                _normalize_character_names(previous.get("related_characters")),
                _normalize_character_names(thread.get("related_characters")),
                limit=16,
            )
            updated = {
                **previous,
                "status": status,
                "description": thread.get("description") or previous.get("description") or "",
                "related_characters": related,
                "evidence": thread.get("evidence") or previous.get("evidence") or "",
                "last_touched_scene": thread.get("introduced_scene") or previous.get("last_touched_scene") or previous.get("introduced_scene"),
                "last_touched_title": thread.get("scene_title") or previous.get("last_touched_title") or previous.get("scene_title"),
                "updated_at": thread.get("updated_at") or _utc_now_iso(),
                "history": history[-MAX_RECENT_EVIDENCE:],
            }
            if status == "resolved" and not updated.get("resolved_scene"):
                updated["resolved_scene"] = thread.get("introduced_scene")
                updated["resolved_title"] = thread.get("scene_title")
                updated["resolved_at"] = thread.get("updated_at") or _utc_now_iso()
            merged[matched_index] = updated

        return merged[-limit:]

    def _find_matching_thread_index(
        self,
        existing: list[Dict[str, Any]],
        incoming: Dict[str, Any],
    ) -> Optional[int]:
        incoming_id = incoming.get("thread_id")
        for index, item in enumerate(existing):
            if item.get("thread_id") == incoming_id:
                return index

        incoming_status = str(incoming.get("status") or "open").strip().lower()
        if incoming_status == "open":
            return None

        incoming_desc = str(incoming.get("description") or "")
        incoming_terms = _text_terms(incoming_desc)
        incoming_related = set(_normalize_character_names(incoming.get("related_characters")))
        best: tuple[float, int] | None = None
        for index, item in enumerate(existing):
            status = str(item.get("status") or "open").strip().lower()
            if status == "resolved":
                continue
            item_desc = str(item.get("description") or "")
            if not item_desc:
                continue
            item_terms = _text_terms(item_desc)
            if not incoming_terms or not item_terms:
                continue
            overlap = len(incoming_terms.intersection(item_terms))
            score = overlap / max(1, min(len(incoming_terms), len(item_terms)))
            item_related = set(_normalize_character_names(item.get("related_characters")))
            if incoming_related and item_related and incoming_related.intersection(item_related):
                score += 0.25
            if incoming_desc and (incoming_desc in item_desc or item_desc in incoming_desc):
                score += 0.5
            if score >= 0.42 and (best is None or score > best[0]):
                best = (score, index)
        return best[1] if best is not None else None

    def _events_from_delta(
        self,
        delta: Dict[str, Any],
        scene_card: Dict[str, Any],
        fallback_characters: list[str],
    ) -> list[Dict[str, Any]]:
        events: list[Dict[str, Any]] = []
        for index, item in enumerate(delta.get("events") or []):
            summary = str(item.get("summary") or "").strip()
            if not summary:
                continue
            event_id = f"event-{_hash_text(scene_card.get('scene_id', '') + summary)[:12]}"
            events.append({
                "event_id": event_id,
                "scene_id": scene_card.get("scene_id"),
                "scene_title": scene_card.get("scene_title"),
                "summary": _compact_text(summary, 420),
                "participants": _normalize_character_names(item.get("participants")) or fallback_characters,
                "evidence": _compact_text(str(item.get("evidence") or ""), 260),
                "order": index,
                "updated_at": scene_card.get("updated_at"),
            })
        return events

    def _fact_claims_from_delta(
        self,
        delta: Dict[str, Any],
        scene_card: Dict[str, Any],
    ) -> list[Dict[str, Any]]:
        claims: list[Dict[str, Any]] = []
        for item in delta.get("fact_claims") or []:
            claim = str(item.get("claim") or "").strip()
            if not claim:
                continue
            claim_id = f"claim-{_hash_text(scene_card.get('scene_id', '') + claim)[:12]}"
            claims.append({
                "claim_id": claim_id,
                "scene_id": scene_card.get("scene_id"),
                "scene_title": scene_card.get("scene_title"),
                "claim": _compact_text(claim, 360),
                "entities": _normalize_character_names(item.get("entities")),
                "evidence": _compact_text(str(item.get("evidence") or ""), 260),
                "updated_at": scene_card.get("updated_at"),
            })
        return claims

    def _conflict_risks_from_delta(
        self,
        delta: Dict[str, Any],
        scene_card: Dict[str, Any],
    ) -> list[Dict[str, Any]]:
        risks: list[Dict[str, Any]] = []
        for item in delta.get("conflict_risks") or []:
            risk = str(item.get("risk") or "").strip()
            if not risk:
                continue
            risk_id = f"risk-{_hash_text(scene_card.get('scene_id', '') + risk)[:12]}"
            severity = str(item.get("severity") or "medium").strip().lower()
            risks.append({
                "risk_id": risk_id,
                "scene_id": scene_card.get("scene_id"),
                "scene_title": scene_card.get("scene_title"),
                "risk": _compact_text(risk, 360),
                "severity": severity if severity in {"low", "medium", "high"} else "medium",
                "evidence": _compact_text(str(item.get("evidence") or ""), 260),
                "updated_at": scene_card.get("updated_at"),
            })
        return risks

    def _merge_by_id(
        self,
        existing: list[Dict[str, Any]],
        incoming: list[Dict[str, Any]],
        *,
        id_key: str,
        limit: int,
    ) -> list[Dict[str, Any]]:
        merged = {
            str(item.get(id_key)): item
            for item in existing
            if isinstance(item, dict) and item.get(id_key)
        }
        for item in incoming:
            if isinstance(item, dict) and item.get(id_key):
                merged[str(item.get(id_key))] = item
        return list(merged.values())[-limit:]

    @synchronized_json_state
    def record_quality_review(
        self,
        *,
        review: Dict[str, Any],
        review_target: str = "",
        scene_name: str = "",
        source_path: str = "",
    ) -> list[Dict[str, Any]]:
        """把 Critic 的结构化修订建议写入长期质量记忆。"""
        if not isinstance(review, dict):
            return []
        raw_tickets = review.get("fix_tickets") or []
        if not isinstance(raw_tickets, list):
            raw_tickets = []

        if self._quality_review_passed_without_new_tickets(review, raw_tickets):
            self._close_quality_tickets_for_review(
                review_target=review_target,
                scene_name=scene_name,
                source_path=source_path,
            )
            return []

        tickets: list[Dict[str, Any]] = []
        for index, item in enumerate(raw_tickets):
            if not isinstance(item, dict):
                continue
            target = str(item.get("target") or review_target or scene_name or "未指定片段").strip()
            edit_goal = str(item.get("edit_goal") or item.get("goal") or review.get("rewrite_brief") or "").strip()
            if not target and not edit_goal:
                continue
            must_keep = item.get("must_keep") if isinstance(item.get("must_keep"), list) else []
            operations = item.get("operations") if isinstance(item.get("operations"), list) else []
            evidence = item.get("evidence") if isinstance(item.get("evidence"), list) else []
            ticket_id = f"quality-{_hash_text('|'.join([review_target, scene_name, target, edit_goal, str(index)]))[:12]}"
            tickets.append({
                "ticket_id": ticket_id,
                "status": "open",
                "review_target": review_target,
                "scene_name": scene_name,
                "source_path": source_path.replace("\\", "/") if source_path else "",
                "target": _compact_text(target, 240),
                "edit_goal": _compact_text(edit_goal, 360),
                "must_keep": [str(value) for value in must_keep if str(value).strip()][:8],
                "operations": [str(value) for value in operations if str(value).strip()][:8],
                "evidence": evidence[:6],
                "overall_grade": review.get("overall_grade") or "",
                "decision": review.get("decision") or "",
                "rewrite_brief": _compact_text(str(review.get("rewrite_brief") or ""), 420),
                "created_at": _utc_now_iso(),
                "updated_at": _utc_now_iso(),
            })

        if not tickets and review.get("rewrite_required"):
            brief = str(review.get("rewrite_brief") or review.get("overall_summary") or "").strip()
            if brief:
                ticket_id = f"quality-{_hash_text('|'.join([review_target, scene_name, brief]))[:12]}"
                tickets.append({
                    "ticket_id": ticket_id,
                    "status": "open",
                    "review_target": review_target,
                    "scene_name": scene_name,
                    "source_path": source_path.replace("\\", "/") if source_path else "",
                    "target": review_target or scene_name or "当前文本",
                    "edit_goal": _compact_text(brief, 360),
                    "must_keep": [],
                    "operations": [],
                    "evidence": [],
                    "overall_grade": review.get("overall_grade") or "",
                    "decision": review.get("decision") or "",
                    "rewrite_brief": _compact_text(brief, 420),
                    "created_at": _utc_now_iso(),
                    "updated_at": _utc_now_iso(),
                })

        if not tickets:
            return []

        state = self.load_state()
        state["quality_memory"] = self._merge_by_id(
            state.get("quality_memory") or [],
            tickets,
            id_key="ticket_id",
            limit=240,
        )
        self.save_state(state)
        return tickets

    def _quality_review_passed_without_new_tickets(self, review: Dict[str, Any], raw_tickets: list[Any]) -> bool:
        decision = str(review.get("decision") or "").strip().upper()
        rewrite_required = bool(review.get("rewrite_required", decision != "PASS"))
        return decision == "PASS" and not rewrite_required and not raw_tickets

    @synchronized_json_state
    def _close_quality_tickets_for_review(
        self,
        *,
        review_target: str = "",
        scene_name: str = "",
        source_path: str = "",
    ) -> list[Dict[str, Any]]:
        """当 Critic 复审通过时关闭同一目标的开放修订工单。"""
        normalized_source = source_path.replace("\\", "/") if source_path else ""
        targets = {
            str(value or "").strip()
            for value in (review_target, scene_name, normalized_source)
            if str(value or "").strip()
        }
        if not targets:
            return []

        state = self.load_state()
        closed: list[Dict[str, Any]] = []
        next_memory: list[Dict[str, Any]] = []
        for item in state.get("quality_memory") or []:
            if not isinstance(item, dict):
                continue
            if item.get("status") != "open" or not self._quality_ticket_matches_review_target(item, targets):
                next_memory.append(item)
                continue
            updated = dict(item)
            updated["status"] = "resolved"
            updated["resolution"] = "critic_pass"
            updated["resolved_at"] = _utc_now_iso()
            updated["updated_at"] = updated["resolved_at"]
            closed.append(updated)
            next_memory.append(updated)

        if closed:
            state["quality_memory"] = next_memory
            self.save_state(state)
        return closed

    @staticmethod
    def _quality_ticket_matches_review_target(ticket: Dict[str, Any], targets: set[str]) -> bool:
        values = [
            ticket.get("review_target"),
            ticket.get("scene_name"),
            ticket.get("source_path"),
            ticket.get("target"),
        ]
        haystack = "\n".join(str(value or "").strip() for value in values if str(value or "").strip())
        if not haystack:
            return False
        return any(target == haystack or target in haystack or haystack in target for target in targets)

    def compose_scene_task_pack(
        self,
        *,
        chapter_index: Any = None,
        scene_index: Any = None,
        chapter_title: str = "",
        chapter_description: str = "",
        scene_title: str = "",
        scene_description: str = "",
        scene_characters: Any = None,
        guidance: str = "",
        chr_map: Optional[dict] = None,
        max_recent_scenes: int = 4,
    ) -> Dict[str, Any]:
        """为 Scriptwriter 生成写前事实核对包。"""
        active_characters = _merge_unique(
            _normalize_character_names(scene_characters),
            _scan_character_names(
                "\n".join([chapter_title, chapter_description, scene_title, scene_description, guidance]),
                chr_map,
            ),
            limit=SCENE_TASK_PACK_MAX_CHARACTERS,
        )
        state = self.load_state()
        scene_id = _scene_id(
            chapter_index=chapter_index,
            scene_index=scene_index,
            chapter_title=chapter_title,
            scene_title=scene_title,
        )

        target_position = _scene_position({
            "chapter_index": chapter_index,
            "scene_index": scene_index,
            "scene_title": scene_title,
        })
        ordered_scenes = sorted(
            [item for item in state["scenes"] if isinstance(item, dict)],
            key=_scene_sort_key,
        )
        historical_scenes = []
        for item in ordered_scenes:
            if item.get("scene_id") == scene_id:
                continue
            position = _scene_position(item)
            if target_position is not None:
                if position is None or position >= target_position:
                    continue
            historical_scenes.append(item)
        eligible_scene_ids = {
            str(item.get("scene_id"))
            for item in historical_scenes
            if item.get("scene_id")
        }
        scene_rank_by_id = {
            str(item.get("scene_id")): index
            for index, item in enumerate(historical_scenes)
            if item.get("scene_id")
        }

        character_cards = []
        for name in active_characters:
            raw_card = state["character_states"].get(name)
            if not isinstance(raw_card, dict):
                continue
            evidence = [
                item for item in raw_card.get("recent_evidence") or []
                if isinstance(item, dict) and item.get("scene_id") in eligible_scene_ids
            ]
            if target_position is not None and not evidence:
                continue
            card = dict(raw_card)
            if evidence:
                latest = max(
                    evidence,
                    key=lambda item: scene_rank_by_id.get(str(item.get("scene_id") or ""), -1),
                )
                card["last_seen_scene"] = latest.get("scene_id") or ""
                card["last_seen_title"] = latest.get("scene_title") or ""
                card["recent_evidence"] = evidence
                if raw_card.get("last_seen_scene") not in eligible_scene_ids:
                    card["current_status"] = "以最近可用场景证据为准"
            character_cards.append(card)

        relationship_cards = []
        for a, b in combinations(active_characters[:6], 2):
            rel = state["relationships"].get(_relationship_key(a, b))
            if not isinstance(rel, dict):
                continue
            evidence = [
                item for item in rel.get("recent_evidence") or []
                if isinstance(item, dict) and item.get("scene_id") in eligible_scene_ids
            ]
            if target_position is not None and not evidence:
                continue
            card = dict(rel)
            if evidence:
                latest = max(
                    evidence,
                    key=lambda item: scene_rank_by_id.get(str(item.get("scene_id") or ""), -1),
                )
                card["last_scene"] = latest.get("scene_id") or ""
                card["recent_evidence"] = evidence
                if rel.get("last_scene") not in eligible_scene_ids:
                    card["relation_hint"] = "截至该场已有互动，具体关系以最近证据为准"
            relationship_cards.append(card)

        open_threads = []
        for thread in state["threads"]:
            if not isinstance(thread, dict) or thread.get("status") not in {"open", "advanced"}:
                continue
            reference_scene = thread.get("last_touched_scene") or thread.get("introduced_scene")
            if target_position is not None and reference_scene not in eligible_scene_ids:
                continue
            open_threads.append(thread)
        relevant_threads = self._select_relevant_records(
            open_threads,
            active_characters=active_characters,
            scene_text="\n".join([scene_title, scene_description, guidance]),
            entity_keys=("related_characters",),
            text_keys=("description", "evidence", "scene_title", "last_touched_title"),
            limit=4,
            scene_rank_by_id=scene_rank_by_id,
            scene_id_keys=("last_touched_scene", "introduced_scene"),
        )

        recent_limit = min(
            SCENE_TASK_PACK_RECENT_SCENES,
            max(0, int(max_recent_scenes or 0)),
        )
        recent_scenes = historical_scenes[-recent_limit:] if recent_limit else []
        def eligible_records(records: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
            return [
                item for item in records
                if isinstance(item, dict)
                and (
                    target_position is None
                    or not item.get("scene_id")
                    or item.get("scene_id") in eligible_scene_ids
                )
            ]
        relevant_events = self._select_relevant_records(
            eligible_records(state.get("events") or []),
            active_characters=active_characters,
            scene_text="\n".join([scene_title, scene_description, guidance]),
            entity_keys=("participants",),
            text_keys=("summary", "evidence", "scene_title"),
            limit=4,
            scene_rank_by_id=scene_rank_by_id,
        )
        relevant_facts = self._select_relevant_records(
            eligible_records(state.get("fact_claims") or []),
            active_characters=active_characters,
            scene_text="\n".join([scene_title, scene_description, guidance]),
            entity_keys=("entities",),
            text_keys=("claim", "evidence", "scene_title"),
            limit=5,
            scene_rank_by_id=scene_rank_by_id,
        )
        relevant_risks = self._select_relevant_records(
            eligible_records(state.get("conflict_risks") or []),
            active_characters=active_characters,
            scene_text="\n".join([scene_title, scene_description, guidance]),
            entity_keys=(),
            text_keys=("risk", "evidence", "scene_title"),
            limit=3,
            scene_rank_by_id=scene_rank_by_id,
        )
        relevant_quality_tickets = self._select_relevant_records(
            [
                item for item in state.get("quality_memory") or []
                if isinstance(item, dict) and item.get("status") == "open"
            ],
            active_characters=active_characters,
            scene_text="\n".join([scene_title, scene_description, guidance]),
            entity_keys=(),
            text_keys=("target", "edit_goal", "rewrite_brief", "scene_name", "review_target", "source_path"),
            limit=3,
            scene_rank_by_id=scene_rank_by_id,
        )

        lines: list[str] = []
        lines.append("=== 当前场景事实包（StoryMemory 自动整理，仅供核对）===")
        lines.append("【场景契约】")
        if chapter_title:
            lines.append(f"- 当前章节：{chapter_title}")
        if chapter_description:
            lines.append(f"- 章节目标：{_compact_text(chapter_description, 240)}")
        lines.append(f"- 当前场景：{scene_title or '未命名场景'}")
        if scene_description:
            lines.append(f"- 场景描述：{_compact_text(scene_description, 260)}")
        if active_characters:
            lines.append(f"- 登场角色：{'、'.join(active_characters)}")

        lines.append("\n【登场角色动态状态】")
        if character_cards:
            for card in character_cards:
                lines.append(
                    f"- {card.get('name')}：上次出场 {card.get('last_seen_title') or card.get('last_seen_scene') or '未知'}；"
                    f"最近证据：{_compact_text((card.get('recent_evidence') or [{}])[-1].get('summary', ''), 220)}"
                )
        elif active_characters:
            lines.append("- 暂无这些角色的已写正文状态，请严格依据角色档案与当前场景目标处理。")
        else:
            lines.append("- 当前大纲未标注登场角色；写作前需要主动核对角色与叙事视角。")

        lines.append("\n【人物关系/同场互动记录】")
        if relationship_cards:
            for rel in relationship_cards[:6]:
                chars = " ↔ ".join(rel.get("characters") or [])
                evidence = (rel.get("recent_evidence") or [{}])[-1].get("summary", "")
                lines.append(f"- {chars}：{rel.get('relation_hint')}；最近证据：{_compact_text(evidence, 180)}")
        else:
            lines.append("- 暂无可靠的同场互动记录；不要凭空升级关系。")

        lines.append("\n【开放线索/待核对项】")
        if relevant_threads:
            for thread in relevant_threads:
                lines.append(
                    f"- {thread.get('description')}（来源：{thread.get('scene_title') or thread.get('introduced_scene')}）"
                )
        else:
            lines.append("- 暂无命中的开放线索。")

        lines.append("\n【相关历史事件】")
        if relevant_events:
            for item in relevant_events:
                lines.append(f"- {item.get('summary')}（来源：{item.get('scene_title') or item.get('scene_id')}；证据：{_compact_text(item.get('evidence', ''), 160)}）")
        else:
            lines.append("- 暂无命中的结构化历史事件。")

        lines.append("\n【已确立事实】")
        if relevant_facts:
            for item in relevant_facts:
                lines.append(f"- {item.get('claim')}（证据：{_compact_text(item.get('evidence', ''), 160)}）")
        else:
            lines.append("- 暂无命中的结构化事实记录。")

        lines.append("\n【待人工核对的矛盾风险】")
        if relevant_risks:
            for item in relevant_risks:
                lines.append(f"- [{item.get('severity', 'medium')}] {item.get('risk')}（证据：{_compact_text(item.get('evidence', ''), 160)}）")
        else:
            lines.append("- 暂无明确矛盾风险记录。")

        lines.append("\n【未关闭修订工单 / 质量记忆】")
        if relevant_quality_tickets:
            for item in relevant_quality_tickets:
                lines.append(
                    f"- 目标：{item.get('target') or item.get('review_target') or '当前文本'}；"
                    f"修改目标：{_compact_text(item.get('edit_goal') or item.get('rewrite_brief') or '', 220)}"
                )
                operations = item.get("operations") or []
                if operations:
                    lines.append(f"  建议操作：{'；'.join(str(value) for value in operations[:4])}")
                must_keep = item.get("must_keep") or []
                if must_keep:
                    lines.append(f"  必须保留：{'；'.join(str(value) for value in must_keep[:4])}")
        else:
            lines.append("- 暂无命中的开放修订工单。")

        lines.append("\n【最近已写场景摘要】")
        if recent_scenes:
            for item in recent_scenes:
                lines.append(f"- {item.get('scene_title')}：{_compact_text(item.get('summary', ''), 220)}")
        else:
            lines.append("- 尚无已吸收的场景状态。")

        lines.append("\n【使用边界】")
        lines.append("- 以上内容是已保存正文整理出的事实和证据，不是剧情方案。")
        lines.append("- 写作时核对角色状态、关系状态、开放线索和最近场景事实；具体表达和回收方式由执笔编剧根据大纲与用户意图决定。")
        lines.append("- 若当前任务涉及旧线索、秘密、人物关系或世界规则，写作前优先调用只读工具补查，不要凭空补设定。")
        lines.append("- 写完后系统会在后台吸收本场状态；正文内不要输出状态解释、工具说明或元话语。")

        pack = {
            "scene_id": scene_id,
            "active_characters": active_characters,
            "character_cards": character_cards,
            "relationship_cards": relationship_cards,
            "threads": relevant_threads,
            "events": relevant_events,
            "fact_claims": relevant_facts,
            "conflict_risks": relevant_risks,
            "quality_tickets": relevant_quality_tickets,
            "recent_scenes": recent_scenes,
        }
        return {
            "pack": pack,
            "text": "\n".join(lines).strip(),
        }

    def _select_relevant_records(
        self,
        records: list[Dict[str, Any]],
        *,
        active_characters: list[str],
        scene_text: str,
        entity_keys: tuple[str, ...],
        text_keys: tuple[str, ...],
        limit: int,
        scene_rank_by_id: Optional[Dict[str, int]] = None,
        scene_id_keys: tuple[str, ...] = ("scene_id",),
    ) -> list[Dict[str, Any]]:
        query_terms = _text_terms(scene_text)
        normalized_characters = {
            str(item).strip()
            for item in active_characters
            if str(item).strip()
        }
        ranks = scene_rank_by_id or {}
        scored: list[tuple[float, int, str, int, Dict[str, Any]]] = []
        for record_index, record in enumerate(records):
            if not isinstance(record, dict):
                continue
            score = 0.0
            for key in entity_keys:
                entities = record.get(key) or []
                if isinstance(entities, str):
                    entities = [entities]
                score += len({str(item).strip() for item in entities if str(item).strip()}.intersection(normalized_characters)) * 4
            haystack = "\n".join(str(record.get(key) or "") for key in text_keys)
            score += sum(3 for name in normalized_characters if name and name in haystack)
            haystack_terms = _text_terms(haystack)
            if query_terms and haystack_terms:
                overlap = len(query_terms.intersection(haystack_terms))
                score += min(8.0, overlap / max(1, min(len(query_terms), len(haystack_terms))) * 8.0)

            record_rank = -1
            for key in scene_id_keys:
                candidate_rank = ranks.get(str(record.get(key) or ""), -1)
                record_rank = max(record_rank, candidate_rank)
            if score > 0:
                scored.append((score, record_rank, str(record.get("updated_at") or ""), record_index, record))
        scored.sort(key=lambda item: (item[0], item[1], item[2], item[3]), reverse=True)
        if scored:
            return [item[-1] for item in scored[:limit]]
        if records and not active_characters:
            return sorted(
                records,
                key=lambda record: (
                    max(
                        (ranks.get(str(record.get(key) or ""), -1) for key in scene_id_keys),
                        default=-1,
                    ),
                    str(record.get("updated_at") or ""),
                ),
                reverse=True,
            )[:limit]
        return []

    def format_status(self) -> str:
        state = self.load_state()
        open_quality_tickets = [
            item for item in state.get("quality_memory") or []
            if isinstance(item, dict) and item.get("status") == "open"
        ]
        return (
            "StoryMemory 状态\n"
            f"- 已吸收场景数: {len(state.get('scenes') or [])}\n"
            f"- 已抽取事件数: {len(state.get('events') or [])}\n"
            f"- 已抽取事实数: {len(state.get('fact_claims') or [])}\n"
            f"- 有动态状态的角色数: {len(state.get('character_states') or {})}\n"
            f"- 已记录互动关系数: {len(state.get('relationships') or {})}\n"
            f"- 开放线索数: {len([t for t in state.get('threads') or [] if t.get('status') == 'open'])}\n"
            f"- 潜在冲突风险数: {len(state.get('conflict_risks') or [])}\n"
            f"- 开放修订工单数: {len(open_quality_tickets)}\n"
            f"- 更新时间: {state.get('updated_at') or '-'}"
        )

    def query_text(self, question: str = "", max_items: int = 8) -> str:
        """给 Agent 使用的轻量只读查询。"""
        state = self.load_state()
        question = str(question or "").strip()
        if not question:
            return self.format_status()

        matched_characters = [
            card for name, card in (state.get("character_states") or {}).items()
            if name and name in question
        ]
        matched_relationships = [
            rel for key, rel in (state.get("relationships") or {}).items()
            if any(name in question for name in rel.get("characters") or [])
        ]
        ordered_scenes = sorted(
            [item for item in state.get("scenes") or [] if isinstance(item, dict)],
            key=_scene_sort_key,
        )
        scene_rank_by_id = {
            str(item.get("scene_id")): index
            for index, item in enumerate(ordered_scenes)
            if item.get("scene_id")
        }
        matched_scenes = self._select_relevant_records(
            ordered_scenes,
            active_characters=[name for name in state.get("character_states", {}) if name in question],
            scene_text=question,
            entity_keys=("characters",),
            text_keys=("scene_title", "description", "guidance", "summary"),
            limit=max_items,
            scene_rank_by_id=scene_rank_by_id,
        )
        matched_events = self._select_relevant_records(
            state.get("events") or [],
            active_characters=[name for name in state.get("character_states", {}) if name in question],
            scene_text=question,
            entity_keys=("participants",),
            text_keys=("summary", "evidence", "scene_title"),
            limit=max_items,
            scene_rank_by_id=scene_rank_by_id,
        )
        matched_facts = self._select_relevant_records(
            state.get("fact_claims") or [],
            active_characters=[name for name in state.get("character_states", {}) if name in question],
            scene_text=question,
            entity_keys=("entities",),
            text_keys=("claim", "evidence", "scene_title"),
            limit=max_items,
            scene_rank_by_id=scene_rank_by_id,
        )
        matched_risks = self._select_relevant_records(
            state.get("conflict_risks") or [],
            active_characters=[],
            scene_text=question,
            entity_keys=(),
            text_keys=("risk", "evidence", "scene_title"),
            limit=max_items,
            scene_rank_by_id=scene_rank_by_id,
        )
        matched_quality_tickets = self._select_relevant_records(
            [
                item for item in state.get("quality_memory") or []
                if isinstance(item, dict) and item.get("status") == "open"
            ],
            active_characters=[],
            scene_text=question,
            entity_keys=(),
            text_keys=("target", "edit_goal", "rewrite_brief", "scene_name", "review_target", "source_path"),
            limit=max_items,
            scene_rank_by_id=scene_rank_by_id,
        )

        lines = ["StoryMemory 查询结果", f"- 问题: {question}", ""]
        lines.append("[角色动态状态]")
        if matched_characters:
            for card in matched_characters[:max_items]:
                evidence = (card.get("recent_evidence") or [{}])[-1].get("summary", "")
                lines.append(f"- {card.get('name')}：上次出场 {card.get('last_seen_title') or card.get('last_seen_scene')}；{_compact_text(evidence, 220)}")
        else:
            lines.append("- 未命中角色状态。")

        lines.append("\n[人物关系/同场互动]")
        if matched_relationships:
            for rel in matched_relationships[:max_items]:
                chars = " ↔ ".join(rel.get("characters") or [])
                evidence = (rel.get("recent_evidence") or [{}])[-1].get("summary", "")
                lines.append(f"- {chars}：{rel.get('relation_hint')}；最近证据：{_compact_text(evidence, 180)}")
        else:
            lines.append("- 未命中互动记录。")

        lines.append("\n[相关历史事件]")
        if matched_events:
            for event in matched_events[:max_items]:
                lines.append(f"- {event.get('summary')}（来源：{event.get('scene_title') or event.get('scene_id')}；证据：{_compact_text(event.get('evidence', ''), 180)}）")
        else:
            lines.append("- 未命中历史事件。")

        lines.append("\n[必须保持事实]")
        if matched_facts:
            for fact in matched_facts[:max_items]:
                lines.append(f"- {fact.get('claim')}（证据：{_compact_text(fact.get('evidence', ''), 180)}）")
        else:
            lines.append("- 未命中事实约束。")

        lines.append("\n[潜在冲突风险]")
        if matched_risks:
            for risk in matched_risks[:max_items]:
                lines.append(f"- [{risk.get('severity', 'medium')}] {risk.get('risk')}（证据：{_compact_text(risk.get('evidence', ''), 180)}）")
        else:
            lines.append("- 未命中冲突风险。")

        lines.append("\n[开放修订工单]")
        if matched_quality_tickets:
            for ticket in matched_quality_tickets[:max_items]:
                lines.append(
                    f"- {ticket.get('target') or ticket.get('review_target') or '当前文本'}："
                    f"{_compact_text(ticket.get('edit_goal') or ticket.get('rewrite_brief') or '', 220)}"
                )
        else:
            lines.append("- 未命中开放修订工单。")

        lines.append("\n[相关场景]")
        if matched_scenes:
            for scene in matched_scenes[:max_items]:
                lines.append(f"- {scene.get('scene_title')}：{_compact_text(scene.get('summary', ''), 220)}")
        else:
            lines.append("- 未命中相关场景摘要。")
        return "\n".join(lines)
