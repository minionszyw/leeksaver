"""
会话管理器

管理用户对话会话和上下文
"""

import json
from datetime import datetime, timedelta
from typing import Any

import redis.asyncio as redis

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class Message:
    """会话消息"""

    def __init__(
        self,
        role: str,
        content: str,
        timestamp: datetime | None = None,
        data: dict | None = None,
    ):
        self.role = role
        self.content = content
        self.timestamp = timestamp or datetime.now()
        self.data = data

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            data=data.get("data"),
        )


class Session:
    """会话"""

    def __init__(
        self,
        session_id: str,
        messages: list[Message] | None = None,
        created_at: datetime | None = None,
        metadata: dict | None = None,
    ):
        self.session_id = session_id
        self.messages = messages or []
        self.created_at = created_at or datetime.now()
        self.metadata = metadata or {}

    def add_message(self, role: str, content: str, data: dict | None = None):
        """添加消息"""
        self.messages.append(Message(role=role, content=content, data=data))

    def get_recent_messages(self, n: int = 10) -> list[Message]:
        """获取最近 N 条消息"""
        return self.messages[-n:]

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "messages": [m.to_dict() for m in self.messages],
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        return cls(
            session_id=data["session_id"],
            messages=[Message.from_dict(m) for m in data.get("messages", [])],
            created_at=datetime.fromisoformat(data["created_at"]),
            metadata=data.get("metadata", {}),
        )


class SessionManager:
    """
    会话管理器

    使用 Redis 存储会话数据
    """

    def __init__(
        self,
        redis_url: str | None = None,
        max_messages: int = 20,
        session_ttl: int = 3600,  # 1 小时
    ):
        self.redis_url = redis_url or settings.redis_url
        self.max_messages = max_messages
        self.session_ttl = session_ttl
        self._redis: redis.Redis | None = None

    async def _get_redis(self) -> redis.Redis:
        """获取 Redis 连接"""
        if self._redis is None:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    def _get_key(self, session_id: str) -> str:
        """获取 Redis Key"""
        return f"leeksaver:session:{session_id}"

    async def get_session(self, session_id: str) -> Session:
        """获取或创建会话"""
        r = await self._get_redis()
        key = self._get_key(session_id)

        data = await r.get(key)
        if data:
            try:
                return Session.from_dict(json.loads(data))
            except Exception as e:
                logger.warning("解析会话数据失败", session_id=session_id, error=str(e))

        # 创建新会话
        return Session(session_id=session_id)

    async def save_session(self, session: Session):
        """保存会话"""
        r = await self._get_redis()
        key = self._get_key(session.session_id)

        # 限制消息数量
        if len(session.messages) > self.max_messages:
            session.messages = session.messages[-self.max_messages :]

        data = json.dumps(session.to_dict(), ensure_ascii=False)
        await r.setex(key, self.session_ttl, data)

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        data: dict | None = None,
    ):
        """添加消息到会话"""
        session = await self.get_session(session_id)
        session.add_message(role, content, data)
        await self.save_session(session)

    async def get_context(self, session_id: str, n: int = 5) -> list[dict]:
        """
        获取会话上下文

        返回最近 N 轮对话，用于 LLM 上下文
        """
        session = await self.get_session(session_id)
        messages = session.get_recent_messages(n * 2)  # user + assistant

        return [{"role": m.role, "content": m.content} for m in messages]

    async def clear_session(self, session_id: str):
        """清除会话"""
        r = await self._get_redis()
        key = self._get_key(session_id)
        await r.delete(key)

    async def close(self):
        """关闭连接"""
        if self._redis:
            await self._redis.close()
            self._redis = None


# 全局会话管理器
session_manager = SessionManager()
