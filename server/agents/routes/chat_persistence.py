"""Helpers for chat stream event accumulation and assistant history persistence."""

from copy import deepcopy
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


def _extract_context_window_stats_from_event(delta: Any) -> Dict[str, Any] | None:
    if not isinstance(delta, dict):
        return None

    stats_payload: Dict[str, Any] | None = None
    event_type = str(delta.get("event") or "").strip()
    if event_type == "context_window_stats":
        stats_payload = delta
    else:
        nested = delta.get("context_window_stats") or delta.get("contextWindowStats")
        if isinstance(nested, dict):
            stats_payload = nested

    if not isinstance(stats_payload, dict):
        return None

    agent_id = str(
        stats_payload.get("agent_id")
        or stats_payload.get("agentId")
        or stats_payload.get("source_agent")
        or stats_payload.get("sourceAgent")
        or ""
    ).strip()
    input_tokens = int(stats_payload.get("input_tokens") or stats_payload.get("inputTokens") or 0)
    output_tokens = int(stats_payload.get("output_tokens") or stats_payload.get("outputTokens") or 0)
    original_tokens = int(stats_payload.get("original_tokens") or stats_payload.get("originalTokens") or 0)
    retained_messages = int(stats_payload.get("retained_messages") or stats_payload.get("retainedMessages") or 0)
    model = str(stats_payload.get("model") or "").strip()
    compacted = bool(stats_payload.get("compacted"))
    reason = str(stats_payload.get("reason") or "").strip()

    normalized: Dict[str, Any] = {
        "agent_id": agent_id,
        "input_tokens": max(input_tokens, 0),
        "output_tokens": max(output_tokens, 0),
        "original_tokens": max(original_tokens, 0),
        "retained_messages": max(retained_messages, 0),
        "model": model,
        "compacted": compacted,
        "reason": reason,
    }
    for key in (
        "max_context_tokens",
        "max_output_tokens",
        "hard_budget",
        "trigger_budget",
        "reserved_context_tokens",
        # 兼容旧版聊天事件中的字段。
        "reserved_output_tokens",
        "safety_margin_tokens",
        "usage_ratio",
        "original_usage_ratio",
        "hard_usage_ratio",
        "trigger_usage_ratio",
        "trigger_ratio",
    ):
        value = stats_payload.get(key)
        if value is None:
            camel_key = "".join(
                part.capitalize() if index > 0 else part
                for index, part in enumerate(key.split("_"))
            )
            value = stats_payload.get(camel_key)
        if value is None:
            continue
        try:
            if key.endswith("_ratio") or key == "usage_ratio":
                normalized[key] = max(float(value), 0.0)
            else:
                normalized[key] = max(int(value), 0)
        except Exception:
            continue
    return normalized


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
    source_agent = str(delta.get("source_agent") or "").strip()
    parent_tool = str(delta.get("parent_tool") or "").strip()
    tool_call_key = str(delta.get("tool_call_key") or delta.get("toolCallKey") or "").strip()
    trace_key = tool_call_key or f"{tool_name}::{source_agent}::{parent_tool}::{bool(delta.get('nested'))}"
    if trace_key not in tool_trace_map:
        for existing_key, existing in tool_trace_map.items():
            if (
                existing.get("tool_name") == tool_name
                and (existing.get("source_agent") or "") == source_agent
                and (existing.get("parent_tool") or "") == parent_tool
                and bool(existing.get("nested")) == bool(delta.get("nested"))
                and existing.get("status") not in ("finished", "failed", "cancelled")
            ):
                trace_key = existing_key
                break
    trace = dict(tool_trace_map.get(trace_key) or {"tool_name": tool_name})
    if tool_call_key:
        trace["tool_call_key"] = tool_call_key
    if source_agent:
        trace["source_agent"] = source_agent
    if parent_tool:
        trace["parent_tool"] = parent_tool
    if delta.get("nested"):
        trace["nested"] = True
    tool_provider = str(delta.get("tool_provider") or delta.get("toolProvider") or "").strip().lower()
    if tool_provider:
        trace["tool_provider"] = tool_provider

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
        if delta.get("message"):
            trace["message"] = delta["message"]

    for detail_key in ("tool_input", "tool_result", "tool_error"):
        if detail_key in delta and delta.get(detail_key) is not None:
            trace[detail_key] = deepcopy(delta[detail_key])

    started_at = trace.get("started_at")
    finished_at = trace.get("finished_at")
    if isinstance(started_at, (int, float)) and isinstance(finished_at, (int, float)) and finished_at >= started_at:
        trace["duration"] = round(finished_at - started_at, 2)

    tool_trace_map[trace_key] = trace


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
    tool_call_key: str = "",
    parent_tool: str = "",
    tool_provider: str = "",
    tool_input: Any = None,
    tool_result: Any = None,
    tool_error: Any = None,
) -> None:
    fallback_seg = None
    for seg in reversed(segments):
        if (
            seg.get("type") == "tool_trace"
            and seg.get("tool_name") == tool_name
            and (seg.get("source_agent") or "") == (source_agent or "")
            and bool(seg.get("nested")) == bool(nested)
            and seg.get("status") not in ("finished", "failed", "cancelled")
        ):
            if tool_call_key and seg.get("tool_call_key") not in {tool_call_key, "", None} and seg.get("_seg_id") != tool_call_key:
                if fallback_seg is None:
                    fallback_seg = seg
                continue
            if tool_call_key:
                seg["tool_call_key"] = tool_call_key
                seg["_seg_id"] = seg.get("_seg_id") or tool_call_key
            if parent_tool:
                seg["parent_tool"] = parent_tool
            if tool_provider:
                seg["tool_provider"] = tool_provider
            for detail_key, detail_value in (
                ("tool_input", tool_input),
                ("tool_result", tool_result),
                ("tool_error", tool_error),
            ):
                if detail_value is not None:
                    seg[detail_key] = deepcopy(detail_value)
            if status == "running" and seg.get("status") == "started":
                seg["status"] = "running"
                seg["exec_started_at"] = ts
                if tool_action:
                    seg["tool_action"] = tool_action
            return

    if fallback_seg is not None:
        if tool_call_key:
            fallback_seg["tool_call_key"] = tool_call_key
        if parent_tool:
            fallback_seg["parent_tool"] = parent_tool
        if tool_provider:
            fallback_seg["tool_provider"] = tool_provider
        for detail_key, detail_value in (
            ("tool_input", tool_input),
            ("tool_result", tool_result),
            ("tool_error", tool_error),
        ):
            if detail_value is not None:
                fallback_seg[detail_key] = deepcopy(detail_value)
        if status == "running" and fallback_seg.get("status") == "started":
            fallback_seg["status"] = "running"
            fallback_seg["exec_started_at"] = ts
            if tool_action:
                fallback_seg["tool_action"] = tool_action
        return

    seg_id = ""
    if invocation_counter is not None:
        invocation_counter[0] += 1
        seg_id = tool_call_key or f"{tool_name}::{source_agent}:{invocation_counter[0]}"

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
        **({"tool_call_key": tool_call_key} if tool_call_key else {}),
        **({"parent_tool": parent_tool} if parent_tool else {}),
        **({"tool_provider": tool_provider} if tool_provider else {}),
        **({"tool_input": deepcopy(tool_input)} if tool_input is not None else {}),
        **({"tool_result": deepcopy(tool_result)} if tool_result is not None else {}),
        **({"tool_error": deepcopy(tool_error)} if tool_error is not None else {}),
    })


