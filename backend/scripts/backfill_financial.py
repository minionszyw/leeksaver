#!/usr/bin/env python3
"""
财报数据回溯脚本

用途：回溯过去 N 年的财报数据到数据库
预计数据量：6790 只股票 × 12 季度 = 81,480 条记录（3 年）

执行方式：
    docker compose exec backend python scripts/backfill_financial.py [--years 3] [--batch-size 100]
"""

import asyncio
import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.datasources.akshare_adapter import akshare_adapter
from app.repositories.financial_repository import FinancialRepository
from app.repositories.stock_repository import StockRepository

logger = get_logger(__name__)


class FinancialBackfiller:
    """财报数据回溯器"""

    def __init__(self, years: int = 3, batch_size: int = 100):
        """
        初始化回溯器

        Args:
            years: 回溯年数
            batch_size: 批次大小（每处理多少只股票休息一次）
        """
        self.years = years
        self.batch_size = batch_size
        self.stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "records": 0,
            "skipped": 0,
        }
        self.failed_codes = []

    async def backfill(self, resume_from: str | None = None):
        """
        执行回溯

        Args:
            resume_from: 从指定股票代码恢复（断点续传）
        """
        # 获取所有股票代码
        async with get_db_session() as session:
            stock_repo = StockRepository(session)
            codes = await stock_repo.get_all_codes(asset_type="stock")

        self.stats["total"] = len(codes)

        # 断点续传：跳过已处理的股票
        if resume_from:
            try:
                resume_index = codes.index(resume_from)
                codes = codes[resume_index:]
                logger.info(f"从股票 {resume_from} 恢复，剩余 {len(codes)} 只")
            except ValueError:
                logger.warning(f"未找到股票代码 {resume_from}，从头开始")

        logger.info(
            f"开始回溯 {len(codes)} 只股票的 {self.years} 年财报数据..."
        )

        # 计算日期范围
        end_date = date.today()
        start_date = end_date - timedelta(days=365 * self.years)

        # 逐个处理股票
        for i, code in enumerate(codes):
            try:
                # 获取财报数据
                df = await akshare_adapter.get_financial_statements(
                    code=code, limit=self.years * 4  # 每年 4 个季度
                )

                if len(df) > 0:
                    async with get_db_session() as session:
                        repo = FinancialRepository(session)
                        records = df.to_dicts()
                        count = await repo.upsert_many(records)
                        await session.commit()

                    self.stats["success"] += 1
                    self.stats["records"] += count
                    logger.info(
                        f"[{i+1}/{self.stats['total']}] {code}: ✅ {count} 条财报"
                    )
                else:
                    self.stats["skipped"] += 1
                    logger.info(
                        f"[{i+1}/{self.stats['total']}] {code}: ⏭️  无财报数据"
                    )

            except Exception as e:
                self.stats["failed"] += 1
                self.failed_codes.append(code)
                logger.error(
                    f"[{i+1}/{self.stats['total']}] {code}: ❌ 失败 - {e}"
                )

            # 限频控制：每处理 batch_size 只股票休息一下
            if (i + 1) % self.batch_size == 0:
                logger.info(
                    f"已处理 {i+1}/{self.stats['total']} 只股票，休息 5 秒..."
                )
                await asyncio.sleep(5)

        # 打印总结
        self._print_summary()

    def _print_summary(self):
        """打印回溯总结"""
        logger.info("=" * 60)
        logger.info("财报数据回溯完成！")
        logger.info("=" * 60)
        logger.info(f"总股票数: {self.stats['total']}")
        logger.info(f"成功: {self.stats['success']} 只")
        logger.info(f"跳过（无数据）: {self.stats['skipped']} 只")
        logger.info(f"失败: {self.stats['failed']} 只")
        logger.info(f"总财报记录数: {self.stats['records']} 条")
        logger.info("=" * 60)

        if self.failed_codes:
            logger.warning("失败的股票代码：")
            for code in self.failed_codes[:20]:  # 只显示前 20 个
                logger.warning(f"  - {code}")
            if len(self.failed_codes) > 20:
                logger.warning(f"  ... 还有 {len(self.failed_codes) - 20} 只")

            # 保存失败列表到文件
            failed_file = Path(__file__).parent / "backfill_failed_codes.txt"
            with open(failed_file, "w") as f:
                f.write("\n".join(self.failed_codes))
            logger.info(f"失败列表已保存到: {failed_file}")


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="财报数据回溯脚本")
    parser.add_argument(
        "--years", type=int, default=3, help="回溯年数（默认 3 年）"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="批次大小（每处理多少只股票休息一次，默认 100）",
    )
    parser.add_argument(
        "--resume-from", type=str, help="从指定股票代码恢复（断点续传）"
    )

    args = parser.parse_args()

    backfiller = FinancialBackfiller(years=args.years, batch_size=args.batch_size)
    await backfiller.backfill(resume_from=args.resume_from)


if __name__ == "__main__":
    asyncio.run(main())
