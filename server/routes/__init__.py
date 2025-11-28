"""
Routes Package - API 路由模块

所有 Flask Blueprint 路由都在这里注册
"""

from .bridge import bridge_bp
from .style import style_bp
from .structure import structure_bp
from .production import production_bp
from .outline import outline_bp
from .agent_usage import agent_usage_bp

__all__ = [
    'bridge_bp',
    'style_bp',
    'structure_bp',
    'production_bp',
    'outline_bp',
    'agent_usage_bp',
]
