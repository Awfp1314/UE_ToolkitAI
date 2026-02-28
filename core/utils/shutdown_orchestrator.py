"""ShutdownOrchestrator for parallel module cleanup."""
from __future__ import annotations

import logging
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
from typing import Dict, TYPE_CHECKING

from core.config.thread_config import ThreadConfiguration
from core.utils.cleanup_result import CleanupResult, ModuleCleanupFailure, ShutdownResult

if TYPE_CHECKING:
    from core.module_interface import IModule


class ShutdownOrchestrator:
    """Orchestrates parallel module cleanup during application shutdown."""

    def __init__(self, config: ThreadConfiguration, logger: logging.Logger):
        """
        Initialize the ShutdownOrchestrator.

        Args:
            config: Thread configuration with timeout settings
            logger: Logger instance for recording shutdown events
        """
        self.config = config
        self.logger = logger

    def shutdown_modules(self, modules: Dict[str, "IModule"]) -> ShutdownResult:
        """
        Shut down all modules in parallel with timeout enforcement.

        Args:
            modules: Dictionary mapping module names to module instances

        Returns:
            ShutdownResult containing aggregated cleanup outcomes
        """
        if not modules:
            self.logger.info("No modules to shut down")
            return ShutdownResult(
                total_modules=0,
                success_count=0,
                failure_count=0,
                failures=[],
                duration_ms=0,
            )

        start_time = time.time()
        total_modules = len(modules)
        failures = []
        success_count = 0

        self.logger.info(f"Starting shutdown of {total_modules} modules")

        # Use ThreadPoolExecutor for parallel cleanup
        max_workers = min(total_modules, 10)  # Limit concurrent cleanups
        global_timeout = self.config.global_shutdown_timeout / 1000.0  # Convert to seconds

        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="shutdown") as executor:
            # Submit all cleanup tasks
            future_to_module = {
                executor.submit(self._cleanup_module, name, module): name
                for name, module in modules.items()
            }

            # Wait for all tasks with global timeout
            completed = 0
            try:
                for future in as_completed(future_to_module, timeout=global_timeout):
                    module_name = future_to_module[future]
                    completed += 1

                    try:
                        result = future.result(timeout=0.1)  # Should be immediate since future is done
                        if result.success:
                            success_count += 1
                            self.logger.debug(f"Module {module_name} cleanup succeeded")
                        else:
                            # Cleanup returned failure - check if it's a timeout
                            error_msg = result.error_message or "Cleanup returned failure"
                            if error_msg.startswith("TIMEOUT:"):
                                # Per-module timeout
                                failure_type = "timeout"
                                error_msg = error_msg[8:].strip()  # Remove "TIMEOUT:" prefix
                            else:
                                # Regular failure
                                failure_type = "false_return"

                            failure = ModuleCleanupFailure(
                                module_name=module_name,
                                failure_type=failure_type,
                                error_message=error_msg,
                            )
                            failures.append(failure)
                            self.logger.warning(f"Module {module_name} cleanup failed: {error_msg}")
                    except Exception as e:
                        # Exception during cleanup
                        failure = ModuleCleanupFailure(
                            module_name=module_name,
                            failure_type="exception",
                            exception_type=type(e).__name__,
                            error_message=str(e),
                            traceback=traceback.format_exc(),
                        )
                        failures.append(failure)
                        self.logger.error(f"Module {module_name} cleanup raised exception: {e}", exc_info=True)
            except FuturesTimeoutError:
                # Global timeout exceeded
                self.logger.error(f"Global shutdown timeout ({self.config.global_shutdown_timeout}ms) exceeded")

            # Handle modules that didn't complete within global timeout
            if completed < total_modules:
                timed_out_count = total_modules - completed
                self.logger.error(f"{timed_out_count} modules did not complete within global timeout")

                for future, module_name in future_to_module.items():
                    if not future.done():
                        failure = ModuleCleanupFailure(
                            module_name=module_name,
                            failure_type="timeout",
                            error_message=f"Cleanup exceeded global timeout of {self.config.global_shutdown_timeout}ms",
                        )
                        failures.append(failure)
                        self.logger.error(f"Module {module_name} cleanup timed out")

        failure_count = len(failures)
        duration_ms = int((time.time() - start_time) * 1000)

        # Log critical error if > 50% modules failed
        if failure_count > total_modules * 0.5:
            self.logger.critical(
                f"Widespread cleanup failure: {failure_count}/{total_modules} modules failed cleanup"
            )

        self.logger.info(
            f"Shutdown complete: {success_count} succeeded, {failure_count} failed, duration: {duration_ms}ms"
        )

        return ShutdownResult(
            total_modules=total_modules,
            success_count=success_count,
            failure_count=failure_count,
            failures=failures,
            duration_ms=duration_ms,
        )

    def _cleanup_module(self, module_name: str, module: "IModule") -> CleanupResult:
        """
        Clean up a single module with timeout enforcement.

        This method:
        1. Calls request_stop() if the module supports it
        2. Executes cleanup() in a separate thread with per-module timeout
        3. Returns CleanupResult indicating success or failure

        Args:
            module_name: Name of the module being cleaned up
            module: Module instance to clean up

        Returns:
            CleanupResult indicating cleanup outcome
        """
        # Get module-specific config
        module_config = self.config.get_module_config(module_name)
        cleanup_timeout = module_config.cleanup_timeout / 1000.0  # Convert to seconds

        # Step 1: Call request_stop() if available
        if hasattr(module, "request_stop"):
            try:
                self.logger.debug(f"Calling request_stop() for module {module_name}")
                module.request_stop()
            except Exception as e:
                self.logger.warning(f"request_stop() failed for module {module_name}: {e}")

        # Step 2: Execute cleanup in a separate thread with timeout
        result_container = {"result": None, "exception": None}

        def cleanup_wrapper():
            """Wrapper to capture cleanup result or exception."""
            try:
                result_container["result"] = module.cleanup()
            except Exception as e:
                result_container["exception"] = e

        cleanup_thread = threading.Thread(
            target=cleanup_wrapper,
            name=f"cleanup_{module_name}",
            daemon=True,
        )

        start_time = time.time()
        cleanup_thread.start()
        cleanup_thread.join(timeout=cleanup_timeout)
        duration_ms = int((time.time() - start_time) * 1000)

        # Step 3: Check outcome
        if cleanup_thread.is_alive():
            # Timeout occurred - mark with special error message prefix
            error_msg = f"TIMEOUT: Cleanup timeout after {module_config.cleanup_timeout}ms"
            self.logger.error(f"Module {module_name} {error_msg}")
            return CleanupResult.failure_result(error_message=error_msg)

        if result_container["exception"]:
            # Exception occurred
            exc = result_container["exception"]
            error_msg = f"Cleanup raised {type(exc).__name__}: {exc}"
            self.logger.error(f"Module {module_name} {error_msg}")
            raise result_container["exception"]

        # Success - return the result
        result = result_container["result"]
        if result is None:
            # Old-style module that returns None
            return CleanupResult.success_result()

        if isinstance(result, CleanupResult):
            # Set duration if not already set
            if result.duration_ms == 0:
                result.duration_ms = duration_ms
            return result

        # Unexpected return type
        self.logger.warning(f"Module {module_name} cleanup returned unexpected type: {type(result)}")
        return CleanupResult.success_result()


__all__ = ["ShutdownOrchestrator"]

