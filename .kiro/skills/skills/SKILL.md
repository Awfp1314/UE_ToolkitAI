---
name: UE Toolkit 开发规范
description: 帮助在 UE Toolkit 项目中编写符合规范的 Python + PyQt6 代码
keywords: python, pyqt6, ue toolkit, 模块化, 线程安全
---

# UE Toolkit 开发规范

这个 skill 帮助你在 UE Toolkit 项目中编写符合规范的 Python + PyQt6 代码。

## 架构原则

这是一个模块化的 PyQt6 桌面应用，采用三层架构：

- `core/` - 核心层，提供日志、配置、服务等基础设施
- `modules/` - 功能模块层，各模块独立，通过 `manifest.json` 自动发现
- `ui/` - 全局 UI 组件

依赖规则：

- 模块可以依赖 core（`from core.xxx import yyy`）
- 模块之间禁止直接导入，必须通过依赖注入或 `core.services`
- UI 层可以调用 Logic 层，反之禁止

## 必须遵守的规范

### 日志

```python
from core.logger import get_logger
logger = get_logger(__name__)

# 禁止使用 print()
# 异常必须记录
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
    # 信号必须在类级别定义
    result_ready = pyqtSignal(object)

    def run(self):
        # 禁止在这里直接操作 UI 控件
        result = do_work()
        self.result_ready.emit(result)  # 通过信号传递数据

# 主线程中连接信号
worker.result_ready.connect(self.update_ui)
```

### 资源清理

```python
def cleanup(self) -> CleanupResult:
    """模块必须实现此方法"""
    try:
        # 停止所有线程
        if self.worker:
            self.worker.quit()
            self.worker.wait(1000)
        # 断开信号、关闭连接等
        return CleanupResult.success()
    except Exception as e:
        return CleanupResult.failure_result(str(e))
```

### 版本管理

```python
# 只在 version.py 定义版本号
from version import VERSION  # 其他地方导入使用
```

版本号遵循语义化版本规范（Semantic Versioning）：

- `MAJOR.MINOR.PATCH` 格式（如 1.2.18）
- 主版本号（MAJOR）：重大变更、不兼容的 API 修改
- 次版本号（MINOR）：新功能、向后兼容的改进
- 修订号（PATCH）：Bug 修复、小改进、文档更新

**版本更新流程**：

版本号和代码提交由 Kiro Hook 自动管理：

- 修改 `version.py` 中的 `VERSION` 常量（功能性变更时）
- Hook 会在用户验收成功后自动：
  - **功能性代码变更**：更新版本号 + 同步到 `scripts/package/config/UeToolkitpack.iss` + 提交代码
  - **非功能性修改**（文档、配置等）：只提交代码，不更新版本号

Git 提交信息规范（使用中文）：

- 格式：`[类型] 简短描述` 或 `[类型] 简短描述 v版本号`（功能性变更）
- 类型：feat（新功能）、fix（修复）、refactor（重构）、docs（文档）、style（格式）、perf（性能）、test（测试）、chore（构建/工具）
- 示例：`[feat] 添加资产批量导入功能 v1.3.0`（功能性）
- 示例：`[docs] 更新打包流程说明`（非功能性）

## 常见陷阱

1. PyQt6 跨线程 UI 操作 - 在 `QThread.run()` 中直接调用 `setText()` 会崩溃，必须用信号
2. QTimer 只能在主线程 - 工作线程中用 `time.sleep()` 代替
3. 空异常处理 - 禁止 `except: pass`，必须记录日志
4. 路径字符串拼接 - 使用 `Path` 对象而非字符串
5. 文件只读属性 - 使用 `core.utils.file_utils.safe_copytree` 处理只读文件
6. 模块间直接依赖 - 通过 `core.services` 或依赖注入解耦

## 模块结构

```
modules/<module_name>/
├── __init__.py
├── manifest.json          # 必需：name, display_name, version, entry_point
├── config_template.json   # 可选：配置模板
├── logic/                 # 业务逻辑
└── ui/                    # 界面代码
```

模块必须实现 `IModule` 接口：`get_metadata()`, `get_widget()`, `initialize()`, `cleanup()`

## 打包发布

### 版本号管理

版本号和代码提交由 Kiro Hook 自动管理（`.kiro/hooks/auto-version-commit.kiro.hook`）：

- **功能性代码变更**（core/、modules/、ui/ 目录下的 .py 文件）：
  - 自动更新 `version.py` 中的版本号
  - 自动同步版本号到 `scripts/package/config/UeToolkitpack.iss`
  - 生成带版本号的提交信息并提交代码
- **非功能性修改**（文档、配置、构建脚本等）：
  - 不更新版本号
  - 生成不带版本号的提交信息并提交代码

Hook 会在用户验收成功后自动执行上述操作。

### 打包步骤

**方式一：一键打包（推荐）**

```bash
# 双击运行
scripts/package/tools/build_installer.bat
```

自动执行：清理旧构建 → 打包 EXE → 编译安装包

**方式二：分步执行**

1. **打包 EXE**：`pyinstaller scripts/package/config/ue_toolkit.spec --clean`
2. **编译安装包**：使用 Inno Setup 打开 `scripts/package/config/UeToolkitpack.iss` 并编译

**输出文件**（EXE 在 dist/ 目录，安装包在桌面）：

- `dist/UE_Toolkit.exe` - 单文件可执行程序
- `桌面/UE_Toolkit_Setup_v{版本}.exe` - 安装包

### 打包配置

**PyInstaller 配置**（`scripts/package/config/ue_toolkit.spec`）：

- 单文件模式，使用 UPX 压缩
- 已优化：排除未使用的 AI 库
- 自动包含所有 `config_template.json` 文件

**运行时钩子**（`scripts/package/config/runtime_hook_encoding.py`）：

- 修复 Windows 中文编码问题
- 禁用临时目录清理警告
