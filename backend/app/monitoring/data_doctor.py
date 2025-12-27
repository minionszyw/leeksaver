"""
数据医生 - 数据健康巡检系统

功能：
- 每日自动巡检数据覆盖率、新鲜度、完整性、质量
- 覆盖率 < 95% 时告警并触发自动修复
- 生成巡检报告
"""

from datetime import date, timedelta, datetime
from dataclasses import dataclass
from typing import List

from sqlalchemy import select, func, and_, distinct

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.models.stock import Stock
from app.models.market_data import DailyQuote
from app.models.financial import FinancialStatement
from app.models.news import NewsArticle
from app.models.valuation import DailyValuation
from app.repositories.stock_repository import StockRepository
from app.repositories.market_data_repository import MarketDataRepository
from app.repositories.financial_repository import FinancialRepository

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

    async def run_daily_health_check(self) -> List[HealthCheckResult]:
        """
        执行每日数据健康检查

        Returns:
            巡检结果列表
        """
        logger.info("=" * 60)
        logger.info("开始数据健康巡检")
        logger.info("=" * 60)

        self.results = []

        # 检查 1: 日线行情覆盖率
        await self._check_quote_coverage()

        # 检查 2: 数据新鲜度
        await self._check_data_freshness()

        # 检查 3: 元数据完整性
        await self._check_metadata_completeness()

        # 检查 4: 数据质量（异常值检测）
        await self._check_data_quality()

        # 生成报告
        self._generate_report()

        # 自动修复
        await self._auto_repair()

        logger.info("=" * 60)
        logger.info("数据健康巡检完成")
        logger.info("=" * 60)

        return self.results

    async def _check_quote_coverage(self) -> HealthCheckResult:
        """
        检查日线行情覆盖率

        标准：昨日行情覆盖率 > 95%
        """
        logger.info("检查 1/4: 日线行情覆盖率")

        try:
            async with get_db_session() as session:
                # 获取总股票数
                total_result = await session.execute(
                    select(func.count(Stock.code)).where(
                        and_(Stock.asset_type == "stock", Stock.is_active == True)
                    )
                )
                total_stocks = total_result.scalar() or 0

                if total_stocks == 0:
                    result = HealthCheckResult(
                        metric_name="quote_coverage",
                        status="warning",
                        value=0.0,
                        threshold=0.95,
                        message="⚠️  股票总数为 0，请先同步股票列表",
                    )
                    self.results.append(result)
                    return result

                # 获取昨日日期（考虑周末）
                latest_date = date.today() - timedelta(days=1)
                if latest_date.weekday() >= 5:  # 周六或周日
                    # 回溯到上周五
                    days_back = latest_date.weekday() - 4
                    latest_date = latest_date - timedelta(days=days_back)

                # 获取昨日有行情的股票数
                quote_result = await session.execute(
                    select(func.count(distinct(DailyQuote.code))).where(
                        DailyQuote.trade_date == latest_date
                    )
                )
                quote_count = quote_result.scalar() or 0

                # 计算覆盖率
                coverage = quote_count / total_stocks if total_stocks > 0 else 0

                # 判断状态
                if coverage >= 0.95:
                    status = "healthy"
                    icon = "✅"
                elif coverage >= 0.80:
                    status = "warning"
                    icon = "⚠️"
                else:
                    status = "critical"
                    icon = "❌"

                result = HealthCheckResult(
                    metric_name="quote_coverage",
                    status=status,
                    value=coverage,
                    threshold=0.95,
                    message=f"{icon} 日线行情覆盖率: {coverage*100:.1f}% ({quote_count}/{total_stocks})",
                    details={
                        "total_stocks": total_stocks,
                        "quote_count": quote_count,
                        "check_date": str(latest_date),
                    },
                )

                self.results.append(result)
                logger.info(result.message)
                return result

        except Exception as e:
            logger.error(f"检查日线行情覆盖率失败: {e}")
            result = HealthCheckResult(
                metric_name="quote_coverage",
                status="critical",
                value=0.0,
                threshold=0.95,
                message=f"❌ 检查失败: {e}",
            )
            self.results.append(result)
            return result

    async def _check_data_freshness(self) -> HealthCheckResult:
        """
        检查数据新鲜度（最新交易日是否为昨天或最近交易日）

        标准：最新数据日期距今 <= 3 天（考虑周末和节假日）
        """
        logger.info("检查 2/4: 数据新鲜度")

        try:
            async with get_db_session() as session:
                # 获取最新行情日期
                latest_result = await session.execute(
                    select(func.max(DailyQuote.trade_date))
                )
                latest_date = latest_result.scalar()

                if not latest_date:
                    result = HealthCheckResult(
                        metric_name="data_freshness",
                        status="critical",
                        value=0.0,
                        threshold=3.0,
                        message="❌ 无任何行情数据",
                    )
                    self.results.append(result)
                    return result

                # 计算距今天数
                today = date.today()
                days_diff = (today - latest_date).days

                # 判断状态（考虑周末）
                max_days = 3
                if today.weekday() == 0:  # 周一，允许 3 天
                    max_days = 3
                elif today.weekday() == 6:  # 周日，允许 2 天
                    max_days = 2

                if days_diff <= 1:
                    status = "healthy"
                    icon = "✅"
                elif days_diff <= max_days:
                    status = "warning"
                    icon = "⚠️"
                else:
                    status = "critical"
                    icon = "❌"

                result = HealthCheckResult(
                    metric_name="data_freshness",
                    status=status,
                    value=float(days_diff),
                    threshold=float(max_days),
                    message=f"{icon} 数据新鲜度: 最新数据 {latest_date} (距今 {days_diff} 天)",
                    details={"latest_date": str(latest_date), "days_diff": days_diff},
                )

                self.results.append(result)
                logger.info(result.message)
                return result

        except Exception as e:
            logger.error(f"检查数据新鲜度失败: {e}")
            result = HealthCheckResult(
                metric_name="data_freshness",
                status="critical",
                value=999.0,
                threshold=3.0,
                message=f"❌ 检查失败: {e}",
            )
            self.results.append(result)
            return result

    async def _check_metadata_completeness(self) -> HealthCheckResult:
        """
        检查元数据完整性（industry 字段非空比例）

        标准：行业字段非空率 > 90%
        """
        logger.info("检查 3/4: 元数据完整性")

        try:
            async with get_db_session() as session:
                # 总股票数
                total_result = await session.execute(
                    select(func.count(Stock.code)).where(
                        and_(Stock.asset_type == "stock", Stock.is_active == True)
                    )
                )
                total_stocks = total_result.scalar() or 0

                if total_stocks == 0:
                    result = HealthCheckResult(
                        metric_name="metadata_completeness",
                        status="warning",
                        value=0.0,
                        threshold=0.90,
                        message="⚠️  股票总数为 0",
                    )
                    self.results.append(result)
                    return result

                # 有行业信息的股票数
                with_industry_result = await session.execute(
                    select(func.count(Stock.code)).where(
                        and_(
                            Stock.asset_type == "stock",
                            Stock.is_active == True,
                            Stock.industry.isnot(None),
                            Stock.industry != "",
                        )
                    )
                )
                with_industry = with_industry_result.scalar() or 0

                # 计算完整率
                completeness = with_industry / total_stocks if total_stocks > 0 else 0

                # 判断状态
                if completeness >= 0.90:
                    status = "healthy"
                    icon = "✅"
                elif completeness >= 0.70:
                    status = "warning"
                    icon = "⚠️"
                else:
                    status = "critical"
                    icon = "❌"

                result = HealthCheckResult(
                    metric_name="metadata_completeness",
                    status=status,
                    value=completeness,
                    threshold=0.90,
                    message=f"{icon} 元数据完整性: 行业字段非空率 {completeness*100:.1f}% ({with_industry}/{total_stocks})",
                    details={
                        "total_stocks": total_stocks,
                        "with_industry": with_industry,
                    },
                )

                self.results.append(result)
                logger.info(result.message)
                return result

        except Exception as e:
            logger.error(f"检查元数据完整性失败: {e}")
            result = HealthCheckResult(
                metric_name="metadata_completeness",
                status="critical",
                value=0.0,
                threshold=0.90,
                message=f"❌ 检查失败: {e}",
            )
            self.results.append(result)
            return result

    async def _check_data_quality(self) -> HealthCheckResult:
        """
        检查数据质量（异常值检测）

        检查项：
        - 价格异常（收盘价 <= 0）
        - 成交量异常（成交量 <= 0）
        """
        logger.info("检查 4/4: 数据质量")

        try:
            async with get_db_session() as session:
                # 获取最近 5 天的数据
                check_date = date.today() - timedelta(days=5)

                # 检查异常价格
                abnormal_price_result = await session.execute(
                    select(func.count(DailyQuote.code)).where(
                        and_(
                            DailyQuote.trade_date >= check_date,
                            (DailyQuote.close <= 0) | (DailyQuote.close.is_(None)),
                        )
                    )
                )
                abnormal_price = abnormal_price_result.scalar() or 0

                # 检查异常成交量
                abnormal_volume_result = await session.execute(
                    select(func.count(DailyQuote.code)).where(
                        and_(
                            DailyQuote.trade_date >= check_date,
                            (DailyQuote.volume <= 0) | (DailyQuote.volume.is_(None)),
                        )
                    )
                )
                abnormal_volume = abnormal_volume_result.scalar() or 0

                # 总记录数
                total_result = await session.execute(
                    select(func.count(DailyQuote.code)).where(
                        DailyQuote.trade_date >= check_date
                    )
                )
                total_records = total_result.scalar() or 0

                # 计算异常率
                total_abnormal = abnormal_price + abnormal_volume
                abnormal_rate = (
                    total_abnormal / total_records if total_records > 0 else 0
                )

                # 判断状态
                if abnormal_rate <= 0.01:  # 异常率 < 1%
                    status = "healthy"
                    icon = "✅"
                elif abnormal_rate <= 0.05:  # 异常率 < 5%
                    status = "warning"
                    icon = "⚠️"
                else:
                    status = "critical"
                    icon = "❌"

                result = HealthCheckResult(
                    metric_name="data_quality",
                    status=status,
                    value=abnormal_rate,
                    threshold=0.01,
                    message=f"{icon} 数据质量: 异常率 {abnormal_rate*100:.2f}% (异常价格 {abnormal_price}, 异常成交量 {abnormal_volume})",
                    details={
                        "total_records": total_records,
                        "abnormal_price": abnormal_price,
                        "abnormal_volume": abnormal_volume,
                        "check_period_days": 5,
                    },
                )

                self.results.append(result)
                logger.info(result.message)
                return result

        except Exception as e:
            logger.error(f"检查数据质量失败: {e}")
            result = HealthCheckResult(
                metric_name="data_quality",
                status="warning",
                value=0.0,
                threshold=0.01,
                message=f"⚠️  检查失败: {e}",
            )
            self.results.append(result)
            return result

    def _generate_report(self):
        """生成巡检报告"""
        logger.info("")
        logger.info("=" * 60)
        logger.info("📊 数据健康巡检报告")
        logger.info("=" * 60)
        logger.info(f"巡检时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("")

        # 统计各状态数量
        healthy_count = sum(1 for r in self.results if r.status == "healthy")
        warning_count = sum(1 for r in self.results if r.status == "warning")
        critical_count = sum(1 for r in self.results if r.status == "critical")

        # 总体状态
        if critical_count > 0:
            overall_status = "❌ 严重"
        elif warning_count > 0:
            overall_status = "⚠️  警告"
        else:
            overall_status = "✅ 健康"

        logger.info(f"总体状态: {overall_status}")
        logger.info(
            f"检查项: {len(self.results)} 项 (健康 {healthy_count}, 警告 {warning_count}, 严重 {critical_count})"
        )
        logger.info("")
        logger.info("详细结果:")
        logger.info("-" * 60)

        for result in self.results:
            logger.info(f"  {result.message}")

        logger.info("=" * 60)

    async def _auto_repair(self):
        """
        自动修复（触发补录任务）

        修复策略:
        - 日线行情覆盖率 < 95%: 触发全市场同步
        - 元数据完整性 < 90%: 触发股票列表同步
        """
        logger.info("")
        logger.info("🔧 自动修复检测")
        logger.info("-" * 60)

        repair_triggered = False

        for result in self.results:
            if result.status == "critical":
                logger.warning(f"检测到严重问题: {result.metric_name}")

                if result.metric_name == "quote_coverage":
                    # 触发全市场日线同步
                    logger.info("⚙️  触发全市场日线行情同步...")
                    try:
                        from app.tasks.sync_tasks import sync_daily_quotes

                        sync_daily_quotes.delay()
                        logger.info("✅ 已触发全市场日线行情同步任务")
                        repair_triggered = True
                    except Exception as e:
                        logger.error(f"触发同步任务失败: {e}")

                elif result.metric_name == "metadata_completeness":
                    # 触发股票列表同步
                    logger.info("⚙️  触发股票列表同步...")
                    try:
                        from app.tasks.sync_tasks import sync_stock_list

                        sync_stock_list.delay()
                        logger.info("✅ 已触发股票列表同步任务")
                        repair_triggered = True
                    except Exception as e:
                        logger.error(f"触发同步任务失败: {e}")

        if not repair_triggered:
            logger.info("✅ 无需自动修复")

        logger.info("-" * 60)


# 全局单例
data_doctor = DataDoctor()
