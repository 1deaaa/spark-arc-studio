"""
Tags API - 标签目录与用户自定义标签

统一标签数据源，供前端与 Agent 使用。
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import os
import json

from core.auth import get_current_user
from core.utils import USERDATA_ROOT
from core.project_settings import get_project_story_tags, set_project_story_tags


tags_router = APIRouter()


# 预置标签（统一数据源）
PRESET_TAGS = {
    "styles": [
        "治愈", "致郁", "悬疑", "恐怖", "奇幻", "科幻", "浪漫", "热血", "喜剧", "悲剧",
        "正剧", "史诗", "讽刺", "哥特", "爽文", "甜宠", "虐恋", "沙雕", "群像", "极简"
    ],
    "genres": [
        "校园", "都市", "乡村", "日常", "冒险", "推理", "战争", "宫廷", "江湖", "职场",
        "仙侠", "玄幻", "魔法", "历史", "民国", "刑侦", "医疗", "商战", "娱乐圈", "电竞"
    ],
    "tones": [
        "现实主义", "魔幻现实主义", "梦核", "怪核", "旧核", "蒸汽波", "网络抽象", "青春伤痛", "黑色幽默",
        "意识流", "荒诞", "唯美", "暗黑", "虚无主义", "迷幻", "故障艺术", "童话", "硬汉"
    ],
    "worldviews": [
        "现实", "架空", "阈限空间", "规则怪谈", "后室", "模拟宇宙", "时间循环", "平行时空", "伪人", "基金会",
        "穿越", "重生", "系统", "无限流", "末世", "废土", "赛博朋克", "克苏鲁", "西幻", "修真", "星际", "异能"
    ]
}


class CustomTagsRequest(BaseModel):
    styles: Optional[List[str]] = []
    genres: Optional[List[str]] = []
    tones: Optional[List[str]] = []
    worldviews: Optional[List[str]] = []


def _get_user_custom_tags_path(user_id: str) -> str:
    """获取用户自定义标签文件路径"""
    return os.path.join(USERDATA_ROOT, f"uid_{user_id}", "custom_tags.json")


@tags_router.get('/api/user/custom-tags')
async def get_custom_tags(user: dict = Depends(get_current_user)):
    """获取用户自定义标签"""
    user_id = str(user['user_id'])
    tags_file = _get_user_custom_tags_path(user_id)

    if os.path.exists(tags_file):
        try:
            with open(tags_file, 'r', encoding='utf-8') as f:
                tags = json.load(f)
            return {'success': True, 'tags': tags}
        except Exception as e:
            print(f"Error loading custom tags: {e}")
            return {'success': True, 'tags': {'styles': [], 'genres': [], 'tones': [], 'worldviews': []}}

    return {'success': True, 'tags': {'styles': [], 'genres': [], 'tones': [], 'worldviews': []}}


@tags_router.post('/api/user/custom-tags')
async def save_custom_tags(data: CustomTagsRequest, user: dict = Depends(get_current_user)):
    """保存用户自定义标签"""
    user_id = str(user['user_id'])
    tags_file = _get_user_custom_tags_path(user_id)

    user_dir = os.path.dirname(tags_file)
    os.makedirs(user_dir, exist_ok=True)

    tags = {
        'styles': data.styles or [],
        'genres': data.genres or [],
        'tones': data.tones or [],
        'worldviews': data.worldviews or []
    }

    try:
        with open(tags_file, 'w', encoding='utf-8') as f:
            json.dump(tags, f, ensure_ascii=False, indent=2)
        return {'success': True, 'tags': tags}
    except Exception as e:
        print(f"Error saving custom tags: {e}")
        return JSONResponse(status_code=500, content={'success': False, 'error': str(e)})


@tags_router.get('/api/tags/catalog')
async def get_tags_catalog(
    include_custom: bool = True,
    user: dict = Depends(get_current_user)
):
    """
    获取标签目录（预置 + 自定义）。
    - include_custom=true 时会合并当前用户的自定义标签
    """
    presets = PRESET_TAGS
    custom = {"styles": [], "genres": [], "tones": [], "worldviews": []}

    if include_custom:
        user_id = str(user['user_id'])
        tags_file = _get_user_custom_tags_path(user_id)
        if os.path.exists(tags_file):
            try:
                with open(tags_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    custom = {
                        "styles": data.get("styles", []) or [],
                        "genres": data.get("genres", []) or [],
                        "tones": data.get("tones", []) or [],
                        "worldviews": data.get("worldviews", []) or []
                    }
            except Exception as e:
                print(f"Error loading custom tags for catalog: {e}")

    merged = {
        "styles": presets["styles"] + custom["styles"],
        "genres": presets["genres"] + custom["genres"],
        "tones": presets["tones"] + custom["tones"],
        "worldviews": presets["worldviews"] + custom["worldviews"]
    }

    return {
        "success": True,
        "presets": presets,
        "custom": custom,
        "all": merged
    }


# ==================== 项目级故事主题参数（Story Tags）====================


class ProjectStoryTagsRequest(BaseModel):
    """项目级故事主题参数请求体"""
    projectName: str
    workspaceMode: Optional[str] = None
    style: Optional[str] = None
    genres: Optional[List[str]] = None
    tones: Optional[List[str]] = None
    worldviews: Optional[List[str]] = None
    pov: Optional[str] = None
    lengthHint: Optional[str] = None
    activeInspirationId: Optional[str] = None


@tags_router.get('/api/project/story-tags')
async def get_project_story_tags_api(
    projectName: str,
    user: dict = Depends(get_current_user)
):
    """
    读取项目级故事主题参数（风格/题材/基调/世界观/人称/篇幅）。
    
    这些参数是"项目宪法"，贯穿整个创作周期，所有 Agent 通过 context_provider 统一读取。
    """
    user_id = str(user['user_id'])
    try:
        tags = get_project_story_tags(user_id, projectName)
        return {
            "success": True,
            "tags": tags
        }
    except Exception as e:
        print(f"Error loading project story tags: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@tags_router.post('/api/project/story-tags')
async def set_project_story_tags_api(
    data: ProjectStoryTagsRequest,
    user: dict = Depends(get_current_user)
):
    """
    设置项目级故事主题参数（部分更新，仅覆盖传入的字段）。
    
    这些参数是"项目宪法"，贯穿整个创作周期，所有 Agent 通过 context_provider 统一读取。
    """
    user_id = str(user['user_id'])
    try:
        tags = set_project_story_tags(
            user_id=user_id,
            project_name=data.projectName,
            style=data.style,
            genres=data.genres,
            tones=data.tones,
            worldviews=data.worldviews,
            pov=data.pov,
            length_hint=data.lengthHint,
            active_inspiration_id=data.activeInspirationId
        )
        return {
            "success": True,
            "tags": tags
        }
    except Exception as e:
        print(f"Error saving project story tags: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )
