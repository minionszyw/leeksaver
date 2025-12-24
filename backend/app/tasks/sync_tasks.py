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
