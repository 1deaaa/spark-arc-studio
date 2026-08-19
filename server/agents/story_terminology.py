"""创作模式相关的故事结构术语与数量提示。

内部工具和历史数据仍然使用 ``chapter`` / ``scene`` 命名。本模块只负责把
这些兼容字段解释成当前创作模式下的用户与模型可见术语，避免在各个 Agent
和路由中重复维护模式分支。

重要兼容边界：``chapter``/``scene`` 是旧协议中的字段、工具名和索引名，
不是用户界面的正式称谓。它们在剧本模式下对应“剧幕/场景”，在小说模式下
对应“分卷/章节”。旧名称可能造成语义混乱，但不能直接改名，否则历史请求、
文件名元数据和已保存的大纲无法解析。
"""

from __future__ import annotations

from typing import Any


def normalize_workspace_mode(value: Any) -> str:
    """将外部创作模式收敛为稳定的 ``script`` 或 ``novel``。"""
    return "novel" if str(value or "").strip().lower() == "novel" else "script"


def get_story_terminology(workspace_mode: Any = None) -> dict[str, str]:
    """返回当前模式的故事分组、正文单元和数量指导术语。

    ``chapter_count`` 与 ``scene_count_per_chapter`` 是历史兼容字段，不能
    直接按字段名理解为固定的“章节/场景”层级；调用方必须使用本函数返回
    的模式化术语。保留这些字段名是为了兼容已有请求、工具调用和历史数据。
    同理，``chapter``/``scene`` 角色值只表示旧协议角色，可能造成语义混乱，
    不应直接作为用户可见文案。
    """
    mode = normalize_workspace_mode(workspace_mode)
    if mode == "novel":
        return {
            "workspace_mode": mode,
            "mode_label": "小说模式",
            "group": "分卷",
            "unit": "章节",
            "group_count": "分卷数",
            "unit_count": "章节数",
            "density": "每卷章节数",
            "unit_body": "章节正文",
            "unit_length": "章节篇幅",
        }
    return {
        "workspace_mode": mode,
        "mode_label": "剧本模式",
        "group": "剧幕",
        "unit": "场景",
        "group_count": "剧幕数",
        "unit_count": "场景数",
        "density": "每幕场景数",
        "unit_body": "场景正文",
        "unit_length": "场景篇幅",
    }


def build_story_structure_note(workspace_mode: Any = None) -> str:
    """生成可直接注入 Agent 上下文的结构说明。

    这里集中解释物理目录和历史字段，供共享读取工具、上下文提供器等复用。
    这样模型不会把 ``chapter_index``/``scene_index`` 或文件名排序误认为用户
    可见的文件夹、文件称谓。
    """
    terms = get_story_terminology(workspace_mode)
    return (
        f"【故事结构】当前为{terms['mode_label']}：story_group 是“{terms['group']}”文件夹，"
        f"story_unit 是“{terms['unit']}”正文文件。chapter/scene、chapter_index/scene_index "
        "以及 chapter_name/chapter_path、scene_name/scene_path/work_name 等名称属于历史兼容协议，"
        "可能造成语义混乱；它们不能按字面推断用户称谓，也不能为了改显示名称而重命名。"
        "正文顺序只认系统写入的 chap、scene、order 数字元数据和 stories_order.json，"
        "不按中文标题或 Unicode 文件名排序。"
    )


def build_story_structure_quantity_guidance(
    workspace_mode: Any = None,
    group_count: Any = "不限",
    unit_count: Any = "不限",
) -> str:
    """构建大纲任务的模式化数量指导，并解释历史兼容参数语义。"""
    terms = get_story_terminology(workspace_mode)
    group_value = str(group_count if group_count is not None else "不限")
    unit_value = str(unit_count if unit_count is not None else "不限")
    group_suffix = "" if group_value.strip() in {"", "不限"} else " 个"
    unit_suffix = "" if unit_value.strip() in {"", "不限"} else " 个"
    return (
        f"当前为{terms['mode_label']}：故事文件夹/故事分组称为“{terms['group']}”，"
        f"单个正文文件称为“{terms['unit']}”。本轮目标约 {group_value}{group_suffix}{terms['group']}，"
        f"{terms['density']}参考约 {unit_value}{unit_suffix}。"
        f"内部兼容参数 chapter_count 表示{terms['group_count']}，"
        f"scene_count_per_chapter 表示{terms['density']}；这两个字段名属于历史兼容命名，"
        "可能造成语义混乱，不能按字面把它们理解成固定的章节或场景层级。"
        f"数量只是软目标，应按{terms['group']}与{terms['unit']}的叙事功能、信息密度和节奏弹性安排，"
        "不得为了凑数硬拆、硬合或省略。"
    )
