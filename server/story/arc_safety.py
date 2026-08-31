from __future__ import annotations

import re


_AI_CONTROL_DIRECTIVE_RE = re.compile(
    r"^\s*(?:@next\b.*|@act\b.*|@(?:web|presentation)\b.*)$",
    re.IGNORECASE,
)
_VISUAL_ILLUSTRATION_PROMPT_RE = re.compile(
    r"^(?P<indent>\s*)@presentation\s+illustration_prompt\s*:(?P<value>.*)$",
    re.IGNORECASE,
)
_VISUAL_ILLUSTRATION_PENDING_RE = re.compile(
    r"^(?P<indent>\s*)@presentation\s+illustration_pending\s*:(?P<value>.*)$",
    re.IGNORECASE,
)
_PRESENTATION_BACKGROUND_RE = re.compile(
    r"^(?P<indent>\s*)@presentation\s+bg\s*:(?P<value>[^\s<>,]+)\s*$",
    re.IGNORECASE,
)
_SCENE_HEADER_RE = re.compile(r"^\s*#(?!#)\s+\S")
_SPEAKER_MARKER_RE = re.compile(r"^\s*\[[^\]]+\]\s*$")
_MAX_ILLUSTRATION_PROMPT_CHARS = 1200


def normalize_illustration_prompt(value: str) -> str:
    """把节点描述规范成 ARC 可稳定保存的一行自然语言。"""
    normalized = re.sub(r"\s+", " ", str(value or "")).strip()
    normalized = normalized.replace("<", "").replace(">", "")
    return normalized[:_MAX_ILLUSTRATION_PROMPT_CHARS].strip()


def normalize_illustration_pending(value: object) -> str:
    """只把明确的 true 预留标记规范成 ARC 的固定值。"""
    normalized = str(value or "").strip().lower()
    return "true" if normalized in {"true", "1", "yes"} else ""


def sanitize_arc_ai_fragment(
    text: str,
    *,
    allow_visual_illustration: bool = False,
    allowed_background_ids: set[str] | None = None,
) -> str:
    """清洗一段来源于 AI 的 ARC 文本，但暂不依赖其所在场景位置。

    该阶段只执行字段白名单：删除 ``@next``、``@act`` 和所有资产绑定，
    仅在开关有效时保留规范化的 ``illustration_prompt`` 与 ``illustration_pending``。
    节点位置、场景数量和间距必须在片段并入完整文档后再校验。
    """
    if not text:
        return ""

    kept_lines: list[str] = []
    allowed_backgrounds = {str(value).strip() for value in (allowed_background_ids or set()) if str(value).strip()}
    for line in str(text).splitlines():
        prompt_match = _VISUAL_ILLUSTRATION_PROMPT_RE.match(line)
        if prompt_match:
            if allow_visual_illustration:
                prompt = normalize_illustration_prompt(prompt_match.group("value"))
                if prompt:
                    kept_lines.append(
                        f"{prompt_match.group('indent')}@presentation illustration_prompt:{prompt}"
                    )
            continue
        pending_match = _VISUAL_ILLUSTRATION_PENDING_RE.match(line)
        if pending_match:
            if allow_visual_illustration:
                pending = normalize_illustration_pending(pending_match.group("value"))
                if pending:
                    kept_lines.append(
                        f"{pending_match.group('indent')}@presentation illustration_pending:{pending}"
                    )
            continue
        background_match = _PRESENTATION_BACKGROUND_RE.match(line)
        if background_match:
            asset_id = background_match.group("value").strip()
            if asset_id in allowed_backgrounds:
                kept_lines.append(
                    f"{background_match.group('indent')}@presentation bg:{asset_id}"
                )
            continue
        if _AI_CONTROL_DIRECTIVE_RE.match(line):
            continue
        kept_lines.append(line)
    return "\n".join(kept_lines).strip()


def sanitize_arc_for_ai_context(
    text: str,
    *,
    allow_visual_illustration: bool = False,
    allowed_background_ids: set[str] | None = None,
) -> str:
    """清理传给 AI 的历史 ARC 片段，避免模型模仿运行时控制节点。

    这里仅构造 Scriptwriter 可见的干净上下文视图，不改写用户原文件。
    实验开关开启时只暴露自然语言 ``illustration_prompt`` 或固定的 pending 标记，
    资产 ID 永不暴露。
    """
    return sanitize_arc_ai_fragment(
        text,
        allow_visual_illustration=allow_visual_illustration,
        allowed_background_ids=allowed_background_ids,
    )


def sanitize_arc_for_project_ai_context(text: str, user_id: str, project_name: str) -> str:
    """按项目开关构造模型可见 ARC；读取失败时保持最保守的关闭状态。"""
    try:
        from core.project_settings import is_visual_illustration_enabled

        enabled = is_visual_illustration_enabled(str(user_id), str(project_name))
    except Exception:
        enabled = False
    try:
        from story.presentation_manifest import get_project_background_catalog

        allowed_background_ids = {
            item["id"] for item in get_project_background_catalog(str(user_id), str(project_name))
        }
    except Exception:
        allowed_background_ids = set()
    return sanitize_arc_for_ai_context(
        text,
        allow_visual_illustration=enabled,
        allowed_background_ids=allowed_background_ids,
    )


