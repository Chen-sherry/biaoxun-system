"""
日志初始化（基于 loguru）
"""
import sys
from loguru import logger

from app.config import settings


def setup_logger() -> None:
    """配置 loguru 日志格式与输出位置"""
    logger.remove()

    fmt = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    # 控制台
    logger.add(
        sys.stdout,
        level=settings.log_level,
        format=fmt,
        colorize=True,
    )

    # 文件（按天切割，保留 30 天）
    logger.add(
        f"{settings.log_dir}/app_{{time:YYYY-MM-DD}}.log",
        level=settings.log_level,
        format=fmt,
        rotation="00:00",
        retention="30 days",
        compression="zip",
        encoding="utf-8",
    )

    # 错误日志单独文件
    logger.add(
        f"{settings.log_dir}/error_{{time:YYYY-MM-DD}}.log",
        level="ERROR",
        format=fmt,
        rotation="00:00",
        retention="30 days",
        compression="zip",
        encoding="utf-8",
    )
