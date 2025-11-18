"""Integration tests for AppManager shutdown with ShutdownOrchestrator."""
import logging
import time
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtWidgets import QWidget

from core.app_manager import AppManager
from core.module_manager import ModuleManager, ModuleState, ModuleInfo
from core.module_interface import IModule, ModuleMetadata
from core.utils.cleanup_result import CleanupResult


class MockModule(IModule):
    """Mock module for testing."""

    def __init__(
        self,
        name: str,
        cleanup_delay: float = 0.0,
        should_fail: bool = False,
        raise_exception: bool = False,
    ):
        self.name = name
        self.cleanup_delay = cleanup_delay
        self.should_fail = should_fail
        self.raise_exception = raise_exception
        self.request_stop_called = False
        self.cleanup_called = False

    def get_metadata(self) -> ModuleMetadata:
        return ModuleMetadata(
            name=self.name,
            display_name=self.name,
            version="1.0.0",
            description="Mock module for testing",
        )

    def get_widget(self) -> QWidget:
        return QWidget()

    def initialize(self) -> bool:
        return True

    def request_stop(self) -> None:
        self.request_stop_called = True

    def cleanup(self) -> CleanupResult:
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


@pytest.fixture
def app_manager():
    """Create an AppManager instance for testing."""
    manager = AppManager()
    manager._is_running = True  # Simulate running state
    manager._logger = logging.getLogger("test_app_manager")
    yield manager
    # Cleanup
    manager._is_running = False


@pytest.fixture
def mock_module_manager():
    """Create a mock ModuleManager with test modules."""
    manager = MagicMock(spec=ModuleManager)

    # Create mock modules
    modules = {
        "module1": ModuleInfo(
            name="module1",
            version="1.0.0",
            description="Test module 1",
            state=ModuleState.INITIALIZED,
            instance=MockModule("module1"),
        ),
        "module2": ModuleInfo(
            name="module2",
            version="1.0.0",
            description="Test module 2",
            state=ModuleState.INITIALIZED,
            instance=MockModule("module2"),
        ),
    }

    manager.get_all_modules.return_value = modules
    manager.get_module.side_effect = lambda name: modules.get(name)

    return manager


def test_quit_with_successful_shutdown(app_manager, mock_module_manager):
    """Test quit() with all modules cleaning up successfully."""
    app_manager.module_manager = mock_module_manager

    # Save references to module instances before quit() clears them
    modules = mock_module_manager.get_all_modules()
    module_instances = {name: info.instance for name, info in modules.items()}

    # Mock cleanup_all_services to avoid actual service cleanup
    with patch("core.app_manager.cleanup_all_services"):
        app_manager.quit()

    # Verify all modules were cleaned up (using saved references)
    for module_instance in module_instances.values():
        assert module_instance.cleanup_called
        assert module_instance.request_stop_called

    # Verify app is no longer running
    assert not app_manager._is_running


def test_quit_with_partial_failure(app_manager, mock_module_manager):
    """Test quit() with some modules failing cleanup."""
    # Make one module fail
    modules = mock_module_manager.get_all_modules()
    failed_module = MockModule("module2", should_fail=True)
    modules["module2"] = ModuleInfo(
        name="module2",
        version="1.0.0",
        description="Test module 2",
        state=ModuleState.INITIALIZED,
        instance=failed_module,
    )

    # Save references to module instances before quit() clears them
    module_instances = {name: info.instance for name, info in modules.items()}

    app_manager.module_manager = mock_module_manager

    with patch("core.app_manager.cleanup_all_services"):
        app_manager.quit()

    # Verify all modules attempted cleanup (using saved references)
    for module_instance in module_instances.values():
        assert module_instance.cleanup_called

    # Verify app still shuts down despite failures
    assert not app_manager._is_running


def test_quit_with_no_modules(app_manager):
    """Test quit() when no modules are loaded."""
    app_manager.module_manager = None
    
    with patch("core.app_manager.cleanup_all_services"):
        app_manager.quit()
    
    assert not app_manager._is_running

