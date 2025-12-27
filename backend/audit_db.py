import asyncio
import sys
import logging
from types import ModuleType

# Mock structlog before importing app modules
class MockLogger:
    def info(self, *args, **kwargs): pass
    def error(self, *args, **kwargs): pass
    def warning(self, *args, **kwargs): pass
    def debug(self, *args, **kwargs): pass
    def bind(self, *args, **kwargs): return self

mock_structlog = ModuleType("structlog")
mock_structlog.get_logger = lambda name=None: MockLogger()
mock_structlog.stdlib = ModuleType("structlog.stdlib")
mock_structlog.stdlib.BoundLogger = MockLogger
sys.modules["structlog"] = mock_structlog

from datetime import date, datetime, timedelta
from sqlalchemy import func, select, inspect, text
from app.core.database import get_db_session, engine
from app.models.stock import Stock, Watchlist
from app.models.market_data import DailyQuote
from app.models.financial import FinancialStatement
from app.models.news import NewsArticle
from app.models.capital_flow import NorthboundFlow, StockFundFlow, DragonTiger, MarginTrade
from app.models.market_sentiment import MarketSentiment, LimitUpStock
from app.models.valuation import DailyValuation
from app.models.sector import Sector, SectorQuote
from app.models.macro import MacroIndicator
from app.models.tech_indicator import TechIndicator

# Configure logging to suppress sqlalchemy info logs
logging.basicConfig(level=logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

async def audit_table(session, model, name, date_col=None):
    print(f"\n--- {name} ---")
    try:
        # 1. Total Count
        count_stmt = select(func.count()).select_from(model)
        count_result = await session.execute(count_stmt)
        total_count = count_result.scalar()
        print(f"Total Records: {total_count}")

        if total_count == 0:
            print("Status: EMPTY")
            return

        # 2. Date Range (if applicable)
        if date_col:
            min_stmt = select(func.min(getattr(model, date_col)))
            max_stmt = select(func.max(getattr(model, date_col)))
            
            min_res = await session.execute(min_stmt)
            max_res = await session.execute(max_stmt)
            
            min_date = min_res.scalar()
            max_date = max_res.scalar()
            
            print(f"Date Range: {min_date} to {max_date}")
            
            # Check for staleness
            if isinstance(max_date, (date, datetime)):
                # Convert datetime to date for comparison if necessary
                check_date = max_date.date() if isinstance(max_date, datetime) else max_date
                today = date.today()
                
                # Assume stale if older than 3 days (considering weekends)
                diff = (today - check_date).days
                if diff > 3:
                     print(f"Status: STALE (Last update {diff} days ago)")
                else:
                     print(f"Status: UP-TO-DATE")
            
            # Check for distinct dates (approximate density)
            # Only checking count of distinct dates to see if it's sparse
            distinct_date_stmt = select(func.count(func.distinct(getattr(model, date_col))))
            distinct_res = await session.execute(distinct_date_stmt)
            distinct_count = distinct_res.scalar()
            print(f"Distinct Dates: {distinct_count}")

    except Exception as e:
        print(f"Error auditing {name}: {str(e)}")

async def audit_stock_coverage(session):
    print("\n--- Stock Coverage Analysis ---")
    
    # Total Active Stocks
    stmt = select(func.count()).select_from(Stock).where(Stock.is_active == True)
    active_stocks = (await session.execute(stmt)).scalar()
    print(f"Active Stocks: {active_stocks}")

    if active_stocks == 0:
        return

    # Check recent coverage for DailyQuote
    # Find max date first
    max_date_stmt = select(func.max(DailyQuote.trade_date))
    max_date = (await session.execute(max_date_stmt)).scalar()
    
    if max_date:
        quote_count_stmt = select(func.count()).select_from(DailyQuote).where(DailyQuote.trade_date == max_date)
        quote_count = (await session.execute(quote_count_stmt)).scalar()
        print(f"DailyQuote Coverage on {max_date}: {quote_count}/{active_stocks} ({(quote_count/active_stocks)*100:.1f}%)")
    
    # Check Valuation Coverage
    max_val_date_stmt = select(func.max(DailyValuation.trade_date))
    max_val_date = (await session.execute(max_val_date_stmt)).scalar()
    
    if max_val_date:
        val_count_stmt = select(func.count()).select_from(DailyValuation).where(DailyValuation.trade_date == max_val_date)
        val_count = (await session.execute(val_count_stmt)).scalar()
        print(f"Valuation Coverage on {max_val_date}: {val_count}/{active_stocks} ({(val_count/active_stocks)*100:.1f}%)")

async def check_nulls(session, model, name, cols):
    print(f"\n--- {name} Null Checks ---")
    for col in cols:
        stmt = select(func.count()).select_from(model).where(getattr(model, col) == None)
        count = (await session.execute(stmt)).scalar()
        if count > 0:
            print(f"Column '{col}' has {count} NULLs")
        else:
             print(f"Column '{col}' OK")

async def main():
    print("Starting Data Layer Audit...")
    try:
        async with get_db_session() as session:
            # 1. Base Info
            await audit_table(session, Stock, "Stocks (Base Info)", "list_date")
            await audit_table(session, Watchlist, "Watchlist")
            await audit_table(session, Sector, "Sectors")
            
            # 2. Market Data
            await audit_table(session, DailyQuote, "Daily Quotes", "trade_date")
            await audit_table(session, SectorQuote, "Sector Quotes", "trade_date")
            
            # 3. Financials
            await audit_table(session, FinancialStatement, "Financial Statements", "end_date")
            
            # 4. News
            await audit_table(session, NewsArticle, "News Articles", "publish_time")
            
            # 5. Capital Flow
            await audit_table(session, NorthboundFlow, "Northbound Flow", "trade_date")
            await audit_table(session, StockFundFlow, "Stock Fund Flow", "trade_date")
            await audit_table(session, DragonTiger, "Dragon Tiger", "trade_date")
            await audit_table(session, MarginTrade, "Margin Trade", "trade_date")
            
            # 6. Sentiment & Valuation
            await audit_table(session, MarketSentiment, "Market Sentiment", "trade_date")
            await audit_table(session, DailyValuation, "Daily Valuation", "trade_date")
            await audit_table(session, TechIndicator, "Tech Indicators", "trade_date")
            await audit_table(session, MacroIndicator, "Macro Indicators", "period")
            
            # 7. Coverage & Integrity
            await audit_stock_coverage(session)
            
            # 8. Specific Null Checks
            await check_nulls(session, Stock, "Stock", ["industry"])
            await check_nulls(session, FinancialStatement, "Financials", ["total_revenue", "net_profit"])
            await check_nulls(session, DailyValuation, "Valuation", ["pe_ttm", "total_mv"])

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
