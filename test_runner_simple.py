"""Simple test runner that prints output."""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

# Run pytest programmatically
import pytest

if __name__ == "__main__":
    print("=" * 60)
    print("Running pytest tests")
    print("=" * 60)
    print()
    
    # Run pytest with verbose output
    exit_code = pytest.main([
        "tests/test_thread_configuration.py",
        "-v",
        "--tb=short",
        "--color=yes"
    ])
    
    print()
    print("=" * 60)
    print(f"Tests completed with exit code: {exit_code}")
    print("=" * 60)
    
    sys.exit(exit_code)

