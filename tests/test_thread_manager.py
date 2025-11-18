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
from core.utils.thread_models import ThreadState  # noqa: E402


def make_manager(pool: int = 1, queue_size: int = 1) -> EnhancedThreadManager:
    cfg = ThreadConfiguration(thread_pool_size=pool, task_queue_size=queue_size)
    return EnhancedThreadManager(cfg)


def test_queue_full_raises():
    mgr = make_manager(pool=0, queue_size=0)
    with pytest.raises(QueueFullError):
        mgr.run_in_thread(lambda: None, module_name="m", task_name="t")


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


def test_timeout_records_once(monkeypatch):
    mgr = make_manager(pool=1, queue_size=1)
    # Speed up timers by monkeypatching QTimer.start to call immediately
    class DummyTimer:
        def __init__(self):
            self._callback = None

        def setSingleShot(self, *_):
            pass

        def timeout_connect(self, fn):
            self._callback = fn

        def start(self, *_):
            if self._callback:
                self._callback()

        def stop(self):
            pass

    def fake_qtimer():
        t = DummyTimer()
        # shim to mimic signal connect
        def connect(fn):
            t.timeout_connect(fn)
        t.timeout = type("sig", (), {"connect": connect})
        return t

    monkeypatch.setattr("core.utils.thread_manager.QTimer", fake_qtimer)

    mgr._semaphore.acquire()
    # Provide long running task
    def task(cancel_token):
        time.sleep(0.01)
        return "ok"

    _, _, task_id = mgr.run_in_thread(task, module_name="m", task_name="t", timeout=1)
    mgr._semaphore.release()
    with mgr._lock:
        info = mgr._active_tasks.get(task_id)
        if info:
            info.state = ThreadState.TIMEOUT
            info.timeout_recorded = False
    mgr._cleanup_task(task_id)
    assert mgr.monitor.get_metrics().tasks_timeout == 1
