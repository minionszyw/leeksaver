"""
技术指标 Repository
"""

from datetime import date
from typing import Sequence

from sqlalchemy import select, func, and_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tech_indicator import TechIndicator
from app.repositories.base import BaseRepository
from app.core.logging import get_logger

logger = get_logger(__name__)


class TechIndicatorRepository(BaseRepository[TechIndicator]):
    """技术指标数据访问层"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, TechIndicator)

    async def get_by_code_date(
        self,
        code: str,
        trade_date: date,
    ) -> TechIndicator | None:
        """获取指定股票指定日期的技术指标"""
        result = await self.session.execute(
            select(TechIndicator).where(
                TechIndicator.code == code,
                TechIndicator.trade_date == trade_date,
            )
        )
        return result.scalar_one_or_none()

    async def get_latest(self, code: str) -> TechIndicator | None:
        """获取股票最新技术指标"""
        result = await self.session.execute(
            select(TechIndicator)
            .where(TechIndicator.code == code)
            .order_by(TechIndicator.trade_date.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_code(
        self,
        code: str,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int | None = None,
    ) -> Sequence[TechIndicator]:
        """获取股票的技术指标历史"""
        query = select(TechIndicator).where(TechIndicator.code == code)

        if start_date:
            query = query.where(TechIndicator.trade_date >= start_date)
        if end_date:
            query = query.where(TechIndicator.trade_date <= end_date)

        query = query.order_by(TechIndicator.trade_date.desc())

        if limit:
            query = query.limit(limit)

        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_latest_date(self, code: str | None = None) -> date | None:
        """获取最新技术指标日期"""
        query = select(func.max(TechIndicator.trade_date))
        if code:
            query = query.where(TechIndicator.code == code)

        result = await self.session.execute(query)
        return result.scalar()

    async def find_macd_golden_cross(
        self,
        trade_date: date,
        limit: int = 50,
    ) -> Sequence[TechIndicator]:
        """查找 MACD 金叉股票（MACD Bar 由负转正）"""
        # 获取当日 MACD Bar > 0 的股票
        result = await self.session.execute(
            select(TechIndicator)
            .where(
                TechIndicator.trade_date == trade_date,
                TechIndicator.macd_bar > 0,
            )
            .order_by(TechIndicator.macd_bar.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def find_oversold_rsi(
        self,
        trade_date: date,
        threshold: float = 30.0,
        limit: int = 50,
    ) -> Sequence[TechIndicator]:
        """查找 RSI 超卖股票"""
        result = await self.session.execute(
            select(TechIndicator)
            .where(
                TechIndicator.trade_date == trade_date,
                TechIndicator.rsi_14 < threshold,
                TechIndicator.rsi_14 > 0,  # 排除无效数据
            )
            .order_by(TechIndicator.rsi_14.asc())
            .limit(limit)
        )
        return result.scalars().all()

    async def find_overbought_rsi(
        self,
        trade_date: date,
        threshold: float = 70.0,
        limit: int = 50,
    ) -> Sequence[TechIndicator]:
        """查找 RSI 超买股票"""
        result = await self.session.execute(
            select(TechIndicator)
            .where(
                TechIndicator.trade_date == trade_date,
                TechIndicator.rsi_14 > threshold,
            )
            .order_by(TechIndicator.rsi_14.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def find_above_all_ma(
        self,
        trade_date: date,
        limit: int = 50,
    ) -> Sequence[TechIndicator]:
        """查找多头排列股票（价格在所有均线之上）"""
        # 需要关联 DailyQuote 获取收盘价，这里简化处理
        # 使用 MA5 > MA10 > MA20 > MA60 作为多头排列判断
        result = await self.session.execute(
            select(TechIndicator)
            .where(
                TechIndicator.trade_date == trade_date,
                TechIndicator.ma5 > TechIndicator.ma10,
                TechIndicator.ma10 > TechIndicator.ma20,
                TechIndicator.ma20 > TechIndicator.ma60,
                TechIndicator.ma60 is not None,
            )
            .order_by(TechIndicator.code)
            .limit(limit)
        )
        return result.scalars().all()

    async def upsert_many(self, records: list[dict]) -> int:
        """批量插入或更新技术指标"""
        if not records:
            return 0

        stmt = insert(TechIndicator).values(records)
        stmt = stmt.on_conflict_do_update(
            index_elements=["code", "trade_date"],
            set_={
                "ma5": stmt.excluded.ma5,
                "ma10": stmt.excluded.ma10,
                "ma20": stmt.excluded.ma20,
                "ma60": stmt.excluded.ma60,
                "macd_dif": stmt.excluded.macd_dif,
                "macd_dea": stmt.excluded.macd_dea,
                "macd_bar": stmt.excluded.macd_bar,
                "rsi_14": stmt.excluded.rsi_14,
                "kdj_k": stmt.excluded.kdj_k,
                "kdj_d": stmt.excluded.kdj_d,
                "kdj_j": stmt.excluded.kdj_j,
                "boll_upper": stmt.excluded.boll_upper,
                "boll_middle": stmt.excluded.boll_middle,
                "boll_lower": stmt.excluded.boll_lower,
                "cci": stmt.excluded.cci,
                "atr_14": stmt.excluded.atr_14,
                "obv": stmt.excluded.obv,
            },
        )

        await self.session.execute(stmt)
        await self.session.commit()

        logger.debug("批量更新技术指标", count=len(records))
        return len(records)
