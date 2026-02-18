"""
模型面板 Mixin — 模型列表、探测、筛选、拖拽排序、删除
"""
import threading
import tkinter as tk
from tkinter import messagebox

from llm.llm_mgr.utils import probe_platform_models


class ModelPanelMixin:
    """模型管理功能 Mixin，需与 LLMConfigGUI 混入使用。"""

    # ------------------------------------------------------------------ #
    #  内部工具                                                             #
    # ------------------------------------------------------------------ #



    def _get_probe_cache_key(self, platform_name, base_url, api_key):
        """生成探测缓存 key。"""
        if not base_url:
            return None
        return f"{platform_name}|{base_url}|{api_key[:8] if api_key else ''}"

    def _invalidate_probe_cache(self, platform_name=None):
        """清除探测缓存。"""
        if platform_name is None:
            self.probe_models_cache.clear()
        else:
            keys_to_del = [k for k in self.probe_models_cache if k.startswith(f"{platform_name}|")]
            for k in keys_to_del:
                del self.probe_models_cache[k]

    def _format_model_list_item(self, display_name: str, model_config) -> str:
        """格式化模型列表项显示文本。"""
        if isinstance(model_config, str):
            model_id = model_config
            is_embedding = False
        else:
            model_id = model_config.get("model_name", "")
            is_embedding = bool(model_config.get("is_embedding"))

        tag = " [EMB]" if is_embedding else ""
        return f"{display_name}{tag} → {model_id}"

    def _extract_display_name(self, item_text: str) -> str:
        """从列表项文本中提取显示名称。"""
        display_part = item_text.split(" → ")[0]
        if display_part.endswith(" [EMB]"):
            display_part = display_part[:-6]
        return display_part

    def _parse_extra_body(self, text):
        """解析 Extra Body JSON 字符串（委托给 utils.parse_extra_body 统一处理）。

        支持 Python 风格注释、True/False/None、自动补全外层 {}、赋值前缀剥离。
        """
        from llm.llm_mgr.utils import parse_extra_body
        return parse_extra_body(text)

    # ------------------------------------------------------------------ #
    #  探测功能                                                             #
    # ------------------------------------------------------------------ #

    def probe_models(self, auto_start=False):
        """探测平台可用模型。"""
        platform_name = self._resolve_platform_name()
        base_url = self.base_url_entry.get().strip()
        api_key = self.api_key_entry.get().strip()

        if not base_url:
            if not auto_start:
                messagebox.showwarning("警告", "请先选择平台（Base URL 将自动填充）")
            return

        cache_key = self._get_probe_cache_key(platform_name, base_url, api_key)
        if cache_key and cache_key in self.probe_models_cache and self.probe_models_cache[cache_key]:
            self.log(f"使用缓存的探测结果 ({platform_name})")
            self.probe_listbox.delete(0, tk.END)
            for model_id in self.probe_models_cache[cache_key]:
                self.probe_listbox.insert(tk.END, model_id)
            return

        if not api_key or not api_key.strip():
            if not auto_start:
                messagebox.showerror("错误", "请在 API Key 输入框中填写有效的密钥")
            self.log("⚠ API Key 未填写，跳过自动探测。")
            return

        self.log(f"正在探测 {base_url} ...")
        self.probe_listbox.delete(0, tk.END)

        def do_probe():
            try:
                models = probe_platform_models(base_url, api_key, raise_on_error=True)
                self.root.after(0, lambda res=models: self.show_probe_results(res))
            except Exception as e:
                self.root.after(0, lambda err=str(e): self.show_probe_error(err))

        threading.Thread(target=do_probe, daemon=True).start()

    def show_probe_results(self, models):
        """显示探测结果。"""
        if not models:
            self.log("✗ 未探测到任何模型")
            return

        platform_name = self._resolve_platform_name()
        model_ids = [model.get('id', '') for model in models]
        cache_key = self._get_probe_cache_key(
            platform_name,
            self.base_url_entry.get().strip(),
            self.api_key_entry.get().strip()
        )
        if cache_key:
            self.probe_models_cache[cache_key] = model_ids

        self.probe_listbox.delete(0, tk.END)
        for model_id in model_ids:
            self.probe_listbox.insert(tk.END, model_id)

        self.log(f"✓ 探测到 {len(models)} 个模型", tag="success")

    def show_probe_error(self, error_msg):
        """显示探测错误。"""
        self.log(f"✗ 探测失败: {error_msg}")
        messagebox.showerror("探测失败", error_msg)

    def on_filter_change(self, event=None):
        """筛选关键字变化时更新列表。"""
        platform_name = self._resolve_platform_name()
        keyword = self.filter_entry.get().strip().lower()

        self.probe_listbox.delete(0, tk.END)

        cache_key = self._get_probe_cache_key(
            platform_name,
            self.base_url_entry.get().strip(),
            self.api_key_entry.get().strip()
        )
        cached_models = self.probe_models_cache.get(cache_key, [])

        if not keyword:
            for model_id in cached_models:
                self.probe_listbox.insert(tk.END, model_id)
        else:
            filtered = [m for m in cached_models if keyword in m.lower()]
            for model_id in filtered:
                self.probe_listbox.insert(tk.END, model_id)
            if filtered:
                self.log(f"筛选结果: {len(filtered)} 个模型匹配 '{keyword}'")
            else:
                self.log(f"筛选结果: 没有模型匹配 '{keyword}'")

    def clear_filter(self):
        """清除筛选。"""
        self.filter_entry.delete(0, tk.END)
        self.on_filter_change()

    def use_custom_model_name(self):
        """使用筛选框中输入的自定义名称打开添加模型对话框。"""
        custom_model_id = self.filter_entry.get().strip()
        if not custom_model_id:
            messagebox.showwarning("警告", "请输入要使用的模型名称")
            return
        self.open_add_model_dialog(custom_model_id=custom_model_id)

    # ------------------------------------------------------------------ #
    #  拖拽排序                                                             #
    # ------------------------------------------------------------------ #

    def on_model_drag_start(self, event):
        """开始拖动模型。"""
        index = self.model_listbox.nearest(event.y)
        if index < 0:
            return
        self._drag_data = {"y": event.y, "index": index}

    def on_model_drag_motion(self, event):
        """拖动中。"""
        if not hasattr(self, '_drag_data'):
            return

        new_index = self.model_listbox.nearest(event.y)
        old_index = self._drag_data["index"]

        if new_index != old_index:
            text = self.model_listbox.get(old_index)
            self.model_listbox.delete(old_index)
            self.model_listbox.insert(new_index, text)
            self.model_listbox.selection_clear(0, tk.END)
            self.model_listbox.selection_set(new_index)
            self.model_listbox.activate(new_index)
            self._drag_data["index"] = new_index

    def on_model_drag_stop(self, event):
        """结束拖动。"""
        if not hasattr(self, '_drag_data'):
            return
        self.reorder_models()
        del self._drag_data

    def reorder_models(self):
        """根据列表框顺序更新数据库中的模型排序。"""
        platform_name = self._resolve_platform_name()
        if not platform_name or platform_name not in self.current_config:
            return

        current_models = self.current_config[platform_name].get("models", {})
        if not current_models:
            return

        db_id = self.current_config[platform_name].get("_db_id")
        if not db_id:
            return

        ordered_ids = []
        for i in range(self.model_listbox.size()):
            item_text = self.model_listbox.get(i)
            display_name = self._extract_display_name(item_text)
            model_cfg = current_models.get(display_name)
            if model_cfg and isinstance(model_cfg, dict):
                mid = model_cfg.get("_db_id")
                if mid:
                    ordered_ids.append(mid)

        if ordered_ids:
            try:
                self.ai_manager.admin_reorder_sys_models(db_id, ordered_ids)
            except Exception as e:
                self.log(f"✗ 模型排序失败: {e}")

    # ------------------------------------------------------------------ #
    #  CRUD 操作                                                            #
    # ------------------------------------------------------------------ #

    def delete_model(self):
        """删除选中的模型（实质为禁用，从列表中消失）。"""
        platform_name = self._resolve_platform_name()
        if not platform_name:
            return

        selection = self.model_listbox.curselection()
        if not selection:
            messagebox.showwarning("警告", "请先选择要删除的模型")
            return

        model_str = self.model_listbox.get(selection[0])
        display_name = self._extract_display_name(model_str)

        if not messagebox.askyesno("确认删除", f"确定要删除模型 '{display_name}' 吗？"):
            return

        try:
            model_cfg = self.current_config[platform_name].get("models", {}).get(display_name)
            if isinstance(model_cfg, dict) and model_cfg.get("_db_id"):
                self.ai_manager.disable_model(model_cfg["_db_id"], admin_mode=True)
                self.load_config_from_db()
            else:
                raise ValueError("无法获取模型数据库 ID")
            self.log(f"✓ 已删除模型: {display_name}", tag="success")
        except Exception as e:
            self.log(f"✗ 删除模型失败: {e}")
            messagebox.showerror("错误", f"删除模型失败: {e}")

