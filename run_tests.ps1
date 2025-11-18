# Test runner script for UE_TOOKITS_AI_NEW
# This script ensures tests run with the correct Python interpreter

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Running pytest tests" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Try to find Python
$pythonCmd = $null

# Method 1: Try python command
try {
    $null = python --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        $pythonCmd = "python"
    }
} catch {}

# Method 2: Try py launcher
if (-not $pythonCmd) {
    try {
        $null = py --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            $pythonCmd = "py"
        }
    } catch {}
}

# Method 3: Try known installation path
if (-not $pythonCmd) {
    $knownPath = "C:\DevTools\Python\python3\python.exe"
    if (Test-Path $knownPath) {
        $pythonCmd = $knownPath
    }
}

# If we get here and still no Python, error out
if (-not $pythonCmd) {
    Write-Host "ERROR: Python not found!" -ForegroundColor Red
    Write-Host "Please ensure Python is installed and in PATH." -ForegroundColor Red
    exit 1
}

Write-Host "Using Python: $pythonCmd" -ForegroundColor Green
Write-Host ""

# Show Python version
& $pythonCmd --version
Write-Host ""

# Run pytest with the specified test file or all tests
if ($args.Count -eq 0) {
    Write-Host "Running all tests..." -ForegroundColor Yellow
    & $pythonCmd -m pytest tests/ -v
} else {
    Write-Host "Running tests: $($args[0])" -ForegroundColor Yellow
    & $pythonCmd -m pytest $args[0] -v
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Tests completed" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

