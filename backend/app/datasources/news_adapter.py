import asyncio
from datetime import datetime, date
from typing import Optional, List, Any
import akshare as ak
import polars as pl
import pandas as pd
import json
from app.core.logging import get_logger
from app.datasources.rate_limiter import akshare_limiter

logger = get_logger(__name__)

def json_safe_dict(d: dict) -> dict:
    """递归确保字典内容可以被 JSON 序列化 (支持 date, datetime, time, Timestamp)"""
    from datetime import datetime, date, time
    safe_dict = {}
    for k, v in d.items():
        if isinstance(v, (datetime, date, time, pd.Timestamp)):
            safe_dict[k] = v.isoformat()
        elif isinstance(v, dict):
            safe_dict[k] = json_safe_dict(v)
        elif isinstance(v, (list, tuple)):
            safe_dict[k] = [
                json_safe_dict(i) if isinstance(i, dict) 
                else (i.isoformat() if hasattr(i, 'isoformat') else i) 
                for i in v
            ]
        elif pd.isna(v):
            safe_dict[k] = None
        else:
            safe_dict[k] = v
    return safe_dict

class NewsAdapter:
    def __init__(self):
        self._loop = asyncio.get_event_loop()

    async def _run_sync(self, func, *args, **kwargs):
        async with akshare_limiter:
            return await asyncio.to_thread(func, *args, **kwargs)

    async def get_market_news(self, limit: int = 100) -> List[dict]:
        """获取财联社全市电报"""
        logger.info("获取财联社电报新闻", limit=limit)
        try:
            df = await self._run_sync(ak.stock_info_global_cls)
            if df is None or df.empty:
                return []

            df = df.rename(columns={
                "标题": "title",
                "内容": "content",
                "发布日期": "publish_date",
                "发布时间": "publish_clock",
            })
            
            df["publish_time"] = pd.to_datetime(df["publish_date"].astype(str) + " " + df["publish_clock"].astype(str))
            
            # 移除 adapter 层的时间过滤，由 syncer 层决定增量逻辑
            df = df.sort_values("publish_time", ascending=False).head(limit)
            
            articles = []
            for _, row in df.iterrows():
                unique_key = f"{row['publish_time']}{row['title']}"
                
                # 转换 importance_level
                raw_level = row.get("level", 1)
                try:
                    importance_level = int(raw_level)
                except (ValueError, TypeError):
                    importance_level = 1 # 默认值
                
                # 序列化清理 raw_data
                raw_data = row.to_dict()
                clean_raw_data = json_safe_dict(raw_data)

                articles.append({
                    "title": row["title"] if row["title"] and not pd.isna(row["title"]) else "无标题电报",
                    "content": row["content"],
                    "source": "财联社",
                    "publish_time": row["publish_time"],
                    "url": f"https://www.cls.cn/flash/{unique_key}",
                    "importance_level": importance_level,
                    "related_stocks": None,
                    "keywords": None,
                    "cls_id": None,
                    "raw_data": clean_raw_data
                })
            return articles
        except Exception as e:
            logger.error("获取财联社电报失败", error=str(e))
            raise

    async def get_stock_news(self, code: str, limit: int = 20) -> pl.DataFrame:
        """获取个股新闻 (东方财富)"""
        try:
            df = await self._run_sync(ak.stock_news_em, symbol=code)
            if df is None or df.empty:
                return pl.DataFrame()

            result = pl.from_pandas(df)
            result = result.rename({
                "新闻标题": "title",
                "新闻内容": "content",
                "发布时间": "publish_time",
                "文章来源": "source",
                "新闻链接": "url",
                "关键词": "keywords",
            })

            result = result.with_columns([
                pl.col("publish_time").str.to_datetime("%Y-%m-%d %H:%M:%S", strict=False),
                pl.lit(code).alias("stock_code")
            ])
            
            return result.select([
                "title", "content", "source", "publish_time", "url", "stock_code", "keywords"
            ]).sort("publish_time", descending=True).head(limit)
        except Exception as e:
            logger.error(f"获取个股新闻失败: {code}", error=str(e))
            return pl.DataFrame()

    async def get_batch_stock_news(self, codes: List[str], limit_per_stock: int = 10) -> pl.DataFrame:
        all_news = []
        for code in codes:
            df = await self.get_stock_news(code, limit=limit_per_stock)
            if not df.is_empty():
                all_news.append(df)
            await asyncio.sleep(0.3)
        
        if not all_news:
            return pl.DataFrame()
        
        return pl.concat(all_news).unique(subset=["url"])

news_adapter = NewsAdapter()
