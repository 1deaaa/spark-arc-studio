"""
主窗口 — LLMConfigGUI 主类，混入所有 Mixin，构建产品化 GUI 布局。
"""
import os
import sys
import tkinter as tk
from tkinter import messagebox, ttk

if __package__ in (None, "", "gui"):
    _GUI_DIR = os.path.dirname(os.path.abspath(__file__))
    _PKG_DIR = os.path.dirname(_GUI_DIR)
    _PARENT_DIR = os.path.dirname(_PKG_DIR)
    if _PARENT_DIR not in sys.path:
        sys.path.insert(0, _PARENT_DIR)
    __package__ = f"{os.path.basename(_PKG_DIR)}.{os.path.basename(_GUI_DIR)}"

from ..manager import AIManager
from ..security import SecurityManager
from .dialogs import DialogsMixin
from .dpi import configure_tk_scaling, enable_high_dpi_awareness, prepare_root_window, prepare_toplevel_window
from .key_manager import KeyManagerMixin
from .model_panel import ModelPanelMixin
from .platform_panel import PlatformPanelMixin
from .testing import TestingMixin
from .theme import COLORS, apply_theme, style_listbox, style_text_widget


class LLMConfigGUI(
    PlatformPanelMixin,
    ModelPanelMixin,
    DialogsMixin,
    KeyManagerMixin,
    TestingMixin,
):
    """LLM 配置管理器主窗口。"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.option_add("*tearOff", False)
        self.ui_scale = configure_tk_scaling(self.root)

        self.current_config: dict = {}
        self.probe_models_cache: dict = {}
        self.platform_display_to_key: dict = {}
        self.platform_keys_in_order: list = []
        self.last_selected_platform_name: str = ""
        self.user_usage_rows: list = []
        self.user_usage_sort_column = "requests"
        self.user_usage_sort_descending = True

        self.header_status_var = tk.StringVar(value="等待初始化配置环境")
        self.workflow_hint_var = tk.StringVar(value="推荐流程：填写平台密钥 → 探测模型 → 添加并测试模型。")
        self.user_usage_status_var = tk.StringVar(value="双击用户 ID 可查看详情与编辑配额；点击任意列头可排序。")

        try:
            self.ai_manager = AIManager()
        except Exception as e:
            messagebox.showerror("初始化失败", f"AIManager 初始化失败: {e}")
            raise

        self._build_styles()
        prepare_root_window(
            self.root,
            title="火柴Agent网关 · LLM 配置台",
            base_size=(1480, 930),
            min_size=(1320, 820),
            ui_scale=self.ui_scale,
        )
        self._build_ui()
        self.root.after(100, self._bootstrap_startup)

    def _scale(self, value: int) -> int:
        scale = min(max(self.ui_scale, 1.0), 1.35)
        return max(value, int(round(value * scale)))

    def _bootstrap_startup(self):
        """启动自检：强制主密钥、建表初始化、再加载数据库配置。"""
        try:
            if not self._ensure_master_key_ready_on_startup():
                self.root.after(0, self.root.destroy)
                return

            self.ai_manager.ensure_database_ready()
            self.load_config_from_db()
        except Exception as e:
            messagebox.showerror("初始化失败", f"GUI 启动失败: {e}")
            self.root.after(0, self.root.destroy)

    # ------------------------------------------------------------------ #
    #  样式与布局                                                           #
    # ------------------------------------------------------------------ #

    def _build_styles(self):
        """配置 ttk 样式。"""
        self.theme_tokens = apply_theme(self.root, ui_scale=self.ui_scale)

    def _build_ui(self):
        """构建主界面布局。"""
        shell = ttk.Frame(self.root, style="Shell.TFrame", padding=self._scale(18))
        shell.pack(fill=tk.BOTH, expand=True)
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(1, weight=1)

        self._build_header(shell)

        workspace = ttk.PanedWindow(shell, orient=tk.HORIZONTAL)
        workspace.grid(row=1, column=0, sticky="nsew")

        left_frame = ttk.Frame(workspace, style="Shell.TFrame")
        right_frame = ttk.Frame(workspace, style="Shell.TFrame")
        workspace.add(left_frame, weight=11)
        workspace.add(right_frame, weight=17)

        self._build_left_panel(left_frame)
        self._build_right_panel(right_frame)
        self._update_overview_state()

    def _build_header(self, parent):
        """构建顶部品牌头部与全局操作区。"""
        header = ttk.Frame(parent, style="Hero.TFrame", padding=(self._scale(22), self._scale(18)))
        header.grid(row=0, column=0, sticky="ew", pady=(0, self._scale(14)))
        header.columnconfigure(0, weight=1)
        header.columnconfigure(1, weight=1)

        text_frame = ttk.Frame(header, style="Hero.TFrame")
        text_frame.grid(row=0, column=0, sticky="nw", padx=(0, self._scale(18)))

        ttk.Label(text_frame, text="火柴Agent网关 · LLM 配置台", style="HeroTitle.TLabel").pack(anchor=tk.W)
        ttk.Label(
            text_frame,
            text="为 Agent 场景打造的轻量化配置工作台，集中管理平台、模型、用途与配额。",
            style="HeroSubtitle.TLabel",
            wraplength=self._scale(560),
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(self._scale(6), self._scale(8)))
        ttk.Label(text_frame, textvariable=self.header_status_var, style="Accent.TLabel").pack(anchor=tk.W)

        actions_frame = ttk.Frame(header, style="Hero.TFrame")
        actions_frame.grid(row=0, column=1, sticky="nsew")
        for col in range(3):
            actions_frame.columnconfigure(col, weight=1)

        buttons = [
            ("刷新配置", self.load_config_from_db, "Primary.TButton"),
            ("从配置文件重置", self.reload_from_yaml, "TButton"),
            ("导出到配置文件", self.export_db_to_yaml, "TButton"),
            ("设置主密钥", self.open_set_llm_key_dialog, "TButton"),
            ("系统用途管理", self.edit_system_model, "TButton"),
            ("用户配额管理", self.open_quota_manager_dialog, "TButton"),
        ]
        for index, (text, command, style_name) in enumerate(buttons):
            row = index // 3
            col = index % 3
            ttk.Button(actions_frame, text=text, command=command, style=style_name).grid(
                row=row,
                column=col,
                sticky="ew",
                padx=(0 if col == 0 else self._scale(8), 0),
                pady=(0, self._scale(8) if row == 0 else 0),
            )

    def _build_left_panel(self, parent):
        """构建左侧工作区。"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        left_paned = ttk.PanedWindow(parent, orient=tk.VERTICAL)
        left_paned.grid(row=0, column=0, sticky="nsew")

        plat_frame = ttk.LabelFrame(left_paned, text="平台配置", padding=self._scale(16), style="Card.TLabelframe")
        left_paned.add(plat_frame, weight=7)
        self._build_platform_panel(plat_frame)

        usage_frame = ttk.LabelFrame(left_paned, text="用户调用总览（双击用户查看详情设置配额）", padding=self._scale(16), style="Card.TLabelframe")
        left_paned.add(usage_frame, weight=13)
        self._build_user_usage_panel(usage_frame)

    def _build_platform_panel(self, parent):
        """构建平台管理面板。"""
        parent.columnconfigure(1, weight=1)
        parent.columnconfigure(2, weight=0)

        ttk.Label(parent, text="选择一个平台后，可在此编辑地址、密钥，并管理平台优先级。", style="SurfaceMuted.TLabel", wraplength=self._scale(360), justify=tk.LEFT).grid(
            row=0, column=0, columnspan=3, sticky="ew", pady=(0, self._scale(12))
        )
        ttk.Label(parent, textvariable=self.workflow_hint_var, style="SurfaceMuted.TLabel", wraplength=self._scale(360), justify=tk.LEFT).grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, self._scale(10)))

        ttk.Label(parent, text="平台", style="Surface.TLabel").grid(row=2, column=0, sticky=tk.W, pady=(0, self._scale(10)))
        self.platform_var = tk.StringVar()
        self.platform_combo = ttk.Combobox(parent, textvariable=self.platform_var, state="readonly")
        self.platform_combo.grid(row=2, column=1, columnspan=2, sticky="ew", pady=(0, self._scale(10)))
        self.platform_combo.bind("<<ComboboxSelected>>", self.on_platform_selected)

        ttk.Label(parent, text="当前 URL", style="Surface.TLabel").grid(row=3, column=0, sticky=tk.W, pady=(0, self._scale(10)))
        self.base_url_entry = ttk.Entry(parent, state="readonly", style="Readonly.TEntry")
        self.base_url_entry.grid(row=3, column=1, columnspan=2, sticky="ew", pady=(0, self._scale(10)))

        ttk.Label(parent, text="编辑 URL", style="Surface.TLabel").grid(row=4, column=0, sticky=tk.W, pady=(0, self._scale(10)))
        self.platform_url_entry = ttk.Entry(parent)
        self.platform_url_entry.grid(row=4, column=1, sticky="ew", pady=(0, self._scale(10)), padx=(0, self._scale(8)))
        ttk.Button(parent, text="保存 URL", command=self.save_platform_url, style="Primary.TButton").grid(row=4, column=2, sticky="ew", pady=(0, self._scale(10)))

        ttk.Label(parent, text="API Key", style="Surface.TLabel").grid(row=5, column=0, sticky=tk.W, pady=(0, self._scale(12)))
        self.api_key_entry = ttk.Entry(parent, show="*")
        self.api_key_entry.grid(row=5, column=1, sticky="ew", pady=(0, self._scale(12)), padx=(0, self._scale(8)))
        ttk.Button(parent, text="保存 Key", command=self.save_api_key, style="Primary.TButton").grid(row=5, column=2, sticky="ew", pady=(0, self._scale(12)))

        ttk.Separator(parent, orient=tk.HORIZONTAL).grid(row=6, column=0, columnspan=3, sticky="ew", pady=(0, self._scale(12)))

        action_row = ttk.Frame(parent, style="Card.TFrame")
        action_row.grid(row=7, column=0, columnspan=3, sticky="ew")
        for col in range(3):
            action_row.columnconfigure(col, weight=1)
        ttk.Button(action_row, text="新增平台", command=self.add_platform).grid(row=0, column=0, sticky="ew")
        ttk.Button(action_row, text="删除平台", command=self.delete_platform, style="Danger.TButton").grid(row=0, column=1, sticky="ew", padx=self._scale(8))
        ttk.Button(action_row, text="设为默认平台", command=self.set_as_default).grid(row=0, column=2, sticky="ew")

    def _build_user_usage_panel(self, parent):
        """构建用户调用查询面板。"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        table_frame = ttk.Frame(parent, style="Card.TFrame")
        table_frame.grid(row=0, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        columns = ("user_id", "requests", "tokens", "prompt", "completion", "sys_paid", "self_paid", "errors")
        self.user_usage_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=14)
        headings = {
            "user_id": ("用户 ID", self._scale(126)),
            "requests": ("调用", self._scale(56)),
            "tokens": ("总 Token", self._scale(84)),
            "prompt": ("Prompt", self._scale(72)),
            "completion": ("Completion", self._scale(84)),
            "sys_paid": ("站长付费", self._scale(72)),
            "self_paid": ("用户自费", self._scale(72)),
            "errors": ("错误", self._scale(56)),
        }
        for key, (title, width) in headings.items():
            self.user_usage_tree.heading(key, text=title, command=lambda sort_key=key: self.sort_user_usage_overview(sort_key))
            self.user_usage_tree.column(key, width=width, anchor=tk.W if key == "user_id" else tk.CENTER, stretch=key == "user_id")

        tree_scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.user_usage_tree.yview)
        self.user_usage_tree.configure(yscrollcommand=tree_scroll.set)
        self.user_usage_tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll.grid(row=0, column=1, sticky="ns")
        self.user_usage_tree.bind("<Double-1>", self._on_user_usage_tree_double_click)

    def _clear_user_usage_tree(self):
        """清空用户用量表格。"""
        for item_id in self.user_usage_tree.get_children():
            self.user_usage_tree.delete(item_id)

    def _render_user_usage_overview_rows(self, rows):
        """渲染用户总览表格。"""
        self._clear_user_usage_tree()
        for row in rows:
            self.user_usage_tree.insert(
                "",
                tk.END,
                values=(
                    row.get("user_id", "-"),
                    int(row.get("requests", 0)),
                    int(row.get("total_tokens", 0)),
                    int(row.get("prompt_tokens", 0)),
                    int(row.get("completion_tokens", 0)),
                    int(row.get("sys_paid_requests", 0)),
                    int(row.get("self_paid_requests", 0)),
                    int(row.get("errors", 0)),
                ),
            )

    def load_user_usage_overview(self, silent=False):
        """加载全部用户的累计调用总览。"""
        try:
            self.user_usage_rows = self.ai_manager.get_users_usage_overview()
            self.sort_user_usage_overview(self.user_usage_sort_column, toggle=False, descending=self.user_usage_sort_descending)
            user_count = len(self.user_usage_rows)
            if user_count:
                self.user_usage_status_var.set(
                    f"共 {user_count} 个用户有调用记录；双击用户 ID 可查看详情与编辑配额；点击任意列头可排序。"
                )
            else:
                self.user_usage_status_var.set("当前还没有任何用户调用记录；点击任意列头可排序。")
            self.log("✓ 已刷新全部用户调用总览", tag="success")
        except Exception as exc:
            self.log(f"✗ 加载用户总览失败: {exc}", tag="error")
            self.user_usage_status_var.set(f"加载用户总览失败: {exc}")
            if not silent:
                messagebox.showerror("错误", f"加载用户总览失败: {exc}")

    def sort_user_usage_overview(self, column_key, toggle=True, descending=None):
        """按指定列对用户总览表格排序。"""
        if not self.user_usage_rows:
            self._clear_user_usage_tree()
            return

        key_map = {
            "user_id": "user_id",
            "requests": "requests",
            "tokens": "total_tokens",
            "prompt": "prompt_tokens",
            "completion": "completion_tokens",
            "sys_paid": "sys_paid_requests",
            "self_paid": "self_paid_requests",
            "errors": "errors",
        }
        data_key = key_map.get(column_key, column_key)

        if toggle:
            if self.user_usage_sort_column == column_key:
                self.user_usage_sort_descending = not self.user_usage_sort_descending
            else:
                self.user_usage_sort_column = column_key
                self.user_usage_sort_descending = column_key != "user_id"
        else:
            self.user_usage_sort_column = column_key
            if descending is not None:
                self.user_usage_sort_descending = bool(descending)

        descending_flag = self.user_usage_sort_descending
        if self.user_usage_sort_column == "user_id":
            sorted_rows = sorted(self.user_usage_rows, key=lambda row: str(row.get("user_id", "")).lower(), reverse=descending_flag)
        else:
            sorted_rows = sorted(self.user_usage_rows, key=lambda row: int(row.get(data_key, 0)), reverse=descending_flag)
        self._render_user_usage_overview_rows(sorted_rows)

    def _get_selected_user_id(self):
        """返回当前选中的用户 ID。"""
        selection = self.user_usage_tree.selection()
        if not selection:
            return ""
        values = self.user_usage_tree.item(selection[0], "values")
        if not values:
            return ""
        return str(values[0]).strip()

    def _on_user_usage_tree_double_click(self, event):
        """双击用户 ID 列时打开详情窗口。"""
        item_id = self.user_usage_tree.identify_row(event.y)
        column_id = self.user_usage_tree.identify_column(event.x)
        if not item_id or column_id != "#1":
            return
        values = self.user_usage_tree.item(item_id, "values")
        if not values:
            return
        self.open_user_usage_detail_dialog(str(values[0]).strip())

    def open_user_usage_detail_dialog(self, user_id):
        """打开单个用户的调用详情窗口。"""
        user_id = str(user_id or "").strip()
        if not user_id:
            return

        total_payload = self.ai_manager.get_user_usage_total(user_id)
        stats_rows = self.ai_manager.get_user_usage_stats(user_id)
        quota_payload = self.ai_manager.admin_get_user_quota_status(user_id)

        dialog = tk.Toplevel(self.root)
        dialog.title(f"用户详情 · {user_id}")
        dialog.transient(self.root)
        dialog.grab_set()
        prepare_toplevel_window(
            dialog,
            self.root,
            base_size=(980, 720),
            min_size=(820, 620),
            ui_scale=self.ui_scale,
        )
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)

        header = ttk.Frame(dialog, style="Card.TFrame", padding=self._scale(16))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text=f"用户详情 · {user_id}", style="CardTitle.TLabel").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(header, text="展示该用户的累计调用摘要、额度状态与按模型聚合的调用明细。", style="SurfaceMuted.TLabel").grid(row=1, column=0, sticky=tk.W, pady=(self._scale(4), 0))

        content = ttk.Frame(dialog, style="Card.TFrame", padding=self._scale(16))
        content.grid(row=1, column=0, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.rowconfigure(1, weight=1)

        summary = ttk.Frame(content, style="Card.TFrame")
        summary.grid(row=0, column=0, sticky="ew", pady=(0, self._scale(12)))
        for col in range(4):
            summary.columnconfigure(col, weight=1)

        summary_items = [
            ("总请求", f"{int(total_payload.get('requests', 0))} 次"),
            ("总 Token", str(int(total_payload.get('tokens', 0)))),
            ("站长付费", f"{int(quota_payload.get('sys_paid', {}).get('total', {}).get('usage', {}).get('requests', 0))} 次"),
            ("用户自费", f"{int(quota_payload.get('self_paid', {}).get('total', {}).get('usage', {}).get('requests', 0))} 次"),
        ]
        for index, (title, value) in enumerate(summary_items):
            block = ttk.Frame(summary, style="MutedCard.TFrame", padding=(self._scale(12), self._scale(10)))
            block.grid(row=0, column=index, sticky="nsew", padx=(0, self._scale(6) if index < len(summary_items) - 1 else 0))
            ttk.Label(block, text=title, style="MutedCaption.TLabel").pack(anchor=tk.W)
            ttk.Label(block, text=value, style="MutedValue.TLabel").pack(anchor=tk.W, pady=(self._scale(4), 0))

        detail_frame = ttk.Frame(content, style="Card.TFrame")
        detail_frame.grid(row=1, column=0, sticky="nsew")
        detail_frame.columnconfigure(0, weight=1)
        detail_frame.rowconfigure(0, weight=1)

        columns = ("platform", "display", "calls", "tokens", "prompt", "completion", "success", "error")
        detail_tree = ttk.Treeview(detail_frame, columns=columns, show="headings", height=12)
        detail_rows = list(stats_rows)
        detail_sort_state = {"column": "calls", "descending": True}
        detail_headings = {
            "platform": ("平台", self._scale(120)),
            "display": ("模型", self._scale(160)),
            "calls": ("调用", self._scale(60)),
            "tokens": ("总 Token", self._scale(88)),
            "prompt": ("Prompt", self._scale(76)),
            "completion": ("Completion", self._scale(88)),
            "success": ("成功", self._scale(60)),
            "error": ("错误", self._scale(60)),
        }

        def render_detail_rows(rows):
            for item_id in detail_tree.get_children():
                detail_tree.delete(item_id)
            for row in rows:
                detail_tree.insert(
                    "",
                    tk.END,
                    values=(
                        row.get("platform_name", "-"),
                        row.get("display_name", "-"),
                        int(row.get("call_count", 0)),
                        int(row.get("total_tokens", 0)),
                        int(row.get("prompt_tokens", 0)),
                        int(row.get("completion_tokens", 0)),
                        int(row.get("success_count", 0)),
                        int(row.get("error_count", 0)),
                    ),
                )

        def sort_detail_rows(column_key):
            if detail_sort_state["column"] == column_key:
                detail_sort_state["descending"] = not detail_sort_state["descending"]
            else:
                detail_sort_state["column"] = column_key
                detail_sort_state["descending"] = column_key not in {"platform", "display"}

            if column_key == "platform":
                sorted_rows = sorted(detail_rows, key=lambda row: str(row.get("platform_name", "")).lower(), reverse=detail_sort_state["descending"])
            elif column_key == "display":
                sorted_rows = sorted(detail_rows, key=lambda row: str(row.get("display_name", "")).lower(), reverse=detail_sort_state["descending"])
            else:
                metric_map = {
                    "calls": "call_count",
                    "tokens": "total_tokens",
                    "prompt": "prompt_tokens",
                    "completion": "completion_tokens",
                    "success": "success_count",
                    "error": "error_count",
                }
                sorted_rows = sorted(detail_rows, key=lambda row: int(row.get(metric_map[column_key], 0)), reverse=detail_sort_state["descending"])
            render_detail_rows(sorted_rows)

        for key, (title, width) in detail_headings.items():
            detail_tree.heading(key, text=title, command=lambda sort_key=key: sort_detail_rows(sort_key))
            detail_tree.column(key, width=width, anchor=tk.W if key in {"platform", "display"} else tk.CENTER, stretch=key in {"platform", "display"})
        render_detail_rows(sorted(detail_rows, key=lambda row: int(row.get("call_count", 0)), reverse=True))

        detail_scroll = ttk.Scrollbar(detail_frame, orient=tk.VERTICAL, command=detail_tree.yview)
        detail_tree.configure(yscrollcommand=detail_scroll.set)
        detail_tree.grid(row=0, column=0, sticky="nsew")
        detail_scroll.grid(row=0, column=1, sticky="ns")

        action_row = ttk.Frame(dialog, style="Card.TFrame", padding=(self._scale(16), 0, self._scale(16), self._scale(16)))
        action_row.grid(row=2, column=0, sticky="ew")
        ttk.Button(action_row, text="编辑额度", command=lambda uid=user_id: self.open_quota_manager_dialog(default_user_id=uid)).pack(side=tk.LEFT)
        ttk.Button(action_row, text="关闭", command=dialog.destroy).pack(side=tk.RIGHT)

    def open_current_user_quota_dialog(self):
        """打开当前选中用户的额度管理对话框。"""
        user_id = self._get_selected_user_id()
        if not user_id:
            messagebox.showwarning("提示", "请先在用户总览表格中选中一个用户")
            return
        self.open_quota_manager_dialog(default_user_id=user_id)

    def _build_model_panel(self, parent):
        """构建模型管理面板。"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        ttk.Label(parent, text="维护当前平台的已配置模型。支持拖拽排序，排序后的第一项更适合作为默认选择。", style="SurfaceMuted.TLabel", wraplength=self._scale(640), justify=tk.LEFT).grid(
            row=0, column=0, sticky="ew", pady=(0, self._scale(12))
        )

        list_frame = ttk.Frame(parent, style="Card.TFrame")
        list_frame.grid(row=1, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.model_listbox = tk.Listbox(list_frame, selectmode=tk.SINGLE)
        style_listbox(self.model_listbox, ui_scale=self.ui_scale)
        model_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.model_listbox.yview)
        self.model_listbox.configure(yscrollcommand=model_scroll.set)
        self.model_listbox.grid(row=0, column=0, sticky="nsew")
        model_scroll.grid(row=0, column=1, sticky="ns")

        self.model_listbox.bind("<ButtonPress-1>", self.on_model_drag_start)
        self.model_listbox.bind("<B1-Motion>", self.on_model_drag_motion)
        self.model_listbox.bind("<ButtonRelease-1>", self.on_model_drag_stop)

        btn_row = ttk.Frame(parent, style="Card.TFrame")
        btn_row.grid(row=2, column=0, sticky="ew", pady=(self._scale(12), self._scale(8)))
        for col in range(3):
            btn_row.columnconfigure(col, weight=1)
        ttk.Button(btn_row, text="新增模型", command=self.open_add_model_dialog).grid(row=0, column=0, sticky="ew")
        ttk.Button(btn_row, text="编辑模型", command=self.edit_model).grid(row=0, column=1, sticky="ew", padx=self._scale(8))
        ttk.Button(btn_row, text="删除模型", command=self.delete_model, style="Danger.TButton").grid(row=0, column=2, sticky="ew")

        test_row = ttk.Frame(parent, style="Card.TFrame")
        test_row.grid(row=3, column=0, sticky="ew")
        for col in range(3):
            test_row.columnconfigure(col, weight=1)
        ttk.Button(test_row, text="测试模型", command=self.test_model, style="Primary.TButton").grid(row=0, column=0, sticky="ew")
        ttk.Button(test_row, text="测试 Embedding", command=self.test_embedding).grid(row=0, column=1, sticky="ew", padx=self._scale(8))
        ttk.Button(test_row, text="流式测速", command=self.speed_test_model).grid(row=0, column=2, sticky="ew")

    def _build_right_panel(self, parent):
        """构建右侧工作区。"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=3)
        parent.rowconfigure(1, weight=2)

        notebook_card = ttk.Frame(parent, style="Card.TFrame", padding=self._scale(10))
        notebook_card.grid(row=0, column=0, sticky="nsew", pady=(0, self._scale(12)))
        notebook_card.columnconfigure(0, weight=1)
        notebook_card.rowconfigure(0, weight=1)

        notebook = ttk.Notebook(notebook_card)
        notebook.grid(row=0, column=0, sticky="nsew")

        model_tab = ttk.Frame(notebook, style="Card.TFrame", padding=self._scale(16))
        model_tab.columnconfigure(0, weight=1)
        model_tab.rowconfigure(1, weight=1)

        probe_tab = ttk.Frame(notebook, style="Card.TFrame", padding=self._scale(16))
        probe_tab.columnconfigure(0, weight=1)
        probe_tab.rowconfigure(1, weight=1)

        notebook.add(model_tab, text="已配置模型")
        notebook.add(probe_tab, text="模型探测")

        self._build_model_panel(model_tab)
        self._build_probe_panel(probe_tab)

        log_card = ttk.Frame(parent, style="Card.TFrame", padding=self._scale(16))
        log_card.grid(row=1, column=0, sticky="nsew")
        self._build_log_panel(log_card)

    def _build_probe_panel(self, parent):
        """构建探测面板。"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)

        ttk.Label(parent, text="探测兼容 OpenAI 协议的平台模型列表，并将结果一键加入当前平台。", style="SurfaceMuted.TLabel", wraplength=self._scale(640), justify=tk.LEFT).grid(
            row=0, column=0, sticky="ew", pady=(0, self._scale(12))
        )

        filter_row = ttk.Frame(parent, style="Card.TFrame")
        filter_row.grid(row=1, column=0, sticky="ew", pady=(0, self._scale(12)))
        filter_row.columnconfigure(1, weight=1)
        ttk.Label(filter_row, text="筛选", style="Surface.TLabel").grid(row=0, column=0, sticky=tk.W)
        self.filter_entry = ttk.Entry(filter_row)
        self.filter_entry.grid(row=0, column=1, sticky="ew", padx=self._scale(8))
        self.filter_entry.bind("<KeyRelease>", self.on_filter_change)
        ttk.Button(filter_row, text="清除", command=self.clear_filter).grid(row=0, column=2, sticky="e")

        list_frame = ttk.Frame(parent, style="Card.TFrame")
        list_frame.grid(row=2, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.probe_listbox = tk.Listbox(list_frame, selectmode=tk.SINGLE)
        style_listbox(self.probe_listbox, ui_scale=self.ui_scale)
        probe_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.probe_listbox.yview)
        self.probe_listbox.configure(yscrollcommand=probe_scroll.set)
        self.probe_listbox.grid(row=0, column=0, sticky="nsew")
        probe_scroll.grid(row=0, column=1, sticky="ns")

        btn_row = ttk.Frame(parent, style="Card.TFrame")
        btn_row.grid(row=3, column=0, sticky="ew", pady=(self._scale(12), 0))
        for col in range(3):
            btn_row.columnconfigure(col, weight=1)
        ttk.Button(btn_row, text="开始探测", command=self.probe_models, style="Primary.TButton").grid(row=0, column=0, sticky="ew")
        ttk.Button(btn_row, text="添加选中模型", command=self.open_add_model_dialog).grid(row=0, column=1, sticky="ew", padx=self._scale(8))
        ttk.Button(btn_row, text="按自定义名称添加", command=self.use_custom_model_name).grid(row=0, column=2, sticky="ew")

    def _build_log_panel(self, parent):
        """构建日志面板。"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        header = ttk.Frame(parent, style="Card.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, self._scale(10)))
        header.columnconfigure(0, weight=1)

        ttk.Label(header, text="操作日志", style="CardTitle.TLabel").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(header, text="记录探测、测试、导入导出与密钥处理过程。", style="SurfaceMuted.TLabel").grid(row=1, column=0, sticky=tk.W, pady=(self._scale(4), 0))
        ttk.Button(header, text="清空日志", command=self._clear_log).grid(row=0, column=1, rowspan=2, sticky="e")

        log_body = ttk.Frame(parent, style="Card.TFrame")
        log_body.grid(row=1, column=0, sticky="nsew")
        log_body.columnconfigure(0, weight=1)
        log_body.rowconfigure(0, weight=1)

        self.log_text = tk.Text(log_body, height=10, wrap=tk.WORD)
        style_text_widget(self.log_text, ui_scale=self.ui_scale)
        log_scroll = ttk.Scrollbar(log_body, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        log_scroll.grid(row=0, column=1, sticky="ns")

        self.log_text.tag_configure("success", foreground=COLORS["success"])
        self.log_text.tag_configure("error", foreground=COLORS["danger"])
        self.log_text.tag_configure("warning", foreground=COLORS["warning"])

    def _clear_log(self):
        """清空日志。"""
        self.log_text.delete("1.0", tk.END)

    def _update_overview_state(self):
        """更新头部状态与操作提示。"""
        platform_count = len(self.current_config)
        total_models = sum(len(cfg.get("models", {})) for cfg in self.current_config.values()) if self.current_config else 0

        if not self.current_config:
            self.header_status_var.set("当前尚未加载任何平台配置")
            self.workflow_hint_var.set("可以先从配置文件重置数据库，或直接新增平台并保存密钥后开始探测模型。")
            return

        platform_name = self._resolve_platform_name()
        if not platform_name or platform_name not in self.current_config:
            platform_name = next(iter(self.current_config.keys()), "")

        platform_cfg = self.current_config.get(platform_name, {})
        model_count = len(platform_cfg.get("models", {})) if platform_cfg else 0
        has_api_key = bool(platform_cfg.get("api_key"))

        self.header_status_var.set(
            f"已加载 {platform_count} 个平台 / {total_models} 个模型 · 当前平台：{platform_name or '未选择'} · API Key {'已保存' if has_api_key else '未保存'}"
        )
        self.workflow_hint_var.set(
            f"当前平台已有 {model_count} 个模型。建议先检查 URL 与 Key，再探测模型并完成测试。"
        )

    # ------------------------------------------------------------------ #
    #  日志                                                                  #
    # ------------------------------------------------------------------ #

    def log(self, message, tag=None):
        """向日志区域追加一行消息。"""
        if tag:
            self.log_text.insert(tk.END, f"{message}\n", tag)
        else:
            self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)

    # ------------------------------------------------------------------ #
    #  数据加载                                                              #
    # ------------------------------------------------------------------ #

    def load_config_from_db(self):
        """从数据库加载配置（不含已禁用/已删除的平台和模型）。"""
        try:
            platforms = self.ai_manager.admin_get_sys_platforms(
                include_disabled=False,
                include_models=True,
            )

            db_config = {}
            for p in platforms:
                p_name = p["name"]
                models = {}
                for m in p.get("models", []):
                    if bool(m.get("disabled")):
                        continue
                    display_name = m["display_name"]
                    model_cfg = {
                        "model_name": m["model_name"],
                        "is_embedding": bool(m["is_embedding"]),
                        "_db_id": m["_db_id"],
                        "sys_credit_price_per_million_tokens": m.get("sys_credit_price_per_million_tokens"),
                        "resolved_sys_credit_price_per_million_tokens": m.get("resolved_sys_credit_price_per_million_tokens"),
                    }
                    if m.get("temperature") is not None:
                        model_cfg["temperature"] = m["temperature"]
                    if m.get("extra_body"):
                        model_cfg["extra_body"] = m["extra_body"]
                    models[display_name] = model_cfg

                api_key_val = ""
                raw_key = p.get("api_key", "")
                if raw_key:
                    try:
                        api_key_val = self._decrypt_api_key_strict(raw_key)
                    except Exception:
                        api_key_val = ""

                db_config[p_name] = {
                    "base_url": p["base_url"],
                    "api_key": api_key_val,
                    "models": models,
                    "_db_id": p["platform_id"],
                }

            self.current_config = db_config
            self._refresh_platform_combo()

            if self.current_config:
                self.on_platform_selected()
            else:
                self.platform_var.set("")
                self.model_listbox.delete(0, tk.END)
                self.probe_listbox.delete(0, tk.END)
                for entry in (self.base_url_entry, self.platform_url_entry, self.api_key_entry):
                    entry.config(state="normal")
                    entry.delete(0, tk.END)
                    if entry is self.base_url_entry:
                        entry.config(state="readonly")

            self._update_overview_state()
            self.load_user_usage_overview(silent=True)
            self.log("✓ 已从数据库加载配置", tag="success")

        except Exception as e:
            messagebox.showerror("错误", f"从数据库加载失败: {e}")
            self.log(f"✗ 从数据库加载失败: {e}")

    def reload_from_yaml(self):
        """强制从配置文件重置数据库（调用后端 admin_reload_from_yaml）。"""
        if not messagebox.askyesno(
            "确认重置",
            "⚠️ 警告：这将使用 YAML 文件覆盖数据库中的所有系统平台配置！\n\n"
            "- 数据库中新增的平台将被删除\n"
            "- 平台名称和模型列表将重置为 YAML 中的状态\n"
            "- 用户的 API Key 设置不会受影响\n\n"
            "确定要继续吗？"
        ):
            return

        try:
            self.ai_manager.admin_reload_from_yaml()
            self.log("✓ 数据库已从配置文件重置", tag="success")
            messagebox.showinfo("成功", "数据库已重置。")
            self.load_config_from_db()
        except Exception as e:
            messagebox.showerror("错误", f"重置失败: {e}")
            self.log(f"✗ 重置失败: {e}")

    def export_db_to_yaml(self):
        """导出数据库配置到 YAML（调用后端 admin_export_to_yaml）。"""
        if not messagebox.askyesno(
            "确认导出",
            "这将覆盖当前的 llm_mgr_cfg.yaml 文件。\n确定要导出数据库配置吗？"
        ):
            return

        try:
            path = self.ai_manager.admin_export_to_yaml()
            self.log(f"✓ 已导出配置到 {path}", tag="success")
            messagebox.showinfo("成功", f"已导出到 {path}")
        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {e}")
            self.log(f"✗ 导出失败: {e}")

    # ------------------------------------------------------------------ #
    #  内部工具（覆盖 Mixin 中的简化版本，使用更精确的索引匹配）               #
    # ------------------------------------------------------------------ #

    def _resolve_platform_name(self, platform_value=None):
        """将下拉框显示值解析为实际平台 key（优先使用索引）。"""
        current_index = self.platform_combo.current() if hasattr(self, "platform_combo") else -1
        if isinstance(current_index, int) and 0 <= current_index < len(self.platform_keys_in_order):
            return self.platform_keys_in_order[current_index]

        raw_value = (platform_value if platform_value is not None else self.platform_var.get()).strip()
        if not raw_value:
            return ""
        if raw_value in self.current_config:
            return raw_value
        if raw_value in self.platform_display_to_key:
            return self.platform_display_to_key[raw_value]
        return raw_value

    def _refresh_platform_combo(self, selected_platform_name=None):
        """刷新平台下拉框内容（仅展示未删除的平台）。"""
        platform_names = list(self.current_config.keys()) if self.current_config else []
        self.platform_display_to_key = {}
        self.platform_keys_in_order = list(platform_names)

        self.platform_combo["values"] = platform_names
        for name in platform_names:
            self.platform_display_to_key[name] = name

        target_name = selected_platform_name if selected_platform_name in self.current_config else ""
        if not target_name and platform_names:
            target_name = platform_names[0]

        if target_name:
            target_index = self.platform_keys_in_order.index(target_name)
            self.platform_combo.current(target_index)
        else:
            self.platform_var.set("")

    def _decrypt_api_key_strict(self, api_key_val: str) -> str:
        """严格解密 API Key，要求必须得到可用明文。"""
        if not api_key_val:
            return ""
        if not isinstance(api_key_val, str):
            raise ValueError("API Key 数据类型错误")

        text = api_key_val.strip()
        if not text:
            return ""

        sec_mgr = SecurityManager.get_instance()
        result = sec_mgr.decrypt(text)
        if result.has_plaintext:
            return result.value
        if result.is_missing_key:
            raise ValueError("检测到加密 API Key，但当前未设置 LLM_KEY")
        raise ValueError("API Key 解密失败，请检查 LLM_KEY 或重新配置密钥")

    def _get_probe_cache_key(self, platform_name, base_url, api_key):
        """生成探测缓存 key。"""
        if not platform_name or not base_url or not api_key:
            return None
        return f"{platform_name}::{base_url}::{api_key}"

    def _invalidate_probe_cache(self, platform_name=None):
        """清除探测缓存。"""
        if not platform_name:
            self.probe_models_cache.clear()
            return
        keys_to_remove = [k for k in self.probe_models_cache.keys() if k.startswith(f"{platform_name}::")]
        for k in keys_to_remove:
            del self.probe_models_cache[k]


def main():
    """主函数：启动 GUI。"""
    enable_high_dpi_awareness()
    root = tk.Tk()
    LLMConfigGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
