"""
数据医生 - 数据健康巡检系统 (Ultra 闭环版)

集成：全量分诊 -> RCA 溯源 -> 熔断保护 -> 物理清理 -> 智能自愈。
"""

from datetime import date, timedelta, datetime
from dataclasses import dataclass
from typing import List, Dict, Set, Any

from sqlalchemy import select, func, and_, distinct, text, delete

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.models.stock import Stock
from app.models.market_data import DailyQuote
from app.models.calendar import TradingCalendar
from app.models.sync_error import SyncError

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
        self.stubborn_codes: Set[str] = set() # 顽疾标的 (多次修复失败)

    async def run_daily_health_check(self) -> List[HealthCheckResult]:
        """
        执行全量数据质量巡检与自动修复闭环
        """
        logger.info("=" * 60)
        logger.info("🚀 启动 Data Doctor Ultra 深度巡检")
        logger.info("=" * 60)

        self.results = []
        self.missing_codes = set()
        self.corrupted_codes = set()
        self.stubborn_codes = set()

        async with get_db_session() as session:
            # 0. 确定待检查日期
            check_date = await self._get_latest_check_date(session)
            logger.info(f"巡检目标日期: {check_date}")

            # 1. 分诊：检查覆盖率
            await self._check_quote_coverage("stock", check_date, session)
            await self._check_quote_coverage("etf", check_date, session)

            # 2. 分诊：深度逻辑体检 (K线、量纲、泄露)
            await self._check_deep_logic(check_date, session)

            # 3. 溯源与熔断：剔除无法自动修复的“顽疾”
            await self._root_cause_analysis(session)

            # 4. 其它指标监控
            await self._check_data_freshness(session)
            await self._check_metadata_completeness(session)

            # 5. 物理清理：清理无法通过重同步覆盖的脏数据 (如停牌泄露)
            await self._purge_polluted_data(check_date, session)
            await session.commit()

        # 生成报告
        self._generate_report()

        # 5. 执行自愈修复 (补录)
        await self._auto_repair_smart()

        # 6. [新增] 发送报警邮件 (如果有异常)
        try:
            from app.utils.alert_service import alert_service
            alert_service.send_dqa_report(self.results, self.stubborn_codes)
        except Exception as e:
            logger.error(f"发送报警邮件失败: {e}")

        logger.info("=" * 60)
        logger.info("Ultra 巡检任务执行完毕")
        logger.info("=" * 60)

        return self.results

    async def _root_cause_analysis(self, session):
        """溯源：识别多次尝试后依然失败的代码，执行熔断"""
        all_bad = self.missing_codes | self.corrupted_codes
        if not all_bad: return

        # 查询 sync_errors 表，看这些代码最近 24 小时是否已失败过 >= 3 次
        stubborn_stmt = text("""
            SELECT target_code FROM sync_errors 
            WHERE created_at > NOW() - INTERVAL '24 hours'
              AND retry_count >= 3
              AND target_code = ANY(:codes)
        """)
        
        result = await session.execute(stubborn_stmt, {"codes": list(all_bad)})
        self.stubborn_codes = {row[0] for row in result.fetchall()}
        
        if self.stubborn_codes:
            # 从修复名单中剔除
            self.missing_codes -= self.stubborn_codes
            self.corrupted_codes -= self.stubborn_codes
            
            logger.warning(f"🚫 熔断保护: 发现 {len(self.stubborn_codes)} 只‘顽疾’标的(多次修复失败)，已拦截自动化任务。")
            
            self._add_result(
                "circuit_breaker", "critical", float(len(self.stubborn_codes)), 0,
                f"❌ 熔断拦截: {len(self.stubborn_codes)} 只标的需人工介入排查上游",
                {"stubborn_list": list(self.stubborn_codes)[:10]}
            )

    async def _purge_polluted_data(self, check_date: date, session):
        """物理清理：删除那些无法通过重抓修复的泄露数据"""
        # 识别不活跃但有行情的数据
        leak_stmt = text(f"""
            SELECT q.code FROM daily_quotes q
            JOIN stocks s ON q.code = s.code
            WHERE q.trade_date = '{check_date}' AND s.is_active = False
        """)
        leak_codes = {row[0] for row in (await session.execute(leak_stmt)).fetchall()}
        
        if leak_codes:
            del_stmt = delete(DailyQuote).where(
                and_(DailyQuote.trade_date == check_date, DailyQuote.code.in_(list(leak_codes)))
            )
            await session.execute(del_stmt)
            logger.info(f"🧹 物理清理: 已从行情表中剔除 {len(leak_codes)} 条停牌股泄露数据")

    async def _get_latest_check_date(self, session) -> date:
        """从数据库日历获取最近一个应有数据的开市日"""
        stmt = select(func.max(TradingCalendar.trade_date)).where(
            and_(TradingCalendar.is_open == True, TradingCalendar.trade_date < date.today())
        )
        result = await session.execute(stmt)
        latest_date = result.scalar()
        if not latest_date:
            target = date.today() - timedelta(days=1)
            while target.weekday() >= 5: target -= timedelta(days=1)
            return target
        return latest_date

    async def _check_quote_coverage(self, asset_type: str, check_date: date, session):
        """检查行情覆盖率，记录缺失代码"""
        all_codes_stmt = select(Stock.code).where(
            and_(Stock.asset_type == asset_type, Stock.is_active == True)
        )
        all_codes = {row[0] for row in (await session.execute(all_codes_stmt)).fetchall()}
        total_count = len(all_codes)
        if total_count == 0: return

        synced_stmt = select(DailyQuote.code).where(
            and_(DailyQuote.trade_date == check_date, DailyQuote.code.in_(list(all_codes)))
        )
        synced_codes = {row[0] for row in (await session.execute(synced_stmt)).fetchall()}
        
        missing = all_codes - synced_codes
        self.missing_codes.update(missing)

        coverage = len(synced_codes) / total_count
        status = "healthy" if coverage >= 0.98 else ("warning" if coverage >= 0.9 else "critical")
        self._add_result(
            f"{asset_type}_coverage", status, coverage, 0.95,
            f"{'✅' if status == 'healthy' else '❌'} {asset_type.upper()} 覆盖率: {coverage*100:.1f}% ({len(synced_codes)}/{total_count})"
        )

    async def _check_deep_logic(self, check_date: date, session):
        """深度 SQL 逻辑校验 (全量下推)"""
        # 1. 基础异常值
        basic_stmt = select(DailyQuote.code).where(
            and_(DailyQuote.trade_date == check_date, (DailyQuote.close <= 0) | (DailyQuote.volume < 0))
        )
        basic_err = {row[0] for row in (await session.execute(basic_stmt)).fetchall()}

        # 2. K线逻辑冲突
        kline_stmt = text(f"""
            SELECT code FROM daily_quotes 
            WHERE trade_date = '{check_date}' 
              AND (high < low OR close > high OR open > high OR low > open OR low > close)
        """)
        kline_err = {row[0] for row in (await session.execute(kline_stmt)).fetchall()}

        # 3. 量价量纲错配 (100倍偏移)
        dimension_stmt = text(f"""
            SELECT code FROM daily_quotes 
            WHERE trade_date = '{check_date}' AND volume > 0 AND amount > 0 
              AND (amount/volume < low * 0.8 OR amount/volume > high * 1.2)
        """)
        dim_err = {row[0] for row in (await session.execute(dimension_stmt)).fetchall()}

        # 4. 停牌泄露
        leak_stmt = text(f"""
            SELECT q.code FROM daily_quotes q
            JOIN stocks s ON q.code = s.code
            WHERE q.trade_date = '{check_date}' AND s.is_active = False
        """)
        leak_err = {row[0] for row in (await session.execute(leak_stmt)).fetchall()}

        self.corrupted_codes.update(basic_err | kline_err | dim_err | leak_err)
        total_err = len(self.corrupted_codes)
        status = "healthy" if total_err == 0 else "warning"
        
        self._add_result(
            "quality_logic", status, float(total_err), 0,
            f"{'✅' if status == 'healthy' else '⚠️'} 数据逻辑质量: 发现 {total_err} 条逻辑错误"
        )

    async def _check_data_freshness(self, session):
        latest_date = (await session.execute(select(func.max(DailyQuote.trade_date)))).scalar()
        target_date = await self._get_latest_check_date(session)
        if not latest_date: return
        days_diff = (target_date - latest_date).days
        status = "healthy" if latest_date >= target_date else "critical"
        self._add_result("freshness", status, float(days_diff), 0, f"{'✅' if status == 'healthy' else '❌'} 数据新鲜度: 最新日期 {latest_date}")

    async def _check_metadata_completeness(self, session):
        total = (await session.execute(select(func.count(Stock.code)).where(Stock.is_active == True))).scalar() or 0
        with_industry = (await session.execute(select(func.count(Stock.code)).where(
            and_(Stock.is_active == True, Stock.industry.isnot(None), Stock.industry != "")
        ))).scalar() or 0
        ratio = with_industry / total if total > 0 else 1
        self._add_result("metadata", "healthy" if ratio >= 0.9 else "warning", ratio, 0.9, f"元数据行业覆盖率 {ratio*100:.1f}%")

    def _add_result(self, name, status, value, threshold, message, details=None):
        res = HealthCheckResult(name, status, value, threshold, message, details)
        self.results.append(res)
        logger.info(message)
        return res

    def _generate_report(self):
        logger.info("\n" + "="*40 + "\n📊 Data Doctor Ultra 巡检报告\n" + "="*40)
        for r in self.results:
            logger.info(f"[{r.status.upper():<8}] {r.message}")
        logger.info("="*40)

    async def _auto_repair_smart(self):
        """智能自愈：下发补录任务"""
        all_to_fix = list(self.missing_codes | self.corrupted_codes)
        if not all_to_fix: return
        logger.info(f"🔧 启动自愈修复: 待修复标的 {len(all_to_fix)} 只")
        try:
            from app.tasks.sync_tasks import sync_daily_quotes
            chunk_size = 100
            for i in range(0, len(all_to_fix), chunk_size):
                chunk = all_to_fix[i : i + chunk_size]
                sync_daily_quotes.delay(codes=chunk, is_chunk=True)
            logger.info(f"🚀 已下发 {len(all_to_fix)} 只标的的自愈分片任务")
        except Exception as e:
            logger.error(f"❌ 自愈任务下发失败: {e}")


# 运行入口
async def run_dqa():
    doctor = DataDoctor()
    return await doctor.run_daily_health_check()

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_dqa())
