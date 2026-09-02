"""
密钥管理功能 Mixin（适配 Flet 0.28.3）。
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

from ..env_utils import get_env_var, get_env_path
from ..manager import MasterKeyMigrationRequiredError


class KeyManagerMixin:
    """密钥管理功能 Mixin，需与 LLMConfigGUI 混入使用。"""

    def _format_master_key_summary(self, result: dict) -> str:
        """格式化主密钥迁移结果。"""
        parts = []
        if result.get("encrypted_plaintext"):
            parts.append(f"明文转加密 {result['encrypted_plaintext']} 项")
        if result.get("normalized_existing"):
            parts.append(f"规范化已有密文 {result['normalized_existing']} 项")
        if result.get("rotated_with_old_key"):
            parts.append(f"用旧主密钥迁移 {result['rotated_with_old_key']} 项")
        if result.get("cleared_unrecoverable"):
            parts.append(f"清除不可恢复密钥 {result['cleared_unrecoverable']} 项")
        return "；".join(parts) if parts else "未发现需要迁移的历史密钥"

    def _apply_master_key_change(
        self,
        new_key: str,
        require_success: bool = False,
        old_key: str | None = None,
        allow_clear_unrecoverable: bool = False,
    ) -> bool:
        """调用后端主密钥接口，必要时引导旧主密钥或清除历史密钥。"""
        try:
            result = self.ai_manager.rotate_master_key(
                new_key=new_key,
                old_key=old_key,
                persist=True,
                allow_clear_unrecoverable=allow_clear_unrecoverable,
            )
            self.log(f"✓ 已完成主密钥处理：{self._format_master_key_summary(result)}", tag="success")
            return True
        except MasterKeyMigrationRequiredError as exc:
            self._prompt_master_key_recovery(str(exc), new_key, require_success=require_success)
            return False
        except Exception as exc:
            self.show_error("主密钥处理失败", str(exc))
            self.log(f"✗ 主密钥处理失败: {exc}", tag="error")
            return False

    def _prompt_master_key_recovery(self, error_message: str, new_key: str, require_success: bool) -> None:
        """弹出历史密钥迁移/清除确认对话框。"""
        old_key_entry = ft.TextField(
            label="旧主密钥（留空并点击确定可清除不可恢复密钥）",
            password=True,
            can_reveal_password=True,
            autofocus=True,
        )

        def on_confirm_recovery(e):
            input_old_key = old_key_entry.value.strip() if old_key_entry.value else ""
            if not input_old_key:
                # 提示确认清除
                self.page.close(dlg)

                def do_clear():
                    self._apply_master_key_change(
                        new_key=new_key,
                        require_success=require_success,
                        old_key=None,
                        allow_clear_unrecoverable=True,
                    )

                self.ask_yes_no(
                    "确认清除历史密钥",
                    "你没有提供旧主密钥。\n\n这将清除所有当前无法解密的历史 API Key：\n- 数据库中的相关密钥会被置空\n- YAML 中相关 api_key 也会被删除\n\n该操作不可撤销，是否继续？",
                    on_yes=do_clear,
                    on_no=(lambda: self.page.window.close()) if require_success else None,
                )
                return

            self.page.close(dlg)
            self._apply_master_key_change(
                new_key=new_key,
                require_success=require_success,
                old_key=input_old_key,
                allow_clear_unrecoverable=False,
            )

        def on_cancel(e):
            self.page.close(dlg)
            if require_success and hasattr(self.page, "window") and self.page.window:
                self.page.window.close()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("迁移历史密钥"),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text("当前主密钥无法解密部分历史 API Key：", size=13),
                        ft.Text(error_message, size=12, color=ft.Colors.RED_600),
                        ft.Text("请输入旧主密钥以迁移历史密钥；若不再需要保留历史密钥，可直接留空确定以清除。", size=12),
                        old_key_entry,
                    ],
                    tight=True,
                    spacing=12,
                ),
                width=480,
            ),
            actions=[
                ft.TextButton("取消", on_click=on_cancel),
                ft.ElevatedButton("确定", on_click=on_confirm_recovery),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.open(dlg)

    def _ensure_master_key_ready_on_startup(self) -> bool:
        """启动时强制检查主密钥；缺失时引导设置。"""
        current_key = (get_env_var("LLM_KEY") or "").strip()
        if not current_key:
            self.open_set_llm_key_dialog(require_success=True)
            return False

        success = self._apply_master_key_change(current_key, require_success=True)
        return success

    def save_api_key(self):
        """保存 API Key 到数据库（加密存储）。"""
        platform_name = self._resolve_platform_name()
        if not platform_name or platform_name not in self.current_config:
            if self.last_selected_platform_name:
                platform_name = self.last_selected_platform_name
            else:
                self.show_warning("警告", "请先选择一个有效的平台")
                return

        api_key = (self.api_key_entry.value or "").strip()
        if not api_key:
            self.show_warning("警告", "请输入 API Key")
            return

        try:
            db_id = self.current_config[platform_name].get("_db_id")
            if not db_id:
                raise ValueError("无法获取平台数据库 ID")
            self.ai_manager.admin_update_sys_platform_api_key(db_id, api_key)
            self.current_config[platform_name]["api_key"] = api_key
            self._invalidate_probe_cache(platform_name)
            self.on_platform_selected()
            self.log(f"✓ 平台 '{platform_name}' 的 API Key 已加密保存", tag="success")
            self.show_snack(f"平台 '{platform_name}' 的 API Key 已成功加密保存！")
        except Exception as e:
            self.log(f"✗ 保存失败: {e}", tag="error")
            self.show_error("错误", f"保存 API Key 失败: {e}")

    def open_set_llm_key_dialog(self, require_success: bool = False):
        """手动设置或轮换主密钥 LLM_KEY。"""
        key_input = ft.TextField(
            label="新的主密钥 (LLM_KEY)",
            hint_text="写入 agen_matchbox/.env",
            password=True,
            can_reveal_password=True,
            autofocus=True,
        )
        error_msg_text = ft.Text("", color=ft.Colors.RED_600, size=12, visible=False)

        def on_confirm(e):
            new_key = (key_input.value or "").strip()
            if not new_key:
                error_msg_text.value = "主密钥不能为空！"
                error_msg_text.visible = True
                self.page.update()
                return

            if self._apply_master_key_change(new_key, require_success=require_success):
                self.page.close(dlg)
                self.log(f"✓ 主密钥已保存到 {get_env_path()}", tag="success")
                self.show_snack("主密钥已成功保存！")
                if getattr(self, "current_config", None):
                    self._invalidate_probe_cache()
                    self.load_config_from_db()
                if require_success:
                    self._bootstrap_startup_continue()

        def on_cancel(e):
            self.page.close(dlg)
            if require_success:
                self.show_warning("无法继续", "未完成主密钥设置，GUI 即将关闭。")
                if hasattr(self.page, "window") and self.page.window:
                    self.page.window.close()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("设置主密钥"),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text("请输入新的 LLM_KEY，所有托管和自定义 API Key 将以此密钥加密：", size=13),
                        key_input,
                        error_msg_text,
                    ],
                    tight=True,
                    spacing=12,
                ),
                width=460,
            ),
            actions=[
                ft.TextButton("取消", on_click=on_cancel),
                ft.ElevatedButton("保存主密钥", on_click=on_confirm),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.open(dlg)

    def _ask_password(self, title: str, prompt: str) -> str | None:
        """向后兼容的密码输入接口。"""
        return None
