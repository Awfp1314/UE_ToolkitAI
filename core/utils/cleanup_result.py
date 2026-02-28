"""Data objects for cleanup and shutdown results."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class CleanupResult:
    success: bool
    error_message: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    duration_ms: int = 0

    @classmethod
    def success_result(cls) -> "CleanupResult":
        return cls(success=True)

    @classmethod
    def failure_result(cls, error_message: str, errors: Optional[List[str]] = None) -> "CleanupResult":
        return cls(success=False, error_message=error_message, errors=errors or [])


@dataclass
class ModuleCleanupFailure:
    module_name: str
    failure_type: str  # 'exception', 'false_return', or 'timeout'
    exception_type: Optional[str] = None
    error_message: Optional[str] = None
    traceback: Optional[str] = None


@dataclass
class ShutdownResult:
    total_modules: int
    success_count: int
    failure_count: int
    failures: List[ModuleCleanupFailure]
    duration_ms: int

    @property
    def is_success(self) -> bool:
        return self.failure_count == 0

    @property
    def is_partial_failure(self) -> bool:
        return 0 < self.failure_count < self.total_modules

    @property
    def is_complete_failure(self) -> bool:
        return self.failure_count == self.total_modules


__all__ = [
    "CleanupResult",
    "ModuleCleanupFailure",
    "ShutdownResult",
]
