"""
宏观经济数据同步器
"""

import asyncio
from typing import Dict, Any

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.datasources.macro_adapter import macro_adapter
from app.repositories.macro_repository import MacroIndicatorRepository

logger = get_logger(__name__)


class MacroSyncer:
    """宏观经济数据同步器"""

    async def sync_all(self) -> Dict[str, Any]:
        """
        同步所有宏观经济指标
        """
        logger.info("开始同步宏观经济数据")
        results = {}

        # 1. GDP
        try:
            df = await macro_adapter.get_gdp_data()
            count = await self._save_data(df)
            results["gdp"] = count
        except Exception as e:
            logger.error("同步 GDP 失败", error=str(e))
            results["gdp_error"] = str(e)

        # 2. PMI
        try:
            df = await macro_adapter.get_pmi_data()
            count = await self._save_data(df)
            results["pmi"] = count
        except Exception as e:
            logger.error("同步 PMI 失败", error=str(e))
            results["pmi_error"] = str(e)

        # 3. CPI
        try:
            df = await macro_adapter.get_cpi_data()
            count = await self._save_data(df)
            results["cpi"] = count
        except Exception as e:
            logger.error("同步 CPI 失败", error=str(e))
            results["cpi_error"] = str(e)

        # 4. PPI
        try:
            df = await macro_adapter.get_ppi_data()
            count = await self._save_data(df)
            results["ppi"] = count
        except Exception as e:
            logger.error("同步 PPI 失败", error=str(e))
            results["ppi_error"] = str(e)

        # 5. 社融
        try:
            df = await macro_adapter.get_social_financing_data()
            count = await self._save_data(df)
            results["social_financing"] = count
        except Exception as e:
            logger.error("同步社融数据失败", error=str(e))
            results["social_financing_error"] = str(e)

        # 6. 货币供应
        try:
            df = await macro_adapter.get_money_supply_data()
            count = await self._save_data(df)
            results["money_supply"] = count
        except Exception as e:
            logger.error("同步货币供应数据失败", error=str(e))
            results["money_supply_error"] = str(e)

        # 7. SHIBOR (利率)
        try:
            df = await macro_adapter.get_shibor_data()
            count = await self._save_data(df)
            results["shibor"] = count
        except Exception as e:
            logger.error("同步 SHIBOR 失败", error=str(e))
            results["shibor_error"] = str(e)

        # 8. 国债收益率
        try:
            df = await macro_adapter.get_treasury_yield_data()
            count = await self._save_data(df)
            results["treasury"] = count
        except Exception as e:
            logger.error("同步国债收益率失败", error=str(e))
            results["treasury_error"] = str(e)

        # 9. 汇率
        try:
            df = await macro_adapter.get_exchange_rate_data()
            count = await self._save_data(df)
            results["exchange_rate"] = count
        except Exception as e:
            logger.error("同步汇率数据失败", error=str(e))
            results["exchange_rate_error"] = str(e)

        logger.info("宏观经济数据同步完成", **results)
        return results

    async def _save_data(self, df) -> int:
        """保存数据到数据库"""
        if df is None or len(df) == 0:
            return 0

        records = []
        for row in df.iter_rows(named=True):
            records.append({
                "indicator_name": row["indicator_name"],
                "indicator_category": row["indicator_category"],
                "period": row["period"],
                "period_type": row["period_type"],
                "value": row["value"],
                "yoy_rate": row["yoy_rate"],
                "unit": row["unit"],
            })

        async with get_db_session() as session:
            repo = MacroIndicatorRepository(session)
            count = await repo.upsert_many(records)
            return count


# 全局单例
macro_syncer = MacroSyncer()
