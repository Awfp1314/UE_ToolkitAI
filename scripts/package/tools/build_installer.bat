@echo off
chcp 65001 >nul
echo ========================================
echo UE Toolkit - 自动化打包脚本
echo ========================================
echo.

cd /d "%~dp0"
python build_installer.py

echo.
pause
