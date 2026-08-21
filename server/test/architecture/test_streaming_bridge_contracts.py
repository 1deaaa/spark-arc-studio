from __future__ import annotations

import contextvars
import asyncio
import threading

import pytest

from agents.routes.streaming_utils import iterate_sync_iterable_in_thread
from agents.stream_semantics import (
    merge_semantics,
    on_delta,
    on_done,
    on_error,
    on_progress,
    on_start,
    semantic_event_data,
    semantic_sse_data,
)
from agents.routes import stream_semantics as legacy_stream_semantics


def test_iterate_sync_iterable_in_thread_preserves_contextvars() -> None:
    marker = contextvars.ContextVar("marker", default="")
    marker.set("request-context")

    def factory():
        yield marker.get()
        yield "done"

    async def collect_items():
        result = []
        async for item in iterate_sync_iterable_in_thread(factory):
            result.append(item)
        return result

    result = asyncio.run(collect_items())

    assert result == ["request-context", "done"]


def test_iterate_sync_iterable_in_thread_propagates_worker_errors() -> None:
    class WorkerBoom(RuntimeError):
        pass

    def factory():
        yield "before"
        raise WorkerBoom("boom")

    async def collect_items():
        items = []
        async for item in iterate_sync_iterable_in_thread(factory):
            items.append(item)
        return items

    with pytest.raises(WorkerBoom):
        asyncio.run(collect_items())


def test_iterate_sync_iterable_in_thread_closes_generator_on_break() -> None:
    closed = threading.Event()

    def factory():
        try:
            yield "first"
            while True:
                yield "later"
        finally:
            closed.set()

    async def consume_one():
        async for item in iterate_sync_iterable_in_thread(factory):
            assert item == "first"
            break

    asyncio.run(consume_one())

    assert closed.wait(1)


def test_stream_semantics_payload_shapes_are_stable() -> None:
    payload = merge_semantics(
        on_start("开始"),
        on_progress("生成中", stage="draft"),
        on_delta("文本"),
        on_done("完成"),
        request_id="r1",
    )

    assert payload["onStart"]["message"] == "开始"
    assert payload["onProgress"]["stage"] == "draft"
    assert payload["onDelta"]["text"] == "文本"
    assert payload["onDone"]["message"] == "完成"
    assert payload["request_id"] == "r1"

    assert '"status": "running"' in semantic_sse_data("running", onStart={"message": "开始"})
    event = semantic_event_data("progress", "running", onProgress={"message": "生成中"})
    assert event["event"] == "progress"
    assert '"onProgress"' in event["data"]
    assert on_error("坏了") == {"onError": {"message": "坏了"}}


def test_route_stream_semantics_is_only_a_compatibility_export() -> None:
    assert legacy_stream_semantics.semantic_sse_data is semantic_sse_data
    assert legacy_stream_semantics.merge_semantics is merge_semantics
