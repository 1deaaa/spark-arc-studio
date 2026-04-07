"""
密钥管理 Mixin — LLM_KEY 检查/设置、API Key 管理
"""
import os
import sys
import tkinter as tk
from tkinter import messagebox, simpledialog

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

    # ------------------------------------------------------------------ #
    #  内部工具                                                             #
    # ------------------------------------------------------------------ #

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

    def _prompt_master_key_recovery(self, error_message: str, require_success: bool) -> str | None:
        """提示输入旧主密钥，或允许用户确认清除历史密钥。"""
        while True:
            old_key = simpledialog.askstring(
                "迁移历史密钥",
                "当前主密钥无法解密部分历史 API Key。\n\n"
                f"{error_message}\n\n"
                "请输入旧主密钥以迁移历史密钥。\n"
                "如果这些历史密钥本来就不需要保留，可以直接留空并点击确定，随后确认清除。",
                parent=self.root,
                show='*',
            )

            if old_key is None:
                if require_success:
                    messagebox.showwarning(
                        "无法继续",
                        "必须完成主密钥迁移，或明确确认清除历史密钥后，GUI 才能继续启动。",
                        parent=self.root,
                    )
                    continue
                return None

            old_key = old_key.strip()
            if old_key:
                return old_key

            if messagebox.askyesno(
                "确认清除历史密钥",
                "你没有提供旧主密钥。\n\n"
                "这将清除所有当前无法解密的历史 API Key：\n"
                "- 数据库中的相关密钥会被置空\n"
                "- YAML 中相关 api_key 也会被删除\n\n"
                "该操作不可撤销，是否继续？",
                parent=self.root,
            ):
                return ""

    def _apply_master_key_change(self, new_key: str, require_success: bool = False) -> bool:
        """调用后端唯一主密钥接口，必要时补录旧主密钥或清除历史密钥。"""
        pending_old_key = None
        allow_clear_unrecoverable = False

        while True:
            try:
                result = self.ai_manager.rotate_master_key(
                    new_key=new_key,
                    old_key=pending_old_key,
                    persist=True,
                    allow_clear_unrecoverable=allow_clear_unrecoverable,
                )
                self.log(f"✓ 已完成主密钥处理：{self._format_master_key_summary(result)}", tag="success")
                return True
            except MasterKeyMigrationRequiredError as exc:
                recovery_input = self._prompt_master_key_recovery(str(exc), require_success=require_success)
                if recovery_input is None:
                    return False
                pending_old_key = recovery_input or None
                allow_clear_unrecoverable = recovery_input == ""
            except Exception as exc:
                messagebox.showerror("主密钥处理失败", str(exc), parent=self.root)
                self.log(f"✗ 主密钥处理失败: {exc}", tag="error")
                return False

    def _ensure_master_key_ready_on_startup(self) -> bool:
        """启动时强制检查主密钥；缺失或不匹配时必须完成修复，否则退出 GUI。"""
        current_key = (get_env_var("LLM_KEY") or "").strip()
        if not current_key:
            messagebox.showwarning(
                "必须先设置主密钥",
                "未检测到 LLM_KEY。\n\n"
                "根据当前安全策略，未设置主密钥时不再允许以明文方式保存或继续运行配置 GUI。\n"
                "请先完成主密钥设置；若取消，将直接退出 GUI。",
                parent=self.root,
            )
            return self.open_set_llm_key_dialog(require_success=True)

        return self._apply_master_key_change(current_key, require_success=True)

    # ------------------------------------------------------------------ #
    #  公开方法                                                             #
    # ------------------------------------------------------------------ #

    def save_api_key(self):
        """保存 API Key 到数据库（加密存储）。"""
        platform_name = self._resolve_platform_name()
        if not platform_name or platform_name not in self.current_config:
            if self.last_selected_platform_name:
                platform_name = self.last_selected_platform_name
            else:
                messagebox.showwarning("警告", "请先选择一个有效的平台")
                return

        api_key = self.api_key_entry.get().strip()
        if not api_key:
            messagebox.showwarning("警告", "请输入 API Key")
            return

        try:
            db_id = self.current_config[platform_name].get("_db_id")
            if not db_id:
                raise ValueError("无法获取平台数据库 ID")
            self.ai_manager.admin_update_sys_platform_api_key(db_id, api_key)
            # 更新内存配置
            self.current_config[platform_name]["api_key"] = api_key
            # Key 变化后清理探测缓存
            self._invalidate_probe_cache(platform_name)
            self.on_platform_selected()
            self.log(f"✓ 平台 '{platform_name}' 的 API Key 已加密保存", tag="success")
        except Exception as e:
            self.log(f"✗ 保存失败: {e}")
            messagebox.showerror("错误", f"保存 API Key 失败: {e}")

    def open_set_llm_key_dialog(self, require_success=False):
        """手动设置或轮换主密钥 LLM_KEY。"""

        while True:
            key = simpledialog.askstring(
                "设置主密钥",
                "请输入新的 LLM_KEY（将写入 agen_matchbox/.env）：",
                parent=self.root,
                show='*'
            )
            if key is None:
                if require_success:
                    messagebox.showwarning("无法继续", "未完成主密钥设置，GUI 将退出。", parent=self.root)
                return False

            key = key.strip()
            if not key:
                messagebox.showwarning("提示", "LLM_KEY 不能为空", parent=self.root)
                continue

            if self._apply_master_key_change(key, require_success=require_success):
                self.log(f"✓ 主密钥已保存到 {get_env_path()}", tag="success")
                if getattr(self, "current_config", None):
                    self._invalidate_probe_cache()
                    self.load_config_from_db()
                return True

            if not require_success:
                return False
