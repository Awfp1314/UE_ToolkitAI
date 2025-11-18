"""Integration tests for ShutdownOrchestrator."""
import logging
import time
from typing import Optional

import pytest
from PyQt6.QtWidgets import QWidget

from core.config.thread_config import ThreadConfiguration, ModuleThreadConfig
from core.module_interface import IModule, ModuleMetadata
from core.utils.cleanup_result import CleanupResult
from core.utils.shutdown_orchestrator import ShutdownOrchestrator


class MockModule(IModule):
    """Mock module for testing."""

    def __init__(self, name: str, cleanup_delay: float = 0.0, should_fail: bool = False, raise_exception: bool = False):
        self.name = name
        self.cleanup_delay = cleanup_delay
        self.should_fail = should_fail
        self.raise_exception = raise_exception
        self.request_stop_called = False
        self.cleanup_called = False

    def get_metadata(self) -> ModuleMetadata:
        """Return mock metadata."""
        return ModuleMetadata(
            name=self.name,
            display_name=self.name,
            version="1.0.0",
            description="Mock module for testing",
        )

    def get_widget(self) -> QWidget:
        """Return mock widget."""
        return QWidget()

    def initialize(self) -> bool:
        """Mock initialization."""
        return True

    def request_stop(self) -> None:
        """Record that request_stop was called."""
        self.request_stop_called = True

    def cleanup(self) -> CleanupResult:
        """Simulate cleanup with configurable behavior."""
        self.cleanup_called = True

        if self.cleanup_delay > 0:
            time.sleep(self.cleanup_delay)

        if self.raise_exception:
            raise RuntimeError(f"Cleanup failed for {self.name}")

        if self.should_fail:
            return CleanupResult.failure_result(
                error_message=f"Cleanup failed for {self.name}",
                errors=["Simulated failure"],
            )

        return CleanupResult.success_result()


class ModuleWithoutRequestStop(IModule):
    """Mock module without request_stop method."""

    def __init__(self, name: str):
        self.name = name
        self.cleanup_called = False

    def get_metadata(self) -> ModuleMetadata:
        """Return mock metadata."""
        return ModuleMetadata(
            name=self.name,
            display_name=self.name,
            version="1.0.0",
            description="Mock module without request_stop",
        )

    def get_widget(self) -> QWidget:
        """Return mock widget."""
        return QWidget()

    def initialize(self) -> bool:
        """Mock initialization."""
        return True

    def cleanup(self) -> CleanupResult:
        """Simple cleanup."""
        self.cleanup_called = True
        return CleanupResult.success_result()


@pytest.fixture
def config():
    """Create a test configuration."""
    return ThreadConfiguration(
        task_timeout=5000,
        grace_period=1000,
        cleanup_timeout=2000,
        global_shutdown_timeout=10000,
        thread_pool_size=10,
        task_queue_size=50,
        cancellation_check_interval=500,
        privacy_rules=[],
        module_overrides={},
    )


@pytest.fixture
def logger():
    """Create a test logger."""
    return logging.getLogger("test_shutdown")


def test_shutdown_empty_modules(config, logger):
    """Test shutdown with no modules."""
    orchestrator = ShutdownOrchestrator(config, logger)
    result = orchestrator.shutdown_modules({})

    assert result.total_modules == 0
    assert result.success_count == 0
    assert result.failure_count == 0
    assert result.is_success


def test_shutdown_single_module_success(config, logger):
    """Test successful shutdown of a single module."""
    module = MockModule("test_module")
    orchestrator = ShutdownOrchestrator(config, logger)

    result = orchestrator.shutdown_modules({"test_module": module})

    assert result.total_modules == 1
    assert result.success_count == 1
    assert result.failure_count == 0
    assert result.is_success
    assert module.request_stop_called
    assert module.cleanup_called


def test_shutdown_multiple_modules_parallel(config, logger):
    """Test parallel shutdown of multiple modules."""
    modules = {
        f"module_{i}": MockModule(f"module_{i}", cleanup_delay=0.1)
        for i in range(5)
    }
    orchestrator = ShutdownOrchestrator(config, logger)

    start_time = time.time()
    result = orchestrator.shutdown_modules(modules)
    duration = time.time() - start_time

    assert result.total_modules == 5
    assert result.success_count == 5
    assert result.failure_count == 0
    assert result.is_success

    # Parallel execution should be faster than sequential (5 * 0.1 = 0.5s)
    assert duration < 0.4  # Should complete in ~0.1s with parallelism

    # Verify all modules were cleaned up
    for module in modules.values():
        assert module.request_stop_called
        assert module.cleanup_called


def test_shutdown_module_failure(config, logger):
    """Test shutdown with a module that returns failure."""
    modules = {
        "good_module": MockModule("good_module"),
        "bad_module": MockModule("bad_module", should_fail=True),
    }
    orchestrator = ShutdownOrchestrator(config, logger)

    result = orchestrator.shutdown_modules(modules)

    assert result.total_modules == 2
    assert result.success_count == 1
    assert result.failure_count == 1
    assert result.is_partial_failure
    assert len(result.failures) == 1
    assert result.failures[0].module_name == "bad_module"
    assert result.failures[0].failure_type == "false_return"


