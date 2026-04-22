"""Helpers for chat stream event accumulation and assistant history persistence."""

from typing import Any, Dict, List, Tuple
import time


def _extract_visible_text(delta) -> str:
    if isinstance(delta, str):
        return delta
    if isinstance(delta, dict):
        event_type = delta.get("event")
        if event_type == "assistant_delta":
            return str(delta.get("text") or "")
        if event_type == "error":
            return str(delta.get("message") or "")
    return ""


def _collect_tool_trace_from_event(tool_trace_map: Dict[str, Dict[str, Any]], delta: Any, now_ts: float | None = None) -> None:
    if not isinstance(delta, dict):
        return

    event_type = str(delta.get("event") or "").strip()
    if event_type not in {"tool_intent_started", "tool_exec_started", "tool_exec_finished", "tool_exec_failed"}:
        return

    tool_name = str(delta.get("tool_name") or delta.get("toolName") or "").strip()
    if not tool_name:
        return

    ts = round(float(now_ts if now_ts is not None else time.time()), 3)
    trace = dict(tool_trace_map.get(tool_name) or {"tool_name": tool_name})

    if event_type in {"tool_intent_started", "tool_exec_started"} and not isinstance(trace.get("started_at"), (int, float)):
        trace["started_at"] = ts

    if event_type == "tool_intent_started":
        trace["status"] = "started"
    elif event_type == "tool_exec_started":
        trace["status"] = "running"
        trace["exec_started_at"] = ts
        if delta.get("tool_action"):
            trace["tool_action"] = delta["tool_action"]
    elif event_type == "tool_exec_finished":
        trace["status"] = "finished"
        trace["finished_at"] = ts
        if delta.get("tool_result"):
            trace["tool_result"] = delta["tool_result"]
    elif event_type == "tool_exec_failed":
        trace["status"] = "failed"
        trace["finished_at"] = ts

    started_at = trace.get("started_at")
    finished_at = trace.get("finished_at")
    if isinstance(started_at, (int, float)) and isinstance(finished_at, (int, float)) and finished_at >= started_at:
        trace["duration"] = round(finished_at - started_at, 2)

    tool_trace_map[tool_name] = trace


def _append_text_segment(
    segments: List[Dict[str, Any]],
    *,
    seg_type: str,
    text: str,
    source_agent: str = "",
) -> None:
    if not text:
        return

    last = segments[-1] if segments else None
    if (
        last
        and last.get("type") == seg_type
        and (last.get("source_agent") or "") == (source_agent or "")
    ):
        last["text"] = str(last.get("text") or "") + text
        return

    segment = {"type": seg_type, "text": text}
    if source_agent:
        segment["source_agent"] = source_agent
    segments.append(segment)


def _append_or_upgrade_tool_segment(
    segments: List[Dict[str, Any]],
    *,
    tool_name: str,
    status: str,
    ts: float,
    source_agent: str = "",
    nested: bool = False,
    invocation_counter: List[int] | None = None,
    tool_action: str = "",
) -> None:
    for seg in reversed(segments):
        if (
            seg.get("type") == "tool_trace"
            and seg.get("tool_name") == tool_name
            and (seg.get("source_agent") or "") == (source_agent or "")
            and bool(seg.get("nested")) == bool(nested)
            and seg.get("status") not in ("finished", "failed", "cancelled")
        ):
            if status == "running" and seg.get("status") == "started":
                seg["status"] = "running"
                seg["exec_started_at"] = ts
                if tool_action:
                    seg["tool_action"] = tool_action
            return

    seg_id = ""
    if invocation_counter is not None:
        invocation_counter[0] += 1
        seg_id = f"{tool_name}::{source_agent}:{invocation_counter[0]}"

    segments.append({
        "type": "tool_trace",
        "tool_name": tool_name,
        "status": status,
        "started_at": ts,
        "source_agent": source_agent,
        "nested": nested,
        **({"exec_started_at": ts} if status == "running" else {}),
        **({"_seg_id": seg_id} if seg_id else {}),
        **({"tool_action": tool_action} if tool_action else {}),
    })


