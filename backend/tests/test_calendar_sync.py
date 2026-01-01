import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch
import polars as pl
from sqlalchemy import select, delete

from app.models.calendar import TradingCalendar
from app.sync.calendar_syncer import calendar_syncer
from app.core.database import get_db_session

@pytest.mark.asyncio
async def test_calendar_sync_logic():
    """测试交易日历同步逻辑"""
    
    # 使用较远的历史日期以免干扰当前数据
    test_date_1 = date(1990, 1, 1)
    test_date_2 = date(1990, 1, 2)
    mock_dates = [test_date_1, test_date_2]
    mock_df = pl.DataFrame({"trade_date": mock_dates})

    # 清理旧测试数据
    async with get_db_session() as session:
        await session.execute(delete(TradingCalendar).where(TradingCalendar.trade_date.in_(mock_dates)))

    # Mock AkShare 适配器
    # 注意：sync 内部有日期过滤 logic (过去2年，未来1年)
    # 为了测试，我们需要 mock 一个在范围内的日期
    valid_date = date.today()
    mock_df = pl.DataFrame({"trade_date": [valid_date]})

    with patch("app.sync.calendar_syncer.akshare_adapter.get_trading_calendar", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_df

        # 执行同步
        result = await calendar_syncer.sync()
        
        # 验证结果
        assert result["status"] == "success"
        
        # 验证数据库内容
        async with get_db_session() as session:
            stmt = select(TradingCalendar).where(TradingCalendar.trade_date == valid_date)
            db_result = await session.execute(stmt)
            record = db_result.scalar_one_or_none()
            
            assert record is not None
            assert record.trade_date == valid_date
            assert record.is_open is True

@pytest.mark.asyncio
async def test_calendar_sync_idempotency():
    """测试幂等性：重复同步不会导致数据重复或主键冲突"""
    
    # 使用今天的日期进行测试
    today = date.today()
    mock_df = pl.DataFrame({"trade_date": [today]})

    with patch("app.sync.calendar_syncer.akshare_adapter.get_trading_calendar", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_df

        # 连续同步两次
        res1 = await calendar_syncer.sync()
        res2 = await calendar_syncer.sync()
        
        assert res1["status"] == "success"
        assert res2["status"] == "success"
        
        async with get_db_session() as session:
            stmt = select(TradingCalendar).where(TradingCalendar.trade_date == today)
            db_result = await session.execute(stmt)
            records = db_result.scalars().all()
            
            # 即使同步两次，主键冲突应被 ON CONFLICT 解决，数据库中只有一条记录
            assert len(records) == 1