def test_shutdown_module_exception(config, logger):
    """Test shutdown with a module that raises an exception."""
    modules = {
        "good_module": MockModule("good_module"),
        "exception_module": MockModule("exception_module", raise_exception=True),
    }
    orchestrator = ShutdownOrchestrator(config, logger)

    result = orchestrator.shutdown_modules(modules)

    assert result.total_modules == 2
    assert result.success_count == 1
    assert result.failure_count == 1
    assert result.is_partial_failure
    assert len(result.failures) == 1
    assert result.failures[0].module_name == "exception_module"
    assert result.failures[0].failure_type == "exception"
    assert result.failures[0].exception_type == "RuntimeError"


def test_request_stop_called_before_cleanup(config, logger):
    """Test that request_stop() is called before cleanup()."""
    call_order = []

    class OrderTrackingModule(IModule):
        def get_metadata(self) -> ModuleMetadata:
            return ModuleMetadata(name="test", display_name="test", version="1.0.0", description="test")

        def get_widget(self) -> QWidget:
            return QWidget()

        def initialize(self) -> bool:
            return True

        def request_stop(self):
            call_order.append("request_stop")

        def cleanup(self) -> CleanupResult:
            call_order.append("cleanup")
            return CleanupResult.success_result()

    module = OrderTrackingModule()
    orchestrator = ShutdownOrchestrator(config, logger)

    result = orchestrator.shutdown_modules({"test": module})

    assert result.is_success
    assert call_order == ["request_stop", "cleanup"]


def test_module_without_request_stop(config, logger):
    """Test shutdown of module without request_stop method."""
    module = ModuleWithoutRequestStop("test_module")
    orchestrator = ShutdownOrchestrator(config, logger)

    result = orchestrator.shutdown_modules({"test_module": module})

    assert result.is_success
    assert module.cleanup_called


def test_per_module_cleanup_timeout(config, logger):
    """Test per-module cleanup timeout override."""
    # Configure short timeout for specific module
    config.module_overrides = {
        "slow_module": ModuleThreadConfig(cleanup_timeout=200),  # 200ms timeout
    }

    modules = {
        "slow_module": MockModule("slow_module", cleanup_delay=2.0),  # Takes 2 seconds
    }
    orchestrator = ShutdownOrchestrator(config, logger)

    result = orchestrator.shutdown_modules(modules)

    assert result.total_modules == 1
    assert result.success_count == 0
    assert result.failure_count == 1
    assert result.failures[0].module_name == "slow_module"
    assert result.failures[0].failure_type == "timeout"
    assert "200ms" in result.failures[0].error_message


def test_global_shutdown_timeout(config, logger):
    """Test global shutdown timeout enforcement."""
    # Set very short global timeout
    config.global_shutdown_timeout = 300  # 300ms

    # Create modules that take longer than global timeout individually
    # Even with parallelism, they won't all complete in time
    modules = {
        f"module_{i}": MockModule(f"module_{i}", cleanup_delay=0.5)
        for i in range(10)  # 10 modules, each takes 500ms
    }
    orchestrator = ShutdownOrchestrator(config, logger)

    start_time = time.time()
    result = orchestrator.shutdown_modules(modules)
    duration = time.time() - start_time

    # Should timeout around global timeout (0.3s), not wait for all modules (5s)
    assert duration < 1.0  # Much less than 5s
    assert result.failure_count > 0  # Some modules should timeout


def test_widespread_cleanup_failure_logging(config, logger, caplog):
    """Test critical logging when > 50% modules fail."""
    # Create 10 modules, 6 will fail (60%)
    modules = {}
    for i in range(10):
        should_fail = i < 6
        modules[f"module_{i}"] = MockModule(f"module_{i}", should_fail=should_fail)

    orchestrator = ShutdownOrchestrator(config, logger)

    with caplog.at_level(logging.CRITICAL):
        result = orchestrator.shutdown_modules(modules)

    assert result.total_modules == 10
    assert result.failure_count == 6
    # Check that critical log was emitted
    assert any("Widespread cleanup failure" in record.message for record in caplog.records)


def test_shutdown_performance_within_timeout(config, logger):
    """Test that shutdown completes within global timeout."""
    # Create many fast modules
    modules = {
        f"module_{i}": MockModule(f"module_{i}", cleanup_delay=0.05)
        for i in range(20)
    }

    config.global_shutdown_timeout = 5000  # 5 seconds
    orchestrator = ShutdownOrchestrator(config, logger)

    start_time = time.time()
    result = orchestrator.shutdown_modules(modules)
    duration_ms = (time.time() - start_time) * 1000

    # All should succeed
    assert result.is_success
    # Should complete well within global timeout due to parallelism
    assert duration_ms < config.global_shutdown_timeout

