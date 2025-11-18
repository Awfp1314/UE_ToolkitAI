import json
import sys
from pathlib import Path

import pytest

# Ensure project root on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config.thread_config import (  # noqa: E402
    ModuleThreadConfig,
    PrivacyRule,
    ThreadConfiguration,
)
from core.utils.cleanup_result import (  # noqa: E402
    CleanupResult,
    ModuleCleanupFailure,
    ShutdownResult,
)
from core.utils.thread_models import ThreadInfo, ThreadState, TaskInfo  # noqa: E402
from PyQt6.QtCore import QThread, QTimer
from core.utils.thread_utils import CancellationToken, Worker  # noqa: E402


@pytest.fixture()
def config_file(tmp_path: Path) -> Path:
    data = {
        "task_timeout": 30000,
        "grace_period": 1500,
        "cleanup_timeout": 2500,
        "global_shutdown_timeout": 8000,
        "thread_pool_size": 8,
        "task_queue_size": 40,
        "cancellation_check_interval": 400,
        "privacy_rules": [
            {"field": "error_message", "action": "mask", "pattern": "token=[^&\\s]+"},
        ],
        "module_overrides": {
            "ai_assistant": {"task_timeout": 60000, "cleanup_timeout": 5000}
        },
    }
    path = tmp_path / "thread_config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_load_configuration_with_overrides(config_file: Path):
    cfg = ThreadConfiguration.load_from_file(config_file)

    assert cfg.task_timeout == 30000
    assert cfg.grace_period == 1500
    assert cfg.cleanup_timeout == 2500
    assert cfg.global_shutdown_timeout == 8000
    assert cfg.thread_pool_size == 8
    assert cfg.task_queue_size == 40
    assert cfg.cancellation_check_interval == 400
    assert len(cfg.privacy_rules) == 1

    module_cfg = cfg.get_module_config("ai_assistant")
    assert module_cfg.task_timeout == 60000
    assert module_cfg.cleanup_timeout == 5000

    default_cfg = cfg.get_module_config("unknown")
    assert default_cfg.task_timeout == cfg.task_timeout
    assert default_cfg.cleanup_timeout == cfg.cleanup_timeout


def test_privacy_rule_apply_mask_and_redact():
    mask_rule = PrivacyRule(field="error_message", action="mask", pattern=r"token=[^&\s]+")
    redact_rule = PrivacyRule(field="task_args", action="redact")

    assert mask_rule.apply("oops token=abc123") == "oops [MASKED]"
    assert redact_rule.apply("should hide") == "[REDACTED]"


def test_cleanup_and_shutdown_results():
    ok = CleanupResult.success_result()
    err = CleanupResult.failure_result("fail", ["trace"])

    assert ok.success is True
    assert err.success is False
    assert err.error_message == "fail"
    assert err.errors == ["trace"]

    failures = [ModuleCleanupFailure(module_name="m1", failure_type="timeout")]
    result = ShutdownResult(total_modules=2, success_count=1, failure_count=1, failures=failures, duration_ms=10)

    assert result.is_partial_failure is True
    assert result.is_success is False
    assert result.is_complete_failure is False


def test_thread_state_and_task_info_creation():
    thread = QThread()
    worker = Worker(lambda: None)
    token = worker.cancel_token
    task_info = TaskInfo(
        task_id="t1",
        module_name="mod",
        task_name="task",
        thread=thread,
        worker=worker,
        cancel_token=token,
        state=ThreadState.RUNNING,
        start_time=0.0,
        timeout_ms=1000,
        timeout_timer=QTimer(),
    )

    assert task_info.state == ThreadState.RUNNING
    assert isinstance(task_info.cancel_token, CancellationToken)

    snapshot = ThreadInfo(
        task_id=task_info.task_id,
        module_name=task_info.module_name,
        task_name=task_info.task_name,
        thread_id=id(thread),
        state=task_info.state.value,
        elapsed_ms=0,
        started_at=task_info.timeout_timer.remainingTime() if task_info.timeout_timer else 0,  # type: ignore[arg-type]
    )
    assert snapshot.task_id == "t1"
    assert snapshot.state == ThreadState.RUNNING.value
