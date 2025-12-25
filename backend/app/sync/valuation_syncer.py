"""
估值数据同步器

负责同步每日估值数据（PE、PB、市值等）
"""

import asyncio
from datetime import date
from decimal import Decimal

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
            df = await valuation_adapter.get_all_valuations(trade_date)

            if len(df) == 0:
                logger.warning("未获取到估值数据")
                return {"status": "no_data", "synced": 0}

            # 分批处理
            batch_size = settings.valuation_batch_size
            records = []

            for row in df.iter_rows(named=True):
                records.append({
                    "code": row["code"],
                    "trade_date": row["trade_date"],
                    "pe_ttm": Decimal(str(row["pe_ttm"])) if row["pe_ttm"] else None,
                    "pb": Decimal(str(row["pb"])) if row["pb"] else None,
                    "total_mv": Decimal(str(row["total_mv"])) if row["total_mv"] else None,
                    "circ_mv": Decimal(str(row["circ_mv"])) if row["circ_mv"] else None,
                })

            # 批量存储
            total_synced = 0
            async with get_db_session() as session:
                repo = ValuationRepository(session)

                for i in range(0, len(records), batch_size):
                    batch = records[i:i + batch_size]
                    count = await repo.upsert_many(batch)
                    total_synced += count

                    # 避免过快写入
                    if i + batch_size < len(records):
                        await asyncio.sleep(0.1)

            logger.info("估值数据同步完成", count=total_synced)
            return {"status": "success", "synced": total_synced}

        except Exception as e:
            logger.error("估值数据同步失败", error=str(e))
            raise


# 全局单例
valuation_syncer = ValuationSyncer()
