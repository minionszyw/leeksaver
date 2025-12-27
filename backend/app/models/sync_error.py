"""
同步错误记录模型
"""

from datetime import datetime

from sqlalchemy import Column, String, DateTime, Integer, Text, Index

from app.models.base import Base


class SyncError(Base):
    """同步错误记录表"""

    __tablename__ = "sync_errors"

    id = Column(Integer, primary_key=True)
    task_name = Column(String(100), nullable=False, comment="任务名称，例如: sync_daily_quotes")
    target_code = Column(String(20), nullable=False, comment="目标股票代码")
    error_type = Column(String(50), nullable=False, comment="错误类型，例如: RateLimitError")
    error_message = Column(Text, nullable=False, comment="错误详细信息")
    retry_count = Column(Integer, default=0, comment="重试次数")
    last_retry_at = Column(DateTime, nullable=True, comment="最后重试时间")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, comment="创建时间")
    resolved_at = Column(DateTime, nullable=True, comment="成功恢复的时间")

    __table_args__ = (
        Index("ix_sync_errors_task_code", "task_name", "target_code"),
        Index("ix_sync_errors_created", "created_at"),
        Index("ix_sync_errors_unresolved", "resolved_at"),  # 快速查询未解决的错误
    )

    def __repr__(self):
        return f"<SyncError(task={self.task_name}, code={self.target_code}, error={self.error_type})>"
