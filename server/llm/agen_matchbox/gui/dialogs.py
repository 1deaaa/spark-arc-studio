"""
对话框 Mixin — 添加/编辑模型对话框、系统用途管理对话框
"""
import os
import sys
import json as json_lib
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk

if __package__ in (None, "", "gui"):
    _GUI_DIR = os.path.dirname(os.path.abspath(__file__))
    _PKG_DIR = os.path.dirname(_GUI_DIR)
    _PARENT_DIR = os.path.dirname(_PKG_DIR)
    if _PARENT_DIR not in sys.path:
        sys.path.insert(0, _PARENT_DIR)
    __package__ = f"{os.path.basename(_PKG_DIR)}.{os.path.basename(_GUI_DIR)}"

from ..models import (
    DEFAULT_MAX_CONTEXT_TOKENS,
    DEFAULT_MAX_OUTPUT_TOKENS,
    MODALITY_EMBEDDING,
    MODALITY_IMAGE,
    MODALITY_TEXT,
    normalize_model_modalities,
)
from ..image_adapters import (
    IMAGE_ADAPTER_GEMINI_GENERATE_CONTENT,
    IMAGE_ADAPTER_GEMINI_INTERACTIONS,
    IMAGE_ADAPTER_OPENAI_CHAT_IMAGE,
    IMAGE_ADAPTER_OPENAI_IMAGES,
    IMAGE_ADAPTER_OPENAI_RESPONSES_IMAGE,
    IMAGE_ADAPTER_XAI_IMAGES,
    normalize_image_generation_adapter,
    strip_internal_image_generation_fields,
)
from .dpi import prepare_toplevel_window
from .theme import style_listbox


