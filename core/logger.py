"""
日志配置 - 统一的日志系统
"""

import logging
import sys
from typing import Optional


def get_logger(
    name: str,
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    format_string: Optional[str] = None,
) -> logging.Logger:
    """
    获取配置的日志记录器

    Args:
        name: 日志记录器名称（通常是模块名）
        level: 日志级别
        log_file: 日志文件路径（不指定则输出到控制台）
        format_string: 日志格式字符串

    Returns:
        配置好的 Logger 实例
    """
    logger = logging.getLogger(name)

    # 如果已经配置过，直接返回
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # 默认格式 - 简洁模式，适合终端显示
    if format_string is None:
        format_string = "[%(levelname)s] %(name)s: %(message)s"

    formatter = logging.Formatter(format_string, datefmt="%Y-%m-%d %H:%M:%S")

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件处理器（如果指定了日志文件）
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def setup_root_logger(
    level: int = logging.INFO,
    log_file: Optional[str] = None,
) -> None:
    """
    配置根日志记录器

    Args:
        level: 日志级别
        log_file: 日志文件路径
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # 清除现有处理器
    root_logger.handlers.clear()

    format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    formatter = logging.Formatter(format_string, datefmt="%Y-%m-%d %H:%M:%S")

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 文件处理器（如果指定了日志文件）
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)


# 常用日志级别别名
DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL
