@echo off
REM 清理 Windows 图标缓存脚本
REM 用于解决更新图标后快捷方式仍显示旧图标的问题

echo ========================================
echo 清理 Windows 图标缓存
echo ========================================
echo.

echo [1/4] 停止 Windows 资源管理器...
taskkill /f /im explorer.exe >nul 2>&1

echo [2/4] 删除图标缓存文件...
cd /d %userprofile%\AppData\Local\Microsoft\Windows\Explorer
attrib -h IconCache.db >nul 2>&1
del IconCache.db /f /q >nul 2>&1
del iconcache_*.db /f /q >nul 2>&1
del thumbcache_*.db /f /q >nul 2>&1

echo [3/4] 重启 Windows 资源管理器...
start explorer.exe

echo [4/4] 完成！
echo.
echo 图标缓存已清理，桌面图标应该已更新。
echo 如果仍未更新，请尝试：
echo   1. 删除桌面快捷方式
echo   2. 从开始菜单重新创建快捷方式
echo.
pause
