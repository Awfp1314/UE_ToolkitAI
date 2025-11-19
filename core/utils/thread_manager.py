"""Enhanced ThreadManager with queue-based backpressure, cancellation, and monitoring."""
from __future__ import annotations

import threading
import time
import uuid
from queue import Empty, Full, Queue
from typing import Callable, Dict, Optional, Tuple

from PyQt6.QtCore import QThread, QTimer

from core.config.thread_config import ThreadConfiguration
from core.logger import get_logger
from core.utils.thread_monitor import ThreadMonitor
from core.utils.thread_models import TaskInfo, ThreadInfo, ThreadState
from core.utils.thread_utils import CancellationToken, Worker

logger = get_logger(__name__)


class QueueFullError(Exception):
    """Raised when the task queue is full."""


class EnhancedThreadManager:
    """Enhanced thread manager with timeout, cancellation, and monitoring."""

    def __init__(self, config: ThreadConfiguration):
        self.config = config
        self.monitor = ThreadMonitor(config)
        self._task_queue: Queue = Queue(maxsize=config.task_queue_size)
        self._semaphore = threading.Semaphore(config.thread_pool_size)
        self._lock = threading.Lock()
        self._active_tasks: Dict[str, TaskInfo] = {}

    def run_in_thread(
        self,
        func: Callable,
        module_name: str,
        task_name: Optional[str] = None,
        timeout: Optional[int] = None,
        on_result: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        on_timeout: Optional[Callable] = None,
        *args,
        **kwargs,
    ) -> Tuple[Optional[QThread], Optional[Worker], str]:
        """Submit task with queue-based backpressure.

        Returns:
            (thread, worker, task_id) if started immediately; (None, None, task_id) if queued.
        Raises:
            QueueFullError: when queue at capacity.
        """
        task_id = str(uuid.uuid4())
        if task_name is None:
            task_name = func.__name__

        task_metadata = {
            "task_id": task_id,
            "module_name": module_name,
            "task_name": task_name,
            "func": func,
            "timeout": timeout,
            "on_result": on_result,
            "on_error": on_error,
            "on_timeout": on_timeout,
            "args": args,
            "kwargs": kwargs,
        }

        try:
            self._task_queue.put_nowait(task_metadata)
        except Full:
            logger.error("Task queue full (%s), rejecting %s.%s", self.config.task_queue_size, module_name, task_name)
            raise QueueFullError(f"Task queue at capacity ({self.config.task_queue_size})")

        if self._semaphore.acquire(blocking=False):
            task_metadata = self._task_queue.get_nowait()
            thread, worker = self._start_task(task_metadata)
            return thread, worker, task_id

        logger.debug("Task %s queued", task_id)
        return None, None, task_id

    def _start_task(self, meta: dict) -> Tuple[QThread, Worker]:
        task_id = meta["task_id"]
        module_name = meta["module_name"]
        task_name = meta["task_name"]
        func = meta["func"]
        timeout = meta.get("timeout")
        on_result = meta.get("on_result")
        on_error = meta.get("on_error")
        on_timeout = meta.get("on_timeout")
        args = meta.get("args", ())
        kwargs = meta.get("kwargs", {})

        worker = Worker(func, *args, **kwargs)
        thread = QThread()
        worker.moveToThread(thread)
        thread_name = f"{module_name}_{task_name}_{id(thread)}"
        thread.setObjectName(thread_name)

        # wire signals
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        if on_result:
            worker.result.connect(on_result)
        if on_error:
            worker.error.connect(on_error)
        worker.error.connect(lambda err: self._handle_task_error(task_id, err))

        # timeout handling
        timeout_timer = None
        if timeout and timeout > 0:
            timeout_timer = self._setup_timeout(task_id, worker, timeout, on_timeout)

        task_info = TaskInfo(
            task_id=task_id,
            module_name=module_name,
            task_name=task_name,
            thread=thread,
            worker=worker,
            cancel_token=worker.cancel_token,
            state=ThreadState.RUNNING,
            start_time=time.time(),
            timeout_ms=timeout,
            timeout_timer=timeout_timer,
            timeout_recorded=False,
        )

        with self._lock:
            self._active_tasks[task_id] = task_info

        self.monitor.record_task_start(task_id, module_name, task_name, thread_id=id(thread), thread_name=thread_name)
        thread.finished.connect(lambda: self._on_thread_finished(task_id))
        thread.start()
        return thread, worker

    def _handle_task_error(self, task_id: str, error_message: str):
        with self._lock:
            if task_id in self._active_tasks:
                self._active_tasks[task_id].state = ThreadState.FAILED
        self.monitor.record_task_failed(task_id, error_message)

    def _cleanup_task(self, task_id: str):
        with self._lock:
            task_info = self._active_tasks.pop(task_id, None)
        if not task_info:
            return

        if task_info.timeout_timer:
            task_info.timeout_timer.stop()

        if task_info.grace_timer:
            task_info.grace_timer.stop()

        duration_ms = int((time.time() - task_info.start_time) * 1000)
        if task_info.state == ThreadState.RUNNING:
            task_info.state = ThreadState.COMPLETED
            self.monitor.record_task_complete(task_id, duration_ms)
        elif task_info.state == ThreadState.CANCELLED:
            self.monitor.record_task_cancelled(task_id)
        elif task_info.state == ThreadState.TIMEOUT:
            if not task_info.timeout_recorded:
                self.monitor.record_task_timeout(task_id)
                task_info.timeout_recorded = True
        elif task_info.state == ThreadState.FAILED:
            # already recorded in _handle_task_error
            pass

    def _on_thread_finished(self, task_id: str):
        self._cleanup_task(task_id)
        self._semaphore.release()

        try:
            meta = self._task_queue.get_nowait()
        except Empty:
            return

        if self._semaphore.acquire(blocking=False):
            self._start_task(meta)
        else:
            # no slot, put back
            try:
                self._task_queue.put_nowait(meta)
            except Full:
                logger.warning("Queue full when re-queuing task %s", meta.get("task_id"))

    def _setup_timeout(self, task_id: str, worker: Worker, timeout_ms: int, on_timeout: Optional[Callable]) -> QTimer:
        timer = QTimer()
        timer.setSingleShot(True)

        def on_timeout_triggered():
            logger.warning("Task %s exceeded timeout %sms, requesting cancellation", task_id, timeout_ms)
            worker.cancel()

            grace_timer = QTimer()
            grace_timer.setSingleShot(True)

            def on_grace_expired():
                with self._lock:
                    info = self._active_tasks.get(task_id)
                    if info and info.state == ThreadState.RUNNING:
                        info.state = ThreadState.TIMEOUT
                        if not info.timeout_recorded:
                            self.monitor.record_task_timeout(task_id)
                            info.timeout_recorded = True
                        if on_timeout:
                            on_timeout()

            grace_timer.timeout.connect(on_grace_expired)
            grace_timer.start(self.config.grace_period)

            # Store grace_timer in TaskInfo to prevent garbage collection
            with self._lock:
                info = self._active_tasks.get(task_id)
                if info:
                    info.grace_timer = grace_timer

        timer.timeout.connect(on_timeout_triggered)
        timer.start(timeout_ms)
        return timer

    def cancel_task(self, task_id: str):
        # Active task
        with self._lock:
            info = self._active_tasks.get(task_id)
            if info:
                info.state = ThreadState.CANCELLED
                info.cancel_token.cancel()
                self.monitor.record_task_cancelled(task_id)
                return

        # Queued task: drain and requeue others
        drained = []
        found = False
        while True:
            try:
                meta = self._task_queue.get_nowait()
            except Empty:
                break
            if meta.get("task_id") == task_id:
                found = True
                continue
            drained.append(meta)

        for meta in drained:
            try:
                self._task_queue.put_nowait(meta)
            except Full:
                logger.warning("Queue full while re-queuing task %s", meta.get("task_id"))

        if found:
            # record cancellation for queued task
            # queued任务没有 start 事件，直接累加取消计数
            with self.monitor._lock:  # pylint: disable=protected-access
                self.monitor.metrics.tasks_cancelled += 1

    def get_active_threads(self) -> list[ThreadInfo]:
        with self._lock:
            return [
                ThreadInfo(
                    task_id=info.task_id,
                    module_name=info.module_name,
                    task_name=info.task_name,
                    thread_id=id(info.thread),
                    state=info.state.value,
                    elapsed_ms=int((time.time() - info.start_time) * 1000),
                    started_at=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(info.start_time)),  # type: ignore[arg-type]
                )
                for info in self._active_tasks.values()
            ]

    def cleanup(self, timeout_ms: Optional[int] = None) -> bool:
        if timeout_ms is None:
            timeout_ms = self.config.cleanup_timeout

        with self._lock:
            task_ids = list(self._active_tasks.keys())

        for task_id in task_ids:
            self.cancel_task(task_id)

        start = time.time()
        while self._active_tasks and (time.time() - start) * 1000 < timeout_ms:
            time.sleep(0.05)

        if self._active_tasks:
            logger.warning("%d tasks still active after cleanup timeout", len(self._active_tasks))
            return False
        return True


__all__ = ["EnhancedThreadManager", "QueueFullError"]


# Singleton accessor
_thread_manager_instance: Optional[EnhancedThreadManager] = None
_thread_manager_lock = threading.Lock()


def get_thread_manager() -> EnhancedThreadManager:
    """Get singleton ThreadManager instance (thread-safe)."""
    global _thread_manager_instance
    if _thread_manager_instance is None:
        with _thread_manager_lock:
            if _thread_manager_instance is None:
                config_path = Path("config/thread_config.json")
                try:
                    config = ThreadConfiguration.load_from_file(config_path)
                except FileNotFoundError:
                    config = ThreadConfiguration()
                _thread_manager_instance = EnhancedThreadManager(config)
    return _thread_manager_instance
from pathlib import Path
