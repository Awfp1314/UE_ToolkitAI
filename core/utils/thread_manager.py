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
from core.exceptions import ThreadError
from core.utils.thread_monitor import ThreadMonitor
from core.utils.thread_models import TaskInfo, ThreadInfo, ThreadState, CancellationToken, Worker

logger = get_logger(__name__)


class QueueFullError(ThreadError):
    """Raised when the task queue is full."""
    pass


class EnhancedThreadManager:
    """Enhanced thread manager with timeout, cancellation, and monitoring."""

    def __init__(self, config: ThreadConfiguration):
        self.config = config
        self.monitor = ThreadMonitor(config)
        self._task_queue: Queue = Queue(maxsize=config.task_queue_size)
        self._semaphore = threading.Semaphore(config.thread_pool_size)
        self._lock = threading.Lock()
        self._active_tasks: Dict[str, TaskInfo] = {}
        self._pending_tokens: Dict[str, CancellationToken] = {}  # v5.2.1: 存储排队任务的 cancel_token

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

        # v5.2.1: 提前创建 cancel_token
        cancel_token = CancellationToken()

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
            "cancel_token": cancel_token,  # v5.2.1: 添加到 metadata
        }

        try:
            self._task_queue.put_nowait(task_metadata)
        except Full:
            logger.error(
                "Task queue full (capacity: %s/%s). Rejecting task: %s.%s. "
                "Consider increasing task_queue_size or reducing task submission rate.",
                self.config.task_queue_size,
                self.config.task_queue_size,
                module_name,
                task_name
            )
            raise QueueFullError(
                f"Task queue at capacity ({self.config.task_queue_size}). "
                f"Unable to queue task: {module_name}.{task_name}"
            )

        # v5.2.1: 存储到 _pending_tokens
        with self._lock:
            self._pending_tokens[task_id] = cancel_token

        if self._semaphore.acquire(blocking=False):
            task_metadata = self._task_queue.get_nowait()
            thread, worker = self._start_task(task_metadata)
            return thread, worker, task_id

        logger.debug("Task %s queued", task_id)
        return None, None, task_id

    def _start_task(self, meta: dict) -> Tuple[Optional[QThread], Optional[Worker]]:
        """Start a task or skip if already cancelled.
        
        v5.3.0: Fixed semaphore leak with try-finally pattern.
        Uses semaphore_acquired flag to track ownership transfer.
        Returns (None, None) for cancelled tasks.
        
        Raises:
            ThreadError: When task startup fails unexpectedly
        """
        semaphore_acquired = True  # Track semaphore ownership
        
        try:
            # Process cancelled tasks in a loop
            while True:
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
                cancel_token = meta.get("cancel_token")

                # Check if task is already cancelled
                if cancel_token and cancel_token.is_cancelled():
                    logger.debug(f"Task {task_id} cancelled before start, skipping")
                    
                    # Prevent duplicate monitoring count
                    with self._lock:
                        was_pending = self._pending_tokens.pop(task_id, None) is not None
                    
                    if was_pending:
                        self.monitor.record_task_cancelled(task_id)
                    
                    # Try to get next task from queue
                    try:
                        next_meta = self._task_queue.get_nowait()
                        meta = next_meta
                        continue  # Process next task
                    except Empty:
                        # No more tasks, semaphore will be released in finally
                        logger.debug("No more tasks in queue after cancelled task")
                        return None, None
                
                # Task not cancelled, proceed with start
                break

            # Create worker and thread
            logger.debug(f"Starting task {task_id}: {module_name}.{task_name}")
            
            try:
                worker = Worker(func, *args, external_cancel_token=cancel_token, **kwargs)
                thread = QThread()
                worker.moveToThread(thread)
                thread_name = f"{module_name}_{task_name}_{id(thread)}"
                thread.setObjectName(thread_name)
            except TypeError as e:
                logger.error(f"Invalid task arguments for {task_id}: {e}", exc_info=True)
                raise ThreadError(f"Invalid task arguments: {e}") from e
            except Exception as e:
                logger.error(f"Failed to create worker/thread for {task_id}: {e}", exc_info=True)
                raise ThreadError(f"Failed to create task worker: {e}") from e

            # Wire signals
            thread.started.connect(worker.run)
            worker.finished.connect(thread.quit)
            worker.finished.connect(worker.deleteLater)
            thread.finished.connect(thread.deleteLater)

            if on_result:
                worker.result.connect(on_result)
            if on_error:
                worker.error.connect(on_error)
            worker.error.connect(lambda err: self._handle_task_error(task_id, err))

            # Setup timeout handling
            timeout_timer = None
            if timeout and timeout > 0:
                timeout_timer = self._setup_timeout(task_id, worker, timeout, on_timeout)

            # Create task info
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

            # Register task as active
            with self._lock:
                self._active_tasks[task_id] = task_info
                self._pending_tokens.pop(task_id, None)

            # Record task start
            self.monitor.record_task_start(
                task_id, module_name, task_name, 
                thread_id=id(thread), thread_name=thread_name
            )
            
            # Connect cleanup handler and start thread
            thread.finished.connect(lambda: self._on_thread_finished(task_id))
            thread.start()
            
            # Semaphore ownership transferred to running task
            # It will be released in _on_thread_finished
            semaphore_acquired = False
            logger.debug(f"Task {task_id} started successfully, semaphore ownership transferred")
            
            return thread, worker
            
        except ThreadError:
            # Re-raise ThreadError
            logger.error(f"Thread error starting task {meta.get('task_id', 'unknown')}", exc_info=True)
            raise
        except Exception as e:
            # Log any unexpected errors during task startup
            logger.error(f"Unexpected error starting task {meta.get('task_id', 'unknown')}: {e}", exc_info=True)
            raise ThreadError(f"Unexpected error starting task: {e}") from e
            
        finally:
            # Release semaphore if ownership was not transferred to task
            if semaphore_acquired:
                self._semaphore.release()
                logger.debug(f"Semaphore released in finally block for task {meta.get('task_id', 'unknown')}")

    def _handle_task_error(self, task_id: str, error_message: str):
        with self._lock:
            if task_id in self._active_tasks:
                self._active_tasks[task_id].state = ThreadState.FAILED
        self.monitor.record_task_failed(task_id, error_message)

    def _cleanup_task(self, task_id: str):
        """Clean up task resources.
        
        v5.2.1: Also removes from _pending_tokens (defensive).
        """
        with self._lock:
            task_info = self._active_tasks.pop(task_id, None)
            self._pending_tokens.pop(task_id, None)  # v5.2.1: 防御性清理
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
        logger.debug(f"Semaphore released after task {task_id} finished")

        try:
            meta = self._task_queue.get_nowait()
            logger.debug(f"Retrieved next task from queue: {meta.get('task_id', 'unknown')}")
        except Empty:
            logger.debug("No tasks in queue, semaphore slot remains available")
            return

        if self._semaphore.acquire(blocking=False):
            logger.debug(f"Semaphore acquired for next task: {meta.get('task_id', 'unknown')}")
            thread, worker = self._start_task(meta)
            # If _start_task returns (None, None), semaphore was already released
            if thread is None and worker is None:
                logger.debug("Task startup returned None, semaphore already released")
        else:
            # No slot available, put task back in queue
            try:
                self._task_queue.put_nowait(meta)
                logger.debug(f"No semaphore slot available, re-queued task: {meta.get('task_id', 'unknown')}")
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
        """Cancel a task by ID.
        
        v5.2.1: Fixes monitoring count for window-period cancellations.
        Counts cancellation if token exists, regardless of queue status.
        """
        # 1. Check active tasks
        with self._lock:
            info = self._active_tasks.get(task_id)
            if info:
                info.state = ThreadState.CANCELLED
                info.cancel_token.cancel()
                self.monitor.record_task_cancelled(task_id)
                return

        # 2. Handle queued tasks - v5.2.1: 先弹出 _pending_tokens 并记录状态
        cancel_token = None
        with self._lock:
            cancel_token = self._pending_tokens.pop(task_id, None)
        
        # 如果 token 存在，标记为已取消
        if cancel_token:
            cancel_token.cancel()

        # 3. 尝试从队列中移除任务
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

        # 重新入队其他任务
        for meta in drained:
            try:
                self._task_queue.put_nowait(meta)
            except Full:
                logger.warning("Queue full while re-queuing task %s", meta.get("task_id"))

        # 4. v5.2.1: 精确计数
        if cancel_token:
            # cancel_token 存在说明任务确实是排队状态
            # 无论是否在队列中找到，都应该计数
            with self.monitor._lock:  # pylint: disable=protected-access
                self.monitor.metrics.tasks_cancelled += 1
            
            if not found:
                # v5.2.1: 特殊情况 - 任务已从队列取出但还未启动
                logger.debug(f"任务 {task_id} 已从队列取出但还未启动（取消成功）")
        elif found:
            # 理论上不应该发生（token 已被清理但任务还在队列）
            # 防御性计数
            logger.warning(f"任务 {task_id} 在队列中找到但 token 已被清理（异常情况）")
            with self.monitor._lock:  # pylint: disable=protected-access
                self.monitor.metrics.tasks_cancelled += 1

    def get_cancel_token(self, task_id: str) -> Optional[CancellationToken]:
        """Get cancel token for a task.
        
        Args:
            task_id: Task ID
            
        Returns:
            CancellationToken if task exists, None otherwise
            
        Thread-safe: Yes
        
        v5.2.1: Supports both queued and active tasks.
        """
        with self._lock:
            # 1. Check queued tasks
            if task_id in self._pending_tokens:
                return self._pending_tokens[task_id]
            
            # 2. Check active tasks
            info = self._active_tasks.get(task_id)
            if info:
                return info.cancel_token
            
            # 3. Task not found
            logger.warning(f"无法找到任务的取消令牌: {task_id}")
            return None

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

    def get_semaphore_status(self) -> dict:
        """Get current semaphore status for monitoring.
        
        Returns:
            Dictionary with semaphore statistics:
            - total_slots: Total thread pool size
            - available_slots: Currently available slots (approximate)
            - active_tasks: Number of active tasks
            - queued_tasks: Number of queued tasks
            - pending_tasks: Number of pending tasks (queued but not started)
        """
        with self._lock:
            active_count = len(self._active_tasks)
            pending_count = len(self._pending_tokens)
        
        queued_count = self._task_queue.qsize()
        
        # Approximate available slots (may not be exact due to race conditions)
        # This is the configured pool size minus active tasks
        available_slots = max(0, self.config.thread_pool_size - active_count)
        
        status = {
            "total_slots": self.config.thread_pool_size,
            "available_slots": available_slots,
            "active_tasks": active_count,
            "queued_tasks": queued_count,
            "pending_tasks": pending_count,
        }
        
        logger.debug(
            f"Semaphore status: {available_slots}/{self.config.thread_pool_size} slots available, "
            f"{active_count} active, {queued_count} queued, {pending_count} pending"
        )
        
        return status

    def cleanup(self, timeout_ms: Optional[int] = None) -> bool:
        if timeout_ms is None:
            timeout_ms = self.config.cleanup_timeout

        with self._lock:
            task_ids = list(self._active_tasks.keys())

        for task_id in task_ids:
            self.cancel_task(task_id)

        start = time.time()
        while self._active_tasks and (time.time() - start) * 1000 < timeout_ms:
            time.sleep(0.05)  # 50ms polling interval

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
