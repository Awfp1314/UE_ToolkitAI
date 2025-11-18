"""Verify tests and write results to file."""
import sys
import os
from io import StringIO
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

# Capture output
output = StringIO()

def write_output(msg):
    """Write to both stdout and string buffer."""
    print(msg)
    output.write(msg + "\n")

write_output("=" * 60)
write_output(f"Test Verification - {datetime.now()}")
write_output("=" * 60)
write_output("")

# Try to import pytest
try:
    import pytest
    write_output(f"✅ pytest found: version {pytest.__version__}")
except ImportError as e:
    write_output(f"❌ pytest not found: {e}")
    sys.exit(1)

# Try to import test modules
write_output("")
write_output("Checking test dependencies...")
write_output("")

try:
    from core.config.thread_config import ThreadConfiguration, ModuleThreadConfig, PrivacyRule
    write_output("✅ core.config.thread_config imported successfully")
except ImportError as e:
    write_output(f"❌ Failed to import thread_config: {e}")

try:
    from core.utils.cleanup_result import CleanupResult, ModuleCleanupFailure, ShutdownResult
    write_output("✅ core.utils.cleanup_result imported successfully")
except ImportError as e:
    write_output(f"❌ Failed to import cleanup_result: {e}")

try:
    from core.utils.thread_models import ThreadState, TaskInfo, ThreadInfo
    write_output("✅ core.utils.thread_models imported successfully")
except ImportError as e:
    write_output(f"❌ Failed to import thread_models: {e}")

# Run the tests
write_output("")
write_output("=" * 60)
write_output("Running tests...")
write_output("=" * 60)
write_output("")

exit_code = pytest.main([
    "tests/test_thread_configuration.py",
    "-v",
    "--tb=short",
    "-p", "no:warnings"
])

write_output("")
write_output("=" * 60)
write_output(f"Tests completed with exit code: {exit_code}")
write_output("=" * 60)

# Write results to file
result_file = "test_results.txt"
with open(result_file, "w", encoding="utf-8") as f:
    f.write(output.getvalue())

write_output("")
write_output(f"Results written to: {result_file}")

sys.exit(exit_code)

