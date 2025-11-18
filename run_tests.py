#!/usr/bin/env python
"""
Test runner script for UE_TOOKITS_AI_NEW.
This script runs pytest tests and displays results.

Usage:
    python run_tests.py                          # Run all tests
    python run_tests.py tests/test_xxx.py        # Run specific test file
    python run_tests.py tests/test_xxx.py::test_func  # Run specific test
"""
import sys
import subprocess
from pathlib import Path


def main():
    """Run pytest with the given arguments."""
    # Get the project root
    project_root = Path(__file__).parent
    
    # Build pytest command
    pytest_args = [sys.executable, "-m", "pytest"]
    
    # Add test path or default to tests/
    if len(sys.argv) > 1:
        pytest_args.extend(sys.argv[1:])
    else:
        pytest_args.append("tests/")
    
    # Add verbose flag if not already present
    if "-v" not in pytest_args and "--verbose" not in pytest_args:
        pytest_args.append("-v")
    
    # Print command
    print("=" * 60)
    print("Running pytest tests")
    print("=" * 60)
    print(f"Command: {' '.join(pytest_args)}")
    print(f"Python: {sys.executable}")
    print(f"Version: {sys.version}")
    print("=" * 60)
    print()
    
    # Run pytest
    try:
        result = subprocess.run(
            pytest_args,
            cwd=project_root,
            check=False
        )
        
        print()
        print("=" * 60)
        print(f"Tests completed with exit code: {result.returncode}")
        print("=" * 60)
        
        return result.returncode
        
    except Exception as e:
        print(f"ERROR: Failed to run tests: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

