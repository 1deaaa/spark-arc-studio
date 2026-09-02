"""
模型面板 Mixin — 模型列表、探测、筛选、拖拽排序、删除（适配 Flet 0.28.3）。
"""
from __future__ import annotations

import os
import sys
import threading
import flet as ft

if __package__ in (None, "", "gui"):
    _GUI_DIR = os.path.dirname(os.path.abspath(__file__))
    _PKG_DIR = os.path.dirname(_GUI_DIR)
    _PARENT_DIR = os.path.dirname(_PKG_DIR)
    if _PARENT_DIR not in sys.path:
        sys.path.insert(0, _PARENT_DIR)
    __package__ = f"{os.path.basename(_PKG_DIR)}.{os.path.basename(_GUI_DIR)}"

from ..models import (
    MODALITY_EMBEDDING,
    MODALITY_IMAGE,
    MODALITY_TEXT,
    normalize_model_modalities,
)
from ..utils import probe_platform_models


class ModelPanelMixin:
    """模型管理功能 Mixin，需与 LLMConfigGUI 混入使用。"""

    def _format_model_list_item(self, display_name: str, model_config) -> str:
        """格式化模型列表项显示文本。"""
        if isinstance(model_config, str):
            model_id = model_config
            input_modalities, output_modalities = normalize_model_modalities()
        else:
            model_id = model_config.get("model_name", "")
            input_modalities, output_modalities = normalize_model_modalities(
                model_config.get("input_modalities"),
                model_config.get("output_modalities"),
            )

        tags = []
        if MODALITY_TEXT in output_modalities:
            tags.append("T")
        if MODALITY_IMAGE in output_modalities:
            tags.append("I")
        if MODALITY_IMAGE in input_modalities:
            tags.append("V")
        if MODALITY_EMBEDDING in output_modalities:
            tags.append("E")
        tag = f" [{' '.join(tags)}]" if tags else ""
        return f"{display_name}{tag} → {model_id}"

    def _extract_display_name(self, item_text: str) -> str:
        """从列表项文本中提取显示名称。"""
        display_part = item_text.split(" → ")[0]
        tag_start = display_part.rfind(" [")
        if tag_start >= 0 and display_part.endswith("]"):
            tag_tokens = display_part[tag_start + 2 : -1].split()
            if tag_tokens and all(token in {"T", "I", "V", "E"} for token in tag_tokens):
                display_part = display_part[:tag_start]
        return display_part

    def _parse_extra_body(self, text):
        """解析 Extra Body JSON 字符串。"""
        from ..utils import parse_extra_body

        return parse_extra_body(text)

    def _get_selected_model_display_name(self) -> str:
        """返回当前选中的已配置模型显示名称。"""
        return getattr(self, "selected_model_display_name", "") or ""

    def _get_selected_probe_model_id(self) -> str:
        """返回当前选中的探测模型 ID。"""
        return getattr(self, "selected_probe_model_id", "") or ""

    # ------------------------------------------------------------------ #
    #  探测功能                                                             #
    # ------------------------------------------------------------------ #

    def probe_models(self, auto_start=False):
        """探测平台可用模型。"""
        platform_name = self._resolve_platform_name()
        base_url = (self.base_url_entry.value or "").strip()
        api_key = (self.api_key_entry.value or "").strip()

        if not base_url:
            if not auto_start:
                self.show_warning("警告", "请先选择平台（Base URL 将自动填充）")
            return

        cache_key = self._get_probe_cache_key(platform_name, base_url, api_key)
        if cache_key and cache_key in self.probe_models_cache and self.probe_models_cache[cache_key]:
            self.log(f"使用缓存的探测结果 ({platform_name})")
            self.show_probe_results(self.probe_models_cache[cache_key])
            return

        if not api_key:
            if not auto_start:
                self.show_error("错误", "请在 API Key 输入框中填写有效的密钥并保存")
            self.log("🔑 API Key 未填写，跳过自动探测。")
            return

        self.log(f"正在探测 {base_url} ...")
        self._clear_probe_list()

        def do_probe():
            try:
                models = probe_platform_models(base_url, api_key, raise_on_error=True)
                self.show_probe_results(models)
            except Exception as e:
                self.show_probe_error(str(e))

        threading.Thread(target=do_probe, daemon=True).start()

    def show_probe_results(self, models):
        """显示探测结果列表。"""
        if not models:
            self.log("✗ 未探测到任何模型")
            return

        platform_name = self._resolve_platform_name()
        cache_key = self._get_probe_cache_key(
            platform_name,
            (self.base_url_entry.value or "").strip(),
            (self.api_key_entry.value or "").strip(),
        )
        if cache_key:
            self.probe_models_cache[cache_key] = models
        self._last_probed_models = list(models)

        self._render_probe_items(models)
        self.log(f"✓ 探测到 {len(models)} 个模型", tag="success")

    def show_probe_error(self, error_msg):
        """显示探测错误（仅输出至日志，不弹窗阻塞）。"""
        self.log(f"✗ 探测失败: {error_msg}", tag="error")

    def on_filter_change(self, event=None):
        """筛选关键字变化时更新探测列表。"""
        platform_name = self._resolve_platform_name()
        keyword = (self.filter_entry.value or "").strip().lower()

        cache_key = self._get_probe_cache_key(
            platform_name,
            (self.base_url_entry.value or "").strip(),
            (self.api_key_entry.value or "").strip(),
        )
        cached_models = self.probe_models_cache.get(cache_key) if cache_key else None
        if cached_models is None:
            cached_models = getattr(self, "_last_probed_models", [])

        if not keyword:
            self._render_probe_items(cached_models)
        else:
            filtered = []
            for m in cached_models:
                m_id = m.get("id", "") if isinstance(m, dict) else str(m)
                if keyword in m_id.lower():
                    filtered.append(m)
            self._render_probe_items(filtered)

    def clear_filter(self):
        """清除筛选。"""
        self.filter_entry.value = ""
        self.on_filter_change()

    def select_all_probe_models(self):
        """全选当前渲染的探测模型。"""
        models = getattr(self, "_current_rendered_probe_models", [])
        for m in models:
            mid = m.get("id", "") if isinstance(m, dict) else str(m)
            if mid:
                self.selected_probe_model_ids.add(mid)
        self._update_probe_controls_state()
        self._render_probe_items(models)

    def clear_probe_selection(self):
        """清空探测模型选中项。"""
        self.selected_probe_model_ids.clear()
        self.selected_probe_model_id = ""
        self.last_clicked_probe_index = None
        self._update_probe_controls_state()
        self._render_probe_items(getattr(self, "_current_rendered_probe_models", []))

    def add_selected_probe_models(self):
        """添加或批量添加当前选中的探测模型。"""
        selected_ids = list(getattr(self, "selected_probe_model_ids", set()))
        if not selected_ids:
            if getattr(self, "selected_probe_model_id", None):
                selected_ids = [self.selected_probe_model_id]

        if not selected_ids:
            self.show_warning("提示", "请先在模型探测列表中勾选或点击选中要添加的模型。\n（支持按住 Ctrl 逐个多选，或按住 Shift 范围多选）")
            return

        if len(selected_ids) == 1:
            # 单个模型：打开完整自定义对话框
            self.open_add_model_dialog(custom_model_id=selected_ids[0])
            return

        # 多个模型：执行批量添加
        platform_name = self._resolve_platform_name()
        self.ask_yes_no(
            "批量添加模型",
            f"确定要将选中的 {len(selected_ids)} 个模型批量添加至平台 '{platform_name}' 吗？\n"
            f"模型将自动配置为默认对话模型，已有模型将被完整保留。",
            on_yes=lambda: self._batch_add_probe_models(selected_ids),
        )

    def _batch_add_probe_models(self, model_ids: list[str]):
        """批量添加选中的探测模型至当前平台，保留所有已有模型。"""
        platform_name = self._resolve_platform_name()
        if not platform_name or platform_name not in getattr(self, "current_config", {}):
            self.show_warning("警告", "请先选择一个有效的平台")
            return

        db_id = self.current_config[platform_name].get("_db_id")
        if not db_id:
            self.show_error("错误", "无法获取当前平台的数据库 ID")
            return

        # 1. 收集已有模型配置，确保不被覆盖或禁用
        existing_models = self.current_config[platform_name].get("models", {})
        payloads = []
        existing_names = set()
        for dname, mcfg in existing_models.items():
            if isinstance(mcfg, dict):
                existing_names.add(dname)
                payloads.append({
                    "display_name": dname,
                    "model_name": mcfg.get("model_name") or dname,
                    "input_modalities": mcfg.get("input_modalities", ["text"]),
                    "output_modalities": mcfg.get("output_modalities", ["text"]),
                    "extra_body": mcfg.get("extra_body"),
                    "image_generation_adapter": mcfg.get("image_generation_adapter"),
                    "temperature": mcfg.get("temperature"),
                    "max_context_tokens": mcfg.get("max_context_tokens"),
                    "max_output_tokens": mcfg.get("max_output_tokens"),
                    "sys_credit_input_price_per_million": mcfg.get("sys_credit_input_price_per_million"),
                    "sys_credit_cached_input_price_per_million": mcfg.get("sys_credit_cached_input_price_per_million"),
                    "sys_credit_output_price_per_million": mcfg.get("sys_credit_output_price_per_million"),
                })

        # 2. 查找探测元数据映射
        meta_map = {}
        for m in getattr(self, "_current_rendered_probe_models", []):
            if isinstance(m, dict) and m.get("id"):
                meta_map[m["id"]] = m

        added_count = 0
        skipped_count = 0
        for mid in model_ids:
            if mid in existing_names:
                skipped_count += 1
                continue
            meta = meta_map.get(mid, {})
            ctx = meta.get("max_context_tokens") or 128000
            out = meta.get("max_output_tokens") or 8192
            payloads.append({
                "display_name": mid,
                "model_name": mid,
                "input_modalities": ["text"],
                "output_modalities": ["text"],
                "extra_body": None,
                "image_generation_adapter": None,
                "temperature": None,
                "max_context_tokens": ctx,
                "max_output_tokens": out,
            })
            existing_names.add(mid)
            added_count += 1

        if added_count == 0:
            self.show_snack("所选模型已存在于该平台，无需重复添加。")
            return

        try:
            self.ai_manager.admin_sync_platform_models(db_id, payloads)
            msg = f"已成功批量添加 {added_count} 个模型至平台 '{platform_name}'"
            if skipped_count:
                msg += f" (已跳过 {skipped_count} 个重复模型)"
            self.log(f"✓ {msg}", tag="success")
            self.show_snack(msg)
            self.selected_probe_model_ids.clear()
            self.selected_probe_model_id = ""
            self.load_config_from_db()
            self._update_probe_controls_state()
            self._render_probe_items(getattr(self, "_current_rendered_probe_models", []))
        except Exception as e:
            self.log(f"✗ 批量添加模型失败: {e}", tag="error")
            self.show_error("错误", f"批量添加模型失败: {e}")

    def use_custom_model_name(self):
        """使用筛选框中输入的自定义名称打开添加模型对话框。"""
        custom_model_id = (self.filter_entry.value or "").strip()
        if not custom_model_id:
            self.show_warning("警告", "请输入要使用的模型名称")
            return
        self.open_add_model_dialog(custom_model_id=custom_model_id)

    # ------------------------------------------------------------------ #
    #  拖拽排序与 CRUD                                                    #
    # ------------------------------------------------------------------ #

    def reorder_models(self):
        """根据列表当前顺序更新数据库中的模型排序。"""
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
        for ctrl in self.model_list_view.controls:
            display_name = getattr(ctrl, "data", None)
            if not display_name:
                continue
            model_cfg = current_models.get(display_name)
            if model_cfg and isinstance(model_cfg, dict):
                mid = model_cfg.get("_db_id")
                if mid:
                    ordered_ids.append(mid)

        if ordered_ids:
            try:
                self.ai_manager.admin_reorder_sys_models(db_id, ordered_ids)
                self.log("✓ 已同步更新模型排序", tag="success")
            except Exception as e:
                self.log(f"✗ 模型排序失败: {e}", tag="error")

    def delete_model(self):
        """删除选中的模型（软禁用）。"""
        platform_name = self._resolve_platform_name()
        if not platform_name:
            return

        display_name = self._get_selected_model_display_name()
        if not display_name:
            self.show_warning("警告", "请先选择要删除的模型")
            return

        def on_confirm_delete():
            try:
                model_cfg = self.current_config[platform_name].get("models", {}).get(display_name)
                if isinstance(model_cfg, dict) and model_cfg.get("_db_id"):
                    self.ai_manager.disable_model(model_cfg["_db_id"], admin_mode=True)
                    self.selected_model_display_name = ""
                    self.load_config_from_db()
                else:
                    raise ValueError("无法获取模型数据库 ID")
                self.log(f"✓ 已删除模型: {display_name}", tag="success")
                self.show_snack(f"模型 '{display_name}' 已成功删除！")
            except Exception as e:
                self.log(f"✗ 删除模型失败: {e}", tag="error")
                self.show_error("错误", f"删除模型失败: {e}")

        self.ask_yes_no(
            "确认删除",
            f"确定要删除模型 '{display_name}' 吗？\n删除后该模型将从列表中移除（保留历史记录软禁用）。",
            on_yes=on_confirm_delete,
        )
