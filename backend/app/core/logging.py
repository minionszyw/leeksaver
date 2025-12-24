"""
日志配置模块

使用 structlog 进行结构化日志记录
"""

import logging
import sys

import structlog

from app.config import settings


def setup_logging() -> None:
    """配置日志系统"""

    # 设置日志级别
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # 配置 structlog 处理器
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.ExtraAdder(),
    ]

    if settings.log_format == "json":
        # JSON 格式 (生产环境)
        processors = shared_processors + [
            structlog.processors.JSONRenderer(),
        ]
    else:
        # 控制台友好格式 (开发环境)
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # 配置标准库 logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # 降低第三方库日志级别
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str = __name__) -> structlog.stdlib.BoundLogger:
    """获取 logger 实例"""
    return structlog.get_logger(name)
