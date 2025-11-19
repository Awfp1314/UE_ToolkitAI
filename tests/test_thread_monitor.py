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


def test_privacy_rule_redact(tmp_path: Path):
    """Test privacy rule with 'redact' action."""
    cfg = ThreadConfiguration(
        privacy_rules=[PrivacyRule(field="error_message", action="redact")]
    )
    monitor = ThreadMonitor(cfg)
    monitor.record_task_start("t1", "mod", "task", thread_id=1, thread_name="thread_1")
    monitor.record_task_failed("t1", "Sensitive error message")

    out = tmp_path / "events.ndjson"
    monitor.export_ndjson(out, apply_privacy=True)
    exported = json.loads(out.read_text(encoding="utf-8").strip())
    assert exported["error_message"] == "[REDACTED]"


def test_privacy_rule_mask_pattern(tmp_path: Path):
    """Test privacy rule with 'mask' action and pattern."""
    cfg = ThreadConfiguration(
        privacy_rules=[
            PrivacyRule(field="task_name", action="mask", pattern=r"secret_\w+")
        ]
    )
    monitor = ThreadMonitor(cfg)
    monitor.record_task_start("t1", "mod", "secret_task_123", thread_id=1, thread_name="thread_1")
    monitor.record_task_complete("t1", duration_ms=100)

    out = tmp_path / "events.ndjson"
    monitor.export_ndjson(out, apply_privacy=True)
    exported = json.loads(out.read_text(encoding="utf-8").strip())
    assert exported["task_name"] == "[MASKED]"


def test_ndjson_export_format(tmp_path: Path):
    """Test NDJSON export format with multiple events."""
    monitor = ThreadMonitor(make_config())

    # Record multiple events
    monitor.record_task_start("t1", "mod1", "task1", thread_id=1, thread_name="thread_1")
    monitor.record_task_complete("t1", duration_ms=100)

    monitor.record_task_start("t2", "mod2", "task2", thread_id=2, thread_name="thread_2")
    monitor.record_task_failed("t2", "Error message")

    # Export to NDJSON
    out = tmp_path / "events.ndjson"
    count = monitor.export_ndjson(out, apply_privacy=False)
    assert count == 2

    # Verify NDJSON format (one JSON object per line)
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2

    # Verify each line is valid JSON
    event1 = json.loads(lines[0])
    event2 = json.loads(lines[1])

    assert event1["task_id"] == "t1"
    assert event1["state"] == "completed"
    assert event1["duration_ms"] == 100

    assert event2["task_id"] == "t2"
    assert event2["state"] == "failed"
    assert event2["error_message"] == "Error message"


def test_export_without_privacy(tmp_path: Path):
    """Test export without applying privacy rules."""
    cfg = ThreadConfiguration(
        privacy_rules=[PrivacyRule(field="error_message", action="redact")]
    )
    monitor = ThreadMonitor(cfg)
    monitor.record_task_start("t1", "mod", "task", thread_id=1, thread_name="thread_1")
    monitor.record_task_failed("t1", "Sensitive error")

    out = tmp_path / "events.ndjson"
    monitor.export_ndjson(out, apply_privacy=False)
    exported = json.loads(out.read_text(encoding="utf-8").strip())

    # Error message should NOT be redacted
    assert exported["error_message"] == "Sensitive error"


def test_performance_benchmark_export(tmp_path: Path):
    """Performance benchmark: export 1000 events should take < 100ms."""
    import time

    monitor = ThreadMonitor(make_config())

    # Record 1000 events
    for i in range(1000):
        monitor.record_task_start(f"task_{i}", "mod", f"task_{i}", thread_id=i, thread_name=f"thread_{i}")
        if i % 2 == 0:
            monitor.record_task_complete(f"task_{i}", duration_ms=100)
        else:
            monitor.record_task_failed(f"task_{i}", "Error")

    # Measure export time
    out = tmp_path / "events.ndjson"
    start_time = time.time()
    count = monitor.export_ndjson(out, apply_privacy=False)
    duration_ms = (time.time() - start_time) * 1000

    assert count == 1000
    assert duration_ms < 100, f"Export took {duration_ms:.2f}ms, expected < 100ms"

    # Verify file was written correctly
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1000


def test_thread_safety(tmp_path: Path):
    """Test thread safety of ThreadMonitor."""
    import threading

    monitor = ThreadMonitor(make_config())

    def record_events(start_idx: int, count: int):
        for i in range(start_idx, start_idx + count):
            monitor.record_task_start(f"task_{i}", "mod", f"task_{i}", thread_id=i, thread_name=f"thread_{i}")
            monitor.record_task_complete(f"task_{i}", duration_ms=100)

    # Start 10 threads, each recording 10 events
    threads = []
    for i in range(10):
        t = threading.Thread(target=record_events, args=(i * 10, 10))
        threads.append(t)
        t.start()

    # Wait for all threads to complete
    for t in threads:
        t.join()

    # Verify all events were recorded
    metrics = monitor.get_metrics()
    assert metrics.total_tasks_executed == 100
    assert metrics.tasks_completed == 100
    assert len(monitor.events) == 100

