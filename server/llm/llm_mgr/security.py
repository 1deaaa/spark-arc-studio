"""
安全管理模块
负责 API Key 的加密/解密和密钥管理
"""

import os
import base64
import hashlib
from dataclasses import dataclass
from typing import Optional

from cryptography.fernet import Fernet

from .env_utils import get_env_var, set_env_var


@dataclass(frozen=True)
class SecretResolution:
    """结构化的解密结果。

    状态约定：
    - empty: 输入为空、None、或非字符串；表示当前没有可处理的密钥值。
    - plain: 输入本来就是明文；常见于尚未加密写库前的过渡数据。
    - success: 输入是 ENC: 密文，且已成功解密出明文。
    - missing_key: 遇到 ENC: 密文，但当前没有可用的主密钥 LLM_KEY。
    - failed: 已有主密钥，但无法解密；通常意味着主密钥不匹配、历史密文来自其他环境、或密文已损坏。
    """

    status: str
    value: Optional[str] = None
    encrypted_input: bool = False
    message: str = ""
    error: str = ""

    @property
    def has_plaintext(self) -> bool:
        return self.status in {"plain", "success"} and isinstance(self.value, str)

    @property
    def is_missing_key(self) -> bool:
        return self.status == "missing_key"

    @property
    def is_failed(self) -> bool:
        return self.status == "failed"

    def to_optional_plaintext(self) -> Optional[str]:
        return self.value if self.has_plaintext else None


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
            print("   请在 server/llm/llm_mgr/.env 文件中设置 LLM_KEY，或运行配置工具。")
            self._fernet = None
        else:
            try:
                self._fernet = self._build_fernet(key)
            except Exception as e:
                print(f"❌ 初始化加密组件失败: {e}")
                self._fernet = None

    @staticmethod
    def _build_fernet(key: str):
        key = str(key or "").strip()
        if not key:
            return None
        digest = hashlib.sha256(key.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(digest)
        return Fernet(fernet_key)

    @staticmethod
    def is_encrypted_value(text: str) -> bool:
        return isinstance(text, str) and text.startswith("ENC:")

    def has_active_key(self) -> bool:
        return self._fernet is not None

    @classmethod
    def _resolve_secret(cls, text: str, fernet) -> SecretResolution:
        if not text or not isinstance(text, str):
            return SecretResolution(
                status="empty",
                value=None,
                encrypted_input=False,
                message="输入为空，当前没有可处理的密钥值。",
            )

        if not text.startswith("ENC:"):
            return SecretResolution(
                status="plain",
                value=text,
                encrypted_input=False,
                message="输入本身就是明文。",
            )

        if not fernet:
            return SecretResolution(
                status="missing_key",
                value=None,
                encrypted_input=True,
                message="检测到加密密钥，但当前未设置主密钥 LLM_KEY。",
            )

        try:
            current = text
            for _ in range(5):
                if not current.startswith("ENC:"):
                    return SecretResolution(
                        status="success",
                        value=current,
                        encrypted_input=True,
                        message="密钥已成功解密。",
                    )
                ciphertext = current[4:]
                current = fernet.decrypt(ciphertext.encode()).decode()

            return SecretResolution(
                status="failed",
                value=None,
                encrypted_input=True,
                message="密钥解密层级异常（疑似重复加密或数据结构异常）。",
                error="too_many_encryption_layers",
            )
        except Exception as e:
            return SecretResolution(
                status="failed",
                value=None,
                encrypted_input=True,
                message="火柴网关主密钥无效，待配置新密钥......",
                error=str(e),
            )

    @classmethod
    def encrypt_with_key(cls, text: str, key: str) -> str:
        if not text:
            return text
        if isinstance(text, str) and text.startswith("ENC:"):
            raise ValueError("encrypt_with_key() 仅接受明文 API Key，禁止传入 ENC 密文")

        fernet = cls._build_fernet(key)
        if not fernet:
            raise ValueError("未提供有效的主密钥，无法执行加密操作")

        return "ENC:" + fernet.encrypt(text.encode()).decode()

    @classmethod
    def decrypt_with_key(cls, text: str, key: str) -> SecretResolution:
        fernet = cls._build_fernet(key)
        return cls._resolve_secret(text, fernet)
            
    def encrypt(self, text: str) -> str:
        if not text: return text
        if not self._fernet:
            raise ValueError("未设置 LLM_KEY，无法执行加密操作")
        if isinstance(text, str) and text.startswith("ENC:"):
            raise ValueError("encrypt() 仅接受明文 API Key，禁止传入 ENC 密文")
        try:
            return "ENC:" + self._fernet.encrypt(text.encode()).decode()
        except Exception as e:
            print(f"❌ 加密失败: {e}")
            raise ValueError(f"API Key 加密失败: {e}") from e
        
    def decrypt(self, text: str) -> SecretResolution:
        result = self._resolve_secret(text, self._fernet)
        if result.is_missing_key:
            print("⚠️ 警告: 遇到加密数据但未设置 LLM_KEY，当前只能保留密文状态")
        elif result.is_failed:
            print(f"❌ 解密失败: {result.error or result.message}")
        return result

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
        
        try:
            self._fernet = self._build_fernet(key)
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

