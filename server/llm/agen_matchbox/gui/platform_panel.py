"""
平台管理功能 Mixin（适配 Flet 0.28.3）。
"""
from __future__ import annotations

import os
import sys
import flet as ft

if __package__ in (None, "", "gui"):
    _GUI_DIR = os.path.dirname(os.path.abspath(__file__))
    _PKG_DIR = os.path.dirname(_GUI_DIR)
    _PARENT_DIR = os.path.dirname(_PKG_DIR)
    if _PARENT_DIR not in sys.path:
        sys.path.insert(0, _PARENT_DIR)
    __package__ = f"{os.path.basename(_PKG_DIR)}.{os.path.basename(_GUI_DIR)}"

from ..utils import normalize_base_url, normalize_recharge_url


class PlatformPanelMixin:
    """平台管理功能 Mixin，需与 LLMConfigGUI 混入使用。"""

    def on_platform_selected(self, event=None):
        """平台选择变化时更新界面各控件与模型列表。"""
        platform_name = self._resolve_platform_name()
        if not platform_name or platform_name not in self.current_config:
            if hasattr(self, "_update_overview_state"):
                self._update_overview_state()
            return

        self.last_selected_platform_name = platform_name
        platform_cfg = self.current_config[platform_name]

        # 填充 Base URL
        base_url = platform_cfg.get("base_url", "")
        self.base_url_entry.value = base_url
        self.platform_url_entry.value = base_url

        # 填充充值地址
        recharge_url = platform_cfg.get("recharge_url", "") or ""
        self.recharge_url_entry.value = recharge_url

        # 填充 API Key
        api_key = platform_cfg.get("api_key", "")
        self.api_key_entry.value = api_key or ""

        # 清空并恢复探测结果
        self._clear_probe_list()
        cache_key = self._get_probe_cache_key(platform_name, base_url, api_key.strip())
        if cache_key and cache_key in self.probe_models_cache:
            self._render_probe_items(self.probe_models_cache[cache_key])

        # 渲染模型列表
        self._refresh_model_list_view()

        # 异步启动一次模型探测
        self.probe_models(auto_start=True)

        if hasattr(self, "_update_overview_state"):
            self._update_overview_state()
        self.page.update()

    def rename_platform(self, new_name: str | None = None):
        """给当前选中的平台改名。"""
        if not self.last_selected_platform_name:
            return

        old_name = self.last_selected_platform_name
        if not new_name:
            # 弹窗输入新名称
            name_field = ft.TextField(label="平台新名称", value=old_name, autofocus=True)

            def on_confirm_rename(e):
                val = (name_field.value or "").strip()
                if val and val != old_name:
                    self.page.close(dlg)
                    self._execute_rename_platform(old_name, val)

            dlg = ft.AlertDialog(
                title=ft.Text("平台重命名"),
                content=name_field,
                actions=[
                    ft.TextButton("取消", on_click=lambda e: self.page.close(dlg)),
                    ft.ElevatedButton("保存", on_click=on_confirm_rename),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            self.page.open(dlg)
            return

        self._execute_rename_platform(old_name, new_name)

    def _execute_rename_platform(self, old_name: str, new_name: str):
        if not new_name or new_name == old_name:
            return

        if new_name in self.current_config:
            self.show_warning("警告", f"平台名称 '{new_name}' 已存在")
            return

        try:
            db_id = self.current_config[old_name].get("_db_id")
            if not db_id:
                raise ValueError("无法获取平台数据库 ID")
            base_url = self.current_config[old_name].get("base_url", "")
            self.ai_manager.admin_update_sys_platform(db_id, new_name, base_url)

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
            self.show_snack(f"平台已成功重命名为 '{new_name}'")
        except Exception as e:
            self.log(f"✗ 改名失败: {e}", tag="error")
            self.show_error("错误", f"改名失败: {e}")

    def add_platform(self):
        """添加新平台。"""
        name_entry = ft.TextField(label="平台名称", hint_text="例如: DeepSeek, OpenAI", autofocus=True)
        url_entry = ft.TextField(label="Base URL", value="https://api.example.com/v1")
        key_entry = ft.TextField(label="API Key (可选)", password=True, can_reveal_password=True)
        recharge_entry = ft.TextField(label="充值地址 (可选)", hint_text="https://...")
        error_text = ft.Text("", color=ft.Colors.RED_600, size=12, visible=False)

        def do_add(e):
            name = (name_entry.value or "").strip()
            url = (url_entry.value or "").strip()
            key = (key_entry.value or "").strip()
            recharge_url = (recharge_entry.value or "").strip()

            if not name or not url:
                error_text.value = "平台名称和 Base URL 不能为空"
                error_text.visible = True
                self.page.update()
                return

            if not (url.startswith("http://") or url.startswith("https://")):
                error_text.value = "URL 必须以 http:// 或 https:// 开头"
                error_text.visible = True
                self.page.update()
                return

            url = normalize_base_url(url)
            try:
                recharge_url = normalize_recharge_url(recharge_url)
            except ValueError as exc:
                error_text.value = str(exc)
                error_text.visible = True
                self.page.update()
                return

            if name in self.current_config:
                error_text.value = f"平台名称 '{name}' 已存在"
                error_text.visible = True
                self.page.update()
                return

            try:
                created = self.ai_manager.admin_add_sys_platform(
                    name,
                    url,
                    key or None,
                    recharge_url=recharge_url,
                )
                p_id = created.id if hasattr(created, "id") else None

                self.current_config[name] = {
                    "base_url": url,
                    "recharge_url": recharge_url or "",
                    "api_key": key or "",
                    "models": {},
                    "_db_id": p_id,
                }

                self.page.close(dlg)
                self._refresh_platform_combo(selected_platform_name=name)
                self.on_platform_selected()
                self.log(f"✓ 平台 '{name}' 已添加", tag="success")
                self.show_snack(f"平台 '{name}' 已成功添加！")
            except Exception as ex:
                self.log(f"✗ 添加平台失败: {ex}", tag="error")
                error_text.value = f"添加平台失败: {ex}"
                error_text.visible = True
                self.page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("添加新平台"),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text("添加一个兼容 OpenAI 协议的平台，保存后即可测试并探测模型。", size=12, color=ft.Colors.GREY_600),
                        name_entry,
                        url_entry,
                        key_entry,
                        recharge_entry,
                        error_text,
                    ],
                    tight=True,
                    spacing=10,
                ),
                width=500,
            ),
            actions=[
                ft.TextButton("取消", on_click=lambda e: self.page.close(dlg)),
                ft.ElevatedButton("保存", on_click=do_add),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.open(dlg)

    def delete_platform(self):
        """删除选中的平台（实质为软禁用，从列表中隐藏）。"""
        platform_name = self._resolve_platform_name()
        if not platform_name or platform_name not in self.current_config:
            if self.last_selected_platform_name:
                platform_name = self.last_selected_platform_name
            else:
                self.show_warning("警告", "请先选择一个有效的平台")
                return

        def on_confirm_delete():
            try:
                db_id = self.current_config[platform_name].get("_db_id")
                if not db_id:
                    raise ValueError("无法获取平台数据库 ID")
                self.ai_manager.disable_platform(db_id, admin_mode=True)
                self._invalidate_probe_cache(platform_name)
                self.load_config_from_db()
                self.log(f"✓ 平台 '{platform_name}' 已禁用", tag="success")
                self.show_snack(f"平台 '{platform_name}' 已禁用")
            except Exception as e:
                self.log(f"✗ 禁用平台失败: {e}", tag="error")
                self.show_error("错误", f"禁用平台失败: {e}")

        self.ask_yes_no(
            "确认禁用",
            f"确定要禁用平台 '{platform_name}' 吗？\n该平台及其模型会从默认列表中隐藏，但不会被物理删除。",
            on_yes=on_confirm_delete,
        )

    def save_platform_config(self, silent: bool = False) -> bool:
        """一键保存当前平台的全部配置（Base URL、充值地址、API Key）。"""
        platform_name = self._resolve_platform_name()
        if not platform_name or platform_name not in getattr(self, "current_config", {}):
            if getattr(self, "last_selected_platform_name", None):
                platform_name = self.last_selected_platform_name
            else:
                if not silent:
                    self.show_warning("警告", "请先选择一个有效的平台")
                return False

        db_id = self.current_config[platform_name].get("_db_id")
        if not db_id:
            if not silent:
                self.show_error("错误", "无法获取平台数据库 ID")
            return False

        changed_items = []
        try:
            # 1. 检查并保存 Base URL
            new_url = (self.platform_url_entry.value or "").strip()
            if new_url:
                if not (new_url.startswith("http://") or new_url.startswith("https://")):
                    if not silent:
                        self.show_error("错误", "Base URL 必须以 http:// 或 https:// 开头")
                    return False
                new_url = normalize_base_url(new_url)
                if new_url != self.current_config[platform_name].get("base_url"):
                    self.ai_manager.admin_update_sys_platform(db_id, platform_name, new_url)
                    self.current_config[platform_name]["base_url"] = new_url
                    self.base_url_entry.value = new_url
                    changed_items.append("Base URL")

            # 2. 检查并保存充值地址
            raw_recharge = (self.recharge_url_entry.value or "").strip()
            recharge_url = normalize_recharge_url(raw_recharge) if raw_recharge else ""
            if recharge_url != (self.current_config[platform_name].get("recharge_url") or ""):
                self.ai_manager.admin_update_sys_platform(
                    db_id,
                    recharge_url=recharge_url,
                    update_recharge_url=True,
                )
                self.current_config[platform_name]["recharge_url"] = recharge_url
                self.recharge_url_entry.value = recharge_url
                changed_items.append("充值地址")

            # 3. 检查并保存 API Key
            new_key = (self.api_key_entry.value or "").strip()
            if new_key != (self.current_config[platform_name].get("api_key") or ""):
                self.ai_manager.admin_update_sys_platform_api_key(db_id, new_key)
                self.current_config[platform_name]["api_key"] = new_key
                changed_items.append("API Key")

            if changed_items:
                self._invalidate_probe_cache(platform_name)
                if hasattr(self, "_update_overview_state"):
                    self._update_overview_state()
                self.log(f"✓ 平台 '{platform_name}' 配置已成功保存: {', '.join(changed_items)}", tag="success")
                if not silent:
                    self.show_snack(f"平台 '{platform_name}' 配置已保存！")
            else:
                if not silent:
                    self.show_snack("当前平台配置未发生改动。")
            self.page.update()
            return True
        except Exception as e:
            self.log(f"✗ 保存平台配置失败: {e}", tag="error")
            if not silent:
                self.show_error("错误", f"保存平台配置失败: {e}")
            return False

    def save_platform_url(self):
        """保存平台的 Base URL。"""
        platform_name = self._resolve_platform_name()
        if not platform_name or platform_name not in self.current_config:
            if self.last_selected_platform_name:
                platform_name = self.last_selected_platform_name
            else:
                self.show_warning("警告", "请先选择一个有效的平台")
                return

        new_url = (self.platform_url_entry.value or "").strip()
        if not new_url:
            self.show_error("错误", "请填写平台 URL")
            return
        if not (new_url.startswith("http://") or new_url.startswith("https://")):
            self.show_error("错误", "URL 必须以 http:// 或 https:// 开头")
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
            self.show_snack("平台 URL 已保存！")
        except Exception as e:
            self.log(f"✗ 保存失败: {e}", tag="error")
            self.show_error("错误", f"保存平台 URL 失败: {e}")

    def save_recharge_url(self):
        """保存平台充值地址。"""
        platform_name = self._resolve_platform_name()
        if not platform_name or platform_name not in self.current_config:
            if self.last_selected_platform_name:
                platform_name = self.last_selected_platform_name
            else:
                self.show_warning("警告", "请先选择一个有效的平台")
                return

        raw_recharge_url = (self.recharge_url_entry.value or "").strip()
        try:
            recharge_url = normalize_recharge_url(raw_recharge_url)
        except ValueError as exc:
            self.show_error("错误", str(exc))
            return

        try:
            db_id = self.current_config[platform_name].get("_db_id")
            if not db_id:
                raise ValueError("无法获取平台数据库 ID")
            self.ai_manager.admin_update_sys_platform(
                db_id,
                recharge_url=recharge_url,
                update_recharge_url=True,
            )
            self.current_config[platform_name]["recharge_url"] = recharge_url or ""
            self.recharge_url_entry.value = recharge_url or ""
            if hasattr(self, "_update_overview_state"):
                self._update_overview_state()
            self.page.update()
            self.log(f"✓ 平台 '{platform_name}' 的充值地址已更新", tag="success")
            self.show_snack("平台充值地址已保存！")
        except Exception as e:
            self.log(f"✗ 保存失败: {e}", tag="error")
            self.show_error("错误", f"保存充值地址失败: {e}")

    def set_as_default(self):
        """将选中的平台设为默认。"""
        platform_name = self._resolve_platform_name()
        if not platform_name:
            self.show_warning("警告", "请先选择一个平台")
            return

        def on_confirm():
            try:
                db_id = self.current_config[platform_name].get("_db_id")
                if not db_id:
                    raise ValueError("无法获取平台数据库 ID")
                self.ai_manager.admin_set_sys_platform_default(db_id)
                self.load_config_from_db()
                self.log(f"✓ 已将 '{platform_name}' 设为默认平台", tag="success")
                self.show_snack(f"已将 '{platform_name}' 设为系统默认平台！")
            except Exception as e:
                self.log(f"✗ 设置默认平台失败: {e}", tag="error")
                self.show_error("错误", f"设置默认平台失败: {e}")

        self.ask_yes_no(
            "确认设置默认",
            f"确定要将 '{platform_name}' 设为默认平台吗？\n它将被置顶，当未显式指定平台时系统将优先使用它。",
            on_yes=on_confirm,
        )
