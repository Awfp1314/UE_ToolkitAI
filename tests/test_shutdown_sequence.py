"""Integration tests for shutdown sequence (Task 14.6).

Tests ShutdownOrchestrator with multiple modules, varying cleanup times,
failures, timeouts, and mixed scenarios.
"""
import logging
import time
import pytest
from typing import Optional

from core.config.thread_config import ThreadConfiguration, ModuleThreadConfig
from core.utils.cleanup_result import CleanupResult
from core.utils.shutdown_orchestrator import ShutdownOrchestrator


class MockModule:
    """Mock module for testing shutdown scenarios."""
    
    def __init__(
        self,
        name: str,
        cleanup_behavior: str = "success",
        cleanup_delay: float = 0.0,
        raise_exception: bool = False,
        exception_type: type = RuntimeError,
    ):
        """
        Initialize mock module.
        
        Args:
            name: Module name
            cleanup_behavior: "success", "failure", or "timeout"
            cleanup_delay: Delay in seconds before cleanup completes
            raise_exception: Whether to raise an exception during cleanup
            exception_type: Type of exception to raise
        """
        self.name = name
        self.cleanup_behavior = cleanup_behavior
        self.cleanup_delay = cleanup_delay
        self.raise_exception = raise_exception
        self.exception_type = exception_type
        self.cleanup_called = False
        self.request_stop_called = False
        self.cleanup_start_time: Optional[float] = None
        self.cleanup_end_time: Optional[float] = None
    
    def request_stop(self):
        """Request module to stop (optional method)."""
        self.request_stop_called = True
    
    def cleanup(self) -> CleanupResult:
        """Cleanup module resources."""
        self.cleanup_called = True
        self.cleanup_start_time = time.time()
        
        if self.cleanup_delay > 0:
            time.sleep(self.cleanup_delay)
        
        self.cleanup_end_time = time.time()
        
        if self.raise_exception:
            raise self.exception_type(f"Cleanup failed for {self.name}")
        
        if self.cleanup_behavior == "success":
            return CleanupResult.success_result()
        elif self.cleanup_behavior == "failure":
            return CleanupResult.failure_result(
                error_message=f"Cleanup failed for {self.name}",
                errors=["Error 1", "Error 2"]
            )
        else:
            # Should not reach here for timeout - timeout is handled by orchestrator
            return CleanupResult.success_result()


@pytest.fixture
def thread_config():
    """Create a ThreadConfiguration for testing."""
    return ThreadConfiguration(
        task_timeout=1000,
        grace_period=500,
        cleanup_timeout=1000,  # Default 1 second
        global_shutdown_timeout=5000,  # 5 seconds
        thread_pool_size=5,
        task_queue_size=10,
        module_overrides={
            "fast_module": ModuleThreadConfig(cleanup_timeout=500),  # 0.5 seconds
            "slow_module": ModuleThreadConfig(cleanup_timeout=2000),  # 2 seconds
            "timeout_module": ModuleThreadConfig(cleanup_timeout=100),  # 0.1 seconds (will timeout)
        },
    )


@pytest.fixture
def logger():
    """Create a logger for testing."""
    logger = logging.getLogger("test_shutdown")
    logger.setLevel(logging.DEBUG)
    return logger


