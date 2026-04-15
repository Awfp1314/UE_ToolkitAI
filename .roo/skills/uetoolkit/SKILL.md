---
name: UE Toolkit 开发规范
description: 帮助在 UE Toolkit 项目中编写符合规范的 Python + PyQt6 代码
keywords: python, pyqt6, ue toolkit, 模块化, 线程安全, remote control api
---

# UE Toolkit 开发规范

## 架构原则

模块化 PyQt6 桌面应用，三层架构：

- `core/` - 核心层（日志、配置、服务）
- `modules/` - 功能模块层（通过 `manifest.json` 自动发现）
- `ui/` - 全局 UI 组件

依赖规则：模块可依赖 core，模块间禁止直接导入（通过依赖注入或 `core.services`），UI 可调用 Logic，反之禁止。

## UE 集成架构

### Remote Control API（推荐）

```python
# 使用 HTTP Remote Control API 与 UE 通信
from modules.ai_assistant.clients.ue_tool_client import UEToolClient

client = UEToolClient(base_url="http://127.0.0.1:30010")
result = client.execute_tool_rpc("ExtractBlueprint", AssetPath="/Game/BP_Test")
```

**架构**：`Python App → HTTP (30010) → Remote Control API → UE Subsystem`

**优势**：

- UE 官方 API，稳定可靠
- 标准 HTTP + JSON，易调试
- 支持读写操作
- 无需自定义协议

**配置**：UE 编辑器 → 项目设置 → Remote Control → 启用 Remote Control Web Server

### 连接检测

```python
# UI 层自动检测（每 5 秒）
def _check_ue_connection(self):
    response = requests.get('http://127.0.0.1:30010/remote/info', timeout=1.5)
    if response.status_code == 200:
        self._ue_connection_changed.emit(True)
```

## 必须遵守的规范

### 日志

```python
from core.logger import get_logger
logger = get_logger(__name__)
# 禁止 print()，异常必须记录
try:
    ...
except Exception as e:
    logger.exception(f"操作失败: {e}")
```

### 路径操作

```python
from pathlib import Path
# 使用 Path 对象，禁止字符串拼接
config_path = Path.home() / "AppData" / "Roaming" / "ue_toolkit"
```

### PyQt6 线程安全

```python
class Worker(QThread):
    result_ready = pyqtSignal(object)  # 信号必须在类级别定义
    def run(self):
        result = do_work()
        self.result_ready.emit(result)  # 禁止直接操作 UI
# 主线程连接信号
worker.result_ready.connect(self.update_ui)
```

### 资源清理

```python
def cleanup(self) -> CleanupResult:
    try:
        if self.worker:
            self.worker.quit()
            self.worker.wait(1000)
        return CleanupResult.success()
    except Exception as e:
        return CleanupResult.failure_result(str(e))
```

### 版本管理

```python
from version import VERSION  # 只在 version.py 定义版本号
```

版本号格式：`MAJOR.MINOR.PATCH`（如 1.2.18）

版本更新由 Kiro Hook 自动管理：

- 功能性变更：更新 `version.py` + 同步到 `scripts/package/config/UeToolkitpack.iss` + 提交代码
- 非功能性变更：只提交代码，不更新版本号

Git 提交规范：`[类型] 描述` 或 `[类型] 描述 v版本号`
类型：feat、fix、refactor、docs、style、perf、test、chore

## 常见陷阱

1. PyQt6 跨线程 UI 操作 - 在 `QThread.run()` 中直接调用 `setText()` 会崩溃，必须用信号
2. QTimer 只能在主线程 - 工作线程中用 `time.sleep()` 代替
3. 空异常处理 - 禁止 `except: pass`，必须记录日志
4. 路径字符串拼接 - 使用 `Path` 对象而非字符串
5. 文件只读属性 - 使用 `core.utils.file_utils.safe_copytree` 处理只读文件
6. 模块间直接依赖 - 通过 `core.services` 或依赖注入解耦
7. UE 连接检测 - 使用 Remote Control API (30010)，不要用旧的 Socket RPC (9998)

## 模块结构

```
modules/<module_name>/
├── __init__.py
├── manifest.json          # 必需
├── config_template.json   # 可选
├── logic/                 # 业务逻辑
└── ui/                    # 界面代码
```

模块必须实现 `IModule` 接口：`get_metadata()`, `get_widget()`, `initialize()`, `cleanup()`

## 打包发布

### 打包步骤

**方式一：一键打包（推荐）**

```bash
scripts/package/tools/build_installer.bat
# 或：python scripts/package/tools/build_installer.py
```

**打包前自动检查**（6 项）：

1. License 配置检查（\_DEV_MODE 必须为 False）
2. 调试代码检查（可选自动注释 DEBUG 打印）
3. 依赖检查（PyQt6、requests、Pillow）
4. 代码质量检查（语法错误）
5. 版本号检查（格式和一致性）
6. 配置文件检查（必要文件存在性）

检查失败会阻止打包，确保代码处于生产就绪状态。

**自动执行流程**：清理旧构建 → 打包 EXE → 编译安装包 → 清理临时文件

**方式二：分步执行**

1. 打包 EXE：`pyinstaller scripts/package/config/ue_toolkit.spec --clean`
2. 编译安装包：使用 Inno Setup 打开 `scripts/package/config/UeToolkitpack.iss` 并编译

**输出文件**：

- `dist/UE_Toolkit.exe` - 单文件可执行程序（临时，打包后自动清理）
- `桌面/UE_Toolkit_Setup_v{版本}.exe` - 安装包（最终产物）
- `logs/build/` - 打包日志（pyinstaller/ 和 inno/ 子目录）

### 打包配置

**PyInstaller 配置**（`scripts/package/config/ue_toolkit.spec`）：

- 单文件模式，使用 UPX 压缩
- 已优化：排除未使用的 AI 库
- 自动包含所有 `config_template.json` 文件

**运行时钩子**（`scripts/package/config/runtime_hook_encoding.py`）：

- 修复 Windows 中文编码问题
- 禁用临时目录清理警告
