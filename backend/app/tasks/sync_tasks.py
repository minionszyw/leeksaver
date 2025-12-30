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
def sync_daily_quotes(self, codes: list[str] | None = None, is_chunk: bool = False):
    """
    同步日线行情数据 (L1)

    策略：
    1. 如果没有指定 codes，则获取全市场列表并分片(Chunking)异步执行
    2. 如果指定了 codes，则直接同步这些股票
    """
    from app.sync.daily_quote_syncer import daily_quote_syncer
    from app.core.database import get_db_session
    from app.repositories.stock_repository import StockRepository

    if codes is None:
        # 1. 生产者模式：获取全量代码并分片分发任务
        logger.info("开始全市场同步任务调度（分片模式）")
        
        async def get_all_codes():
            async with get_db_session() as session:
                repo = StockRepository(session)
                return await repo.get_all_codes()

        all_codes = run_async(get_all_codes())
        
        # 每 100 只股票一个分片
        chunk_size = 100
        chunks = [all_codes[i:i + chunk_size] for i in range(0, len(all_codes), chunk_size)]
        
        logger.info(f"全市场共 {len(all_codes)} 只标的，切分为 {len(chunks)} 个分片执行")
        
        for chunk in chunks:
            sync_daily_quotes.delay(codes=chunk, is_chunk=True)
            
        return {"status": "dispatched", "chunks": len(chunks), "total": len(all_codes)}

    # 2. 消费者模式：执行具体的同步
    scope = f"分片任务({len(codes)}只)" if is_chunk else f"{len(codes)} 只股票"
    logger.info("开始同步日线行情", scope=scope)

    try:
        result = run_async(daily_quote_syncer.sync_batch(codes, max_concurrent=5))
        logger.info("日线行情同步完成", scope=scope, **result)
        return {"status": "success", "scope": scope, **result}
    except Exception as e:
        logger.error("日线行情同步失败", scope=scope, error=str(e))
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
def sync_minute_quotes(self):
    """
    同步自选股分钟行情数据 (L2)
    """
    from app.sync.minute_quote_syncer import minute_quote_syncer

    logger.info("开始同步自选股分钟行情")
    try:
        result = run_async(minute_quote_syncer.sync_watchlist())
        logger.info("自选股分钟行情同步完成", **result)
        return {"status": "success", **result}
    except Exception as e:
        logger.error("自选股分钟行情同步失败", error=str(e))
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
        result = run_async(financial_syncer.sync_all(sync_type="financial"))
        logger.info("财务报表同步完成", **result)
        return {"status": "success", **result}
    except Exception as e:
        logger.error("财务报表同步失败", error=str(e))
        # 失败后 5 分钟重试
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=3)
def sync_operation_data(self):
    """
    同步全市场经营数据 (主营构成)
    """
    from app.sync.financial_syncer import financial_syncer

    logger.info("开始同步经营数据")
    try:
        # 为了验证，我们先只同步前 50 只股票，避免执行时间过长
        from app.core.database import get_db_session
        from app.repositories.stock_repository import StockRepository
        
        async def get_test_codes():
            async with get_db_session() as session:
                repo = StockRepository(session)
                codes = await repo.get_all_codes(asset_type="stock")
                return codes[:50]
        
        test_codes = run_async(get_test_codes())
        result = run_async(financial_syncer.sync_batch(test_codes, sync_type="operation"))
        
        logger.info("经营数据同步完成", **result)
        return {"status": "success", **result}
    except Exception as e:
        logger.error("经营数据同步失败", error=str(e))
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=3)
def sync_global_news(self):
    """
    同步全市快讯 (财联社单一源)
    """
    from app.sync.news_syncer import news_syncer

    logger.info("开始同步全市快讯")
    try:
        result = run_async(news_syncer.sync_market_news())
        logger.info("全市快讯同步完成", **result)
        return {"status": "success", **result}
    except Exception as e:
        logger.error("全市快讯同步失败", error=str(e))
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=3)
def sync_stock_news_rotation(self):
    """
    全市场个股新闻轮询同步 (东方财富)
    """
    from app.sync.news_syncer import news_syncer

    logger.info("开始轮询个股新闻")
    try:
        # 每批次处理 50 只股票
        result = run_async(news_syncer.sync_stock_news_batch(batch_size=50))
        logger.info("个股新闻轮询同步完成", **result)
        return {"status": "success", **result}
    except Exception as e:
        logger.error("个股新闻轮询同步失败", error=str(e))
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
    注意：两融数据通常 T+1 披露，所以默认同步 T-1 日数据
    """
    from datetime import date, timedelta
    from app.sync.capital_flow_syncer import capital_flow_syncer

    target_date = date.today() - timedelta(days=1)
    logger.info("开始同步两融数据", target_date=str(target_date))
    try:
        result = run_async(capital_flow_syncer.sync_margin_trade(target_date))
        logger.info("两融数据同步完成", **result)
        return {"status": "success", **result}
    except Exception as e:
        logger.error("两融数据同步失败", error=str(e))
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=3)
def sync_northbound_history(self):
    """
    同步北向资金历史数据（回填用）
    """
    from app.sync.capital_flow_syncer import capital_flow_syncer

    logger.info("开始同步北向资金历史")
    try:
        result = run_async(capital_flow_syncer.sync_northbound_history())
        logger.info("北向资金历史同步完成", **result)
        return {"status": "success", **result}
    except Exception as e:
        logger.error("北向资金历史同步失败", error=str(e))
        raise self.retry(exc=e, countdown=300)


# ==================== 情绪面同步任务 ====================


@shared_task(bind=True, max_retries=5)
def sync_market_sentiment(self):
    """
    同步市场情绪数据

    每日收盘后执行，计算涨跌统计、连板情况等
    若依赖的行情数据未准备好，会自动重试
    """
    from datetime import date
    from app.sync.sentiment_syncer import sentiment_syncer

    logger.info("开始同步市场情绪")
    try:
        # 同步涨停池
        limit_up_result = run_async(sentiment_syncer.sync_limit_up_pool(date.today()))
        # 同步市场情绪指标
        sentiment_result = run_async(sentiment_syncer.sync_market_sentiment(date.today()))

        # 检查是否因为缺数据而跳过
        if sentiment_result.get("status") == "no_data":
            logger.warning("市场情绪数据缺失（可能行情未同步），稍后重试")
            raise self.retry(countdown=300)

        logger.info("市场情绪同步完成", limit_up=limit_up_result, sentiment=sentiment_result)
        return {
            "status": "success",
            "limit_up": limit_up_result,
            "sentiment": sentiment_result,
        }
    except Exception as e:
        logger.error("市场情绪同步失败", error=str(e))
        raise self.retry(exc=e, countdown=300)


# ==================== 宏观经济同步任务 ====================


@shared_task(bind=True, max_retries=3)
def sync_macro_economic_data(self):
    """
    同步宏观经济数据 (GDP, PMI, CPI, etc.)
    """
    from app.sync.macro_syncer import macro_syncer

    logger.info("开始同步宏观经济数据")
    try:
        result = run_async(macro_syncer.sync_all())
        logger.info("宏观经济数据同步完成", **result)
        return {"status": "success", **result}
    except Exception as e:
        logger.error("宏观经济数据同步失败", error=str(e))
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
