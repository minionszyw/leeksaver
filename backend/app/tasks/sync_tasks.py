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
    from app.sync.news_syncer import news_syncer

    logger.info("开始同步全市场新闻")
    try:
        result = run_async(news_syncer.sync_market_news(limit=50))
        logger.info("全市场新闻同步完成", **result)
        return {"status": "success", **result}
    except Exception as e:
        logger.error("全市场新闻同步失败", error=str(e))
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=3)
def sync_hot_stocks_news(self):
    """
    同步热门股票新闻

    每天执行 2 次（早 8:00 和晚 18:00）
    """
    from app.sync.news_syncer import news_syncer

    logger.info("开始同步热门股票新闻")
    try:
        result = run_async(
            news_syncer.sync_hot_stocks_news(
                top_n=50,
                limit_per_stock=5,
            )
        )
        logger.info("热门股票新闻同步完成", **result)
        return {"status": "success", **result}
    except Exception as e:
        logger.error("热门股票新闻同步失败", error=str(e))
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=3)
def generate_news_embeddings(self):
    """
    为新闻生成文本向量

    每小时执行一次，为新入库的新闻生成向量
    """
    from app.sync.news_syncer import news_syncer

    logger.info("开始生成新闻向量")
    try:
        result = run_async(news_syncer.generate_embeddings(batch_size=100))
        logger.info("新闻向量生成完成", **result)
        return {"status": "success", **result}
    except Exception as e:
        logger.error("新闻向量生成失败", error=str(e))
        raise self.retry(exc=e, countdown=300)


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
