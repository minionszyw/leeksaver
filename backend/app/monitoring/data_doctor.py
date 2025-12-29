"""
数据医生 - 数据健康巡检系统

功能：
- 每日自动巡检数据覆盖率 (Stock & ETF)、新鲜度、完整性、质量
- 精准定位缺失数据的标的代码
- 触发针对性的自动修复任务
- 生成详细巡检报告
"""

from datetime import date, timedelta, datetime
from dataclasses import dataclass
from typing import List, Dict, Set

from sqlalchemy import select, func, and_, distinct

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.models.stock import Stock
from app.models.market_data import DailyQuote
from app.repositories.stock_repository import StockRepository

logger = get_logger(__name__)


@dataclass
class HealthCheckResult:
    """巡检结果"""

    metric_name: str
    status: str  # "healthy" | "warning" | "critical"
    value: float
    threshold: float
    message: str
    details: dict | None = None


class DataDoctor:
    """数据健康巡检系统"""

    def __init__(self):
        self.results: List[HealthCheckResult] = []
        self.missing_codes: Dict[str, List[str]] = {"stock": [], "etf": []}

    async def run_daily_health_check(self) -> List[HealthCheckResult]:
        """
        执行每日数据健康检查
        """
        logger.info("=" * 60)
        logger.info("开始数据健康巡检 (智能版)")
        logger.info("=" * 60)

        self.results = []
        self.missing_codes = {"stock": [], "etf": []}

        # 1. 检查日线行情覆盖率 (分别针对股票和 ETF)
        await self._check_quote_coverage("stock")
        await self._check_quote_coverage("etf")

        # 2. 检查数据新鲜度
        await self._check_data_freshness()

        # 3. 检查元数据完整性
        await self._check_metadata_completeness()

        # 4. 检查数据质量
        await self._check_data_quality()

        # 生成报告
        self._generate_report()

        # 5. 精准自动修复
        await self._auto_repair_smart()

        logger.info("=" * 60)
        logger.info("数据健康巡检完成")
        logger.info("=" * 60)

        return self.results

    async def _check_quote_coverage(self, asset_type: str) -> HealthCheckResult:
        """
        检查指定类型的日线行情覆盖率，并记录缺失的代码
        """
        logger.info(f"巡检: {asset_type.upper()} 行情覆盖率")

        try:
            async with get_db_session() as session:
                # 获取该类型的所有活跃代码
                all_codes_stmt = select(Stock.code).where(
                    and_(Stock.asset_type == asset_type, Stock.is_active == True)
                )
                all_codes_result = await session.execute(all_codes_stmt)
                all_codes = {row[0] for row in all_codes_result.fetchall()}
                total_count = len(all_codes)

                if total_count == 0:
                    return self._add_result(
                        f"{asset_type}_coverage", "healthy", 1.0, 0.95, f"✅ 无活跃 {asset_type} 标的"
                    )

                # 确定最近交易日
                check_date = self._get_latest_check_date()

                # 获取该交易日有数据的代码
                synced_stmt = select(DailyQuote.code).where(
                    and_(DailyQuote.trade_date == check_date, DailyQuote.code.in_(list(all_codes)))
                )
                synced_result = await session.execute(synced_stmt)
                synced_codes = {row[0] for row in synced_result.fetchall()}
                synced_count = len(synced_codes)

                # 找出缺失的代码
                missing = list(all_codes - synced_codes)
                self.missing_codes[asset_type] = missing

                coverage = synced_count / total_count if total_count > 0 else 0
                
                status = "healthy" if coverage >= 0.95 else ("warning" if coverage >= 0.8 else "critical")
                icon = "✅" if status == "healthy" else ("⚠️" if status == "warning" else "❌")

                return self._add_result(
                    f"{asset_type}_coverage",
                    status,
                    coverage,
                    0.95,
                    f"{icon} {asset_type.upper()} 覆盖率: {coverage*100:.1f}% ({synced_count}/{total_count})",
                    {"missing_count": len(missing), "check_date": str(check_date)}
                )

        except Exception as e:
            logger.error(f"检查 {asset_type} 覆盖率失败: {e}")
            return self._add_result(f"{asset_type}_coverage", "critical", 0, 0.95, f"❌ 检查失败: {e}")

    def _get_latest_check_date(self) -> date:
        """获取最近一个应该有数据的交易日"""
        target = date.today() - timedelta(days=1)
        # 简单跳过周末，节假日逻辑未来可接入交易日历
        while target.weekday() >= 5:
            target -= timedelta(days=1)
        return target

    def _add_result(self, name, status, value, threshold, message, details=None):
        res = HealthCheckResult(name, status, value, threshold, message, details)
        self.results.append(res)
        logger.info(message)
        return res

    async def _check_data_freshness(self) -> HealthCheckResult:
        """
        检查数据新鲜度
        """
        try:
            async with get_db_session() as session:
                latest_result = await session.execute(select(func.max(DailyQuote.trade_date)))
                latest_date = latest_result.scalar()

                if not latest_date:
                    return self._add_result("freshness", "critical", 0, 1, "❌ 数据库无任何行情数据")

                days_diff = (date.today() - latest_date).days
                max_allowed = 3 if date.today().weekday() == 0 else 1 # 周一允许3天，平时允许1天

                status = "healthy" if days_diff <= max_allowed else "critical"
                icon = "✅" if status == "healthy" else "❌"
                
                return self._add_result(
                    "freshness", status, float(days_diff), float(max_allowed),
                    f"{icon} 数据新鲜度: 最新日期 {latest_date} (距今 {days_diff} 天)"
                )
        except Exception as e:
            return self._add_result("freshness", "critical", 99, 1, f"❌ 检查新鲜度失败: {e}")

    async def _check_metadata_completeness(self) -> HealthCheckResult:
        """
        检查行业元数据完整性
        """
        try:
            async with get_db_session() as session:
                total = (await session.execute(select(func.count(Stock.code)).where(Stock.is_active == True))).scalar() or 0
                with_industry = (await session.execute(select(func.count(Stock.code)).where(
                    and_(Stock.is_active == True, Stock.industry.isnot(None), Stock.industry != "")
                ))).scalar() or 0

                ratio = with_industry / total if total > 0 else 1
                status = "healthy" if ratio >= 0.9 else "warning"
                
                return self._add_result(
                    "metadata", status, ratio, 0.9,
                    f"{'✅' if status == 'healthy' else '⚠️'} 元数据完整性: 行业覆盖率 {ratio*100:.1f}%"
                )
        except Exception as e:
            return self._add_result("metadata", "critical", 0, 0.9, f"❌ 检查元数据失败: {e}")

    async def _check_data_quality(self) -> HealthCheckResult:
        """检查最近数据是否有 0 值或空值"""
        try:
            async with get_db_session() as session:
                check_date = date.today() - timedelta(days=3)
                abnormal = (await session.execute(select(func.count(DailyQuote.code)).where(
                    and_(DailyQuote.trade_date >= check_date, (DailyQuote.close <= 0) | (DailyQuote.volume <= 0))
                ))).scalar() or 0
                
                status = "healthy" if abnormal == 0 else "warning"
                return self._add_result(
                    "quality", status, float(abnormal), 0,
                    f"{'✅' if status == 'healthy' else '⚠️'} 数据质量: 发现 {abnormal} 条异常记录 (最近3天)"
                )
        except Exception as e:
            return self._add_result("quality", "critical", 1, 0, f"❌ 检查质量失败: {e}")

    def _generate_report(self):
        """打印巡检总结报告"""
        logger.info("\n" + "="*40 + "\n📊 数据健康巡检总结报告\n" + "="*40)
        for r in self.results:
            logger.info(f"[{r.status.upper():<8}] {r.message}")
        logger.info("="*40)

    async def _auto_repair_smart(self):
        """
        智能自动修复：精准补录缺失代码
        """
        all_missing = self.missing_codes["stock"] + self.missing_codes["etf"]
        
        if not all_missing:
            logger.info("✅ 巡检通过，无需执行智能修复")
            return

        logger.info(f"🔧 启动智能修复: 发现 {len(all_missing)} 只标的数据缺失")
        
        try:
            from app.tasks.sync_tasks import sync_daily_quotes
            
            # 使用分片任务进行精准补录
            # 每 100 只一组，利用我们之前增强的 sync_daily_quotes 逻辑
            chunk_size = 100
            for i in range(0, len(all_missing), chunk_size):
                chunk = all_missing[i : i + chunk_size]
                sync_daily_quotes.delay(codes=chunk, is_chunk=True)
            
            logger.info(f"🚀 已下发 {len(all_missing)} 只标的的补录任务 (共 { (len(all_missing)//chunk_size) + 1 } 个分片)")
        except Exception as e:
            logger.error(f"❌ 智能修复任务下发失败: {e}")


# 全局单例
data_doctor = DataDoctor()