def _finalize_tool_traces(tool_trace_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    traces: List[Dict[str, Any]] = []
    for trace in tool_trace_map.values():
        tool_name = str(trace.get("tool_name") or "").strip()
        if not tool_name:
            continue
        item = dict(trace)
        if isinstance(item.get("duration"), (int, float)):
            item["duration"] = round(float(item["duration"]), 2)
        traces.append(item)
    return traces


def _collect_segment_from_event(
    segments: List[Dict[str, Any]],
    invocation_counter: List[int],
    delta: Any,
    now_ts: float | None = None,
) -> None:
    ts = round(float(now_ts if now_ts is not None else time.time()), 3)

    if not isinstance(delta, dict):
        raw_text = str(delta) if delta else ""
        if raw_text:
            _append_text_segment(segments, seg_type="text", text=raw_text)
        return

    event_type = str(delta.get("event") or "").strip()
    source_agent = str(delta.get("source_agent") or "").strip()

    if event_type == "reasoning_delta":
        text = str(delta.get("text") or delta.get("content") or "")
        if not text:
            return
        _append_text_segment(segments, seg_type="reasoning", text=text, source_agent=source_agent)
        return

    if event_type == "assistant_delta":
        raw_text = str(delta.get("text") or delta.get("content") or "")
        if not raw_text:
            return
        _append_text_segment(segments, seg_type="text", text=raw_text, source_agent=source_agent)
        return

    tool_name = str(delta.get("tool_name") or delta.get("toolName") or "").strip()
    if not tool_name:
        return

    is_nested = bool(delta.get("nested"))

    if event_type == "tool_intent_started":
        _append_or_upgrade_tool_segment(
            segments,
            tool_name=tool_name,
            status="started",
            ts=ts,
            source_agent=source_agent,
            nested=is_nested,
            invocation_counter=invocation_counter,
        )
        return

    if event_type == "tool_exec_started":
        tool_action = str(delta.get("tool_action") or "").strip()
        _append_or_upgrade_tool_segment(
            segments,
            tool_name=tool_name,
            status="running",
            ts=ts,
            source_agent=source_agent,
            nested=is_nested,
            invocation_counter=invocation_counter,
            tool_action=tool_action,
        )
        return

    if event_type in {"tool_exec_finished", "tool_exec_failed"}:
        final_status = "finished" if event_type == "tool_exec_finished" else "failed"
        tool_result = str(delta.get("tool_result") or "").strip()
        for seg in reversed(segments):
            if (
                seg.get("type") == "tool_trace"
                and seg.get("tool_name") == tool_name
                and (seg.get("source_agent") or "") == source_agent
                and seg.get("status") not in ("finished", "failed")
            ):
                seg["status"] = final_status
                seg["finished_at"] = ts
                started = seg.get("started_at")
                if isinstance(started, (int, float)):
                    seg["duration"] = round(ts - started, 2)
                if tool_result:
                    seg["tool_result"] = tool_result
                break
        return


def _finalize_segments(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    now_ts = round(time.time(), 3)
    for seg in segments:
        if seg.get("type") == "tool_trace" and seg.get("status") not in ("finished", "failed", "cancelled"):
            seg["status"] = "finished"
            seg["finished_at"] = now_ts
            started = seg.get("started_at")
            if isinstance(started, (int, float)):
                seg["duration"] = round(now_ts - started, 2)
    return segments


def _build_stream_reply_metadata(
    *,
    channel: str,
    terminated_early: bool = False,
    reasoning: str = "",
    reasoning_duration: float = 0.0,
    tool_trace_map: Dict[str, Dict[str, Any]] | None = None,
    segments: List[Dict[str, Any]] | None = None,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    metadata: Dict[str, Any] = {"channel": channel}
    if terminated_early:
        metadata["interrupted"] = True
        metadata["finish_reason"] = "cancelled"
    if reasoning:
        metadata["reasoning"] = reasoning
        metadata["reasoning_duration"] = round(float(reasoning_duration), 2)

    finalized_tool_traces = _finalize_tool_traces(tool_trace_map or {})
    if finalized_tool_traces:
        metadata["tool_traces"] = finalized_tool_traces

    finalized_segments = _finalize_segments(segments or [])
    if finalized_segments:
        metadata["segments"] = finalized_segments

    return metadata, finalized_tool_traces

