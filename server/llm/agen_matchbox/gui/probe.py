"""
模型探测与测试 Mixin（适配 Flet 0.28.3）。
"""
from __future__ import annotations

import os
import sys
import threading
import json as json_lib
import flet as ft

if __package__ in (None, "", "gui"):
    _GUI_DIR = os.path.dirname(os.path.abspath(__file__))
    _PKG_DIR = os.path.dirname(_GUI_DIR)
    _PARENT_DIR = os.path.dirname(_PKG_DIR)
    if _PARENT_DIR not in sys.path:
        sys.path.insert(0, _PARENT_DIR)
    __package__ = f"{os.path.basename(_PKG_DIR)}.{os.path.basename(_GUI_DIR)}"

from ..utils import (
    stream_speed_test,
    test_platform_embedding,
    test_platform_chat,
)
from ..models import (
    MODALITY_EMBEDDING,
    MODALITY_TEXT,
    normalize_model_modalities,
)


class ProbeMixin:
    """模型探测与测试功能 Mixin，需与 LLMConfigGUI 混入使用。"""

    @staticmethod
    def _model_modalities_from_config(model_config):
        if isinstance(model_config, str):
            return normalize_model_modalities()
        return normalize_model_modalities(
            model_config.get("input_modalities"),
            model_config.get("output_modalities"),
        )

    def _get_selected_model_context(self, target_display_name: str | None = None):
        """获取当前选中的平台名、显示名及对应配置。"""
        platform_name = self._resolve_platform_name()
        if not platform_name:
            self.show_warning("警告", "请先选择一个平台")
            return None, None, None

        display_name = target_display_name or self._get_selected_model_display_name()
        if not display_name:
            self.show_warning("警告", "请在已配置模型列表中选择要测试的模型")
            return None, None, None

        models = self.current_config.get(platform_name, {}).get("models", {})
        model_config = models.get(display_name)
        if not model_config:
            self.show_error("错误", f"未找到模型 '{display_name}' 的配置")
            return None, None, None

        return platform_name, display_name, model_config

    def test_model(self, target_display_name: str | None = None):
        """测试选中的模型是否可用（对话能力）。"""
        platform_name, display_name, model_config = self._get_selected_model_context(target_display_name)
        if not platform_name:
            return

        if isinstance(model_config, str):
            model_id = model_config
            extra_body = None
        else:
            model_id = model_config.get("model_name", "")
            extra_body = model_config.get("extra_body")
        _, output_modalities = self._model_modalities_from_config(model_config)

        if MODALITY_TEXT not in output_modalities:
            self.show_warning("提示", "当前模型不支持文本对话测试")
            return

        base_url = self.current_config[platform_name].get("base_url", "").strip()
        api_key = (self.api_key_entry.value or "").strip()

        if not base_url:
            self.show_error("错误", "当前平台缺少 Base URL，无法测试模型")
            return
        if not api_key:
            self.show_error("错误", "请先填写并保存 API Key 以进行测试")
            return
        if not model_id:
            self.show_error("错误", "模型配置缺少模型 ID")
            return

        self.log(f"正在测试模型: {display_name} ({model_id})...")

        def do_test():
            try:
                result = test_platform_chat(
                    base_url,
                    api_key,
                    model_id,
                    extra_body=extra_body,
                    return_json=True,
                )
                self.show_test_result(True, display_name, result)
            except Exception as exc:
                self.show_test_result(False, display_name, str(exc))

        threading.Thread(target=do_test, daemon=True).start()

    def test_embedding(self, target_display_name: str | None = None):
        """测试选中的 Embedding 模型是否可用。"""
        platform_name, display_name, model_config = self._get_selected_model_context(target_display_name)
        if not platform_name:
            return

        if isinstance(model_config, str):
            model_id = model_config
        else:
            model_id = model_config.get("model_name", "")
        _, output_modalities = self._model_modalities_from_config(model_config)

        if MODALITY_EMBEDDING not in output_modalities:
            self.show_warning("提示", "当前模型未勾选向量（Embedding）能力")
            return

        base_url = self.current_config[platform_name].get("base_url", "").strip()
        api_key = (self.api_key_entry.value or "").strip()

        if not base_url:
            self.show_error("错误", "当前平台缺少 Base URL，无法测试 Embedding")
            return
        if not api_key:
            self.show_error("错误", "请先填写并保存 API Key 以进行测试")
            return
        if not model_id:
            self.show_error("错误", "模型配置缺少模型 ID")
            return

        self.log(f"正在测试 Embedding: {display_name} ({model_id})...")

        def do_test():
            try:
                result = test_platform_embedding(base_url, api_key, model_id)
                self.show_embedding_test_result(True, display_name, result)
            except Exception as exc:
                self.show_embedding_test_result(False, display_name, str(exc))

        threading.Thread(target=do_test, daemon=True).start()

    def speed_test_model(self, target_display_name: str | None = None):
        """流式测速选中的模型。"""
        platform_name, display_name, model_config = self._get_selected_model_context(target_display_name)
        if not platform_name:
            return

        if isinstance(model_config, str):
            model_id = model_config
            extra_body = None
        else:
            model_id = model_config.get("model_name", "")
            extra_body = model_config.get("extra_body")
        _, output_modalities = self._model_modalities_from_config(model_config)

        if MODALITY_TEXT not in output_modalities:
            self.show_warning("提示", "当前模型不支持文本测速")
            return

        base_url = self.current_config[platform_name].get("base_url", "").strip()
        api_key = (self.api_key_entry.value or "").strip()

        if not base_url or not api_key:
            self.show_error("错误", "缺少 URL 或 API Key")
            return

        self.log(f"开始测速模型: {display_name} (预计 5 秒)...")

        def do_speed_test():
            try:
                generator = stream_speed_test(base_url, api_key, model_id, extra_body=extra_body)
                for item in generator:
                    if "error" in item:
                        self.log(f"✗ 测速出错: {item['error']}", tag="error")
                        break
                    if item["type"] == "update":
                        msg = f"  进度: {item['elapsed']}s | 速度: {item['speed']:.1f} token/s"
                        self.log(msg)
                    elif item["type"] == "final":
                        ftl_str = f"{item['ftl']:.0f}ms" if item['ftl'] else "N/A"
                        res = (
                            f"✓ 测速完成: {display_name}\n"
                            f"  平均速度: {item['speed']:.1f} token/s\n"
                            f"  首次延迟: {ftl_str} (含推理时间)\n"
                            f"  总输出 token: {item['total_tokens']}"
                        )
                        self.log(res, tag="success")
                        self.show_info("测速结果", res)
            except Exception as e:
                self.log(f"✗ 测速失败: {e}", tag="error")
                self.show_error("测速失败", str(e))

        threading.Thread(target=do_speed_test, daemon=True).start()

    def show_test_result(self, success: bool, model_name: str, result):
        """显示模型测试结果。"""
        if success:
            content_preview = ""
            if isinstance(result, dict):
                choices = result.get("choices")
                if isinstance(choices, list) and choices:
                    message_block = choices[0].get("message", {})
                    content_preview = message_block.get("content", "") or "[响应体缺少消息内容]"
                log_payload = json_lib.dumps(result, ensure_ascii=False, indent=2)
            else:
                log_payload = str(result)
                content_preview = "[未知格式的响应]"

            if len(log_payload) > 800:
                log_payload = log_payload[:800] + "..."

            self.log(f"✓ 模型 '{model_name}' 测试成功!", tag="success")
            self.log(f"  响应: {log_payload}")
            self.show_info(
                "测试成功",
                f"模型 '{model_name}' 可用！\n\n响应预览:\n{content_preview}",
            )
        else:
            self.log(f"✗ 模型 '{model_name}' 测试失败: {result}", tag="error")
            self.show_error("测试失败", f"模型 '{model_name}' 测试失败。\n\n错误详情:\n{result}")

    def show_embedding_test_result(self, success: bool, model_name: str, result):
        """显示 Embedding 测试结果。"""
        if success:
            dims = None
            if isinstance(result, dict):
                dims = result.get("dims")
            msg = f"Embedding '{model_name}' 可用！"
            if dims:
                msg += f"\n向量维度: {dims}"
            self.log(f"✓ Embedding '{model_name}' 测试成功", tag="success")
            self.show_info("测试成功", msg)
        else:
            self.log(f"✗ Embedding '{model_name}' 测试失败: {result}", tag="error")
            self.show_error("测试失败", f"Embedding '{model_name}' 测试失败。\n\n错误详情:\n{result}")
