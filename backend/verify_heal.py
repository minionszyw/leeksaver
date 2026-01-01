
import asyncio
from datetime import date
from app.sync.daily_quote_syncer import daily_quote_syncer
from app.core.database import get_db_session
from app.repositories.market_data_repository import MarketDataRepository

async def verify_heal():
    code = '000001'
    target_date = date(2025, 12, 31)
    
    print(f"--- 开始原子自愈测试 ({code}) ---")
    
    # 1. 显式同步
    print(f"正在执行强制同步: {target_date}")
    count = await daily_quote_syncer.sync_single(
        code=code, 
        start_date=target_date, 
        end_date=target_date
    )
    print(f"同步完成，影响行数: {count}")
    
    # 2. 查库验证
    async with get_db_session() as session:
        repo = MarketDataRepository(session)
        from sqlalchemy import text
        stmt = text(f"SELECT volume FROM daily_quotes WHERE code='{code}' AND trade_date='{target_date}'")
        result = await session.execute(stmt)
        volume = result.scalar()
        print(f"数据库最新成交量: {volume}")
        
verify_heal()
if __name__ == "__main__":
    asyncio.run(verify_heal())
