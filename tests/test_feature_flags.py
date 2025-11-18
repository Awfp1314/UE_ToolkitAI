"""
Unit tests for FeatureFlagManager.
"""

import json
import pytest
import tempfile
from pathlib import Path

from core.config.feature_flags import (
    ModuleFeatureFlags,
    FeatureFlagManager,
    get_feature_flags,
)


class TestModuleFeatureFlags:
    """Test ModuleFeatureFlags data class."""

    def test_default_values(self):
        """Test default flag values."""
        flags = ModuleFeatureFlags()
        assert flags.thread_manager_enforced is False

    def test_to_dict(self):
        """Test conversion to dictionary."""
        flags = ModuleFeatureFlags(thread_manager_enforced=True)
        data = flags.to_dict()
        assert data == {"thread_manager_enforced": True}

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {"thread_manager_enforced": True}
        flags = ModuleFeatureFlags.from_dict(data)
        assert flags.thread_manager_enforced is True

    def test_from_dict_with_missing_fields(self):
        """Test creation from dictionary with missing fields uses defaults."""
        data = {}
        flags = ModuleFeatureFlags.from_dict(data)
        assert flags.thread_manager_enforced is False


class TestFeatureFlagManager:
    """Test FeatureFlagManager."""

    @pytest.fixture
    def temp_config_file(self):
        """Create a temporary config file."""
        # Create temp file and close it immediately to avoid Windows file locking
        fd, temp_path = tempfile.mkstemp(suffix=".json")
        import os
        os.close(fd)  # Close the file descriptor
        config_path = Path(temp_path)

        yield config_path

        # Cleanup
        try:
            if config_path.exists():
                config_path.unlink()
        except PermissionError:
            pass  # Ignore cleanup errors on Windows

    def test_init_with_nonexistent_file(self, temp_config_file):
        """Test initialization with non-existent config file."""
        # Delete the file to ensure it doesn't exist
        if temp_config_file.exists():
            temp_config_file.unlink()

        manager = FeatureFlagManager(config_path=temp_config_file)
        assert manager.get_all_flags() == {}

    def test_init_with_existing_file(self, temp_config_file):
        """Test initialization with existing config file."""
        # Write test data
        data = {
            "modules": {
                "ai_assistant": {"thread_manager_enforced": True},
                "asset_manager": {"thread_manager_enforced": False},
            }
        }
        with open(temp_config_file, "w") as f:
            json.dump(data, f)

        manager = FeatureFlagManager(config_path=temp_config_file)
        flags = manager.get_all_flags()

        assert len(flags) == 2
        assert flags["ai_assistant"].thread_manager_enforced is True
        assert flags["asset_manager"].thread_manager_enforced is False

    def test_is_thread_manager_enforced_default(self, temp_config_file):
        """Test is_thread_manager_enforced returns False for unknown module."""
        if temp_config_file.exists():
            temp_config_file.unlink()

        manager = FeatureFlagManager(config_path=temp_config_file)
        assert manager.is_thread_manager_enforced("unknown_module") is False

    def test_is_thread_manager_enforced_true(self, temp_config_file):
        """Test is_thread_manager_enforced returns True when enforced."""
        # Write test data
        data = {
            "modules": {
                "ai_assistant": {"thread_manager_enforced": True},
            }
        }
        with open(temp_config_file, "w") as f:
            json.dump(data, f)

        manager = FeatureFlagManager(config_path=temp_config_file)
        assert manager.is_thread_manager_enforced("ai_assistant") is True

    def test_is_thread_manager_enforced_false(self, temp_config_file):
        """Test is_thread_manager_enforced returns False when not enforced."""
        # Write test data
        data = {
            "modules": {
                "asset_manager": {"thread_manager_enforced": False},
            }
        }
        with open(temp_config_file, "w") as f:
            json.dump(data, f)

        manager = FeatureFlagManager(config_path=temp_config_file)
        assert manager.is_thread_manager_enforced("asset_manager") is False

    def test_set_enforcement_new_module(self, temp_config_file):
        """Test setting enforcement for a new module."""
        if temp_config_file.exists():
            temp_config_file.unlink()

        manager = FeatureFlagManager(config_path=temp_config_file)
        manager.set_enforcement("new_module", True)

        # Verify in memory
        assert manager.is_thread_manager_enforced("new_module") is True

        # Verify saved to file
        with open(temp_config_file, "r") as f:
            data = json.load(f)
        assert data["modules"]["new_module"]["thread_manager_enforced"] is True

    def test_set_enforcement_existing_module(self, temp_config_file):
        """Test updating enforcement for an existing module."""
        # Write initial data
        data = {
            "modules": {
                "ai_assistant": {"thread_manager_enforced": False},
            }
        }
        with open(temp_config_file, "w") as f:
            json.dump(data, f)

        manager = FeatureFlagManager(config_path=temp_config_file)
        manager.set_enforcement("ai_assistant", True)

        # Verify in memory
        assert manager.is_thread_manager_enforced("ai_assistant") is True

        # Verify saved to file
        with open(temp_config_file, "r") as f:
            data = json.load(f)
        assert data["modules"]["ai_assistant"]["thread_manager_enforced"] is True

    def test_get_all_flags(self, temp_config_file):
        """Test getting all flags."""
        # Write test data
        data = {
            "modules": {
                "ai_assistant": {"thread_manager_enforced": True},
                "asset_manager": {"thread_manager_enforced": False},
            }
        }
        with open(temp_config_file, "w") as f:
            json.dump(data, f)

        manager = FeatureFlagManager(config_path=temp_config_file)
        flags = manager.get_all_flags()

        assert len(flags) == 2
        assert "ai_assistant" in flags
        assert "asset_manager" in flags

    def test_thread_safety(self, temp_config_file):
        """Test thread-safe access to flags."""
        import threading

        if temp_config_file.exists():
            temp_config_file.unlink()

        manager = FeatureFlagManager(config_path=temp_config_file)

        def set_flag(module_name: str, enforced: bool):
            manager.set_enforcement(module_name, enforced)

        def get_flag(module_name: str) -> bool:
            return manager.is_thread_manager_enforced(module_name)

        # Create multiple threads that set and get flags
        threads = []
        for i in range(10):
            t1 = threading.Thread(target=set_flag, args=(f"module_{i}", True))
            t2 = threading.Thread(target=get_flag, args=(f"module_{i}",))
            threads.extend([t1, t2])

        # Start all threads
        for t in threads:
            t.start()

        # Wait for all threads to complete
        for t in threads:
            t.join()

        # Verify all flags were set
        for i in range(10):
            assert manager.is_thread_manager_enforced(f"module_{i}") is True


class TestGetFeatureFlags:
    """Test get_feature_flags singleton accessor."""

    def test_singleton_returns_same_instance(self):
        """Test that get_feature_flags returns the same instance."""
        # Note: This test may interfere with other tests due to global state
        # In a real scenario, we'd need to reset the singleton between tests
        manager1 = get_feature_flags()
        manager2 = get_feature_flags()
        assert manager1 is manager2

    def test_singleton_thread_safety(self):
        """Test thread-safe singleton initialization."""
        import threading

        instances = []

        def get_instance():
            instances.append(get_feature_flags())

        # Create multiple threads that get the singleton
        threads = [threading.Thread(target=get_instance) for _ in range(10)]

        # Start all threads
        for t in threads:
            t.start()

        # Wait for all threads to complete
        for t in threads:
            t.join()

        # Verify all threads got the same instance
        assert len(instances) == 10
        assert all(instance is instances[0] for instance in instances)

