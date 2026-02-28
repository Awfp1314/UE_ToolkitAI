"""Thread configuration module for thread/resource management unification.

Provides dataclasses for global and per-module thread configuration and
privacy rules. Loading is JSON-based with defaults for missing fields.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from core.utils.config_utils import ConfigUtils
from core.exceptions import ConfigError


@dataclass
class PrivacyRule:
    """Rule for redacting or masking sensitive information in monitoring data."""

    field: str
    action: str  # 'redact' or 'mask'
    pattern: Optional[str] = None

    def apply(self, value: str) -> str:
        if self.action == "redact":
            return "[REDACTED]"
        if self.action == "mask" and self.pattern:
            return re.sub(self.pattern, "[MASKED]", value)
        return value


@dataclass
class ModuleThreadConfig:
    """Per-module configuration overrides."""

    task_timeout: Optional[int] = None
    cleanup_timeout: Optional[int] = None

    def merge_with_defaults(self, defaults: "ThreadConfiguration") -> "ModuleThreadConfig":
        return ModuleThreadConfig(
            task_timeout=self.task_timeout if self.task_timeout is not None else defaults.task_timeout,
            cleanup_timeout=self.cleanup_timeout if self.cleanup_timeout is not None else defaults.cleanup_timeout,
        )


@dataclass
class ThreadConfiguration:
    """Thread management configuration with defaults and per-module overrides."""

    task_timeout: int = 30000
    grace_period: int = 2000
    cleanup_timeout: int = 2000
    global_shutdown_timeout: int = 10000
    thread_pool_size: int = 10
    task_queue_size: int = 50
    cancellation_check_interval: int = 500
    privacy_rules: List[PrivacyRule] = field(default_factory=list)
    module_overrides: Dict[str, ModuleThreadConfig] = field(default_factory=dict)

    @classmethod
    def load_from_file(cls, config_path: Path) -> "ThreadConfiguration":
        """Load configuration from a JSON file.

        Missing files raise FileNotFoundError to surface configuration issues
        early. Unknown keys are ignored so the config can evolve without
        breaking older versions.
        """
        data = ConfigUtils.read_json(config_path, default=None)
        if data is None:
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        module_overrides = {
            name: ModuleThreadConfig(**override)
            for name, override in data.get("module_overrides", {}).items()
        }
        privacy_rules = [PrivacyRule(**rule) for rule in data.get("privacy_rules", [])]

        return cls(
            task_timeout=data.get("task_timeout", 30000),
            grace_period=data.get("grace_period", 2000),
            cleanup_timeout=data.get("cleanup_timeout", 2000),
            global_shutdown_timeout=data.get("global_shutdown_timeout", 10000),
            thread_pool_size=data.get("thread_pool_size", 10),
            task_queue_size=data.get("task_queue_size", 50),
            cancellation_check_interval=data.get("cancellation_check_interval", 500),
            privacy_rules=privacy_rules,
            module_overrides=module_overrides,
        )

    def get_module_config(self, module_name: str) -> ModuleThreadConfig:
        if module_name in self.module_overrides:
            return self.module_overrides[module_name].merge_with_defaults(self)
        return ModuleThreadConfig(
            task_timeout=self.task_timeout,
            cleanup_timeout=self.cleanup_timeout,
        )

    def to_dict(self) -> dict:
        """Serialize configuration for debugging or logging."""

        return {
            "task_timeout": self.task_timeout,
            "grace_period": self.grace_period,
            "cleanup_timeout": self.cleanup_timeout,
            "global_shutdown_timeout": self.global_shutdown_timeout,
            "thread_pool_size": self.thread_pool_size,
            "task_queue_size": self.task_queue_size,
            "cancellation_check_interval": self.cancellation_check_interval,
            "privacy_rules": [rule.__dict__ for rule in self.privacy_rules],
            "module_overrides": {
                name: override.__dict__ for name, override in self.module_overrides.items()
            },
        }


__all__ = [
    "PrivacyRule",
    "ModuleThreadConfig",
    "ThreadConfiguration",
]
