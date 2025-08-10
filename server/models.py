"""ORM 数据模型定义文件。

使用 SQLAlchemy 定义 users 与 sessions 表，对应原先的 sqlite3 手工创建结构。
"""

from datetime import datetime
from sqlalchemy import (
	Column,
	Integer,
	String,
	DateTime,
	Boolean,
	ForeignKey,
	UniqueConstraint,
	Index,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
	__tablename__ = "users"

	id = Column(Integer, primary_key=True, autoincrement=True)
	username = Column(String(150), unique=True, nullable=False, index=True)
	password_hash = Column(String(128), nullable=False)
	salt = Column(String(128), nullable=False)
	created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
	last_login = Column(DateTime, nullable=True)
	is_active = Column(Boolean, default=True, nullable=False)

	sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")

	def __repr__(self):  # pragma: no cover - 调试辅助
		return f"<User id={self.id} username={self.username!r}>"


class Session(Base):
	__tablename__ = "sessions"

	id = Column(Integer, primary_key=True, autoincrement=True)
	user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
	session_token = Column(String(255), unique=True, nullable=False, index=True)
	created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
	expires_at = Column(DateTime, nullable=False, index=True)
	is_active = Column(Boolean, default=True, nullable=False)

	user = relationship("User", back_populates="sessions")

	__table_args__ = (
		UniqueConstraint("session_token", name="uq_session_token"),
		Index("ix_session_active", "is_active", "expires_at"),
	)

	def __repr__(self):  # pragma: no cover - 调试辅助
		return f"<Session id={self.id} user_id={self.user_id} active={self.is_active}>"

