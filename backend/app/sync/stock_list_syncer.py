"""
股票列表同步器
"""

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.datasources.akshare_adapter import akshare_adapter
from app.repositories.stock_repository import StockRepository

logger = get_logger(__name__)


class StockListSyncer:
    """股票列表同步器"""

    async def sync(self) -> dict:
        """
        同步全市场股票和 ETF 列表

        Returns:
            同步结果统计
        """
        logger.info("开始同步股票列表")

        stats = {
            "stocks": 0,
            "etfs": 0,
            "total": 0,
            "errors": [],
        }

        try:
            # 获取股票列表
            logger.info("获取股票列表...")
            stock_df = await akshare_adapter.get_stock_list()
            stats["stocks"] = len(stock_df)

            # 获取 ETF 列表
            logger.info("获取 ETF 列表...")
            etf_df = await akshare_adapter.get_etf_list()
            stats["etfs"] = len(etf_df)

            # 补充股票元数据（行业、上市日期等）
            logger.info("补充股票元数据...")
            stock_df = await akshare_adapter.enrich_stock_list_with_metadata(stock_df)

            # 为 ETF 添加相同的列结构（industry 和 list_date 设为 NULL）
            import polars as pl

            etf_df = etf_df.with_columns(
                [
                    pl.lit(None, dtype=pl.Utf8).alias("industry"),
                    pl.lit(None, dtype=pl.Date).alias("list_date"),
                ]
            )

            # 合并数据
            all_df = pl.concat([stock_df, etf_df])
            stats["total"] = len(all_df)

            # 转换为字典列表
            records = all_df.to_dicts()

            # 写入数据库
            async with get_db_session() as session:
                repo = StockRepository(session)
                await repo.upsert_many(records)

            logger.info(
                "股票列表同步完成",
                stocks=stats["stocks"],
                etfs=stats["etfs"],
                total=stats["total"],
            )

        except Exception as e:
            logger.error("股票列表同步失败", error=str(e))
            stats["errors"].append(str(e))
            raise

        return stats


# 全局单例
stock_list_syncer = StockListSyncer()
