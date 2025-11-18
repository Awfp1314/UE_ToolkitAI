import json
import sys
from pathlib import Path

import pytest

# Ensure project root on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config.thread_config import PrivacyRule, ThreadConfiguration  # noqa: E402
from core.utils.thread_monitor import (  # noqa: E402
    ThreadLifecycleEvent,
    ThreadMetrics,
    ThreadMonitor,
)


def make_config(with_privacy: bool = False) -> ThreadConfiguration:
    rules = [PrivacyRule(field="error_message", action="mask", pattern="token=[^&\\s]+")] if with_privacy else []
    return ThreadConfiguration(privacy_rules=rules)


def test_record_and_metrics_update(tmp_path: Path):
    monitor = ThreadMonitor(make_config())
    monitor.record_task_start("t1", "mod", "task", thread_id=1, thread_name="mod_task_1")
    monitor.record_task_complete("t1", duration_ms=123)

    metrics = monitor.get_metrics()
    assert metrics.total_tasks_executed == 1
    assert metrics.tasks_completed == 1
    assert metrics.tasks_failed == 0
    assert metrics.tasks_cancelled == 0
    assert metrics.tasks_timeout == 0

    # Export and inspect content
    out = tmp_path / "events.ndjson"
    count = monitor.export_ndjson(out)
    assert count == 1
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    event = json.loads(lines[0])
    assert event["task_id"] == "t1"
    assert event["state"] == "completed"
    assert event["duration_ms"] == 123


def test_failure_and_cancellation_tracking():
    monitor = ThreadMonitor(make_config())
    monitor.record_task_start("t2", "mod", "task", thread_id=2, thread_name="mod_task_2")
    monitor.record_task_failed("t2", "boom")
    monitor.record_task_start("t3", "mod", "task", thread_id=3, thread_name="mod_task_3")
    monitor.record_task_cancelled("t3")
    monitor.record_task_start("t4", "mod", "task", thread_id=4, thread_name="mod_task_4")
    monitor.record_task_timeout("t4")

    metrics = monitor.get_metrics()
    assert metrics.tasks_failed == 1
    assert metrics.tasks_cancelled == 1
    assert metrics.tasks_timeout == 1
    assert metrics.total_tasks_executed == 3


def test_privacy_rules_applied(tmp_path: Path):
    cfg = make_config(with_privacy=True)
    monitor = ThreadMonitor(cfg)
    monitor.record_task_start("t5", "mod", "task", thread_id=5, thread_name="mod_task_5")
    monitor.record_task_failed("t5", "oops token=secret123")

    out = tmp_path / "events.ndjson"
    monitor.export_ndjson(out, apply_privacy=True)
    exported = json.loads(out.read_text(encoding="utf-8").strip())
    assert exported["error_message"] == "oops [MASKED]"

