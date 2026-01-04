"""
story/routes_story.py - 聚合路由

为保持向后兼容，此文件现在充当聚合路由，导入并包含拆分后的子路由。
原有的庞大逻辑已拆分至：
- routes_project.py: 项目管理
- routes_files.py: 文件操作
- routes_version.py: 版本控制
- routes_share.py: 分享与快照
- routes_blueprint.py: 蓝图与绑定
"""

from fastapi import APIRouter

# 导入拆分后的子路由
from .routes_project import project_router
from .routes_files import files_router
from .routes_version import version_router
from .routes_share import share_router
from .routes_blueprint import blueprint_router

# 创建主路由器
story_router = APIRouter()

# 注册所有子路由
story_router.include_router(project_router)
story_router.include_router(files_router)
story_router.include_router(version_router)
story_router.include_router(share_router)
story_router.include_router(blueprint_router)