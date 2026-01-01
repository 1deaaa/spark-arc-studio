"""
安全管理模块
负责 API Key 的加密/解密和密钥管理
"""

import os
import base64
import hashlib
from typing import Optional
from cryptography.fernet import Fernet


class SecurityManager:
    """安全管理器：负责 API Key 的加密/解密"""
    _instance = None
    _fernet = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        if SecurityManager._instance is not None:
             # 防止重复初始化，虽然单例模式主要靠 get_instance 保证
            pass

        key = os.environ.get("LLM_KEY")
        
        # 兜底策略: (Windows) 尝试读取注册表
        if not key and os.name == 'nt':
            key = self.get_win_registry_key()

        if not key:
            if os.name != 'nt':
                print("⚠️ 警告: 未设置环境变量 LLM_KEY。如果您刚刚设置了环境变量，请尝试重启终端。")
            else:
                print("⚠️ 警告: 未设置环境变量 LLM_KEY，将无法解密配置文件中的敏感信息。")
            self._fernet = None
        else:
            if "LLM_KEY" not in os.environ:
                os.environ["LLM_KEY"] = key

            digest = hashlib.sha256(key.encode()).digest()
            fernet_key = base64.urlsafe_b64encode(digest)
            try:
                self._fernet = Fernet(fernet_key)
            except Exception as e:
                print(f"❌ 初始化加密组件失败: {e}")
                self._fernet = None

    @staticmethod
    def get_win_registry_key() -> Optional[str]:
        """从 Windows 注册表读取 LLM_KEY"""
        if os.name != 'nt':
            return None
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as reg_key:
                reg_val, _ = winreg.QueryValueEx(reg_key, "LLM_KEY")
                return str(reg_val) if reg_val else None
        except Exception:
            return None
            
    def encrypt(self, text: str) -> str:
        if not text: return text
        if not self._fernet:
            raise ValueError("未设置 LLM_KEY，无法执行加密操作")
        try:
            return "ENC:" + self._fernet.encrypt(text.encode()).decode()
        except Exception as e:
            print(f"❌ 加密失败: {e}")
            return text
        
    def decrypt(self, text: str) -> str:
        if not text or not isinstance(text, str): return text
        if not text.startswith("ENC:"): return text
        
        if not self._fernet:
            print("⚠️ 警告: 遇到加密数据但未设置 LLM_KEY，无法解密")
            return text 
            
        try:
            ciphertext = text[4:]
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except Exception as e:
            print(f"❌ 解密失败: {e}")
            return text

    def set_key(self, key: str):
        """运行时更新密钥"""
        if not key:
            self._fernet = None
            return
        
        digest = hashlib.sha256(key.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(digest)
        try:
            self._fernet = Fernet(fernet_key)
            os.environ["LLM_KEY"] = key
        except Exception as e:
            print(f"❌ SecurityManager: 密钥更新失败: {e}")
            self._fernet = None
