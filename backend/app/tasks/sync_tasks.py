"""
数据同步 Celery 任务
"""

import asyncio

from celery import shared_task

from app.core.logging import get_logger

logger = get_logger(__name__)


def run_async(coro):
    """在 Celery 中运行异步函数"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@shared_task(bind=True, max_retries=3)
def sync_stock_list(self):
    """
    同步股票列表

    从 AkShare 获取全市场股票和 ETF 列表
    """
    from app.sync.stock_list_syncer import stock_list_syncer

    logger.info("开始同步股票列表")
    try:
        result = run_async(stock_list_syncer.sync())
        logger.info("股票列表同步完成", **result)
        return {"status": "success", **result}
    except Exception as e:
        logger.error("股票列表同步失败", error=str(e))
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def sync_daily_quotes(self, codes: list[str] | None = None):
    """
    同步日线行情数据 (L1)

    Args:
        codes: 股票代码列表, None 表示全市场
    """
    from app.sync.daily_quote_syncer import daily_quote_syncer

    scope = "全市场" if codes is None else f"{len(codes)} 只股票"
    logger.info("开始同步日线行情", scope=scope)

    try:
        if codes:
            result = run_async(daily_quote_syncer.sync_batch(codes))
        else:
            result = run_async(daily_quote_syncer.sync_all())

        logger.info("日线行情同步完成", scope=scope, **result)
        return {"status": "success", "scope": scope, **result}
    except Exception as e:
        logger.error("日线行情同步失败", error=str(e))
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def sync_watchlist_quotes(self):
    """
    同步自选股行情数据 (L2)
    """
    from app.sync.daily_quote_syncer import daily_quote_syncer

    logger.info("开始同步自选股行情")
    try:
        result = run_async(daily_quote_syncer.sync_watchlist())
        logger.info("自选股行情同步完成", **result)
        return {"status": "success", **result}
    except Exception as e:
        logger.error("自选股行情同步失败", error=str(e))
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def sync_single_stock(self, code: str):
    """
    按需同步单只股票数据 (L3)

    Args:
        code: 股票代码
    """
    from app.sync.daily_quote_syncer import daily_quote_syncer

    logger.info("开始按需同步股票", code=code)
    try:
        count = run_async(daily_quote_syncer.sync_single(code))
        logger.info("股票数据同步完成", code=code, records=count)
        return {"status": "success", "code": code, "records": count}
    except Exception as e:
        logger.error("股票数据同步失败", code=code, error=str(e))
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def sync_financial_statements(self):
    """
    同步全市场财务报表数据

    每周执行一次，获取最新的财务报表数据
    """
    from app.sync.financial_syncer import financial_syncer

    logger.info("开始同步财务报表")
    try:
        result = run_async(financial_syncer.sync_all())
        logger.info("财务报表同步完成", **result)
        return {"status": "success", **result}
    except Exception as e:
        logger.error("财务报表同步失败", error=str(e))
        # 失败后 5 分钟重试
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=3)
def sync_market_news(self):
    """
    同步全市场财经新闻

    每天执行 2 次（早 8:00 和晚 18:00）
    """
    from app.config import settings
    from app.sync.news_syncer import news_syncer

    logger.info("开始同步全市场新闻")
    try:
        result = run_async(news_syncer.sync_market_news(limit=settings.news_sync_market_limit))
        logger.info("全市场新闻同步完成", **result)
        return {"status": "success", **result}
    except Exception as e:
        logger.error("全市场新闻同步失败", error=str(e))
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=3)
def sync_watchlist_news(self):
    """
    同步自选股新闻

    优先同步用户自选股的相关新闻，如果没有自选股则降级为全市场新闻
    每天执行 2 次（早 8:05 和晚 18:05）
    """
    from app.config import settings
    from app.sync.news_syncer import news_syncer

    logger.info("开始同步自选股新闻")
    try:
        result = run_async(
            news_syncer.sync_watchlist_news(
                limit_per_stock=settings.news_sync_watchlist_limit_per_stock
            )
        )
        logger.info("自选股新闻同步完成", **result)
        return {"status": "success", **result}
    except Exception as e:
        logger.error("自选股新闻同步失败", error=str(e))
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=3)
def generate_news_embeddings(self):
    """
    为新闻生成文本向量

    每小时执行一次，为新入库的新闻生成向量
    """
    from app.config import settings
    from app.sync.news_syncer import news_syncer

    logger.info("开始生成新闻向量")
    try:
        result = run_async(news_syncer.generate_embeddings(batch_size=settings.embedding_batch_size))
        logger.info("新闻向量生成完成", **result)
        return {"status": "success", **result}
    except Exception as e:
        logger.error("新闻向量生成失败", error=str(e))
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=3)
def cleanup_old_news(self):
    """
    清理过期新闻数据

    策略：
    1. 删除超过保留期的新闻
    2. 保护自选股相关的新闻（如果配置启用）
    """
    from app.sync.news_cleaner import news_cleaner

    logger.info("开始清理过期新闻")
    try:
        result = run_async(news_cleaner.cleanup_old_news())
        logger.info("新闻清理完成", **result)
        return {"status": "success", **result}
    except Exception as e:
        logger.error("新闻清理失败", error=str(e))
        raise self.retry(exc=e, countdown=300)


# ==================== 资金面同步任务 ====================


@shared_task(bind=True, max_retries=3)
def sync_northbound_flow(self):
    """
    同步北向资金数据

    每日收盘后执行，获取北向资金净流入数据
    """
    from app.sync.capital_flow_syncer import capital_flow_syncer

    logger.info("开始同步北向资金")
    try:
        result = run_async(capital_flow_syncer.sync_northbound_flow())
        logger.info("北向资金同步完成", **result)
        return {"status": "success", **result}
    except Exception as e:
        logger.error("北向资金同步失败", error=str(e))
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=3)
def sync_stock_fund_flow(self):
    """
    同步个股资金流向数据

    每日收盘后执行，获取主力资金净流入排行
    """
    from datetime import date
    from app.sync.capital_flow_syncer import capital_flow_syncer

    logger.info("开始同步资金流向")
    try:
        result = run_async(capital_flow_syncer.sync_stock_fund_flow(date.today()))
        logger.info("资金流向同步完成", **result)
        return {"status": "success", **result}
    except Exception as e:
        logger.error("资金流向同步失败", error=str(e))
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=3)
def sync_dragon_tiger(self):
    """
    同步龙虎榜数据

    每日收盘后执行（通常在 18:00 后数据更完整）
    """
    from datetime import date
    from app.sync.capital_flow_syncer import capital_flow_syncer

    logger.info("开始同步龙虎榜")
    try:
        result = run_async(capital_flow_syncer.sync_dragon_tiger(date.today()))
        logger.info("龙虎榜同步完成", **result)
        return {"status": "success", **result}
    except Exception as e:
        logger.error("龙虎榜同步失败", error=str(e))
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=3)
def sync_margin_trade(self):
    """
    同步两融数据

    每日收盘后执行，获取融资融券余额
    """
    from datetime import date
    from app.sync.capital_flow_syncer import capital_flow_syncer

    logger.info("开始同步两融数据")
    try:
        result = run_async(capital_flow_syncer.sync_margin_trade(date.today()))
        logger.info("两融数据同步完成", **result)
        return {"status": "success", **result}
    except Exception as e:
        logger.error("两融数据同步失败", error=str(e))
        raise self.retry(exc=e, countdown=300)


# ==================== 情绪面同步任务 ====================


@shared_task(bind=True, max_retries=3)
def sync_market_sentiment(self):
    """
    同步市场情绪数据

    每日收盘后执行，计算涨跌统计、连板情况等
    """
    from datetime import date
    from app.sync.sentiment_syncer import sentiment_syncer

    logger.info("开始同步市场情绪")
    try:
        # 同步涨停池
        limit_up_result = run_async(sentiment_syncer.sync_limit_up_pool(date.today()))
        # 同步市场情绪指标
        sentiment_result = run_async(sentiment_syncer.sync_market_sentiment(date.today()))

        logger.info("市场情绪同步完成", limit_up=limit_up_result, sentiment=sentiment_result)
        return {
            "status": "success",
            "limit_up": limit_up_result,
            "sentiment": sentiment_result,
        }
    except Exception as e:
        logger.error("市场情绪同步失败", error=str(e))
        raise self.retry(exc=e, countdown=300)


# ==================== 估值同步任务 ====================


@shared_task(bind=True, max_retries=3)
def sync_daily_valuation(self):
    """
    同步每日估值数据

    每日收盘后执行，获取全市场 PE/PB/市值等
    """
    from datetime import date
    from app.sync.valuation_syncer import valuation_syncer

    logger.info("开始同步估值数据")
    try:
        result = run_async(valuation_syncer.sync_all(date.today()))
        logger.info("估值数据同步完成", **result)
        return {"status": "success", **result}
    except Exception as e:
        logger.error("估值数据同步失败", error=str(e))
        raise self.retry(exc=e, countdown=300)


# ==================== 技术指标任务 ====================


@shared_task(bind=True, max_retries=3)
def calculate_tech_indicators(self):
    """
    计算全市场技术指标

    每日收盘后执行，计算 MA/MACD/RSI/KDJ 等指标
    """
    from datetime import date
    from app.sync.tech_indicator_syncer import tech_indicator_syncer

    logger.info("开始计算技术指标")
    try:
        result = run_async(tech_indicator_syncer.calculate_all(date.today()))
        logger.info("技术指标计算完成", **result)
        return {"status": "success", **result}
    except Exception as e:
        logger.error("技术指标计算失败", error=str(e))
        raise self.retry(exc=e, countdown=300)


# ==================== 板块同步任务 ====================


@shared_task(bind=True, max_retries=3)
def sync_sector_quotes(self):
    """
    同步板块行情数据

    每日收盘后执行，同步行业和概念板块行情
    """
    logger.info("开始同步板块行情")
    try:
        from app.datasources.sector_adapter import sector_adapter
        from app.core.database import get_db_session
        from app.models.sector import Sector, SectorQuote
        from sqlalchemy.dialects.postgresql import insert

        async def sync():
            # 获取所有板块数据
            sectors_df = await sector_adapter.get_all_sectors()

            if sectors_df is None or len(sectors_df) == 0:
                return {"status": "no_data", "synced": 0}

            async with get_db_session() as session:
                synced_sectors = 0
                synced_quotes = 0

                # 同步板块基础信息
                for row in sectors_df.iter_rows(named=True):
                    # 插入或更新板块信息
                    stmt = insert(Sector).values(
                        code=row["code"],
                        name=row["name"],
                        sector_type=row["sector_type"],
                        is_active=True,
                    )
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["code"],
                        set_={"name": stmt.excluded.name, "is_active": True},
                    )
                    await session.execute(stmt)
                    synced_sectors += 1

                # 同步板块行情
                for row in sectors_df.iter_rows(named=True):
                    stmt = insert(SectorQuote).values(
                        sector_code=row["code"],
                        trade_date=row["trade_date"],
                        index_value=float(row["index_value"]) if row["index_value"] else None,
                        change_pct=float(row["change_pct"]) if row["change_pct"] else None,
                        change_amount=float(row["change_amount"]) if row["change_amount"] else None,
                        total_amount=float(row["total_amount"]) if row["total_amount"] else None,
                        rising_count=row["rising_count"],
                        falling_count=row["falling_count"],
                        leading_stock=row["leading_stock"],
                        leading_stock_pct=float(row["leading_stock_pct"]) if row["leading_stock_pct"] else None,
                    )
                    stmt = stmt.on_conflict_do_nothing(
                        index_elements=["sector_code", "trade_date"]
                    )
                    await session.execute(stmt)
                    synced_quotes += 1

                await session.commit()

                return {
                    "status": "success",
                    "sectors": synced_sectors,
                    "quotes": synced_quotes,
                }

        result = run_async(sync())
        logger.info("板块行情同步完成", **result)
        return result

    except Exception as e:
        logger.error("板块行情同步失败", error=str(e))
        raise self.retry(exc=e, countdown=300)