def sanitize_arc_ai_output(
    text: str,
    *,
    allow_visual_illustration: bool = False,
    max_per_scene: int = 2,
    min_node_gap: int = 1,
    allowed_background_ids: set[str] | None = None,
) -> str:
    """清洗 Scriptwriter 即将落盘的 ARC，执行字段白名单与节奏硬约束。

    ``illustration_prompt`` 和 ``illustration_pending`` 必须挂在说话人节点之后。
    每个 ``#`` 场景独立计数；``min_node_gap=1`` 表示两个视觉节点之间至少隔一个普通节点。
    """
    safe_fragment = sanitize_arc_ai_fragment(
        text,
        allow_visual_illustration=allow_visual_illustration,
        allowed_background_ids=allowed_background_ids,
    )
    if not safe_fragment:
        return ""

    safe_max = max(1, min(4, int(max_per_scene or 2)))
    safe_gap = max(0, min(4, int(min_node_gap or 0)))
    scene_visual_count = 0
    node_index = -1
    last_visual_node = -10_000
    node_has_prompt = False
    node_has_pending = False
    pending_output_index: int | None = None
    kept_lines: list[str | None] = []

    for line in safe_fragment.splitlines():
        if _SCENE_HEADER_RE.match(line):
            scene_visual_count = 0
            node_index = -1
            last_visual_node = -10_000
            node_has_prompt = False
            node_has_pending = False
            pending_output_index = None
            kept_lines.append(line)
            continue

        if _SPEAKER_MARKER_RE.match(line):
            node_index += 1
            node_has_prompt = False
            node_has_pending = False
            pending_output_index = None
            kept_lines.append(line)
            continue

        prompt_match = _VISUAL_ILLUSTRATION_PROMPT_RE.match(line)
        if prompt_match:
            prompt = normalize_illustration_prompt(prompt_match.group("value"))
            reserved_by_current_node = 1 if node_has_pending else 0
            previous_visual_node = None if node_has_pending else last_visual_node
            can_keep = (
                allow_visual_illustration
                and bool(prompt)
                and node_index >= 0
                and scene_visual_count - reserved_by_current_node < safe_max
                and (
                    previous_visual_node is None
                    or node_index - previous_visual_node > safe_gap
                )
            )
            if can_keep:
                if pending_output_index is not None:
                    kept_lines[pending_output_index] = None
                    scene_visual_count -= 1
                    pending_output_index = None
                    node_has_pending = False
                kept_lines.append(
                    f"{prompt_match.group('indent')}@presentation illustration_prompt:{prompt}"
                )
                scene_visual_count += 1
                last_visual_node = node_index
                node_has_prompt = True
            continue

        pending_match = _VISUAL_ILLUSTRATION_PENDING_RE.match(line)
        if pending_match:
            pending = normalize_illustration_pending(pending_match.group("value"))
            can_keep = (
                allow_visual_illustration
                and bool(pending)
                and node_index >= 0
                and not node_has_prompt
                and not node_has_pending
                and scene_visual_count < safe_max
                and node_index - last_visual_node > safe_gap
            )
            if can_keep:
                pending_output_index = len(kept_lines)
                kept_lines.append(
                    f"{pending_match.group('indent')}@presentation illustration_pending:{pending}"
                )
                scene_visual_count += 1
                last_visual_node = node_index
                node_has_pending = True
            continue

        kept_lines.append(line)

    return "\n".join(line for line in kept_lines if line is not None).strip()


def _visual_prompt_policy_metrics(
    text: str,
    *,
    max_per_scene: int,
    min_node_gap: int,
) -> list[tuple[int, int, int]]:
    """按场景统计孤立、超量和间距违规，供增量落盘比较。"""
    safe_max = max(1, min(4, int(max_per_scene or 2)))
    safe_gap = max(0, min(4, int(min_node_gap or 0)))
    metrics: list[tuple[int, int, int]] = []
    node_index = -1
    prompt_count = 0
    orphan_count = 0
    gap_violation_count = 0
    last_prompt_node: int | None = None

    def flush_scene() -> None:
        metrics.append((
            orphan_count,
            max(0, prompt_count - safe_max),
            gap_violation_count,
        ))

    for line in str(text or "").splitlines():
        if _SCENE_HEADER_RE.match(line):
            flush_scene()
            node_index = -1
            prompt_count = 0
            orphan_count = 0
            gap_violation_count = 0
            last_prompt_node = None
            continue
        if _SPEAKER_MARKER_RE.match(line):
            node_index += 1
            continue
        prompt_match = _VISUAL_ILLUSTRATION_PROMPT_RE.match(line)
        if prompt_match:
            if not normalize_illustration_prompt(prompt_match.group("value")):
                continue
        else:
            pending_match = _VISUAL_ILLUSTRATION_PENDING_RE.match(line)
            if not pending_match or not normalize_illustration_pending(pending_match.group("value")):
                continue
        prompt_count += 1
        if node_index < 0:
            orphan_count += 1
        if last_prompt_node is not None and node_index - last_prompt_node <= safe_gap:
            gap_violation_count += 1
        last_prompt_node = node_index

    flush_scene()
    return metrics


def validate_arc_visual_prompt_candidate(
    original_text: str,
    candidate_text: str,
    *,
    max_per_scene: int = 2,
    min_node_gap: int = 1,
) -> None:
    """拒绝增量写入新引入的插图节奏违规，同时保留既有人工字段。

    该校验比较修改前后各场景的违规指标。用户原文件即使已经含有超量描述，
    无关的 AI 文本 patch 仍可继续；但 AI 不得新增孤立、超量或过近的描述。
    """
    before = _visual_prompt_policy_metrics(
        original_text,
        max_per_scene=max_per_scene,
        min_node_gap=min_node_gap,
    )
    after = _visual_prompt_policy_metrics(
        candidate_text,
        max_per_scene=max_per_scene,
        min_node_gap=min_node_gap,
    )
    for index, current in enumerate(after):
        baseline = before[index] if index < len(before) else (0, 0, 0)
        if any(value > baseline[pos] for pos, value in enumerate(current)):
            raise ValueError(
                "AI 修改会新增孤立、超量或间距过近的视觉插图描述，请减少插图节点后重试"
            )