def _append_or_update_context_compaction_segment(
    segments: List[Dict[str, Any]],
    *,
    event_type: str,
    ts: float,
    delta: Dict[str, Any],
) -> None:
    status = "running"
    if event_type == "context_compaction_finished":
        status = "finished"
    elif event_type == "context_compaction_failed":
        status = "failed"

    for seg in reversed(segments):
        if seg.get("type") == "context_compaction" and seg.get("status") == "running":
            seg["status"] = status
            seg["updated_at"] = ts
            if status != "running":
                seg["finished_at"] = ts
                started = seg.get("started_at")
                if isinstance(started, (int, float)):
                    seg["duration"] = round(ts - started, 2)
            for key in ("original_tokens", "compacted_tokens", "retained_messages", "model", "reason", "message"):
                if key in delta:
                    seg[key] = delta[key]
            return

    segment = {
        "type": "context_compaction",
        "status": status,
        "started_at": ts,
        "updated_at": ts,
    }
    if status != "running":
        segment["finished_at"] = ts
    for key in ("original_tokens", "compacted_tokens", "retained_messages", "model", "reason", "message"):
        if key in delta:
            segment[key] = delta[key]
    segments.append(segment)


def _terminal_tool_status(stream_status: str) -> str:
    if stream_status == "cancelled":
        return "cancelled"
    if stream_status == "error":
        return "failed"
    return "finished"


