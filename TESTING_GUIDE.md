# Testing Guide for UE_TOOKITS_AI_NEW

## Quick Start

### Method 1: Using the test runner script (Recommended)

```bash
# Run all tests
python run_tests.py

# Run specific test file
python run_tests.py tests/test_thread_configuration.py

# Run specific test function
python run_tests.py tests/test_thread_configuration.py::test_load_configuration_with_overrides
```

### Method 2: Direct pytest command

```bash
# If python is in PATH
python -m pytest tests/test_thread_configuration.py -v

# If using py launcher (Windows)
py -m pytest tests/test_thread_configuration.py -v

# If using full path
C:\DevTools\Python\python3\python.exe -m pytest tests/test_thread_configuration.py -v
```

### Method 3: Using batch/PowerShell scripts

```bash
# Windows Batch
run_tests.bat tests/test_thread_configuration.py

# PowerShell
powershell -ExecutionPolicy Bypass -File run_tests.ps1 tests/test_thread_configuration.py
```

## Common Test Commands

### Run all tests
```bash
python run_tests.py
```

### Run tests in a specific directory
```bash
python run_tests.py tests/
```

### Run a specific test file
```bash
python run_tests.py tests/test_thread_configuration.py
```

### Run a specific test function
```bash
python run_tests.py tests/test_thread_configuration.py::test_load_configuration_with_overrides
```

### Run tests with specific markers
```bash
python -m pytest -m unit          # Run only unit tests
python -m pytest -m integration   # Run only integration tests
python -m pytest -m thread        # Run only thread-related tests
```

### Run tests with coverage report
```bash
python -m pytest --cov=core --cov=modules --cov-report=html
# Then open htmlcov/index.html in browser
```

### Run tests with verbose output
```bash
python run_tests.py tests/test_thread_configuration.py -v
```

### Run tests and show print statements
```bash
python -m pytest tests/test_thread_configuration.py -s
```

## Test Markers

The following markers are available (defined in `pytest.ini`):

- `unit`: Unit tests for individual components
- `integration`: Integration tests for multiple components
- `slow`: Tests that take a long time to run
- `qt`: Tests that require PyQt6/QApplication
- `thread`: Tests involving threading/QThread
- `config`: Tests for configuration loading
- `service`: Tests for service layer
- `module`: Tests for application modules
- `migration`: Tests for migration tools

## Current Test Status

### Task 1: Core Configuration and Data Objects ✅

**File**: `tests/test_thread_configuration.py`

**Tests**:
- `test_load_configuration_with_overrides` ✅ PASSED
- `test_privacy_rule_apply_mask_and_redact` ✅ PASSED
- `test_cleanup_and_shutdown_results` ✅ PASSED
- `test_thread_state_and_task_info_creation` ✅ PASSED

**Coverage**:
- `core/config/thread_config.py`: 96%
- `core/utils/cleanup_result.py`: 100%
- `core/utils/thread_models.py`: 100%

**Status**: All tests passing (4/4)

## Troubleshooting

### Python not found

If you get "python: command not found" or similar errors:

1. **Check if Python is installed**:
   ```bash
   python --version
   py --version
   ```

2. **Use the test runner script** (it auto-detects Python):
   ```bash
   python run_tests.py
   ```

3. **Use full path to Python**:
   ```bash
   C:\DevTools\Python\python3\python.exe run_tests.py
   ```

### pytest not found

If you get "No module named pytest":

1. **Install pytest**:
   ```bash
   python -m pip install pytest pytest-qt pytest-cov
   ```

2. **Verify installation**:
   ```bash
   python -m pytest --version
   ```

### Import errors

If tests fail with import errors:

1. **Ensure you're in the project root**:
   ```bash
   cd C:\Users\wang\Desktop\UI TO NEW\UE_TOOKITS_AI_NEW
   ```

2. **Check Python path** (tests should handle this automatically)

## For AI Assistants (GPT/Codex)

When running tests in automated environments:

### ✅ Recommended approach

```python
# Use the test runner script
import subprocess
result = subprocess.run(
    ["python", "run_tests.py", "tests/test_thread_configuration.py"],
    cwd="C:/Users/wang/Desktop/UI TO NEW/UE_TOOKITS_AI_NEW",
    capture_output=True,
    text=True
)
print(result.stdout)
print(result.stderr)
```

### ✅ Alternative approach

```python
# Direct pytest invocation
import subprocess
result = subprocess.run(
    ["C:/DevTools/Python/python3/python.exe", "-m", "pytest", 
     "tests/test_thread_configuration.py", "-v"],
    cwd="C:/Users/wang/Desktop/UI TO NEW/UE_TOOKITS_AI_NEW",
    capture_output=True,
    text=True
)
print(result.stdout)
```

### ❌ Avoid

```bash
# Don't use bare pytest command (may not be in PATH)
pytest tests/test_thread_configuration.py

# Don't use python3 (doesn't exist on Windows)
python3 -m pytest tests/test_thread_configuration.py
```

