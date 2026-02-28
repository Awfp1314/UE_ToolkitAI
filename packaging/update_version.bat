@echo off
chcp 65001 >nul
echo ========================================
echo UE Toolkit - 更新 Inno Setup 版本号
echo ========================================
echo.

cd /d "%~dp0"
python update_version.py

echo.
pause
