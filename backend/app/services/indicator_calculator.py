"""
技术指标计算服务

提供 MA、MACD、RSI、KDJ、布林带、CCI、ATR、OBV 等技术指标的计算
"""

import polars as pl
from decimal import Decimal
from typing import Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


class IndicatorCalculator:
    """
    技术指标计算器

    支持批量计算多种技术指标，输入为 Polars DataFrame
    """

    # 指标参数配置
    MA_PERIODS = [5, 10, 20, 60]
    MACD_PARAMS = {"fast": 12, "slow": 26, "signal": 9}
    RSI_PERIOD = 14
    KDJ_PARAMS = {"n": 9, "m1": 3, "m2": 3}
    BOLL_PARAMS = {"period": 20, "std_dev": 2}
    CCI_PERIOD = 14
    ATR_PERIOD = 14

    def calculate_all(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        计算所有技术指标

        Args:
            df: 包含 trade_date, open, high, low, close, volume 列的 DataFrame
                必须按日期升序排序

        Returns:
            添加了所有技术指标列的 DataFrame
        """
        if len(df) < 60:
            logger.warning("数据量不足，无法计算所有指标", count=len(df))
            return df

        # 确保按日期升序
        df = df.sort("trade_date", descending=False)

        # 依次计算各指标
        df = self._calc_ma(df)
        df = self._calc_macd(df)
        df = self._calc_rsi(df)
        df = self._calc_kdj(df)
        df = self._calc_boll(df)
        df = self._calc_cci(df)
        df = self._calc_atr(df)
        df = self._calc_obv(df)

        return df

    def _calc_ma(self, df: pl.DataFrame) -> pl.DataFrame:
        """计算均线"""
        return df.with_columns([
            pl.col("close").rolling_mean(window_size=p).round(2).alias(f"ma{p}")
            for p in self.MA_PERIODS
        ])

    def _calc_macd(self, df: pl.DataFrame) -> pl.DataFrame:
        """计算 MACD"""
        fast = self.MACD_PARAMS["fast"]
        slow = self.MACD_PARAMS["slow"]
        signal = self.MACD_PARAMS["signal"]

        # 计算 EMA
        ema_fast = df["close"].ewm_mean(span=fast)
        ema_slow = df["close"].ewm_mean(span=slow)

        # DIF = EMA(fast) - EMA(slow)
        dif = ema_fast - ema_slow

        # DEA = EMA(DIF, signal)
        dea = dif.ewm_mean(span=signal)

        # MACD Bar = (DIF - DEA) * 2
        macd_bar = (dif - dea) * 2

        return df.with_columns([
            dif.round(4).alias("macd_dif"),
            dea.round(4).alias("macd_dea"),
            macd_bar.round(4).alias("macd_bar"),
        ])

    def _calc_rsi(self, df: pl.DataFrame) -> pl.DataFrame:
        """计算 RSI"""
        period = self.RSI_PERIOD

        # 计算价格变化
        delta = df["close"].diff()

        # 使用 Polars 原生操作替代 map_elements，避免类型问题
        # 分离上涨和下跌
        gain = pl.when(delta > 0).then(delta).otherwise(0.0)
        loss = pl.when(delta < 0).then(-delta).otherwise(0.0)

        # 计算平均涨跌幅
        avg_gain = gain.rolling_mean(window_size=period)
        avg_loss = loss.rolling_mean(window_size=period)

        # 避免除零，使用 fill_null 和 when 替代 map_elements
        avg_loss_safe = pl.when(avg_loss > 0).then(avg_loss).otherwise(0.0001)

        # RS = 平均涨幅 / 平均跌幅
        rs = avg_gain / avg_loss_safe

        # RSI = 100 - (100 / (1 + RS))
        rsi = 100.0 - (100.0 / (1.0 + rs))

        return df.with_columns([
            rsi.round(4).alias("rsi_14"),
        ])

    def _calc_kdj(self, df: pl.DataFrame) -> pl.DataFrame:
        """计算 KDJ"""
        n = self.KDJ_PARAMS["n"]
        m1 = self.KDJ_PARAMS["m1"]
        m2 = self.KDJ_PARAMS["m2"]

        # 计算 N 日内最低价和最高价
        low_n = df["low"].rolling_min(window_size=n)
        high_n = df["high"].rolling_max(window_size=n)

        # RSV = (Close - Low_N) / (High_N - Low_N) * 100
        denominator = high_n - low_n
        # 使用 Polars 原生操作替代 map_elements
        denominator_safe = pl.when(denominator > 0).then(denominator).otherwise(0.0001)

        rsv = (df["close"] - low_n) / denominator_safe * 100.0

        # K = EMA(RSV, m1)
        # D = EMA(K, m2)
        # 使用指数平滑近似
        k = rsv.ewm_mean(span=m1 * 2 - 1)
        d = k.ewm_mean(span=m2 * 2 - 1)

        # J = 3K - 2D
        j = 3.0 * k - 2.0 * d

        return df.with_columns([
            k.round(4).alias("kdj_k"),
            d.round(4).alias("kdj_d"),
            j.round(4).alias("kdj_j"),
        ])

    def _calc_boll(self, df: pl.DataFrame) -> pl.DataFrame:
        """计算布林带"""
        period = self.BOLL_PARAMS["period"]
        std_dev = self.BOLL_PARAMS["std_dev"]

        # 中轨 = MA(period)
        middle = df["close"].rolling_mean(window_size=period)

        # 标准差
        std = df["close"].rolling_std(window_size=period)

        # 上轨 = 中轨 + std_dev * 标准差
        upper = middle + std_dev * std

        # 下轨 = 中轨 - std_dev * 标准差
        lower = middle - std_dev * std

        return df.with_columns([
            upper.round(2).alias("boll_upper"),
            middle.round(2).alias("boll_middle"),
            lower.round(2).alias("boll_lower"),
        ])

    def _calc_cci(self, df: pl.DataFrame) -> pl.DataFrame:
        """计算 CCI"""
        period = self.CCI_PERIOD

        # 典型价格 TP = (High + Low + Close) / 3
        tp = (df["high"] + df["low"] + df["close"]) / 3.0

        # 典型价格的移动平均
        tp_ma = tp.rolling_mean(window_size=period)

        # 平均绝对偏差 (简化计算)
        # MD = 滚动标准差 * 0.6745 近似
        tp_std = tp.rolling_std(window_size=period)
        # 使用 Polars 原生操作替代 map_elements
        md_safe = pl.when(tp_std > 0).then(tp_std).otherwise(0.0001)

        # CCI = (TP - MA) / (0.015 * MD)
        cci = (tp - tp_ma) / (0.015 * md_safe)

        return df.with_columns([
            cci.round(4).alias("cci"),
        ])

    def _calc_atr(self, df: pl.DataFrame) -> pl.DataFrame:
        """计算 ATR (平均真实波幅)"""
        period = self.ATR_PERIOD

        high = df["high"]
        low = df["low"]
        prev_close = df["close"].shift(1)

        # 真实波幅 TR = max(High-Low, |High-PrevClose|, |Low-PrevClose|)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()

        # 取最大值
        tr = pl.max_horizontal(tr1, tr2, tr3)

        # ATR = MA(TR, period)
        atr = tr.rolling_mean(window_size=period)

        return df.with_columns([
            atr.round(4).alias("atr_14"),
        ])

    def _calc_obv(self, df: pl.DataFrame) -> pl.DataFrame:
        """计算 OBV (能量潮)"""
        # 价格变化方向
        close_diff = df["close"].diff()

        # 使用 Polars 原生操作替代 map_elements
        sign = (
            pl.when(close_diff > 0).then(1)
            .when(close_diff < 0).then(-1)
            .otherwise(0)
        )

        # OBV = 累积（符号 * 成交量）
        obv = (df["volume"] * sign).cum_sum()

        return df.with_columns([
            obv.alias("obv"),
        ])


# 全局单例
indicator_calculator = IndicatorCalculator()
