"""
密钥管理 Mixin — LLM_KEY 检查/设置、API Key 管理
"""
import os
import yaml
import tkinter as tk
from tkinter import messagebox, simpledialog

from llm.llm_mgr.security import SecurityManager
from llm.llm_mgr.env_utils import get_env_var, set_env_var, get_env_path
from llm.llm_mgr.models import LLMPlatform


class KeyManagerMixin:
    """密钥管理功能 Mixin，需与 LLMConfigGUI 混入使用。"""

    # ------------------------------------------------------------------ #
    #  内部工具                                                             #
    # ------------------------------------------------------------------ #

    def _decrypt_api_key_strict(self, api_key_val: str) -> str:
        """严格解密 API Key，失败时抛出异常。"""
        if not api_key_val:
            return ""
        sec_mgr = SecurityManager.get_instance()
        if api_key_val.startswith("ENC:"):
            decrypted = sec_mgr.decrypt(api_key_val)
            if not decrypted or decrypted.startswith("ENC:"):
                raise ValueError(f"无法解密 API Key（LLM_KEY 可能不匹配）: {api_key_val[:20]}...")
            return decrypted
        return api_key_val

    def _find_encrypted_key_sample(self):
        """返回任意一个 ENC: 样本密文（优先数据库，其次 YAML）。"""
        try:
            with self.ai_manager.Session() as session:
                plat = session.query(LLMPlatform).filter(LLMPlatform.api_key.like("ENC:%")).first()
                if plat and plat.api_key:
                    return plat.api_key
        except Exception:
            pass

        try:
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "llm_mgr_cfg.yaml")
            if not os.path.exists(config_path):
                return None
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            if not isinstance(cfg, dict):
                return None
            for _, p_cfg in cfg.items():
                api_key = p_cfg.get("api_key") if isinstance(p_cfg, dict) else None
                if isinstance(api_key, str) and api_key.startswith("ENC:"):
                    return api_key
        except Exception:
            return None
        return None

    def _normalize_all_api_keys(self):
        """将数据库中所有 API Key 统一规范为单层 ENC。"""
        sec_mgr = SecurityManager.get_instance()

        # 规范化数据库
        with self.ai_manager.Session() as session:
            all_platforms = session.query(LLMPlatform).all()
            for plat in all_platforms:
                raw = plat.api_key
                if not raw:
                    continue
                try:
                    plain = self._decrypt_api_key_strict(raw)
                    plat.api_key = sec_mgr.encrypt(plain) if plain else ""
                except Exception:
                    plat.api_key = ""
            session.commit()

    def _has_decrypt_failures(self) -> bool:
        """检测当前 LLM_KEY 下是否存在无法解密的密钥。"""
        try:
            with self.ai_manager.Session() as session:
                all_platforms = session.query(LLMPlatform).all()
                for plat in all_platforms:
                    raw = plat.api_key
                    if not raw:
                        continue
                    try:
                        self._decrypt_api_key_strict(raw)
                    except Exception:
                        return True
        except Exception:
            return True
        return False

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

    def _check_and_set_llm_key(self):
        """启动时检查 LLM_KEY；如果解析失败，主动提示是否初始化。"""
        current_key = (get_env_var("LLM_KEY") or "").strip()
        encrypted_sample = self._find_encrypted_key_sample()

        if not encrypted_sample and current_key:
            return

        sec_mgr = SecurityManager.get_instance()

        # 有密文但没有 key：提示初始化
        if encrypted_sample and not current_key:
            if messagebox.askyesno(
                "检测到加密配置",
                "检测到已加密的 API Key，但当前未设置 LLM_KEY。\n\n是否现在初始化主密钥？"
            ):
                self.open_set_llm_key_dialog(require_success=True)
            else:
                self.log("⚠ 未初始化 LLM_KEY，已加密 Key 暂不可解密")
            return

        # 有密文且已有 key：验证是否可解密
        if encrypted_sample and current_key:
            decrypted = sec_mgr.decrypt(encrypted_sample)
            if not decrypted or decrypted.startswith("ENC:"):
                if messagebox.askyesno(
                    "主密钥解析失败",
                    "当前 LLM_KEY 无法解密已有配置。\n\n是否现在重新初始化 LLM_KEY？"
                ):
                    self.open_set_llm_key_dialog(require_success=True)
                else:
                    self.log("⚠ 当前 LLM_KEY 无法解密已有配置")
                    return

        current_key = (get_env_var("LLM_KEY") or "").strip()
        if current_key and self._has_decrypt_failures():
            if messagebox.askyesno(
                "检测到解密失败",
                "检测到部分 API Key 无法解密。\n\n是否执行一次规范化修复？\n"
                "- 会将可解密项重写为单层 ENC\n- 无法解密项会被清空"
            ):
                try:
                    self._normalize_all_api_keys()
                    self.log("✓ 已完成 API Key 单层加密规范化", tag="success")
                except Exception as e:
                    self.log(f"⚠ API Key 规范化失败: {e}")

    def open_set_llm_key_dialog(self, require_success=False):
        """手动设置主密钥 LLM_KEY。"""
        encrypted_sample = self._find_encrypted_key_sample()

        while True:
            key = simpledialog.askstring(
                "设置主密钥",
                "请输入 LLM_KEY（将写入 llm_mgr/.env）：",
                parent=self.root,
                show='*'
            )
            if key is None:
                if require_success:
                    if messagebox.askyesno("取消设置", "未设置主密钥可能导致解密失败。\n是否继续取消？"):
                        return
                    continue
                return

            key = key.strip()
            if not key:
                messagebox.showwarning("提示", "LLM_KEY 不能为空", parent=self.root)
                continue

            sec_mgr = SecurityManager.get_instance()
            sec_mgr.set_key(key, persist=False)

            if encrypted_sample:
                decrypted = sec_mgr.decrypt(encrypted_sample)
                if not decrypted or decrypted.startswith("ENC:"):
                    if not messagebox.askyesno(
                        "解密校验失败",
                        "该密钥无法解密现有配置。\n\n"
                        "是否仍然保存为新的 LLM_KEY？\n（保存后你需要重新录入相关 API Key）",
                        parent=self.root,
                    ):
                        continue

            self._persist_llm_key(key)
            self.log("✓ 已更新 LLM_KEY", tag="success")
            return

    def _persist_llm_key(self, key_value):
        """持久化 LLM_KEY 到 .env 文件。"""
        if set_env_var("LLM_KEY", key_value):
            self.log(f"✓ 主密码已保存到 {get_env_path()}", tag="success")
        else:
            messagebox.showerror("保存失败", "写入 .env 文件失败，请检查文件权限")