class TestShutdownSequence:
    """Test suite for shutdown sequence integration."""
    
    def test_all_modules_succeed(self, thread_config, logger):
        """Test shutdown with all modules succeeding."""
        modules = {
            "module1": MockModule("module1", cleanup_behavior="success", cleanup_delay=0.1),
            "module2": MockModule("module2", cleanup_behavior="success", cleanup_delay=0.1),
            "module3": MockModule("module3", cleanup_behavior="success", cleanup_delay=0.1),
        }
        
        orchestrator = ShutdownOrchestrator(thread_config, logger)
        result = orchestrator.shutdown_modules(modules)
        
        assert result.total_modules == 3
        assert result.success_count == 3
        assert result.failure_count == 0
        assert len(result.failures) == 0
        assert result.is_success
        assert not result.is_partial_failure
        assert not result.is_complete_failure
        
        # Verify all modules were cleaned up
        for module in modules.values():
            assert module.cleanup_called
            assert module.request_stop_called
    
    def test_some_modules_fail(self, thread_config, logger):
        """Test shutdown with some modules failing cleanup."""
        modules = {
            "success_module": MockModule("success_module", cleanup_behavior="success"),
            "failure_module1": MockModule("failure_module1", cleanup_behavior="failure"),
            "failure_module2": MockModule("failure_module2", cleanup_behavior="failure"),
        }
        
        orchestrator = ShutdownOrchestrator(thread_config, logger)
        result = orchestrator.shutdown_modules(modules)
        
        assert result.total_modules == 3
        assert result.success_count == 1
        assert result.failure_count == 2
        assert len(result.failures) == 2
        assert not result.is_success
        assert result.is_partial_failure
        assert not result.is_complete_failure
        
        # Verify failure types
        for failure in result.failures:
            assert failure.failure_type == "false_return"
            assert "Cleanup failed" in failure.error_message

    def test_some_modules_timeout(self, thread_config, logger):
        """Test shutdown with some modules timing out."""
        modules = {
            "success_module": MockModule("success_module", cleanup_behavior="success", cleanup_delay=0.05),
            "timeout_module1": MockModule("timeout_module1", cleanup_behavior="success", cleanup_delay=0.5),  # Will timeout (100ms limit)
            "timeout_module2": MockModule("timeout_module2", cleanup_behavior="success", cleanup_delay=0.5),  # Will timeout (100ms limit)
        }

        # Override timeout for timeout modules
        thread_config.module_overrides["timeout_module1"] = ModuleThreadConfig(cleanup_timeout=100)
        thread_config.module_overrides["timeout_module2"] = ModuleThreadConfig(cleanup_timeout=100)

        orchestrator = ShutdownOrchestrator(thread_config, logger)
        result = orchestrator.shutdown_modules(modules)

        assert result.total_modules == 3
        assert result.success_count == 1
        assert result.failure_count == 2
        assert len(result.failures) == 2
        assert not result.is_success
        assert result.is_partial_failure

        # Verify failure types are timeout
        for failure in result.failures:
            if failure.module_name.startswith("timeout_module"):
                assert failure.failure_type == "timeout"
                assert "timeout" in failure.error_message.lower()

    def test_some_modules_raise_exception(self, thread_config, logger):
        """Test shutdown with some modules raising exceptions."""
        modules = {
            "success_module": MockModule("success_module", cleanup_behavior="success"),
            "exception_module1": MockModule("exception_module1", raise_exception=True, exception_type=RuntimeError),
            "exception_module2": MockModule("exception_module2", raise_exception=True, exception_type=ValueError),
        }

        orchestrator = ShutdownOrchestrator(thread_config, logger)
        result = orchestrator.shutdown_modules(modules)

        assert result.total_modules == 3
        assert result.success_count == 1
        assert result.failure_count == 2
        assert len(result.failures) == 2
        assert not result.is_success
        assert result.is_partial_failure

        # Verify failure types are exception
        exception_failures = [f for f in result.failures if f.module_name.startswith("exception_module")]
        assert len(exception_failures) == 2

        for failure in exception_failures:
            assert failure.failure_type == "exception"
            assert failure.exception_type in ["RuntimeError", "ValueError"]
            assert failure.traceback is not None

    def test_mixed_failure_scenario(self, thread_config, logger):
        """Test mixed failure scenario: timeout + exception + failure + success."""
        modules = {
            "success_module": MockModule("success_module", cleanup_behavior="success", cleanup_delay=0.05),
            "failure_module": MockModule("failure_module", cleanup_behavior="failure"),
            "exception_module": MockModule("exception_module", raise_exception=True, exception_type=RuntimeError),
            "timeout_module": MockModule("timeout_module", cleanup_behavior="success", cleanup_delay=0.5),
        }

        # Override timeout for timeout module
        thread_config.module_overrides["timeout_module"] = ModuleThreadConfig(cleanup_timeout=100)

        orchestrator = ShutdownOrchestrator(thread_config, logger)
        result = orchestrator.shutdown_modules(modules)

        assert result.total_modules == 4
        assert result.success_count == 1
        assert result.failure_count == 3
        assert len(result.failures) == 3
        assert not result.is_success
        assert result.is_partial_failure

        # Verify each failure type
        failure_types = {f.module_name: f.failure_type for f in result.failures}
        assert failure_types["failure_module"] == "false_return"
        assert failure_types["exception_module"] == "exception"
        assert failure_types["timeout_module"] == "timeout"

    def test_parallel_execution(self, thread_config, logger):
        """Test that modules are cleaned up in parallel."""
        # Create 5 modules, each taking 0.2 seconds
        modules = {
            f"module{i}": MockModule(f"module{i}", cleanup_behavior="success", cleanup_delay=0.2)
            for i in range(5)
        }

        orchestrator = ShutdownOrchestrator(thread_config, logger)
        start_time = time.time()
        result = orchestrator.shutdown_modules(modules)
        duration = time.time() - start_time

        # If sequential, would take 5 * 0.2 = 1.0 seconds
        # If parallel, should take ~0.2 seconds (plus overhead)
        assert duration < 0.5, f"Parallel execution took {duration:.2f}s, expected < 0.5s"

        assert result.total_modules == 5
        assert result.success_count == 5
        assert result.failure_count == 0

        # Verify all modules started cleanup around the same time
        start_times = [m.cleanup_start_time for m in modules.values()]
        time_spread = max(start_times) - min(start_times)
        assert time_spread < 0.1, f"Modules started {time_spread:.2f}s apart, expected < 0.1s"

    def test_critical_error_logging_when_majority_fail(self, thread_config, logger, caplog):
        """Test critical error logging when > 50% modules fail."""
        # Create 5 modules: 2 succeed, 3 fail (60% failure rate)
        modules = {
            "success1": MockModule("success1", cleanup_behavior="success"),
            "success2": MockModule("success2", cleanup_behavior="success"),
            "failure1": MockModule("failure1", cleanup_behavior="failure"),
            "failure2": MockModule("failure2", cleanup_behavior="failure"),
            "failure3": MockModule("failure3", cleanup_behavior="failure"),
        }

        orchestrator = ShutdownOrchestrator(thread_config, logger)

        with caplog.at_level(logging.CRITICAL):
            result = orchestrator.shutdown_modules(modules)

        assert result.total_modules == 5
        assert result.success_count == 2
        assert result.failure_count == 3

        # Verify critical log was emitted
        critical_logs = [record for record in caplog.records if record.levelname == "CRITICAL"]
        assert len(critical_logs) > 0
        assert "Widespread cleanup failure" in critical_logs[0].message
        assert "3/5" in critical_logs[0].message

    def test_no_critical_error_when_minority_fail(self, thread_config, logger, caplog):
        """Test no critical error logging when <= 50% modules fail."""
        # Create 5 modules: 3 succeed, 2 fail (40% failure rate)
        modules = {
            "success1": MockModule("success1", cleanup_behavior="success"),
            "success2": MockModule("success2", cleanup_behavior="success"),
            "success3": MockModule("success3", cleanup_behavior="success"),
            "failure1": MockModule("failure1", cleanup_behavior="failure"),
            "failure2": MockModule("failure2", cleanup_behavior="failure"),
        }

        orchestrator = ShutdownOrchestrator(thread_config, logger)

        with caplog.at_level(logging.CRITICAL):
            result = orchestrator.shutdown_modules(modules)

        assert result.total_modules == 5
        assert result.success_count == 3
        assert result.failure_count == 2

        # Verify no critical log was emitted
        critical_logs = [record for record in caplog.records if record.levelname == "CRITICAL"]
        assert len(critical_logs) == 0

    def test_empty_modules_dict(self, thread_config, logger):
        """Test shutdown with no modules."""
        orchestrator = ShutdownOrchestrator(thread_config, logger)
        result = orchestrator.shutdown_modules({})

        assert result.total_modules == 0
        assert result.success_count == 0
        assert result.failure_count == 0
        assert len(result.failures) == 0
        assert result.is_success

    def test_is_partial_failure_logic(self, thread_config, logger):
        """Test ShutdownResult.is_partial_failure() logic."""
        # All succeed
        modules = {
            "success1": MockModule("success1", cleanup_behavior="success"),
            "success2": MockModule("success2", cleanup_behavior="success"),
        }
        orchestrator = ShutdownOrchestrator(thread_config, logger)
        result = orchestrator.shutdown_modules(modules)
        assert result.is_success
        assert not result.is_partial_failure
        assert not result.is_complete_failure

        # Partial failure
        modules = {
            "success1": MockModule("success1", cleanup_behavior="success"),
            "failure1": MockModule("failure1", cleanup_behavior="failure"),
        }
        result = orchestrator.shutdown_modules(modules)
        assert not result.is_success
        assert result.is_partial_failure
        assert not result.is_complete_failure

        # Complete failure
        modules = {
            "failure1": MockModule("failure1", cleanup_behavior="failure"),
            "failure2": MockModule("failure2", cleanup_behavior="failure"),
        }
        result = orchestrator.shutdown_modules(modules)
        assert not result.is_success
        assert not result.is_partial_failure
        assert result.is_complete_failure

