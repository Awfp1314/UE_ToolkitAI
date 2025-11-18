import sys
from pathlib import Path

# Ensure project root on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.utils.thread_utils import Worker  # noqa: E402


def test_worker_emits_result_on_success():
    captured = []
    finished = []

    def task():
        return "ok"

    worker = Worker(task)
    worker.result.connect(lambda r: captured.append(r))
    worker.finished.connect(lambda: finished.append(True))

    worker.run()

    assert captured == ["ok"]
    assert finished == [True]


def test_worker_emits_error_on_exception():
    errors = []
    finished = []

    def task():
        raise ValueError("boom")

    worker = Worker(task)
    worker.error.connect(lambda e: errors.append(e))
    worker.finished.connect(lambda: finished.append(True))

    worker.run()

    assert len(errors) == 1
    assert finished == [True]


def test_worker_cancellation_prevents_result():
    captured = []
    finished = []

    def task(cancel_token):
        if cancel_token.is_cancelled():
            return "should_not_emit"
        return "ok"

    worker = Worker(task)
    worker.result.connect(lambda r: captured.append(r))
    worker.finished.connect(lambda: finished.append(True))

    worker.cancel()
    worker.run()

    assert captured == []
    # cancellation path should still emit finished to allow cleanup
    assert finished == [True]
