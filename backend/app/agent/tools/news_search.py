"""
新闻检索工具

提供语义搜索和按股票检索财经新闻的功能
"""

from datetime import datetime
from typing import List, Literal

from pydantic import BaseModel, Field

from app.agent.tools.base import ToolBase, ToolResult
from app.core.database import get_db_session
from app.core.logging import get_logger
from app.repositories.news_repository import NewsRepository
from app.services.embedding_service import embedding_service

logger = get_logger(__name__)


class NewsArticleOutput(BaseModel):
    """新闻文章输出格式"""

    title: str = Field(description="新闻标题")
    summary: str | None = Field(description="新闻摘要")
    content: str = Field(description="新闻正文")
    source: str = Field(description="数据源")
    publish_time: datetime = Field(description="发布时间")
    url: str = Field(description="原文链接")
    related_stocks: str | None = Field(description="关联股票代码（JSON 数组）")


class NewsSearchResult(BaseModel):
    """新闻搜索结果"""

    total: int = Field(description="找到的新闻数量")
    articles: List[NewsArticleOutput] = Field(description="新闻列表")
    query: str | None = Field(default=None, description="查询文本")
    stock_code: str | None = Field(default=None, description="股票代码")


class SemanticSearchInput(BaseModel):
    """语义搜索输入"""

    query: str = Field(description="搜索关键词或问题，如：'贵州茅台 业绩'、'新能源汽车 政策'")
    limit: int = Field(default=10, ge=1, le=50, description="返回结果数量（1-50）")
    days: int = Field(default=7, ge=1, le=30, description="搜索最近 N 天的新闻（1-30）")
    similarity_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="相似度阈值（0-1），越高越严格",
    )


class StockNewsInput(BaseModel):
    """按股票搜索新闻输入"""

    stock_code: str = Field(description="股票代码，如：600519、000001")
    limit: int = Field(default=10, ge=1, le=50, description="返回结果数量（1-50）")
    days: int = Field(default=7, ge=1, le=30, description="搜索最近 N 天的新闻（1-30）")


class NewsSearchTool(ToolBase):
    """
    新闻语义搜索工具

    使用向量相似度搜索相关新闻
    """

    name: str = "news_semantic_search"
    description: str = """
    通过语义搜索查找相关财经新闻。

    适用场景：
    - 查询某个主题的新闻（如：'白酒行业 调整'）
    - 了解某个事件的报道（如：'茅台 价格上涨'）
    - 寻找特定关键词的新闻（如：'新能源汽车 补贴政策'）

    返回最近 N 天内相似度最高的新闻。
    """

    input_schema = SemanticSearchInput
    output_schema = NewsSearchResult

    async def execute(self, **kwargs) -> ToolResult:
        """执行语义搜索"""
        try:
            # 验证输入
            params = self.validate_input(**kwargs)
            if not params:
                return ToolResult(success=False, error="参数验证失败")

            logger.info(
                "执行新闻语义搜索",
                query=params.query,
                limit=params.limit,
                days=params.days,
            )

            # 执行搜索
            async with get_db_session() as session:
                articles = await embedding_service.search_similar_news(
                    session=session,
                    query_text=params.query,
                    limit=params.limit,
                    similarity_threshold=params.similarity_threshold,
                    days=params.days,
                )

            # 转换为输出格式
            result = NewsSearchResult(
                total=len(articles),
                query=params.query,
                articles=[
                    NewsArticleOutput(
                        title=article.title,
                        summary=article.summary,
                        content=article.content[:500] + "..."
                        if len(article.content) > 500
                        else article.content,  # 截断过长内容
                        source=article.source,
                        publish_time=article.publish_time,
                        url=article.url,
                        related_stocks=article.related_stocks,
                    )
                    for article in articles
                ],
            )

            logger.info("新闻语义搜索完成", found_count=result.total)

            return ToolResult(
                success=True,
                data=result,
                message=f"找到 {result.total} 条相关新闻",
            )

        except Exception as e:
            logger.error("新闻语义搜索失败", error=str(e))
            return ToolResult(success=False, error=f"搜索失败: {str(e)}")


class StockNewsTool(ToolBase):
    """
    股票新闻检索工具

    按股票代码检索相关新闻
    """

    name: str = "stock_news_search"
    description: str = """
    按股票代码查找相关新闻。

    适用场景：
    - 查询某只股票的最新新闻（如：600519 贵州茅台）
    - 了解个股的近期动态
    - 获取公司公告和新闻报道

    返回最近 N 天内该股票的相关新闻，按时间降序排列。
    """

    input_schema = StockNewsInput
    output_schema = NewsSearchResult

    async def execute(self, **kwargs) -> ToolResult:
        """执行股票新闻检索"""
        try:
            # 验证输入
            params = self.validate_input(**kwargs)
            if not params:
                return ToolResult(success=False, error="参数验证失败")

            logger.info(
                "执行股票新闻检索",
                stock_code=params.stock_code,
                limit=params.limit,
                days=params.days,
            )

            # 执行检索
            async with get_db_session() as session:
                repo = NewsRepository(session)
                articles = await repo.get_articles_by_stock(
                    stock_code=params.stock_code,
                    days=params.days,
                    limit=params.limit,
                )

            # 转换为输出格式
            result = NewsSearchResult(
                total=len(articles),
                stock_code=params.stock_code,
                articles=[
                    NewsArticleOutput(
                        title=article.title,
                        summary=article.summary,
                        content=article.content[:500] + "..."
                        if len(article.content) > 500
                        else article.content,
                        source=article.source,
                        publish_time=article.publish_time,
                        url=article.url,
                        related_stocks=article.related_stocks,
                    )
                    for article in articles
                ],
            )

            logger.info("股票新闻检索完成", stock_code=params.stock_code, found_count=result.total)

            return ToolResult(
                success=True,
                data=result,
                message=f"找到 {result.total} 条 {params.stock_code} 的相关新闻",
            )

        except Exception as e:
            logger.error("股票新闻检索失败", stock_code=params.stock_code, error=str(e))
            return ToolResult(success=False, error=f"检索失败: {str(e)}")


# 注册工具
from app.agent.tools.base import ToolRegistry

ToolRegistry.register(NewsSearchTool())
ToolRegistry.register(StockNewsTool())
