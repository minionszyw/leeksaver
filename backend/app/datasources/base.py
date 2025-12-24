"""
数据源抽象基类
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import Any

import polars as pl


class DataSourceBase(ABC):
    """数据源抽象基类"""

    @abstractmethod
    async def get_stock_list(self) -> pl.DataFrame:
        """
        获取股票列表

        Returns:
            DataFrame with columns: code, name, market, asset_type
        """
        pass

    @abstractmethod
    async def get_etf_list(self) -> pl.DataFrame:
        """
        获取 ETF 列表

        Returns:
            DataFrame with columns: code, name, market, asset_type
        """
        pass

    @abstractmethod
    async def get_daily_quotes(
        self,
        code: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pl.DataFrame:
        """
        获取日线行情

        Args:
            code: 股票代码
            start_date: 起始日期
            end_date: 结束日期

        Returns:
            DataFrame with columns: code, trade_date, open, high, low, close, volume, amount, change, change_pct
        """
        pass

    @abstractmethod
    async def get_realtime_quote(self, code: str) -> dict[str, Any]:
        """
        获取实时行情

        Args:
            code: 股票代码

        Returns:
            实时行情字典
        """
        pass
