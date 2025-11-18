# Implementation Plan

## Overview

This implementation plan breaks down the thread and resource management unification into discrete, manageable coding tasks. Each task builds incrementally on previous work, with testing integrated throughout.

## Task List

- [x] 1. Implement core configuration and data objects

  - Create ThreadConfiguration, ModuleThreadConfig, and PrivacyRule classes with JSON loading
  - Create CleanupResult, ModuleCleanupFailure, ShutdownResult data classes
  - Create ThreadState enum and TaskInfo, ThreadInfo data classes
  - Write unit tests for configuration loading and data object creation
  - _Requirements: 8.1, 8.2, 8.3, 3.1_

- [x] 2. Implement ThreadMonitor with privacy-aware export

  - Create ThreadLifecycleEvent and ThreadMetrics classes
  - Implement ThreadMonitor with record methods for all states (start, complete, failed, cancelled, timeout)
  - Implement NDJSON export with privacy rule application
  - Write unit tests for event recording and privacy redaction
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 3. Enhance existing Worker and CancellationToken

  - Review existing Worker class in core/utils/thread_utils.py
  - Add error signal handling if not present
  - Ensure CancellationToken is properly integrated
  - Write unit tests for Worker error handling and cancellation
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 4. Implement EnhancedThreadManager core functionality
- [ ] 4.1 Implement singleton accessor with double-checked locking

  - Create get_thread_manager() function with thread-safe initialization
  - Load ThreadConfiguration from file with fallback to defaults
  - Write unit tests for singleton behavior and thread safety
  - _Requirements: 14.1, 14.2_

- [ ] 4.2 Implement CancellationToken injection with signature inspection

  - Create \_inject_cancellation_token() method with functools unwrapping
  - Use inspect.signature to detect cancel_token parameter
  - Log one-time warning for functions without cancel_token
  - Write unit tests for various function signatures (plain, partial, wrapped, lambda)
  - _Requirements: 2.1, 2.2, 2.3_

- [ ] 4.3 Implement queue-based task submission with backpressure

  - Create \_task_queue with configurable size
  - Implement run_in_thread() with non-blocking enqueue
  - Raise QueueFullError when queue is full
  - Return (QThread, Worker, task_id) or (None, None, task_id)
  - Write unit tests for queue overflow and task queuing
  - _Requirements: 11.1, 11.2, 11.3, 11.4_

- [ ] 4.4 Implement \_start_task() with QThread + Worker creation

  - Create QThread and Worker from task metadata
  - Wire signals: started, finished, result, error
  - Set thread name using \_create_thread_name()
  - Create TaskInfo and store in \_active_tasks
  - Record task start in ThreadMonitor
  - Write unit tests for thread creation and signal wiring
  - _Requirements: 1.1, 1.4, 14.4_

- [ ] 4.5 Implement timeout mechanism with QTimer and grace period

  - Create \_setup_timeout() method with QTimer
  - On timeout: cancel token, start grace period timer
  - Handle completion during grace vs stuck after grace
  - Write unit tests for timeout scenarios (complete before, during grace, stuck)
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [ ] 4.6 Implement task completion and cleanup

  - Create \_cleanup_task() to record final state and remove from active_tasks
  - Create \_on_thread_finished() to cleanup, release semaphore, process queue
  - Create \_handle_task_error() for error signal handling
  - Implement cancel_task() for user-initiated cancellation
  - Write unit tests for all completion paths (success, error, cancel, timeout)
  - Write unit tests for task_id propagation and cancellation via task_id
  - Write unit tests for cancelling queued tasks (verify queue state and cleanup)
  - Add performance assertions for task submission overhead (< 10ms)
  - _Requirements: 2.3, 2.4, 2.5, 5.2, 5.3, 5.4_

- [ ] 4.7 Implement thread pool management and monitoring

  - Implement get_active_threads() for snapshot
  - Implement get_metrics() for aggregated metrics
  - Implement cleanup() for manager shutdown
  - Write unit tests for pool utilization and cleanup
  - _Requirements: 5.1, 5.2, 5.5, 11.5_

- [ ] 5. Update IModule interface with CleanupResult contract

  - Add request_stop() method to IModule (optional, default no-op)
  - Update cleanup() signature to return CleanupResult
  - Create backward compatibility wrapper for legacy cleanup methods
  - Write unit tests for interface compliance
  - _Requirements: 3.1, 3.2, 3.4, 3.5_

