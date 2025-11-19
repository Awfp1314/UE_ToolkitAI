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


def test_load_configuration_file_not_found():
    """Test that FileNotFoundError is raised when config file doesn't exist."""
    non_existent_path = Path("/non/existent/path/config.json")

    with pytest.raises(FileNotFoundError):
        ThreadConfiguration.load_from_file(non_existent_path)


def test_load_configuration_invalid_json(tmp_path: Path):
    """Test that JSONDecodeError is raised for invalid JSON."""
    invalid_json_file = tmp_path / "invalid.json"
    invalid_json_file.write_text("{ this is not valid json }", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        ThreadConfiguration.load_from_file(invalid_json_file)


def test_load_configuration_with_defaults(tmp_path: Path):
    """Test that default values are used when fields are missing."""
    minimal_config = tmp_path / "minimal.json"
    minimal_config.write_text("{}", encoding="utf-8")

    cfg = ThreadConfiguration.load_from_file(minimal_config)

    # Verify all defaults are applied
    assert cfg.task_timeout == 30000
    assert cfg.grace_period == 2000
    assert cfg.cleanup_timeout == 2000
    assert cfg.global_shutdown_timeout == 10000
    assert cfg.thread_pool_size == 10
    assert cfg.task_queue_size == 50
    assert cfg.cancellation_check_interval == 500
    assert len(cfg.privacy_rules) == 0
    assert len(cfg.module_overrides) == 0


def test_load_configuration_partial_overrides(tmp_path: Path):
    """Test that partial module overrides merge with defaults."""
    partial_config = tmp_path / "partial.json"
    data = {
        "task_timeout": 40000,
        "module_overrides": {
            "test_module": {"task_timeout": 50000}  # Only override task_timeout
        }
    }
    partial_config.write_text(json.dumps(data), encoding="utf-8")

    cfg = ThreadConfiguration.load_from_file(partial_config)
    module_cfg = cfg.get_module_config("test_module")

    # task_timeout should be overridden
    assert module_cfg.task_timeout == 50000
    # cleanup_timeout should use global default
    assert module_cfg.cleanup_timeout == cfg.cleanup_timeout


def test_configuration_to_dict():
    """Test that configuration can be serialized to dict."""
    cfg = ThreadConfiguration(
        task_timeout=35000,
        grace_period=1800,
        privacy_rules=[PrivacyRule(field="test", action="redact")],
        module_overrides={"mod1": ModuleThreadConfig(task_timeout=45000)}
    )

    result = cfg.to_dict()

    assert result["task_timeout"] == 35000
    assert result["grace_period"] == 1800
    assert len(result["privacy_rules"]) == 1
    assert result["privacy_rules"][0]["field"] == "test"
    assert result["privacy_rules"][0]["action"] == "redact"
    assert "mod1" in result["module_overrides"]
    assert result["module_overrides"]["mod1"]["task_timeout"] == 45000


def test_privacy_rule_no_pattern():
    """Test privacy rule without pattern (for redact action)."""
    rule = PrivacyRule(field="sensitive", action="redact")
    assert rule.apply("secret data") == "[REDACTED]"


def test_privacy_rule_mask_no_match():
    """Test mask rule when pattern doesn't match."""
    rule = PrivacyRule(field="data", action="mask", pattern=r"password=\w+")
    # Pattern doesn't match, should return original
    assert rule.apply("no password here") == "no password here"


def test_module_config_merge_with_defaults():
    """Test ModuleThreadConfig merge behavior."""
    defaults = ThreadConfiguration(task_timeout=30000, cleanup_timeout=2000)

    # Module config with only task_timeout override
    module_cfg = ModuleThreadConfig(task_timeout=60000, cleanup_timeout=None)
    merged = module_cfg.merge_with_defaults(defaults)

    assert merged.task_timeout == 60000
    assert merged.cleanup_timeout == 2000  # From defaults

    # Module config with both overrides
    module_cfg2 = ModuleThreadConfig(task_timeout=70000, cleanup_timeout=5000)
    merged2 = module_cfg2.merge_with_defaults(defaults)

    assert merged2.task_timeout == 70000
    assert merged2.cleanup_timeout == 5000
