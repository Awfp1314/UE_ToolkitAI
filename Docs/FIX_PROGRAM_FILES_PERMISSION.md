# Program Files 权限问题修复

## 问题描述

程序打包成 .exe 后，安装在 `C:\Program Files` 下运行会报错：

```
LOADER: failed to create runtime-tmpdir... 拒绝访问
```

## 根本原因

1. PyInstaller 的 `runtime_tmpdir` 设置不当，尝试在程序目录创建临时文件
2. `main.py` 中的 `os.chdir(exe_dir)` 导致工作目录设置为受保护的 Program Files 目录
3. MCP 服务器日志尝试写入项目目录而非用户目录

## 修复内容

### 1. PyInstaller 配置 (`scripts/package/config/ue_toolkit.spec`)

- 确认 `runtime_tmpdir=None`（使用系统临时目录 `%TEMP%`）
- 添加详细注释说明不要使用相对路径

### 2. 主入口 (`main.py`)

- 移除打包环境下的 `os.chdir(exe_dir)`
- 只在开发环境设置工作目录
- 简化临时目录清理逻辑（PyInstaller 自动管理）

### 3. MCP 服务器日志 (`scripts/mcp_servers/blueprint_extractor_bridge.py`)

- 修改日志路径为用户目录：`%APPDATA%/ue_toolkit/user_data/logs/mcp`
- 跨平台兼容（Windows/macOS/Linux）

## 验证

所有配置和日志已正确使用用户目录：

- 配置：`%APPDATA%/ue_toolkit/user_data/configs`
- 日志：`%APPDATA%/ue_toolkit/user_data/logs`
- MCP 日志：`%APPDATA%/ue_toolkit/user_data/logs/mcp`

## 测试建议

1. 重新打包程序
2. 安装到 `C:\Program Files\UE_Toolkit`
3. 以普通用户权限运行
4. 验证程序正常启动，无权限错误
