"""
模型管理 Mixin
处理模型的增删改
"""

import json
from typing import Optional, Dict, Any

from ..models import LLMPlatform, LLModels
from ..config import SYSTEM_USER_ID


class ModelMixin:
    """模型管理功能"""

    def add_model(
        self,
        platform_id: int,
        model_name: str,
        display_name: str,
        user_id: str,
        extra_body: Optional[Dict[str, Any]] = None,
    ):
        self._ensure_mutable()
        if not (platform_id and model_name and display_name):
            raise ValueError("platform_id / model_name / display_name 必填")
        if user_id is None or user_id == SYSTEM_USER_ID:
            raise ValueError("为模型绑定真实 user_id")

        with self.Session() as session:
            plat = session.query(LLMPlatform).filter_by(id=platform_id, user_id=user_id, is_sys=0).first()
            if not plat:
                raise ValueError("平台不存在、无权限或为不可修改的系统平台")

            user_platforms = session.query(LLMPlatform).filter_by(user_id=user_id, is_sys=0).all()
            user_platform_ids = [p.id for p in user_platforms]
            existing_display = session.query(LLModels).filter(
                LLModels.platform_id.in_(user_platform_ids),
                LLModels.display_name == display_name
            ).first()
            if existing_display:
                existing_plat = session.query(LLMPlatform).filter_by(id=existing_display.platform_id).first()
                raise ValueError(f"模型显示名称 '{display_name}' 已存在于您的平台 '{existing_plat.name}'")
            
            if session.query(LLModels).filter_by(platform_id=plat.id, model_name=model_name).first():
                raise ValueError(f"模型ID '{model_name}' 已存在于该平台")
            
            extra_body_json = json.dumps(extra_body) if extra_body else None

            m = LLModels(
                platform_id=plat.id,
                model_name=model_name,
                display_name=display_name,
                extra_body=extra_body_json
            )
            session.add(m)
            session.commit()
            return m

    def delete_model(self, user_id: str, model_id: int):
        self._ensure_mutable()
        with self.Session() as session:
            model = session.query(LLModels).filter_by(id=model_id).first()
            if not model:
                raise ValueError("模型不存在")
            
            plat = session.query(LLMPlatform).filter_by(id=model.platform_id).first()
            if not plat or plat.is_sys or plat.user_id != user_id:
                raise ValueError("无权删除此模型（系统模型或他人模型）")
            
            session.delete(model)
            session.commit()
            return True

    def update_model(
        self,
        user_id: str,
        model_id: int,
        new_display_name: Optional[str] = None,
        new_extra_body: Optional[Dict[str, Any]] = None,
    ):
        self._ensure_mutable()
        with self.Session() as session:
            model = session.query(LLModels).filter_by(id=model_id).first()
            if not model:
                raise ValueError("模型不存在")
            
            plat = session.query(LLMPlatform).filter_by(id=model.platform_id).first()
            if not plat or plat.is_sys or plat.user_id != user_id:
                raise ValueError("无权修改此模型（系统模型或他人模型）")
            
            if new_display_name is not None:
                # 检查显示名称唯一性
                user_platforms = session.query(LLMPlatform).filter_by(user_id=user_id, is_sys=0).all()
                user_platform_ids = [p.id for p in user_platforms]
                existing = session.query(LLModels).filter(
                    LLModels.platform_id.in_(user_platform_ids),
                    LLModels.display_name == new_display_name,
                    LLModels.id != model_id
                ).first()
                if existing:
                    raise ValueError(f"显示名称 '{new_display_name}' 已被使用")
                model.display_name = new_display_name
            
            if new_extra_body is not None:
                model.extra_body = json.dumps(new_extra_body) if new_extra_body else None
            
            session.commit()
            return True
