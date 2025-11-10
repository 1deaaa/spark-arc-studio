"""
LLM 配置管理器 - 图形化界面
用于管理系统平台配置（llm_mgr_cfg.yaml）
支持平台和模型的添加、编辑、删除操作
"""
import os
import ast
import yaml
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import json as json_lib
from llm_mgr import substitute_env_vars, probe_platform_models, load_default_platform_configs


class LLMConfigGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("LLM 配置管理器")
        self.root.geometry("1200x800")
        
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
        
        ttk.Label(right_frame, text="环境变量名:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.env_var_entry = ttk.Entry(right_frame, width=40)
        self.env_var_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        
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
        self.load_config()
    
    def log(self, message):
        """添加日志"""
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
    
    def load_config(self):
        """加载配置文件"""
        try:
            self.current_config = load_default_platform_configs()
            self.platform_combo['values'] = list(self.current_config.keys())
            if self.current_config:
                self.platform_var.set(list(self.current_config.keys())[0])
                self.on_platform_selected()
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
        
        # 处理 api_key 和环境变量名
        self.api_key_entry.delete(0, tk.END)
        self.env_var_entry.delete(0, tk.END)
        
        api_key_raw = platform_cfg.get("api_key", "")
        if api_key_raw:
            # 检查是否为环境变量占位符格式 {ENV_VAR_NAME}
            if api_key_raw.startswith("{") and api_key_raw.endswith("}"):
                env_var_name = api_key_raw[1:-1]  # 提取变量名
                self.env_var_entry.insert(0, env_var_name)
                # 尝试从环境变量读取实际值
                actual_value = os.environ.get(env_var_name, "")
                if actual_value:
                    self.api_key_entry.insert(0, actual_value)  # 显示实际值
                    self.log(f"✓ 已从环境变量 {env_var_name} 加载 API Key")
                else:
                    self.api_key_entry.insert(0, "")  # 空白，等待用户输入
                    self.log(f"⚠ 环境变量 {env_var_name} 未设置，请在下方输入自定义 Key")
            else:
                # 明文 API Key - 尝试反向查找是否存在于环境变量中
                self.api_key_entry.insert(0, api_key_raw)
                
                # 反向查找：检查是否有环境变量的值与这个 key 匹配
                found_env_var = None
                for env_name, env_value in os.environ.items():
                    if env_value == api_key_raw:
                        # 找到匹配的环境变量，优先选择包含常见关键词的
                        if any(keyword in env_name.upper() for keyword in ['API', 'KEY', 'TOKEN', 'SECRET']):
                            found_env_var = env_name
                            break
                        elif found_env_var is None:
                            found_env_var = env_name
                
                if found_env_var:
                    self.env_var_entry.insert(0, found_env_var)
                    self.log(f"✓ 已加载 API Key (检测到环境变量: {found_env_var})")
                else:
                    self.log(f"✓ 已加载用户自定义 API Key (明文)")
        
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
        
        # 环境变量名 (可选)
        ttk.Label(dialog, text="环境变量名 (可选):").grid(row=3, column=0, sticky=tk.W, padx=10, pady=10)
        env_entry = ttk.Entry(dialog, width=40)
        env_entry.grid(row=3, column=1, padx=10, pady=10)
        
        def do_add():
            name = name_entry.get().strip()
            url = url_entry.get().strip()
            key = key_entry.get().strip()
            env_var = env_entry.get().strip()
            
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
                if env_var:
                    # 使用环境变量格式
                    new_platform["api_key"] = f"{{{env_var}}}"
                    if key:
                        # 同时保存到环境变量
                        os.environ[env_var] = key
                        self.log(f"✓ 已设置环境变量: {env_var}")
                elif key:
                    # 直接保存明文
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
        """保存 API Key 到配置文件（环境变量格式）"""
        platform_name = self.platform_var.get()
        if not platform_name:
            messagebox.showwarning("警告", "请先选择一个平台")
            return
        
        env_var_name = self.env_var_entry.get().strip()
        api_key = self.api_key_entry.get().strip()
        
        if not api_key:
            messagebox.showerror("错误", "请填写 API Key")
            return
        
        # 环境变量名是可选的（不填则直接保存明文）
        # 如果填了环境变量名，需要验证格式
        if env_var_name:
            import re
            if not re.match(r'^[A-Z0-9_]+$', env_var_name):
                messagebox.showerror("错误", "环境变量名只能包含大写字母、数字和下划线\n例如: OPENAI_API_KEY")
                return
        
        try:
            # 策略：如果提供了环境变量名，使用环境变量；否则直接保存明文
            if env_var_name:
                # 1. 设置到当前进程的环境变量（立即生效）
                os.environ[env_var_name] = api_key
                
                # 2. 保存到配置文件（环境变量占位符格式）
                self.current_config[platform_name]["api_key"] = f"{{{env_var_name}}}"
                
                # 3. 尝试保存到系统环境变量（Windows）
                if os.name == 'nt':  # Windows
                    import winreg
                    try:
                        # 打开用户环境变量注册表项
                        key = winreg.OpenKey(
                            winreg.HKEY_CURRENT_USER, 
                            r'Environment', 
                            0, 
                            winreg.KEY_SET_VALUE
                        )
                        winreg.SetValueEx(key, env_var_name, 0, winreg.REG_SZ, api_key)
                        winreg.CloseKey(key)
                        
                        # 通知系统环境变量已更改
                        import ctypes
                        HWND_BROADCAST = 0xFFFF
                        WM_SETTINGCHANGE = 0x1A
                        SMTO_ABORTIFHUNG = 0x0002
                        result = ctypes.c_long()
                        ctypes.windll.user32.SendMessageTimeoutW(
                            HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment", 
                            SMTO_ABORTIFHUNG, 5000, ctypes.byref(result)
                        )
                        
                        self.log(f"✓ API Key 已保存到系统环境变量: {env_var_name}")
                    except Exception as e:
                        self.log(f"⚠ 保存到系统环境变量失败: {e}")
                        self.log(f"✓ 但已保存到当前会话和配置文件")
                else:
                    # Linux/Mac - 提示用户手动添加
                    self.log(f"⚠ 请手动添加到 ~/.bashrc 或 ~/.zshrc:")
                    self.log(f"   export {env_var_name}='{api_key}'")
                
                save_msg = f"API Key 已保存！\n\n环境变量: {env_var_name}\n配置文件: {{{env_var_name}}}"
            else:
                # 没有环境变量名，直接保存明文到配置文件
                self.current_config[platform_name]["api_key"] = api_key
                save_msg = f"API Key 已保存！\n\n保存方式: 明文\n⚠️ 建议填写环境变量名以提高安全性"
            
            # 立即写入配置文件
            self._save_config_to_file()
            
            # 刷新显示
            self.on_platform_selected()
            
            messagebox.showinfo("成功", save_msg)
            
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
        display_name_entry.config(state='readonly')  # 不允许修改显示名称
        
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
            new_model_id = model_id_entry.get().strip()
            
            if not new_model_id:
                messagebox.showwarning("警告", "请填写模型ID", parent=dialog)
                return
            
            # 解析 extra_body
            extra_body_str = extra_body_text.get("1.0", tk.END)
            try:
                extra_body = self._parse_extra_body(extra_body_str)
            except ValueError as err:
                messagebox.showerror("错误", str(err), parent=dialog)
                return
            
            # 更新配置
            if extra_body:
                self.current_config[platform_name]["models"][display_name] = {
                    "model_name": new_model_id,
                    "extra_body": extra_body
                }
            else:
                self.current_config[platform_name]["models"][display_name] = new_model_id
            
            # 立即保存到配置文件
            try:
                self._save_config_to_file()
                self.log(f"✓ 已更新模型: {display_name}")
                messagebox.showinfo("成功", f"模型 '{display_name}' 已更新", parent=dialog)
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
        """内部方法：将配置保存到文件"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), "llm_mgr_cfg.yaml")
            
            # 准备保存的配置（保留环境变量占位符格式）
            save_config = {}
            for name, cfg in self.current_config.items():
                save_cfg = dict(cfg)
                save_config[name] = save_cfg
            
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(save_config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            
            self.log(f"✓ 配置已保存到: {config_path}")
            
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
            messagebox.showinfo("测试成功", f"模型 '{model_name}' 可用！\n\n响应预览（部分模型可能会输出错误的身份信息，属正常现象）:\n{content_preview}")
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


def main():
    """主函数：启动 GUI"""
    root = tk.Tk()
    app = LLMConfigGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
