from __future__ import annotations

import asyncio
import json


def _start(service, user_id: str, project_name: str):
    return service.start_auto_write_background(
        user_id=user_id,
        project_name=project_name,
        outline={"nodes": []},
        mode="continuous_write",
        start_chapter_index=0,
        start_scene_index=0,
        export_format="arc",
    )


def test_auto_write_tasks_are_isolated_by_user_and_stop_target_only(monkeypatch) -> None:
    from agents import auto_write_service as service

    async def fake_stream(**kwargs):
        yield 'data: {"status":"started"}\n\n'
        while not kwargs["stop_event"].is_set():
            await asyncio.sleep(0.005)
        yield 'data: {"status":"cancelled"}\n\n'

    monkeypatch.setattr("agents.routes.auto_write.generate_script_stream", fake_stream)

    first = _start(service, "u-auto-1", "同名项目")
    second = _start(service, "u-auto-2", "同名项目")
    duplicate = _start(service, "u-auto-1", "同名项目")

    assert first.started is True
    assert second.started is True
    assert duplicate.started is False
    assert service.stop_auto_write("u-auto-1", "同名项目") is True
    first.entry.thread.join(timeout=2)
    assert first.entry.done is True
    assert service.is_auto_write_running("u-auto-2", "同名项目") is True

    assert service.cancel_auto_write_background("u-auto-2", "同名项目", wait_timeout=2) is True
    assert second.entry.done is True


def test_auto_write_completed_task_can_restart_and_replay_progress(monkeypatch) -> None:
    from agents import auto_write_service as service

    async def fake_stream(**kwargs):
        yield 'data: {"status":"started"}\n\n'
        yield 'data: {"status":"complete"}\n\n'

    monkeypatch.setattr("agents.routes.auto_write.generate_script_stream", fake_stream)

    first = _start(service, "u-auto-3", "可重启项目")
    first.entry.thread.join(timeout=2)
    assert first.entry.done is True

    async def collect():
        return [event async for event in service.observe_auto_write_progress("u-auto-3", "可重启项目")]

    replayed = asyncio.run(collect())
    payloads = [
        json.loads(next(line[5:].strip() for line in event.splitlines() if line.startswith("data:")))
        for event in replayed
    ]
    assert [item["status"] for item in payloads] == ["started", "complete"]
    assert [item["streamSeq"] for item in payloads] == [1, 2]

    restarted = _start(service, "u-auto-3", "可重启项目")
    restarted.entry.thread.join(timeout=2)
    assert restarted.started is True
    assert restarted.entry is not first.entry
