"""
AkShare 数据源适配器

封装 AkShare 接口，提供统一的数据获取能力
"""

import asyncio
import random
from datetime import date, datetime, timedelta
from typing import Any

import akshare as ak
import polars as pl

from app.core.logging import get_logger
from app.datasources.base import DataSourceBase
from app.datasources.rate_limiter import akshare_limiter

logger = get_logger(__name__)


def retry_with_backoff(retries: int = 3, backoff_in_seconds: int = 1):
    """
    指数退避重试装饰器
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            x = 0
            while True:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    # 检查是否为网络错误或限频错误
                    # 这里捕获所有 Exception，因为 AkShare 抛出的错误类型不统一
                    if x == retries:
                        raise
                    
                    sleep = (backoff_in_seconds * 2 ** x + random.uniform(0, 1))
                    logger.warning(
                        f"调用失败，将在 {sleep:.2f}s 后重试: {str(e)}",
                        func=func.__name__,
                        retry=x + 1
                    )
                    await asyncio.sleep(sleep)
                    x += 1
        return wrapper
    return decorator


class AkShareAdapter(DataSourceBase):
    """
    AkShare 数据源适配器

    注意：AkShare 是同步库，需要在线程池中执行
    """

    def __init__(self):
        pass

    @retry_with_backoff(retries=3, backoff_in_seconds=1)
    async def _run_sync(self, func, *args, **kwargs):
        """在线程池中运行同步函数"""
        async with akshare_limiter:
            return await asyncio.to_thread(func, *args, **kwargs)

    async def get_stock_list(self) -> pl.DataFrame:
        """
        获取 A 股股票列表

        使用 stock_info_a_code_name 接口
        """
        logger.info("获取 A 股股票列表")

        try:
            # 获取沪深股票列表
            df = await self._run_sync(ak.stock_info_a_code_name)

            # 转换为 Polars DataFrame
            result = pl.from_pandas(df)

            # 规范化列名
            result = result.rename({"code": "code", "name": "name"})

            # 添加市场标识
            result = result.with_columns(
                pl.when(pl.col("code").str.starts_with("6"))
                .then(pl.lit("SH"))
                .when(pl.col("code").str.starts_with("0"))
                .then(pl.lit("SZ"))
                .when(pl.col("code").str.starts_with("3"))
                .then(pl.lit("SZ"))
                .otherwise(pl.lit("BJ"))
                .alias("market"),
                pl.lit("stock").alias("asset_type"),
            )

            logger.info("获取 A 股股票列表成功", count=len(result))
            return result

        except Exception as e:
            logger.error("获取 A 股股票列表失败", error=str(e))
            raise

    async def get_etf_list(self) -> pl.DataFrame:
        """
        获取场内 ETF 列表

        使用 fund_etf_spot_em 接口
        """
        logger.info("获取 ETF 列表")

        try:
            # 获取 ETF 实时行情 (包含 ETF 列表)
            df = await self._run_sync(ak.fund_etf_spot_em)

            # 转换为 Polars DataFrame
            result = pl.from_pandas(df)

            # 选择需要的列并重命名
            result = result.select(
                pl.col("代码").alias("code"),
                pl.col("名称").alias("name"),
            ).with_columns(
                pl.when(pl.col("code").str.starts_with("5"))
                .then(pl.lit("SH"))
                .when(pl.col("code").str.starts_with("1"))
                .then(pl.lit("SZ"))
                .otherwise(pl.lit("SZ"))
                .alias("market"),
                pl.lit("etf").alias("asset_type"),
            )

            logger.info("获取 ETF 列表成功", count=len(result))
            return result

        except Exception as e:
            logger.error("获取 ETF 列表失败", error=str(e))
            raise

    async def get_daily_quotes(
        self,
        code: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pl.DataFrame:
        """
        获取股票日线行情

        使用 stock_zh_a_hist 接口
        """
        # 默认获取最近 2 年数据
        if start_date is None:
            start_date = date.today() - timedelta(days=730)
        if end_date is None:
            end_date = date.today()

        logger.debug(
            "获取日线行情",
            code=code,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )

        try:
            # 调用 AkShare 接口
            df = await self._run_sync(
                ak.stock_zh_a_hist,
                symbol=code,
                period="daily",
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
                adjust="qfq",  # 前复权
            )

            if df is None or df.empty:
                logger.warning("日线行情数据为空", code=code)
                return pl.DataFrame()

            # 转换为 Polars DataFrame
            result = pl.from_pandas(df)

            # 规范化列名
            # 处理日期列：如果是 date 类型直接使用，如果是字符串则转换
            date_col = result["日期"]
            if date_col.dtype == pl.Date:
                trade_date_expr = pl.col("日期").alias("trade_date")
            else:
                trade_date_expr = pl.col("日期").str.to_date("%Y-%m-%d").alias("trade_date")

            result = result.select(
                pl.lit(code).alias("code"),
                trade_date_expr,
                pl.col("开盘").cast(pl.Decimal(10, 2)).alias("open"),
                pl.col("最高").cast(pl.Decimal(10, 2)).alias("high"),
                pl.col("最低").cast(pl.Decimal(10, 2)).alias("low"),
                pl.col("收盘").cast(pl.Decimal(10, 2)).alias("close"),
                pl.col("成交量").cast(pl.Int64).alias("volume"),
                pl.col("成交额").cast(pl.Decimal(18, 2)).alias("amount"),
                pl.col("涨跌额").cast(pl.Decimal(10, 2)).alias("change"),
                pl.col("涨跌幅").cast(pl.Decimal(8, 4)).alias("change_pct"),
                pl.col("换手率").cast(pl.Decimal(8, 4)).alias("turnover_rate"),
            )

            # 数据清洗：过滤掉关键字段为空或为 0 的记录
            original_count = len(result)

            # 基础清洗：价格和成交量必须有效
            result = result.filter(
                pl.col("open").is_not_null() & (pl.col("open") > 0) &
                pl.col("high").is_not_null() & (pl.col("high") > 0) &
                pl.col("low").is_not_null() & (pl.col("low") > 0) &
                pl.col("close").is_not_null() & (pl.col("close") > 0) &
                pl.col("volume").is_not_null() & (pl.col("volume") > 0)
            )

            # 高级清洗规则
            # 1. 高低价倒挂检测：high 必须 >= low
            result = result.filter(pl.col("high") >= pl.col("low"))

            # 2. 价格合理性检测：开盘价、最高价、最低价应在收盘价的合理范围内
            #    允许涨跌停板（±10%）+ 一些缓冲（±25% 覆盖所有正常情况）
            result = result.filter(
                (pl.col("high") <= pl.col("close") * 1.25) &
                (pl.col("low") >= pl.col("close") * 0.75) &
                (pl.col("open") <= pl.col("close") * 1.25) &
                (pl.col("open") >= pl.col("close") * 0.75)
            )

            # 3. 涨跌幅合理性检测
            #    正常股票 ±20%（包含特殊情况）
            #    注：这里使用较宽松的限制，因为有些特殊情况（复牌、重组等）可能有大涨跌
            result = result.filter(
                pl.col("change_pct").abs() <= 30.0  # 绝对值不超过 30%
            )

            filtered_count = len(result)
            dropped = original_count - filtered_count
            if dropped > 0:
                drop_rate = (dropped / original_count * 100) if original_count > 0 else 0
                logger.warning(
                    "过滤无效行情数据",
                    code=code,
                    original=original_count,
                    filtered=filtered_count,
                    dropped=dropped,
                    drop_rate=f"{drop_rate:.2f}%"
                )

            logger.debug("获取日线行情成功", code=code, count=len(result))
            return result

        except Exception as e:
            logger.error("获取日线行情失败", code=code, error=str(e))
            raise

    async def get_minute_quotes(
        self,
        code: str,
        period: str = "1",
        adjust: str = "qfq",
    ) -> pl.DataFrame:
        """
        获取股票分钟行情

        使用 stock_zh_a_minute 接口
        """
        logger.debug("获取分钟行情", code=code, period=period)

        try:
            # 调用 AkShare 接口
            df = await self._run_sync(
                ak.stock_zh_a_minute,
                symbol=code,
                period=period,
                adjust=adjust,
            )

            if df is None or df.empty:
                logger.warning("分钟行情数据为空", code=code)
                return pl.DataFrame()

            # 转换为 Polars DataFrame
            result = pl.from_pandas(df)

            # 规范化列名
            # AkShare 返回列名：day, open, high, low, close, volume
            result = result.select(
                pl.lit(code).alias("code"),
                pl.col("day").str.to_datetime().alias("timestamp"),
                pl.col("open").cast(pl.Decimal(10, 2)),
                pl.col("high").cast(pl.Decimal(10, 2)),
                pl.col("low").cast(pl.Decimal(10, 2)),
                pl.col("close").cast(pl.Decimal(10, 2)),
                pl.col("volume").cast(pl.Int64),
            )

            # 基础清洗
            result = result.filter(
                pl.col("open").is_not_null() & (pl.col("open") > 0) &
                pl.col("high").is_not_null() & (pl.col("high") > 0) &
                pl.col("low").is_not_null() & (pl.col("low") > 0) &
                pl.col("close").is_not_null() & (pl.col("close") > 0)
            )

            logger.debug("获取分钟行情成功", code=code, count=len(result))
            return result

        except Exception as e:
            logger.error("获取分钟行情失败", code=code, error=str(e))
            raise

    async def get_financial_statements(
        self,
        code: str,
        limit: int = 8,
    ) -> pl.DataFrame:
        """
        获取股票财务指标数据

        使用 stock_financial_abstract_ths 接口（同花顺数据源）
        返回最近 N 个报告期的财务数据

        Args:
            code: 股票代码
            limit: 返回最近 N 个报告期，默认 8 个（最近 2 年）

        Returns:
            包含财务指标的 Polars DataFrame
        """
        logger.debug("获取财务数据", code=code, limit=limit)

        try:
            # 调用 AkShare 接口（同花顺-业绩报表）
            df = await self._run_sync(
                ak.stock_financial_abstract_ths,
                symbol=code,
                indicator="业绩报表",
            )

            if df is None or df.empty:
                logger.warning("财务数据为空", code=code)
                return pl.DataFrame()

            # 在 Pandas 中处理报告期转换（YYYY → YYYY-12-31）
            df["end_date"] = df["报告期"].apply(
                lambda x: f"{x}-12-31" if len(str(x)) == 4 else str(x)
            )

            # 将所有列转换为字符串类型，避免 Polars 类型推断错误
            for col in df.columns:
                df[col] = df[col].astype(str)

            # 转换为 Polars DataFrame
            result = pl.from_pandas(df)

            # 在 Polars 中解析日期
            result = result.with_columns([
                pl.col("end_date").str.to_date("%Y-%m-%d").alias("end_date")
            ])

            # 过滤空日期
            result = result.filter(pl.col("end_date").is_not_null())

            # 首先，将所有相关列转换为字符串类型
            result = result.with_columns([
                pl.col(col).cast(pl.Utf8) for col in result.columns if col != "end_date" and col != "报告期" and col != "code"
            ])

            # 辅助函数：解析数值（处理百分比和中文单位）
            def parse_numeric_column(col_name: str, decimal_type: tuple = (20, 2)):
                """解析数值列，处理 X.XX亿、X.XX% 等格式"""
                # 使用 fill_null 处理 null 值，使用 str.replace_all 处理 False
                col = (
                    pl.col(col_name)
                    .fill_null("0")
                    .str.replace_all("False", "0")
                    .str.replace_all("%", "")
                    .str.replace_all("亿", "e8")  # 使用科学计数法
                    .str.replace_all("万", "e4")
                )

                # 转换为浮点数然后转decimal
                return (
                    col.cast(pl.Float64, strict=False)
                    .cast(pl.Decimal(decimal_type[0], decimal_type[1]))
                    .alias(col_name)
                )

            # 检查列是否存在（银行股没有毛利率）
            has_gross_margin = "销售毛利率" in result.columns

            # 规范化列名并映射到模型字段
            columns_to_add = [
                pl.lit(code).alias("code"),
                # 核心指标（金额单位：元，从亿转换）
                parse_numeric_column("营业总收入", (20, 2)),
                parse_numeric_column("净利润", (20, 2)),
                parse_numeric_column("扣非净利润", (20, 2)),
                parse_numeric_column("每股经营现金流", (10, 4)),
                # 盈利能力（百分比）
                parse_numeric_column("净资产收益率-摊薄", (10, 4)),
                parse_numeric_column("销售净利率", (10, 4)),
                # 成长能力（百分比）
                parse_numeric_column("营业总收入同比增长率", (10, 4)),
                parse_numeric_column("净利润同比增长率", (10, 4)),
                # 偿债与运营
                parse_numeric_column("资产负债率", (10, 4)),
                parse_numeric_column("基本每股收益", (10, 4)),
                parse_numeric_column("每股净资产", (10, 4)),
            ]

            # 只有非银行股才有毛利率
            if has_gross_margin:
                columns_to_add.insert(6, parse_numeric_column("销售毛利率", (10, 4)))

            result = result.with_columns(columns_to_add)

            # 重命名列以匹配模型
            select_columns = [
                pl.col("code"),
                pl.col("end_date"),
                pl.col("营业总收入").alias("total_revenue"),
                pl.col("净利润").alias("net_profit"),
                pl.col("扣非净利润").alias("deduct_net_profit"),
                pl.lit(None, dtype=pl.Decimal(20, 2)).alias("net_cash_flow_oper"),  # 占位，后续可补充
                pl.col("净资产收益率-摊薄").alias("roe_weighted"),
            ]

            # 如果有毛利率列，添加它；否则用 NULL
            if has_gross_margin:
                select_columns.append(pl.col("销售毛利率").alias("gross_profit_margin"))
            else:
                select_columns.append(pl.lit(None, dtype=pl.Decimal(10, 4)).alias("gross_profit_margin"))

            select_columns.extend([
                pl.col("销售净利率").alias("net_profit_margin"),
                pl.col("营业总收入同比增长率").alias("revenue_yoy"),
                pl.col("净利润同比增长率").alias("net_profit_yoy"),
                pl.col("资产负债率").alias("debt_asset_ratio"),
                pl.col("基本每股收益").alias("eps"),
                pl.col("每股净资产").alias("bps"),
            ])

            result = result.select(select_columns)

            # 按日期降序排序，取最近 N 个
            result = result.sort("end_date", descending=True).head(limit)

            # 添加报告类型（根据月份判断）
            result = result.with_columns(
                pl.when(pl.col("end_date").dt.month() == 3)
                .then(pl.lit("一季报"))
                .when(pl.col("end_date").dt.month() == 6)
                .then(pl.lit("中报"))
                .when(pl.col("end_date").dt.month() == 9)
                .then(pl.lit("三季报"))
                .when(pl.col("end_date").dt.month() == 12)
                .then(pl.lit("年报"))
                .otherwise(pl.lit("其他"))
                .alias("report_type")
            )

            logger.debug("获取财务数据成功", code=code, count=len(result))
            return result

        except Exception as e:
            logger.error("获取财务数据失败", code=code, error=str(e))
            raise

    async def enrich_stock_list_with_metadata(
        self, stock_df: pl.DataFrame
    ) -> pl.DataFrame:
        """
        为股票列表补充元数据（行业、上市日期等）

        策略:
        1. 少量股票 (< 100): 直接使用 stock_individual_info_em (快)
        2. 大量股票: 使用东方财富板块接口批量获取行业分类 (减少请求数)

        Args:
            stock_df: 股票列表 DataFrame（需包含 code 列）

        Returns:
            补充了元数据的 DataFrame
        """
        logger.info("开始补充股票元数据", count=len(stock_df))

        try:
            enriched = stock_df.clone()
            
            # 确保 industry 和 list_date 列存在
            if "industry" not in enriched.columns:
                enriched = enriched.with_columns(pl.lit(None, dtype=pl.Utf8).alias("industry"))
            if "list_date" not in enriched.columns:
                enriched = enriched.with_columns(pl.lit(None, dtype=pl.Date).alias("list_date"))

            # 1. 批量获取行业分类 (仅对大量股票使用)
            if len(stock_df) > 100:
                logger.info("标的数量较多，尝试批量获取行业分类")
                industry_map = {}
                try:
                    boards_df = await self._run_sync(ak.stock_board_industry_name_em)
                    for board_name in boards_df["板块名称"].to_list():
                        try:
                            cons_df = await self._run_sync(
                                ak.stock_board_industry_cons_em, symbol=board_name
                            )
                            for code in cons_df["代码"].to_list():
                                industry_map[code] = board_name
                        except Exception as e:
                            logger.warning(f"获取板块 {board_name} 成员失败: {e}")
                    
                    if industry_map:
                        industry_pl = pl.DataFrame(
                            {"code": list(industry_map.keys()), "industry_batch": list(industry_map.values())}
                        )
                        enriched = enriched.join(industry_pl, on="code", how="left")
                        enriched = enriched.with_columns(
                            pl.coalesce(["industry", "industry_batch"]).alias("industry")
                        ).drop("industry_batch")
                except Exception as e:
                    logger.error(f"批量获取行业分类失败: {e}")

            # 2. 针对仍缺失元数据的股票，逐个补充 (带并发控制)
            missing_metadata = enriched.filter(
                pl.col("industry").is_null() | pl.col("list_date").is_null()
            )

            if len(missing_metadata) > 0:
                logger.info(f"正在补充 {len(missing_metadata)} 只股票的详细元数据")
                
                # 并发控制：最多 5 个并发任务
                semaphore = asyncio.Semaphore(5)

                async def fetch_info(code):
                    async with semaphore:
                        try:
                            info_df = await self._run_sync(
                                ak.stock_individual_info_em, symbol=code
                            )
                            # 转换结果
                            info = dict(zip(info_df["item"], info_df["value"]))
                            
                            industry = info.get("行业")
                            list_date_str = info.get("上市时间")
                            
                            list_date = None
                            if list_date_str and len(str(list_date_str)) == 8:
                                try:
                                    list_date = datetime.strptime(str(list_date_str), "%Y%m%d").date()
                                except:
                                    pass
                                    
                            return {"code": code, "industry_new": industry, "list_date_new": list_date}
                        except Exception as e:
                            logger.debug(f"获取股票 {code} 详细信息失败: {e}")
                            return {"code": code, "industry_new": None, "list_date_new": None}

                tasks = [fetch_info(code) for code in missing_metadata["code"].to_list()]
                
                # 分批执行
                batch_size = 50
                results = []
                for i in range(0, len(tasks), batch_size):
                    batch = tasks[i:i+batch_size]
                    batch_results = await asyncio.gather(*batch)
                    results.extend(batch_results)
                    if i + batch_size < len(tasks):
                        await asyncio.sleep(0.5)

                # 更新结果
                if results:
                    details_df = pl.DataFrame(results)
                    # 确保 details_df 包含必要的列
                    for col in ["industry_new", "list_date_new"]:
                        if col not in details_df.columns:
                            details_df = details_df.with_columns(pl.lit(None).alias(col))
                    
                    enriched = enriched.join(details_df, on="code", how="left")
                    
                    enriched = enriched.with_columns([
                        pl.coalesce(["industry", "industry_new"]).alias("industry"),
                        pl.coalesce(["list_date", "list_date_new"]).alias("list_date"),
                    ]).drop(["industry_new", "list_date_new"])

            logger.info(
                "股票元数据补充完成",
                total=len(enriched),
                with_industry=enriched.filter(pl.col("industry").is_not_null()).height,
                with_list_date=enriched.filter(pl.col("list_date").is_not_null()).height,
            )

            return enriched

        except Exception as e:
            logger.error(f"补充股票元数据过程中发生未捕获异常: {e}")
            if "industry" not in stock_df.columns:
                stock_df = stock_df.with_columns(pl.lit(None, dtype=pl.Utf8).alias("industry"))
            if "list_date" not in stock_df.columns:
                stock_df = stock_df.with_columns(pl.lit(None, dtype=pl.Date).alias("list_date"))
            return stock_df

    async def get_realtime_quote(self, code: str) -> dict[str, Any]:
        """
        获取实时行情

        使用 stock_zh_a_spot_em 接口
        """
        logger.debug("获取实时行情", code=code)

        try:
            # 获取全市场实时行情
            df = await self._run_sync(ak.stock_zh_a_spot_em)

            # 筛选指定股票
            result = pl.from_pandas(df).filter(pl.col("代码") == code)

            if len(result) == 0:
                logger.warning("未找到股票实时行情", code=code)
                return {}

            row = result.row(0, named=True)

            return {
                "code": code,
                "name": row.get("名称"),
                "price": row.get("最新价"),
                "change": row.get("涨跌额"),
                "change_pct": row.get("涨跌幅"),
                "volume": row.get("成交量"),
                "amount": row.get("成交额"),
                "open": row.get("今开"),
                "high": row.get("最高"),
                "low": row.get("最低"),
                "pre_close": row.get("昨收"),
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error("获取实时行情失败", code=code, error=str(e))
            raise


# 全局单例
akshare_adapter = AkShareAdapter()
