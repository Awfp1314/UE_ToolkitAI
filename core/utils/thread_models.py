"""Thread-related data classes used by the unified ThreadManager."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Union
from enum import Enum

from PyQt6.QtCore import QThread, QTimer
from core.utils.thread_utils import Worker, CancellationToken


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
    "ThreadState",
    "TaskInfo",
    "ThreadInfo",
]
