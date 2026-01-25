"""
安全管理模块
负责 API Key 的加密/解密和密钥管理
"""

import os
import base64
import hashlib
from cryptography.fernet import Fernet

from .env_utils import get_env_var, set_env_var


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

        key = get_env_var("LLM_KEY")

        if not key:
            print("⚠️ 警告: 未设置 LLM_KEY，将无法解密配置文件中的敏感信息。")
            print("   请在 server/.env 文件中设置 LLM_KEY，或运行配置工具。")
            self._fernet = None
        else:
            digest = hashlib.sha256(key.encode()).digest()
            fernet_key = base64.urlsafe_b64encode(digest)
            try:
                self._fernet = Fernet(fernet_key)
            except Exception as e:
                print(f"❌ 初始化加密组件失败: {e}")
                self._fernet = None
            
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
            # 解密失败（可能是密码错误或数据损坏），返回空值，
            # 这样上层逻辑会认为 key 无效/未配置，从而触发重新配置流程
            return ""

    def set_key(self, key: str, persist: bool = True):
        """
        运行时更新密钥
        
        Args:
            key: 新的密钥
            persist: 是否持久化到 .env 文件（默认 True）
        """
        if not key:
            self._fernet = None
            return
        
        digest = hashlib.sha256(key.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(digest)
        try:
            self._fernet = Fernet(fernet_key)
            # 更新当前进程环境变量
            os.environ["LLM_KEY"] = key
            # 持久化到 .env 文件
            if persist:
                set_env_var("LLM_KEY", key)
            # 刷新默认平台配置，确保加密字段即时解密生效
            try:
                from .config import reload_default_platform_configs
                reload_default_platform_configs()
            except Exception as e:
                print(f"⚠️ 已设置 LLM_KEY，但刷新平台配置失败：{e}")
        except Exception as e:
            print(f"❌ SecurityManager: 密钥更新失败: {e}")
            self._fernet = None