- [ ] 6. Implement ShutdownOrchestrator for parallel module cleanup

  - Create ShutdownOrchestrator class with ThreadPoolExecutor
  - Implement shutdown_modules() with parallel cleanup submission
  - Implement \_cleanup_module() with request_stop() and timeout enforcement
  - Aggregate failures and create ShutdownResult
  - Log critical error if > 50% modules fail
  - Write integration tests for shutdown sequence with multiple modules
  - Add integration test to verify request_stop() is called before cleanup()
  - Add integration test to verify per-module cleanup timeout overrides
  - Add performance assertions for shutdown time (within global_shutdown_timeout)
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 10.1, 10.2, 10.3, 10.4_

- [ ] 7. Implement FeatureFlagManager for migration control

  - Create ModuleFeatureFlags and FeatureFlagManager classes
  - Implement JSON loading and saving
  - Implement is_thread_manager_enforced() and set_enforcement()
  - Create get_feature_flags() singleton accessor
  - Write unit tests for flag management
  - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_

- [ ] 8. Implement MigrationValidator for static analysis

  - Create QThreadViolation data class
  - Implement AST-based scanning for QThread usage (instantiation, subclass, import)
  - Implement scan_module() and scan_all_modules()
  - Implement generate_report() for JSON output
  - Write unit tests with sample code containing violations
  - _Requirements: 6.1, 6.5_

- [ ] 9. Integrate ShutdownOrchestrator into AppManager

  - Update AppManager.quit() to use ShutdownOrchestrator
  - Log ShutdownResult with success/failure details
  - Handle partial and complete failures appropriately
  - Write integration tests for application shutdown
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [ ] 10. Create developer documentation

  - Write guide for implementing cancellation-aware tasks
  - Write guide for implementing cleanup contracts
  - Write guide for configuring timeouts
  - Write troubleshooting guide for stuck tasks and cleanup failures
  - Include code examples and best practices
  - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5_

- [ ] 11. Migrate AI Assistant module to ThreadManager
- [ ] 11.1 Enable feature flag for ai_assistant module

  - Set thread_manager_enforced: true in config/feature_flags.json
  - _Requirements: 13.1, 13.2_

- [ ] 11.2 Migrate APIClient from QThread to ThreadManager

  - Replace QThread inheritance with task function
  - Add cancel_token parameter to task function
  - Update cleanup() to return CleanupResult
  - Update all call sites to use ThreadManager.run_in_thread()
  - Run existing tests to verify functionality
  - _Requirements: 1.1, 1.3, 2.1, 3.1, 6.2, 6.3_

- [ ] 11.3 Migrate AsyncMemoryCompressor from QThread to ThreadManager

  - Replace QThread inheritance with task function
  - Add cancel_token parameter
  - Update cleanup() to return CleanupResult
  - Update call sites
  - Run existing tests
  - _Requirements: 1.1, 1.3, 2.1, 3.1, 6.2, 6.3_

- [ ] 11.4 Migrate FunctionCallingCoordinator from QThread to ThreadManager

  - Replace QThread inheritance with task function
  - Add cancel_token parameter
  - Update cleanup() to return CleanupResult
  - Update call sites
  - Run existing tests
  - _Requirements: 1.1, 1.3, 2.1, 3.1, 6.2, 6.3_

- [ ] 11.5 Migrate remaining AI Assistant workers

  - Migrate NonStreamingWorker
  - Migrate StreamingAPIClient
  - Migrate AsyncTemplateGeneratorThread
  - Run full AI Assistant test suite
  - _Requirements: 1.1, 1.3, 2.1, 3.1, 6.2, 6.3_

- [ ] 11.6 Verify feature flag behavior for ai_assistant module

  - Identify key functionality regression test cases (API calls, streaming, function calling, memory compression)
  - Test module behavior with thread_manager_enforced: true
  - Test module behavior with thread_manager_enforced: false (rollback scenario)
  - Compare results and verify functionality is identical in both modes
  - Document any behavioral differences or edge cases
  - _Requirements: 13.1, 13.2, 13.5_

- [ ] 11.7 Run MigrationValidator on ai_assistant module

  - Verify no direct QThread usage remains
  - Generate migration report
  - _Requirements: 6.5_

- [ ] 12. Migrate Asset Manager module to ThreadManager
- [ ] 12.1 Enable feature flag for asset_manager module

  - Set thread_manager_enforced: true in config/feature_flags.json
  - _Requirements: 13.1, 13.2_

- [ ] 12.2 Migrate AssetLoadThread from QThread to ThreadManager

  - Replace QThread inheritance with task function
  - Add cancel_token parameter
  - Update LazyAssetLoader to use ThreadManager
  - Update cleanup() to return CleanupResult
  - Run existing tests
  - _Requirements: 1.1, 1.3, 2.1, 3.1, 6.2, 6.3_

