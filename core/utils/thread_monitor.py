"""Thread monitoring and metrics collection with privacy-aware export."""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from core.config.thread_config import PrivacyRule, ThreadConfiguration


@dataclass
class ThreadLifecycleEvent:
    task_id: str
    module_name: str
    task_name: str
    thread_id: int
    thread_name: str
    state: str  # 'started', 'completed', 'failed', 'cancelled', 'timeout'
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "module_name": self.module_name,
            "task_name": self.task_name,
            "thread_id": self.thread_id,
            "thread_name": self.thread_name,
            "state": self.state,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "error_message": self.error_message,
        }


@dataclass
class ThreadMetrics:
    total_tasks_executed: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    tasks_cancelled: int = 0
    tasks_timeout: int = 0


class ThreadMonitor:
    """Thread lifecycle monitoring and metrics collection."""

    def __init__(self, config: ThreadConfiguration):
        self.config = config
        self.events: List[ThreadLifecycleEvent] = []
        self.metrics = ThreadMetrics()
        self._lock = threading.Lock()

    def record_task_start(self, task_id: str, module_name: str, task_name: str, thread_id: int, thread_name: str):
        with self._lock:
            event = ThreadLifecycleEvent(
                task_id=task_id,
                module_name=module_name,
                task_name=task_name,
                thread_id=thread_id,
                thread_name=thread_name,
                state="started",
                start_time=time.time(),
            )
            self.events.append(event)
            self.metrics.total_tasks_executed += 1

    def record_task_complete(self, task_id: str, duration_ms: int):
        with self._lock:
            for event in reversed(self.events):
                if event.task_id == task_id:
                    event.state = "completed"
                    event.end_time = time.time()
                    event.duration_ms = duration_ms
                    self.metrics.tasks_completed += 1
                    break

    def record_task_failed(self, task_id: str, error_message: str):
        with self._lock:
            for event in reversed(self.events):
                if event.task_id == task_id:
                    event.state = "failed"
                    event.end_time = time.time()
                    event.error_message = error_message
                    self.metrics.tasks_failed += 1
                    break

    def record_task_cancelled(self, task_id: str):
        with self._lock:
            for event in reversed(self.events):
                if event.task_id == task_id:
                    event.state = "cancelled"
                    event.end_time = time.time()
                    self.metrics.tasks_cancelled += 1
                    break

    def record_task_timeout(self, task_id: str):
        with self._lock:
            for event in reversed(self.events):
                if event.task_id == task_id:
                    event.state = "timeout"
                    event.end_time = time.time()
                    self.metrics.tasks_timeout += 1
                    break

    def export_ndjson(self, output_path: Path, apply_privacy: bool = True) -> int:
        with self._lock:
            events_to_export = list(self.events)
            privacy_rules: List[PrivacyRule] = list(self.config.privacy_rules)

        with open(output_path, "w", encoding="utf-8") as f:
            for event in events_to_export:
                event_dict = event.to_dict()

                if apply_privacy and privacy_rules:
                    for rule in privacy_rules:
                        if rule.field in event_dict and event_dict[rule.field]:
                            event_dict[rule.field] = rule.apply(str(event_dict[rule.field]))

                f.write(json.dumps(event_dict, ensure_ascii=False) + "\n")

        return len(events_to_export)

    def get_metrics(self) -> ThreadMetrics:
        with self._lock:
            return ThreadMetrics(
                total_tasks_executed=self.metrics.total_tasks_executed,
                tasks_completed=self.metrics.tasks_completed,
                tasks_failed=self.metrics.tasks_failed,
                tasks_cancelled=self.metrics.tasks_cancelled,
                tasks_timeout=self.metrics.tasks_timeout,
            )


__all__ = [
    "ThreadMonitor",
    "ThreadLifecycleEvent",
    "ThreadMetrics",
]
