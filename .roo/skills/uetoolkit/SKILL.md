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
from modules.ai_assistant.clients.ue_tool_client import UEToolClient
client = UEToolClient(base_url="http://127.0.0.1:30010")
result = client.execute_tool_rpc("ExtractBlueprint", AssetPath="/Game/BP_Test")
```

**架构**：`Python → HTTP (30010) → Remote Control API → UE Subsystem`

**优势**：UE 官方 API，稳定可靠，标准 HTTP + JSON，易调试

**配置**：UE 编辑器 → 项目设置 → Remote Control → 启用 Web Server

### Blueprint Analyzer 插件（当前使用）

**插件路径**：`Plugins/BlueprintAnalyzer/`

**Subsystem 路径**：`/Script/BlueprintAnalyzer.Default__BlueprintAnalyzerSubsystem`

**MCP 桥接**：通过 `scripts/mcp_servers/blueprint_extractor_bridge.py` 暴露工具给 AI 助手

**核心蓝图工具（4个）**：

- `ExtractBlueprint` - 提取蓝图结构（免费）
- `CreateBlueprint` - 创建新蓝图（付费）
- `AddBlueprintVariable` - 添加蓝图变量（付费）
- `AddBlueprintFunction` - 添加蓝图函数（付费）

**工具定义**：`scripts/mcp_servers/blueprint_extractor_tools.json`（共 27 个工具）

**注意**：旧版本使用 `BlueprintToolsUE54` 和内置工具注册表，已废弃。现在统一使用 MCP 协议

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
```

### 路径操作

```python
from pathlib import Path
config_path = Path.home() / "AppData" / "Roaming" / "ue_toolkit"
```

### PyQt6 线程安全

```python
class Worker(QThread):
    result_ready = pyqtSignal(object)
    def run(self):
        self.result_ready.emit(do_work())  # 禁止直接操作 UI
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

## 文档编写规范

**重要原则**：除非用户明确要求，否则不要创建或更新文档文件。

- ✅ 在聊天窗口中回答用户问题
- ✅ 提供代码示例和使用说明
- ❌ 不要自动创建 README.md、GUIDE.md 等文档
- ❌ 不要自动更新设计文档

**例外情况**：

- 用户明确说"写个文档"、"更新文档"
- 用户要求"创建使用说明"
- 项目初始化时必需的文档（如 manifest.json）

## 常见陷阱

1. PyQt6 跨线程 UI 操作 - 必须用信号，不能直接调用 UI 方法
2. QTimer 只能在主线程 - 工作线程用 `time.sleep()`
3. 空异常处理 - 禁止 `except: pass`，必须记录日志
4. 路径字符串拼接 - 使用 `Path` 对象
5. 文件只读属性 - 使用 `core.utils.file_utils.safe_copytree`
6. 模块间直接依赖 - 通过 `core.services` 解耦
7. UE 连接检测 - 使用 Remote Control API (30010)
8. 过度文档化 - 在聊天中说明，不要自动创建文档
9. 蓝图工具调用 - 通过 MCP 协议调用 Blueprint Analyzer 插件，不要直接使用旧的内置工具注册表

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

```bash
scripts/package/tools/build_installer.bat  # 一键打包
```

**自动检查**（6 项）：License、调试代码、依赖、代码质量、版本号、配置

**自动流程**：清理 → 打包 EXE → 编译安装包 → 清理临时文件

**输出**：`桌面/UE_Toolkit_Setup_v{版本}.exe`，日志在 `logs/build/`

### 打包配置

**PyInstaller**（`scripts/package/config/ue_toolkit.spec`）：单文件模式，UPX 压缩，自动包含 `config_template.json`
