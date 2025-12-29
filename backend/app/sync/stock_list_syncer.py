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

        采用两步走策略：
        1. 快速获取基础列表并入库（代码+名称），解锁后续行情任务
        2. 耗时抓取详细元数据并更新
        """
        logger.info("开始同步股票列表")

        stats = {
            "stocks": 0,
            "etfs": 0,
            "total": 0,
            "errors": [],
        }

        try:
            # 1. 快速获取基础列表
            logger.info("获取股票列表基础信息...")
            stock_df = await akshare_adapter.get_stock_list()
            stats["stocks"] = len(stock_df)

            logger.info("获取 ETF 列表基础信息...")
            etf_df = await akshare_adapter.get_etf_list()
            stats["etfs"] = len(etf_df)

            # 快速入库基础数据 (仅代码和名称)
            import polars as pl
            # 统一结构以便合并入库
            base_stocks = stock_df.select(["code", "name", "asset_type", "market"])
            base_etfs = etf_df.select(["code", "name", "asset_type", "market"])
            
            all_base_df = pl.concat([base_stocks, base_etfs])
            async with get_db_session() as session:
                repo = StockRepository(session)
                await repo.upsert_many(all_base_df.to_dicts())
                await session.commit()
            
            logger.info("第一阶段：基础列表已入库，后续行情任务已解锁", total=len(all_base_df))

            # 2. 补充股票元数据（行业、上市日期等）- 这一步较慢
            logger.info("第二阶段：开始补充股票元数据...")
            stock_df = await akshare_adapter.enrich_stock_list_with_metadata(stock_df)

            # 为 ETF 添加相同的列结构（industry 和 list_date 设为 NULL）
            etf_df = etf_df.with_columns(
                [
                    pl.lit(None, dtype=pl.Utf8).alias("industry"),
                    pl.lit(None, dtype=pl.Date).alias("list_date"),
                ]
            )

            # 合并完整数据
            all_df = pl.concat([stock_df, etf_df])
            stats["total"] = len(all_df)

            # 更新数据库完整信息
            async with get_db_session() as session:
                repo = StockRepository(session)
                await repo.upsert_many(all_df.to_dicts())
                await session.commit()

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

    async def sync_metadata_only(self, limit: int = 500) -> dict:
        """
        仅同步缺失的元数据

        Args:
            limit: 本次处理的股票数量限制

        Returns:
            处理统计
        """
        logger.info("开始增量同步股票元数据", limit=limit)
        
        async with get_db_session() as session:
            repo = StockRepository(session)
            # 获取缺失元数据的股票
            stocks = await repo.get_all() # 这里可能需要一个专门的 get_missing_metadata
            
            # 简单起见，这里先取所有，然后在内存过滤
            import polars as pl
            df = pl.from_dicts([{"code": s.code, "industry": s.industry, "list_date": s.list_date} for s in stocks])
            
            missing = df.filter(pl.col("industry").is_null() | pl.col("list_date").is_null()).head(limit)
            
            if len(missing) == 0:
                logger.info("没有缺失元数据的股票")
                return {"count": 0}

            logger.info(f"发现 {len(missing)} 只股票缺失元数据，开始补充")
            
            # 仅传入 code 列进行补充
            enriched = await akshare_adapter.enrich_stock_list_with_metadata(missing.select("code"))
            
            # 写入数据库
            records = enriched.to_dicts()
            await repo.upsert_many(records)
            
            logger.info("增量补充股票元数据完成", count=len(records))
            return {"count": len(records)}


# 全局单例
stock_list_syncer = StockListSyncer()
