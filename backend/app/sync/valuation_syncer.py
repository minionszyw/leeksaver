"""
估值数据同步器

负责同步每日估值数据（PE、PB、市值等）
"""

import asyncio
from datetime import date
from decimal import Decimal

import polars as pl

from app.config import settings
from app.core.database import get_db_session
from app.core.logging import get_logger
from app.datasources.valuation_adapter import valuation_adapter
from app.repositories.valuation_repository import ValuationRepository

logger = get_logger(__name__)


class ValuationSyncer:
    """估值数据同步器"""

    async def sync_all(self, trade_date: date) -> dict:
        """
        同步全市场估值数据

        Args:
            trade_date: 交易日期
        """
        logger.info("开始同步全市场估值", trade_date=str(trade_date))

        try:
            # 获取全市场估值数据
            result_data = await valuation_adapter.get_all_valuations(trade_date)

            # 容错：检查是否为有效的列表或 Polars DataFrame
            # 由于使用了缓存装饰器，这里可能返回 dict {"data": [...], "columns": [...]}
            if isinstance(result_data, dict) and "data" in result_data:
                records_raw = result_data["data"]
            elif isinstance(result_data, pl.DataFrame):
                records_raw = result_data.to_dicts()
            else:
                logger.warning("未获取到全市场估值数据，可能为非交易日或接口限频", trade_date=str(trade_date))
                return {"status": "no_data", "synced": 0}

            if not records_raw:
                logger.warning("估值数据为空", trade_date=str(trade_date))
                return {"status": "no_data", "synced": 0}

            # 处理数据格式
            records = []
            for row in records_raw:
                records.append({
                    "code": row["code"],
                    "trade_date": row["trade_date"],
                    "pe_ttm": Decimal(str(row["pe_ttm"])) if row.get("pe_ttm") else None,
                    "pb": Decimal(str(row["pb"])) if row.get("pb") else None,
                    "total_mv": Decimal(str(row["total_mv"])) if row.get("total_mv") else None,
                    "circ_mv": Decimal(str(row["circ_mv"])) if row.get("circ_mv") else None,
                })

            # 批量存储
            total_synced = 0
            async with get_db_session() as session:
                repo = ValuationRepository(session)

                for i in range(0, len(records), settings.valuation_batch_size):
                    batch = records[i:i + settings.valuation_batch_size]
                    count = await repo.upsert_many(batch)
                    total_synced += count

                    # 避免过快写入
                    if i + settings.valuation_batch_size < len(records):
                        await asyncio.sleep(0.1)

            logger.info("估值数据同步完成", count=total_synced)
            return {"status": "success", "synced": total_synced}

        except Exception as e:
            logger.error("估值数据同步失败", error=str(e))
            raise


# 全局单例
valuation_syncer = ValuationSyncer()
