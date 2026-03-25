"""Story 包导出。

避免在包初始化阶段提前导入 [`story.routes_story`](server/story/routes_story.py:1)，
从而在诸如 [`story.file_naming`](server/story/file_naming.py:1) 被轻量导入时触发循环依赖。
"""

__all__ = ["story_router", "import_project_stories_to_db"]


def __getattr__(name):
    if name == "story_router":
        from .routes_story import story_router

        return story_router
    if name == "import_project_stories_to_db":
        from .importer import import_project_stories_to_db

        return import_project_stories_to_db
    raise AttributeError(name)
