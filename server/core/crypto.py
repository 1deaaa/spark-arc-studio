import base64
from typing import Tuple
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend

class RSAKeyManager:
    _instance = None
    
    def __init__(self):
        # 每次启动应用时生成新的临时密钥对
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        self.public_key = self.private_key.public_key()
        
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_public_key_pem(self) -> str:
        """获取 PEM 格式的公钥，供前端使用"""
        pem = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return pem.decode('utf-8')

    def decrypt(self, encrypted_b64: str) -> str:
        """
        解密前端传输的数据
        前端使用 RSA-OAEP, SHA-256
        """
        try:
            encrypted_data = base64.b64decode(encrypted_b64)
            original_data = self.private_key.decrypt(
                encrypted_data,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            return original_data.decode('utf-8')
        except Exception as e:
            print(f"解密失败: {e}")
            raise ValueError("数据解密失败")

# 单例模式
rsa_manager = RSAKeyManager.get_instance()