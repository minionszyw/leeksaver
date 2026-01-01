"""
数据医生 - 数据健康巡检系统 (Pro 增强版)

集成全量 SQL 深度逻辑校验与精准自动修复能力。
"""

from datetime import date, timedelta, datetime
from dataclasses import dataclass
from typing import List, Dict, Set, Any

from sqlalchemy import select, func, and_, distinct, text

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.models.stock import Stock
from app.models.market_data import DailyQuote
from app.models.calendar import TradingCalendar
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
        self.missing_codes: Set[str] = set()
        self.corrupted_codes: Set[str] = set()

    async def run_daily_health_check(self) -> List[HealthCheckResult]:
        """
        执行全量数据质量巡检 (DQA)
        """
        logger.info("=" * 60)
        logger.info("🚀 启动 Data Doctor Pro 深度巡检")
        logger.info("=" * 60)

        self.results = []
        self.missing_codes = set()
        self.corrupted_codes = set()

        async with get_db_session() as session:
            # 0. 确定待检查日期 (最新已过去交易日)
            check_date = await self._get_latest_check_date(session)
            logger.info(f"巡检目标日期: {check_date}")

            # 1. 检查日线行情覆盖率 (针对活跃 Stock & ETF)
            await self._check_quote_coverage("stock", check_date, session)
            await self._check_quote_coverage("etf", check_date, session)

            # 2. 检查数据新鲜度 (L1)
            await self._check_data_freshness(session)

            # 3. 深度逻辑体检 (K线、量纲、泄露)
            await self._check_deep_logic(check_date, session)

            # 4. 元数据完整性
            await self._check_metadata_completeness(session)

        # 生成报告
        self._generate_report()

        # 5. 执行自愈修复
        await self._auto_repair_smart()

        logger.info("=" * 60)
        logger.info("巡检完成")
        logger.info("=" * 60)

        return self.results

    async def _get_latest_check_date(self, session) -> date:
        """从数据库日历获取最近一个应有数据的开市日"""
        stmt = select(func.max(TradingCalendar.trade_date)).where(
            and_(TradingCalendar.is_open == True, TradingCalendar.trade_date < date.today())
        )
        result = await session.execute(stmt)
        latest_date = result.scalar()
        
        if not latest_date:
            # 兜底：如果日历表为空，按自然日回退
            target = date.today() - timedelta(days=1)
            while target.weekday() >= 5: target -= timedelta(days=1)
            return target
        return latest_date

    async def _check_quote_coverage(self, asset_type: str, check_date: date, session) -> HealthCheckResult:
        """检查行情覆盖率，记录缺失代码"""
        # 获取活跃标的
        all_codes_stmt = select(Stock.code).where(
            and_(Stock.asset_type == asset_type, Stock.is_active == True)
        )
        all_codes = {row[0] for row in (await session.execute(all_codes_stmt)).fetchall()}
        total_count = len(all_codes)

        if total_count == 0:
            return self._add_result(f"{asset_type}_coverage", "healthy", 1.0, 0.95, f"✅ 无活跃 {asset_type} 标的")

        # 获取已入库代码
        synced_stmt = select(DailyQuote.code).where(
            and_(DailyQuote.trade_date == check_date, DailyQuote.code.in_(list(all_codes)))
        )
        synced_codes = {row[0] for row in (await session.execute(synced_stmt)).fetchall()}
        
        # 记录缺失代码
        missing = all_codes - synced_codes
        self.missing_codes.update(missing)

        coverage = len(synced_codes) / total_count
        status = "healthy" if coverage >= 0.98 else ("warning" if coverage >= 0.9 else "critical")
        icon = "✅" if status == "healthy" else ("⚠️" if status == "warning" else "❌")

        return self._add_result(
            f"{asset_type}_coverage", status, coverage, 0.95,
            f"{icon} {asset_type.upper()} 覆盖率: {coverage*100:.1f}% ({len(synced_codes)}/{total_count})",
            {"missing": len(missing)}
        )

    async def _check_deep_logic(self, check_date: date, session) -> HealthCheckResult:
        """深度 SQL 逻辑校验 (全量下推)"""
        logger.info("深度质量体检: 执行全量逻辑勾稽校验...")
        
        # 1. 基础异常值 (价格<=0, 成交量<0)
        basic_stmt = select(DailyQuote.code).where(
            and_(DailyQuote.trade_date == check_date, 
                 (DailyQuote.close <= 0) | (DailyQuote.volume < 0))
        )
        basic_err_codes = {row[0] for row in (await session.execute(basic_stmt)).fetchall()}

        # 2. K线逻辑冲突
        kline_stmt = text(f"""
            SELECT code FROM daily_quotes 
            WHERE trade_date = '{check_date}' 
              AND (high < low OR close > high OR open > high OR low > open OR low > close)
        """)
        kline_err_codes = {row[0] for row in (await session.execute(kline_stmt)).fetchall()}

        # 3. 量价量纲错配 (100倍偏移)
        dimension_stmt = text(f"""
            SELECT code FROM daily_quotes 
            WHERE trade_date = '{check_date}' AND volume > 0 AND amount > 0 
              AND (amount/volume < low * 0.8 OR amount/volume > high * 1.2)
        """)
        dim_err_codes = {row[0] for row in (await session.execute(dimension_stmt)).fetchall()}

        # 4. 停牌泄露 (活跃标志 is_active=False 但产生了行情)
        leak_stmt = text(f"""
            SELECT q.code FROM daily_quotes q
            JOIN stocks s ON q.code = s.code
            WHERE q.trade_date = '{check_date}' AND s.is_active = False
        """)
        leak_err_codes = {row[0] for row in (await session.execute(leak_stmt)).fetchall()}

        # 5. [新增] 财务勾稽异常 (全量扫描)
        fin_stmt = text("SELECT count(*) FROM financial_statements WHERE total_revenue > 0 AND (net_profit / total_revenue > 5.0)")
        fin_err_count = (await session.execute(fin_stmt)).scalar() or 0

        # 6. [新增] Embedding 异常 (全量扫描)
        emb_stmt = text("SELECT count(*) FROM news_articles WHERE embedding IS NOT NULL AND vector_dims(embedding) != 1024")
        emb_err_count = (await session.execute(emb_stmt)).scalar() or 0

        # 汇总需要自愈修复的标的代码 (仅针对行情类)
        self.corrupted_codes.update(basic_err_codes | kline_err_codes | dim_err_codes | leak_err_codes)

        total_err = len(self.corrupted_codes) + fin_err_count + emb_err_count
        status = "healthy" if total_err == 0 else "warning"
        
        details = {
            "invalid_price_vol": len(basic_err_codes),
            "kline_logic_error": len(kline_err_codes),
            "dimension_mismatch": len(dim_err_codes),
            "inactive_leak": len(leak_err_codes),
            "financial_anomaly": fin_err_count,
            "embedding_dim_error": emb_err_count
        }

        return self._add_result(
            "quality_logic", status, float(total_err), 0,
            f"{'✅' if status == 'healthy' else '⚠️'} 数据逻辑质量: 发现 {total_err} 条逻辑错误",
            details
        )

    async def _check_data_freshness(self, session) -> HealthCheckResult:
        """检查行情新鲜度"""
        latest_date = (await session.execute(select(func.max(DailyQuote.trade_date)))).scalar()
        if not latest_date:
            return self._add_result("freshness", "critical", 0, 1, "❌ 数据库无任何行情数据")

        today = date.today()
        # 计算应更新到的日期
        target_date = await self._get_latest_check_date(session)
        days_diff = (target_date - latest_date).days

        status = "healthy" if latest_date >= target_date else "critical"
        icon = "✅" if status == "healthy" else "❌"
        
        return self._add_result(
            "freshness", status, float(days_diff), 0,
            f"{icon} 数据新鲜度: 最新日期 {latest_date} (期待日期 {target_date})",
            {"delay_days": days_diff}
        )

    async def _check_metadata_completeness(self, session) -> HealthCheckResult:
        """检查元数据完整性 (行业字段)"""
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

    def _add_result(self, name, status, value, threshold, message, details=None):
        res = HealthCheckResult(name, status, value, threshold, message, details)
        self.results.append(res)
        logger.info(message)
        return res

    def _generate_report(self):
        """打印巡检总结报告"""
        logger.info("\n" + "="*40 + "\n📊 数据健康巡检总结报告\n" + "="*40)
        for r in self.results:
            logger.info(f"[{r.status.upper():<8}] {r.message}")
        logger.info("="*40)

    async def _auto_repair_smart(self):
        """智能自愈：针对缺失和损坏的代码重新同步数据"""
        all_to_fix = list(self.missing_codes | self.corrupted_codes)
        
        if not all_to_fix:
            logger.info("✅ 巡检通过，无需执行修复")
            return

        logger.info(f"🔧 启动自愈修复: 待修复标的 {len(all_to_fix)} 只 (缺失: {len(self.missing_codes)}, 损坏: {len(self.corrupted_codes)})")
        
        try:
            from app.tasks.sync_tasks import sync_daily_quotes
            chunk_size = 100
            for i in range(0, len(all_to_fix), chunk_size):
                chunk = all_to_fix[i : i + chunk_size]
                sync_daily_quotes.delay(codes=chunk, is_chunk=True)
            logger.info(f"🚀 已下发分片自愈任务，总计 {len(all_to_fix)} 只标的")
        except Exception as e:
            logger.error(f"❌ 自愈任务下发失败: {e}")


# 全量 DQA 巡检入口
async def run_dqa():
    doctor = DataDoctor()
    return await doctor.run_daily_health_check()


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_dqa())
