from __future__ import annotations

import asyncio
import threading
from typing import Any, Dict

from core.request_context import current_project_name, current_user_id


def start_auto_write_background(
    *,
    user_id: str,
    project_name: str,
    outline: Dict[str, Any],
    mode: str,
    start_chapter_index: int,
    start_scene_index: int,
    export_format: str,
    context_strategy: str = "accumulate",
    auto_review: bool = False,
    from_director: bool = True,
) -> threading.Thread:
    from agents.routes.auto_write import generate_script_stream

    def _run_auto_write() -> None:
        current_user_id.set(str(user_id))
        current_project_name.set(project_name)

        async def _drain() -> None:
            async for _ in generate_script_stream(
                user_id=str(user_id),
                project_name=project_name,
                outline=outline,
                request=None,
                mode=mode,
                start_chapter_index=start_chapter_index,
                start_scene_index=start_scene_index,
                context_strategy=context_strategy,
                export_format=export_format,
                auto_review=auto_review,
                from_director=from_director,
            ):
                pass

        asyncio.run(_drain())

    thread = threading.Thread(
        target=_run_auto_write,
        daemon=True,
        name=f"auto_write_{project_name}",
    )
    thread.start()
    return thread


def load_auto_write_status(user_id: str, project_name: str) -> Dict[str, Any]:
    from agents.routes.auto_write_state import load_auto_write_state

    return load_auto_write_state(user_id, project_name)
