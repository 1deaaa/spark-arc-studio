"""
平台面板 Mixin — 平台列表、选择、删除、改名、排序、设默认
"""
import tkinter as tk
from tkinter import messagebox

from llm.llm_mgr.utils import normalize_base_url


class PlatformPanelMixin:
    """平台管理功能 Mixin，需与 LLMConfigGUI 混入使用。"""

    # ------------------------------------------------------------------ #
    #  内部工具                                                             #
    # ------------------------------------------------------------------ #

    def _refresh_platform_combo(self, selected_platform_name=None):
        """刷新平台下拉框内容（仅显示未删除的平台）。"""
        self.platform_display_to_key = {}
        self.platform_keys_in_order = []
        platform_names = list(self.current_config.keys())

        for p_name in platform_names:
            self.platform_display_to_key[p_name] = p_name
            self.platform_keys_in_order.append(p_name)

        self.platform_combo["values"] = platform_names

        if selected_platform_name and selected_platform_name in self.current_config:
            self.platform_var.set(selected_platform_name)
        elif platform_names:
            self.platform_var.set(platform_names[0])

    def _resolve_platform_name(self, platform_value=None):
        """将下拉框显示值解析为实际平台 key。"""
        if platform_value is None:
            platform_value = self.platform_var.get()
        if not platform_value:
            return None
        # 先尝试直接匹配（可能是 key 本身）
        if platform_value in self.current_config:
            return platform_value
        # 再尝试通过显示名称映射
        return self.platform_display_to_key.get(platform_value)

    # ------------------------------------------------------------------ #
    #  事件处理                                                             #
    # ------------------------------------------------------------------ #

    def on_platform_selected(self, event=None):
        """平台选择变化时更新模型列表。"""
        platform_name = self._resolve_platform_name()
        if not platform_name or platform_name not in self.current_config:
            return

        self.last_selected_platform_name = platform_name
        platform_cfg = self.current_config[platform_name]
        self.model_listbox.delete(0, tk.END)

        # 立即清空探测结果列表
        self.probe_listbox.delete(0, tk.END)

        # 填充 base_url
        base_url = platform_cfg.get("base_url", "")
        self.base_url_entry.config(state='normal')
        self.base_url_entry.delete(0, tk.END)
        self.base_url_entry.insert(0, base_url)
        self.base_url_entry.config(state='readonly')

        self.platform_url_entry.delete(0, tk.END)
        self.platform_url_entry.insert(0, base_url)

        # 处理 api_key
        self.api_key_entry.delete(0, tk.END)
        api_key = platform_cfg.get("api_key", "")
        if api_key:
            self.api_key_entry.insert(0, api_key)

        # 尝试从缓存恢复探测结果
        cache_key = self._get_probe_cache_key(platform_name, base_url, self.api_key_entry.get().strip())
        if cache_key and cache_key in self.probe_models_cache:
            for model_id in self.probe_models_cache[cache_key]:
                self.probe_listbox.insert(tk.END, model_id)

        # 显示模型列表（不含已删除的模型）
        models = platform_cfg.get("models", {})
        for display_name, model_config in models.items():
            self.model_listbox.insert(tk.END, self._format_model_list_item(display_name, model_config))

        # 异步执行一次模型探测
        self.probe_models(auto_start=True)

    def rename_platform(self, event=None):
        """给当前选中的平台改名（调用后端 admin_update_sys_platform）。"""
        if not self.last_selected_platform_name:
            return

        new_name = self._resolve_platform_name()
        if new_name is None:
            new_name = self.platform_var.get().strip()
        old_name = self.last_selected_platform_name

        if not new_name or new_name == old_name:
            return

        if new_name in self.current_config:
            self.platform_var.set(old_name)
            return

        try:
            db_id = self.current_config[old_name].get("_db_id")
            if not db_id:
                raise ValueError("无法获取平台数据库 ID")
            base_url = self.current_config[old_name].get("base_url", "")
            self.ai_manager.admin_update_sys_platform(db_id, new_name, base_url)

            # 更新内存配置
            new_config = {}
            for k, v in self.current_config.items():
                if k == old_name:
                    new_config[new_name] = v
                else:
                    new_config[k] = v
            self.current_config = new_config
            self.last_selected_platform_name = new_name

            self._refresh_platform_combo(selected_platform_name=new_name)
            self._invalidate_probe_cache(old_name)
            self._invalidate_probe_cache(new_name)
            self.log(f"✓ 平台已改名: {old_name} → {new_name}", tag="success")
        except Exception as e:
            self.log(f"✗ 改名失败: {e}")
            # 恢复旧名称
            self.platform_var.set(old_name)

    # ------------------------------------------------------------------ #
    #  CRUD 操作                                                            #
    # ------------------------------------------------------------------ #

    def add_platform(self):
        """添加新平台（调用后端 admin_add_sys_platform）。"""
        dialog = tk.Toplevel(self.root)
        dialog.title("添加新平台")
        dialog.geometry("450x250")
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text="平台名称:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=10)
        from tkinter import ttk
        name_entry = ttk.Entry(dialog, width=40)
        name_entry.grid(row=0, column=1, padx=10, pady=10)

        tk.Label(dialog, text="Base URL:").grid(row=1, column=0, sticky=tk.W, padx=10, pady=10)
        url_entry = ttk.Entry(dialog, width=40)
        url_entry.grid(row=1, column=1, padx=10, pady=10)
        url_entry.insert(0, "https://api.example.com/v1")

        tk.Label(dialog, text="API Key (可选):").grid(row=2, column=0, sticky=tk.W, padx=10, pady=10)
        key_entry = ttk.Entry(dialog, width=40)
        key_entry.grid(row=2, column=1, padx=10, pady=10)

        def do_add():
            name = name_entry.get().strip()
            url = url_entry.get().strip()
            key = key_entry.get().strip()

            if not name or not url:
                from tkinter import messagebox as mb
                mb.showerror("错误", "平台名称和 Base URL 不能为空", parent=dialog)
                return
            if not (url.startswith("http://") or url.startswith("https://")):
                from tkinter import messagebox as mb
                mb.showerror("错误", "URL 必须以 http:// 或 https:// 开头", parent=dialog)
                return

            url = normalize_base_url(url)

            if name in self.current_config:
                from tkinter import messagebox as mb
                mb.showerror("错误", f"平台名称 '{name}' 已存在", parent=dialog)
                return

            try:
                created = self.ai_manager.admin_add_sys_platform(name, url, key or None)
                p_id = created.id if hasattr(created, 'id') else None

                self.current_config[name] = {
                    "base_url": url,
                    "api_key": key or "",
                    "models": {},
                    "_db_id": p_id,
                }

                self._refresh_platform_combo(selected_platform_name=name)
                self.on_platform_selected()
                self.log(f"✓ 平台 '{name}' 已添加", tag="success")
                dialog.destroy()
            except Exception as e:
                self.log(f"✗ 添加平台失败: {e}")
                from tkinter import messagebox as mb
                mb.showerror("错误", f"添加平台失败: {e}", parent=dialog)

        btn_frame = ttk.Frame(dialog)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="确定", command=do_add).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")

    def delete_platform(self):
        """删除选中的平台（实质为禁用，从列表中消失）。"""
        platform_name = self._resolve_platform_name()
        if not platform_name or platform_name not in self.current_config:
            if self.last_selected_platform_name:
                platform_name = self.last_selected_platform_name
            else:
                messagebox.showwarning("警告", "请先选择一个有效的平台")
                return

        if not messagebox.askyesno("确认删除", f"确定要删除平台 '{platform_name}' 吗？\n该平台及其模型将从列表中移除。"):
            return

        try:
            db_id = self.current_config[platform_name].get("_db_id")
            if not db_id:
                raise ValueError("无法获取平台数据库 ID")
            self.ai_manager.disable_platform(db_id, admin_mode=True)
            self._invalidate_probe_cache(platform_name)
            self.load_config_from_db()
            self.log(f"✓ 平台 '{platform_name}' 已删除", tag="success")
        except Exception as e:
            self.log(f"✗ 删除平台失败: {e}")
            messagebox.showerror("错误", f"删除平台失败: {e}")

    def save_platform_url(self):
        """保存平台的 base_url（调用后端 admin_update_sys_platform）。"""
        platform_name = self._resolve_platform_name()
        if not platform_name or platform_name not in self.current_config:
            if self.last_selected_platform_name:
                platform_name = self.last_selected_platform_name
            else:
                messagebox.showwarning("警告", "请先选择一个有效的平台")
                return

        new_url = self.platform_url_entry.get().strip()
        if not new_url:
            messagebox.showerror("错误", "请填写平台 URL")
            return
        if not (new_url.startswith("http://") or new_url.startswith("https://")):
            messagebox.showerror("错误", "URL 必须以 http:// 或 https:// 开头")
            return

        new_url = normalize_base_url(new_url)

        try:
            db_id = self.current_config[platform_name].get("_db_id")
            if not db_id:
                raise ValueError("无法获取平台数据库 ID")
            self.ai_manager.admin_update_sys_platform(db_id, platform_name, new_url)
            self.current_config[platform_name]["base_url"] = new_url
            self._invalidate_probe_cache(platform_name)
            self.on_platform_selected()
            self.log(f"✓ 平台 '{platform_name}' 的 URL 已更新", tag="success")
        except Exception as e:
            self.log(f"✗ 保存失败: {e}")
            messagebox.showerror("错误", f"保存平台 URL 失败: {e}")

    def set_as_default(self):
        """将选中的平台设为默认（调用后端 admin_set_sys_platform_default）。"""
        platform_name = self._resolve_platform_name()
        if not platform_name:
            messagebox.showwarning("警告", "请先选择一个平台")
            return

        if not messagebox.askyesno(
            "确认",
            f"确定要将 '{platform_name}' 设为默认平台吗？\n它将被放到第一位，在用户没有选中模型的时候优先使用。"
        ):
            return

        try:
            db_id = self.current_config[platform_name].get("_db_id")
            if not db_id:
                raise ValueError("无法获取平台数据库 ID")
            self.ai_manager.admin_set_sys_platform_default(db_id)
            self.load_config_from_db()
            self.log(f"✓ 已将 '{platform_name}' 设为默认平台", tag="success")
        except Exception as e:
            self.log(f"✗ 设置默认平台失败: {e}")
            messagebox.showerror("错误", f"设置默认平台失败: {e}")

