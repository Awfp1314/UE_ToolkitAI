# UE Toolkit Client — AI 开发契约

> Python 3.9 + PyQt6 | 版本 1.2.9 | 5 模块 33,489 行代码

**⚠️ AI 激活此文档后，所有代码生成必须严格遵循以下规则，尤其是依赖规则和 10 个陷阱。**

---

## 项目结构与依赖规则

```
Client/
├── main.py                     # 程序入口
├── version.py                  # 版本号单一来源（VERSION = "1.2.9"）
├── core/                       # 核心层（被所有模块依赖）
│   ├── bootstrap/              # 启动引导（6 阶段）
│   ├── security/               # 授权系统（Freemium 模式）
│   ├── config/                 # 配置管理
│   ├── services/               # 核心服务（_config_service, _log_service, _path_service, _thread_service）
│   ├── utils/                  # 工具类（thread_manager, style_system, path_utils, error_handler）
│   ├── module_manager.py       # 模块发现、依赖解析、加载
│   ├── logger.py               # 日志系统（get_logger(__name__)）
│   └── constants.py
├── modules/                    # 功能模块层（模块间不直接依赖）
│   ├── ai_assistant/           # 56 文件，16,129 行 - AI 对话 + 蓝图分析
│   ├── asset_manager/          # 35 文件，11,780 行 - 资产库管理
│   ├── my_projects/            # 11 文件，3,715 行 - 工程管理
│   ├── config_tool/            # 7 文件，1,278 行 - UE 配置工具
│   └── site_recommendations/   # 7 文件，587 行 - 站点推荐
├── ui/                         # 全局 UI 组件
│   ├── ue_main_window.py       # 主窗口
│   ├── splash_screen.py
│   └── dialogs/
└── resources/                  # 资源文件
    ├── icons/
    └── styles/themes/          # modern_dark.qss, modern_light.qss
```

### 模块标准结构

```
modules/<module_name>/
├── __init__.py
├── manifest.json               # 模块元数据（name, display_name, version, entry_point）
├── config_template.json        # 配置模板（可选）
├── logic/                      # 业务逻辑层
│   └── *.py
├── ui/                         # 界面层
│   └── *.py
└── resources/                  # 模块资源（可选）
```

### 依赖规则（硬性约束）

- **模块 → 核心**: 允许，`from core.xxx import yyy`
- **模块 → 模块**: 禁止直接导入（❌ `from modules.asset_manager.ui import AssetWidget`），必须通过依赖注入或 `core.services`
- **核心 → 模块**: 禁止
- **UI → Logic**: 允许
- **Logic → UI**: 禁止

### 配置层级（优先级从高到低）

1. 环境变量
2. 模块配置（`%APPDATA%/ue_toolkit/user_data/<module>/config.json`）
3. 全局配置（`core/config/config_manager.py`）
4. 硬编码默认值

---

## 编码硬性规范

### 1. 日志规范

- 必须使用 `from core.logger import get_logger; logger = get_logger(__name__)`
- 禁止使用 `print()`，必须用 `logger.debug/info/warning/error/exception()`
- 所有异常必须记录：`except Exception as e: logger.exception(f"错误: {e}")`
- 禁止空 `except` 块或 `except: pass`

### 2. 路径操作

- 必须使用 `from pathlib import Path`，禁止字符串拼接路径
- 路径拼接：`Path.home() / "AppData" / "Roaming" / "ue_toolkit"`
- 禁止硬编码绝对路径（如 `C:/Users/wang/...`）

### 3. PyQt6 线程规范

- UI 更新必须在主线程，工作线程通过 `pyqtSignal` 回传数据
- 信号必须在类级别定义：`class Worker(QThread): result_ready = pyqtSignal(object)`
- 禁止在 `QThread.run()` 中直接操作 UI 控件（`setText`、`setEnabled` 等）
- `QTimer.singleShot` 只能在主线程调用
- `QWidget` 只能在主线程创建

### 4. 资源清理

- 模块必须实现 `cleanup() -> CleanupResult` 方法
- 必须停止所有 `QThread`：`worker.quit(); worker.wait(1000)`
- 必须移除文件监听器、关闭数据库连接、断开信号连接

### 5. 版本号管理

- 版本号只在 `Client/version.py` 定义：`VERSION = "1.2.9"`
- 其他地方必须导入：`from version import VERSION`
- 禁止在多处硬编码版本号

### 6. QSS 样式规范

