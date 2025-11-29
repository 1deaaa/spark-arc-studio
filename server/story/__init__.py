from flask import Blueprint

story_bp = Blueprint('story_bp', __name__)

# 导入路由模块以确保装饰器执行注册
from .routes import routes_sample  # noqa: F401
from .routes import routes_files  # noqa: F401
from .routes import routes_projects  # noqa: F401
from .routes import routes_characters  # noqa: F401
from .routes import routes_blueprint  # noqa: F401
from .importer import import_project_stories_to_db

__all__ = [
    'story_bp',
    'import_project_stories_to_db',
]
