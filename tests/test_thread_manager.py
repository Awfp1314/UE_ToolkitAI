import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config.thread_config import ThreadConfiguration  # noqa: E402
from core.utils.thread_manager import (  # noqa: E402
    EnhancedThreadManager,
    QueueFullError,
)
from core.utils.thread_models import ThreadState, TaskInfo  # noqa: E402


def make_manager(pool: int = 1, queue_size: int = 1) -> EnhancedThreadManager:
    cfg = ThreadConfiguration(thread_pool_size=pool, task_queue_size=queue_size)
    return EnhancedThreadManager(cfg)


def test_queue_full_raises():
    mgr = make_manager(pool=1, queue_size=1)
    # 占用线程槽，确保后续任务入队
    mgr._semaphore.acquire()
    # 填满队列
    mgr.run_in_thread(lambda: None, module_name="m", task_name="t")
    with pytest.raises(QueueFullError):
        mgr.run_in_thread(lambda: None, module_name="m", task_name="t2")
    mgr._semaphore.release()


def test_cancel_queued_task():
    mgr = make_manager(pool=1, queue_size=1)
    # Occupy semaphore to force queue
    mgr._semaphore.acquire()
    _, _, task_id = mgr.run_in_thread(lambda: None, module_name="m", task_name="t")
    assert not mgr._task_queue.empty()
    mgr.cancel_task(task_id)
    assert mgr._task_queue.empty()
    metrics = mgr.monitor.get_metrics()
    assert metrics.tasks_cancelled == 1
    # release the semaphore to avoid leaking
    mgr._semaphore.release()


def test_timeout_records_once():
    """Test that ThreadManager's timeout_recorded flag prevents duplicate timeout recording."""
    from PyQt6.QtCore import QThread
    from core.utils.thread_utils import Worker, CancellationToken

    mgr = make_manager(pool=1, queue_size=1)

    # Create a fake task in active_tasks
    task_id = "test-timeout-task-123"

    # Create minimal QThread and Worker for testing
    thread = QThread()
    worker = Worker(lambda: "test")
    cancel_token = CancellationToken()

    task_info = TaskInfo(
        task_id=task_id,
        module_name="m",
        task_name="t",
        thread=thread,
        worker=worker,
        cancel_token=cancel_token,
        state=ThreadState.TIMEOUT,
        start_time=time.time(),
        timeout_ms=1000,
        timeout_timer=None,
        timeout_recorded=False  # Not yet recorded
    )

    # Add to active tasks
    with mgr._lock:
        mgr._active_tasks[task_id] = task_info

    # Record start event for the monitor
    mgr.monitor.record_task_start(task_id, "m", "t", thread_id=1, thread_name="m_t_1")

    # First cleanup - should record timeout
    mgr._cleanup_task(task_id)
    assert mgr.monitor.get_metrics().tasks_timeout == 1

    # Re-add the task with timeout_recorded=True
    task_info.timeout_recorded = True
    with mgr._lock:
        mgr._active_tasks[task_id] = task_info

    # Second cleanup - should NOT record timeout again (already recorded)
    mgr._cleanup_task(task_id)

    # Should still be 1, not 2
    metrics = mgr.monitor.get_metrics()
    assert metrics.tasks_timeout == 1