class DialogsMixin:
    """对话框功能 Mixin，需与 LLMConfigGUI 混入使用。"""

    IMAGE_ADAPTER_OPTIONS = {
        "OpenAI Images / 兼容协议": IMAGE_ADAPTER_OPENAI_IMAGES,
        "OpenAI Responses 图片工具": IMAGE_ADAPTER_OPENAI_RESPONSES_IMAGE,
        "OpenAI Chat 图片 / 兼容网关": IMAGE_ADAPTER_OPENAI_CHAT_IMAGE,
        "Gemini generateContent / Nano Banana": IMAGE_ADAPTER_GEMINI_GENERATE_CONTENT,
        "Gemini Interactions": IMAGE_ADAPTER_GEMINI_INTERACTIONS,
        "Grok Image": IMAGE_ADAPTER_XAI_IMAGES,
    }
    DEFAULT_IMAGE_ADAPTER = IMAGE_ADAPTER_OPENAI_IMAGES

    def _normalize_image_adapter(self, value) -> str:
        return normalize_image_generation_adapter(value) or self.DEFAULT_IMAGE_ADAPTER

    def _image_adapter_label(self, value) -> str:
        normalized = self._normalize_image_adapter(value)
        for label, adapter in self.IMAGE_ADAPTER_OPTIONS.items():
            if adapter == normalized:
                return label
        return next(iter(self.IMAGE_ADAPTER_OPTIONS))

    def _image_adapter_value(self, label_or_value) -> str:
        return self.IMAGE_ADAPTER_OPTIONS.get(
            str(label_or_value or "").strip(),
            self._normalize_image_adapter(label_or_value),
        )

    def _extract_image_adapter(self, adapter_value=None) -> str:
        """只读取显式协议字段；Extra Body 永不承担内部协议选择。"""
        return self._normalize_image_adapter(adapter_value)

    def _image_adapter_for_modalities(self, output_modalities, adapter):
        _, normalized_output = normalize_model_modalities(None, output_modalities)
        if MODALITY_IMAGE not in normalized_output:
            return None
        return self._image_adapter_value(adapter)

    def _make_model_modality_checkboxes(
        self,
        parent,
        *,
        row: int,
        initial_input_modalities=None,
        initial_output_modalities=None,
    ):
        """创建用户可见的模型能力复选框。文本能力默认隐含，不单独展示。"""
        input_modalities, output_modalities = normalize_model_modalities(
            initial_input_modalities,
            initial_output_modalities,
        )
        vars_map = {
            "vision": tk.BooleanVar(value=MODALITY_IMAGE in input_modalities),
            "image": tk.BooleanVar(value=MODALITY_IMAGE in output_modalities),
            "embedding": tk.BooleanVar(value=MODALITY_EMBEDDING in output_modalities),
        }

        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=row, column=1, sticky=tk.W, padx=20, pady=5)

        def on_embedding_toggle():
            if vars_map["embedding"].get():
                vars_map["vision"].set(False)
                vars_map["image"].set(False)

        def on_regular_toggle():
            if vars_map["vision"].get() or vars_map["image"].get():
                vars_map["embedding"].set(False)

        ctk.CTkCheckBox(
            frame,
            text="视觉",
            variable=vars_map["vision"],
            command=on_regular_toggle,
            font=("Microsoft YaHei UI", 11),
        ).pack(side=tk.LEFT, padx=(0, 16))
        ctk.CTkCheckBox(
            frame,
            text="生图",
            variable=vars_map["image"],
            command=on_regular_toggle,
            font=("Microsoft YaHei UI", 11),
        ).pack(side=tk.LEFT, padx=(0, 16))
        ctk.CTkCheckBox(
            frame,
            text="向量",
            variable=vars_map["embedding"],
            command=on_embedding_toggle,
            font=("Microsoft YaHei UI", 11),
        ).pack(side=tk.LEFT)
        return vars_map

    def _modality_vars_to_modalities(self, vars_map):
        if vars_map["embedding"].get():
            return normalize_model_modalities([MODALITY_TEXT], [MODALITY_EMBEDDING])

        input_modalities = [MODALITY_TEXT]
        output_modalities = [MODALITY_TEXT]
        if vars_map["vision"].get():
            input_modalities.append(MODALITY_IMAGE)
        if vars_map["image"].get():
            output_modalities.append(MODALITY_IMAGE)
        return normalize_model_modalities(input_modalities, output_modalities)

    @staticmethod
    def _parse_optional_non_negative_int(raw_value: str, *, field_label: str):
        text = str(raw_value or "").strip()
        if not text:
            return None
        try:
            value = int(text)
        except (TypeError, ValueError):
            raise ValueError(f"{field_label} 必须是整数")
        if value < 0:
            raise ValueError(f"{field_label} 不能小于 0")
        return value

    @staticmethod
    def _parse_optional_non_negative_float(raw_value: str, *, field_label: str):
        text = str(raw_value or "").strip()
        if not text:
            return None
        try:
            value = float(text)
        except (TypeError, ValueError):
            raise ValueError(f"{field_label} 必须是数字")
        if value < 0:
            raise ValueError(f"{field_label} 不能小于 0")
        return value

    def _create_modal_dialog(self, title: str, *, default_size=(860, 700), min_size=(680, 520)):
        """创建带有统一尺寸策略的模态对话框。"""
        dialog = ctk.CTkToplevel(self.root)
        dialog.title(title)
        dialog.transient(self.root)
        dialog.grab_set()
        prepare_toplevel_window(
            dialog,
            self.root,
            base_size=default_size,
            min_size=min_size,
            ui_scale=getattr(self, "ui_scale", 1.0),
        )
        return dialog

    def open_add_model_dialog(self, custom_model_id=None):
        """打开添加模型对话框。"""
        platform_name = self._resolve_platform_name()
        if not platform_name:
            messagebox.showwarning("警告", "请先选择一个平台")
            return

        # 从探测缓存中查找 token 上限
        auto_max_context = None
        auto_max_output = None

        if custom_model_id:
            selected_model_id = custom_model_id
        else:
            selected_model_id = ""
            selection = self.probe_listbox.curselection()
            if selection:
                raw_text = self.probe_listbox.get(selection[0])
                selected_model_id = raw_text.split('  [')[0].strip()

        if selected_model_id:
            cache_key = self._get_probe_cache_key(
                platform_name,
                self.base_url_entry.get().strip(),
                self.api_key_entry.get().strip(),
            )
            cached_models = self.probe_models_cache.get(cache_key, [])
            for m in cached_models:
                if isinstance(m, dict) and m.get('id') == selected_model_id:
                    auto_max_context = m.get('max_context_tokens')
                    auto_max_output = m.get('max_output_tokens')
                    break

        dialog = self._create_modal_dialog(
            f"添加模型到 {platform_name}",
            default_size=(860, 760),
            min_size=(720, 620),
        )

        ctk.CTkLabel(dialog, text="显示名称:", font=("Microsoft YaHei UI", 11)).grid(row=0, column=0, sticky=tk.W, padx=20, pady=10)
        display_name_entry = ctk.CTkEntry(dialog, width=320)
        display_name_entry.grid(row=0, column=1, padx=20, pady=10, sticky=tk.W)
        if selected_model_id:
            display_name_entry.insert(0, selected_model_id)

        ctk.CTkLabel(dialog, text="模型ID:", font=("Microsoft YaHei UI", 11)).grid(row=1, column=0, sticky=tk.W, padx=20, pady=10)
        model_id_entry = ctk.CTkEntry(dialog, width=320)
        model_id_entry.grid(row=1, column=1, padx=20, pady=10, sticky=tk.W)
        if selected_model_id:
            model_id_entry.insert(0, selected_model_id)

        ctk.CTkLabel(dialog, text="模型能力:", font=("Microsoft YaHei UI", 11)).grid(row=2, column=0, sticky=tk.W, padx=20, pady=5)
        modality_vars = self._make_model_modality_checkboxes(dialog, row=2)

        ctk.CTkLabel(dialog, text="生图协议:", font=("Microsoft YaHei UI", 11)).grid(row=3, column=0, sticky=tk.W, padx=20, pady=5)
        image_adapter_var = tk.StringVar(value=self._image_adapter_label(self.DEFAULT_IMAGE_ADAPTER))
        image_adapter_combo = ctk.CTkComboBox(
            dialog,
            variable=image_adapter_var,
            values=list(self.IMAGE_ADAPTER_OPTIONS.keys()),
            state="disabled",
            width=260,
            font=("Microsoft YaHei UI", 11),
        )
        image_adapter_combo.grid(row=3, column=1, sticky=tk.W, padx=20, pady=5)

        def refresh_image_adapter_state(*_):
            image_adapter_combo.configure(state="readonly" if modality_vars["image"].get() else "disabled")

        modality_vars["image"].trace_add("write", refresh_image_adapter_state)
        modality_vars["embedding"].trace_add("write", refresh_image_adapter_state)
        refresh_image_adapter_state()

        temperature_enabled_var = tk.BooleanVar(value=False)
        temperature_var = tk.DoubleVar(value=0.7)

        temp_row = ctk.CTkFrame(dialog, fg_color="transparent")
        temp_row.grid(row=4, column=1, padx=20, pady=(6, 0), sticky=(tk.W, tk.E))

        def on_temperature_toggle():
            enabled = bool(temperature_enabled_var.get())
            if enabled:
                messagebox.showwarning(
                    "Temperature 参数警告",
                    "务必了解该模型temperature基准值\n部分模型在温度设置错误时会直接报错\n如果你不清楚这样做的意义\n请不要动这个参数",
                    parent=dialog,
                )
                temperature_entry.configure(state='normal')
            else:
                temperature_entry.configure(state='disabled')

        ctk.CTkCheckBox(
            temp_row,
            text="启用 Temperature",
            variable=temperature_enabled_var,
            command=on_temperature_toggle,
            font=("Microsoft YaHei UI", 11)
        ).pack(side=tk.LEFT)

        ctk.CTkLabel(dialog, text="Temperature: ", font=("Microsoft YaHei UI", 11)).grid(row=4, column=0, sticky=tk.W, padx=20, pady=(6, 0))
        temperature_entry = ctk.CTkEntry(dialog, width=80, textvariable=temperature_var)
        temperature_entry.grid(row=4, column=1, padx=(180, 20), pady=(6, 0), sticky=tk.W)
        temperature_entry.configure(state='disabled')
        ctk.CTkLabel(dialog, text="范围 0.3 - 1.5", text_color="gray", font=("Microsoft YaHei UI", 10)).grid(row=4, column=1, padx=(270, 20), pady=(6, 0), sticky=tk.W)

        ctk.CTkLabel(dialog, text="Token 上限:", font=("Microsoft YaHei UI", 11)).grid(row=5, column=0, sticky=tk.W, padx=20, pady=(8, 0))
        token_row = ctk.CTkFrame(dialog, fg_color="transparent")
        token_row.grid(row=5, column=1, padx=20, pady=(8, 0), sticky=tk.W)
        ctk.CTkLabel(token_row, text="上下文", font=("Microsoft YaHei UI", 10)).pack(side=tk.LEFT, padx=(0, 6))
        max_context_entry = ctk.CTkEntry(token_row, width=120)
        max_context_entry.pack(side=tk.LEFT, padx=(0, 10))
        _init_max_context = auto_max_context if auto_max_context is not None else DEFAULT_MAX_CONTEXT_TOKENS
        max_context_entry.insert(0, str(_init_max_context))
        _ctx_hint = f"探测值: {auto_max_context}" if auto_max_context is not None else "默认 256000"
        ctk.CTkLabel(token_row, text=_ctx_hint, text_color="gray", font=("Microsoft YaHei UI", 10)).pack(side=tk.LEFT, padx=(0, 14))
        ctk.CTkLabel(token_row, text="单次输出", font=("Microsoft YaHei UI", 10)).pack(side=tk.LEFT, padx=(0, 6))
        max_output_entry = ctk.CTkEntry(token_row, width=120)
        max_output_entry.pack(side=tk.LEFT, padx=(0, 10))
        _init_max_output = auto_max_output if auto_max_output is not None else DEFAULT_MAX_OUTPUT_TOKENS
        max_output_entry.insert(0, str(_init_max_output))
        _out_hint = f"探测值: {auto_max_output}" if auto_max_output is not None else "默认 64000"
        ctk.CTkLabel(token_row, text=_out_hint, text_color="gray", font=("Microsoft YaHei UI", 10)).pack(side=tk.LEFT)

        ctk.CTkLabel(dialog, text="价格(每1M token):", font=("Microsoft YaHei UI", 11)).grid(row=6, column=0, sticky=tk.W, padx=20, pady=(8, 0))
        price_row = ctk.CTkFrame(dialog, fg_color="transparent")
        price_row.grid(row=6, column=1, padx=20, pady=(8, 0), sticky=tk.W)
        ctk.CTkLabel(price_row, text="输入", font=("Microsoft YaHei UI", 10)).pack(side=tk.LEFT, padx=(0, 6))
        model_input_price_entry = ctk.CTkEntry(price_row, width=90)
        model_input_price_entry.pack(side=tk.LEFT, padx=(0, 10))
        ctk.CTkLabel(price_row, text="缓存输入", font=("Microsoft YaHei UI", 10)).pack(side=tk.LEFT, padx=(0, 6))
        model_cached_input_price_entry = ctk.CTkEntry(price_row, width=90)
        model_cached_input_price_entry.pack(side=tk.LEFT, padx=(0, 10))
        ctk.CTkLabel(price_row, text="输出", font=("Microsoft YaHei UI", 10)).pack(side=tk.LEFT, padx=(0, 6))
        model_output_price_entry = ctk.CTkEntry(price_row, width=90)
        model_output_price_entry.pack(side=tk.LEFT, padx=(0, 10))
        ctk.CTkLabel(price_row, text="0 表示免费", text_color="gray", font=("Microsoft YaHei UI", 10)).pack(side=tk.LEFT)

        ctk.CTkLabel(dialog, text="Extra Body (JSON):", font=("Microsoft YaHei UI", 11)).grid(row=7, column=0, sticky=(tk.W, tk.N), padx=20, pady=10)
        extra_body_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        extra_body_frame.grid(row=7, column=1, padx=20, pady=10, sticky=(tk.W, tk.E, tk.N, tk.S))
        extra_body_text = ctk.CTkTextbox(extra_body_frame)
        extra_body_text.pack(fill=tk.BOTH, expand=True)
        ctk.CTkLabel(
            extra_body_frame,
            text='示例1: {"thinkingBudget": 0} | 示例2: {"thinking": {"type": "disabled"}} | 示例3: {"top_k": 40}',
            text_color="gray",
            font=('Microsoft YaHei UI', 10),
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

            input_modalities, output_modalities = self._modality_vars_to_modalities(modality_vars)
            image_generation_adapter = self._image_adapter_for_modalities(
                output_modalities,
                image_adapter_var.get(),
            )
            try:
                max_context_tokens = self._parse_optional_non_negative_int(
                    max_context_entry.get(),
                    field_label="最大上下文",
                )
                max_output_tokens = self._parse_optional_non_negative_int(
                    max_output_entry.get(),
                    field_label="最大单次输出",
                )
                model_input_price = self._parse_optional_non_negative_float(
                    model_input_price_entry.get(),
                    field_label="输入价格",
                )
                model_cached_input_price = self._parse_optional_non_negative_float(
                    model_cached_input_price_entry.get(),
                    field_label="缓存输入价格",
                )
                model_output_price = self._parse_optional_non_negative_float(
                    model_output_price_entry.get(),
                    field_label="输出价格",
                )
            except ValueError as err:
                messagebox.showerror("错误", str(err), parent=dialog)
                return

            max_context_tokens = DEFAULT_MAX_CONTEXT_TOKENS if max_context_tokens is None else max_context_tokens
            max_output_tokens = DEFAULT_MAX_OUTPUT_TOKENS if max_output_tokens is None else max_output_tokens

            try:
                db_id = self.current_config[platform_name].get("_db_id")
                if not db_id:
                    raise ValueError("无法获取平台数据库 ID")

                model_cfg_payload = {
                    "display_name": display_name,
                    "model_name": model_id,
                    "input_modalities": input_modalities,
                    "output_modalities": output_modalities,
                    "extra_body": extra_body,
                    "image_generation_adapter": image_generation_adapter,
                    "temperature": temperature_value,
                    "max_context_tokens": max_context_tokens,
                    "max_output_tokens": max_output_tokens,
                    "sys_credit_input_price_per_million": model_input_price,
                    "sys_credit_cached_input_price_per_million": model_cached_input_price,
                    "sys_credit_output_price_per_million": model_output_price,
                }
                self.ai_manager.admin_sync_platform_models(db_id, [model_cfg_payload])

                self.load_config_from_db()
                self.log(f"✓ 模型 '{display_name}' 已添加", tag="success")
                dialog.destroy()
            except Exception as e:
                self.log(f"✗ 保存失败: {e}")
                messagebox.showerror("错误", f"添加模型失败: {e}", parent=dialog)

        button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        button_frame.grid(row=8, column=0, columnspan=2, pady=20)
        ctk.CTkButton(button_frame, text="添加", command=do_add, width=100, fg_color="#3667D6", hover_color="#2E57B5", font=("Microsoft YaHei UI", 11)).pack(side=tk.LEFT, padx=5)
        ctk.CTkButton(button_frame, text="取消", command=dialog.destroy, width=100, font=("Microsoft YaHei UI", 11)).pack(side=tk.LEFT, padx=5)

        dialog.columnconfigure(1, weight=1)
        dialog.rowconfigure(7, weight=1)

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
            model_image_adapter = None
            model_input_modalities, model_output_modalities = normalize_model_modalities()
            model_temperature = None
            model_disabled = False
            model_input_price = None
            model_cached_input_price = None
            model_output_price = None
            model_max_context = DEFAULT_MAX_CONTEXT_TOKENS
            model_max_output = DEFAULT_MAX_OUTPUT_TOKENS
        else:
            model_id = model_config.get("model_name", "")
            extra_body_dict = model_config.get("extra_body")
            model_image_adapter = model_config.get("image_generation_adapter")
            model_input_modalities, model_output_modalities = normalize_model_modalities(
                model_config.get("input_modalities"),
                model_config.get("output_modalities"),
            )
            model_temperature = model_config.get("temperature")
            model_disabled = bool(model_config.get("disabled"))
            model_input_price = model_config.get("sys_credit_input_price_per_million")
            model_cached_input_price = model_config.get("sys_credit_cached_input_price_per_million")
            model_output_price = model_config.get("sys_credit_output_price_per_million")
            model_max_context = model_config.get("max_context_tokens", DEFAULT_MAX_CONTEXT_TOKENS)
            model_max_output = model_config.get("max_output_tokens", DEFAULT_MAX_OUTPUT_TOKENS)
            if isinstance(extra_body_dict, dict):
                extra_body_dict = strip_internal_image_generation_fields(extra_body_dict)

        if model_temperature is None and isinstance(extra_body_dict, dict) and "temperature" in extra_body_dict:
            try:
                model_temperature = float(extra_body_dict.get("temperature"))
            except (TypeError, ValueError):
                model_temperature = None
            extra_body_dict = dict(extra_body_dict)
            extra_body_dict.pop("temperature", None)

        dialog = self._create_modal_dialog(
            f"编辑模型: {display_name}",
            default_size=(860, 740),
            min_size=(720, 620),
        )

        ctk.CTkLabel(dialog, text="显示名称:", font=("Microsoft YaHei UI", 11)).grid(row=0, column=0, sticky=tk.W, padx=20, pady=10)
        display_name_entry = ctk.CTkEntry(dialog, width=320)
        display_name_entry.grid(row=0, column=1, padx=20, pady=10, sticky=tk.W)
        display_name_entry.insert(0, display_name)

        ctk.CTkLabel(dialog, text="模型ID:", font=("Microsoft YaHei UI", 11)).grid(row=1, column=0, sticky=tk.W, padx=20, pady=10)
        model_id_entry = ctk.CTkEntry(dialog, width=320)
        model_id_entry.grid(row=1, column=1, padx=20, pady=10, sticky=tk.W)
        model_id_entry.insert(0, model_id)
        model_id_entry.configure(state='readonly')

        ctk.CTkLabel(dialog, text="模型能力:", font=("Microsoft YaHei UI", 11)).grid(row=2, column=0, sticky=tk.W, padx=20, pady=5)
        modality_vars = self._make_model_modality_checkboxes(
            dialog,
            row=2,
            initial_input_modalities=model_input_modalities,
            initial_output_modalities=model_output_modalities,
        )

        ctk.CTkLabel(dialog, text="生图协议:", font=("Microsoft YaHei UI", 11)).grid(row=3, column=0, sticky=tk.W, padx=20, pady=5)
        image_adapter_var = tk.StringVar(value=self._image_adapter_label(self._extract_image_adapter(model_image_adapter)))
        image_adapter_combo = ctk.CTkComboBox(
            dialog,
            variable=image_adapter_var,
            values=list(self.IMAGE_ADAPTER_OPTIONS.keys()),
            state="disabled",
            width=260,
            font=("Microsoft YaHei UI", 11),
        )
        image_adapter_combo.grid(row=3, column=1, sticky=tk.W, padx=20, pady=5)

        def refresh_image_adapter_state(*_):
            image_adapter_combo.configure(state="readonly" if modality_vars["image"].get() else "disabled")

        modality_vars["image"].trace_add("write", refresh_image_adapter_state)
        modality_vars["embedding"].trace_add("write", refresh_image_adapter_state)
        refresh_image_adapter_state()

        temperature_enabled_var = tk.BooleanVar(value=model_temperature is not None)
        temperature_var = tk.DoubleVar(value=model_temperature if model_temperature is not None else 0.7)

        temp_row = ctk.CTkFrame(dialog, fg_color="transparent")
        temp_row.grid(row=4, column=1, padx=20, pady=(6, 0), sticky=(tk.W, tk.E))

        def on_temperature_toggle():
            enabled = bool(temperature_enabled_var.get())
            if enabled:
                messagebox.showwarning(
                    "Temperature 参数警告",
                    "务必了解该模型temperature基准值\n如果你不清楚这样做的意义\n请不要动这个参数\n部分模型在温度设置错误时会直接报错",
                    parent=dialog,
                )
                temperature_entry.configure(state='normal')
            else:
                temperature_entry.configure(state='disabled')

        ctk.CTkCheckBox(
            temp_row,
            text="启用 Temperature",
            variable=temperature_enabled_var,
            command=on_temperature_toggle,
            font=("Microsoft YaHei UI", 11)
        ).pack(side=tk.LEFT)

        ctk.CTkLabel(dialog, text="Temperature: ", font=("Microsoft YaHei UI", 11)).grid(row=4, column=0, sticky=tk.W, padx=20, pady=(6, 0))
        temperature_entry = ctk.CTkEntry(dialog, width=80, textvariable=temperature_var)
        temperature_entry.grid(row=4, column=1, padx=(180, 20), pady=(6, 0), sticky=tk.W)
        if not bool(temperature_enabled_var.get()):
            temperature_entry.configure(state='disabled')
        ctk.CTkLabel(dialog, text="范围 0.3 - 1.5", text_color="gray", font=("Microsoft YaHei UI", 10)).grid(row=4, column=1, padx=(270, 20), pady=(6, 0), sticky=tk.W)

        ctk.CTkLabel(dialog, text="Token 上限:", font=("Microsoft YaHei UI", 11)).grid(row=5, column=0, sticky=tk.W, padx=20, pady=(8, 0))
        token_row = ctk.CTkFrame(dialog, fg_color="transparent")
        token_row.grid(row=5, column=1, padx=20, pady=(8, 0), sticky=tk.W)
        ctk.CTkLabel(token_row, text="上下文", font=("Microsoft YaHei UI", 10)).pack(side=tk.LEFT, padx=(0, 6))
        max_context_entry = ctk.CTkEntry(token_row, width=120)
        max_context_entry.pack(side=tk.LEFT, padx=(0, 10))
        max_context_entry.insert(0, str(model_max_context))
        ctk.CTkLabel(token_row, text="默认 256000", text_color="gray", font=("Microsoft YaHei UI", 10)).pack(side=tk.LEFT, padx=(0, 14))
        ctk.CTkLabel(token_row, text="单次输出", font=("Microsoft YaHei UI", 10)).pack(side=tk.LEFT, padx=(0, 6))
        max_output_entry = ctk.CTkEntry(token_row, width=120)
        max_output_entry.pack(side=tk.LEFT, padx=(0, 10))
        max_output_entry.insert(0, str(model_max_output))
        ctk.CTkLabel(token_row, text="默认 64000", text_color="gray", font=("Microsoft YaHei UI", 10)).pack(side=tk.LEFT)

        ctk.CTkLabel(dialog, text="价格(每1M token):", font=("Microsoft YaHei UI", 11)).grid(row=6, column=0, sticky=tk.W, padx=20, pady=(8, 0))
        price_row = ctk.CTkFrame(dialog, fg_color="transparent")
        price_row.grid(row=6, column=1, padx=20, pady=(8, 0), sticky=tk.W)
        ctk.CTkLabel(price_row, text="输入", font=("Microsoft YaHei UI", 10)).pack(side=tk.LEFT, padx=(0, 6))
        model_input_price_entry = ctk.CTkEntry(price_row, width=90)
        model_input_price_entry.pack(side=tk.LEFT, padx=(0, 10))
        if model_input_price is not None:
            model_input_price_entry.insert(0, str(model_input_price))
        ctk.CTkLabel(price_row, text="缓存输入", font=("Microsoft YaHei UI", 10)).pack(side=tk.LEFT, padx=(0, 6))
        model_cached_input_price_entry = ctk.CTkEntry(price_row, width=90)
        model_cached_input_price_entry.pack(side=tk.LEFT, padx=(0, 10))
        if model_cached_input_price is not None:
            model_cached_input_price_entry.insert(0, str(model_cached_input_price))
        ctk.CTkLabel(price_row, text="输出", font=("Microsoft YaHei UI", 10)).pack(side=tk.LEFT, padx=(0, 6))
        model_output_price_entry = ctk.CTkEntry(price_row, width=90)
        model_output_price_entry.pack(side=tk.LEFT, padx=(0, 10))
        if model_output_price is not None:
            model_output_price_entry.insert(0, str(model_output_price))
        ctk.CTkLabel(price_row, text="0 表示免费", text_color="gray", font=("Microsoft YaHei UI", 10)).pack(side=tk.LEFT)

        ctk.CTkLabel(dialog, text="Extra Body (JSON):", font=("Microsoft YaHei UI", 11)).grid(row=7, column=0, sticky=(tk.W, tk.N), padx=20, pady=10)
        extra_body_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        extra_body_frame.grid(row=7, column=1, padx=20, pady=10, sticky=(tk.W, tk.E, tk.N, tk.S))
        extra_body_text = ctk.CTkTextbox(extra_body_frame)
        extra_body_text.pack(fill=tk.BOTH, expand=True)
        if extra_body_dict:
            extra_body_text.insert("1.0", json_lib.dumps(extra_body_dict, indent=2, ensure_ascii=False))
        ctk.CTkLabel(
            extra_body_frame,
            text='示例1: {"thinkingBudget": 0} | 示例2: {"thinking": {"type": "disabled"}} | 示例3: {"top_k": 40}',
            text_color="gray",
            font=('Microsoft YaHei UI', 10),
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

            raw_input_price_text = model_input_price_entry.get().strip()
            raw_cached_input_price_text = model_cached_input_price_entry.get().strip()
            raw_output_price_text = model_output_price_entry.get().strip()
            update_credit_price = (
                raw_input_price_text != ""
                or raw_cached_input_price_text != ""
                or raw_output_price_text != ""
                or model_input_price is not None
                or model_cached_input_price is not None
                or model_output_price is not None
            )
            try:
                max_context_tokens = self._parse_optional_non_negative_int(
                    max_context_entry.get(),
                    field_label="最大上下文",
                )
                max_output_tokens = self._parse_optional_non_negative_int(
                    max_output_entry.get(),
                    field_label="最大单次输出",
                )
                model_input_price_value = self._parse_optional_non_negative_float(
                    raw_input_price_text,
                    field_label="输入价格",
                )
                model_cached_input_price_value = self._parse_optional_non_negative_float(
                    raw_cached_input_price_text,
                    field_label="缓存输入价格",
                )
                model_output_price_value = self._parse_optional_non_negative_float(
                    raw_output_price_text,
                    field_label="输出价格",
                )
            except ValueError as err:
                messagebox.showerror("错误", str(err), parent=dialog)
                return

            max_context_tokens = DEFAULT_MAX_CONTEXT_TOKENS if max_context_tokens is None else max_context_tokens
            max_output_tokens = DEFAULT_MAX_OUTPUT_TOKENS if max_output_tokens is None else max_output_tokens
            updated_input_modalities, updated_output_modalities = self._modality_vars_to_modalities(modality_vars)
            image_generation_adapter = self._image_adapter_for_modalities(
                updated_output_modalities,
                image_adapter_var.get(),
            )

            try:
                db_id = self.current_config[platform_name].get("_db_id")
                if not db_id:
                    raise ValueError("无法获取平台数据库 ID")

                model_db_id = model_config.get("_db_id") if isinstance(model_config, dict) else None
                if not model_db_id:
                    raise ValueError("无法获取模型数据库 ID")

                self.ai_manager.admin_update_sys_model(
                    model_id=model_db_id,
                    display_name=new_display_name,
                    extra_body=extra_body,
                    image_generation_adapter=image_generation_adapter,
                    update_image_generation_adapter=True,
                    temperature=temperature_value,
                    input_modalities=updated_input_modalities,
                    output_modalities=updated_output_modalities,
                    update_modalities=True,
                    max_context_tokens=max_context_tokens,
                    max_output_tokens=max_output_tokens,
                    sys_credit_input_price_per_million=model_input_price_value,
                    sys_credit_cached_input_price_per_million=model_cached_input_price_value,
                    sys_credit_output_price_per_million=model_output_price_value,
                    update_credit_price=update_credit_price,
                    update_max_context_tokens=True,
                    update_max_output_tokens=True,
                )

                self.load_config_from_db()
                self.log(f"✓ 模型 '{new_display_name}' 已更新", tag="success")
                dialog.destroy()
            except Exception as e:
                self.log(f"✗ 保存失败: {e}")
                messagebox.showerror("错误", f"更新模型失败: {e}", parent=dialog)

        button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        button_frame.grid(row=8, column=0, columnspan=2, pady=20)
        ctk.CTkButton(button_frame, text="保存", command=do_update, width=100, fg_color="#3667D6", hover_color="#2E57B5", font=("Microsoft YaHei UI", 11)).pack(side=tk.LEFT, padx=5)
        ctk.CTkButton(button_frame, text="取消", command=dialog.destroy, width=100, font=("Microsoft YaHei UI", 11)).pack(side=tk.LEFT, padx=5)

        dialog.columnconfigure(1, weight=1)
        dialog.rowconfigure(7, weight=1)

    def edit_system_model(self):
        """编辑系统用户 (-1) 的模型选择及用途管理。"""
        dialog = self._create_modal_dialog(
            "系统模型与用途管理",
            default_size=(980, 640),
            min_size=(780, 560),
        )

        system_user_id = "-1"

        def load_data():
            try:
                self.ai_manager.admin_sync_from_yaml()
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

        # 使用 ctk.CTkFrame 来进行分栏布局，体验更好
        paned = ctk.CTkFrame(dialog, fg_color="transparent")
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        paned.columnconfigure(0, weight=2)
        paned.columnconfigure(1, weight=3)
        paned.rowconfigure(0, weight=1)

        left_frame = ctk.CTkFrame(paned)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=0)

        ctk.CTkLabel(left_frame, text="用途列表 (Usage Slots)", font=("Microsoft YaHei UI", 11, "bold")).pack(anchor=tk.W, padx=10, pady=(10, 5))

        usage_listbox = tk.Listbox(left_frame, height=15)
        style_listbox(usage_listbox, ui_scale=getattr(self, "ui_scale", 1.0))
        usage_scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=usage_listbox.yview)
        usage_listbox.configure(yscrollcommand=usage_scrollbar.set)
        usage_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=(0, 10))
        usage_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=(0, 10))

        right_frame = ctk.CTkFrame(paned)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        right_frame.columnconfigure(1, weight=1)

        ctk.CTkLabel(right_frame, text="绑定模型配置", font=("Microsoft YaHei UI", 11, "bold")).grid(row=0, column=0, columnspan=2, sticky=tk.W, padx=16, pady=(10, 5))

        ctk.CTkLabel(right_frame, text="用途标识 (Key):", font=("Microsoft YaHei UI", 11)).grid(row=1, column=0, sticky=tk.W, padx=16, pady=5)
        key_label = ctk.CTkLabel(right_frame, text="-", font=("Consolas", 11, "bold"), text_color="#3667D6")
        key_label.grid(row=1, column=1, sticky=tk.W, padx=16, pady=5)

        ctk.CTkLabel(right_frame, text="显示名称 (Label):", font=("Microsoft YaHei UI", 11)).grid(row=2, column=0, sticky=tk.W, padx=16, pady=5)
        label_label = ctk.CTkLabel(right_frame, text="-", font=("Microsoft YaHei UI", 11))
        label_label.grid(row=2, column=1, sticky=tk.W, padx=16, pady=5)

        sep = ctk.CTkFrame(right_frame, height=2, fg_color=("gray85", "gray30"))
        sep.grid(row=3, column=0, columnspan=2, sticky="ew", pady=10, padx=16)

        ctk.CTkLabel(right_frame, text="选择平台:", font=("Microsoft YaHei UI", 11)).grid(row=4, column=0, sticky=tk.W, padx=16, pady=5)
        platform_var = tk.StringVar()
        platform_combo = ctk.CTkComboBox(right_frame, variable=platform_var, values=platforms, state='readonly', command=lambda choice: on_platform_change())
        platform_combo.grid(row=4, column=1, sticky=(tk.W, tk.E), pady=5, padx=16)

        ctk.CTkLabel(right_frame, text="选择模型:", font=("Microsoft YaHei UI", 11)).grid(row=5, column=0, sticky=tk.W, padx=16, pady=5)
        model_var = tk.StringVar()
        model_combo = ctk.CTkComboBox(right_frame, variable=model_var, state='readonly')
        model_combo.grid(row=5, column=1, sticky=(tk.W, tk.E), pady=5, padx=16)

        current_usage_data = {}

        def refresh_list():
            usage_listbox.delete(0, tk.END)
            for u in self.usage_list:
                display = f"{u['usage_label']} ({u['usage_key']})"
                usage_listbox.insert(tk.END, display)

        def on_platform_change(event=None):
            selected_platform = platform_var.get()
            model_display_names = [m[0] for m in models_by_platform.get(selected_platform, [])]
            model_combo.configure(values=model_display_names)
            if model_var.get() not in model_display_names:
                model_var.set(model_display_names[0] if model_display_names else "")
                if model_display_names:
                    model_combo.set(model_display_names[0])
                else:
                    model_combo.set("")

        def on_select(event):
            selection = usage_listbox.curselection()
            if not selection:
                return
            idx = selection[0]
            usage = self.usage_list[idx]
            current_usage_data.clear()
            current_usage_data.update(usage)
            key_label.configure(text=usage['usage_key'])
            label_label.configure(text=usage['usage_label'])
            plat_name = usage.get('platform')
            model_name = usage.get('model_display_name')
            if plat_name in platforms:
                platform_var.set(plat_name)
                platform_combo.set(plat_name)
                on_platform_change()
                model_list = [m[0] for m in models_by_platform.get(plat_name, [])]
                if model_name in model_list:
                    model_var.set(model_name)
                    model_combo.set(model_name)
                else:
                    model_var.set("")
                    model_combo.set("")
            else:
                platform_var.set("")
                platform_combo.set("")
                model_var.set("")
                model_combo.set("")

        usage_listbox.bind('<<ListboxSelect>>', on_select)

        def add_usage():
            dialog_key = ctk.CTkInputDialog(text="请输入用途标识 (Key, 英文):", title="新建用途")
            key = dialog_key.get_input()
            if not key or not key.strip():
                return
            key = key.strip()
            
            dialog_label = ctk.CTkInputDialog(text="请输入显示名称 (Label):", title="新建用途")
            label = dialog_label.get_input()
            if not label or not label.strip():
                label = key
            else:
                label = label.strip()
                
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
                    key_label.configure(text="-")
                    label_label.configure(text="-")
                    platform_var.set("")
                    platform_combo.set("")
                    model_var.set("")
                    model_combo.set("")
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

        btn_left_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        btn_left_frame.pack(fill=tk.X, padx=10, pady=5)
        ctk.CTkButton(btn_left_frame, text="+ 新建用途", command=add_usage, width=100, font=("Microsoft YaHei UI", 11)).pack(side=tk.LEFT)
        ctk.CTkButton(btn_left_frame, text="- 删除用途", command=delete_usage, fg_color="#D14343", hover_color="#B83636", width=100, font=("Microsoft YaHei UI", 11)).pack(side=tk.RIGHT)
        
        ctk.CTkButton(right_frame, text="保存绑定配置", command=save_binding, fg_color="#3667D6", hover_color="#2E57B5", font=("Microsoft YaHei UI", 11)).grid(row=6, column=1, sticky=tk.E, pady=20, padx=16)

        refresh_list()

    def open_quota_manager_dialog(self, default_user_id=None):
        """打开用户配额管理对话框。"""
        dialog = self._create_modal_dialog(
            "用户配额管理",
            default_size=(980, 760),
            min_size=(820, 620),
        )

        ctk.CTkLabel(dialog, text="用户ID:", font=("Microsoft YaHei UI", 11)).grid(row=0, column=0, sticky=tk.W, padx=20, pady=(15, 6))
        user_id_var = tk.StringVar()
        user_id_entry = ctk.CTkEntry(dialog, width=280, textvariable=user_id_var)
        user_id_entry.grid(row=0, column=1, sticky=tk.W, padx=20, pady=(15, 6))
        if default_user_id is not None:
            user_id_var.set(str(default_user_id))

        policy_frame = ctk.CTkFrame(dialog)
        policy_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.N, tk.S, tk.W, tk.E), padx=20, pady=8)

        quota_fields = [
            ("sys_paid_window_hours", "sys_paid 窗口小时数"),
            ("sys_paid_window_token_limit", "sys_paid 窗口 token 上限"),
            ("sys_paid_window_request_limit", "sys_paid 窗口请求上限"),
            ("sys_paid_total_token_limit", "sys_paid 总 token 上限"),
            ("sys_paid_total_request_limit", "sys_paid 总请求上限"),
            ("self_paid_window_hours", "self_paid 窗口小时数"),
            ("self_paid_window_token_limit", "self_paid 窗口 token 上限"),
            ("self_paid_window_request_limit", "self_paid 窗口请求上限"),
            ("self_paid_total_token_limit", "self_paid 总 token 上限"),
            ("self_paid_total_request_limit", "self_paid 总请求上限"),
        ]

        ctk.CTkLabel(policy_frame, text="配额策略", font=("Microsoft YaHei UI", 11, "bold")).grid(row=0, column=0, columnspan=4, sticky=tk.W, padx=16, pady=(10, 5))

        field_entries = {}
        for idx, (field_name, label_text) in enumerate(quota_fields):
            row = (idx % 5) + 1
            col = (idx // 5) * 2
            ctk.CTkLabel(policy_frame, text=f"{label_text}:", font=("Microsoft YaHei UI", 11)).grid(
                row=row,
                column=col,
                sticky=tk.W,
                padx=(16, 6),
                pady=4,
            )
            entry = ctk.CTkEntry(policy_frame, width=150)
            entry.grid(row=row, column=col + 1, sticky=tk.W, padx=(0, 16), pady=4)
            field_entries[field_name] = entry

        ctk.CTkLabel(
            policy_frame,
            text="留空表示不限制；小时数字段必须 >= 1，其它字段必须 >= 0",
            text_color="gray",
            font=("Microsoft YaHei UI", 10),
        ).grid(row=6, column=0, columnspan=4, sticky=tk.W, padx=16, pady=(8, 10))

        status_frame = ctk.CTkFrame(dialog)
        status_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.N, tk.S, tk.W, tk.E), padx=20, pady=(0, 8))
        
        status_label_frame = ctk.CTkFrame(status_frame, fg_color="transparent")
        status_label_frame.pack(fill=tk.X, padx=10, pady=(10, 5))
        ctk.CTkLabel(status_label_frame, text="当前状态", font=("Microsoft YaHei UI", 11, "bold")).pack(side=tk.LEFT)
        
        status_text = ctk.CTkTextbox(status_frame, height=180, wrap=tk.WORD)
        status_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        def render_status(status_payload):
            status_text.configure(state='normal')
            status_text.delete("1.0", tk.END)
            status_text.insert(tk.END, json_lib.dumps(status_payload, ensure_ascii=False, indent=2))
            status_text.configure(state='disabled')

        def clear_fields():
            for entry in field_entries.values():
                entry.delete(0, tk.END)

        def fill_policy(policy_payload):
            for field_name, _ in quota_fields:
                entry = field_entries[field_name]
                entry.delete(0, tk.END)
                value = policy_payload.get(field_name)
                if value is not None:
                    entry.insert(0, str(value))

        def load_user_quota():
            user_id = user_id_var.get().strip()
            if not user_id:
                messagebox.showwarning("警告", "请先输入用户ID", parent=dialog)
                return
            try:
                policy = self.ai_manager.admin_get_user_quota_policy(user_id)
                status = self.ai_manager.admin_get_user_quota_status(user_id)
                fill_policy(policy)
                render_status(status)
                self.log(f"✓ 已加载用户 '{user_id}' 的配额策略", tag="success")
            except Exception as exc:
                self.log(f"✗ 加载配额失败: {exc}")
                messagebox.showerror("错误", f"加载配额失败: {exc}", parent=dialog)

        def save_user_quota():
            user_id = user_id_var.get().strip()
            if not user_id:
                messagebox.showwarning("警告", "请先输入用户ID", parent=dialog)
                return

            payload = {}
            try:
                for field_name, _ in quota_fields:
                    raw_text = field_entries[field_name].get().strip()
                    if not raw_text:
                        payload[field_name] = None
                    else:
                        parsed = int(raw_text)
                        min_value = 1 if field_name.endswith("_window_hours") else 0
                        if parsed < min_value:
                            raise ValueError(f"{field_name} 不能小于 {min_value}")
                        payload[field_name] = parsed
            except Exception as exc:
                messagebox.showerror("错误", f"输入格式错误: {exc}", parent=dialog)
                return

            try:
                self.ai_manager.admin_save_user_quota_policy(user_id, **payload)
                status = self.ai_manager.admin_get_user_quota_status(user_id)
                render_status(status)
                self.log(f"✓ 已保存用户 '{user_id}' 的配额策略", tag="success")
                messagebox.showinfo("成功", "配额策略已保存", parent=dialog)
            except Exception as exc:
                self.log(f"✗ 保存配额失败: {exc}")
                messagebox.showerror("错误", f"保存配额失败: {exc}", parent=dialog)

        action_row = ctk.CTkFrame(dialog, fg_color="transparent")
        action_row.grid(row=3, column=0, columnspan=3, sticky=tk.EW, padx=20, pady=(10, 15))
        ctk.CTkButton(action_row, text="加载", width=100, command=load_user_quota, font=("Microsoft YaHei UI", 11)).pack(side=tk.LEFT, padx=4)
        ctk.CTkButton(action_row, text="保存", width=100, command=save_user_quota, fg_color="#3667D6", hover_color="#2E57B5", font=("Microsoft YaHei UI", 11)).pack(side=tk.LEFT, padx=4)
        ctk.CTkButton(action_row, text="清空", width=100, command=clear_fields, font=("Microsoft YaHei UI", 11)).pack(side=tk.LEFT, padx=4)
        ctk.CTkButton(action_row, text="关闭", width=100, command=dialog.destroy, font=("Microsoft YaHei UI", 11)).pack(side=tk.RIGHT, padx=4)

        dialog.columnconfigure(0, weight=1)
        dialog.columnconfigure(1, weight=1)
        dialog.columnconfigure(2, weight=1)
        dialog.rowconfigure(2, weight=1)

        if default_user_id is not None:
            dialog.after(0, load_user_quota)
