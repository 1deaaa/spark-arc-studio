"""
同步流式生成桥接工具。

很多 Agent 的 `llm.stream()` 返回的是同步生成器。如果在 FastAPI 的
`async def` 路由里直接 `for chunk in ...`，当底层模型长时间等待 token
或网络阻塞时，会占住事件循环线程，进而拖慢其他请求。

本文件负责把“同步生成器 -> 异步 HTTP 流式响应”的桥接逻辑统一收口：
1. 复制当前请求的 `ContextVar` 上下文；
2. 把同步迭代过程放到后台线程执行；
3. 通过 `asyncio.Queue` 把结果安全回传给异步路由协程。

注意：
- 这里不会吞掉后台线程中的原始异常；
- 路由层可以继续用既有的 `format_ai_error()` 把友好提示和原始报错一并传给前端。
"""

from __future__ import annotations

import asyncio
import contextlib
import contextvars
import threading
from collections.abc import AsyncIterator, Callable, Iterable
from dataclasses import dataclass
from typing import Any, TypeVar, cast

T = TypeVar("T")


class ClientDisconnectedError(RuntimeError):
    """客户端主动断开流连接。"""


@dataclass(slots=True)
class _WorkerError:
    """后台线程执行失败时，用于把原始异常投递回异步消费者。"""

    error: Exception


def close_iterable_safely(iterable: Any) -> None:
    """尽力关闭同步生成器 / 迭代器，避免客户端中止后继续悬挂。"""

    if iterable is None:
        return

    close = getattr(iterable, "close", None)
    if callable(close):
        try:
            close()
        except Exception:
            pass


async def stop_on_client_disconnect(
    request,
    stop_event: threading.Event,
    *,
    poll_interval: float = 0.15,
    cancelled_event: threading.Event | None = None,
) -> None:
    """轮询客户端连接状态，一旦断开则设置停止事件。

    Args:
        cancelled_event: 可选。仅在客户端主动断开时设置，正常完成时不动。
            调用方可用它区分"迭代正常结束"和"被取消"两种情况，
            因为 iterate_sync_iterable_in_thread 的 finally 块会无条件
            set(stop_event)，用 stop_event 无法判断是否真的被取消。
    """

    if request is None:
        return

    try:
        while not stop_event.is_set():
            if await request.is_disconnected():
                stop_event.set()
                if cancelled_event is not None:
                    cancelled_event.set()
                raise ClientDisconnectedError("client disconnected")
            await asyncio.sleep(poll_interval)
    except asyncio.CancelledError:
        raise
    except RuntimeError:
        stop_event.set()
        if cancelled_event is not None:
            cancelled_event.set()


async def iterate_sync_iterable_in_thread(
    iterable_factory: Callable[[], Iterable[T] | None],
    *,
    request=None,
    stop_event: threading.Event | None = None,
    cancelled_event: threading.Event | None = None,
    poll_interval: float = 0.15,
) -> AsyncIterator[T]:
    """
    在线程池中执行同步可迭代对象，并在异步上下文中逐项产出。

    适用场景：
    - LangChain / LLM SDK 返回同步流式迭代器；
    - FastAPI 路由本身是 `async`，不能直接长时间阻塞在同步 `for` 循环上；
    - 需要保留当前请求的 `ContextVar`（例如用户、项目上下文）给后台线程继续使用。

    Args:
        iterable_factory: 返回同步可迭代对象的工厂函数。
        cancelled_event: 可选。仅在客户端主动断开时设置，正常完成时不动。
            调用方可用它区分"迭代正常结束"和"被取消"两种情况——
            本函数的 finally 块会无条件 set(stop_event)，
            因此不能用 stop_event 判断是否真的被取消。

    Yields:
        同步迭代器产生的每一项。

    Raises:
        Exception: 后台线程中的原始异常，保持不变地抛回给调用方。
    """

    loop = asyncio.get_running_loop()
    result_queue: asyncio.Queue[object] = asyncio.Queue()
    sentinel = object()
    request_context = contextvars.copy_context()
    worker_stop_event = stop_event or threading.Event()
    worker_iterable: Iterable[T] | None = None

    def _put(item: object) -> None:
        loop.call_soon_threadsafe(result_queue.put_nowait, item)

    def _worker() -> None:
        nonlocal worker_iterable

        def _consume_iterable() -> None:
            iterable = iterable_factory()
            worker_iterable = iterable
            if iterable is None:
                return

            for item in iterable:
                if worker_stop_event.is_set():
                    break
                _put(item)

        try:
            # 必须把“创建生成器 + 实际迭代”都放在复制出来的上下文里执行。
            # 否则像 `ShowrunnerAgent.execute()` 这类返回同步生成器的方法，
            # 其真正执行发生在 `for item in iterable` 阶段，可能丢失请求级 ContextVar。
            request_context.run(_consume_iterable)
        except Exception as exc:  # noqa: BLE001 - 需要原样把异常回传给路由层
            _put(_WorkerError(exc))
        finally:
            close_iterable_safely(worker_iterable)
            _put(sentinel)

    worker_future = loop.run_in_executor(None, _worker)
    disconnect_task = None
    if request is not None:
        disconnect_task = asyncio.create_task(
            stop_on_client_disconnect(
                request,
                worker_stop_event,
                poll_interval=poll_interval,
                cancelled_event=cancelled_event,
            )
        )

    try:
        while True:
            try:
                item = await asyncio.wait_for(result_queue.get(), timeout=poll_interval)
            except asyncio.TimeoutError:
                if worker_stop_event.is_set() and worker_future.done():
                    break
                continue

            if item is sentinel:
                break
            if isinstance(item, _WorkerError):
                await worker_future
                raise item.error
            yield cast(T, item)
    finally:
        worker_stop_event.set()
        await loop.run_in_executor(None, close_iterable_safely, worker_iterable)

        if disconnect_task is not None:
            disconnect_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, ClientDisconnectedError):
                await disconnect_task

        if worker_future.done():
            await worker_future
