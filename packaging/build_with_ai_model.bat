@echo off
chcp 65001 >nul
echo ========================================
echo UE Toolkit 完整打包（包含AI模型）
echo ========================================
echo.
echo 此版本会将AI模型打包进EXE
echo 优点：用户无需联网下载模型
echo 缺点：文件更大（约370MB）
echo.

echo [1/4] 检查AI模型是否存在...
set MODEL_PATH=%USERPROFILE%\.cache\huggingface\hub\models--BAAI--bge-small-zh-v1.5
if exist "%MODEL_PATH%" (
    echo ✓ 找到AI模型: %MODEL_PATH%
) else (
    echo ✗ 未找到AI模型
    echo 请先运行程序一次，让它下载模型
    pause
    exit /b 1
)

echo.
echo [2/4] 清理旧的打包文件...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
echo ✓ 清理完成

echo.
echo [3/4] 开始打包（包含AI模型）...
echo 注意：打包时间较长（15-20分钟）
echo 打包后的文件约370MB
echo 请耐心等待...
echo.
python -m PyInstaller ue_toolkit.spec --clean
if errorlevel 1 (
    echo [错误] 打包失败
    pause
    exit /b 1
)

echo.
echo [4/4] 检查打包结果...
if exist "dist\UE_Toolkit.exe" (
    for %%I in ("dist\UE_Toolkit.exe") do set SIZE=%%~zI
    set /a SIZE_MB=!SIZE!/1048576
    echo ========================================
    echo 打包成功！
    echo ========================================
    echo 输出文件: dist\UE_Toolkit.exe
    echo 文件大小: !SIZE_MB! MB
    echo.
    echo ✓ AI模型已打包进EXE
    echo ✓ 用户无需联网即可使用AI功能
    echo ========================================
) else (
    echo [错误] 未找到生成的EXE文件
    pause
    exit /b 1
)

echo.
pause
