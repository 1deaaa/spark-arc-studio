"""
LLM 配置管理器 - 图形化界面

⚠️ 重要说明：系统平台的两种数据源

1. 数据库模式 (推荐)
   - 直接操作 SQLite 数据库 (llm_config.db)
   - 修改即时生效，无需重启服务
   - 适用于：生产环境、需要动态修改配置、有前端 Web 管理界面

2. YAML 模式 (传统)
   - 直接操作 YAML 文件 (llm_mgr_cfg.yaml)
   - 修改后需重启服务才生效
   - 适用于：无前端环境、快速部署、配置模板分发、版本控制

同步策略：
- 首次启动时，YAML 配置初始化到数据库
- 后续启动时，仅添加 YAML 中新增的平台，不覆盖已有配置
- 可通过"从 YAML 重置"按钮强制同步

支持平台和模型的添加、编辑、删除操作
"""
import os
import ast
import yaml
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
import threading
import json as json_lib

# 配置工具启动时：允许 llm_mgr 在缺少 LLM_KEY 的情况下被导入。
# 否则会出现“配置密钥的工具依赖 llm_mgr，而 llm_mgr 又强制要求 LLM_KEY”的循环依赖。
os.environ.setdefault("LLM_MGR_ALLOW_NO_KEY", "1")

# 调整导入路径以支持直接运行和作为模块导入
try:
    # 尝试作为包的一部分导入
    from .manager import AIManager
    from .utils import (
        probe_platform_models, stream_speed_test, test_platform_embedding,
        normalize_base_url, test_platform_chat
    )
    from .security import SecurityManager
    from .config import load_default_platform_configs, DEFAULT_PLATFORM_CONFIGS
    from .env_utils import get_env_var, set_env_var
    
    # 构造一个兼容的对象以支持旧代码中的 llm_mgr.xxx 调用
    class LLMMgrMock:
        pass
    llm_mgr = LLMMgrMock()
    llm_mgr.AIManager = AIManager
    llm_mgr.probe_platform_models = probe_platform_models
    llm_mgr.stream_speed_test = stream_speed_test
    llm_mgr.test_platform_embedding = test_platform_embedding
    llm_mgr.test_platform_chat = test_platform_chat
    llm_mgr.normalize_base_url = normalize_base_url
    llm_mgr.SecurityManager = SecurityManager
    llm_mgr.load_default_platform_configs = load_default_platform_configs
    llm_mgr.DEFAULT_PLATFORM_CONFIGS = DEFAULT_PLATFORM_CONFIGS
except (ImportError, ValueError):
    # 尝试作为独立脚本运行
    import sys
    # 获取 server 目录 (llm_mgr_cfg_gui.py -> llm_mgr -> llm -> server)
    curr_path = os.path.dirname(os.path.abspath(__file__))
    server_path = os.path.abspath(os.path.join(curr_path, "../../")) # 注意：这里是 server 目录
    
    if server_path not in sys.path:
        sys.path.insert(0, server_path)
    
    try:
        # 通过全路径导入，这样内部的相对导入就能工作了
        from llm.llm_mgr.manager import AIManager
        from llm.llm_mgr.utils import (
            probe_platform_models, stream_speed_test, test_platform_embedding,
            normalize_base_url, test_platform_chat
        )
        from llm.llm_mgr.security import SecurityManager
        from llm.llm_mgr.config import load_default_platform_configs, DEFAULT_PLATFORM_CONFIGS
        from llm.llm_mgr.env_utils import get_env_var, set_env_var
        
        class LLMMgrMock:
            pass
        llm_mgr = LLMMgrMock()
        llm_mgr.AIManager = AIManager
        llm_mgr.probe_platform_models = probe_platform_models
        llm_mgr.stream_speed_test = stream_speed_test
        llm_mgr.test_platform_embedding = test_platform_embedding
        llm_mgr.test_platform_chat = test_platform_chat
        llm_mgr.normalize_base_url = normalize_base_url
        llm_mgr.SecurityManager = SecurityManager
        llm_mgr.load_default_platform_configs = load_default_platform_configs
        llm_mgr.DEFAULT_PLATFORM_CONFIGS = DEFAULT_PLATFORM_CONFIGS
    except ImportError as e:
        print(f"导入失败: {e}")
        # 兜底处理
        AIManager = None
        probe_platform_models = None
        stream_speed_test = None
        test_platform_embedding = None
        test_platform_chat = None
        normalize_base_url = None
        SecurityManager = None
        llm_mgr = None


class LLMConfigGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("LLM 配置管理器")
        self.root.geometry("1200x850")
        
        # 检查并强制设置 LLM_KEY
        self._check_and_set_llm_key()
        
        # 初始化 AIManager
        # 确保数据库路径正确（相对于 server 根目录）
        self.ai_manager = AIManager()
        
        # 数据源模式：'database' 或 'yaml'
        # 默认使用数据库模式（推荐）
        self.data_mode = 'database'
        
        # 创建主框架
        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        
        # 顶部：模式选择
        mode_frame = ttk.LabelFrame(main_frame, text="⚠️ 数据源选择（请仔细阅读说明）", padding="5")
        mode_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.mode_var = tk.StringVar(value='database')
        
        # 数据库模式
        db_radio = ttk.Radiobutton(
            mode_frame,
            text="📦 数据库模式 (推荐)",
            variable=self.mode_var,
            value='database',
            command=self.on_mode_change
        )
        db_radio.grid(row=0, column=0, sticky=tk.W, padx=10)
        ttk.Label(
            mode_frame,
            text="修改即时生效，无需重启服务。适用于生产环境和 Web 前端管理。",
            foreground="gray"
        ).grid(row=0, column=1, sticky=tk.W, padx=5)
        
        # YAML 模式
        yaml_radio = ttk.Radiobutton(
            mode_frame,
            text="📄 YAML 模式",
            variable=self.mode_var,
            value='yaml',
            command=self.on_mode_change
        )
        yaml_radio.grid(row=1, column=0, sticky=tk.W, padx=10)
        ttk.Label(
            mode_frame,
            text="修改后需重启服务。适用于配置分享、版本控制、无前端环境。",
            foreground="gray"
        ).grid(row=1, column=1, sticky=tk.W, padx=5)
        
        # 同步按钮
        sync_frame = ttk.Frame(mode_frame)
        sync_frame.grid(row=0, column=2, rowspan=2, padx=20)
        ttk.Button(sync_frame, text="从 YAML 重置数据库", command=self.reload_from_yaml).pack(pady=2)
        ttk.Button(sync_frame, text="导出数据库到 YAML", command=self.export_db_to_yaml).pack(pady=2)
        
        # 左侧：平台列表
        left_frame = ttk.LabelFrame(main_frame, text="系统平台配置", padding="5")
        left_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        # 平台选择和管理
        platform_header_frame = ttk.Frame(left_frame)
        platform_header_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(platform_header_frame, text="选择平台:").pack(side=tk.LEFT, padx=5)
        self.platform_var = tk.StringVar()
        self.platform_combo = ttk.Combobox(platform_header_frame, textvariable=self.platform_var, state='normal', width=25)
        self.platform_combo.pack(side=tk.LEFT, padx=5)
        self.platform_combo.bind('<<ComboboxSelected>>', self.on_platform_selected)
        self.platform_combo.bind('<FocusOut>', self.rename_platform)
        self.platform_combo.bind('<Return>', self.rename_platform)
        
        # 平台管理按钮
        ttk.Button(platform_header_frame, text="设为默认", command=self.set_as_default).pack(side=tk.LEFT, padx=2)
        ttk.Button(platform_header_frame, text="添加平台", command=self.add_platform).pack(side=tk.LEFT, padx=2)
        ttk.Button(platform_header_frame, text="删除平台", command=self.delete_platform).pack(side=tk.LEFT, padx=2)
        ttk.Button(platform_header_frame, text="系统用途管理", command=self.edit_system_model).pack(side=tk.LEFT, padx=2)
        # 模型列表
        ttk.Label(left_frame, text="当前模型:").grid(row=1, column=0, sticky=(tk.W, tk.N), pady=5)
        
        model_frame = ttk.Frame(left_frame)
        model_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5, padx=5)
        
        self.model_listbox = tk.Listbox(model_frame, height=10, width=40)
        model_scrollbar = ttk.Scrollbar(model_frame, orient=tk.VERTICAL, command=self.model_listbox.yview)
        self.model_listbox.configure(yscrollcommand=model_scrollbar.set)
        self.model_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        model_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        # 绑定双击事件到编辑
        self.model_listbox.bind('<Double-Button-1>', lambda e: self.edit_model())
        # 绑定拖动排序事件
        self.model_listbox.bind('<Button-1>', self.on_model_drag_start)
        self.model_listbox.bind('<B1-Motion>', self.on_model_drag_motion)
        self.model_listbox.bind('<ButtonRelease-1>', self.on_model_drag_stop)
        
        # 模型操作按钮
        model_btn_frame = ttk.Frame(left_frame)
        model_btn_frame.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        
        ttk.Label(model_btn_frame, text="* 按住拖动可排序", foreground="gray", font=('TkDefaultFont', 8)).pack(side=tk.LEFT)
        
        btns_frame = ttk.Frame(model_btn_frame)
        btns_frame.pack(side=tk.RIGHT)
        
        ttk.Button(btns_frame, text="测速选中模型", command=self.speed_test_model).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns_frame, text="测试选中模型", command=self.test_model).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns_frame, text="测试Embedding", command=self.test_embedding).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns_frame, text="编辑选中模型", command=self.edit_model).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns_frame, text="删除选中模型", command=self.delete_model).pack(side=tk.LEFT, padx=2)
        
        # 平台 URL 编辑
        ttk.Label(left_frame, text="平台 URL:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.platform_url_entry = ttk.Entry(left_frame, width=40)
        self.platform_url_entry.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        ttk.Button(left_frame, text="保存平台 URL", command=self.save_platform_url).grid(row=4, column=1, sticky=tk.E, pady=5, padx=5)
        
        # 右侧：探测模型
        right_frame = ttk.LabelFrame(main_frame, text="模型探测", padding="5")
        right_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        # 探测配置区域
        ttk.Label(right_frame, text="Base URL:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.base_url_entry = ttk.Entry(right_frame, width=40, state='readonly')
        self.base_url_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        
        ttk.Label(right_frame, text="API Key:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.api_key_entry = ttk.Entry(right_frame, width=40)
        self.api_key_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        
        # 按钮框架
        button_row_frame = ttk.Frame(right_frame)

        button_row_frame.grid(row=3, column=0, columnspan=2, pady=10)
        ttk.Button(button_row_frame, text="保存 API Key", command=self.save_api_key).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_row_frame, text="探测可用模型", command=self.probe_models).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_row_frame, text="添加模型到平台", command=self.open_add_model_dialog).pack(side=tk.LEFT, padx=5)
        
        # 筛选区域
        filter_frame = ttk.Frame(right_frame)
        filter_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        ttk.Label(filter_frame, text="输入模型名称:").pack(side=tk.LEFT, padx=5)
        self.filter_entry = ttk.Entry(filter_frame, width=30)
        self.filter_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.filter_entry.bind('<KeyRelease>', self.on_filter_change)
        ttk.Button(filter_frame, text="清除", command=self.clear_filter).pack(side=tk.LEFT, padx=2)
        ttk.Button(filter_frame, text="使用此名称", command=self.use_custom_model_name).pack(side=tk.LEFT, padx=2)
        
        # 探测结果（更大的列表）
        ttk.Label(right_frame, text="探测结果:").grid(row=5, column=0, sticky=(tk.W, tk.N), pady=5)
        
        probe_frame = ttk.Frame(right_frame)
        probe_frame.grid(row=5, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5, padx=5)
        
        self.probe_listbox = tk.Listbox(probe_frame, height=20, width=40)
        probe_scrollbar = ttk.Scrollbar(probe_frame, orient=tk.VERTICAL, command=self.probe_listbox.yview)
        self.probe_listbox.configure(yscrollcommand=probe_scrollbar.set)
        self.probe_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        probe_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        # 双击直接打开添加对话框
        self.probe_listbox.bind('<Double-Button-1>', lambda e: self.open_add_model_dialog())
        
        # 底部：日志和保存
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        
        ttk.Label(bottom_frame, text="操作日志:").pack(anchor=tk.W)
        self.log_text = scrolledtext.ScrolledText(bottom_frame, height=8, width=110)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.tag_config("success", foreground="green")
        
        # 底部按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, sticky=tk.E, pady=5)
        ttk.Button(button_frame, text="重新加载配置", command=self.reload_config).pack(side=tk.RIGHT, padx=5)
        ttk.Label(button_frame, text="💡 所有操作自动保存", foreground="green").pack(side=tk.RIGHT, padx=10)
        
        # 配置权重
        main_frame.columnconfigure(0, weight=2)  # 左侧更宽
        main_frame.columnconfigure(1, weight=3)  # 右侧相对窄
        main_frame.rowconfigure(0, weight=3)
        main_frame.rowconfigure(1, weight=1)
        
        left_frame.columnconfigure(1, weight=1)
        left_frame.rowconfigure(1, weight=1)
        
        right_frame.columnconfigure(1, weight=1)
        right_frame.rowconfigure(5, weight=1)  # 探测结果行可扩展
        
        # 当前配置（内存中）
        self.current_config = None
        self.probe_models_cache = {}  # 缓存完整的探测结果 {platform_name: [model_id, ...]}
        self._current_platform_original_api_key = None  # 记录原始 api_key 配置（含占位符）
        self.last_selected_platform_name = None  # 记录上一次选中的平台名称，用于改名
        self.load_config()
    
    def log(self, message, tag=None):
        """添加日志"""
        if tag:
            self.log_text.insert(tk.END, f"{message}\n", tag)
        else:
            self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
    
    def load_config(self):
        """加载配置文件"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), "llm_mgr_cfg.yaml")
            with open(config_path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}

            if not isinstance(loaded, dict):
                raise ValueError("配置文件格式错误，应为字典结构")

            self.current_config = loaded
            platform_names = list(self.current_config.keys())
            self.platform_combo['values'] = platform_names

            if platform_names:
                # 默认选中第一个平台
                self.platform_var.set(platform_names[0])
                self.on_platform_selected()
            else:
                self.platform_var.set("")

            self.log("✓ 配置加载成功", tag="success")
        except Exception as e:
            messagebox.showerror("错误", f"加载配置失败: {e}")
            self.log(f"✗ 加载配置失败: {e}")
            
    def on_mode_change(self):
        """数据源模式切换"""
        new_mode = self.mode_var.get()
        if new_mode == self.data_mode:
            return
            
        self.data_mode = new_mode
        self.log(f"⚡ 切换到 {new_mode} 模式")
        
        # 重新加载对应源的数据
        if self.data_mode == 'database':
            self.load_config_from_db()
        else:
            self.load_config() # 原有逻辑是加载 YAML

    def load_config_from_db(self):
        """从数据库加载配置"""
        try:
            # 使用 admin 方法获取系统平台
            platforms = self.ai_manager.admin_get_sys_platforms()
            
            # 转换为兼容的配置格式
            db_config = {}
            for p in platforms:
                p_id = p['platform_id']
                p_name = p['name']
                
                # 获取平台详细信息（包括模型）
                # 这里我们需要重新查询以获取模型列表，因为 admin_get_sys_platforms 只返回统计
                # 直接使用 proxy_list_models 的逻辑变体或者扩充 admin 接口
                # 暂时我们用比较笨的方法：构造配置字典
                
                # 注意：这里我们只能拿到 API Key 是否设置的状态，无法拿到明文 API Key
                # 除非我们是系统用户且有密钥
                
                # 为了 GUI 编辑方便，我们需要获取完整数据
                # 我们可以直接使用 manager 的 session
                with self.ai_manager.Session() as session:
                    from .models import LLMPlatform, LLMSysPlatformKey
                    plat_obj = session.query(LLMPlatform).filter_by(id=p_id).first()
                    
                    models = {}
                    for m in plat_obj.models:
                        display_name = m.display_name
                        model_cfg = {
                            "model_name": m.model_name,
                            "is_embedding": m.is_embedding
                        }
                        if m.extra_body:
                            try:
                                model_cfg["extra_body"] = json_lib.loads(m.extra_body)
                            except:
                                pass
                        models[display_name] = model_cfg
                    
                    # 获取 API Key (尝试解密)
                    api_key_val = plat_obj.api_key
                    if not api_key_val:
                        # 尝试获取系统配置的默认key (如果 config.py 里有)
                        pass
                    
                    db_config[p_name] = {
                        "base_url": plat_obj.base_url,
                        "api_key": api_key_val, # 保持加密状态或明文
                        "models": models,
                        "_db_id": p_id # 内部标记
                    }

            self.current_config = db_config
            
            # 刷新 UI
            platform_names = list(self.current_config.keys())
            self.platform_combo['values'] = platform_names
            
            if platform_names:
                self.platform_var.set(platform_names[0])
                self.on_platform_selected()
            else:
                self.platform_var.set("")
                self.model_listbox.delete(0, tk.END)
                
            self.log("✓ 已从数据库加载配置", tag="success")
            
        except Exception as e:
            messagebox.showerror("错误", f"从数据库加载失败: {e}")
            self.log(f"✗ 从数据库加载失败: {e}")
            # 回退到 YAML 模式
            self.mode_var.set('yaml')
            self.data_mode = 'yaml'
            self.load_config()

    def reload_from_yaml(self):
        """强制从 YAML 重置数据库"""
        if not messagebox.askyesno("确认重置",
            "⚠️ 警告：这将使用 YAML 文件覆盖数据库中的所有系统平台配置！\n\n"
            "- 数据库中新增的平台将被删除\n"
            "- 平台名称和模型列表将重置为 YAML 中的状态\n"
            "- 用户的 API Key 设置不会受影响\n\n"
            "确定要继续吗？"):
            return
            
        try:
            self.ai_manager.admin_reload_from_yaml()
            self.log("✓ 数据库已从 YAML 重置", tag="success")
            messagebox.showinfo("成功", "数据库已重置。")
            
            # 如果当前在数据库模式，刷新显示
            if self.data_mode == 'database':
                self.load_config_from_db()
                
        except Exception as e:
            messagebox.showerror("错误", f"重置失败: {e}")
            self.log(f"✗ 重置失败: {e}")

    def export_db_to_yaml(self):
        """导出数据库配置到 YAML"""
        if not messagebox.askyesno("确认导出",
            "这将覆盖当前的 llm_mgr_cfg.yaml 文件。\n"
            "确定要导出数据库配置吗？"):
            return
            
        try:
            # 切换到数据库模式以确保加载最新数据
            if self.data_mode != 'database':
                self.load_config_from_db()
            
            # 保存到文件 (复用现有逻辑，因为 current_config 已经是通过 DB 加载的结构)
            self._save_config_to_file()
            
            messagebox.showinfo("成功", "已导出到 llm_mgr_cfg.yaml")
            
        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {e}")
    
    def reload_config(self):
        """重新加载配置"""
        try:
            if self.data_mode == 'database':
                self.load_config_from_db()
            else:
                self.load_config()
            self.log("✓ 配置已重新加载", tag="success")
        except Exception as e:
            messagebox.showerror("错误", f"重新加载失败: {e}")
    
    def on_platform_selected(self, event=None):
        """平台选择变化时更新模型列表"""
        platform_name = self.platform_var.get()
        if not platform_name or platform_name not in self.current_config:
            return
        
        self.last_selected_platform_name = platform_name
        platform_cfg = self.current_config[platform_name]
        self.model_listbox.delete(0, tk.END)
        
        # 立即清空探测结果列表，并尝试从缓存恢复
        self.probe_listbox.delete(0, tk.END)
        if platform_name in self.probe_models_cache:
            cached_models = self.probe_models_cache[platform_name]
            for model_id in cached_models:
                self.probe_listbox.insert(tk.END, model_id)
        
        # 填充 base_url（两个地方，但右侧只读）
        base_url = platform_cfg.get("base_url", "")
        self.base_url_entry.config(state='normal')
        self.base_url_entry.delete(0, tk.END)
        self.base_url_entry.insert(0, base_url)
        self.base_url_entry.config(state='readonly')
        
        self.platform_url_entry.delete(0, tk.END)
        self.platform_url_entry.insert(0, base_url)
        
        # 处理 api_key
        self.api_key_entry.delete(0, tk.END)
        
        # 直接显示解密后的 API Key
        api_key = platform_cfg.get("api_key", "")
        if api_key:
            # 尝试解密
            try:
                decrypted_key = SecurityManager.get_instance().decrypt(api_key)
                self.api_key_entry.insert(0, decrypted_key)
                if isinstance(decrypted_key, str) and decrypted_key.startswith("ENC:"):
                     self.log(f"⚠ API Key 解密失败，请检查 LLM_KEY 是否正确")
            except Exception as e:
                self.api_key_entry.insert(0, api_key)
                self.log(f"⚠ API Key 解密出错: {e}")
        
        # 显示模型列表
        models = platform_cfg.get("models", {})

        for display_name, model_config in models.items():
            self.model_listbox.insert(tk.END, self._format_model_list_item(display_name, model_config))

        # 异步执行一次模型探测
        self.probe_models(auto_start=True)
    
    def rename_platform(self, event=None):
        """给当前选中的平台改名"""
        if not self.last_selected_platform_name:
            return
            
        new_name = self.platform_var.get().strip()
        old_name = self.last_selected_platform_name
        
        if not new_name or new_name == old_name:
            return
            
        if new_name in self.current_config:
            # 如果新名字已存在，恢复旧名字
            self.platform_var.set(old_name)
            return
            
        # 执行改名：在字典中替换 Key，但保持顺序
        new_config = {}
        for k, v in self.current_config.items():
            if k == old_name:
                new_config[new_name] = v
            else:
                new_config[k] = v
        
        self.current_config = new_config
        self.last_selected_platform_name = new_name
        
        # 更新下拉框
        platform_names = list(self.current_config.keys())
        self.platform_combo['values'] = platform_names
        self.platform_var.set(new_name)
        
        self._save_config_to_file()

    def add_platform(self):
        """添加新平台"""
        # 创建对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("添加新平台")
        dialog.geometry("450x250")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 平台名称
        ttk.Label(dialog, text="平台名称:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=10)
        name_entry = ttk.Entry(dialog, width=40)
        name_entry.grid(row=0, column=1, padx=10, pady=10)
        
        # Base URL
        ttk.Label(dialog, text="Base URL:").grid(row=1, column=0, sticky=tk.W, padx=10, pady=10)
        url_entry = ttk.Entry(dialog, width=40)
        url_entry.grid(row=1, column=1, padx=10, pady=10)
        url_entry.insert(0, "https://api.example.com/v1")
        
        # API Key (可选)
        ttk.Label(dialog, text="API Key (可选):").grid(row=2, column=0, sticky=tk.W, padx=10, pady=10)
        key_entry = ttk.Entry(dialog, width=40)
        key_entry.grid(row=2, column=1, padx=10, pady=10)
        
        def do_add():
            name = name_entry.get().strip()
            url = url_entry.get().strip()
            key = key_entry.get().strip()
            
            if not name or not url:
                messagebox.showerror("错误", "平台名称和 Base URL 不能为空", parent=dialog)
                return
            
            # 验证 URL 格式
            if not (url.startswith("http://") or url.startswith("https://")):
                messagebox.showerror("错误", "URL 必须以 http:// 或 https:// 开头", parent=dialog)
                return
            
            # 规范化 URL
            url = normalize_base_url(url)
            
            # 检查名称冲突
            if name in self.current_config:
                messagebox.showerror("错误", f"平台名称 '{name}' 已存在", parent=dialog)
                return
            
            try:
                # 添加到配置
                new_platform = {
                    "base_url": url,
                    "models": {}
                }
                
                # 处理 API Key
                if key:
                    new_platform["api_key"] = key
                else:
                    new_platform["api_key"] = None
                
                self.current_config[name] = new_platform
                
                # 保存到文件
                self._save_config_to_file()
                
                # 刷新界面
                self.platform_combo['values'] = list(self.current_config.keys())
                self.platform_var.set(name)
                self.on_platform_selected()
                
                self.log(f"✓ 平台 '{name}' 已添加", tag="success")
                dialog.destroy()
                
            except Exception as e:
                self.log(f"✗ 添加平台失败: {e}")
                messagebox.showerror("错误", f"添加平台失败: {e}", parent=dialog)
        
        # 按钮
        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=4, column=0, columnspan=2, pady=20)
        ttk.Button(button_frame, text="确定", command=do_add).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        
        # 居中显示
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
    
    def delete_platform(self):
        """删除选中的平台"""
        platform_name = self.platform_var.get()
        if not platform_name or platform_name not in self.current_config:
            if self.last_selected_platform_name:
                platform_name = self.last_selected_platform_name
            else:
                messagebox.showwarning("警告", "请先选择一个有效的平台")
                return
        
        if not messagebox.askyesno("确认", f"确定要删除平台 '{platform_name}' 及其所有模型吗？\n此操作不可恢复！"):
            return
        
        try:
            # 从配置中删除
            if platform_name in self.current_config:
                del self.current_config[platform_name]
            
            # 清除缓存
            if platform_name in self.probe_models_cache:
                del self.probe_models_cache[platform_name]
            
            # 保存到文件
            self._save_config_to_file()
            
            # 刷新界面
            self.platform_combo['values'] = list(self.current_config.keys())
            if self.current_config:
                new_plat = list(self.current_config.keys())[0]
                self.platform_var.set(new_plat)
                self.last_selected_platform_name = new_plat
                self.on_platform_selected()
            else:
                self.platform_var.set("")
                self.last_selected_platform_name = None
                self.model_listbox.delete(0, tk.END)
            
            self.log(f"✓ 平台 '{platform_name}' 已删除", tag="success")
            
        except Exception as e:
            self.log(f"✗ 删除平台失败: {e}")
            messagebox.showerror("错误", f"删除平台失败: {e}")
    
    def save_platform_url(self):
        """保存平台的 base_url"""
        platform_name = self.platform_var.get()
        if not platform_name or platform_name not in self.current_config:
            if self.last_selected_platform_name:
                platform_name = self.last_selected_platform_name
            else:
                messagebox.showwarning("警告", "请先选择一个有效的平台")
                return
        
        new_url = self.platform_url_entry.get().strip()
        if not new_url:
            messagebox.showerror("错误", "请填写平台 URL")
            return
        
        # 验证 URL 格式
        if not (new_url.startswith("http://") or new_url.startswith("https://")):
            messagebox.showerror("错误", "URL 必须以 http:// 或 https:// 开头")
            return
        
        # 规范化 URL
        new_url = normalize_base_url(new_url)
        
        try:
            # 更新配置
            self.current_config[platform_name]["base_url"] = new_url
            
            # 立即保存到配置文件
            self._save_config_to_file()
            
            # 刷新显示
            self.on_platform_selected()
            
            self.log(f"✓ 平台 '{platform_name}' 的 URL 已更新", tag="success")
            
        except Exception as e:
            self.log(f"✗ 保存失败: {e}")
            messagebox.showerror("错误", f"保存平台 URL 失败: {e}")
    
    def save_api_key(self):
        """保存 API Key 到配置文件（加密存储）"""
        platform_name = self.platform_var.get()
        if not platform_name or platform_name not in self.current_config:
            if self.last_selected_platform_name:
                platform_name = self.last_selected_platform_name
            else:
                messagebox.showwarning("警告", "请先选择一个有效的平台")
                return

        api_key = self.api_key_entry.get().strip()
        
        # 如果没有填写 API Key，直接返回
        if not api_key:
            messagebox.showwarning("警告", "请输入 API Key")
            return
        
        try:
            # 直接保存明文到内存配置，_save_config_to_file 会负责加密
            self.current_config[platform_name]["api_key"] = api_key

            self._save_config_to_file()
            self.on_platform_selected()

            self.log(f"✓ 平台 '{platform_name}' 的 API Key 已加密保存", tag="success")

        except Exception as e:
            self.log(f"✗ 保存失败: {e}")
            messagebox.showerror("错误", f"保存 API Key 失败: {e}")
    
    def probe_models(self, auto_start=False):
        """探测平台可用模型"""
        platform_name = self.platform_var.get()
        base_url = self.base_url_entry.get().strip()
        api_key = self.api_key_entry.get().strip()
        
        if not base_url:
            if not auto_start: # 只有用户手动点击时才警告
                messagebox.showwarning("警告", "请先选择平台（Base URL 将自动填充）")
            return

        # 如果缓存已存在，且不是自动启动（手动点击），则直接使用缓存
        if platform_name in self.probe_models_cache and self.probe_models_cache[platform_name]:
            self.log(f"使用缓存的探测结果 ({platform_name})")
            self.probe_listbox.delete(0, tk.END)
            for model_id in self.probe_models_cache[platform_name]:
                self.probe_listbox.insert(tk.END, model_id)
            return
        
        # 验证 API Key（如果输入框有内容就直接使用，否则从配置读取）
        if not api_key or not api_key.strip():
            if not auto_start: # 只有用户手动点击时才警告
                messagebox.showerror("错误", "请在 API Key 输入框中填写有效的密钥")
            self.log("⚠ API Key 未填写，跳过自动探测。")
            return
        
        self.log(f"正在探测 {base_url} ...")
        self.probe_listbox.delete(0, tk.END)
        
        def do_probe():
            try:
                models = probe_platform_models(base_url, api_key, raise_on_error=True)
                self.root.after(0, lambda res=models: self.show_probe_results(res))
            except Exception as e:
                self.root.after(0, lambda err=str(e): self.show_probe_error(err))
        
        threading.Thread(target=do_probe, daemon=True).start()
    
    def show_probe_results(self, models):
        """显示探测结果"""
        if not models:
            self.log("✗ 未探测到任何模型")
            return
        
        platform_name = self.platform_var.get()
        
        # 缓存完整结果
        model_ids = [model.get('id', '') for model in models]
        if platform_name:
            self.probe_models_cache[platform_name] = model_ids
        
        # 显示所有模型
        self.probe_listbox.delete(0, tk.END)
        for model_id in model_ids:
            self.probe_listbox.insert(tk.END, model_id)
        
        self.log(f"✓ 探测到 {len(models)} 个模型", tag="success")
    
    def show_probe_error(self, error_msg):
        """显示探测错误"""
        self.log(f"✗ 探测失败: {error_msg}")
        messagebox.showerror("探测失败", error_msg)
    
    def on_filter_change(self, event=None):
        """筛选关键字变化时更新列表"""
        platform_name = self.platform_var.get()
        keyword = self.filter_entry.get().strip().lower()
        
        self.probe_listbox.delete(0, tk.END)
        
        # 获取当前平台的缓存
        cached_models = self.probe_models_cache.get(platform_name, [])
        
        if not keyword:
            # 没有关键字，显示所有
            for model_id in cached_models:
                self.probe_listbox.insert(tk.END, model_id)
        else:
            # 筛选匹配的模型
            filtered = [m for m in cached_models if keyword in m.lower()]
            for model_id in filtered:
                self.probe_listbox.insert(tk.END, model_id)
            
            if filtered:
                self.log(f"筛选结果: {len(filtered)} 个模型匹配 '{keyword}'")
            else:
                self.log(f"筛选结果: 没有模型匹配 '{keyword}'")
    
    def clear_filter(self):
        """清除筛选"""
        self.filter_entry.delete(0, tk.END)
        self.on_filter_change()

    def use_custom_model_name(self):
        """使用筛选框中输入的自定义名称打开添加模型对话框"""
        custom_model_id = self.filter_entry.get().strip()
        if not custom_model_id:
            messagebox.showwarning("警告", "请输入要使用的模型名称")
            return
        self.open_add_model_dialog(custom_model_id=custom_model_id)

    def _format_model_list_item(self, display_name: str, model_config) -> str:
        if isinstance(model_config, str):
            model_id = model_config
            is_embedding = False
        else:
            model_id = model_config.get("model_name", "")
            is_embedding = bool(model_config.get("is_embedding"))

        tag = " [EMB]" if is_embedding else ""
        return f"{display_name}{tag} → {model_id}"

    def _extract_display_name(self, item_text: str) -> str:
        display_part = item_text.split(" → ")[0]
        if display_part.endswith(" [EMB]"):
            display_part = display_part[:-6]
        return display_part
    
    def open_add_model_dialog(self, custom_model_id=None):
        """打开添加模型对话框"""
        platform_name = self.platform_var.get()
        if not platform_name:
            messagebox.showwarning("警告", "请先选择一个平台")
            return
        
        # 获取选中的模型ID（如果有）
        if custom_model_id:
            selected_model_id = custom_model_id
        else:
            selected_model_id = ""
            selection = self.probe_listbox.curselection()
            if selection:
                selected_model_id = self.probe_listbox.get(selection[0])
        
        # 创建对话框
        dialog = tk.Toplevel(self.root)
        dialog.title(f"添加模型到 {platform_name}")
        dialog.geometry("550x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 显示名称
        ttk.Label(dialog, text="显示名称:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=10)
        display_name_entry = ttk.Entry(dialog, width=50)
        display_name_entry.grid(row=0, column=1, padx=10, pady=10, sticky=(tk.W, tk.E))
        if selected_model_id:
            display_name_entry.insert(0, selected_model_id)
        
        # 模型ID
        ttk.Label(dialog, text="模型ID:").grid(row=1, column=0, sticky=tk.W, padx=10, pady=10)
        model_id_entry = ttk.Entry(dialog, width=50)
        model_id_entry.grid(row=1, column=1, padx=10, pady=10, sticky=(tk.W, tk.E))
        if selected_model_id:
            model_id_entry.insert(0, selected_model_id)
        
        # Embedding 标记
        is_embedding_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(dialog, text="Embedding 模型", variable=is_embedding_var).grid(row=2, column=1, sticky=tk.W, padx=10)

        # Extra Body
        ttk.Label(dialog, text="Extra Body (JSON):").grid(row=3, column=0, sticky=(tk.W, tk.N), padx=10, pady=10)
        
        extra_body_frame = ttk.Frame(dialog)
        extra_body_frame.grid(row=3, column=1, padx=10, pady=10, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        extra_body_text = tk.Text(extra_body_frame, width=50, height=8)
        extra_body_text.pack(fill=tk.BOTH, expand=True)
        
        # 示例说明
        example_label = ttk.Label(extra_body_frame, 
                                  text='示例1: {"thinkingBudget": 0}\n'
                                       '示例2: {"thinking": {"type": "disabled"}}\n'
                                       '示例3: {"top_k": 40, "temperature": 0.7}',
                                  foreground="gray", 
                                  font=('TkDefaultFont', 8),
                                  justify=tk.LEFT)
        example_label.pack(anchor=tk.W, pady=(5, 0))
        
        def do_add():
            display_name = display_name_entry.get().strip()
            model_id = model_id_entry.get().strip()
            
            if not display_name or not model_id:
                messagebox.showwarning("警告", "请填写显示名称和模型ID", parent=dialog)
                return
            
            # 检查显示名称是否重复
            if display_name in self.current_config[platform_name].get("models", {}):
                if not messagebox.askyesno("确认", 
                    f"显示名称 '{display_name}' 已存在，是否覆盖？", 
                    parent=dialog):
                    return
            
            # 解析 extra_body
            extra_body_str = extra_body_text.get("1.0", tk.END)
            try:
                extra_body = self._parse_extra_body(extra_body_str)
            except ValueError as err:
                messagebox.showerror("错误", str(err), parent=dialog)
                return
            
            # 添加到内存配置
            if "models" not in self.current_config[platform_name]:
                self.current_config[platform_name]["models"] = {}
            
            is_embedding = bool(is_embedding_var.get())

            # 根据是否有 extra_body / embedding 标记 选择存储格式
            if extra_body or is_embedding:
                payload = {
                    "model_name": model_id,
                }
                if extra_body:
                    payload["extra_body"] = extra_body
                if is_embedding:
                    payload["is_embedding"] = True
                self.current_config[platform_name]["models"][display_name] = payload
            else:
                self.current_config[platform_name]["models"][display_name] = model_id
            
            # 立即保存到配置文件
            try:
                self._save_config_to_file()
                self.log(f"✓ 模型 '{display_name}' 已添加", tag="success")
            except Exception as e:
                self.log(f"✗ 保存失败: {e}")
                messagebox.showerror("错误", f"添加模型失败: {e}", parent=dialog)
                return
            
            # 刷新显示
            self.on_platform_selected()
            dialog.destroy()
        
        # 按钮
        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=4, column=0, columnspan=2, pady=20)
        ttk.Button(button_frame, text="添加", command=do_add, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消", command=dialog.destroy, width=15).pack(side=tk.LEFT, padx=5)
        
        # 配置权重
        dialog.columnconfigure(1, weight=1)
        dialog.rowconfigure(3, weight=1)
        
        # 居中显示
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
    
    def on_model_drag_start(self, event):
        """开始拖动模型"""
        # 记录起始位置和索引
        index = self.model_listbox.nearest(event.y)
        if index < 0:
            return
        self._drag_data = {"y": event.y, "index": index}
        # 确保选中当前项（因为我们绑定了 Button-1，可能会覆盖默认行为）
        # 但为了不破坏多选等默认行为，我们只在确实发生拖动时才干预
        # 这里先不做 selection_set，让默认行为处理选中

    def on_model_drag_motion(self, event):
        """拖动中"""
        if not hasattr(self, '_drag_data'):
            return
        
        new_index = self.model_listbox.nearest(event.y)
        old_index = self._drag_data["index"]
        
        if new_index != old_index:
            # 移动列表项
            text = self.model_listbox.get(old_index)
            self.model_listbox.delete(old_index)
            self.model_listbox.insert(new_index, text)
            self.model_listbox.selection_clear(0, tk.END)
            self.model_listbox.selection_set(new_index)
            self.model_listbox.activate(new_index)
            self._drag_data["index"] = new_index

    def on_model_drag_stop(self, event):
        """结束拖动"""
        if not hasattr(self, '_drag_data'):
            return
        
        # 重新排序配置
        self.reorder_models()
        del self._drag_data

    def reorder_models(self):
        """根据列表框顺序更新配置"""
        platform_name = self.platform_var.get()
        if not platform_name or platform_name not in self.current_config:
            return
            
        current_models = self.current_config[platform_name].get("models", {})
        if not current_models:
            return
            
        new_models = {}
        # 遍历列表框中的每一项
        for i in range(self.model_listbox.size()):
            item_text = self.model_listbox.get(i)
            # 解析显示名称： "display_name → model_id" (兼容 embedding 标记)
            display_name = self._extract_display_name(item_text)
            
            if display_name in current_models:
                new_models[display_name] = current_models[display_name]
        
        # 更新配置
        self.current_config[platform_name]["models"] = new_models
        self._save_config_to_file()
        # self.log("✓ 模型顺序已更新") # 静默更新，不打扰用户

    def edit_model(self):
        """编辑选中的模型（打开编辑对话框）"""
        platform_name = self.platform_var.get()
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
        
        # 解析模型配置
        if isinstance(model_config, str):
            model_id = model_config
            extra_body_dict = None
            is_embedding = False
        else:
            model_id = model_config.get("model_name", "")
            extra_body_dict = model_config.get("extra_body")
            is_embedding = bool(model_config.get("is_embedding"))
        
        # 创建编辑对话框
        dialog = tk.Toplevel(self.root)
        dialog.title(f"编辑模型: {display_name}")
        dialog.geometry("550x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 显示名称
        ttk.Label(dialog, text="显示名称:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=10)
        display_name_entry = ttk.Entry(dialog, width=50)
        display_name_entry.grid(row=0, column=1, padx=10, pady=10, sticky=(tk.W, tk.E))
        display_name_entry.insert(0, display_name)
        # display_name_entry.config(state='readonly') # 允许编辑已有模型名字
        
        # 模型ID
        ttk.Label(dialog, text="模型ID:").grid(row=1, column=0, sticky=tk.W, padx=10, pady=10)
        model_id_entry = ttk.Entry(dialog, width=50)
        model_id_entry.grid(row=1, column=1, padx=10, pady=10, sticky=(tk.W, tk.E))
        model_id_entry.insert(0, model_id)
        model_id_entry.config(state='readonly') # 禁止编辑已有模型ID
        
        # Embedding 标记
        is_embedding_var = tk.BooleanVar(value=is_embedding)
        ttk.Checkbutton(dialog, text="Embedding 模型", variable=is_embedding_var).grid(row=2, column=1, sticky=tk.W, padx=10)

        # Extra Body
        ttk.Label(dialog, text="Extra Body (JSON):").grid(row=3, column=0, sticky=(tk.W, tk.N), padx=10, pady=10)
        
        extra_body_frame = ttk.Frame(dialog)
        extra_body_frame.grid(row=3, column=1, padx=10, pady=10, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        extra_body_text = tk.Text(extra_body_frame, width=50, height=8)
        extra_body_text.pack(fill=tk.BOTH, expand=True)
        
        if extra_body_dict:
            import json
            extra_body_text.insert("1.0", json.dumps(extra_body_dict, indent=2, ensure_ascii=False))
        
        # 示例说明
        example_label = ttk.Label(extra_body_frame, 
                                  text='示例1: {"thinkingBudget": 0}\n'
                                       '示例2: {"thinking": {"type": "disabled"}}\n'
                                       '示例3: {"top_k": 40, "temperature": 0.7}',
                                  foreground="gray", 
                                  font=('TkDefaultFont', 8),
                                  justify=tk.LEFT)
        example_label.pack(anchor=tk.W, pady=(5, 0))
        def do_update():
            new_display_name = display_name_entry.get().strip()
            new_model_id = model_id_entry.get().strip()
            
            if not new_display_name or not new_model_id:
                messagebox.showwarning("警告", "请填写显示名称和模型ID", parent=dialog)
                return
            
            # 检查显示名称是否与其他模型冲突
            if new_display_name != display_name and new_display_name in self.current_config[platform_name].get("models", {}):
                if not messagebox.askyesno("确认",
                    f"显示名称 '{new_display_name}' 已存在，是否覆盖？",
                    parent=dialog):
                    return
                return
            
            # 解析 extra_body
            extra_body_str = extra_body_text.get("1.0", tk.END)
            try:
                extra_body = self._parse_extra_body(extra_body_str)
            except ValueError as err:
                messagebox.showerror("错误", str(err), parent=dialog)
                return
            
            # 如果显示名称改变，删除旧的配置
            if new_display_name != display_name:
                del self.current_config[platform_name]["models"][display_name]
            
            # 更新配置
            is_embedding = bool(is_embedding_var.get())
            if extra_body or is_embedding:
                payload = {
                    "model_name": new_model_id,
                }
                if extra_body:
                    payload["extra_body"] = extra_body
                if is_embedding:
                    payload["is_embedding"] = True
                self.current_config[platform_name]["models"][new_display_name] = payload
            else:
                self.current_config[platform_name]["models"][new_display_name] = new_model_id
            
            # 立即保存到配置文件
            try:
                self._save_config_to_file()
                self.log(f"✓ 模型 '{new_display_name}' 已更新", tag="success")
            except Exception as e:
                self.log(f"✗ 保存失败: {e}")
                messagebox.showerror("错误", f"更新模型失败: {e}", parent=dialog)
                return
            
            # 刷新显示
            self.on_platform_selected()
            dialog.destroy()
        
        # 按钮
        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=4, column=0, columnspan=2, pady=20)
        ttk.Button(button_frame, text="保存", command=do_update, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消", command=dialog.destroy, width=15).pack(side=tk.LEFT, padx=5)
        
        # 配置权重
        dialog.columnconfigure(1, weight=1)
        dialog.rowconfigure(3, weight=1)
        
        # 居中显示
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
    def edit_system_model(self):
        """编辑系统用户 (-1) 的模型选择及用途管理"""
        dialog = tk.Toplevel(self.root)
        dialog.title("系统模型与用途管理")
        dialog.geometry("800x500")
        dialog.transient(self.root)
        dialog.grab_set()

        system_user_id = "-1"
        
        # --- 数据加载 ---
        def load_data():
            try:
                # 1. 重新加载全局配置
                llm_mgr.DEFAULT_PLATFORM_CONFIGS = llm_mgr.load_default_platform_configs()
                # 2. 强制同步默认平台
                self.ai_manager._sync_default_platforms()
                # 3. 获取数据
                _all_models = self.ai_manager.get_platform_models(user_id=system_user_id)
                _usage_list = self.ai_manager.list_user_usage_selections(user_id=system_user_id)
                return _all_models, _usage_list
            except Exception as e:
                messagebox.showerror("错误", f"加载数据失败: {e}", parent=dialog)
                return [], []

        self.all_models, self.usage_list = load_data()
        
        # 整理模型数据
        platforms = sorted(list(set(m['platform_name'] for m in self.all_models)))
        models_by_platform = {p_name: [] for p_name in platforms}
        for model_info in self.all_models:
            models_by_platform[model_info['platform_name']].append((model_info['display_name'], model_info))

        # --- UI 布局 ---
        # 分割面板
        paned = ttk.PanedWindow(dialog, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 左侧：用途列表
        left_frame = ttk.LabelFrame(paned, text="用途列表 (Usage Slots)", padding="5")
        paned.add(left_frame, weight=1)
        
        usage_listbox = tk.Listbox(left_frame, height=15)
        usage_scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=usage_listbox.yview)
        usage_listbox.configure(yscrollcommand=usage_scrollbar.set)
        
        usage_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        usage_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        left_btn_frame = ttk.Frame(left_frame)
        left_btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=5)
        
        # 右侧：配置详情
        right_frame = ttk.LabelFrame(paned, text="绑定模型配置", padding="10")
        paned.add(right_frame, weight=2)

        # 详情控件
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

        # --- 逻辑处理 ---
        current_usage_data = {} # 存储当前选中的 usage 完整数据

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

            # 更新UI
            key_label.config(text=usage['usage_key'])
            label_label.config(text=usage['usage_label'])
            
            # 设置选中项
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
            if not key: return
            
            label = simpledialog.askstring("新建用途", "请输入显示名称 (Label):", parent=dialog, initialvalue=key)
            if not label: label = key

            try:
                # 创建新槽位
                self.ai_manager.create_user_usage_slot(user_id=system_user_id, usage_key=key, usage_label=label)
                # 刷新数据
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
                    # 刷新数据
                    _, self.usage_list = load_data()
                    refresh_list()
                    # 清空右侧
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

            # 查找模型ID
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
                
                # 刷新列表数据（虽然绑定变了但列表显示内容没变，不过为了保险还是刷新下数据）
                _, self.usage_list = load_data()
                
            except Exception as e:
                messagebox.showerror("错误", f"保存失败: {e}", parent=dialog)

        # 按钮布局
        ttk.Button(left_frame, text="+ 新建用途", command=add_usage).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(left_frame, text="- 删除用途", command=delete_usage).pack(side=tk.RIGHT, padx=5, pady=5)

        ttk.Button(right_frame, text="保存绑定配置", command=save_binding).grid(row=5, column=1, sticky=tk.E, pady=20)

        # 初始化
        refresh_list()
        
        # 居中显示对话框
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")

    def _parse_extra_body(self, text):
        raw_text = (text or "").strip()
        if not raw_text:
            return None

        try:
            parsed = json_lib.loads(raw_text)
        except json_lib.JSONDecodeError:
            try:
                parsed = ast.literal_eval(raw_text)
            except (ValueError, SyntaxError) as exc:
                raise ValueError(f"Extra Body 不是有效的 JSON/字面量:\n{exc}") from exc

        if not isinstance(parsed, dict):
            raise ValueError("Extra Body 必须是一个 JSON 对象，例如 {\"enable_thinking\": true}")

        return parsed

    def _save_config_to_file(self):
        """保存配置到文件或数据库（根据当前模式）"""
        if self.data_mode == 'database':
            self._save_to_db()
        else:
            self._save_to_yaml()

    def _save_to_db(self):
        """将当前内存配置持久化到数据库"""
        try:
            # 1. 获取数据库中现有的系统平台
            db_platforms = self.ai_manager.admin_get_sys_platforms()
            db_plat_map = {p['name']: p['platform_id'] for p in db_platforms}
            
            # 2. 遍历内存中的配置
            for p_name, p_cfg in self.current_config.items():
                base_url = p_cfg.get("base_url")
                api_key = p_cfg.get("api_key")
                models = p_cfg.get("models", {})

                if p_name in db_plat_map:
                    # 更新现有平台
                    p_id = db_plat_map[p_name]
                    self.ai_manager.admin_update_sys_platform(p_id, p_name, base_url)
                    if api_key:
                        self.ai_manager.admin_update_sys_platform_api_key(p_id, api_key)
                else:
                    # 添加新平台
                    p_id = self.ai_manager.admin_add_sys_platform(p_name, base_url, api_key)
                    # 更新内存中的 ID
                    p_cfg["_db_id"] = p_id

                # 3. 处理模型同步（删除后重建以保持顺序）
                with self.ai_manager.Session() as session:
                    from .models import LLMPlatform, LLModels
                    plat_obj = session.query(LLMPlatform).filter_by(id=p_id).first()
                    if plat_obj:
                        # 删除旧模型
                        session.query(LLModels).filter_by(platform_id=p_id).delete()
                        # 添加新模型
                        for display_name, m_cfg in models.items():
                            if isinstance(m_cfg, str):
                                m_id = m_cfg
                                is_emb = False
                                extra = None
                            else:
                                m_id = m_cfg.get("model_name")
                                is_emb = bool(m_cfg.get("is_embedding"))
                                extra = json_lib.dumps(m_cfg.get("extra_body")) if m_cfg.get("extra_body") else None
                            
                            new_model = LLModels(
                                platform_id=p_id,
                                display_name=display_name,
                                model_name=m_id,
                                is_embedding=is_emb,
                                extra_body=extra
                            )
                            session.add(new_model)
                        session.commit()

            # 4. 删除数据库中存在但内存中已删除的平台
            for name, p_id in db_plat_map.items():
                if name not in self.current_config:
                    self.ai_manager.admin_delete_sys_platform(p_id)

            self.log("✓ 配置已保存到数据库", tag="success")
        except Exception as e:
            self.log(f"✗ 数据库保存失败: {e}")
            messagebox.showerror("错误", f"数据库保存失败: {e}")

    def _save_to_yaml(self):
        """保存配置到 YAML 文件（加密敏感信息）"""
        config_path = os.path.join(os.path.dirname(__file__), "llm_mgr_cfg.yaml")
        
        # 深拷贝配置，避免修改内存中的明文配置
        import copy
        config_to_save = copy.deepcopy(self.current_config)
        
        # 移除内部标记
        for p_cfg in config_to_save.values():
            if "_db_id" in p_cfg:
                del p_cfg["_db_id"]
        
        # 加密所有 API Key
        sec_mgr = SecurityManager.get_instance()
        
        for platform_name, platform_cfg in config_to_save.items():
            api_key = platform_cfg.get("api_key")
            if api_key:
                # 保留占位符（{ENV_VAR}）原样，不对占位符加密
                if isinstance(api_key, str):
                    if api_key.startswith("ENC:"):
                        continue
                    if api_key.startswith("{") and api_key.endswith("}"):
                        # 直接保留占位符
                        continue
                # 否则进行加密
                try:
                    encrypted_key = sec_mgr.encrypt(api_key)
                    platform_cfg["api_key"] = encrypted_key
                except Exception as e:
                    self.log(f"⚠ 平台 {platform_name} 的 Key 加密失败: {e}")
                    # 询问用户是否保存明文
                    if messagebox.askyesno(
                        "加密失败",
                        f"平台 '{platform_name}' 的 API Key 加密失败。\n\n"
                        "是否以【明文】形式保存？\n"
                        "⚠️ 警告：明文保存可能导致 API Key 泄露，造成财产损失！",
                        icon='warning'
                    ):
                        platform_cfg["api_key"] = api_key
                    else:
                        platform_cfg["api_key"] = None

        try:
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(config_to_save, f, allow_unicode=True, sort_keys=False)
            
            self.log("✓ 配置已保存到文件", tag="success")
        except Exception as e:
            self.log(f"✗ 保存失败: {e}")
            raise

    def test_model(self):
        """测试选中的模型是否可用"""
        platform_name = self.platform_var.get()
        if not platform_name:
            messagebox.showwarning("警告", "请先选择一个平台")
            return

        selection = self.model_listbox.curselection()
        if not selection:
            messagebox.showwarning("警告", "请在左侧选择要测试的模型")
            return

        model_str = self.model_listbox.get(selection[0])
        display_name = self._extract_display_name(model_str)

        models = self.current_config[platform_name].get("models", {})
        model_config = models.get(display_name)
        if not model_config:
            messagebox.showerror("错误", f"未找到模型 '{display_name}' 的配置")
            return

        if isinstance(model_config, str):
            model_id = model_config
            extra_body = None
            is_embedding = False
        else:
            model_id = model_config.get("model_name", "")
            extra_body = model_config.get("extra_body")
            is_embedding = bool(model_config.get("is_embedding"))

        if is_embedding:
            messagebox.showwarning("提示", "当前为 Embedding 模型，请使用『测试Embedding』按钮")
            return

        base_url = self.current_config[platform_name].get("base_url", "").strip()
        api_key = self.api_key_entry.get().strip()

        if not base_url:
            messagebox.showerror("错误", "当前平台缺少 Base URL，无法测试模型")
            return
        if not api_key:
            messagebox.showerror("错误", "请填写 API Key 以进行测试")
            return
        if not model_id:
            messagebox.showerror("错误", "模型配置缺少模型 ID")
            return

        self.log(f"正在测试模型: {display_name} ({model_id})...")

        test_msg = "一句话介绍你自己叫什么，由谁开发，用最少的回复。快速回答，无需推理或思考。"
        
        def do_test():
            try:
                # 使用统一的测试函数
                _test_chat = test_platform_chat if test_platform_chat else llm_mgr.test_platform_chat
                
                result = _test_chat(
                    base_url, api_key, model_id, 
                    extra_body=extra_body, 
                    return_json=True
                )
                self.root.after(0, lambda r=result: self.show_test_result(True, display_name, r))

            except Exception as exc:
                self.root.after(0, lambda err=str(exc): self.show_test_result(False, display_name, err))

        threading.Thread(target=do_test, daemon=True).start()

    def test_embedding(self):
        """测试选中的 Embedding 模型是否可用"""
        platform_name = self.platform_var.get()
        if not platform_name:
            messagebox.showwarning("警告", "请先选择一个平台")
            return

        selection = self.model_listbox.curselection()
        if not selection:
            messagebox.showwarning("警告", "请在左侧选择要测试的模型")
            return

        model_str = self.model_listbox.get(selection[0])
        display_name = self._extract_display_name(model_str)

        models = self.current_config[platform_name].get("models", {})
        model_config = models.get(display_name)
        if not model_config:
            messagebox.showerror("错误", f"未找到模型 '{display_name}' 的配置")
            return

        if isinstance(model_config, str):
            model_id = model_config
            is_embedding = False
        else:
            model_id = model_config.get("model_name", "")
            is_embedding = bool(model_config.get("is_embedding"))

        if not is_embedding:
            messagebox.showwarning("提示", "当前模型不是 Embedding")
            return

        base_url = self.current_config[platform_name].get("base_url", "").strip()
        api_key = self.api_key_entry.get().strip()

        if not base_url:
            messagebox.showerror("错误", "当前平台缺少 Base URL，无法测试 Embedding")
            return
        if not api_key:
            messagebox.showerror("错误", "请填写 API Key 以进行测试")
            return
        if not model_id:
            messagebox.showerror("错误", "模型配置缺少模型 ID")
            return

        self.log(f"正在测试 Embedding: {display_name} ({model_id})...")

        def do_test():
            try:
                # 使用统一的测试函数
                _test_embedding = test_platform_embedding if test_platform_embedding else llm_mgr.test_platform_embedding
                
                result = _test_embedding(base_url, api_key, model_id)
                self.root.after(0, lambda r=result: self.show_embedding_test_result(True, display_name, r))
            except Exception as exc:
                self.root.after(0, lambda err=str(exc): self.show_embedding_test_result(False, display_name, err))

        threading.Thread(target=do_test, daemon=True).start()

    def show_embedding_test_result(self, success, model_name, result):
        """在主线程中显示 Embedding 测试结果"""
        if success:
            dims = None
            if isinstance(result, dict):
                dims = result.get("dims")
            msg = f"Embedding '{model_name}' 可用！"
            if dims:
                msg = f"Embedding '{model_name}' 可用！\n向量维度: {dims}"
            self.log(f"✓ Embedding '{model_name}' 测试成功", tag="success")
            messagebox.showinfo("测试成功", msg)
        else:
            self.log(f"✗ Embedding '{model_name}' 测试失败: {result}")
            messagebox.showerror("测试失败", f"Embedding '{model_name}' 测试失败。\n\n错误详情:\n{result}")

    def speed_test_model(self):
        """流式测速选中的模型"""
        platform_name = self.platform_var.get()
        if not platform_name:
            messagebox.showwarning("警告", "请先选择一个平台")
            return

        selection = self.model_listbox.curselection()
        if not selection:
            messagebox.showwarning("警告", "请在左侧选择要测试的模型")
            return

        model_str = self.model_listbox.get(selection[0])
        display_name = self._extract_display_name(model_str)

        models = self.current_config[platform_name].get("models", {})
        model_config = models.get(display_name)
        if not model_config:
            return

        if isinstance(model_config, str):
            model_id = model_config
            extra_body = None
            is_embedding = False
        else:
            model_id = model_config.get("model_name", "")
            extra_body = model_config.get("extra_body")
            is_embedding = bool(model_config.get("is_embedding"))

        if is_embedding:
            messagebox.showwarning("提示", "Embedding 模型不支持测速")
            return

        base_url = self.current_config[platform_name].get("base_url", "").strip()
        api_key = self.api_key_entry.get().strip()

        if not base_url or not api_key:
            messagebox.showerror("错误", "缺少 URL 或 API Key")
            return

        self.log(f"开始测速模型: {display_name} (预计5秒)...")

        def do_speed_test():
            try:
                # 使用全局导入的 stream_speed_test
                if llm_mgr and hasattr(llm_mgr, 'stream_speed_test'):
                    _stream_speed_test = llm_mgr.stream_speed_test
                else:
                    # 尝试动态导入作为备选
                    try:
                        from llm.llm_mgr.utils import stream_speed_test as _stream_speed_test
                    except ImportError:
                        from .utils import stream_speed_test as _stream_speed_test

                # 传入 extra_body
                generator = _stream_speed_test(base_url, api_key, model_id, extra_body=extra_body)
                for item in generator:
                    if "error" in item:
                        self.root.after(0, lambda m=item["error"]: self.log(f"✗ 测速出错: {m}"))
                        break
                    
                    if item["type"] == "update":
                        msg = f"  进度: {item['elapsed']}s | 速度: {item['speed']:.1f} chars/s"
                        self.root.after(0, lambda m=msg: self.log(m))
                    elif item["type"] == "final":
                        ftl_str = f"{item['ftl']:.0f}ms" if item['ftl'] else "N/A"
                        res = (f"✓ 测速完成: {display_name}\n"
                               f"  平均速度: {item['speed']:.1f} chars/s\n"
                               f"  首次延迟: {ftl_str} (含推理时间)\n"
                               f"  总输出字符: {item['total_chars']}")
                        self.root.after(0, lambda r=res: self.log(r, tag="success"))
                        self.root.after(0, lambda r=res: messagebox.showinfo("测速结果", r))
            except Exception as e:
                self.root.after(0, lambda err=str(e): self.log(f"✗ 测速失败: {err}"))

        threading.Thread(target=do_speed_test, daemon=True).start()

    def show_test_result(self, success, model_name, result):
        """在主线程中显示测试结果"""
        if success:
            content_preview = ""
            if isinstance(result, dict):
                choices = result.get("choices")
                if isinstance(choices, list) and choices:
                    message_block = choices[0].get("message", {})
                    content_preview = message_block.get("content", "") or "[响应体缺少消息内容]"
                log_payload = json_lib.dumps(result, ensure_ascii=False, indent=2)
            else:
                # 兜底，确保可以显示
                log_payload = str(result)
                content_preview = "[未知格式的响应]"

            if len(log_payload) > 800:
                log_payload = log_payload[:800] + "..."

            self.log(f"✓ 模型 '{model_name}' 测试成功!", tag="success")
            self.log(f"  响应: {log_payload}")
            messagebox.showinfo("测试成功", f"模型 '{model_name}' 可用！\n\n响应预览（部分模型可能会输出错误的身份信息，或出现空回复，属正常现象）:\n{content_preview}")
        else:
            self.log(f"✗ 模型 '{model_name}' 测试失败: {result}")
            messagebox.showerror("测试失败", f"模型 '{model_name}' 测试失败。\n\n错误详情:\n{result}")
    
    def set_as_default(self):
        """将选中的平台设为默认（移动到配置文件第一位）"""
        platform_name = self.platform_var.get()
        if not platform_name:
            messagebox.showwarning("警告", "请先选择一个平台")
            return
        
        if not messagebox.askyesno("确认", f"确定要将 '{platform_name}' 设为默认平台吗？\n它将被移动到配置文件的第一位，在用户没有选中模型的时候优先使用。"):
            return

        try:
            # 获取当前配置的键列表
            keys = list(self.current_config.keys())
            
            # 如果已经是第一个，无需操作
            if keys[0] == platform_name:
                self.log(f"✓ '{platform_name}' 已经是默认平台", tag="success")
                return

            # 重新构建字典，将选中的平台移到第一位
            new_config = {}
            new_config[platform_name] = self.current_config[platform_name]
            
            for key in keys:
                if key != platform_name:
                    new_config[key] = self.current_config[key]
            
            # 更新内存中的配置
            self.current_config = new_config
            
            # 保存到文件
            self._save_config_to_file()
            
            # 刷新界面
            self.platform_combo['values'] = list(self.current_config.keys())
            self.platform_var.set(platform_name) # 保持当前选中状态
            self.on_platform_selected()
            
            self.log(f"✓ 已将 '{platform_name}' 设为默认平台", tag="success")
            
        except Exception as e:
            self.log(f"✗ 设置默认平台失败: {e}")
            messagebox.showerror("错误", f"设置默认平台失败: {e}")
    
    def delete_model(self):
        """删除选中的模型"""
        platform_name = self.platform_var.get()
        if not platform_name:
            return
        
        selection = self.model_listbox.curselection()
        if not selection:
            messagebox.showwarning("警告", "请先选择要删除的模型")
            return
        
        model_str = self.model_listbox.get(selection[0])
        display_name = self._extract_display_name(model_str)
        
        if not messagebox.askyesno("确认", f"确定要删除模型 '{display_name}' 吗？"):
            return
        
        # 从内存配置中删除
        if display_name in self.current_config[platform_name].get("models", {}):
            del self.current_config[platform_name]["models"][display_name]
            
            # 立即保存到配置文件
            try:
                self._save_config_to_file()
                self.log(f"✓ 已删除模型: {display_name}", tag="success")
            except Exception as e:
                self.log(f"✗ 保存失败: {e}")
                messagebox.showerror("错误", f"删除模型失败: {e}")
                return
            
            self.on_platform_selected()

    def _check_and_set_llm_key(self):
        """检查并强制设置 LLM_KEY"""
        # 1. 检查环境变量（会自动从 .env 加载）
        if get_env_var("LLM_KEY"):
            return

        # 2. 检查配置文件中是否有加密数据
        has_encrypted_data = False
        encrypted_sample = None
        try:
            config_path = os.path.join(os.path.dirname(__file__), "llm_mgr_cfg.yaml")
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
                    for p_name, p_cfg in cfg.items():
                        api_key = p_cfg.get("api_key")
                        if isinstance(api_key, str) and api_key.startswith("ENC:"):
                            has_encrypted_data = True
                            encrypted_sample = api_key
                            break
        except Exception:
            pass

        # 3. 强制弹窗要求设置
        while True:
            if has_encrypted_data:
                prompt_msg = (
                    "⚠️ 检测到配置文件中包含加密的 API Key\n\n"
                    "请输入您之前用于加密的密钥以解密配置：\n"
                    "(输入新密钥将导致旧的加密数据无法解密，需要重新配置)"
                )
            else:
                prompt_msg = (
                    "⚠️ 未检测到 LLM_KEY\n\n"
                    "请输入一个主密码用于加密存储 API Key：\n"
                    "(此密码将保存到 server/.env 文件)"
                )

            key = simpledialog.askstring(
                "安全设置",
                prompt_msg,
                parent=self.root,
                show='*'
            )
            
            if not key:
                # 用户取消
                if messagebox.askyesno("退出", "必须设置主密码才能安全使用本工具。\n是否退出程序？"):
                    self.root.destroy()
                    import sys
                    sys.exit(0)
                continue

            key = key.strip()
            if not key:
                continue

            # 验证密钥
            sec_mgr = SecurityManager.get_instance()
            
            # 临时设置密钥进行测试（persist=False，先不写入文件）
            sec_mgr.set_key(key, persist=False)
            
            if has_encrypted_data and encrypted_sample:
                decrypted = sec_mgr.decrypt(encrypted_sample)
                # 如果解密失败，SecurityManager.decrypt 通常返回原文(ENC:...)
                if decrypted.startswith("ENC:"):
                    if messagebox.askyesno(
                        "解密失败",
                        "无法使用该密钥解密现有的 API Key。\n\n"
                        "是否强制使用新密钥？\n"
                        "(选择'是'将覆盖密钥，您需要重新录入所有 API Key)\n"
                        "(选择'否'请重新输入密钥)"
                    ):
                        # 用户选择覆盖，跳出循环
                        pass
                    else:
                        # 用户选择重试
                        continue
            
            # 保存并应用（写入 .env 文件）
            self._persist_llm_key(key)
            self.log("✓ 已设置主密码并应用", tag="success")
            break

    def _persist_llm_key(self, key_value):
        """持久化 LLM_KEY 到 .env 文件"""
        # 使用 env_utils 写入 .env 文件
        if set_env_var("LLM_KEY", key_value):
            self.log("✓ 主密码已保存到 server/.env 文件", tag="success")
        else:
            messagebox.showerror("保存失败", "写入 .env 文件失败，请检查文件权限")


def main():
    """主函数：启动 GUI"""
    root = tk.Tk()
    app = LLMConfigGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
