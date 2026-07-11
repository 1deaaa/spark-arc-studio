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


def sanitize_arc_ai_fragment(
    text: str,
    *,
    allow_visual_illustration: bool = False,
    allowed_background_ids: set[str] | None = None,
) -> str:
    """清洗一段来源于 AI 的 ARC 文本，但暂不依赖其所在场景位置。

    该阶段只执行字段白名单：删除 ``@next``、``@act`` 和所有资产绑定，
    仅在开关有效时保留规范化的 ``illustration_prompt``。节点位置、场景数量
    和间距必须在片段并入完整文档后再校验。
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
    实验开关开启时也只暴露自然语言 ``illustration_prompt``，资产 ID 永不暴露。
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

    ``illustration_prompt`` 必须挂在说话人节点之后。每个 ``#`` 场景独立计数；
    ``min_node_gap=1`` 表示两个插图描述节点之间至少隔一个普通节点。
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
    scene_prompt_count = 0
    node_index = -1
    last_prompt_node = -10_000
    kept_lines: list[str] = []

    for line in safe_fragment.splitlines():
        if _SCENE_HEADER_RE.match(line):
            scene_prompt_count = 0
            node_index = -1
            last_prompt_node = -10_000
            kept_lines.append(line)
            continue

        if _SPEAKER_MARKER_RE.match(line):
            node_index += 1
            kept_lines.append(line)
            continue

        prompt_match = _VISUAL_ILLUSTRATION_PROMPT_RE.match(line)
        if prompt_match:
            prompt = normalize_illustration_prompt(prompt_match.group("value"))
            can_keep = (
                allow_visual_illustration
                and bool(prompt)
                and node_index >= 0
                and scene_prompt_count < safe_max
                and node_index - last_prompt_node > safe_gap
            )
            if can_keep:
                kept_lines.append(
                    f"{prompt_match.group('indent')}@presentation illustration_prompt:{prompt}"
                )
                scene_prompt_count += 1
                last_prompt_node = node_index
            continue

        kept_lines.append(line)

    return "\n".join(kept_lines).strip()


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
        if not prompt_match or not normalize_illustration_prompt(prompt_match.group("value")):
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
