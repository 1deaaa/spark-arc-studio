"""
主窗口 — LLMConfigGUI 主类，混入所有 Mixin，构建 UI 布局
"""
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox

# 设置环境变量，允许在没有 LLM_KEY 的情况下导入 llm_mgr
os.environ.setdefault("LLM_MGR_ALLOW_NO_KEY", "1")

# 路径调整：确保 server/ 在 sys.path 中
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_SERVER_DIR = os.path.abspath(os.path.join(_THIS_DIR, "..", "..", ".."))
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)

from llm.llm_mgr.manager import AIManager
from llm.llm_mgr.security import SecurityManager

# 导入各 Mixin
from llm.llm_mgr.gui.platform_panel import PlatformPanelMixin
from llm.llm_mgr.gui.model_panel import ModelPanelMixin
from llm.llm_mgr.gui.dialogs import DialogsMixin
from llm.llm_mgr.gui.key_manager import KeyManagerMixin
from llm.llm_mgr.gui.testing import TestingMixin


class LLMConfigGUI(
    PlatformPanelMixin,
    ModelPanelMixin,
    DialogsMixin,
    KeyManagerMixin,
    TestingMixin,
):
    """LLM 配置管理器主窗口。

    通过 Mixin 组合各功能模块：
    - PlatformPanelMixin: 平台 CRUD、排序
    - ModelPanelMixin: 模型探测、筛选、拖拽排序、CRUD
    - DialogsMixin: 添加/编辑模型对话框、系统用途管理
    - KeyManagerMixin: LLM_KEY 检查/设置、API Key 管理
    - TestingMixin: 模型测试、Embedding 测试、测速

    注意：删除操作实质为禁用（软删除），禁用后的平台/模型不再在 GUI 中展示。
    """

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("LLM 配置管理器")
        self.root.geometry("1280x800")
        self.root.minsize(900, 600)

        # 状态
        self.current_config: dict = {}
        self.probe_models_cache: dict = {}
        self.platform_display_to_key: dict = {}
        self.platform_keys_in_order: list = []
        self.last_selected_platform_name: str = ""

        # 初始化 AIManager
        try:
            self.ai_manager = AIManager()
        except Exception as e:
            messagebox.showerror("初始化失败", f"AIManager 初始化失败: {e}")
            raise

        # 构建 UI
        self._build_styles()
        self._build_ui()

        # 启动时检查 LLM_KEY
        self.root.after(100, self._check_and_set_llm_key)

        # 加载数据库配置
        self.root.after(200, self.load_config_from_db)

    # ------------------------------------------------------------------ #
    #  样式                                                                 #
    # ------------------------------------------------------------------ #

    def _build_styles(self):
        """配置 ttk 样式。"""
        style = ttk.Style()
        style.configure("Toolbar.TFrame", relief="flat")
        style.configure("Log.TFrame", relief="sunken", borderwidth=1)

    # ------------------------------------------------------------------ #
    #  UI 构建                                                              #
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        """构建主界面布局。"""
        # 顶部工具栏
        self._build_toolbar()

        # 主内容区（左右分割）
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        # 左侧：平台 + 模型面板
        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=1)
        self._build_left_panel(left_frame)

        # 右侧：探测面板 + 日志
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=1)
        self._build_right_panel(right_frame)

    def _build_toolbar(self):
        """构建顶部工具栏。"""
        toolbar = ttk.Frame(self.root, style="Toolbar.TFrame", padding=(5, 4))
        toolbar.pack(fill=tk.X, side=tk.TOP)

        ttk.Button(toolbar, text="🔄 刷新", command=self.load_config_from_db, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="📥 从YAML重置DB", command=self.reload_from_yaml, width=16).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="📤 导出DB到YAML", command=self.export_db_to_yaml, width=16).pack(side=tk.LEFT, padx=2)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)

        ttk.Button(toolbar, text="🔑 设置主密钥", command=self.open_set_llm_key_dialog, width=14).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="⚙ 系统模型管理", command=self.edit_system_model, width=16).pack(side=tk.LEFT, padx=2)

    def _build_left_panel(self, parent):
        """构建左侧面板（平台 + 模型）。"""
        left_paned = ttk.PanedWindow(parent, orient=tk.VERTICAL)
        left_paned.pack(fill=tk.BOTH, expand=True)

        # 平台面板
        plat_frame = ttk.LabelFrame(left_paned, text="平台管理", padding="5")
        left_paned.add(plat_frame, weight=1)
        self._build_platform_panel(plat_frame)

        # 模型面板
        model_frame = ttk.LabelFrame(left_paned, text="模型管理 长按拖动排序", padding="5")
        left_paned.add(model_frame, weight=2)
        self._build_model_panel(model_frame)

    def _build_platform_panel(self, parent):
        """构建平台管理面板。"""
        # 平台选择行
        select_row = ttk.Frame(parent)
        select_row.pack(fill=tk.X, pady=(0, 4))

        ttk.Label(select_row, text="平台:").pack(side=tk.LEFT)
        self.platform_var = tk.StringVar()
        self.platform_combo = ttk.Combobox(
            select_row, textvariable=self.platform_var,
            state='readonly', width=28
        )
        self.platform_combo.pack(side=tk.LEFT, padx=(4, 0), fill=tk.X, expand=True)
        self.platform_combo.bind("<<ComboboxSelected>>", self.on_platform_selected)

        # Base URL（只读显示）
        url_row = ttk.Frame(parent)
        url_row.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(url_row, text="URL:").pack(side=tk.LEFT)
        self.base_url_entry = ttk.Entry(url_row, state='readonly', width=40)
        self.base_url_entry.pack(side=tk.LEFT, padx=(4, 0), fill=tk.X, expand=True)

        # 编辑 URL 行
        edit_url_row = ttk.Frame(parent)
        edit_url_row.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(edit_url_row, text="新URL:").pack(side=tk.LEFT)
        self.platform_url_entry = ttk.Entry(edit_url_row, width=34)
        self.platform_url_entry.pack(side=tk.LEFT, padx=(4, 4), fill=tk.X, expand=True)
        ttk.Button(edit_url_row, text="保存URL", command=self.save_platform_url, width=8).pack(side=tk.LEFT)

        # API Key 行
        key_row = ttk.Frame(parent)
        key_row.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(key_row, text="API Key:").pack(side=tk.LEFT)
        self.api_key_entry = ttk.Entry(key_row, width=30, show="*")
        self.api_key_entry.pack(side=tk.LEFT, padx=(4, 4), fill=tk.X, expand=True)
        ttk.Button(key_row, text="保存Key", command=self.save_api_key, width=8).pack(side=tk.LEFT)

        # 平台操作按钮
        btn_row = ttk.Frame(parent)
        btn_row.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(btn_row, text="+ 添加平台", command=self.add_platform).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="✕ 删除平台", command=self.delete_platform).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="⭐ 设为默认", command=self.set_as_default).pack(side=tk.LEFT, padx=2)

    def _build_model_panel(self, parent):
        """构建模型管理面板。"""
        # 模型列表
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.model_listbox = tk.Listbox(list_frame, selectmode=tk.SINGLE, height=12)
        model_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.model_listbox.yview)
        self.model_listbox.configure(yscrollcommand=model_scroll.set)
        self.model_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        model_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # 拖拽排序绑定
        self.model_listbox.bind("<ButtonPress-1>", self.on_model_drag_start)
        self.model_listbox.bind("<B1-Motion>", self.on_model_drag_motion)
        self.model_listbox.bind("<ButtonRelease-1>", self.on_model_drag_stop)

        # 模型操作按钮
        btn_row = ttk.Frame(parent)
        btn_row.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(btn_row, text="+ 添加模型", command=self.open_add_model_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="✎ 编辑模型", command=self.edit_model).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="✕ 删除模型", command=self.delete_model).pack(side=tk.LEFT, padx=2)

        # 测试按钮行
        test_row = ttk.Frame(parent)
        test_row.pack(fill=tk.X, pady=(2, 0))
        ttk.Button(test_row, text="🧪 测试模型", command=self.test_model).pack(side=tk.LEFT, padx=2)
        ttk.Button(test_row, text="🔢 测试Embedding", command=self.test_embedding).pack(side=tk.LEFT, padx=2)
        ttk.Button(test_row, text="⚡ 测速", command=self.speed_test_model).pack(side=tk.LEFT, padx=2)

    def _build_right_panel(self, parent):
        """构建右侧面板（探测 + 日志）。"""
        right_paned = ttk.PanedWindow(parent, orient=tk.VERTICAL)
        right_paned.pack(fill=tk.BOTH, expand=True)

        # 探测面板
        probe_frame = ttk.LabelFrame(right_paned, text="模型探测", padding="5")
        right_paned.add(probe_frame, weight=2)
        self._build_probe_panel(probe_frame)

        # 日志面板
        log_frame = ttk.LabelFrame(right_paned, text="操作日志", padding="5")
        right_paned.add(log_frame, weight=1)
        self._build_log_panel(log_frame)

    def _build_probe_panel(self, parent):
        """构建探测面板。"""
        # 筛选行
        filter_row = ttk.Frame(parent)
        filter_row.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(filter_row, text="筛选:").pack(side=tk.LEFT)
        self.filter_entry = ttk.Entry(filter_row, width=24)
        self.filter_entry.pack(side=tk.LEFT, padx=(4, 4), fill=tk.X, expand=True)
        self.filter_entry.bind("<KeyRelease>", self.on_filter_change)
        ttk.Button(filter_row, text="清除", command=self.clear_filter, width=6).pack(side=tk.LEFT)

        # 探测结果列表
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=tk.BOTH, expand=True)
        self.probe_listbox = tk.Listbox(list_frame, selectmode=tk.SINGLE, height=14)
        probe_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.probe_listbox.yview)
        self.probe_listbox.configure(yscrollcommand=probe_scroll.set)
        self.probe_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        probe_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # 探测操作按钮
        btn_row = ttk.Frame(parent)
        btn_row.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(btn_row, text="🔍 探测模型", command=self.probe_models).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="+ 添加选中", command=self.open_add_model_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="✎ 自定义名称添加", command=self.use_custom_model_name).pack(side=tk.LEFT, padx=2)

    def _build_log_panel(self, parent):
        """构建日志面板。"""
        self.log_text = tk.Text(parent, height=8, state='normal', wrap=tk.WORD)
        log_scroll = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # 配置日志标签样式
        self.log_text.tag_configure("success", foreground="green")
        self.log_text.tag_configure("error", foreground="red")
        self.log_text.tag_configure("warning", foreground="orange")

    # ------------------------------------------------------------------ #
    #  日志                                                                 #
    # ------------------------------------------------------------------ #

    def log(self, message, tag=None):
        """向日志区域追加一行消息。"""
        if tag:
            self.log_text.insert(tk.END, f"{message}\n", tag)
        else:
            self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)

    # ------------------------------------------------------------------ #
    #  数据加载                                                             #
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
                p_name = p['name']
                models = {}
                for m in p.get('models', []):
                    # 跳过已禁用的模型（删除=禁用，不展示）
                    if bool(m.get('disabled')):
                        continue
                    display_name = m['display_name']
                    model_cfg = {
                        "model_name": m['model_name'],
                        "is_embedding": bool(m['is_embedding']),
                        "_db_id": m['_db_id'],
                    }
                    if m.get('temperature') is not None:
                        model_cfg["temperature"] = m['temperature']
                    if m.get('extra_body'):
                        model_cfg["extra_body"] = m['extra_body']
                    models[display_name] = model_cfg

                # 解密 API Key
                api_key_val = ""
                raw_key = p.get('api_key', '')
                if raw_key:
                    try:
                        api_key_val = self._decrypt_api_key_strict(raw_key)
                    except Exception:
                        api_key_val = ""

                db_config[p_name] = {
                    "base_url": p['base_url'],
                    "api_key": api_key_val,
                    "models": models,
                    "_db_id": p['platform_id'],
                }

            self.current_config = db_config
            self._refresh_platform_combo()

            if self.current_config:
                self.on_platform_selected()
            else:
                self.platform_var.set("")
                self.model_listbox.delete(0, tk.END)

            self.log("✓ 已从数据库加载配置", tag="success")

        except Exception as e:
            messagebox.showerror("错误", f"从数据库加载失败: {e}")
            self.log(f"✗ 从数据库加载失败: {e}")

    def reload_from_yaml(self):
        """强制从 YAML 重置数据库（调用后端 admin_reload_from_yaml）。"""
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
            self.log("✓ 数据库已从 YAML 重置", tag="success")
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
    #  内部工具（覆盖 Mixin 中的简化版本，使用更精确的索引匹配）              #
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

        # 平台名称直接作为显示值（不再有禁用标记）
        self.platform_combo['values'] = platform_names
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
        """严格解密 API Key，支持多层 ENC 嵌套。"""
        if not api_key_val:
            return ""
        if not isinstance(api_key_val, str):
            raise ValueError("API Key 数据类型错误")

        text = api_key_val.strip()
        if not text:
            return ""
        if not text.startswith("ENC:"):
            return text

        sec_mgr = SecurityManager.get_instance()
        for _ in range(5):
            text = sec_mgr.decrypt(text)
            if not text:
                raise ValueError("API Key 解密失败，请检查 LLM_KEY")
            if not text.startswith("ENC:"):
                return text
        raise ValueError("API Key 解密层级异常（疑似重复加密）")

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
    root = tk.Tk()
    app = LLMConfigGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
