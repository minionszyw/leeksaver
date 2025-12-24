"""
新闻资讯数据模型
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Text, Index
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.models.base import Base, TimestampMixin


class NewsArticle(Base, TimestampMixin):
    """
    新闻文章表

    存储财经新闻数据，支持向量检索
    """

    __tablename__ = "news_articles"

    # 主键 ID
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # 标题
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="新闻标题",
    )

    # 正文内容
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="新闻正文",
    )

    # 摘要（可选，用于显示）
    summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="新闻摘要",
    )

    # 数据源
    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="数据源: eastmoney-东方财富, sina-新浪财经, etc.",
    )

    # 发布时间
    publish_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="发布时间",
    )

    # 原文链接
    url: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        comment="原文链接",
    )

    # 关联股票代码（JSON 字符串格式）
    # 例如: '["600519", "000001"]'
    related_stocks: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="关联股票代码列表（JSON 格式）",
    )

    # 文本向量（1536 维，OpenAI text-embedding-3-small）
    embedding: Mapped[Optional[Vector]] = mapped_column(
        Vector(1536),
        nullable=True,
        comment="文本向量（OpenAI text-embedding-3-small）",
    )

    # 索引
    __table_args__ = (
        Index("ix_news_articles_publish_time", "publish_time"),
        Index("ix_news_articles_source", "source"),
        Index("ix_news_articles_url", "url", unique=True),  # URL 唯一，防止重复
        # pgvector HNSW 索引（高效向量检索）
        Index(
            "ix_news_articles_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        {"comment": "新闻文章表"},
    )

    def __repr__(self) -> str:
        return f"<NewsArticle {self.id} {self.title[:30]}>"
