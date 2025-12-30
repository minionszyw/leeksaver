"""
新闻资讯数据模型
"""

from datetime import datetime
from typing import Optional, Any

from sqlalchemy import String, DateTime, Text, Index, Integer, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.models.base import Base, TimestampMixin


class NewsArticle(Base, TimestampMixin):
    """
    全市新闻电报表 (财联社)
    """

    __tablename__ = "news_articles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # 财联社原生 ID (用于去重)
    cls_id: Mapped[Optional[int]] = mapped_column(Integer, unique=True, comment="财联社原生ID")
    
    title: Mapped[str] = mapped_column(String(500), nullable=False, comment="标题")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="正文")
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="财联社")
    publish_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    
    # 扩展字段
    importance_level: Mapped[int] = mapped_column(Integer, default=1, comment="重要性级别(1-5)")
    related_stocks: Mapped[Optional[str]] = mapped_column(String(500), comment="关联股票代码")
    keywords: Mapped[Optional[str]] = mapped_column(String(500), comment="分类标签")
    
    # 存储所有原始数据以便回溯
    raw_data: Mapped[Optional[dict]] = mapped_column(JSON, comment="原始JSON数据")
    
    embedding: Mapped[Optional[Vector]] = mapped_column(Vector(1024))

    __table_args__ = (
        Index("ix_news_articles_publish_time", "publish_time"),
        {"comment": "全市新闻电报表 (财联社单一源)"},
    )


class StockNewsArticle(Base, TimestampMixin):
    """
    个股深度新闻表 (东方财富)
    """

    __tablename__ = "stock_news_articles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True, comment="关联股票代码")
    
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    publish_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    
    keywords: Mapped[Optional[str]] = mapped_column(String(500))
    raw_data: Mapped[Optional[dict]] = mapped_column(JSON)
    
    embedding: Mapped[Optional[Vector]] = mapped_column(Vector(1024))

    __table_args__ = (
        Index("ix_stock_news_articles_stock_publish", "stock_code", "publish_time"),
        {"comment": "个股深度新闻表 (东方财富源)"},
    )
