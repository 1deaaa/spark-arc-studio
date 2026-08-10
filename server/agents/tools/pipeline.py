from __future__ import annotations

from langchain.tools import tool
from pydantic import BaseModel


PIPELINE_COMPLETION_TOOL_NAME = "complete_pipeline_step"
PIPELINE_COMPLETION_MARKER = "__PIPELINE_STEP_COMPLETE__"


class CompletePipelineStepInput(BaseModel):
    """流水线完成标记不接受模型生成的总结参数。"""


@tool(args_schema=CompletePipelineStepInput)
def complete_pipeline_step() -> str:
    """仅用于 silent_continue：全部必要落盘完成后，作为最终工具批次的最后一个调用。"""
    return PIPELINE_COMPLETION_MARKER

