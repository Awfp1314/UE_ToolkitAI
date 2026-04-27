"""Thread-related data classes used by the unified ThreadManager."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Union, Callable, Any
from enum import Enum
import traceback
import inspect

from PyQt6.QtCore import QThread, QTimer, QObject, pyqtSignal
from core.logger import get_logger

logger = get_logger(__name__)


class CancellationToken:
    """取消令牌 - 用于在任务函数中检查是否被取消

    使用示例:
        def long_task(cancel_token):
            for i in range(100):
                if cancel_token.is_cancelled():
                    return None  # 提前退出
                # 执行耗时操作
                time.sleep(0.1)
            return "完成"
    """

    def __init__(self):
        self._is_cancelled = False

    def cancel(self) -> None:
        """标记为已取消"""
        self._is_cancelled = True

    def is_cancelled(self) -> bool:
        """检查是否已取消

        Returns:
            bool: True表示已取消
        """
        return self._is_cancelled


class Worker(QObject):
    """通用工作线程

    支持协作式取消：任务函数需要主动检查 cancel_token.is_cancelled()

    使用示例:
        # 1. 编写可取消的任务函数
        def long_task(cancel_token, n):
            for i in range(n):
                if cancel_token.is_cancelled():
                    logger.info("任务被取消")
                    return None
                time.sleep(1)
            return "完成"

        # 2. 运行任务
        thread, worker = thread_manager.run_in_thread(long_task, n=10)

        # 3. 取消任务
        worker.cancel()
    """

    finished = pyqtSignal()
    error = pyqtSignal(str)
    result = pyqtSignal(object)
    progress = pyqtSignal(int)  # 进度信号 (0-100)

    def __init__(self, func: Callable, *args, external_cancel_token: Optional[CancellationToken] = None, **kwargs):
        """初始化Worker

        Args:
            func: 要执行的函数（如果第一个参数名为 cancel_token，会自动注入取消令牌）
            *args: 函数的位置参数
            external_cancel_token: 外部提供的取消令牌（v5.2.1新增）
            **kwargs: 函数的关键字参数
        """
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
        
        # v5.2.1: 优先使用外部 token，否则创建新的
        if external_cancel_token is not None:
            self.cancel_token = external_cancel_token
        else:
            self.cancel_token = CancellationToken()

        # 检查函数是否接受 cancel_token 参数
        sig = inspect.signature(func)
        self._supports_cancellation = 'cancel_token' in sig.parameters

    def run(self) -> None:
        """执行任务"""
        try:
            logger.debug(f"开始执行任务: {self.func.__name__}")

            # 如果函数支持取消令牌，自动注入
            if self._supports_cancellation:
                result = self.func(self.cancel_token, *self.args, **self.kwargs)
            else:
                result = self.func(*self.args, **self.kwargs)

            if not self.cancel_token.is_cancelled():
                self.result.emit(result)
                logger.debug(f"任务完成: {self.func.__name__}")
            else:
                logger.debug(f"任务被取消: {self.func.__name__}")
        except Exception as e:
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            logger.error(f"任务执行失败: {self.func.__name__}, 错误: {error_msg}")
            self.error.emit(error_msg)
        finally:
            # 始终发出 finished，便于上层清理和状态同步
            self.finished.emit()

    def cancel(self) -> None:
        """取消任务

        注意：这是协作式取消，任务函数需要主动检查 cancel_token.is_cancelled()
        如果任务函数不检查取消标志，任务仍会继续执行。
        """
        self.cancel_token.cancel()
        logger.debug(f"任务取消请求已发送: {self.func.__name__}")


class ThreadState(Enum):
    QUEUED = "queued"
    STARTING = "starting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class TaskInfo:
    task_id: str
    module_name: str
    task_name: str
    thread: QThread
    worker: Worker
    cancel_token: CancellationToken
    state: ThreadState
    start_time: float
    timeout_ms: Optional[int]
    timeout_timer: Optional[QTimer] = None
    grace_timer: Optional[QTimer] = None  # Grace period timer to prevent GC
    timeout_recorded: bool = False


@dataclass
class ThreadInfo:
    task_id: str
    module_name: str
    task_name: str
    thread_id: int
    state: str
    elapsed_ms: int
    started_at: str


__all__ = [
    "CancellationToken",
    "Worker",
    "ThreadState",
    "TaskInfo",
    "ThreadInfo",
]
