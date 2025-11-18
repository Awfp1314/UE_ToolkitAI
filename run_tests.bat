@echo off
REM Test runner script for UE_TOOKITS_AI_NEW
REM This script ensures tests run with the correct Python interpreter

echo ========================================
echo Running pytest tests
echo ========================================
echo.

REM Try to find Python
set PYTHON_CMD=

REM Method 1: Try python command
python --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=python
    goto :run_tests
)

REM Method 2: Try py launcher
py --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=py
    goto :run_tests
)

REM Method 3: Try known installation path
if exist "C:\DevTools\Python\python3\python.exe" (
    set PYTHON_CMD=C:\DevTools\Python\python3\python.exe
    goto :run_tests
)

REM If we get here, Python was not found
echo ERROR: Python not found!
echo Please ensure Python is installed and in PATH.
exit /b 1

:run_tests
echo Using Python: %PYTHON_CMD%
echo.

REM Show Python version
%PYTHON_CMD% --version
echo.

REM Run pytest with the specified test file or all tests
if "%1"=="" (
    echo Running all tests...
    %PYTHON_CMD% -m pytest tests/ -v
) else (
    echo Running tests: %1
    %PYTHON_CMD% -m pytest %1 -v
)

echo.
echo ========================================
echo Tests completed
echo ========================================

