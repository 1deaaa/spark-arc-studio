"""
向量索引服务包

提供基于 LanceDB 的项目级向量索引构建、查询、增量更新功能。
"""

from .service import VectorIndexService

__all__ = ["VectorIndexService"]