- 按钮必须使用统一 `objectName`（格式 `#XxxButton`）：`BrowseButton`（标准操作）、`AddProjectButton`（添加）、`CardButton`（卡片操作）、`CardDeleteButton`（删除）、`SaveButton`（保存）、`CancelButton`（取消）
- 禁止内联样式：`setStyleSheet("background-color: blue;")`
- QSS 选择器避免过度限定：用 `#InfoTitleLabel` 而非 `#AssetCard #InfoTitleLabel`

### 7. 文件操作

- 大文件复制使用 `from core.utils.file_utils import safe_copytree`（自动处理只读属性）
- 文件编码必须指定：`file.read_text(encoding="utf-8")`
- 大文件复制使用 1MB 缓冲区：`BUFFER_SIZE = 1024 * 1024`

### 8. 模块接口

- 模块必须实现 `IModule` 接口：`get_metadata()`, `get_widget()`, `initialize()`, `cleanup()`
- `initialize()` 返回 `bool`，失败时记录日志并返回 `False`
- `cleanup()` 返回 `CleanupResult`，异常时返回 `CleanupResult.failure_result(str(e))`

### 9. 异常处理

- 捕获具体异常类型：`except FileNotFoundError` 而非 `except Exception`
- 记录异常后决定：返回默认值、继续执行、或重新抛出
- 关键操作失败时使用 `QMessageBox.critical()` 提示用户

### 10. 编码声明

- 所有 Python 文件头部添加：`# -*- coding: utf-8 -*-`
- 模块文档字符串：`"""模块说明"""`

---

## 常见陷阱（10 个）

### P01: PyQt6 跨线程 UI 操作

❌ `QThread.run()` 中 `self.label.setText("更新")` 会崩溃 ✅ 类级别定义 `update_text = pyqtSignal(str)`，`run()` 中 `emit()`，主线程 `connect()`

### P02: QTimer 只能在主线程

❌ `QThread.run()` 中 `QTimer.singleShot(1000, func)` 不工作 ✅ 主线程调用 `QTimer` 或工作线程用 `time.sleep(1)`

### P03: 空异常处理隐藏错误

❌ `except Exception: pass` 完全隐藏错误 ✅ `except Exception as e: logger.exception(f"错误: {e}"); return default_value`

### P04: 路径字符串拼接

❌ `path = base_dir + "/" + filename`（分隔符问题） ✅ `path = Path(base_dir) / filename`

### P05: 文件只读属性

❌ `shutil.copytree(src, dst)` 遇到只读文件失败 ✅ `from core.utils.file_utils import safe_copytree; safe_copytree(src, dst)`

### P06: QSS 选择器作用域

❌ `#AssetCard #InfoTitleLabel` 只匹配特定父容器 ✅ 全局样式用 `#InfoTitleLabel`，不加父容器限定

### P07: 模块间直接依赖

❌ `from modules.asset_manager.logic import AssetController` 导致耦合 ✅ 依赖注入或 `core.services`

### P08: 忘记清理资源

❌ 模块卸载不停止 `QThread` 导致内存泄漏 ✅ `cleanup()` 中 `worker.quit(); worker.wait(1000)`

### P09: 版本号不一致

❌ 多处定义版本号导致不一致 ✅ 只在 `version.py` 定义，其他地方 `from version import VERSION`

### P10: 配置路径硬编码

❌ `"C:/Users/wang/AppData/..."` 硬编码绝对路径 ✅ `Path(os.getenv("APPDATA", str(Path.home() / "AppData/Roaming"))) / "ue_toolkit"`

---

## 启动流程（6 阶段）

```
main.py → AppBootstrap.run()
  ├─> [1] AppInitializer.initialize()      # 日志、QApplication、单实例
  ├─> [2] UILauncher.prepare_ui()          # 主题、启动画面
  ├─> [3] UpdateCheckerIntegration         # 异步检查更新
  ├─> [4] ModuleLoader.load_modules()      # 发现、解析、加载、初始化模块
  ├─> [5] UILauncher.show_ui()             # 显示主窗口
  └─> [6] QApplication.exec()              # 事件循环
```

---

## 关键约束

- 所有模块通过 `ModuleManager` 自动发现（扫描 `modules/` 目录的 `manifest.json`）
- 模块加载顺序由依赖关系决定（拓扑排序）
- 授权系统：Freemium 模式（免费模块：my_projects, asset_manager, site_recommendations；付费模块：ai_assistant, config_tool）
- 资产库统一包装结构：`资产名/Content|Project|Plugins|Others/实际内容`
- 日志路径：`%APPDATA%/ue_toolkit/logs/app.log`
- 配置路径：`%APPDATA%/ue_toolkit/config.json`

---

**文档版本**: 3.0.0 | **行数**: 147 行（不含分隔线）
