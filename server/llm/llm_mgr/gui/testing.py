"""
模型测试 Mixin — 测试、Embedding 测试、测速
"""
import threading
import json as json_lib
import tkinter as tk
from tkinter import messagebox

from llm.llm_mgr.utils import (
    stream_speed_test,
    test_platform_embedding,
    test_platform_chat,
)


class TestingMixin:
    """模型测试功能 Mixin，需与 LLMConfigGUI 混入使用。"""

    def test_model(self):
        """测试选中的模型是否可用。"""
        platform_name = self._resolve_platform_name()
        if not platform_name:
            messagebox.showwarning("警告", "请先选择一个平台")
            return

        selection = self.model_listbox.curselection()
        if not selection:
            messagebox.showwarning("警告", "请在左侧选择要测试的模型")
            return

        model_str = self.model_listbox.get(selection[0])
        display_name = self._extract_display_name(model_str)

        models = self.current_config[platform_name].get("models", {})
        model_config = models.get(display_name)
        if not model_config:
            messagebox.showerror("错误", f"未找到模型 '{display_name}' 的配置")
            return

        if isinstance(model_config, str):
            model_id = model_config
            extra_body = None
            is_embedding = False
        else:
            model_id = model_config.get("model_name", "")
            extra_body = model_config.get("extra_body")
            is_embedding = bool(model_config.get("is_embedding"))

        if is_embedding:
            messagebox.showwarning("提示", "当前为 Embedding 模型，请使用『测试Embedding』按钮")
            return

        base_url = self.current_config[platform_name].get("base_url", "").strip()
        api_key = self.api_key_entry.get().strip()

        if not base_url:
            messagebox.showerror("错误", "当前平台缺少 Base URL，无法测试模型")
            return
        if not api_key:
            messagebox.showerror("错误", "请填写 API Key 以进行测试")
            return
        if not model_id:
            messagebox.showerror("错误", "模型配置缺少模型 ID")
            return

        self.log(f"正在测试模型: {display_name} ({model_id})...")

        def do_test():
            try:
                result = test_platform_chat(
                    base_url, api_key, model_id,
                    extra_body=extra_body,
                    return_json=True
                )
                self.root.after(0, lambda r=result: self.show_test_result(True, display_name, r))
            except Exception as exc:
                self.root.after(0, lambda err=str(exc): self.show_test_result(False, display_name, err))

        threading.Thread(target=do_test, daemon=True).start()

    def test_embedding(self):
        """测试选中的 Embedding 模型是否可用。"""
        platform_name = self._resolve_platform_name()
        if not platform_name:
            messagebox.showwarning("警告", "请先选择一个平台")
            return

        selection = self.model_listbox.curselection()
        if not selection:
            messagebox.showwarning("警告", "请在左侧选择要测试的模型")
            return

        model_str = self.model_listbox.get(selection[0])
        display_name = self._extract_display_name(model_str)

        models = self.current_config[platform_name].get("models", {})
        model_config = models.get(display_name)
        if not model_config:
            messagebox.showerror("错误", f"未找到模型 '{display_name}' 的配置")
            return

        if isinstance(model_config, str):
            model_id = model_config
            is_embedding = False
        else:
            model_id = model_config.get("model_name", "")
            is_embedding = bool(model_config.get("is_embedding"))

        if not is_embedding:
            messagebox.showwarning("提示", "当前模型不是 Embedding")
            return

        base_url = self.current_config[platform_name].get("base_url", "").strip()
        api_key = self.api_key_entry.get().strip()

        if not base_url:
            messagebox.showerror("错误", "当前平台缺少 Base URL，无法测试 Embedding")
            return
        if not api_key:
            messagebox.showerror("错误", "请填写 API Key 以进行测试")
            return
        if not model_id:
            messagebox.showerror("错误", "模型配置缺少模型 ID")
            return

        self.log(f"正在测试 Embedding: {display_name} ({model_id})...")

        def do_test():
            try:
                result = test_platform_embedding(base_url, api_key, model_id)
                self.root.after(0, lambda r=result: self.show_embedding_test_result(True, display_name, r))
            except Exception as exc:
                self.root.after(0, lambda err=str(exc): self.show_embedding_test_result(False, display_name, err))

        threading.Thread(target=do_test, daemon=True).start()

    def show_embedding_test_result(self, success, model_name, result):
        """在主线程中显示 Embedding 测试结果。"""
        if success:
            dims = None
            if isinstance(result, dict):
                dims = result.get("dims")
            msg = f"Embedding '{model_name}' 可用！"
            if dims:
                msg = f"Embedding '{model_name}' 可用！\n向量维度: {dims}"
            self.log(f"✓ Embedding '{model_name}' 测试成功", tag="success")
            messagebox.showinfo("测试成功", msg)
        else:
            self.log(f"✗ Embedding '{model_name}' 测试失败: {result}")
            messagebox.showerror("测试失败", f"Embedding '{model_name}' 测试失败。\n\n错误详情:\n{result}")

    def speed_test_model(self):
        """流式测速选中的模型。"""
        platform_name = self._resolve_platform_name()
        if not platform_name:
            messagebox.showwarning("警告", "请先选择一个平台")
            return

        selection = self.model_listbox.curselection()
        if not selection:
            messagebox.showwarning("警告", "请在左侧选择要测试的模型")
            return

        model_str = self.model_listbox.get(selection[0])
        display_name = self._extract_display_name(model_str)

        models = self.current_config[platform_name].get("models", {})
        model_config = models.get(display_name)
        if not model_config:
            return

        if isinstance(model_config, str):
            model_id = model_config
            extra_body = None
            is_embedding = False
        else:
            model_id = model_config.get("model_name", "")
            extra_body = model_config.get("extra_body")
            is_embedding = bool(model_config.get("is_embedding"))

        if is_embedding:
            messagebox.showwarning("提示", "Embedding 模型不支持测速")
            return

        base_url = self.current_config[platform_name].get("base_url", "").strip()
        api_key = self.api_key_entry.get().strip()

        if not base_url or not api_key:
            messagebox.showerror("错误", "缺少 URL 或 API Key")
            return

        self.log(f"开始测速模型: {display_name} (预计5秒)...")

        def do_speed_test():
            try:
                generator = stream_speed_test(base_url, api_key, model_id, extra_body=extra_body)
                for item in generator:
                    if "error" in item:
                        self.root.after(0, lambda m=item["error"]: self.log(f"✗ 测速出错: {m}"))
                        break
                    if item["type"] == "update":
                        msg = f"  进度: {item['elapsed']}s | 速度: {item['speed']:.1f} chars/s"
                        self.root.after(0, lambda m=msg: self.log(m))
                    elif item["type"] == "final":
                        ftl_str = f"{item['ftl']:.0f}ms" if item['ftl'] else "N/A"
                        res = (f"✓ 测速完成: {display_name}\n"
                               f"  平均速度: {item['speed']:.1f} chars/s\n"
                               f"  首次延迟: {ftl_str} (含推理时间)\n"
                               f"  总输出字符: {item['total_chars']}")
                        self.root.after(0, lambda r=res: self.log(r, tag="success"))
                        self.root.after(0, lambda r=res: messagebox.showinfo("测速结果", r))
            except Exception as e:
                self.root.after(0, lambda err=str(e): self.log(f"✗ 测速失败: {err}"))

        threading.Thread(target=do_speed_test, daemon=True).start()

    def show_test_result(self, success, model_name, result):
        """在主线程中显示测试结果。"""
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
            messagebox.showinfo(
                "测试成功",
                f"模型 '{model_name}' 可用！\n\n响应预览（部分模型可能会输出错误的身份信息，或出现空回复，属正常现象）:\n{content_preview}"
            )
        else:
            self.log(f"✗ 模型 '{model_name}' 测试失败: {result}")
            messagebox.showerror("测试失败", f"模型 '{model_name}' 测试失败。\n\n错误详情:\n{result}")
