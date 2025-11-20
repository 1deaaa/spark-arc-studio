"""
LLM 配置管理器 - 图形化界面
用于管理系统平台配置（llm_mgr_cfg.yaml）
支持平台和模型的添加、编辑、删除操作
"""
import os
import ast
import yaml
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
import threading
import json as json_lib
# 调整导入路径以支持直接运行和作为模块导入
try:
    from . import llm_mgr
    from .llm_mgr import probe_platform_models, AIManager
except ImportError:
    import llm_mgr
    from llm_mgr import probe_platform_models, AIManager


class LLMConfigGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("LLM 配置管理器")
        self.root.geometry("1200x800")
        
        # 检查并强制设置 LLM_KEY
        self._check_and_set_llm_key()
        
        # 初始化 AIManager
        # 确保数据库路径正确（相对于 server 根目录）
        self.ai_manager = AIManager()
        
        # 创建主框架
        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        
        # 左侧：平台列表
        left_frame = ttk.LabelFrame(main_frame, text="系统平台配置", padding="5")
        left_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        # 平台选择和管理
        platform_header_frame = ttk.Frame(left_frame)
        platform_header_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(platform_header_frame, text="选择平台:").pack(side=tk.LEFT, padx=5)
        self.platform_var = tk.StringVar()
        self.platform_combo = ttk.Combobox(platform_header_frame, textvariable=self.platform_var, state='readonly', width=25)
        self.platform_combo.pack(side=tk.LEFT, padx=5)
        self.platform_combo.bind('<<ComboboxSelected>>', self.on_platform_selected)
        
        # 平台管理按钮
        # 平台管理按钮
        ttk.Button(platform_header_frame, text="设为默认", command=self.set_as_default).pack(side=tk.LEFT, padx=2)
        ttk.Button(platform_header_frame, text="添加平台", command=self.add_platform).pack(side=tk.LEFT, padx=2)
        ttk.Button(platform_header_frame, text="删除平台", command=self.delete_platform).pack(side=tk.LEFT, padx=2)
        ttk.Button(platform_header_frame, text="编辑系统模型", command=self.edit_system_model).pack(side=tk.LEFT, padx=2)
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
        
        # 模型操作按钮
        model_btn_frame = ttk.Frame(left_frame)
        model_btn_frame.grid(row=2, column=1, sticky=tk.E, pady=5, padx=5)
        ttk.Button(model_btn_frame, text="测试选中模型", command=self.test_model).pack(side=tk.LEFT, padx=2)
        ttk.Button(model_btn_frame, text="编辑选中模型", command=self.edit_model).pack(side=tk.LEFT, padx=2)
        ttk.Button(model_btn_frame, text="删除选中模型", command=self.delete_model).pack(side=tk.LEFT, padx=2)
        
        # 平台 URL 编辑
        ttk.Label(left_frame, text="平台 URL:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.platform_url_entry = ttk.Entry(left_frame, width=40)
        self.platform_url_entry.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        ttk.Button(left_frame, text="保存平台 URL", command=self.save_platform_url).grid(row=4, column=1, sticky=tk.E, pady=5, padx=5)
        
        # 右侧：探测模型
        right_frame = ttk.LabelFrame(main_frame, text="模型探测", padding="5")
        right_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
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
        self.probe_models_cache = []  # 缓存完整的探测结果
        self._current_platform_original_api_key = None  # 记录原始 api_key 配置（含占位符）
        self.load_config()
    
    def log(self, message):
        """添加日志"""
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

            self.log("✓ 配置加载成功")
        except Exception as e:
            messagebox.showerror("错误", f"加载配置失败: {e}")
            self.log(f"✗ 加载配置失败: {e}")
    
    def reload_config(self):
        """重新加载配置"""
        try:
            self.load_config()
            messagebox.showinfo("成功", "配置已重新加载")
        except Exception as e:
            messagebox.showerror("错误", f"重新加载失败: {e}")
    
    def on_platform_selected(self, event=None):
        """平台选择变化时更新模型列表"""
        platform_name = self.platform_var.get()
        if not platform_name or platform_name not in self.current_config:
            return
        
        platform_cfg = self.current_config[platform_name]
        self.model_listbox.delete(0, tk.END)
        
        # 立即清空探测结果列表和缓存
        self.probe_listbox.delete(0, tk.END)
        self.probe_models_cache = []
        
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
                from .llm_mgr import SecurityManager
            except ImportError:
                from llm_mgr import SecurityManager
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
            if isinstance(model_config, str):
                model_id = model_config
            else:
                model_id = model_config.get("model_name", "")
            self.model_listbox.insert(tk.END, f"{display_name} → {model_id}")

        # 异步执行一次模型探测
        self.probe_models(auto_start=True)
    
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
                
                self.log(f"✓ 已添加新平台: {name}")
                dialog.destroy()
                messagebox.showinfo("成功", f"平台 '{name}' 已添加")
                
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
        if not platform_name:
            messagebox.showwarning("警告", "请先选择一个平台")
            return
        
        if not messagebox.askyesno("确认", f"确定要删除平台 '{platform_name}' 及其所有模型吗？\n此操作不可恢复！"):
            return
        
        try:
            # 从配置中删除
            del self.current_config[platform_name]
            
            # 保存到文件
            self._save_config_to_file()
            
            # 刷新界面
            self.platform_combo['values'] = list(self.current_config.keys())
            if self.current_config:
                self.platform_var.set(list(self.current_config.keys())[0])
                self.on_platform_selected()
            else:
                self.platform_var.set("")
                self.model_listbox.delete(0, tk.END)
            
            self.log(f"✓ 已删除平台: {platform_name}")
            messagebox.showinfo("成功", f"平台 '{platform_name}' 已删除")
            
        except Exception as e:
            self.log(f"✗ 删除平台失败: {e}")
            messagebox.showerror("错误", f"删除平台失败: {e}")
    
    def save_platform_url(self):
        """保存平台的 base_url"""
        platform_name = self.platform_var.get()
        if not platform_name:
            messagebox.showwarning("警告", "请先选择一个平台")
            return
        
        new_url = self.platform_url_entry.get().strip()
        if not new_url:
            messagebox.showerror("错误", "请填写平台 URL")
            return
        
        # 验证 URL 格式
        if not (new_url.startswith("http://") or new_url.startswith("https://")):
            messagebox.showerror("错误", "URL 必须以 http:// 或 https:// 开头")
            return
        
        try:
            # 更新配置
            self.current_config[platform_name]["base_url"] = new_url
            
            # 立即保存到配置文件
            self._save_config_to_file()
            
            # 刷新显示
            self.on_platform_selected()
            
            self.log(f"✓ 已更新平台 '{platform_name}' 的 URL: {new_url}")
            messagebox.showinfo("成功", f"平台 URL 已更新")
            
        except Exception as e:
            self.log(f"✗ 保存失败: {e}")
            messagebox.showerror("错误", f"保存平台 URL 失败: {e}")
    
    def save_api_key(self):
        """保存 API Key 到配置文件（加密存储）"""
        platform_name = self.platform_var.get()
        if not platform_name:
            messagebox.showwarning("警告", "请先选择一个平台")
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

            self.log(f"✓ 平台 '{platform_name}' 的 API Key 已更新（加密存储）")

            messagebox.showinfo(
                "成功",
                f"API Key 已加密保存！",
            )

        except Exception as e:
            self.log(f"✗ 保存失败: {e}")
            messagebox.showerror("错误", f"保存 API Key 失败: {e}")
    
    def probe_models(self, auto_start=False):
        """探测平台可用模型"""
        base_url = self.base_url_entry.get().strip()
        api_key = self.api_key_entry.get().strip()
        
        if not base_url:
            if not auto_start: # 只有用户手动点击时才警告
                messagebox.showwarning("警告", "请先选择平台（Base URL 将自动填充）")
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
            messagebox.showinfo("结果", "未探测到任何模型")
            return
        
        # 缓存完整结果
        self.probe_models_cache = [model.get('id', '') for model in models]
        
        # 显示所有模型
        self.probe_listbox.delete(0, tk.END)
        for model_id in self.probe_models_cache:
            self.probe_listbox.insert(tk.END, model_id)
        
        self.log(f"✓ 探测到 {len(models)} 个模型")
    
    def show_probe_error(self, error_msg):
        """显示探测错误"""
        self.log(f"✗ 探测失败: {error_msg}")
        messagebox.showerror("探测失败", error_msg)
    
    def on_filter_change(self, event=None):
        """筛选关键字变化时更新列表"""
        keyword = self.filter_entry.get().strip().lower()
        
        self.probe_listbox.delete(0, tk.END)
        
        if not keyword:
            # 没有关键字，显示所有
            for model_id in self.probe_models_cache:
                self.probe_listbox.insert(tk.END, model_id)
        else:
            # 筛选匹配的模型
            filtered = [m for m in self.probe_models_cache if keyword in m.lower()]
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
        
        # Extra Body
        ttk.Label(dialog, text="Extra Body (JSON):").grid(row=2, column=0, sticky=(tk.W, tk.N), padx=10, pady=10)
        
        extra_body_frame = ttk.Frame(dialog)
        extra_body_frame.grid(row=2, column=1, padx=10, pady=10, sticky=(tk.W, tk.E, tk.N, tk.S))
        
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
            
            # 根据是否有 extra_body 选择存储格式
            if extra_body:
                self.current_config[platform_name]["models"][display_name] = {
                    "model_name": model_id,
                    "extra_body": extra_body
                }
            else:
                self.current_config[platform_name]["models"][display_name] = model_id
            
            # 立即保存到配置文件
            try:
                self._save_config_to_file()
                self.log(f"✓ 已添加模型: {display_name} → {model_id}")
                messagebox.showinfo("成功", f"模型 '{display_name}' 已添加", parent=dialog)
            except Exception as e:
                self.log(f"✗ 保存失败: {e}")
                messagebox.showerror("错误", f"添加模型失败: {e}", parent=dialog)
                return
            
            # 刷新显示
            self.on_platform_selected()
            dialog.destroy()
        
        # 按钮
        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=3, column=0, columnspan=2, pady=20)
        ttk.Button(button_frame, text="添加", command=do_add, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消", command=dialog.destroy, width=15).pack(side=tk.LEFT, padx=5)
        
        # 配置权重
        dialog.columnconfigure(1, weight=1)
        dialog.rowconfigure(2, weight=1)
        
        # 居中显示
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
    
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
        display_name = model_str.split(" → ")[0]
        
        models = self.current_config[platform_name].get("models", {})
        model_config = models.get(display_name)
        
        if not model_config:
            return
        
        # 解析模型配置
        if isinstance(model_config, str):
            model_id = model_config
            extra_body_dict = None
        else:
            model_id = model_config.get("model_name", "")
            extra_body_dict = model_config.get("extra_body")
        
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
        # 允许编辑显示名称
        
        # 模型ID
        ttk.Label(dialog, text="模型ID:").grid(row=1, column=0, sticky=tk.W, padx=10, pady=10)
        model_id_entry = ttk.Entry(dialog, width=50)
        model_id_entry.grid(row=1, column=1, padx=10, pady=10, sticky=(tk.W, tk.E))
        model_id_entry.insert(0, model_id)
        
        # Extra Body
        ttk.Label(dialog, text="Extra Body (JSON):").grid(row=2, column=0, sticky=(tk.W, tk.N), padx=10, pady=10)
        
        extra_body_frame = ttk.Frame(dialog)
        extra_body_frame.grid(row=2, column=1, padx=10, pady=10, sticky=(tk.W, tk.E, tk.N, tk.S))
        
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
            
            # 如果显示名称被修改，检查是否与其他模型冲突
            if new_display_name != display_name:
                if new_display_name in self.current_config[platform_name].get("models", {}):
                    messagebox.showerror("错误", f"显示名称 '{new_display_name}' 已存在，请使用其他名称", parent=dialog)
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
            if extra_body:
                self.current_config[platform_name]["models"][new_display_name] = {
                    "model_name": new_model_id,
                    "extra_body": extra_body
                }
            else:
                self.current_config[platform_name]["models"][new_display_name] = new_model_id
            
            # 立即保存到配置文件
            try:
                self._save_config_to_file()
                if new_display_name != display_name:
                    self.log(f"✓ 已更新模型: {display_name} → {new_display_name}")
                else:
                    self.log(f"✓ 已更新模型: {new_display_name}")
                messagebox.showinfo("成功", f"模型已更新", parent=dialog)
            except Exception as e:
                self.log(f"✗ 保存失败: {e}")
                messagebox.showerror("错误", f"更新模型失败: {e}", parent=dialog)
                return
            
            # 刷新显示
            self.on_platform_selected()
            dialog.destroy()
        
        # 按钮
        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=3, column=0, columnspan=2, pady=20)
        ttk.Button(button_frame, text="保存", command=do_update, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消", command=dialog.destroy, width=15).pack(side=tk.LEFT, padx=5)
        
        # 配置权重
        dialog.columnconfigure(1, weight=1)
        dialog.rowconfigure(2, weight=1)
        
        # 居中显示
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
    def edit_system_model(self):
        """编辑系统用户 (-1) 的模型选择"""
        dialog = tk.Toplevel(self.root)
        dialog.title("编辑系统默认模型")
        dialog.geometry("500x250")
        dialog.transient(self.root)
        dialog.grab_set()

        # 获取数据
        system_user_id = "-1"
        try:
            # 1. 重新加载全局配置（因为 YAML 可能已被 GUI 修改）
            llm_mgr.DEFAULT_PLATFORM_CONFIGS = llm_mgr.load_default_platform_configs()
            
            # 2. 强制同步默认平台，确保数据库与 YAML 一致
            self.ai_manager._sync_default_platforms()
            
            # 3. 获取数据
            all_models = self.ai_manager.get_platform_models(user_id=system_user_id)
            current_selection = self.ai_manager.get_user_selection_detail(user_id=system_user_id)
        except Exception as e:
            messagebox.showerror("错误", f"加载模型数据失败: {e}", parent=dialog)
            dialog.destroy()
            return

        platforms = sorted(list(set(m['platform_name'] for m in all_models)))

        # --- UI ---
        frame = ttk.Frame(dialog, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="平台:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        platform_var = tk.StringVar()
        platform_combo = ttk.Combobox(frame, textvariable=platform_var, values=platforms, state='readonly')
        platform_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)

        ttk.Label(frame, text="模型:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        model_var = tk.StringVar()
        model_combo = ttk.Combobox(frame, textvariable=model_var, state='readonly')
        model_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)

        # --- Logic ---
        models_by_platform = {p_name: [] for p_name in platforms}
        for model_info in all_models:
            models_by_platform[model_info['platform_name']].append((model_info['display_name'], model_info))

        def on_platform_change(event=None):
            selected_platform = platform_var.get()
            model_display_names = [m[0] for m in models_by_platform.get(selected_platform, [])]
            model_combo['values'] = model_display_names
            # 如果当前选择的模型不在新平台下，则清空模型选择
            if model_var.get() not in model_display_names:
                model_var.set(model_display_names[0] if model_display_names else "")

        platform_combo.bind('<<ComboboxSelected>>', on_platform_change)

        # 初始化选择
        # 如果有当前选择，则使用它
        # 注意：get_user_selection_detail 返回的键是 'platform' 和 'model_display_name'
        sel_platform = current_selection.get('platform') if current_selection else None
        sel_model = current_selection.get('model_display_name') if current_selection else None

        if sel_platform and sel_platform in platforms:
            platform_var.set(sel_platform)
            on_platform_change()
            
            if sel_model and sel_model in model_combo['values']:
                model_var.set(sel_model)
            else:
                # 如果平台匹配但模型不匹配，清空模型选择
                model_var.set("")
        else:
            # 如果没有有效的当前选择，则不进行任何默认选中
            self.log(f"⚠ 未找到有效的系统默认模型配置，请手动选择。")
            platform_var.set("")
            model_var.set("")
            model_combo['values'] = []

        def do_save():
            selected_platform_name = platform_var.get()
            selected_model_display_name = model_var.get()

            if not selected_platform_name or not selected_model_display_name:
                messagebox.showerror("错误", "请选择平台和模型", parent=dialog)
                return

            model_info = next((m[1] for m in models_by_platform[selected_platform_name] if m[0] == selected_model_display_name), None)

            if model_info:
                self.ai_manager.save_user_selection(user_id=system_user_id, platform_id=model_info['platform_id'], model_id=model_info['model_id'])
                self.log(f"✓ 已更新系统用户模型为: {selected_platform_name} / {selected_model_display_name}")
                messagebox.showinfo("成功", "系统默认模型已更新", parent=dialog)
                dialog.destroy()
            else:
                messagebox.showerror("错误", "找不到所选模型的详细信息", parent=dialog)

        ttk.Button(frame, text="保存", command=do_save).grid(row=2, column=1, sticky=tk.E, pady=20, padx=5)
        ttk.Button(frame, text="取消", command=dialog.destroy).grid(row=2, column=1, sticky=tk.W, pady=20, padx=5)

        # 居中显示对话框
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        ttk.Button(frame, text="取消", command=dialog.destroy).grid(row=2, column=1, sticky=tk.W, pady=20, padx=5)

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
        """保存配置到文件（加密敏感信息）"""
        config_path = os.path.join(os.path.dirname(__file__), "llm_mgr_cfg.yaml")
        
        # 深拷贝配置，避免修改内存中的明文配置
        import copy
        config_to_save = copy.deepcopy(self.current_config)
        
        # 加密所有 API Key
        try:
            from .llm_mgr import SecurityManager
        except ImportError:
            from llm_mgr import SecurityManager
        sec_mgr = SecurityManager.get_instance()
        
        for platform_name, platform_cfg in config_to_save.items():
            api_key = platform_cfg.get("api_key")
            if api_key:
                # 如果已经是加密格式（可能来自未解密的加载），保持不变
                if isinstance(api_key, str) and api_key.startswith("ENC:"):
                    continue
                # 否则进行加密
                try:
                    encrypted_key = sec_mgr.encrypt(api_key)
                    platform_cfg["api_key"] = encrypted_key
                except Exception as e:
                    self.log(f"⚠ 平台 {platform_name} 的 Key 加密失败: {e}")
                    # 加密失败时，为了安全，不要保存明文？或者保存明文但警告？
                    # 这里选择不保存该 Key 或者报错
                    # raise ValueError(f"加密失败: {e}")
                    # 暂时保留原值（明文），但记录错误
                    pass

        try:
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(config_to_save, f, allow_unicode=True, sort_keys=False)
            
            self.log("✓ 配置已保存到文件")
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
        display_name = model_str.split(" → ")[0]

        models = self.current_config[platform_name].get("models", {})
        model_config = models.get(display_name)
        if not model_config:
            messagebox.showerror("错误", f"未找到模型 '{display_name}' 的配置")
            return

        if isinstance(model_config, str):
            model_id = model_config
            extra_body = None
        else:
            model_id = model_config.get("model_name", "")
            extra_body = model_config.get("extra_body")

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

        payload = {
            "model": model_id,
            "messages": [{"role": "user", "content": "一句话介绍你自己叫什么，由谁开发，用最少的回复。快速回答，无需推理或思考。"}],
            "max_tokens": 16
        }
        if isinstance(extra_body, dict):
            # 不修改原配置，复制后再合并
            payload.update(extra_body)

        url = base_url.rstrip("/")
        if url.endswith("/v1"):
            url = f"{url}/chat/completions"
        elif url.endswith("/v1/"):
            url = f"{url}chat/completions"
        else:
            url = f"{url}/v1/chat/completions"

        def do_test():
            try:
                import requests

                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }

                resp = requests.post(url, headers=headers, json=payload, timeout=30)

                if resp.ok:
                    result = resp.json()
                    self.root.after(0, lambda r=result: self.show_test_result(True, display_name, r))
                else:
                    error_detail = f"HTTP {resp.status_code}: {resp.text[:200]}"
                    self.root.after(0, lambda err=error_detail: self.show_test_result(False, display_name, err))

            except Exception as exc:
                self.root.after(0, lambda err=str(exc): self.show_test_result(False, display_name, err))

        threading.Thread(target=do_test, daemon=True).start()

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

            self.log(f"✓ 模型 '{model_name}' 测试成功!")
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
                self.log(f"✓ '{platform_name}' 已经是默认平台")
                messagebox.showinfo("提示", f"'{platform_name}' 已经是默认平台。")
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
            
            self.log(f"✓ 已将 '{platform_name}' 设为默认平台")
            messagebox.showinfo("成功", f"已将 '{platform_name}' 设为默认平台。")
            
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
        display_name = model_str.split(" → ")[0]
        
        if not messagebox.askyesno("确认", f"确定要删除模型 '{display_name}' 吗？"):
            return
        
        # 从内存配置中删除
        if display_name in self.current_config[platform_name].get("models", {}):
            del self.current_config[platform_name]["models"][display_name]
            
            # 立即保存到配置文件
            try:
                self._save_config_to_file()
                self.log(f"✓ 已删除模型: {display_name}")
            except Exception as e:
                self.log(f"✗ 保存失败: {e}")
                messagebox.showerror("错误", f"删除模型失败: {e}")
                return
            
            self.on_platform_selected()

    def _check_and_set_llm_key(self):
        """检查并强制设置 LLM_KEY"""
        # 1. 检查当前进程环境变量
        if os.environ.get("LLM_KEY"):
            return

        # 2. 尝试从注册表读取（防止当前进程未继承但注册表已有）
        reg_key = self._get_env_from_registry("LLM_KEY")
        if reg_key:
            os.environ["LLM_KEY"] = reg_key
            try:
                from .llm_mgr import SecurityManager
            except ImportError:
                from llm_mgr import SecurityManager
            SecurityManager.get_instance().set_key(reg_key)
            return

        # 3. 检查配置文件中是否有加密数据
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

        # 4. 强制弹窗要求设置
        while True:
            if has_encrypted_data:
                prompt_msg = (
                    "⚠️ 检测到配置文件中包含加密的 API Key\n\n"
                    "请输入您之前用于加密的密钥以解密配置：\n"
                    "(输入新密钥将导致旧的加密数据无法解密，需要重新配置)"
                )
            else:
                prompt_msg = (
                    "⚠️ 未检测到 LLM_KEY 环境变量\n\n"
                    "请输入一个主密码用于加密存储 API Key：\n"
                    "(此密码将保存到用户环境变量)"
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
            try:
                from .llm_mgr import SecurityManager
            except ImportError:
                from llm_mgr import SecurityManager
            sec_mgr = SecurityManager.get_instance()
            
            # 临时设置密钥进行测试
            sec_mgr.set_key(key)
            
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
            
            # 保存并应用
            self._persist_llm_key(key)
            break
    
    def _get_env_from_registry(self, name):
        if os.name != 'nt': return None
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
                return winreg.QueryValueEx(key, name)[0]
        except:
            return None

    def _persist_llm_key(self, key_value):
        # 1. 设置当前进程
        os.environ["LLM_KEY"] = key_value
        
        # 2. 写入注册表（Windows 永久生效）
        if os.name == 'nt':
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_SET_VALUE) as reg_key:
                    winreg.SetValueEx(reg_key, "LLM_KEY", 0, winreg.REG_SZ, key_value)
                
                # 3. 广播消息（尝试刷新 cmd）
                import ctypes
                HWND_BROADCAST = 0xFFFF
                WM_SETTINGCHANGE = 0x1A
                SMTO_ABORTIFHUNG = 0x0002
                result = ctypes.c_long()
                ctypes.windll.user32.SendMessageTimeoutW(
                    HWND_BROADCAST,
                    WM_SETTINGCHANGE,
                    0,
                    "Environment",
                    SMTO_ABORTIFHUNG,
                    5000,
                    ctypes.byref(result),
                )
                messagebox.showinfo("设置成功", "主密码已保存到用户环境变量。\n\n注意：已打开的终端窗口可能需要重启才能生效。")
            except Exception as e:
                messagebox.showerror("保存失败", f"写入注册表失败: {e}")
        else:
            # Linux/Mac 提示
            messagebox.showinfo("提示", f"请手动设置环境变量 LLM_KEY='{key_value}' 以持久化。\n\n设置完成后，请重启终端以生效。")


def main():
    """主函数：启动 GUI"""
    root = tk.Tk()
    app = LLMConfigGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
