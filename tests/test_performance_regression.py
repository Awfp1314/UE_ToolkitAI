"""Performance regression test suite.

This test suite ensures that performance does not degrade over time.
It uses the same benchmarks as test_performance_validation.py but is designed
to run in CI/CD pipelines to catch performance regressions early.

Performance Targets (must not exceed):
- ThreadManager initialization: < 50ms
- Task submission overhead: < 10ms per task
- Shutdown sequence: within global_shutdown_timeout
- Monitoring export: < 100ms for 1000 events
"""
import sys
import time
from pathlib import Path

import pytest

# Ensure project root on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config.thread_config import ThreadConfiguration  # noqa: E402
from core.utils.thread_manager import EnhancedThreadManager  # noqa: E402
from core.utils.thread_monitor import ThreadMonitor  # noqa: E402
from core.utils.shutdown_orchestrator import ShutdownOrchestrator  # noqa: E402
from core.utils.cleanup_result import CleanupResult  # noqa: E402


@pytest.mark.performance
class TestPerformanceRegression:
    """Performance regression tests - fail if performance degrades."""
    
    def test_initialization_regression(self):
        """Ensure ThreadManager initialization stays < 50ms."""
        target_ms = 50.0
        
        start_time = time.time()
        config = ThreadConfiguration()
        manager = EnhancedThreadManager(config)
        duration_ms = (time.time() - start_time) * 1000
        
        assert duration_ms < target_ms, (
            f"PERFORMANCE REGRESSION: Initialization took {duration_ms:.2f}ms, "
            f"expected < {target_ms}ms"
        )
    
    def test_submission_overhead_regression(self, qtbot):
        """Ensure task submission overhead stays < 10ms per task."""
        target_ms = 10.0
        
        config = ThreadConfiguration(thread_pool_size=5, task_queue_size=20)
        manager = EnhancedThreadManager(config)
        
        def dummy_task(cancel_token):
            return "done"
        
        num_tasks = 10
        start_time = time.time()
        
        for i in range(num_tasks):
            manager.run_in_thread(
                dummy_task,
                module_name="regression_test",
                task_name=f"task_{i}",
            )
        
        total_duration_ms = (time.time() - start_time) * 1000
        avg_duration_ms = total_duration_ms / num_tasks
        
        manager.cleanup()
        
        assert avg_duration_ms < target_ms, (
            f"PERFORMANCE REGRESSION: Task submission took {avg_duration_ms:.2f}ms per task, "
            f"expected < {target_ms}ms"
        )
    
    def test_shutdown_time_regression(self):
        """Ensure shutdown sequence stays within timeout."""
        import logging
        
        class MockModule:
            def __init__(self, name: str, delay: float = 0.1):
                self.name = name
                self.delay = delay
            
            def request_stop(self):
                pass
            
            def cleanup(self) -> CleanupResult:
                time.sleep(self.delay)
                return CleanupResult.success_result()
        
        modules = {f"module_{i}": MockModule(f"module_{i}", 0.1) for i in range(10)}
        
        config = ThreadConfiguration(
            cleanup_timeout=1000,
            global_shutdown_timeout=5000,
        )
        logger = logging.getLogger("regression_test")
        orchestrator = ShutdownOrchestrator(config, logger)
        
        start_time = time.time()
        result = orchestrator.shutdown_modules(modules)
        duration_ms = (time.time() - start_time) * 1000
        
        target_ms = config.global_shutdown_timeout
        
        assert duration_ms < target_ms and result.is_success, (
            f"PERFORMANCE REGRESSION: Shutdown took {duration_ms:.2f}ms, "
            f"expected < {target_ms}ms"
        )
    
    def test_export_time_regression(self, tmp_path):
        """Ensure monitoring export stays < 100ms for 1000 events."""
        target_ms = 100.0
        
        config = ThreadConfiguration()
        monitor = ThreadMonitor(config)
        
        for i in range(1000):
            monitor.record_task_start(f"task_{i}", "mod", f"task_{i}", thread_id=i, thread_name=f"thread_{i}")
            if i % 2 == 0:
                monitor.record_task_complete(f"task_{i}", duration_ms=100)
            else:
                monitor.record_task_failed(f"task_{i}", "Error")
        
        out = tmp_path / "events.ndjson"
        start_time = time.time()
        count = monitor.export_ndjson(out, apply_privacy=False)
        duration_ms = (time.time() - start_time) * 1000
        
        assert duration_ms < target_ms and count == 1000, (
            f"PERFORMANCE REGRESSION: Export took {duration_ms:.2f}ms, "
            f"expected < {target_ms}ms"
        )

