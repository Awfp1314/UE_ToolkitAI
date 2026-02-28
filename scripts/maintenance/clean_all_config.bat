@echo off
chcp 65001 >nul
echo ========================================
echo UE Toolkit - Complete Clean for Testing
echo ========================================
echo.
echo This script will DELETE ALL configuration and data:
echo   [X] All app configs in AppData
echo   [X] AI model cache
echo   [X] Asset library configs
echo   [X] All user data
echo.
echo This simulates a fresh installation!
echo.
pause

echo.
echo Starting complete cleanup...
echo.

REM Clean AI model cache
echo [1/2] Cleaning AI model cache...
if exist "%USERPROFILE%\.cache\huggingface" (
    rmdir /s /q "%USERPROFILE%\.cache\huggingface"
    echo   [OK] Deleted: %USERPROFILE%\.cache\huggingface
) else (
    echo   [SKIP] AI model cache not found
)

REM Clean entire app data directory
echo [2/2] Cleaning all app data...
if exist "%APPDATA%\ue_toolkit" (
    rmdir /s /q "%APPDATA%\ue_toolkit"
    echo   [OK] Deleted: %APPDATA%\ue_toolkit
) else (
    echo   [SKIP] App data directory not found
)

echo.
echo ========================================
echo Complete cleanup finished!
echo ========================================
echo.
echo All configuration and data has been removed.
echo You can now test the installer as a fresh installation.
echo.
pause
