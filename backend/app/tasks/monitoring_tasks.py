"""
监控相关的 Celery 任务
"""

from celery import shared_task

from app.core.logging import get_logger

logger = get_logger(__name__)


@shared_task(name="daily_data_health_check")
def daily_health_check():
    """
    每日数据健康巡检任务

    执行时间：根据配置执行 (环境变量 HEALTH_CHECK_HOUR/MINUTE)
    功能：检查数据覆盖率、新鲜度、完整性、质量 (Data Doctor Pro)
    """
    import asyncio
    from app.monitoring.data_doctor import data_doctor

    logger.info("开始执行每日数据健康巡检")

    try:
        # 运行异步巡检
        results = asyncio.run(data_doctor.run_daily_health_check())

        # 统计结果
        critical_count = sum(1 for r in results if r.status == "critical")
        warning_count = sum(1 for r in results if r.status == "warning")
        healthy_count = sum(1 for r in results if r.status == "healthy")

        logger.info(
            f"数据健康巡检完成: 健康 {healthy_count}, 警告 {warning_count}, 严重 {critical_count}"
        )

        return {
            "success": True,
            "total_checks": len(results),
            "healthy": healthy_count,
            "warning": warning_count,
            "critical": critical_count,
        }

    except Exception as e:
        logger.error(f"数据健康巡检失败: {e}")
        return {"success": False, "error": str(e)}
