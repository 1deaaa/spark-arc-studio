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
import contextvars
from collections.abc import AsyncIterator, Callable, Iterable
from dataclasses import dataclass
from typing import TypeVar, cast

T = TypeVar("T")


@dataclass(slots=True)
class _WorkerError:
    """后台线程执行失败时，用于把原始异常投递回异步消费者。"""

    error: Exception


async def iterate_sync_iterable_in_thread(
    iterable_factory: Callable[[], Iterable[T] | None],
) -> AsyncIterator[T]:
    """
    在线程池中执行同步可迭代对象，并在异步上下文中逐项产出。

    适用场景：
    - LangChain / LLM SDK 返回同步流式迭代器；
    - FastAPI 路由本身是 `async`，不能直接长时间阻塞在同步 `for` 循环上；
    - 需要保留当前请求的 `ContextVar`（例如用户、项目上下文）给后台线程继续使用。

    Args:
        iterable_factory: 返回同步可迭代对象的工厂函数。

    Yields:
        同步迭代器产生的每一项。

    Raises:
        Exception: 后台线程中的原始异常，保持不变地抛回给调用方。
    """

    loop = asyncio.get_running_loop()
    result_queue: asyncio.Queue[object] = asyncio.Queue()
    sentinel = object()
    request_context = contextvars.copy_context()

    def _put(item: object) -> None:
        loop.call_soon_threadsafe(result_queue.put_nowait, item)

    def _worker() -> None:
        def _consume_iterable() -> None:
            iterable = iterable_factory()
            if iterable is None:
                return

            for item in iterable:
                _put(item)

        try:
            # 必须把“创建生成器 + 实际迭代”都放在复制出来的上下文里执行。
            # 否则像 `ShowrunnerAgent.execute()` 这类返回同步生成器的方法，
            # 其真正执行发生在 `for item in iterable` 阶段，可能丢失请求级 ContextVar。
            request_context.run(_consume_iterable)
        except Exception as exc:  # noqa: BLE001 - 需要原样把异常回传给路由层
            _put(_WorkerError(exc))
        finally:
            _put(sentinel)

    worker_future = loop.run_in_executor(None, _worker)

    while True:
        item = await result_queue.get()
        if item is sentinel:
            break
        if isinstance(item, _WorkerError):
            await worker_future
            raise item.error
        yield cast(T, item)

    await worker_future
