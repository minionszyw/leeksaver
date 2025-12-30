from datetime import datetime, timedelta, timezone
from sqlalchemy import delete
from app.config import settings
from app.core.database import get_db_session
from app.core.logging import get_logger
from app.models.news import NewsArticle, StockNewsArticle

logger = get_logger(__name__)

class NewsCleaner:
    """新闻数据清理器"""

    async def cleanup_old_news(self) -> dict:
        """
        清理过期新闻 (全市与个股同步处理)
        """
        retention_years = settings.news_retention_years
        logger.info("开始清理过期新闻", retention_years=retention_years)

        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=365 * retention_years)
            
            async with get_db_session() as session:
                # 清理全市新闻
                stmt1 = delete(NewsArticle).where(NewsArticle.publish_time < cutoff_time)
                res1 = await session.execute(stmt1)
                
                # 清理个股新闻
                stmt2 = delete(StockNewsArticle).where(StockNewsArticle.publish_time < cutoff_time)
                res2 = await session.execute(stmt2)
                
                await session.commit()
                
                deleted_market = res1.rowcount
                deleted_stock = res2.rowcount

                logger.info("新闻清理完成", deleted_market=deleted_market, deleted_stock=deleted_stock)

                return {
                    "status": "success",
                    "deleted_market": deleted_market,
                    "deleted_stock": deleted_stock,
                    "cutoff_time": cutoff_time.isoformat()
                }
        except Exception as e:
            logger.error("新闻清理失败", error=str(e))
            raise

news_cleaner = NewsCleaner()