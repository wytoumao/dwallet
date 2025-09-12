# core/logger.py
import logging
import sys
from typing import Optional

# 全局logger实例
_logger: Optional[logging.Logger] = None

def get_logger() -> logging.Logger:
    """获取全局logger实例"""
    global _logger
    if _logger is None:
        _logger = setup_logger()
    return _logger

def setup_logger(
    name: str = "dwallet",
    level: int = logging.INFO,
    format_str: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
) -> logging.Logger:
    """
    设置全局logger配置

    Args:
        name: logger名称
        level: 日志级别 (DEBUG=10, INFO=20, WARNING=30, ERROR=40)
        format_str: 日志格式
    """
    logger = logging.getLogger(name)

    # 如果已经有handler，先清除
    if logger.handlers:
        logger.handlers.clear()

    # 创建控制台handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    # 设置格式
    formatter = logging.Formatter(format_str)
    handler.setFormatter(formatter)

    # 添加handler到logger
    logger.addHandler(handler)
    logger.setLevel(level)

    # 防止日志向上传播（避免重复输出）
    logger.propagate = False

    global _logger
    _logger = logger
    return logger

def set_log_level(level: int):
    """动态修改日志级别"""
    logger = get_logger()
    logger.setLevel(level)
    for handler in logger.handlers:
        handler.setLevel(level)

def enable_debug():
    """启用DEBUG级别日志"""
    set_log_level(logging.DEBUG)

def disable_debug():
    """禁用DEBUG级别日志，只显示INFO及以上"""
    set_log_level(logging.INFO)
