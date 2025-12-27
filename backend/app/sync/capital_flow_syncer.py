"""
资金面数据同步器

负责同步北向资金、个股资金流向、龙虎榜、两融数据
"""

from datetime import date
from decimal import Decimal

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.datasources.capital_flow_adapter import capital_flow_adapter
from app.repositories.capital_flow_repository import (
    NorthboundFlowRepository,
    StockFundFlowRepository,
    DragonTigerRepository,
    MarginTradeRepository,
)

logger = get_logger(__name__)


class CapitalFlowSyncer:
    """资金面数据同步器"""

    async def sync_northbound_flow(self, trade_date: date | None = None) -> dict:
        """
        同步北向资金数据

        Args:
            trade_date: 指定日期，为空则同步最新数据
        """
        logger.info("开始同步北向资金", trade_date=str(trade_date) if trade_date else "最新")

        try:
            # 获取数据
            data = await capital_flow_adapter.get_northbound_flow(trade_date)

            if not data:
                logger.warning("未获取到北向资金数据")
                return {"status": "no_data", "synced": 0}

            # 存储
            async with get_db_session() as session:
                repo = NorthboundFlowRepository(session)
                await repo.upsert(data)

            logger.info("北向资金同步完成", trade_date=str(data["trade_date"]))
            return {"status": "success", "synced": 1, "trade_date": str(data["trade_date"])}

        except Exception as e:
            logger.error("北向资金同步失败", error=str(e))
            raise

    async def sync_northbound_history(self) -> dict:
        """
        同步北向资金历史数据
        """
        logger.info("开始同步北向资金历史数据")

        try:
            # 获取历史数据
            df = await capital_flow_adapter.get_northbound_flow_history()

            if len(df) == 0:
                logger.warning("未获取到北向资金历史数据")
                return {"status": "no_data", "synced": 0}

            # 转换为记录
            records = []
            for row in df.iter_rows(named=True):
                records.append({
                    "trade_date": row["trade_date"],
                    "sh_net_inflow": Decimal(str(row["sh_net_inflow"])) if row["sh_net_inflow"] is not None else None,
                    "sz_net_inflow": Decimal(str(row["sz_net_inflow"])) if row["sz_net_inflow"] is not None else None,
                    "total_net_inflow": Decimal(str(row["total_net_inflow"])) if row["total_net_inflow"] is not None else None,
                })

            # 存储
            async with get_db_session() as session:
                repo = NorthboundFlowRepository(session)
                count = await repo.upsert_many(records)

            logger.info("北向资金历史同步完成", count=count)
            return {"status": "success", "synced": count}

        except Exception as e:
            logger.error("北向资金历史同步失败", error=str(e))
            raise

    async def sync_stock_fund_flow(
        self,
        trade_date: date,
        limit: int = 100,
    ) -> dict:
        """
        同步个股资金流向数据

        Args:
            trade_date: 交易日期
            limit: 获取排行前 N 名
        """
        logger.info("开始同步资金流向", trade_date=str(trade_date), limit=limit)

        try:
            # 获取资金流向排行
            df = await capital_flow_adapter.get_stock_fund_flow_rank(
                indicator="今日",
                limit=limit,
            )

            if len(df) == 0:
                logger.warning("未获取到资金流向数据")
                return {"status": "no_data", "synced": 0}

            # 转换为记录
            records = []
            for row in df.iter_rows(named=True):
                records.append({
                    "code": row["code"],
                    "trade_date": trade_date,
                    "main_net_inflow": Decimal(str(row["main_net_inflow"])) if row["main_net_inflow"] else None,
                    "main_net_pct": Decimal(str(row["main_net_pct"])) if row["main_net_pct"] else None,
                    "super_large_net": Decimal(str(row["super_large_net"])) if row["super_large_net"] else None,
                    "large_net": Decimal(str(row["large_net"])) if row["large_net"] else None,
                    "medium_net": Decimal(str(row["medium_net"])) if row["medium_net"] else None,
                    "small_net": Decimal(str(row["small_net"])) if row["small_net"] else None,
                })

            # 存储
            async with get_db_session() as session:
                repo = StockFundFlowRepository(session)
                count = await repo.upsert_many(records)

            logger.info("资金流向同步完成", count=count)
            return {"status": "success", "synced": count}

        except Exception as e:
            logger.error("资金流向同步失败", error=str(e))
            raise

    async def sync_dragon_tiger(self, trade_date: date) -> dict:
        """
        同步龙虎榜数据

        Args:
            trade_date: 交易日期
        """
        logger.info("开始同步龙虎榜", trade_date=str(trade_date))

        try:
            # 获取龙虎榜数据
            df = await capital_flow_adapter.get_dragon_tiger(trade_date)

            if len(df) == 0:
                logger.warning("未获取到龙虎榜数据")
                return {"status": "no_data", "synced": 0}

            # 转换为记录
            records = []
            for row in df.iter_rows(named=True):
                records.append({
                    "code": row["code"],
                    "name": row["name"],
                    "trade_date": row["trade_date"],
                    "reason": row["reason"],
                    "buy_amount": Decimal(str(row["buy_amount"])) if row["buy_amount"] else None,
                    "sell_amount": Decimal(str(row["sell_amount"])) if row["sell_amount"] else None,
                    "net_amount": Decimal(str(row["net_amount"])) if row["net_amount"] else None,
                    "close": Decimal(str(row["close"])) if row["close"] else None,
                    "change_pct": Decimal(str(row["change_pct"])) if row["change_pct"] else None,
                    "turnover_rate": Decimal(str(row["turnover_rate"])) if row["turnover_rate"] else None,
                })

            # 存储
            async with get_db_session() as session:
                repo = DragonTigerRepository(session)
                count = await repo.upsert_many(records)

            logger.info("龙虎榜同步完成", count=count)
            return {"status": "success", "synced": count}

        except Exception as e:
            logger.error("龙虎榜同步失败", error=str(e))
            raise

    async def sync_margin_trade(self, trade_date: date) -> dict:
        """
        同步两融数据

        Args:
            trade_date: 交易日期
        """
        logger.info("开始同步两融数据", trade_date=str(trade_date))

        try:
            # 获取沪市和深市数据
            sse_df = await capital_flow_adapter.get_margin_trade_sse(trade_date)
            szse_df = await capital_flow_adapter.get_margin_trade_szse(trade_date)

            # 合并数据
            records = []

            # 处理沪市（沪市只有融券余量，没有融券余额）
            if len(sse_df) > 0:
                for row in sse_df.iter_rows(named=True):
                    records.append({
                        "code": row.get("code"),
                        "trade_date": trade_date,
                        "rzye": Decimal(str(row.get("rzye", 0) or 0)),
                        "rzmre": Decimal(str(row.get("rzmre", 0) or 0)),
                        "rqyl": row.get("rqyl"),  # 融券余量
                        "rqmcl": row.get("rqmcl"),
                    })

            # 处理深市
            if len(szse_df) > 0:
                for row in szse_df.iter_rows(named=True):
                    records.append({
                        "code": row.get("code"),
                        "trade_date": trade_date,
                        "rzye": Decimal(str(row.get("rzye", 0) or 0)),
                        "rzmre": Decimal(str(row.get("rzmre", 0) or 0)),
                        "rqye": Decimal(str(row.get("rqye", 0) or 0)),
                        "rqmcl": row.get("rqmcl"),
                    })

            if not records:
                logger.warning("未获取到两融数据")
                return {"status": "no_data", "synced": 0}

            # 存储
            async with get_db_session() as session:
                repo = MarginTradeRepository(session)
                count = await repo.upsert_many(records)

            logger.info("两融数据同步完成", count=count)
            return {"status": "success", "synced": count}

        except Exception as e:
            logger.error("两融数据同步失败", error=str(e))
            raise


# 全局单例
capital_flow_syncer = CapitalFlowSyncer()