def _finalize_tool_traces(tool_trace_map: Dict[str, Dict[str, Any]], stream_status: str = "completed") -> List[Dict[str, Any]]:
    now_ts = round(time.time(), 3)
    traces: List[Dict[str, Any]] = []
    for trace in tool_trace_map.values():
        tool_name = str(trace.get("tool_name") or "").strip()
        if not tool_name:
            continue
        item = dict(trace)
        if stream_status != "running" and item.get("status") not in ("finished", "failed", "cancelled"):
            item["status"] = _terminal_tool_status(stream_status)
            item["finished_at"] = item.get("finished_at") or now_ts
        if isinstance(item.get("duration"), (int, float)):
            item["duration"] = round(float(item["duration"]), 2)
        else:
            started_at = item.get("started_at")
            finished_at = item.get("finished_at")
            if isinstance(started_at, (int, float)) and isinstance(finished_at, (int, float)) and finished_at >= started_at:
                item["duration"] = round(finished_at - started_at, 2)
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
    tool_call_key = str(delta.get("tool_call_key") or delta.get("toolCallKey") or "").strip()

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

    if event_type in {"context_compaction_started", "context_compaction_finished", "context_compaction_failed"}:
        _append_or_update_context_compaction_segment(
            segments,
            event_type=event_type,
            ts=ts,
            delta=delta,
        )
        return

    tool_name = str(delta.get("tool_name") or delta.get("toolName") or "").strip()
    if not tool_name:
        return

    is_nested = bool(delta.get("nested"))
    parent_tool = str(delta.get("parent_tool") or "").strip()
    tool_provider = str(delta.get("tool_provider") or delta.get("toolProvider") or "").strip().lower()

    if event_type == "tool_intent_started":
        _append_or_upgrade_tool_segment(
            segments,
            tool_name=tool_name,
            status="started",
            ts=ts,
            source_agent=source_agent,
            nested=is_nested,
            invocation_counter=invocation_counter,
            tool_call_key=tool_call_key,
            parent_tool=parent_tool,
            tool_provider=tool_provider,
            tool_input=delta.get("tool_input"),
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
            tool_call_key=tool_call_key,
            parent_tool=parent_tool,
            tool_provider=tool_provider,
            tool_input=delta.get("tool_input"),
        )
        return

    if event_type in {"tool_exec_finished", "tool_exec_failed"}:
        final_status = "finished" if event_type == "tool_exec_finished" else "failed"
        tool_result = delta.get("tool_result")
        tool_error = delta.get("tool_error")
        fallback_seg = None
        for seg in reversed(segments):
            if (
                seg.get("type") == "tool_trace"
                and seg.get("tool_name") == tool_name
                and (seg.get("source_agent") or "") == source_agent
                and seg.get("status") not in ("finished", "failed")
            ):
                if tool_call_key and seg.get("tool_call_key") not in {tool_call_key, "", None} and seg.get("_seg_id") != tool_call_key:
                    if fallback_seg is None:
                        fallback_seg = seg
                    continue
                seg["status"] = final_status
                seg["finished_at"] = ts
                started = seg.get("started_at")
                if isinstance(started, (int, float)):
                    seg["duration"] = round(ts - started, 2)
                if tool_result:
                    seg["tool_result"] = deepcopy(tool_result)
                if tool_error is not None:
                    seg["tool_error"] = deepcopy(tool_error)
                if delta.get("tool_input") is not None:
                    seg["tool_input"] = deepcopy(delta["tool_input"])
                if tool_call_key:
                    seg["tool_call_key"] = tool_call_key
                if parent_tool:
                    seg["parent_tool"] = parent_tool
                if tool_provider:
                    seg["tool_provider"] = tool_provider
                if final_status == "failed" and delta.get("message"):
                    seg["message"] = delta["message"]
                break
        else:
            if fallback_seg is not None:
                fallback_seg["status"] = final_status
                fallback_seg["finished_at"] = ts
                started = fallback_seg.get("started_at")
                if isinstance(started, (int, float)):
                    fallback_seg["duration"] = round(ts - started, 2)
                if tool_result:
                    fallback_seg["tool_result"] = deepcopy(tool_result)
                if tool_error is not None:
                    fallback_seg["tool_error"] = deepcopy(tool_error)
                if delta.get("tool_input") is not None:
                    fallback_seg["tool_input"] = deepcopy(delta["tool_input"])
                if tool_call_key:
                    fallback_seg["tool_call_key"] = tool_call_key
                if parent_tool:
                    fallback_seg["parent_tool"] = parent_tool
                if final_status == "failed" and delta.get("message"):
                    fallback_seg["message"] = delta["message"]
            else:
                segment = {
                    "type": "tool_trace",
                    "tool_name": tool_name,
                    "status": final_status,
                    "started_at": ts,
                    "finished_at": ts,
                    "duration": 0.0,
                    "source_agent": source_agent,
                    "nested": is_nested,
                }
                if tool_call_key:
                    segment["tool_call_key"] = tool_call_key
                if parent_tool:
                    segment["parent_tool"] = parent_tool
                if tool_provider:
                    segment["tool_provider"] = tool_provider
                if delta.get("tool_input") is not None:
                    segment["tool_input"] = deepcopy(delta["tool_input"])
                if tool_result:
                    segment["tool_result"] = deepcopy(tool_result)
                if tool_error is not None:
                    segment["tool_error"] = deepcopy(tool_error)
                if final_status == "failed" and delta.get("message"):
                    segment["message"] = delta["message"]
                segments.append(segment)
        return


