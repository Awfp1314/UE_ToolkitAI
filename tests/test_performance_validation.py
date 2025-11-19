"""Performance validation test suite (Task 15).

Aggregates and validates all performance benchmarks for ThreadManager system.

Performance Targets:
- ThreadManager initialization: < 50ms
- Task submission overhead: < 10ms per task
- Shutdown sequence: within global_shutdown_timeout
- Monitoring export: < 100ms for 1000 events

This test suite collects performance metrics and generates reports if targets are not met.
"""
import json
import platform
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

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


class PerformanceMetrics:
    """Container for performance metrics."""
    
    def __init__(self):
        self.metrics: List[Dict[str, Any]] = []
        self.system_info = {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "processor": platform.processor(),
            "machine": platform.machine(),
        }
    
    def add_metric(self, test_name: str, metric_name: str, value: float, target: float, passed: bool):
        """Add a performance metric."""
        self.metrics.append({
            "timestamp": datetime.now().isoformat(),
            "test_name": test_name,
            "metric_name": metric_name,
            "value": value,
            "target": target,
            "passed": passed,
            "system_info": self.system_info,
        })
    
    def get_failed_metrics(self) -> List[Dict[str, Any]]:
        """Get all failed metrics."""
        return [m for m in self.metrics if not m["passed"]]
    
    def save_to_json(self, filepath: Path):
        """Save metrics to JSON file."""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.metrics, f, indent=2)
    
    def generate_report(self, filepath: Path):
        """Generate performance analysis report."""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        failed = self.get_failed_metrics()
        total = len(self.metrics)
        passed = total - len(failed)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("# Performance Validation Report\n\n")
            f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**System Info**:\n")
            for key, value in self.system_info.items():
                f.write(f"- {key}: {value}\n")
            f.write(f"\n## Summary\n\n")
            f.write(f"- Total Tests: {total}\n")
            f.write(f"- Passed: {passed}\n")
            f.write(f"- Failed: {len(failed)}\n")
            f.write(f"- Pass Rate: {(passed/total*100):.1f}%\n\n")
            
            if failed:
                f.write("## Failed Performance Targets\n\n")
                for metric in failed:
                    f.write(f"### {metric['test_name']} - {metric['metric_name']}\n\n")
                    f.write(f"- **Value**: {metric['value']:.2f}ms\n")
                    f.write(f"- **Target**: {metric['target']:.2f}ms\n")
                    f.write(f"- **Exceeded by**: {(metric['value'] - metric['target']):.2f}ms\n\n")
            
            f.write("## All Metrics\n\n")
            f.write("| Test Name | Metric | Value | Target | Status |\n")
            f.write("|-----------|--------|-------|--------|--------|\n")
            for metric in self.metrics:
                status = "✅ PASS" if metric["passed"] else "❌ FAIL"
                f.write(f"| {metric['test_name']} | {metric['metric_name']} | "
                       f"{metric['value']:.2f}ms | {metric['target']:.2f}ms | {status} |\n")


@pytest.fixture(scope="module")
def perf_metrics():
    """Shared performance metrics collector."""
    return PerformanceMetrics()


