"""ORM 数据模型定义文件。

使用 SQLAlchemy 定义 users 与 sessions 表，对应原先的 sqlite3 手工创建结构。

SQLAlchemy 的 nullable默认为 True。
"""

from datetime import datetime, timezone

from sqlalchemy import (
	Column,
	Integer,
	String,
	DateTime,
	Boolean,
	Float,
	JSON,
	UniqueConstraint,
	Index,
	create_engine,
	ForeignKey,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.types import TypeDecorator, BLOB
import json

UserInfo = declarative_base()
StoryData = declarative_base()

class SqliteJSONB(TypeDecorator):
    """自定义 SQLite JSONB 类型，使用 BLOB 存储并支持原生 jsonb() 优化。"""
    impl = BLOB
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        # 在写入时，我们返回字节串。如果需要利用 SQLite 的 jsonb() 函数，
        # 可以在 SQL 层面使用 func.jsonb()。
        return json.dumps(value, ensure_ascii=False).encode('utf-8')

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return json.loads(value.decode('utf-8'))

###系统用户相关###
class User(UserInfo):
	__tablename__ = "users"

	id = Column(Integer, primary_key=True, autoincrement=True)
	username = Column(String(150), unique=True, nullable=False, index=True)
	password_hash = Column(String(128), nullable=False)
	salt = Column(String(128), nullable=False)
	created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
	last_login = Column(DateTime, nullable=True)
	is_active = Column(Boolean, default=True, nullable=False)
	is_admin = Column(Boolean, default=False, nullable=False)  # 管理员角色
	mcp_api_key = Column(String(64), nullable=True, index=True)  # MCP 服务专用 API Key

	sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")

	first_login = Column(Integer, default=1)  # 是否首次登录，用于强制修改密码等
	def __repr__(self):  # pragma: no cover - 调试辅助
		return f"<User id={self.id} username={self.username!r} is_admin={self.is_admin}>"


class UserSession(UserInfo):
	__tablename__ = "user_sessions"

	id = Column(Integer, primary_key=True, autoincrement=True)
	user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
	session_token = Column(String(255), unique=True, nullable=False, index=True)
	created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
	expires_at = Column(DateTime, nullable=False, index=True)
	is_active = Column(Boolean, default=True, nullable=False)

	user = relationship("User", back_populates="sessions")

	__table_args__ = (
		UniqueConstraint("session_token", name="uq_session_token"),
		Index("ix_session_active", "is_active", "expires_at"),
	)

	def __repr__(self):  # pragma: no cover - 调试辅助
		return f"<Session id={self.id} user_id={self.user_id} active={self.is_active}>"


class ChatMessage(UserInfo):
	__tablename__ = "chat_messages"

	id = Column(Integer, primary_key=True, autoincrement=True)
	user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
	project_name = Column(String(255), nullable=False)
	agent_id = Column(String(100), nullable=False)
	context_key = Column(String(255), nullable=False, default="global")
	role = Column(String(20), nullable=False)  # 'user', 'assistant', 'system'
	content = Column(SqliteJSONB, nullable=False)
	metadata_json = Column(SqliteJSONB)
	timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

	user = relationship("User", backref="chat_messages")

	__table_args__ = (
		Index("idx_chat_session", "user_id", "project_name", "agent_id", "context_key"),
	)

	def __repr__(self):
		return f"<ChatMessage id={self.id} user={self.user_id} role={self.role}>"


class Share(UserInfo):
	__tablename__ = "shares"

	id = Column(String(36), primary_key=True)  # UUID
	user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
	project_name = Column(String(255), nullable=False)
	title = Column(String(255), nullable=False)
	description = Column(String, nullable=True)
	created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
	is_active = Column(Boolean, default=True, nullable=False) # 软删除标记
	is_shared = Column(Boolean, default=False, nullable=False) # 是否公开分享
	snapshot_path = Column(String(512), nullable=False)  # Path to the copied stories.db

	user = relationship("User", backref="shares")

	def __repr__(self):
		return f"<Share id={self.id} title={self.title!r}>"


class ProjectVersion(UserInfo):
	__tablename__ = "project_versions"

	id = Column(String(36), primary_key=True)  # UUID
	user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
	project_name = Column(String(255), nullable=False)
	version_name = Column(String(255), nullable=False)  # 用户定义的版本名，如 v1.0
	description = Column(String, nullable=True)
	snapshot_path = Column(String(512), nullable=False) # 快照数据库路径
	created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
	
	is_shared = Column(Boolean, default=False, nullable=False) # 是否开启分享
	share_id = Column(String(36), unique=True, nullable=True) # 分享用的唯一ID，如果开启分享则生成

	user = relationship("User", backref="versions")

	def __repr__(self):
		return f"<ProjectVersion id={self.id} project={self.project_name} version={self.version_name}>"


class SystemPlatformQuota(UserInfo):
	"""系统平台限额配置表
	
	用于管理员设置系统平台/模型的使用限额。
	只有使用系统提供的API Key时才会受此限额限制。
	用户自定义API Key时不受限额限制。
	
	quota_value:
		-1 = 无限制（默认）
		0 = 禁用
		>0 = 每日token限额
	"""
	__tablename__ = "system_platform_quotas"
	__table_args__ = (
		UniqueConstraint("platform_id", "model_id", name="uq_platform_model_quota"),
	)

	id = Column(Integer, primary_key=True, autoincrement=True)
	platform_id = Column(Integer, nullable=False, index=True)  # 系统平台ID
	model_id = Column(Integer, nullable=True, index=True)  # 模型ID，为空表示平台级别限额
	quota_value = Column(Integer, default=-1, nullable=False)  # -1=无限, 0=禁用, >0=每日token限额
	updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
	updated_by = Column(Integer, ForeignKey('users.id'), nullable=True)  # 最后修改的管理员

	def __repr__(self):
		return f"<SystemPlatformQuota platform={self.platform_id} model={self.model_id} quota={self.quota_value}>"


##########################数据相关表########################

class Story(StoryData):
	#本表用于存储每个场景的基本信息
	__tablename__ = "stories"
	id = Column(Integer, primary_key=True, autoincrement=True)#每个场景的唯一ID
	chapter = Column(Integer, nullable=False)#用来筛选场景的章节
	scene_name = Column(String, nullable=False)#场景名称 也是可选用于索引场景的字段
	button_text = Column(String) #可选 接近角色时 显示的对话按钮文本 为空时默认是角色名字
	progress = Column(Float, default=0, nullable=False)#完成当前场景后 欲将主线进度设置的值
	caption = Column(String, nullable=False)#显示在任务简要概述区的文本
	conditions = Column(SqliteJSONB) #可选 触发该场景的条件 对应行为act节点的record记录关键事件值 如果不符合条件 则根据进度顺序 自动索引到下一符合条件的场景
	#cond示例
	# {
	#     "player_success": "",#允许为空
	#     "npc1_status":"dead"
	# }
	dlg_json = Column(SqliteJSONB, nullable=False) #以原始的JSON格式存储每个场景的根级dia 也就是最上层对话节点下面的内容 并不包括子级的dia
	hiden = Column(Boolean)#为True隐藏本场景 一般情况下为null即可

class BindChr(StoryData):
	__tablename__ = "binding_chr"
	id = Column(Integer, primary_key=True, autoincrement=True)
	chr_id = Column(Integer, nullable=False)
	chr_name = Column(String, nullable=False)


class BindAct(StoryData):
	__tablename__ = "binding_act"
	id = Column(Integer, primary_key=True, autoincrement=True)
	act_type = Column(String)#函数类型 行为函数较多时 通过此字段来筛选
	act_name = Column(String, nullable=False)#目前系统已注册的行为函数 对应在act节点的名称 如“wether”
	func_name = Column(String, nullable=False)#对应的实际调用函数名 如“ChangeWeatherAPI”
	act_description = Column(String)#行为函数的描述 如“更改天气，第一个参数是...”
	act_args = Column(SqliteJSONB)#行为函数的参数示例 这些由自动程序转换
	# {
	#     "可选天气":["sunny","cloudy","rainy"] #传入list会在编辑器显示一个下拉框
	#	  "持续时间": 12
	#     "地点": "{place}" 同样允许直接使用占位符获取list
	# }


class Character(StoryData):
	"""角色表，存储角色ID与名称的映射"""
	__tablename__ = "characters"
	id = Column(Integer, primary_key=True, autoincrement=True)
	character_id = Column(Integer, nullable=False) # ARC脚本中的ID，如 0, 1
	name = Column(String, nullable=False)
	description = Column(String, nullable=True) # 简短描述
	content = Column(String, nullable=True) # 详细设定内容
	avatar_path = Column(String, nullable=True)  # 可选：头像路径


class Registry(StoryData):
	#用于注册一些全局信息 比如玩家名 游戏内的场景 可选的BGM 支持的天气 可以全局{}调用
	__tablename__ = "registry"
	id = Column(Integer, primary_key=True, autoincrement=True)
	name = Column(String, nullable=False)#place,player_name
	value = Column(SqliteJSONB, nullable=False)#必须为json数组 可以为单个变量 ["玩家名"] 此时会作为纯文本传入 也可以是一个选项数组["沃森区","太平洲","狗镇"] 此时作为数组传入



# 使用绝对路径，确保在不同目录下运行时都能找到同一个数据库
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
user_db_path = os.path.join(BASE_DIR, 'data', 'users.db')

user_engine = create_engine(f'sqlite:///{user_db_path}', echo=False, future=True)
UserInfoSession = sessionmaker(bind=user_engine, expire_on_commit=False, future=True)
#expire_on_commit参数指的是在提交事务后，是否立即过期会话中的对象 设为false一般用于绑定的对象只读的情况

# 注意：表创建现由 Alembic 迁移管理
# 首次部署时运行: cd server && alembic upgrade head -x db=users
# 如需保持向后兼容（无 Alembic 环境时自动创建表），取消下行注释：
# [FIX] 在 Alembic 运行时调用的 import 链中会导致死锁/占用，故注释掉。
# UserInfo.metadata.create_all(user_engine)