def _finalize_segments(segments: List[Dict[str, Any]], stream_status: str = "completed") -> List[Dict[str, Any]]:
    if stream_status == "running":
        return segments
    now_ts = round(time.time(), 3)
    for seg in segments:
        if seg.get("type") == "tool_trace" and seg.get("status") not in ("finished", "failed", "cancelled"):
            seg["status"] = _terminal_tool_status(stream_status)
            seg["finished_at"] = now_ts
            started = seg.get("started_at")
            if isinstance(started, (int, float)):
                seg["duration"] = round(now_ts - started, 2)
        if seg.get("type") == "context_compaction" and seg.get("status") == "running":
            seg["status"] = "failed" if stream_status == "error" else "finished"
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
    stream_status: str = "completed",
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    metadata: Dict[str, Any] = {"channel": channel}
    if terminated_early:
        metadata["interrupted"] = True
        metadata["finish_reason"] = "cancelled"
    metadata["stream_status"] = stream_status
    if reasoning:
        metadata["reasoning"] = reasoning
        metadata["reasoning_duration"] = round(float(reasoning_duration), 2)

    finalized_tool_traces = _finalize_tool_traces(tool_trace_map or {}, stream_status=stream_status)
    if finalized_tool_traces:
        metadata["tool_traces"] = finalized_tool_traces

    finalized_segments = _finalize_segments(segments or [], stream_status=stream_status)
    if finalized_segments:
        metadata["segments"] = finalized_segments

    return metadata, finalized_tool_traces


