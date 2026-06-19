"""故事记忆收口层。

本包先提供轻量级项目状态文件，作为 Scriptwriter 写前任务包和写后状态回写的统一入口。
后续如果要接数据库或重型 GraphRAG，也应继续从这里扩展，而不是散落在路由或 Agent 内部。
"""

from .facade import StoryMemoryFacade
from .jobs import (
    enqueue_scene_memory_write,
    enqueue_story_content_memory_write,
    enqueue_story_file_memory_write,
)

__all__ = [
    "StoryMemoryFacade",
    "enqueue_scene_memory_write",
    "enqueue_story_content_memory_write",
    "enqueue_story_file_memory_write",
]
