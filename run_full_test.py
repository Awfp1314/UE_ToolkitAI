"""Run full test suite and generate detailed report."""
import sys
import os
from datetime import datetime
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

def main():
    """Run tests and generate report."""
    print("=" * 70)
    print(f"Full Test Suite - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()
    
    # Check pytest
    try:
        import pytest
        print(f"✅ pytest version: {pytest.__version__}")
    except ImportError:
        print("❌ pytest not installed!")
        return 1
    
    # Check dependencies
    print("\n" + "=" * 70)
    print("Checking dependencies...")
    print("=" * 70)
    
    dependencies = {
        "core.config.thread_config": ["ThreadConfiguration", "ModuleThreadConfig", "PrivacyRule"],
        "core.utils.cleanup_result": ["CleanupResult", "ModuleCleanupFailure", "ShutdownResult"],
        "core.utils.thread_models": ["ThreadState", "TaskInfo", "ThreadInfo"],
    }
    
    all_ok = True
    for module_name, classes in dependencies.items():
        try:
            module = __import__(module_name, fromlist=classes)
            for cls in classes:
                if hasattr(module, cls):
                    print(f"  ✅ {module_name}.{cls}")
                else:
                    print(f"  ❌ {module_name}.{cls} not found")
                    all_ok = False
        except ImportError as e:
            print(f"  ❌ {module_name}: {e}")
            all_ok = False
    
    if not all_ok:
        print("\n❌ Dependency check failed!")
        return 1
    
    # Run tests
    print("\n" + "=" * 70)
    print("Running tests...")
    print("=" * 70)
    print()

    # Run with detailed output
    exit_code = pytest.main([
        "tests/test_thread_configuration.py",
        "tests/test_thread_monitor.py",
        "tests/test_worker.py",
        "tests/test_thread_manager.py",
        "-v",
        "--tb=short",
        "-p", "no:warnings",
        "--no-header"
    ])
    
    # Summary
    print("\n" + "=" * 70)
    if exit_code == 0:
        print("✅ ALL TESTS PASSED!")
    else:
        print(f"❌ TESTS FAILED (exit code: {exit_code})")
    print("=" * 70)
    
    # Write summary to file
    summary = {
        "timestamp": datetime.now().isoformat(),
        "pytest_version": pytest.__version__,
        "exit_code": exit_code,
        "status": "PASSED" if exit_code == 0 else "FAILED",
        "test_files": [
            "tests/test_thread_configuration.py",
            "tests/test_thread_monitor.py",
            "tests/test_worker.py",
            "tests/test_thread_manager.py"
        ]
    }
    
    with open("test_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    
    print(f"\nSummary written to: test_summary.json")
    
    return exit_code

if __name__ == "__main__":
    sys.exit(main())