class TestPerformanceValidation:
    """Performance validation test suite."""
    
    def test_thread_manager_initialization_time(self, perf_metrics):
        """Verify ThreadManager initialization time < 50ms."""
        target_ms = 50.0
        
        # Measure initialization time
        start_time = time.time()
        config = ThreadConfiguration()
        manager = EnhancedThreadManager(config)
        duration_ms = (time.time() - start_time) * 1000
        
        passed = duration_ms < target_ms
        perf_metrics.add_metric(
            "ThreadManager Initialization",
            "initialization_time",
            duration_ms,
            target_ms,
            passed
        )
        
        assert passed, f"Initialization took {duration_ms:.2f}ms, expected < {target_ms}ms"

    def test_task_submission_overhead(self, perf_metrics, qtbot):
        """Verify task submission overhead < 10ms per task."""
        target_ms = 10.0

        config = ThreadConfiguration(thread_pool_size=5, task_queue_size=20)
        manager = EnhancedThreadManager(config)

        def dummy_task(cancel_token):
            """Dummy task that does nothing."""
            return "done"

        # Measure submission time for 10 tasks
        num_tasks = 10
        start_time = time.time()

        for i in range(num_tasks):
            manager.run_in_thread(
                dummy_task,
                module_name="perf_test",
                task_name=f"task_{i}",
            )

        total_duration_ms = (time.time() - start_time) * 1000
        avg_duration_ms = total_duration_ms / num_tasks

        passed = avg_duration_ms < target_ms
        perf_metrics.add_metric(
            "Task Submission",
            "submission_overhead",
            avg_duration_ms,
            target_ms,
            passed
        )

        # Cleanup
        manager.cleanup()

        assert passed, f"Task submission took {avg_duration_ms:.2f}ms per task, expected < {target_ms}ms"

    def test_shutdown_sequence_time(self, perf_metrics):
        """Verify shutdown sequence completes within global_shutdown_timeout."""
        import logging

        # Create mock modules
        class MockModule:
            def __init__(self, name: str, delay: float = 0.1):
                self.name = name
                self.delay = delay

            def request_stop(self):
                pass

            def cleanup(self) -> CleanupResult:
                time.sleep(self.delay)
                return CleanupResult.success_result()

        # Create 10 modules with 0.1s cleanup each
        modules = {f"module_{i}": MockModule(f"module_{i}", 0.1) for i in range(10)}

        config = ThreadConfiguration(
            cleanup_timeout=1000,
            global_shutdown_timeout=5000,  # 5 seconds
        )
        logger = logging.getLogger("perf_test")
        orchestrator = ShutdownOrchestrator(config, logger)

        # Measure shutdown time
        start_time = time.time()
        result = orchestrator.shutdown_modules(modules)
        duration_ms = (time.time() - start_time) * 1000

        target_ms = config.global_shutdown_timeout
        passed = duration_ms < target_ms and result.is_success

        perf_metrics.add_metric(
            "Shutdown Sequence",
            "shutdown_time",
            duration_ms,
            target_ms,
            passed
        )

        assert passed, f"Shutdown took {duration_ms:.2f}ms, expected < {target_ms}ms"

    def test_monitoring_export_time(self, perf_metrics, tmp_path):
        """Verify monitoring export time < 100ms for 1000 events."""
        target_ms = 100.0

        config = ThreadConfiguration()
        monitor = ThreadMonitor(config)

        # Record 1000 events
        for i in range(1000):
            monitor.record_task_start(f"task_{i}", "mod", f"task_{i}", thread_id=i, thread_name=f"thread_{i}")
            if i % 2 == 0:
                monitor.record_task_complete(f"task_{i}", duration_ms=100)
            else:
                monitor.record_task_failed(f"task_{i}", "Error")

        # Measure export time
        out = tmp_path / "events.ndjson"
        start_time = time.time()
        count = monitor.export_ndjson(out, apply_privacy=False)
        duration_ms = (time.time() - start_time) * 1000

        passed = duration_ms < target_ms and count == 1000
        perf_metrics.add_metric(
            "Monitoring Export",
            "export_time",
            duration_ms,
            target_ms,
            passed
        )

        assert passed, f"Export took {duration_ms:.2f}ms, expected < {target_ms}ms"


@pytest.fixture(scope="module", autouse=True)
def save_performance_report(request, perf_metrics):
    """Save performance report after all tests complete."""
    yield

    # Save metrics to JSON
    logs_dir = PROJECT_ROOT / "logs" / "performance"
    perf_metrics.save_to_json(logs_dir / "thread_manager_benchmarks.json")

    # Generate report if any tests failed
    failed = perf_metrics.get_failed_metrics()
    if failed:
        reports_dir = PROJECT_ROOT / "reports"
        perf_metrics.generate_report(reports_dir / "performance_analysis.md")
        print(f"\n⚠️  Performance targets not met! Report saved to: {reports_dir / 'performance_analysis.md'}")
    else:
        print(f"\n✅ All performance targets met!")

    print(f"📊 Performance metrics saved to: {logs_dir / 'thread_manager_benchmarks.json'}")

