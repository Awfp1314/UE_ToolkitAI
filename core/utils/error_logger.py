# -*- coding: utf-8 -*-

"""
错误日志工具模块
提供统一的错误日志和信号发射方法
"""

import logging
from typing import Optional

from PyQt6.QtCore import pyqtSignal


def log_and_emit_error(
    logger: logging.Logger,
    signal: pyqtSignal,
    message: str,
    exception: Optional[Exception] = None
) -> None:
    """记录错误日志并发射错误信号
    
    这是一个通用的错误处理函数，用于减少重复的错误日志和信号发射代码
    
    Args:
        logger: 日志记录器
        signal: PyQt信号对象（用于发射错误消息）
        message: 错误消息
        exception: 可选的异常对象（如果提供，将记录完整堆栈跟踪）
        
    Examples:
        >>> log_and_emit_error(
        ...     logger,
        ...     self.error_occurred,
        ...     "Failed to load config",
        ...     exception=e
        ... )
    """
    if exception:
        # 记录完整的异常信息和堆栈跟踪
        logger.error(f"{message}: {exception}", exc_info=True)
        # 发射信号时包含异常信息
        signal.emit(f"{message}: {str(exception)}")
    else:
        # 只记录消息
        logger.error(message)
        signal.emit(message)


def log_and_raise(
    logger: logging.Logger,
    exception_class: type,
    message: str,
    cause: Optional[Exception] = None
) -> None:
    """记录错误日志并抛出异常
    
    这是一个通用的错误处理函数，用于减少重复的日志记录和异常抛出代码
    
    Args:
        logger: 日志记录器
        exception_class: 要抛出的异常类
        message: 错误消息
        cause: 可选的原始异常（用于异常链）
        
    Raises:
        exception_class: 指定类型的异常
        
    Examples:
        >>> log_and_raise(
        ...     logger,
        ...     ConfigError,
        ...     "Invalid configuration format",
        ...     cause=e
        ... )
    """
    if cause:
        # 记录完整的异常信息
        logger.error(f"{message}: {cause}", exc_info=True)
        # 抛出新异常，保留异常链
        raise exception_class(message) from cause
    else:
        # 只记录消息
        logger.error(message)
        # 抛出异常
        raise exception_class(message)


def log_warning_and_emit(
    logger: logging.Logger,
    signal: pyqtSignal,
    message: str
) -> None:
    """记录警告日志并发射信号
    
    Args:
        logger: 日志记录器
        signal: PyQt信号对象
        message: 警告消息
    """
    logger.warning(message)
    signal.emit(message)


def log_info_and_emit(
    logger: logging.Logger,
    signal: pyqtSignal,
    message: str
) -> None:
    """记录信息日志并发射信号
    
    Args:
        logger: 日志记录器
        signal: PyQt信号对象
        message: 信息消息
    """
    logger.info(message)
    signal.emit(message)


__all__ = [
    "log_and_emit_error",
    "log_and_raise",
    "log_warning_and_emit",
    "log_info_and_emit"
]
