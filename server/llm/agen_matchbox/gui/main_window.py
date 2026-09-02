"""
主窗口 — LLMConfigGUI 主类，混入所有 Mixin，构建现代化 Flet 0.28.3 响应式布局。
"""
from __future__ import annotations

import datetime
import os
import sys
from pathlib import Path
from typing import Callable, Optional
import flet as ft

if __package__ in (None, "", "gui"):
    _component_dir = Path(__file__).resolve().parents[1]
    for _import_root in (_component_dir.parent.parent, _component_dir.parent):
        _import_root_text = str(_import_root)
        if _import_root_text not in sys.path:
            sys.path.insert(0, _import_root_text)
    __package__ = f"{_component_dir.name}.gui"

from ..manager import AIManager
from ..security import SecurityManager
from .dialogs import DialogsMixin
from .dpi import configure_page_window, enable_high_dpi_awareness
from .key_manager import KeyManagerMixin
from .model_panel import ModelPanelMixin
from .platform_panel import PlatformPanelMixin
from .probe import ProbeMixin
from .theme import COLORS, create_theme


class LLMConfigGUI(
    PlatformPanelMixin,
    ModelPanelMixin,
    DialogsMixin,
    KeyManagerMixin,
    ProbeMixin,
):
    """LLM 配置管理器主界面。"""

    def __init__(
        self,
        page: ft.Page,
        *,
        schema_initializer: Optional[Callable[[AIManager], None]] = None,
        auto_bootstrap: bool = True,
    ):
        self.page = page
        self._schema_initializer = schema_initializer

        self.current_config: dict = {}
        self.probe_models_cache: dict = {}
        self.platform_display_to_key: dict = {}
        self.platform_keys_in_order: list = []
        self.last_selected_platform_name: str = ""
        self.user_usage_rows: list = []
        self.user_usage_sort_column: str = "requests"
        self.user_usage_sort_descending: bool = True
        self.selected_model_display_name: str = ""
        self.selected_probe_model_id: str = ""

        try:
            self.ai_manager = AIManager()
        except Exception as e:
            if hasattr(self.page, "open"):
                self.show_error("初始化失败", f"AIManager 初始化失败: {e}")
            raise

        self._init_controls()
        configure_page_window(
            self.page,
            title="火柴Agent网关 · LLM 配置台",
            width=1460,
            height=900,
            min_width=1180,
            min_height=740,
        )
        self.page.theme = create_theme()
        self.page.theme_mode = ft.ThemeMode.LIGHT

        self._build_ui()

        if auto_bootstrap:
            self._bootstrap_startup()

    # ------------------------------------------------------------------ #
    #  基础工具与格式化                                                     #
    # ------------------------------------------------------------------ #

    def _scale(self, value: int) -> int:
        return value

    @staticmethod
    def _fmt_tokens(n) -> str:
        """将 Token 数格式化为 K / M 缩写，精确到小数点 3 位。"""
        try:
            n = int(n)
        except (TypeError, ValueError):
            return str(n)
        if n >= 1_000_000:
            return f"{n / 1_000_000:.3f}M"
        if n >= 1_000:
            return f"{n / 1_000:.3f}K"
        return str(n)

    # ------------------------------------------------------------------ #
    #  通用提示与弹窗辅助                                                   #
    # ------------------------------------------------------------------ #

    def show_info(self, title: str, message: str, on_ok=None):
        """显示信息弹窗。"""
        def handle_ok(e):
            self.page.close(dlg)
            if on_ok:
                on_ok()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row([ft.Icon(ft.Icons.INFO_OUTLINE, color=ft.Colors.BLUE_600), ft.Text(title)]),
            content=ft.Text(message, selectable=True),
            actions=[ft.ElevatedButton("确定", on_click=handle_ok)],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.open(dlg)

    def show_error(self, title: str, message: str):
        """显示错误弹窗。"""
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row([ft.Icon(ft.Icons.ERROR_OUTLINE, color=ft.Colors.RED_600), ft.Text(title)]),
            content=ft.Text(message, selectable=True),
            actions=[ft.ElevatedButton("确定", on_click=lambda e: self.page.close(dlg))],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.open(dlg)

    def show_warning(self, title: str, message: str):
        """显示警告弹窗。"""
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row([ft.Icon(ft.Icons.WARNING_AMBER_OUTLINED, color=ft.Colors.AMBER_700), ft.Text(title)]),
            content=ft.Text(message, selectable=True),
            actions=[ft.ElevatedButton("确定", on_click=lambda e: self.page.close(dlg))],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.open(dlg)

    def ask_yes_no(self, title: str, message: str, on_yes, on_no=None):
        """显示确认弹窗。"""
        def handle_yes(e):
            self.page.close(dlg)
            if on_yes:
                on_yes()

        def handle_no(e):
            self.page.close(dlg)
            if on_no:
                on_no()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row([ft.Icon(ft.Icons.HELP_OUTLINE, color=ft.Colors.BLUE_700), ft.Text(title)]),
            content=ft.Text(message, selectable=True),
            actions=[
                ft.TextButton("取消", on_click=handle_no),
                ft.ElevatedButton("确定", on_click=handle_yes),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.open(dlg)

    def show_snack(self, message: str):
        """底部轻提示。"""
        snack = ft.SnackBar(content=ft.Text(message), duration=2500)
        self.page.open(snack)

    # ------------------------------------------------------------------ #
    #  控件初始化与 UI 构建                                                 #
    # ------------------------------------------------------------------ #

    def _init_controls(self):
        """预实例化各核心输入与显示控件。"""
        # 头部状态
        self.header_status_text = ft.Text("等待初始化配置环境", size=12, color=ft.Colors.BLUE_700, weight=ft.FontWeight.W_500)
        self.user_usage_status_text = ft.Text("点击列头可排序；双击用户行查看详情与配额。", size=12, color=ft.Colors.GREY_700)

        # 平台控件
        self.platform_dropdown = ft.Dropdown(
            label="当前平台",
            options=[],
            on_change=lambda e: self.on_platform_selected(),
            dense=True,
            expand=True,
        )
        self.platform_url_entry = ft.TextField(
            label="Base URL",
            hint_text="例如: https://api.openai.com/v1",
            dense=True,
        )
        self.base_url_entry = self.platform_url_entry  # 兼容所有既有属性引用
        self.recharge_url_entry = ft.TextField(label="充值地址", dense=True)
        self.api_key_entry = ft.TextField(label="API Key", password=True, can_reveal_password=True, dense=True)

        # 模型列表控件 (支持拖拽排序，关闭原生重复把手)
        self.model_list_view = ft.ReorderableListView(
            on_reorder=self._on_model_reorder,
            expand=True,
            padding=6,
            show_default_drag_handles=False,
        )

        # 探测控件与多选状态
        self.selected_probe_model_ids = set()
        self.last_clicked_probe_index = None
        self._current_rendered_probe_models = []
        self.is_ctrl_pressed = False
        self.is_shift_pressed = False

        self.btn_add_probe_models = ft.OutlinedButton(
            "添加选中模型",
            icon=ft.Icons.ADD_LINK,
            on_click=lambda e: self.add_selected_probe_models(),
            height=36,
        )

        self.filter_entry = ft.TextField(
            label="筛选模型",
            hint_text="输入关键词过滤...",
            prefix_icon=ft.Icons.SEARCH,
            suffix=ft.IconButton(icon=ft.Icons.CLEAR, tooltip="清除筛选", on_click=lambda e: self.clear_filter()),
            on_change=self.on_filter_change,
            dense=True,
            expand=True,
        )
        self.probe_list_view = ft.ListView(expand=True, spacing=4)

        # 用户总览表格
        self.user_usage_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("用户 ID"), on_sort=lambda e: self.sort_user_usage_overview("user_id")),
                ft.DataColumn(ft.Text("调用"), numeric=True, on_sort=lambda e: self.sort_user_usage_overview("requests")),
                ft.DataColumn(ft.Text("总 Token"), numeric=True, on_sort=lambda e: self.sort_user_usage_overview("tokens")),
                ft.DataColumn(ft.Text("Prompt"), numeric=True, on_sort=lambda e: self.sort_user_usage_overview("prompt")),
                ft.DataColumn(ft.Text("Completion"), numeric=True, on_sort=lambda e: self.sort_user_usage_overview("completion")),
                ft.DataColumn(ft.Text("站长付费"), numeric=True, on_sort=lambda e: self.sort_user_usage_overview("sys_paid")),
                ft.DataColumn(ft.Text("用户自费"), numeric=True, on_sort=lambda e: self.sort_user_usage_overview("self_paid")),
                ft.DataColumn(ft.Text("错误"), numeric=True, on_sort=lambda e: self.sort_user_usage_overview("errors")),
                ft.DataColumn(ft.Text("操作")),
            ],
            rows=[],
            heading_row_height=40,
            data_row_min_height=36,
            data_row_max_height=42,
        )

        # 日志控件
        self.log_list_view = ft.ListView(expand=True, spacing=2, auto_scroll=True)

    def _build_ui(self):
        """构建主界面整体布局。"""
        self.page.clean()
        self.page.padding = 16
        self.page.spacing = 10

        # 监听全局键盘事件以支持 Ctrl / Shift 组合按键
        def on_keyboard(e: ft.KeyboardEvent):
            self.is_ctrl_pressed = bool(e.ctrl or e.meta)
            self.is_shift_pressed = bool(e.shift)

        self.page.on_keyboard_event = on_keyboard

        # 监听断开或关闭事件（纯数据层静默保存兜底）
        def on_disconnect(e):
            try:
                self.save_platform_config(silent=True, skip_ui_update=True)
            except Exception:
                pass

        self.page.on_disconnect = on_disconnect

        # 1. 顶部 Header
        header = self._build_header()

        # 2. 中间工作台（左侧平台设置 420px，右侧多标签工作区铺满）
        workspace = self._build_workspace()

        # 3. 底部操作日志（调高默认高度至 240px，便于舒适查看日志信息）
        log_panel = self._build_log_panel()

        self.page.add(
            ft.Column(
                [
                    header,
                    ft.Container(content=workspace, expand=True),
                    ft.Container(content=log_panel, height=240),
                ],
                expand=True,
                spacing=10,
            )
        )
        self.page.update()

    def _build_header(self) -> ft.Control:
        """构建顶部品牌与操作按钮栏。"""
        brand_col = ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.HUB_ROUNDED, color=ft.Colors.BLUE_700, size=24),
                        ft.Text("火柴Agent网关 · LLM 配置台", size=17, weight=ft.FontWeight.BOLD),
                    ],
                    spacing=8,
                    tight=True,
                ),
                self.header_status_text,
            ],
            spacing=3,
            tight=True,
        )

        actions_row = ft.Row(
            [
                ft.ElevatedButton("刷新配置", icon=ft.Icons.REFRESH, on_click=lambda e: self.load_config_from_db(), height=36),
                ft.OutlinedButton("系统用途", icon=ft.Icons.TUNE_OUTLINED, on_click=lambda e: self.edit_system_model(), height=36),
                ft.OutlinedButton("用户配额", icon=ft.Icons.ADMIN_PANEL_SETTINGS_OUTLINED, on_click=lambda e: self.open_quota_manager_dialog(), height=36),
                ft.OutlinedButton("设置主密钥", icon=ft.Icons.KEY_OUTLINED, on_click=lambda e: self.open_set_llm_key_dialog(), height=36),
                ft.PopupMenuButton(
                    icon=ft.Icons.MORE_HORIZ,
                    tooltip="高级 / YAML 操作",
                    items=[
                        ft.PopupMenuItem(text="从配置文件重置 (YAML)", icon=ft.Icons.RESTORE_PAGE_OUTLINED, on_click=lambda e: self.reload_from_yaml()),
                        ft.PopupMenuItem(text="导出配置到文件 (YAML)", icon=ft.Icons.FILE_DOWNLOAD_OUTLINED, on_click=lambda e: self.export_db_to_yaml()),
                    ],
                ),
            ],
            spacing=8,
            wrap=False,
        )

        return ft.Card(
            content=ft.Container(
                content=ft.Row([brand_col, actions_row], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=False),
                padding=12,
            )
        )

    def _build_workspace(self) -> ft.Control:
        """构建中间工作区（两栏自适应）。"""
        left_panel = self._build_platform_panel()
        right_panel = self._build_tabs_panel()

        return ft.Row(
            [
                ft.Container(content=left_panel, width=420),
                ft.VerticalDivider(width=1),
                ft.Container(content=right_panel, expand=True),
            ],
            expand=True,
            spacing=10,
        )

    def _build_platform_panel(self) -> ft.Control:
        """构建左侧平台管理卡片。"""
        return ft.Card(
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.DNS_OUTLINED, color=ft.Colors.BLUE_700, size=20),
                                ft.Text("平台配置", size=14, weight=ft.FontWeight.BOLD),
                            ],
                            spacing=6,
                        ),
                        ft.Row([self.platform_dropdown], expand=False),
                        self.platform_url_entry,
                        self.recharge_url_entry,
                        self.api_key_entry,
                        ft.Divider(height=1),
                        ft.Row(
                            [
                                ft.ElevatedButton("+ 新增平台", on_click=lambda e: self.add_platform(), expand=True, height=36),
                                ft.OutlinedButton("重命名", icon=ft.Icons.EDIT_NOTE, on_click=lambda e: self.rename_platform(), expand=True, height=36),
                                ft.OutlinedButton(
                                    "禁用平台",
                                    icon=ft.Icons.DELETE_OUTLINE,
                                    on_click=lambda e: self.delete_platform(),
                                    style=ft.ButtonStyle(color=ft.Colors.RED_600),
                                    expand=True,
                                    height=36,
                                ),
                            ],
                            spacing=6,
                        ),
                        ft.Row(
                            [
                                ft.OutlinedButton(
                                    "设为系统默认平台",
                                    icon=ft.Icons.STAR_BORDER,
                                    on_click=lambda e: self.set_as_default(),
                                    expand=True,
                                    height=38,
                                ),
                                ft.ElevatedButton(
                                    "保存配置",
                                    icon=ft.Icons.SAVE_OUTLINED,
                                    on_click=lambda e: self.save_platform_config(),
                                    expand=True,
                                    height=38,
                                ),
                            ],
                            spacing=8,
                        ),
                    ],
                    spacing=9,
                    scroll=ft.ScrollMode.AUTO,
                ),
                padding=14,
            )
        )

    def _build_tabs_panel(self) -> ft.Control:
        """构建右侧三标签卡片。"""
        # Tab 1: 已配置模型
        model_tab_content = ft.Column(
            [
                ft.Row(
                    [
                        ft.Row(
                            [
                                ft.ElevatedButton("+ 新增模型", on_click=lambda e: self.open_add_model_dialog(), height=36),
                                ft.OutlinedButton("编辑模型", icon=ft.Icons.EDIT_OUTLINED, on_click=lambda e: self.edit_model(), height=36),
                                ft.OutlinedButton("删除模型", icon=ft.Icons.DELETE_OUTLINE, on_click=lambda e: self.delete_model(), style=ft.ButtonStyle(color=ft.Colors.RED_600), height=36),
                            ],
                            spacing=6,
                            wrap=False,
                        ),
                        ft.Container(
                            content=ft.Row(
                                [
                                    ft.Icon(ft.Icons.SWAP_VERT, size=15, color=ft.Colors.BLUE_700),
                                    ft.Text("上下拖动卡片可调整优先级 · 首位模型缺省优先", size=11, color=ft.Colors.BLUE_900),
                                ],
                                spacing=4,
                                tight=True,
                            ),
                            padding=ft.padding.symmetric(horizontal=10, vertical=4),
                            bgcolor=ft.Colors.BLUE_50,
                            border=ft.border.all(1, ft.Colors.BLUE_200),
                            border_radius=14,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    wrap=True,
                ),
                ft.Container(
                    content=self.model_list_view,
                    expand=True,
                    border=ft.border.all(1, ft.Colors.GREY_300),
                    border_radius=6,
                    padding=4,
                ),
            ],
            expand=True,
            spacing=8,
        )

        # Tab 2: 模型探测
        probe_tab_content = ft.Column(
            [
                ft.Row(
                    [
                        self.filter_entry,
                        ft.ElevatedButton("开始探测", icon=ft.Icons.RADAR, on_click=lambda e: self.probe_models(), height=36),
                        self.btn_add_probe_models,
                        ft.OutlinedButton("按自定义名称添加", icon=ft.Icons.TEXT_FIELDS, on_click=lambda e: self.use_custom_model_name(), height=36),
                        ft.TextButton("全选", on_click=lambda e: self.select_all_probe_models()),
                        ft.TextButton("清空选择", on_click=lambda e: self.clear_probe_selection()),
                    ],
                    spacing=6,
                    wrap=False,
                ),
                ft.Container(content=self.probe_list_view, expand=True, border=ft.border.all(1, ft.Colors.GREY_300), border_radius=6, padding=4),
            ],
            expand=True,
            spacing=8,
        )

        # Tab 3: 用户调用总览
        user_usage_content = ft.Column(
            [
                ft.Row([self.user_usage_status_text, ft.OutlinedButton("刷新数据", icon=ft.Icons.REFRESH, on_click=lambda e: self.load_user_usage_overview(), height=32)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Container(
                    content=ft.Row([self.user_usage_table], scroll=ft.ScrollMode.AUTO, expand=True),
                    expand=True,
                    border=ft.border.all(1, ft.Colors.GREY_300),
                    border_radius=6,
                ),
            ],
            expand=True,
            spacing=8,
        )

        tabs = ft.Tabs(
            selected_index=0,
            animation_duration=200,
            tabs=[
                ft.Tab(text="已配置模型", icon=ft.Icons.SETTINGS_SUGGEST_OUTLINED, content=model_tab_content),
                ft.Tab(text="模型探测", icon=ft.Icons.EXPLORE_OUTLINED, content=probe_tab_content),
                ft.Tab(text="用户调用总览", icon=ft.Icons.PEOPLE_ALT_OUTLINED, content=user_usage_content),
            ],
            expand=True,
        )

        return ft.Card(content=ft.Container(content=tabs, padding=10, expand=True), expand=True)

    def _build_log_panel(self) -> ft.Control:
        """构建底部操作日志面板。"""
        return ft.Card(
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Row([ft.Icon(ft.Icons.TERMINAL, size=16, color=ft.Colors.BLUE_700), ft.Text("系统操作日志", size=13, weight=ft.FontWeight.BOLD)], spacing=6),
                                ft.TextButton("清空日志", icon=ft.Icons.CLEAR_ALL, on_click=lambda e: self._clear_log()),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.Container(
                            content=self.log_list_view,
                            expand=True,
                            bgcolor=ft.Colors.GREY_50,
                            border=ft.border.all(1, ft.Colors.GREY_200),
                            border_radius=6,
                            padding=6,
                        ),
                    ],
                    expand=True,
                    spacing=4,
                ),
                padding=ft.padding.symmetric(horizontal=12, vertical=8),
                expand=True,
            ),
            expand=True,
        )

    # ------------------------------------------------------------------ #
    #  日志记录与清理                                                        #
    # ------------------------------------------------------------------ #

    def log(self, message: str, tag: str | None = None):
        """向日志列表追加一行格式化消息。"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        color = ft.Colors.BLACK87
        if tag == "success":
            color = ft.Colors.GREEN_700
        elif tag == "error":
            color = ft.Colors.RED_700
        elif tag == "warning":
            color = ft.Colors.AMBER_800

        self.log_list_view.controls.append(
            ft.Text(f"[{timestamp}] {message}", color=color, size=12, selectable=True)
        )
        if len(self.log_list_view.controls) > 300:
            self.log_list_view.controls.pop(0)
        self.page.update()

    def _clear_log(self):
        """清空日志列表。"""
        self.log_list_view.controls.clear()
        self.page.update()

    # ------------------------------------------------------------------ #
    #  启动与初始化                                                         #
    # ------------------------------------------------------------------ #

    def _bootstrap_startup(self):
        """启动自检：强制主密钥、建表初始化、再加载数据库配置。"""
        try:
            if not self._ensure_master_key_ready_on_startup():
                return
            self._bootstrap_startup_continue()
        except Exception as e:
            self.show_error("初始化失败", f"GUI 启动失败: {e}")

    def _bootstrap_startup_continue(self):
        """主密钥就绪后的初始化链路。"""
        try:
            if self._schema_initializer is None:
                self.ai_manager.ensure_schema()
            else:
                self._schema_initializer(self.ai_manager)
            self.ai_manager.initialize_defaults()
            self.load_config_from_db()
        except Exception as e:
            self.show_error("初始化失败", f"配置环境初始化失败: {e}")

    # ------------------------------------------------------------------ #
    #  数据加载与配置重载                                                   #
    # ------------------------------------------------------------------ #

    def load_config_from_db(self):
        """从数据库加载配置。"""
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
                        "input_modalities": m.get("input_modalities", ["text"]),
                        "output_modalities": m.get("output_modalities", ["text"]),
                        "_db_id": m["_db_id"],
                        "max_context_tokens": m.get("max_context_tokens", 256000),
                        "max_output_tokens": m.get("max_output_tokens", 64000),
                        "sys_credit_input_price_per_million": m.get("sys_credit_input_price_per_million"),
                        "sys_credit_cached_input_price_per_million": m.get("sys_credit_cached_input_price_per_million"),
                        "sys_credit_output_price_per_million": m.get("sys_credit_output_price_per_million"),
                    }
                    if m.get("image_generation_adapter"):
                        model_cfg["image_generation_adapter"] = m["image_generation_adapter"]
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
                    "recharge_url": p.get("recharge_url") or "",
                    "api_key": api_key_val,
                    "models": models,
                    "_db_id": p["platform_id"],
                }

            self.current_config = db_config
            self._refresh_platform_combo()

            if self.current_config:
                self.on_platform_selected()
            else:
                self.platform_dropdown.value = None
                self.model_list_view.controls.clear()
                self.probe_list_view.controls.clear()
                self.base_url_entry.value = ""
                self.platform_url_entry.value = ""
                self.recharge_url_entry.value = ""
                self.api_key_entry.value = ""

            self._update_overview_state()
            self.load_user_usage_overview(silent=True)
            self.log("✓ 已从数据库加载配置", tag="success")
            self.page.update()

        except Exception as e:
            self.log(f"✗ 从数据库加载失败: {e}", tag="error")
            self.show_error("错误", f"从数据库加载失败: {e}")

    def reload_from_yaml(self):
        """从本地 YAML 文件重置数据库。"""
        def do_reset():
            try:
                self.ai_manager.admin_reload_from_yaml()
                self.log("✓ 数据库已从配置文件重置", tag="success")
                self.show_snack("数据库配置已从 YAML 成功重置！")
                self.load_config_from_db()
            except Exception as e:
                self.log(f"✗ 重置失败: {e}", tag="error")
                self.show_error("错误", f"重置失败: {e}")

        self.ask_yes_no(
            "确认重置",
            "⚠️ 警告：这将使用 YAML 文件重置数据库中的系统平台配置！\n\n- YAML 中不存在的平台将被软禁用\n- 平台名称和模型列表将重置为 YAML 中的状态\n- 用户的 API Key 设置不会受影响\n\n确定要继续吗？",
            on_yes=do_reset,
        )

    def export_db_to_yaml(self):
        """导出当前数据库配置至 YAML。"""
        def do_export():
            try:
                paths = self.ai_manager.admin_save_to_yaml()
                cfg_path = paths.get("config_path", paths) if isinstance(paths, dict) else paths
                key_path = paths.get("key_path", "") if isinstance(paths, dict) else ""
                self.log(f"✓ 已导出配置到 {cfg_path}", tag="success")
                if key_path:
                    self.log(f"✓ 已导出密钥到 {key_path}", tag="success")
                self.show_info("导出成功", f"配置已导出至:\n{cfg_path}\n{key_path}")
            except Exception as e:
                self.log(f"✗ 导出失败: {e}", tag="error")
                self.show_error("错误", f"导出失败: {e}")

        self.ask_yes_no(
            "确认导出",
            "这将覆盖当前的 matchbox_cfg.yaml 和 matchbox_key.yaml 文件。\n确定要导出数据库配置吗？",
            on_yes=do_export,
        )

    # ------------------------------------------------------------------ #
    #  用户用量总览表格                                                      #
    # ------------------------------------------------------------------ #

    def load_user_usage_overview(self, silent=False):
        """加载全部用户的调用总览。"""
        try:
            self.user_usage_rows = self.ai_manager.get_users_usage_overview()
            self.sort_user_usage_overview(self.user_usage_sort_column, toggle=False, descending=self.user_usage_sort_descending)
            count = len(self.user_usage_rows)
            if count:
                self.user_usage_status_text.value = f"共 {count} 个用户有调用记录；点击列头可排序，双击用户行或点击“明细”查看详情与配置额度。"
            else:
                self.user_usage_status_text.value = "当前暂无用户调用记录。"
            self.log("✓ 已刷新全部用户调用总览", tag="success")
            self.page.update()
        except Exception as exc:
            self.log(f"✗ 加载用户总览失败: {exc}", tag="error")
            self.user_usage_status_text.value = f"加载用户总览失败: {exc}"
            if not silent:
                self.show_error("错误", f"加载用户总览失败: {exc}")

    def sort_user_usage_overview(self, column_key: str, toggle: bool = True, descending: bool | None = None):
        """对用户总览按指定列进行排序。"""
        if not self.user_usage_rows:
            self.user_usage_table.rows.clear()
            self.page.update()
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

        desc = self.user_usage_sort_descending
        if self.user_usage_sort_column == "user_id":
            sorted_rows = sorted(self.user_usage_rows, key=lambda r: str(r.get("user_id", "")).lower(), reverse=desc)
        else:
            sorted_rows = sorted(self.user_usage_rows, key=lambda r: int(r.get(data_key, 0)), reverse=desc)

        self._render_user_usage_table_rows(sorted_rows)

    def _render_user_usage_table_rows(self, rows: list):
        """渲染用户用量表格行。"""
        self.user_usage_table.rows.clear()
        for r in rows:
            uid = str(r.get("user_id", "-"))
            detail_btn = ft.IconButton(
                icon=ft.Icons.VISIBILITY_OUTLINED,
                tooltip="查看明细与配额",
                on_click=lambda e, u=uid: self.open_user_usage_detail_dialog(u),
            )
            self.user_usage_table.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(uid, weight=ft.FontWeight.BOLD), on_double_tap=lambda e, u=uid: self.open_user_usage_detail_dialog(u)),
                        ft.DataCell(ft.Text(str(int(r.get("requests", 0))))),
                        ft.DataCell(ft.Text(self._fmt_tokens(r.get("total_tokens", 0)))),
                        ft.DataCell(ft.Text(self._fmt_tokens(r.get("prompt_tokens", 0)))),
                        ft.DataCell(ft.Text(self._fmt_tokens(r.get("completion_tokens", 0)))),
                        ft.DataCell(ft.Text(str(int(r.get("sys_paid_requests", 0))))),
                        ft.DataCell(ft.Text(str(int(r.get("self_paid_requests", 0))))),
                        ft.DataCell(ft.Text(str(int(r.get("errors", 0))))),
                        ft.DataCell(detail_btn),
                    ]
                )
            )
        self.page.update()

    # ------------------------------------------------------------------ #
    #  模型与探测列表渲染                                                   #
    # ------------------------------------------------------------------ #

    def _refresh_model_list_view(self):
        """刷新已配置模型列表视图。"""
        self.model_list_view.controls.clear()
        platform_name = self._resolve_platform_name()
        if not platform_name or platform_name not in self.current_config:
            self.page.update()
            return

        models = self.current_config[platform_name].get("models", {})
        for d_name, m_cfg in models.items():
            formatted_text = self._format_model_list_item(d_name, m_cfg)
            is_selected = d_name == self.selected_model_display_name

            def on_tile_click(e, name=d_name):
                self.selected_model_display_name = name
                self._refresh_model_list_view()

            # 智能判断模型能力：文本对话 vs 向量嵌入
            _, out_modalities = self._model_modalities_from_config(m_cfg)
            is_embedding = (
                "embedding" in out_modalities
                or (isinstance(m_cfg, dict) and "embedding" in str(m_cfg.get("model_name", "")).lower())
                or "embedding" in d_name.lower()
            )

            # 动态构建该项专属的操作按钮
            action_buttons = []
            if is_embedding:
                action_buttons.append(
                    ft.IconButton(
                        icon=ft.Icons.TRANSFORM_OUTLINED,
                        tooltip="测试向量",
                        icon_size=18,
                        icon_color=ft.Colors.TEAL_600,
                        on_click=lambda e, n=d_name: [setattr(self, "selected_model_display_name", n), self.test_embedding(target_display_name=n)],
                    )
                )
            else:
                action_buttons.extend([
                    ft.IconButton(
                        icon=ft.Icons.CHAT_OUTLINED,
                        tooltip="对话测试",
                        icon_size=18,
                        icon_color=ft.Colors.BLUE_600,
                        on_click=lambda e, n=d_name: [setattr(self, "selected_model_display_name", n), self.test_model(target_display_name=n)],
                    ),
                    ft.IconButton(
                        icon=ft.Icons.SPEED_OUTLINED,
                        tooltip="速度测试",
                        icon_size=18,
                        icon_color=ft.Colors.PURPLE_600,
                        on_click=lambda e, n=d_name: [setattr(self, "selected_model_display_name", n), self.speed_test_model(target_display_name=n)],
                    ),
                ])

            action_buttons.extend([
                ft.IconButton(
                    icon=ft.Icons.EDIT_OUTLINED,
                    tooltip="编辑模型",
                    icon_size=18,
                    on_click=lambda e, n=d_name: [setattr(self, "selected_model_display_name", n), self.edit_model()],
                ),
                ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    tooltip="删除模型",
                    icon_size=18,
                    icon_color=ft.Colors.RED_500,
                    on_click=lambda e, n=d_name: [setattr(self, "selected_model_display_name", n), self.delete_model()],
                ),
            ])

            card = ft.Container(
                content=ft.ListTile(
                    leading=ft.Icon(ft.Icons.DRAG_HANDLE, color=ft.Colors.GREY_400, size=22),
                    title=ft.Text(d_name, weight=ft.FontWeight.BOLD if is_selected else ft.FontWeight.W_500, size=14),
                    subtitle=ft.Text(formatted_text, size=12, color=ft.Colors.GREY_700),
                    trailing=ft.Row(
                        action_buttons,
                        tight=True,
                        spacing=2,
                    ),
                    dense=True,
                    on_click=on_tile_click,
                ),
                bgcolor=ft.Colors.BLUE_50 if is_selected else ft.Colors.WHITE,
                border=ft.border.all(1.5 if is_selected else 1, ft.Colors.BLUE_500 if is_selected else ft.Colors.GREY_200),
                border_radius=8,
                padding=ft.padding.symmetric(horizontal=4, vertical=2),
                data=d_name,
            )
            self.model_list_view.controls.append(card)
        self.page.update()

    def _on_model_reorder(self, e: ft.OnReorderEvent):
        """响应模型拖拽排序事件。"""
        item = self.model_list_view.controls.pop(e.old_index)
        self.model_list_view.controls.insert(e.new_index, item)
        self.reorder_models()
        self.page.update()

    def _is_ctrl_pressed(self) -> bool:
        """检测当前是否按下了 Ctrl 键（或 Mac 上的 Command/Meta 键）。"""
        if sys.platform == "win32":
            try:
                import ctypes
                if bool(ctypes.windll.user32.GetKeyState(0x11) & 0x8000):
                    return True
            except Exception:
                pass
        return getattr(self, "is_ctrl_pressed", False)

    def _is_shift_pressed(self) -> bool:
        """检测当前是否按下了 Shift 键。"""
        if sys.platform == "win32":
            try:
                import ctypes
                if bool(ctypes.windll.user32.GetKeyState(0x10) & 0x8000):
                    return True
            except Exception:
                pass
        return getattr(self, "is_shift_pressed", False)

    def _update_probe_controls_state(self):
        """根据当前选中的探测模型数量更新操作按钮提示与状态。"""
        if not hasattr(self, "btn_add_probe_models") or self.btn_add_probe_models is None:
            return
        sel_count = len(getattr(self, "selected_probe_model_ids", set()))
        if sel_count == 0:
            self.btn_add_probe_models.text = "添加选中模型"
            self.btn_add_probe_models.icon = ft.Icons.ADD_LINK
        elif sel_count == 1:
            self.btn_add_probe_models.text = "添加选中模型 (1)"
            self.btn_add_probe_models.icon = ft.Icons.ADD_LINK
        else:
            self.btn_add_probe_models.text = f"批量添加选中模型 ({sel_count})"
            self.btn_add_probe_models.icon = ft.Icons.LIBRARY_ADD

    def _clear_probe_list(self):
        """清空探测结果列表及多选状态。"""
        self.probe_list_view.controls.clear()
        self.selected_probe_model_id = ""
        self.selected_probe_model_ids.clear()
        self.last_clicked_probe_index = None
        self._current_rendered_probe_models = []
        self._update_probe_controls_state()
        self.page.update()

    def _render_probe_items(self, models: list):
        """渲染探测到的模型列表，支持 Ctrl 逐个多选与 Shift 范围批量多选。"""
        self._current_rendered_probe_models = list(models)
        self.probe_list_view.controls.clear()

        for idx, m in enumerate(models):
            m_id = m.get("id", "") if isinstance(m, dict) else str(m)
            ctx = m.get("max_context_tokens") if isinstance(m, dict) else None
            out = m.get("max_output_tokens") if isinstance(m, dict) else None
            hints = []
            if ctx:
                hints.append(f"ctx={ctx}")
            if out:
                hints.append(f"out={out}")
            hint_str = f"  [{' '.join(hints)}]" if hints else ""

            is_sel = m_id in self.selected_probe_model_ids

            def make_on_select(curr_idx=idx, curr_mid=m_id):
                def handler(e):
                    ctrl = self._is_ctrl_pressed()
                    shift = self._is_shift_pressed()

                    if shift and self.last_clicked_probe_index is not None:
                        start = min(self.last_clicked_probe_index, curr_idx)
                        end = max(self.last_clicked_probe_index, curr_idx)
                        for i in range(start, end + 1):
                            item = self._current_rendered_probe_models[i]
                            item_id = item.get("id", "") if isinstance(item, dict) else str(item)
                            if item_id:
                                self.selected_probe_model_ids.add(item_id)
                    elif ctrl:
                        if curr_mid in self.selected_probe_model_ids:
                            self.selected_probe_model_ids.remove(curr_mid)
                        else:
                            self.selected_probe_model_ids.add(curr_mid)
                        self.last_clicked_probe_index = curr_idx
                    else:
                        if self.selected_probe_model_ids == {curr_mid}:
                            self.selected_probe_model_ids.clear()
                            self.last_clicked_probe_index = None
                        else:
                            self.selected_probe_model_ids = {curr_mid}
                            self.last_clicked_probe_index = curr_idx

                    self.selected_probe_model_id = curr_mid if curr_mid in self.selected_probe_model_ids else (next(iter(self.selected_probe_model_ids)) if self.selected_probe_model_ids else "")
                    self._update_probe_controls_state()
                    self._render_probe_items(self._current_rendered_probe_models)
                return handler

            def on_quick_add(e, mid=m_id):
                self.selected_probe_model_ids = {mid}
                self.selected_probe_model_id = mid
                self.open_add_model_dialog(custom_model_id=mid)

            def make_on_checkbox(curr_idx=idx, curr_mid=m_id):
                def handler(e):
                    if e.control.value:
                        self.selected_probe_model_ids.add(curr_mid)
                        self.last_clicked_probe_index = curr_idx
                    else:
                        self.selected_probe_model_ids.discard(curr_mid)
                    self.selected_probe_model_id = curr_mid if curr_mid in self.selected_probe_model_ids else (next(iter(self.selected_probe_model_ids)) if self.selected_probe_model_ids else "")
                    self._update_probe_controls_state()
                    self._render_probe_items(self._current_rendered_probe_models)
                return handler

            checkbox = ft.Checkbox(
                value=is_sel,
                on_change=make_on_checkbox(idx, m_id),
            )

            self.probe_list_view.controls.append(
                ft.Container(
                    content=ft.ListTile(
                        leading=ft.Row([checkbox, ft.Icon(ft.Icons.SMART_TOY_OUTLINED, size=20, color=ft.Colors.BLUE_600)], tight=True, spacing=6),
                        title=ft.Text(f"{m_id}{hint_str}", weight=ft.FontWeight.BOLD if is_sel else ft.FontWeight.W_400, size=13),
                        trailing=ft.ElevatedButton("添加", on_click=on_quick_add, height=32),
                        dense=True,
                        on_click=make_on_select(idx, m_id),
                    ),
                    bgcolor=ft.Colors.BLUE_50 if is_sel else None,
                    border=ft.border.all(1, ft.Colors.BLUE_300 if is_sel else ft.Colors.TRANSPARENT),
                    border_radius=6,
                )
            )
        self._update_probe_controls_state()
        self.page.update()

    # ------------------------------------------------------------------ #
    #  平台下拉框与辅助计算                                                 #
    # ------------------------------------------------------------------ #

    def _resolve_platform_name(self, platform_value=None) -> str:
        """获取当前选中的平台标识。"""
        if platform_value:
            raw = str(platform_value).strip()
            return self.platform_display_to_key.get(raw, raw)
        current = (self.platform_dropdown.value or "").strip()
        return self.platform_display_to_key.get(current, current)

    def _refresh_platform_combo(self, selected_platform_name: str | None = None):
        """刷新平台下拉选项。"""
        platform_names = list(self.current_config.keys()) if self.current_config else []
        self.platform_display_to_key = {name: name for name in platform_names}
        self.platform_keys_in_order = list(platform_names)

        self.platform_dropdown.options = [ft.dropdown.Option(name, name) for name in platform_names]

        target = selected_platform_name if selected_platform_name in self.current_config else ""
        if not target and platform_names:
            target = platform_names[0]

        self.platform_dropdown.value = target if target else None
        self.page.update()

    def _update_overview_state(self):
        """更新顶部状态文本。"""
        p_count = len(self.current_config)
        total_m = sum(len(c.get("models", {})) for c in self.current_config.values()) if self.current_config else 0

        if not self.current_config:
            self.header_status_text.value = "当前尚未加载任何平台配置"
            self.page.update()
            return

        p_name = self._resolve_platform_name()
        if not p_name or p_name not in self.current_config:
            p_name = next(iter(self.current_config.keys()), "")

        p_cfg = self.current_config.get(p_name, {})
        has_key = bool(p_cfg.get("api_key"))

        self.header_status_text.value = (
            f"已加载 {p_count} 个平台 / {total_m} 个模型 · 当前平台：{p_name or '未选择'} · API Key {'已保存' if has_key else '未保存'}"
        )
        self.page.update()

    def _decrypt_api_key_strict(self, api_key_val: str) -> str:
        """严格解密 API Key。"""
        if not api_key_val or not isinstance(api_key_val, str):
            return ""
        text = api_key_val.strip()
        if not text:
            return ""
        sec = SecurityManager.get_instance()
        res = sec.decrypt(text)
        if res.has_plaintext:
            return res.value
        if res.is_missing_key:
            raise ValueError("检测到加密 API Key，但当前未设置 LLM_KEY")
        raise ValueError("托管密钥与当前站点主密钥不匹配，该平台需要重新配置 API Key")

    def _get_probe_cache_key(self, platform_name, base_url, api_key) -> str | None:
        if not platform_name or not base_url or not api_key:
            return None
        return f"{platform_name}::{base_url}::{api_key}"

    def _invalidate_probe_cache(self, platform_name: str | None = None):
        if not platform_name:
            self.probe_models_cache.clear()
            return
        keys_to_remove = [k for k in self.probe_models_cache.keys() if k.startswith(f"{platform_name}::")]
        for k in keys_to_remove:
            del self.probe_models_cache[k]


def main(*, schema_initializer: Optional[Callable[[AIManager], None]] = None):
    """主函数：启动 Flet GUI。"""
    enable_high_dpi_awareness()

    gui_instance = None

    def app_main(page: ft.Page):
        nonlocal gui_instance
        gui_instance = LLMConfigGUI(page, schema_initializer=schema_initializer)

    ft.app(target=app_main)

    # 窗口关闭后 ft.app() 正常返回退出，此时尽力保存一次（纯数据层操作，无 UI 阻塞）
    if gui_instance is not None:
        try:
            gui_instance.save_platform_config(silent=True, skip_ui_update=True)
        except Exception:
            pass


if __name__ == "__main__":
    main()
