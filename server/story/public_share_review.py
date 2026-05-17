from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import os
from typing import Literal

from agents.agent_critic import CriticAgent
from core.file_ingest.chunking import TokenTextSplitter
from core.utils import get_project_stories_path
from story.arc_parser import serialize_to_arc
from story.file_naming import parse_story_filename, story_sort_key
from story.novel_parser import aggregate_novel
from story.scene_loader import load_story_file
from story.scene_models import scene_models_to_plain

PUBLIC_SHARE_REVIEW_CHUNK_TOKENS = 30000


@dataclass(slots=True)
class PublicShareReviewResult:
    decision: str
    reason: str
    risk_tags: list[str]
    evidence: list[str]
    rejected_chunk_index: int | None
    total_chunks: int


class PublicShareReviewRejectedError(RuntimeError):
    def __init__(self, result: PublicShareReviewResult):
        self.result = result
        super().__init__(result.reason)


def _normalize_content_format(value: str | None) -> Literal["script", "novel"]:
    return "novel" if str(value or "").strip().lower() == "novel" else "script"


def _collect_sorted_arc_files(user_id: str, project_name: str) -> list[tuple[str, str]]:
    stories_path = get_project_stories_path(user_id, project_name)
    story_files: list[tuple[object, str, str]] = []

    for root, _, files in os.walk(stories_path):
        for file_name in files:
            if not file_name.endswith(".arc"):
                continue
            parsed = parse_story_filename(file_name)
            if not parsed:
                continue
            full_path = os.path.join(root, file_name)
            rel_path = os.path.relpath(full_path, stories_path)
            story_files.append((story_sort_key(rel_path), rel_path, full_path))

    story_files.sort(key=lambda item: item[0])
    return [(rel_path, full_path) for _, rel_path, full_path in story_files]


def _build_script_public_share_text(user_id: str, project_name: str) -> str:
    blocks: list[str] = []
    for rel_path, full_path in _collect_sorted_arc_files(user_id, project_name):
        scene_models = load_story_file(full_path)
        scene_payload = scene_models_to_plain(scene_models)
        if not scene_payload:
            continue
        arc_text = serialize_to_arc(scene_payload).strip()
        if not arc_text:
            continue
        caption_lines = [
            f"【场景摘要】{scene.guide.strip()}"
            for scene in scene_models
            if str(scene.guide or "").strip()
        ]
        if caption_lines:
            blocks.append(f"【剧本文件】{rel_path}\n" + "\n".join(caption_lines) + f"\n{arc_text}")
        else:
            blocks.append(f"【剧本文件】{rel_path}\n{arc_text}")
    return "\n\n".join(blocks).strip()


def build_public_share_source_text(user_id: str, project_name: str, content_format: str | None) -> str:
    normalized_format = _normalize_content_format(content_format)
    if normalized_format == "novel":
        return aggregate_novel(user_id, project_name, export_format="md").strip()
    return _build_script_public_share_text(user_id, project_name)


def _review_single_chunk(
    critic: CriticAgent,
    chunk_text: str,
    review_target: str,
    chunk_index: int,
    total_chunks: int,
) -> tuple[int, dict | Exception]:
    """审核单个切片，返回 (chunk_index, result_dict | Exception)。"""
    try:
        result = critic.moderate_public_share(
            content_text=chunk_text,
            review_target=f"{review_target}（第 {chunk_index + 1}/{total_chunks} 段）",
        )
        return (chunk_index, result)
    except Exception as exc:
        return (chunk_index, exc)


def review_public_share(user_id: str, project_name: str, content_format: str | None) -> PublicShareReviewResult:
    normalized_format = _normalize_content_format(content_format)
    source_text = build_public_share_source_text(user_id, project_name, normalized_format)
    if not source_text:
        raise ValueError("当前项目没有可用于公开分享审核的文本内容")

    splitter = TokenTextSplitter(chunk_tokens=PUBLIC_SHARE_REVIEW_CHUNK_TOKENS)
    chunks = splitter.split(source_text)
    if not chunks:
        raise ValueError("公开分享审核文本切分失败")

    critic = CriticAgent(user_id)
    review_target = "项目全量小说公开分享" if normalized_format == "novel" else "项目全量剧本公开分享"
    total_chunks = len(chunks)

    # 并发审核所有切片
    rejected_chunks: list[tuple[int, dict]] = []  # (chunk_index, result)
    model_errors: list[tuple[int, Exception]] = []  # (chunk_index, exception)

    with ThreadPoolExecutor(max_workers=min(len(chunks), 4)) as executor:
        futures = {
            executor.submit(
                _review_single_chunk,
                critic,
                chunk.text,
                review_target,
                chunk.index,
                total_chunks,
            ): chunk.index
            for chunk in chunks
        }
        for future in as_completed(futures):
            chunk_index, outcome = future.result()
            if isinstance(outcome, Exception):
                model_errors.append((chunk_index, outcome))
            else:
                decision = str(outcome.get("decision") or "").strip().upper()
                if decision != "PASS":
                    rejected_chunks.append((chunk_index, outcome))

    # 模型报错：返回友好提示
    if model_errors:
        first_idx, first_exc = model_errors[0]
        error_detail = f"{type(first_exc).__name__}: {first_exc}"
        return PublicShareReviewResult(
            decision="REJECT",
            reason=(
                f"审核时 fast 用途模型出现问题，请确保该模型可用，"
                f"也有可能是待审核内容出现了严重违规内容，上游厂商拒绝返回处理结果。"
                f"原始报错如下：{error_detail}"
            ),
            risk_tags=["model_error"],
            evidence=[f"第 {first_idx + 1}/{total_chunks} 段审核失败"],
            rejected_chunk_index=first_idx,
            total_chunks=total_chunks,
        )

    # 全部通过
    if not rejected_chunks:
        return PublicShareReviewResult(
            decision="PASS",
            reason="审核通过",
            risk_tags=[],
            evidence=[],
            rejected_chunk_index=None,
            total_chunks=total_chunks,
        )

    # 汇总所有拒绝原因
    all_risk_tags: list[str] = []
    all_evidence: list[str] = []
    reason_parts: list[str] = []
    for chunk_index, result in rejected_chunks:
        chunk_reason = str(result.get("reason") or "公开前审核未通过").strip() or "公开前审核未通过"
        reason_parts.append(f"第 {chunk_index + 1}/{total_chunks} 段：{chunk_reason}")
        all_risk_tags.extend(str(t) for t in (result.get("risk_tags") or []) if str(t).strip())
        all_evidence.extend(str(e) for e in (result.get("evidence") or []) if str(e).strip())

    return PublicShareReviewResult(
        decision="REJECT",
        reason="；".join(reason_parts),
        risk_tags=list(dict.fromkeys(all_risk_tags)),  # 去重保序
        evidence=all_evidence,
        rejected_chunk_index=rejected_chunks[0][0],
        total_chunks=total_chunks,
    )


def ensure_public_share_allowed(user_id: str, project_name: str, content_format: str | None) -> PublicShareReviewResult:
    result = review_public_share(user_id, project_name, content_format)
    if result.decision != "PASS":
        raise PublicShareReviewRejectedError(result)
    return result
