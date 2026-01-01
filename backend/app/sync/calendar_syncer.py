from datetime import date, timedelta
import polars as pl
from sqlalchemy.dialects.postgresql import insert

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.datasources.akshare_adapter import akshare_adapter
from app.models.calendar import TradingCalendar

logger = get_logger(__name__)


class CalendarSyncer:
    """
    交易日历同步器
    """

    async def sync(self) -> dict:
        """
        同步交易日历
        
        策略:
        1. 从 AkShare 获取历史交易日数据
        2. 筛选过去 2 年和未来 1 年的数据
        3. 批量更新数据库 (Upsert)
        """
        logger.info("开始同步交易日历")
        
        try:
            # 1. 获取数据
            df = await akshare_adapter.get_trading_calendar()
            if df.is_empty():
                logger.warning("未能从接口获取到交易日历数据")
                return {"status": "failed", "reason": "no_data"}

            # 2. 筛选范围
            today = date.today()
            start_date = today - timedelta(days=365 * 2)
            end_date = today + timedelta(days=365)
            
            # 过滤并转换
            # 假设 df 有 trade_date 列，类型为 date
            sync_df = df.filter(
                (pl.col("trade_date") >= start_date) & 
                (pl.col("trade_date") <= end_date)
            )
            
            if sync_df.is_empty():
                logger.warning("筛选后的交易日历数据为空", start=start_date, end=end_date)
                return {"status": "failed", "reason": "filtered_empty"}

            # 3. 写入数据库
            async with get_db_session() as session:
                synced_count = 0
                
                # 准备数据
                records = []
                for row in sync_df.iter_rows(named=True):
                    records.append({
                        "trade_date": row["trade_date"],
                        "is_open": True
                    })

                if records:
                    # 使用 PostgreSQL 的 ON CONFLICT 处理
                    stmt = insert(TradingCalendar).values(records)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["trade_date"],
                        set_={"is_open": stmt.excluded.is_open}
                    )
                    await session.execute(stmt)
                    synced_count = len(records)
                
                await session.commit()
                
            logger.info("交易日历同步完成", synced=synced_count)
            return {
                "status": "success", 
                "synced": synced_count,
                "range": f"{start_date} to {end_date}"
            }

        except Exception as e:
            logger.error("同步交易日历过程中发生异常", error=str(e))
            return {"status": "error", "message": str(e)}


# 全局单例
calendar_syncer = CalendarSyncer()