- [ ] 12.3 Verify feature flag behavior for asset_manager module

  - Identify key functionality regression test cases (lazy loading, asset retrieval, error handling)
  - Test module behavior with thread_manager_enforced: true
  - Test module behavior with thread_manager_enforced: false (rollback scenario)
  - Compare results and verify functionality is identical in both modes
  - Document any behavioral differences or edge cases
  - _Requirements: 13.1, 13.2, 13.5_

- [ ] 12.4 Run MigrationValidator on asset_manager module

  - Verify no direct QThread usage remains
  - _Requirements: 6.5_

- [ ] 13. Add CI integration for MigrationValidator

  - Create GitHub Actions workflow for thread validation
  - Configure to run on push and pull request
  - Limit scan scope to migrated modules only (ai_assistant, asset_manager)
  - Configure failure threshold and report output path
  - Fail build if violations found in migrated modules
  - Add workflow badge to README
  - _Requirements: 6.5_

- [ ] 14. Write comprehensive test suite
- [ ] 14.1 Unit tests for ThreadConfiguration

  - Test JSON loading with valid and invalid data
  - Test module override resolution
  - Test default value fallback
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 12.1_

- [ ] 14.2 Unit tests for CancellationToken injection

  - Test function with cancel_token parameter
  - Test function without cancel_token parameter
  - Test functools.partial wrapped function
  - Test functools.wraps decorated function
  - Test lambda function
  - Test class method
  - _Requirements: 2.1, 2.2, 2.3, 12.2_

- [ ] 14.3 Unit tests for timeout mechanism

  - Test task completes before timeout
  - Test task exceeds timeout and completes during grace
  - Test task stuck after grace period
  - Test timeout with zero (no timeout)
  - Add performance benchmarks for timeout overhead
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 12.3_

- [ ] 14.4 Unit tests for cleanup contract

  - Test CleanupResult success
  - Test CleanupResult failure with error message
  - Test exception during cleanup
  - Test cleanup timeout
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 12.4_

- [ ] 14.5 Unit tests for ThreadMonitor

  - Test event recording for all states
  - Test NDJSON export format
  - Test privacy rule application (redact and mask)
  - Test metrics aggregation
  - Add performance benchmark for export (target < 100ms for 1000 events)
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 12.5_

- [ ] 14.6 Integration test for shutdown sequence

  - Create multiple test modules with varying cleanup times
  - Test some modules fail cleanup
  - Test some modules timeout
  - Test mixed failure scenario: combine timeout + exception + normal completion
  - Verify parallel execution
  - Verify failure aggregation in ShutdownResult with correct failure_type classification
  - Verify ShutdownResult.is_partial_failure() logic with mixed failures
  - Verify critical error logging when > 50% modules fail
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 12.4_

- [ ] 14.7 Integration test for thread pool backpressure

  - Submit tasks up to pool limit
  - Submit tasks up to queue limit
  - Verify queue overflow rejection with QueueFullError
  - Verify task execution order
  - Test cancelling queued tasks and verify queue state consistency
  - Test cancelling running tasks and verify next queued task starts
  - Add performance benchmark for pool utilization under load
  - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 12.5_

- [ ] 15. Performance validation and optimization

  - Aggregate all performance benchmarks from unit/integration tests
  - Verify ThreadManager initialization time (target < 50ms)
  - Verify task submission overhead (target < 10ms per task)
  - Verify shutdown sequence time (target within global_shutdown_timeout)
  - Verify monitoring export time (target < 100ms for 1000 events)
  - Create performance regression test suite
  - If performance targets not met:
    - Output detailed benchmark data with timestamps and system info
    - Log performance metrics to: logs/performance/thread_manager_benchmarks.json
    - Format: JSON with fields {timestamp, test_name, metric_name, value, target, system_info}
    - Generate performance report with bottleneck analysis to: reports/performance_analysis.md
    - Document optimization recommendations
  - Optimize based on benchmark data and re-test
  - Document performance characteristics and tuning guidelines
  - _Requirements: Performance targets from design_

- [ ] 16. Final validation and cleanup
  - Run MigrationValidator on entire codebase
  - Verify no direct QThread usage in migrated modules
  - Remove backward compatibility wrappers
  - Remove feature flags for fully migrated modules
  - Update all documentation
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

## Notes

- Tasks are ordered to build incrementally
- Each task includes specific requirements it addresses
- Testing is integrated throughout, not deferred to end
- Migration is phased (AI Assistant first, then Asset Manager)
- Feature flags allow rollback if issues discovered
- CI integration prevents regression after migration
