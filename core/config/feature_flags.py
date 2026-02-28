"""
Feature flag management for gradual migration to ThreadManager.

This module provides a feature flag system to control ThreadManager enforcement
per module during migration from legacy QThread to the new ThreadManager.
"""

import logging
import threading
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, Optional

from core.utils.config_utils import ConfigUtils
from core.exceptions import ConfigError


@dataclass
class ModuleFeatureFlags:
    """Feature flags for a single module."""

    thread_manager_enforced: bool = False
    """Whether ThreadManager is enforced for this module (no direct QThread allowed)."""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ModuleFeatureFlags":
        """Create from dictionary loaded from JSON."""
        return cls(
            thread_manager_enforced=data.get("thread_manager_enforced", False)
        )


class FeatureFlagManager:
    """
    Manages feature flags for gradual module migration to ThreadManager.

    Provides per-module control over ThreadManager enforcement, allowing
    safe rollback if issues are discovered during migration.
    """

    def __init__(self, config_path: Optional[Path] = None, logger: Optional[logging.Logger] = None):
        """
        Initialize FeatureFlagManager.

        Args:
            config_path: Path to feature flags JSON file. If None, uses default location.
            logger: Logger instance. If None, creates a new logger.
        """
        self._config_path = config_path or Path("config/feature_flags.json")
        self._logger = logger or logging.getLogger(__name__)
        self._flags: Dict[str, ModuleFeatureFlags] = {}
        self._lock = threading.Lock()

        # Load flags from file
        self._load_flags()

    def _load_flags(self) -> None:
        """Load feature flags from JSON file."""
        if not self._config_path.exists():
            self._logger.info(f"Feature flags file not found: {self._config_path}, using defaults")
            return

        try:
            data = ConfigUtils.read_json(self._config_path, default={})
            if data is None:
                data = {}

            # Load module flags
            modules = data.get("modules", {})
            for module_name, module_data in modules.items():
                self._flags[module_name] = ModuleFeatureFlags.from_dict(module_data)

            self._logger.info(f"Loaded feature flags for {len(self._flags)} modules from {self._config_path}")

        except ConfigError as e:
            self._logger.error(f"Failed to load feature flags from {self._config_path}: {e}")
        except Exception as e:
            self._logger.error(f"Failed to load feature flags from {self._config_path}: {e}")

    def _save_flags(self) -> None:
        """Save feature flags to JSON file."""
        try:
            # Ensure directory exists
            self._config_path.parent.mkdir(parents=True, exist_ok=True)

            # Convert flags to dict
            data = {
                "modules": {
                    module_name: flags.to_dict()
                    for module_name, flags in self._flags.items()
                }
            }

            # Write to file using ConfigUtils
            ConfigUtils.write_json(self._config_path, data, create_backup=False, indent=2)

            self._logger.info(f"Saved feature flags to {self._config_path}")

        except ConfigError as e:
            self._logger.error(f"Failed to save feature flags to {self._config_path}: {e}")
        except Exception as e:
            self._logger.error(f"Failed to save feature flags to {self._config_path}: {e}")

    def is_thread_manager_enforced(self, module_name: str) -> bool:
        """
        Check if ThreadManager is enforced for a module.

        Args:
            module_name: Name of the module to check.

        Returns:
            True if ThreadManager is enforced (no direct QThread allowed),
            False if legacy QThread usage is still permitted.
        """
        with self._lock:
            flags = self._flags.get(module_name)
            if flags is None:
                # Module not in config, default to not enforced
                return False
            return flags.thread_manager_enforced

    def set_enforcement(self, module_name: str, enforced: bool) -> None:
        """
        Enable or disable ThreadManager enforcement for a module.

        Args:
            module_name: Name of the module.
            enforced: True to enforce ThreadManager (no direct QThread),
                     False to allow legacy QThread usage.
        """
        with self._lock:
            # Get or create flags for module
            if module_name not in self._flags:
                self._flags[module_name] = ModuleFeatureFlags()

            # Update enforcement flag
            self._flags[module_name].thread_manager_enforced = enforced

            # Save to file
            self._save_flags()

            self._logger.info(
                f"Set ThreadManager enforcement for '{module_name}': {enforced}"
            )

    def get_all_flags(self) -> Dict[str, ModuleFeatureFlags]:
        """
        Get all module feature flags.

        Returns:
            Dictionary mapping module names to their feature flags.
        """
        with self._lock:
            return self._flags.copy()


# Global singleton instance
_feature_flag_manager: Optional[FeatureFlagManager] = None
_feature_flag_manager_lock = threading.Lock()


def get_feature_flags(
    config_path: Optional[Path] = None,
    logger: Optional[logging.Logger] = None
) -> FeatureFlagManager:
    """
    Get the global FeatureFlagManager singleton instance.

    Uses double-checked locking for thread-safe lazy initialization.

    Args:
        config_path: Path to feature flags JSON file (only used on first call).
        logger: Logger instance (only used on first call).

    Returns:
        The global FeatureFlagManager instance.
    """
    global _feature_flag_manager

    # Fast path: instance already exists
    if _feature_flag_manager is not None:
        return _feature_flag_manager

    # Slow path: need to create instance
    with _feature_flag_manager_lock:
        # Double-check: another thread might have created it
        if _feature_flag_manager is None:
            _feature_flag_manager = FeatureFlagManager(config_path, logger)

        return _feature_flag_manager

