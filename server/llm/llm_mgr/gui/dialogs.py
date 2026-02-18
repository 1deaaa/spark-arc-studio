"""
对话框 Mixin — 添加/编辑模型对话框、系统用途管理对话框
"""
import json as json_lib
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from llm.llm_mgr.config import reload_default_platform_configs


class DialogsMixin:
    """对话框功能 Mixin，需与 LLMConfigGUI 混入使用。"""

    def open_add_model_dialog(self, custom_model_id=None):
        """打开添加模型对话框。"""
        platform_name = self._resolve_platform_name()
        if not platform_name:
            messagebox.showwarning("警告", "请先选择一个平台")
            return

        if custom_model_id:
            selected_model_id = custom_model_id
        else:
            selected_model_id = ""
            selection = self.probe_listbox.curselection()
            if selection:
                selected_model_id = self.probe_listbox.get(selection[0])

        dialog = tk.Toplevel(self.root)
        dialog.title(f"添加模型到 {platform_name}")
        dialog.geometry("550x600")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="显示名称:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=10)
        display_name_entry = ttk.Entry(dialog, width=50)
        display_name_entry.grid(row=0, column=1, padx=10, pady=10, sticky=(tk.W, tk.E))
        if selected_model_id:
            display_name_entry.insert(0, selected_model_id)

        ttk.Label(dialog, text="模型ID:").grid(row=1, column=0, sticky=tk.W, padx=10, pady=10)
        model_id_entry = ttk.Entry(dialog, width=50)
        model_id_entry.grid(row=1, column=1, padx=10, pady=10, sticky=(tk.W, tk.E))
        if selected_model_id:
            model_id_entry.insert(0, selected_model_id)

        is_embedding_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(dialog, text="Embedding 模型", variable=is_embedding_var).grid(row=2, column=1, sticky=tk.W, padx=10)

        temperature_enabled_var = tk.BooleanVar(value=False)
        temperature_var = tk.DoubleVar(value=0.7)

        temp_row = ttk.Frame(dialog)
        temp_row.grid(row=3, column=1, padx=10, pady=(6, 0), sticky=(tk.W, tk.E))

        def on_temperature_toggle():
            enabled = bool(temperature_enabled_var.get())
            if enabled:
                messagebox.showwarning(
                    "Temperature 参数警告",
                    "务必了解该模型temperature基准值\n部分模型在温度设置错误时会直接报错\n如果你不清楚这样做的意义\n请不要动这个参数",
                    parent=dialog,
                )
                temperature_entry.config(state='normal')
            else:
                temperature_entry.config(state='disabled')

        ttk.Checkbutton(
            temp_row,
            text="启用 Temperature（默认关闭）",
            variable=temperature_enabled_var,
            command=on_temperature_toggle,
        ).pack(side=tk.LEFT)

        ttk.Label(dialog, text="Temperature: ").grid(row=3, column=0, sticky=tk.W, padx=10, pady=(6, 0))
        temperature_entry = ttk.Entry(dialog, width=18, textvariable=temperature_var)
        temperature_entry.grid(row=3, column=1, padx=(280, 10), pady=(6, 0), sticky=tk.W)
        temperature_entry.config(state='disabled')
        ttk.Label(dialog, text="范围 0.3 - 1.5", foreground="gray").grid(row=3, column=1, padx=(380, 10), pady=(6, 0), sticky=tk.W)

        ttk.Label(dialog, text="Extra Body (JSON):").grid(row=4, column=0, sticky=(tk.W, tk.N), padx=10, pady=10)
        extra_body_frame = ttk.Frame(dialog)
        extra_body_frame.grid(row=4, column=1, padx=10, pady=10, sticky=(tk.W, tk.E, tk.N, tk.S))
        extra_body_text = tk.Text(extra_body_frame, width=50, height=15)
        extra_body_text.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            extra_body_frame,
            text='示例1: {"thinkingBudget": 0}\n示例2: {"thinking": {"type": "disabled"}}\n示例3: {"top_k": 40}',
            foreground="gray",
            font=('TkDefaultFont', 8),
            justify=tk.LEFT
        ).pack(anchor=tk.W, pady=(5, 0))

        def do_add():
            display_name = display_name_entry.get().strip()
            model_id = model_id_entry.get().strip()

            if not display_name or not model_id:
                messagebox.showwarning("警告", "请填写显示名称和模型ID", parent=dialog)
                return

            if display_name in self.current_config[platform_name].get("models", {}):
                if not messagebox.askyesno("确认", f"显示名称 '{display_name}' 已存在，是否覆盖？", parent=dialog):
                    return

            extra_body_str = extra_body_text.get("1.0", tk.END)
            try:
                extra_body = self._parse_extra_body(extra_body_str)
            except ValueError as err:
                messagebox.showerror("错误", str(err), parent=dialog)
                return

            temperature_value = None
            if bool(temperature_enabled_var.get()):
                try:
                    temp_value = float(temperature_var.get())
                except (TypeError, ValueError):
                    messagebox.showerror("错误", "Temperature 必须是数字", parent=dialog)
                    return
                if temp_value < 0.3 or temp_value > 1.5:
                    messagebox.showerror("错误", "Temperature 必须在 0.3 到 1.5 之间", parent=dialog)
                    return
                temperature_value = temp_value

            is_embedding = bool(is_embedding_var.get())

            try:
                db_id = self.current_config[platform_name].get("_db_id")
                if not db_id:
                    raise ValueError("无法获取平台数据库 ID")

                # 调用后端增量同步方法
                model_cfg_payload = {
                    "display_name": display_name,
                    "model_name": model_id,
                    "is_embedding": is_embedding,
                    "extra_body": extra_body,
                    "temperature": temperature_value,
                }
                self.ai_manager.admin_sync_platform_models(db_id, [model_cfg_payload])

                # 重新从数据库加载以获取 _db_id
                self.load_config_from_db()
                self.log(f"✓ 模型 '{display_name}' 已添加", tag="success")
                dialog.destroy()
            except Exception as e:
                self.log(f"✗ 保存失败: {e}")
                messagebox.showerror("错误", f"添加模型失败: {e}", parent=dialog)

        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=5, column=0, columnspan=2, pady=20)
        ttk.Button(button_frame, text="添加", command=do_add, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消", command=dialog.destroy, width=15).pack(side=tk.LEFT, padx=5)

        dialog.columnconfigure(1, weight=1)
        dialog.rowconfigure(4, weight=1)
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")

    def edit_model(self):
        """编辑选中的模型（打开编辑对话框）。"""
        platform_name = self._resolve_platform_name()
        if not platform_name:
            return

        selection = self.model_listbox.curselection()
        if not selection:
            messagebox.showwarning("警告", "请先选择要编辑的模型")
            return

        model_str = self.model_listbox.get(selection[0])
        display_name = self._extract_display_name(model_str)

        models = self.current_config[platform_name].get("models", {})
        model_config = models.get(display_name)
        if not model_config:
            return

        if isinstance(model_config, str):
            model_id = model_config
            extra_body_dict = None
            is_embedding = False
            model_temperature = None
            model_disabled = False
        else:
            model_id = model_config.get("model_name", "")
            extra_body_dict = model_config.get("extra_body")
            is_embedding = bool(model_config.get("is_embedding"))
            model_temperature = model_config.get("temperature")
            model_disabled = bool(model_config.get("disabled"))

        if model_temperature is None and isinstance(extra_body_dict, dict) and "temperature" in extra_body_dict:
            try:
                model_temperature = float(extra_body_dict.get("temperature"))
            except (TypeError, ValueError):
                model_temperature = None
            extra_body_dict = dict(extra_body_dict)
            extra_body_dict.pop("temperature", None)

        dialog = tk.Toplevel(self.root)
        dialog.title(f"编辑模型: {display_name}")
        dialog.geometry("550x550")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="显示名称:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=10)
        display_name_entry = ttk.Entry(dialog, width=50)
        display_name_entry.grid(row=0, column=1, padx=10, pady=10, sticky=(tk.W, tk.E))
        display_name_entry.insert(0, display_name)

        ttk.Label(dialog, text="模型ID:").grid(row=1, column=0, sticky=tk.W, padx=10, pady=10)
        model_id_entry = ttk.Entry(dialog, width=50)
        model_id_entry.grid(row=1, column=1, padx=10, pady=10, sticky=(tk.W, tk.E))
        model_id_entry.insert(0, model_id)
        model_id_entry.config(state='readonly')

        is_embedding_var = tk.BooleanVar(value=is_embedding)
        ttk.Checkbutton(dialog, text="Embedding 模型", variable=is_embedding_var).grid(row=2, column=1, sticky=tk.W, padx=10)

        temperature_enabled_var = tk.BooleanVar(value=model_temperature is not None)
        temperature_var = tk.DoubleVar(value=model_temperature if model_temperature is not None else 0.7)

        temp_row = ttk.Frame(dialog)
        temp_row.grid(row=3, column=1, padx=10, pady=(6, 0), sticky=(tk.W, tk.E))

        def on_temperature_toggle():
            enabled = bool(temperature_enabled_var.get())
            if enabled:
                messagebox.showwarning(
                    "Temperature 参数警告",
                    "务必了解该模型temperature基准值\n如果你不清楚这样做的意义\n请不要动这个参数\n部分模型在温度设置错误时会直接报错",
                    parent=dialog,
                )
                temperature_entry.config(state='normal')
            else:
                temperature_entry.config(state='disabled')

        ttk.Checkbutton(
            temp_row,
            text="启用 Temperature（默认关闭）",
            variable=temperature_enabled_var,
            command=on_temperature_toggle,
        ).pack(side=tk.LEFT)

        ttk.Label(dialog, text="Temperature: ").grid(row=3, column=0, sticky=tk.W, padx=10, pady=(6, 0))
        temperature_entry = ttk.Entry(dialog, width=18, textvariable=temperature_var)
        temperature_entry.grid(row=3, column=1, padx=(280, 10), pady=(6, 0), sticky=tk.W)
        if not bool(temperature_enabled_var.get()):
            temperature_entry.config(state='disabled')
        ttk.Label(dialog, text="范围 0.3 - 1.5", foreground="gray").grid(row=3, column=1, padx=(380, 10), pady=(6, 0), sticky=tk.W)

        ttk.Label(dialog, text="Extra Body (JSON):").grid(row=4, column=0, sticky=(tk.W, tk.N), padx=10, pady=10)
        extra_body_frame = ttk.Frame(dialog)
        extra_body_frame.grid(row=4, column=1, padx=10, pady=10, sticky=(tk.W, tk.E, tk.N, tk.S))
        extra_body_text = tk.Text(extra_body_frame, width=50, height=15)
        extra_body_text.pack(fill=tk.BOTH, expand=True)
        if extra_body_dict:
            extra_body_text.insert("1.0", json_lib.dumps(extra_body_dict, indent=2, ensure_ascii=False))
        ttk.Label(
            extra_body_frame,
            text='示例1: {"thinkingBudget": 0}\n示例2: {"thinking": {"type": "disabled"}}\n示例3: {"top_k": 40}',
            foreground="gray",
            font=('TkDefaultFont', 8),
            justify=tk.LEFT
        ).pack(anchor=tk.W, pady=(5, 0))

        def do_update():
            new_display_name = display_name_entry.get().strip()
            new_model_id = model_id_entry.get().strip()

            if not new_display_name or not new_model_id:
                messagebox.showwarning("警告", "请填写显示名称和模型ID", parent=dialog)
                return

            if new_display_name != display_name and new_display_name in self.current_config[platform_name].get("models", {}):
                if not messagebox.askyesno("确认", f"显示名称 '{new_display_name}' 已存在，是否覆盖？", parent=dialog):
                    return
                return  # BUG-3 修复：删除多余 return 后这里只保留一个

            extra_body_str = extra_body_text.get("1.0", tk.END)
            try:
                extra_body = self._parse_extra_body(extra_body_str)
            except ValueError as err:
                messagebox.showerror("错误", str(err), parent=dialog)
                return

            temperature_value = None
            if bool(temperature_enabled_var.get()):
                try:
                    temp_value = float(temperature_var.get())
                except (TypeError, ValueError):
                    messagebox.showerror("错误", "Temperature 必须是数字", parent=dialog)
                    return
                if temp_value < 0.3 or temp_value > 1.5:
                    messagebox.showerror("错误", "Temperature 必须在 0.3 到 1.5 之间", parent=dialog)
                    return
                temperature_value = temp_value

            try:
                db_id = self.current_config[platform_name].get("_db_id")
                if not db_id:
                    raise ValueError("无法获取平台数据库 ID")

                model_db_id = model_config.get("_db_id") if isinstance(model_config, dict) else None
                if not model_db_id:
                    raise ValueError("无法获取模型数据库 ID")

                # 调用后端更新方法
                self.ai_manager.admin_update_sys_model(
                    model_id=model_db_id,
                    display_name=new_display_name,
                    extra_body=extra_body,
                    temperature=temperature_value,
                    is_embedding=bool(is_embedding_var.get()),
                )

                self.load_config_from_db()
                self.log(f"✓ 模型 '{new_display_name}' 已更新", tag="success")
                dialog.destroy()
            except Exception as e:
                self.log(f"✗ 保存失败: {e}")
                messagebox.showerror("错误", f"更新模型失败: {e}", parent=dialog)

        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=5, column=0, columnspan=2, pady=20)
        ttk.Button(button_frame, text="保存", command=do_update, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消", command=dialog.destroy, width=15).pack(side=tk.LEFT, padx=5)

        dialog.columnconfigure(1, weight=1)
        dialog.rowconfigure(4, weight=1)
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")

    def edit_system_model(self):
        """编辑系统用户 (-1) 的模型选择及用途管理。"""
        dialog = tk.Toplevel(self.root)
        dialog.title("系统模型与用途管理")
        dialog.geometry("800x500")
        dialog.transient(self.root)
        dialog.grab_set()

        system_user_id = "-1"

        def load_data():
            try:
                reload_default_platform_configs()
                self.ai_manager._sync_default_platforms()
                _all_models = self.ai_manager.get_platform_models(user_id=system_user_id)
                _usage_list = self.ai_manager.list_user_usage_selections(user_id=system_user_id)
                return _all_models, _usage_list
            except Exception as e:
                messagebox.showerror("错误", f"加载数据失败: {e}", parent=dialog)
                return [], []

        self.all_models, self.usage_list = load_data()

        platforms = sorted(list(set(m['platform_name'] for m in self.all_models)))
        models_by_platform = {p_name: [] for p_name in platforms}
        for model_info in self.all_models:
            models_by_platform[model_info['platform_name']].append((model_info['display_name'], model_info))

        paned = ttk.PanedWindow(dialog, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        left_frame = ttk.LabelFrame(paned, text="用途列表 (Usage Slots)", padding="5")
        paned.add(left_frame, weight=1)

        usage_listbox = tk.Listbox(left_frame, height=15)
        usage_scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=usage_listbox.yview)
        usage_listbox.configure(yscrollcommand=usage_scrollbar.set)
        usage_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        usage_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        right_frame = ttk.LabelFrame(paned, text="绑定模型配置", padding="10")
        paned.add(right_frame, weight=2)

        ttk.Label(right_frame, text="用途标识 (Key):").grid(row=0, column=0, sticky=tk.W, pady=5)
        key_label = ttk.Label(right_frame, text="-", font=("Consolas", 10, "bold"))
        key_label.grid(row=0, column=1, sticky=tk.W, pady=5)

        ttk.Label(right_frame, text="显示名称 (Label):").grid(row=1, column=0, sticky=tk.W, pady=5)
        label_label = ttk.Label(right_frame, text="-")
        label_label.grid(row=1, column=1, sticky=tk.W, pady=5)

        ttk.Separator(right_frame, orient=tk.HORIZONTAL).grid(row=2, column=0, columnspan=2, sticky="ew", pady=10)

        ttk.Label(right_frame, text="选择平台:").grid(row=3, column=0, sticky=tk.W, pady=5)
        platform_var = tk.StringVar()
        platform_combo = ttk.Combobox(right_frame, textvariable=platform_var, values=platforms, state='readonly')
        platform_combo.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=5)

        ttk.Label(right_frame, text="选择模型:").grid(row=4, column=0, sticky=tk.W, pady=5)
        model_var = tk.StringVar()
        model_combo = ttk.Combobox(right_frame, textvariable=model_var, state='readonly')
        model_combo.grid(row=4, column=1, sticky=(tk.W, tk.E), pady=5)

        current_usage_data = {}

        def refresh_list():
            usage_listbox.delete(0, tk.END)
            for u in self.usage_list:
                display = f"{u['usage_label']} ({u['usage_key']})"
                usage_listbox.insert(tk.END, display)

        def on_platform_change(event=None):
            selected_platform = platform_var.get()
            model_display_names = [m[0] for m in models_by_platform.get(selected_platform, [])]
            model_combo['values'] = model_display_names
            if model_var.get() not in model_display_names:
                model_var.set(model_display_names[0] if model_display_names else "")

        platform_combo.bind('<<ComboboxSelected>>', on_platform_change)

        def on_select(event):
            selection = usage_listbox.curselection()
            if not selection:
                return
            idx = selection[0]
            usage = self.usage_list[idx]
            current_usage_data.clear()
            current_usage_data.update(usage)
            key_label.config(text=usage['usage_key'])
            label_label.config(text=usage['usage_label'])
            plat_name = usage.get('platform')
            model_name = usage.get('model_display_name')
            if plat_name in platforms:
                platform_var.set(plat_name)
                on_platform_change()
                if model_name in model_combo['values']:
                    model_var.set(model_name)
                else:
                    model_var.set("")
            else:
                platform_var.set("")
                model_var.set("")

        usage_listbox.bind('<<ListboxSelect>>', on_select)

        def add_usage():
            key = simpledialog.askstring("新建用途", "请输入用途标识 (Key, 英文):", parent=dialog)
            if not key:
                return
            label = simpledialog.askstring("新建用途", "请输入显示名称 (Label):", parent=dialog, initialvalue=key)
            if not label:
                label = key
            try:
                self.ai_manager.create_user_usage_slot(user_id=system_user_id, usage_key=key, usage_label=label)
                _, self.usage_list = load_data()
                refresh_list()
                self.log(f"✓ 已添加用途: {label} ({key})", tag="success")
            except Exception as e:
                messagebox.showerror("错误", f"添加失败: {e}", parent=dialog)

        def delete_usage():
            selection = usage_listbox.curselection()
            if not selection:
                messagebox.showwarning("提示", "请先选择要删除的用途", parent=dialog)
                return
            idx = selection[0]
            usage = self.usage_list[idx]
            key = usage['usage_key']
            if messagebox.askyesno("确认", f"确定要删除用途 '{usage['usage_label']}' ({key}) 吗？"):
                try:
                    self.ai_manager.delete_user_usage_slot(user_id=system_user_id, usage_key=key)
                    _, self.usage_list = load_data()
                    refresh_list()
                    key_label.config(text="-")
                    label_label.config(text="-")
                    platform_var.set("")
                    model_var.set("")
                    self.log(f"✓ 已删除用途: {key}", tag="success")
                except Exception as e:
                    messagebox.showerror("错误", f"删除失败: {e}", parent=dialog)

        def save_binding():
            if not current_usage_data:
                messagebox.showwarning("提示", "请先选择一个用途", parent=dialog)
                return
            sel_plat = platform_var.get()
            sel_model = model_var.get()
            if not sel_plat or not sel_model:
                messagebox.showerror("错误", "请选择平台和模型", parent=dialog)
                return
            model_info = next((m[1] for m in models_by_platform[sel_plat] if m[0] == sel_model), None)
            if not model_info:
                messagebox.showerror("错误", "模型信息无效", parent=dialog)
                return
            try:
                self.ai_manager.save_user_selection(
                    user_id=system_user_id,
                    platform_id=model_info['platform_id'],
                    model_id=model_info['model_id'],
                    usage_key=current_usage_data['usage_key']
                )
                self.log(f"✓ 用途 '{current_usage_data['usage_key']}' 的绑定已更新", tag="success")
                _, self.usage_list = load_data()
            except Exception as e:
                messagebox.showerror("错误", f"保存失败: {e}", parent=dialog)

        ttk.Button(left_frame, text="+ 新建用途", command=add_usage).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(left_frame, text="- 删除用途", command=delete_usage).pack(side=tk.RIGHT, padx=5, pady=5)
        ttk.Button(right_frame, text="保存绑定配置", command=save_binding).grid(row=5, column=1, sticky=tk.E, pady=20)

        refresh_list()
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
