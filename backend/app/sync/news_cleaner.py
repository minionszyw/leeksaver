"""
新闻数据清理器

负责清理过期新闻数据
"""

from datetime import datetime, timedelta

from sqlalchemy import and_, delete, or_

from app.config import settings
from app.core.database import get_db_session
from app.core.logging import get_logger
from app.models.news import NewsArticle
from app.repositories.stock_repository import WatchlistRepository

logger = get_logger(__name__)


class NewsCleaner:
    """新闻数据清理器"""

    async def cleanup_old_news(self) -> dict:
        """
        清理过期新闻

        策略：
        1. 删除超过保留期（默认 90 天）的新闻
        2. 保护自选股相关的新闻（如果配置启用）

        Returns:
            清理统计信息
        """
        retention_days = settings.news_retention_days
        protect_watchlist = settings.news_cleanup_protect_watchlist

        logger.info(
            "开始清理过期新闻",
            retention_days=retention_days,
            protect_watchlist=protect_watchlist,
        )

        try:
            # 计算截止时间
            cutoff_time = datetime.now() - timedelta(days=retention_days)

            async with get_db_session() as session:
                # 获取自选股代码（如果启用保护）
                watchlist_codes = []
                if protect_watchlist:
                    watchlist_repo = WatchlistRepository(session)
                    watchlist_codes = await watchlist_repo.get_codes()
                    logger.info("获取到自选股列表（保护）", count=len(watchlist_codes))

                # 构建删除条件
                delete_conditions = [NewsArticle.publish_time < cutoff_time]

                # 如果启用自选股保护，排除相关新闻
                if protect_watchlist and watchlist_codes:
                    # 排除 related_stocks 包含任意自选股代码的新闻
                    exclude_conditions = [
                        NewsArticle.related_stocks.like(f'%"{code}"%')
                        for code in watchlist_codes
                    ]

                    # 删除条件：过期 AND (不包含任何自选股代码)
                    delete_conditions.append(~or_(*exclude_conditions))

                # 执行删除
                stmt = delete(NewsArticle).where(and_(*delete_conditions))

                result = await session.execute(stmt)
                await session.commit()

                deleted_count = result.rowcount

                logger.info(
                    "新闻清理完成",
                    deleted=deleted_count,
                    cutoff_time=cutoff_time.isoformat(),
                    protected_watchlist_count=len(watchlist_codes) if protect_watchlist else 0,
                )

                return {
                    "status": "success",
                    "deleted": deleted_count,
                    "retention_days": retention_days,
                    "protect_watchlist": protect_watchlist,
                    "watchlist_count": len(watchlist_codes) if protect_watchlist else 0,
                }

        except Exception as e:
            logger.error("新闻清理失败", error=str(e))
            raise


# 全局单例
news_cleaner = NewsCleaner()
