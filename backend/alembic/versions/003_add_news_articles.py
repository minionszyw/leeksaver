"""添加新闻资讯数据表

Revision ID: 003
Revises: 002
Create Date: 2024-01-16

创建新闻资讯表:
- news_articles: 财经新闻数据，支持向量检索
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 启用 pgvector 扩展
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 创建 news_articles 表
    op.create_table(
        "news_articles",
        # 主键
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),

        # 新闻内容字段
        sa.Column("title", sa.String(500), nullable=False, comment="新闻标题"),
        sa.Column("content", sa.Text, nullable=False, comment="新闻正文"),
        sa.Column("summary", sa.Text, nullable=True, comment="新闻摘要"),

        # 元数据字段
        sa.Column(
            "source",
            sa.String(50),
            nullable=False,
            comment="数据源: eastmoney/sina/etc.",
        ),
        sa.Column(
            "publish_time",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="发布时间",
        ),
        sa.Column("url", sa.String(1000), nullable=False, comment="原文链接"),
        sa.Column(
            "related_stocks",
            sa.String(500),
            nullable=True,
            comment="关联股票代码列表（JSON 格式）",
        ),

        # 向量字段（1536 维，OpenAI text-embedding-3-small）
        sa.Column(
            "embedding",
            Vector(1536),
            nullable=True,
            comment="文本向量（OpenAI text-embedding-3-small）",
        ),

        # 时间戳字段
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),

        comment="新闻文章表",
    )

    # 创建索引
    op.create_index(
        "ix_news_articles_publish_time",
        "news_articles",
        ["publish_time"],
    )
    op.create_index(
        "ix_news_articles_source",
        "news_articles",
        ["source"],
    )
    op.create_index(
        "ix_news_articles_url",
        "news_articles",
        ["url"],
        unique=True,  # URL 唯一，防止重复
    )

    # 创建 HNSW 向量索引（高效余弦相似度检索）
    op.execute(
        """
        CREATE INDEX ix_news_articles_embedding_hnsw
        ON news_articles
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )


def downgrade() -> None:
    # 删除表（索引会自动删除）
    op.drop_table("news_articles")

    # 禁用 pgvector 扩展（可选，如果其他表也使用则不应禁用）
    # op.execute("DROP EXTENSION IF EXISTS vector")
