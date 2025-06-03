import sqlite3
import hashlib
import secrets
from datetime import datetime, timedelta
import os

class UserDatabase:
    def __init__(self, db_path='users.db'):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """初始化数据库表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
          # 创建用户表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        
        # 创建会话表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_token TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    def hash_password(self, password, salt=None):
        """哈希密码"""
        if salt is None:
            salt = secrets.token_hex(32)
        password_hash = hashlib.pbkdf2_hmac('sha256', 
                                          password.encode('utf-8'), 
                                          salt.encode('utf-8'), 
                                          100000)
        return password_hash.hex(), salt
    
    def create_user(self, username, password):
        """创建新用户"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 检查用户名是否已存在
            cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
            if cursor.fetchone():
                return False, "用户名已存在"
            
            # 哈希密码
            password_hash, salt = self.hash_password(password)
            
            # 插入新用户
            cursor.execute('''
                INSERT INTO users (username, password_hash, salt)
                VALUES (?, ?, ?)
            ''', (username, password_hash, salt))
            
            conn.commit()
            user_id = cursor.lastrowid
            conn.close()
            
            return True, user_id
            
        except Exception as e:
            return False, str(e)
    
    def verify_user(self, username, password):
        """验证用户登录"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT id, password_hash, salt FROM users WHERE username = ? AND is_active = 1', (username,))
            user = cursor.fetchone()
            
            if not user:
                conn.close()
                return False, "用户不存在或已被禁用"
            
            user_id, stored_hash, salt = user
            password_hash, _ = self.hash_password(password, salt)
            
            if password_hash == stored_hash:
                # 更新最后登录时间
                cursor.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (user_id,))
                conn.commit()
                conn.close()
                return True, user_id
            else:
                conn.close()
                return False, "密码错误"
                
        except Exception as e:
            return False, str(e)
    def create_session(self, user_id, session_days=7):
        """创建用户会话"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 生成会话令牌
            session_token = secrets.token_urlsafe(32)
            
            # 设置过期时间（默认7天，记住我30天）
            expires_at = datetime.now() + timedelta(days=session_days)
            
            # 清理该用户的旧会话
            cursor.execute('UPDATE sessions SET is_active = 0 WHERE user_id = ?', (user_id,))
            
            # 创建新会话
            cursor.execute('''
                INSERT INTO sessions (user_id, session_token, expires_at)
                VALUES (?, ?, ?)
            ''', (user_id, session_token, expires_at))
            
            conn.commit()
            conn.close()
            
            return session_token
            
        except Exception as e:
            return None
    
    def verify_session(self, session_token):
        """验证会话"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT s.user_id, u.username 
                FROM sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.session_token = ? 
                AND s.is_active = 1 
                AND s.expires_at > CURRENT_TIMESTAMP
            ''', (session_token,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return True, {"user_id": result[0], "username": result[1]}
            else:
                return False, None
                
        except Exception as e:
            return False, None
    
    def logout_user(self, session_token):
        """用户登出"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('UPDATE sessions SET is_active = 0 WHERE session_token = ?', (session_token,))
            
            conn.commit()
            conn.close()
            
            return True
            
        except Exception as e:
            return False
    def get_user_info(self, user_id):
        """获取用户信息"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT username, created_at, last_login 
                FROM users 
                WHERE id = ?
            ''', (user_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    "username": result[0],
                    "created_at": result[1],
                    "last_login": result[2]
                }
            else:
                return None
                
        except Exception as e:
            return None
