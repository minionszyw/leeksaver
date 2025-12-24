"""
技术分析工具

提供股票技术分析能力，包括趋势判断和技术指标计算
"""

from datetime import date, timedelta
from decimal import Decimal

import polars as pl

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.repositories.stock_repository import StockRepository
from app.repositories.market_data_repository import MarketDataRepository
from app.agent.tools.base import ToolBase, ToolResult, ToolRegistry
from app.agent.schema.tool_schemas import (
    TechAnalysisInput,
    TechAnalysisOutput,
    TrendAnalysis,
    IndicatorResult,
)

logger = get_logger(__name__)


class TechAnalysisTool(ToolBase):
    """技术分析工具"""

    name = "tech_analysis"
    description = "对股票进行技术分析，包括趋势判断和技术指标"
    input_schema = TechAnalysisInput
    output_schema = TechAnalysisOutput

    # 周期映射
    PERIOD_DAYS = {
        "short": 5,
        "medium": 20,
        "long": 60,
    }

    async def execute(self, **kwargs) -> ToolResult:
        """执行技术分析"""
        try:
            input_data = self.validate_input(**kwargs)
            code = input_data.stock_code
            period = input_data.period
            indicators = input_data.indicators or ["ma", "macd"]

            async with get_db_session() as session:
                stock_repo = StockRepository(session)
                market_repo = MarketDataRepository(session)

                # 获取股票信息
                stock = await stock_repo.get_by_code(code)
                if not stock:
                    return ToolResult(success=False, error=f"未找到股票: {code}")

                # 获取历史数据
                days = self.PERIOD_DAYS.get(period, 20) + 60  # 多取一些用于计算指标
                end_date = date.today()
                start_date = end_date - timedelta(days=days * 2)

                quotes = await market_repo.get_daily_quotes(code, start_date, end_date)

                if len(quotes) < 5:
                    return ToolResult(
                        success=False,
                        error=f"历史数据不足，无法进行技术分析",
                    )

                # 转换为 Polars DataFrame
                df = self._quotes_to_df(quotes)

                # 计算技术指标
                df = self._calculate_indicators(df, indicators)

                # 分析趋势
                trend = self._analyze_trend(df, period)

                # 提取指标结果
                indicator_results = self._extract_indicator_results(df, indicators)

                # 生成分析总结
                summary = self._generate_summary(
                    stock.name, trend, indicator_results, period
                )

                # 获取最新价格
                current_price = float(df["close"].head(1)[0])

                output = TechAnalysisOutput(
                    success=True,
                    code=code,
                    name=stock.name,
                    period=period,
                    current_price=current_price,
                    trend=trend,
                    indicators=indicator_results,
                    summary=summary,
                )

                return ToolResult(success=True, data=output)

        except Exception as e:
            logger.error("技术分析失败", error=str(e))
            return ToolResult(success=False, error=str(e))

    def _quotes_to_df(self, quotes) -> pl.DataFrame:
        """将行情数据转换为 DataFrame"""
        data = {
            "date": [q.trade_date for q in quotes],
            "open": [float(q.open) if q.open else None for q in quotes],
            "high": [float(q.high) if q.high else None for q in quotes],
            "low": [float(q.low) if q.low else None for q in quotes],
            "close": [float(q.close) if q.close else None for q in quotes],
            "volume": [q.volume for q in quotes],
        }
        return pl.DataFrame(data).sort("date", descending=True)

    def _calculate_indicators(
        self, df: pl.DataFrame, indicators: list[str]
    ) -> pl.DataFrame:
        """计算技术指标"""
        # MA 均线
        if "ma" in indicators:
            df = df.with_columns(
                pl.col("close").rolling_mean(5).alias("ma5"),
                pl.col("close").rolling_mean(10).alias("ma10"),
                pl.col("close").rolling_mean(20).alias("ma20"),
                pl.col("close").rolling_mean(60).alias("ma60"),
            )

        # MACD
        if "macd" in indicators:
            ema12 = df["close"].ewm_mean(span=12)
            ema26 = df["close"].ewm_mean(span=26)
            dif = ema12 - ema26
            dea = dif.ewm_mean(span=9)
            macd = (dif - dea) * 2

            df = df.with_columns(
                dif.alias("dif"),
                dea.alias("dea"),
                macd.alias("macd"),
            )

        # RSI
        if "rsi" in indicators:
            delta = df["close"].diff()
            gain = delta.map_elements(lambda x: x if x > 0 else 0, return_dtype=pl.Float64)
            loss = delta.map_elements(lambda x: -x if x < 0 else 0, return_dtype=pl.Float64)

            avg_gain = gain.rolling_mean(14)
            avg_loss = loss.rolling_mean(14)

            rs = avg_gain / avg_loss.replace(0, 0.001)
            rsi = 100 - (100 / (1 + rs))

            df = df.with_columns(rsi.alias("rsi"))

        return df

    def _analyze_trend(self, df: pl.DataFrame, period: str) -> TrendAnalysis:
        """分析趋势"""
        period_days = self.PERIOD_DAYS.get(period, 20)

        # 获取近期数据
        recent = df.head(period_days)
        current_price = recent["close"][0]
        start_price = recent["close"][-1]

        # 判断趋势方向
        change_pct = (current_price - start_price) / start_price * 100

        if change_pct > 5:
            direction = "up"
        elif change_pct < -5:
            direction = "down"
        else:
            direction = "sideways"

        # 判断趋势强度
        if abs(change_pct) > 15:
            strength = "strong"
        elif abs(change_pct) > 5:
            strength = "moderate"
        else:
            strength = "weak"

        # 计算支撑位和压力位
        lows = recent["low"].drop_nulls().to_list()
        highs = recent["high"].drop_nulls().to_list()

        support = min(lows) if lows else None
        resistance = max(highs) if highs else None

        return TrendAnalysis(
            direction=direction,
            strength=strength,
            support=support,
            resistance=resistance,
        )

    def _extract_indicator_results(
        self, df: pl.DataFrame, indicators: list[str]
    ) -> list[IndicatorResult]:
        """提取指标结果"""
        results = []
        latest = df.head(1)

        if "ma" in indicators and "ma5" in df.columns:
            current = latest["close"][0]
            ma5 = latest["ma5"][0]
            ma20 = latest["ma20"][0]

            if ma5 and ma20:
                if current > ma5 > ma20:
                    signal = "buy"
                    desc = "短期均线多头排列"
                elif current < ma5 < ma20:
                    signal = "sell"
                    desc = "短期均线空头排列"
                else:
                    signal = "neutral"
                    desc = "均线交织"

                results.append(
                    IndicatorResult(
                        name="MA",
                        value={"ma5": round(ma5, 2), "ma20": round(ma20, 2) if ma20 else None},
                        signal=signal,
                        description=desc,
                    )
                )

        if "macd" in indicators and "macd" in df.columns:
            dif = latest["dif"][0]
            dea = latest["dea"][0]
            macd = latest["macd"][0]

            if dif and dea:
                if dif > dea and macd > 0:
                    signal = "buy"
                    desc = "MACD 金叉，多头趋势"
                elif dif < dea and macd < 0:
                    signal = "sell"
                    desc = "MACD 死叉，空头趋势"
                else:
                    signal = "neutral"
                    desc = "MACD 震荡"

                results.append(
                    IndicatorResult(
                        name="MACD",
                        value={"dif": round(dif, 3), "dea": round(dea, 3)},
                        signal=signal,
                        description=desc,
                    )
                )

        if "rsi" in indicators and "rsi" in df.columns:
            rsi = latest["rsi"][0]
            if rsi:
                if rsi > 70:
                    signal = "sell"
                    desc = "RSI 超买区域"
                elif rsi < 30:
                    signal = "buy"
                    desc = "RSI 超卖区域"
                else:
                    signal = "neutral"
                    desc = "RSI 中性区域"

                results.append(
                    IndicatorResult(
                        name="RSI",
                        value=round(rsi, 2),
                        signal=signal,
                        description=desc,
                    )
                )

        return results

    def _generate_summary(
        self,
        name: str,
        trend: TrendAnalysis,
        indicators: list[IndicatorResult],
        period: str,
    ) -> str:
        """生成分析总结"""
        period_name = {"short": "短期", "medium": "中期", "long": "长期"}[period]

        direction_name = {"up": "上涨", "down": "下跌", "sideways": "震荡"}[
            trend.direction
        ]
        strength_name = {"strong": "强劲", "moderate": "温和", "weak": "较弱"}[
            trend.strength
        ]

        summary = f"{name} {period_name}趋势呈现{strength_name}的{direction_name}态势。"

        if trend.support and trend.resistance:
            summary += f" 支撑位约 {trend.support:.2f}，压力位约 {trend.resistance:.2f}。"

        # 添加指标信号
        buy_signals = [i for i in indicators if i.signal == "buy"]
        sell_signals = [i for i in indicators if i.signal == "sell"]

        if buy_signals:
            summary += f" {', '.join([i.name for i in buy_signals])} 显示买入信号。"
        if sell_signals:
            summary += f" {', '.join([i.name for i in sell_signals])} 显示卖出信号。"

        return summary


# 注册工具
ToolRegistry.register(TechAnalysisTool())