class ChatStreamAccumulator:
    """Single source of truth for one running chat assistant reply."""

    def __init__(self, *, channel: str, task_id: str = "") -> None:
        self.channel = channel
        self.task_id = task_id
        self.started_at = time.time()
        self.last_seq = 0
        self.reasoning_end_time: float | None = None
        self.content_parts: List[str] = []
        self.reasoning_parts: List[str] = []
        self.tool_trace_map: Dict[str, Dict[str, Any]] = {}
        self.segments: List[Dict[str, Any]] = []
        self.context_window_stats: Dict[str, Any] | None = None
        self._seg_invocation_counter: List[int] = [0]

    @property
    def content(self) -> str:
        return "".join(self.content_parts).strip()

    @property
    def reasoning(self) -> str:
        return "".join(self.reasoning_parts).strip()

    def reset_for_retry(self) -> None:
        self.reasoning_end_time = None
        self.content_parts.clear()
        self.reasoning_parts.clear()
        self.tool_trace_map.clear()
        self.segments.clear()
        self.context_window_stats = None
        self._seg_invocation_counter[0] = 0

    def append_event(self, delta: Any, *, seq: int | None = None, now_ts: float | None = None) -> None:
        if seq is not None:
            self.last_seq = max(self.last_seq, int(seq))

        _collect_tool_trace_from_event(self.tool_trace_map, delta, now_ts=now_ts)
        _collect_segment_from_event(self.segments, self._seg_invocation_counter, delta, now_ts=now_ts)
        context_window_stats = _extract_context_window_stats_from_event(delta)
        if context_window_stats is not None:
            self.context_window_stats = context_window_stats

        event_type = delta.get("event") if isinstance(delta, dict) else "assistant_delta"
        if event_type == "reasoning_delta":
            self.reasoning_parts.append(str(delta.get("text") or ""))

        if event_type == "assistant_delta" and self.reasoning_end_time is None and self.reasoning_parts:
            self.reasoning_end_time = time.time()

        text = _extract_visible_text(delta)
        if text:
            self.content_parts.append(text)

    def reasoning_duration(self, *, end_time: float | None = None) -> float:
        reasoning = self.reasoning
        if not reasoning:
            return 0.0
        end = float(end_time if end_time is not None else time.time())
        if self.reasoning_end_time is None:
            return max(0.0, end - self.started_at)
        return max(0.0, self.reasoning_end_time - self.started_at)

    def build_metadata(self, *, stream_status: str = "running", assistant_message_id: int | None = None) -> Dict[str, Any]:
        metadata, _ = _build_stream_reply_metadata(
            channel=self.channel,
            terminated_early=stream_status == "cancelled",
            reasoning=self.reasoning,
            reasoning_duration=self.reasoning_duration(),
            tool_trace_map=deepcopy(self.tool_trace_map),
            segments=deepcopy(self.segments),
            stream_status=stream_status,
        )
        metadata["stream_seq"] = self.last_seq
        if self.task_id:
            metadata["task_id"] = self.task_id
        if assistant_message_id is not None:
            metadata["assistant_message_id"] = assistant_message_id
        if self.context_window_stats:
            metadata["context_window_stats"] = deepcopy(self.context_window_stats)
        if stream_status == "error":
            metadata["finish_reason"] = "error"
        elif stream_status == "completed":
            metadata["finish_reason"] = "stop"
        return metadata

    def build_snapshot(
        self,
        *,
        status: str,
        assistant_message_id: int | None = None,
        seq: int | None = None,
        error_message: str = "",
    ) -> Dict[str, Any]:
        snapshot_seq = int(seq if seq is not None else self.last_seq)
        metadata = self.build_metadata(stream_status=status, assistant_message_id=assistant_message_id)
        payload: Dict[str, Any] = {
            "event": "task_snapshot",
            "task_id": self.task_id,
            "status": status,
            "seq": snapshot_seq,
            "assistant_message_id": assistant_message_id,
            "content": self.content,
            "reasoning": self.reasoning,
            "reasoning_duration": metadata.get("reasoning_duration", 0),
            "tool_traces": metadata.get("tool_traces", []),
            "segments": metadata.get("segments", []),
            "metadata": metadata,
        }
        if metadata.get("context_window_stats"):
            payload["context_window_stats"] = deepcopy(metadata["context_window_stats"])
        if error_message:
            payload["error"] = error_message
        return payload
