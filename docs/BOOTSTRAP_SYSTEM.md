# Bootstrap 系统开发者文档

## 概述

Bootstrap 系统是虚幻引擎工具箱的启动流程管理系统，负责协调应用程序的初始化、UI 准备、模块加载和主窗口显示。

## 架构设计

### 组件结构

```
core/bootstrap/
├── __init__.py              # 导出所有 Bootstrap 组件
├── app_bootstrap.py         # 顶层协调器
├── app_initializer.py       # 应用初始化器
├── ui_launcher.py           # UI 启动器
└── module_loader.py         # 模块加载器
```

### 启动流程

```
main.py
  │
  └─> AppBootstrap.run()
       │
       ├─> 1. AppInitializer.initialize()
       │    ├─ 配置日志系统
       │    ├─ 创建 QApplication
       │    └─ 单例检查
       │
       ├─> 2. UILauncher.prepare_ui()
       │    ├─ 加载主题配置
       │    ├─ 应用主题
       │    └─ 创建 Splash Screen
       │
       ├─> 3. ModuleLoader.load_modules()
       │    ├─ 设置 AppManager
       │    ├─ 异步加载模块
       │    └─ 建立模块依赖
       │
       ├─> 4. UILauncher.show_ui()
       │    ├─ 创建主窗口
       │    ├─ 启动单实例服务器
       │    └─ 显示主窗口
       │
       └─> 5. app.exec()
            └─ 进入事件循环
```

## 组件详解

### 1. AppBootstrap（顶层协调器）

**职责**：协调整个启动流程，管理各阶段的执行顺序和错误处理。

**核心方法**：
- `run() -> int`：执行完整启动流程，返回退出码
- `_cleanup()`：清理资源（Splash、SingleInstance）

**退出码**：
- `0`：成功
- `1`：初始化失败
- `2`：模块加载失败
- `3`：UI 创建失败

**使用示例**：
```python
from core.bootstrap import AppBootstrap

def main():
    bootstrap = AppBootstrap()
    return bootstrap.run()
```

### 2. AppInitializer（应用初始化器）

**职责**：封装应用程序的早期初始化逻辑。

**核心方法**：
- `initialize() -> tuple[QApplication, SingleInstanceManager, bool]`
- `_setup_logging()`：配置日志系统
- `_create_qapplication()`：创建并配置 QApplication
- `_check_single_instance()`：检查单实例

**依赖**：
- `core.logger`
- `core.single_instance.SingleInstanceManager`
- `PyQt6.QtWidgets.QApplication`

### 3. UILauncher（UI 启动器）

**职责**：管理 UI 相关的启动逻辑。

**核心方法**：
- `prepare_ui(app) -> SplashScreen`：准备 UI（主题 + Splash）
- `show_ui(app, module_provider, single_instance) -> bool`：显示主窗口
- `_load_theme_config()`：加载主题配置
- `_apply_theme()`：应用主题
- `_create_splash()`：创建 Splash Screen
- `_create_main_window()`：创建主窗口

**主题配置**：
- 配置文件：`AppData/ue_toolkit/ui_settings.json`
- 支持旧版映射：`dark` → `modern_dark`, `light` → `modern_light`
- 默认主题：`modern_dark`

### 4. ModuleLoader（模块加载器）

**职责**：作为 AppManager 的门面，协调模块加载和依赖建立。

**核心方法**：
- `load_modules(on_progress, on_complete, on_error)`：异步加载模块
- `_setup_app_manager()`：设置 AppManager
- `_start_async_loading()`：启动异步加载
- `_connect_module_dependencies()`：建立模块依赖

**模块依赖连接**：
- `asset_manager` → `ai_assistant.set_asset_manager_logic()`
- `config_tool` → `ai_assistant.set_config_tool_logic()`
- `site_recommendations` → `ai_assistant.site_recommendations_logic`

## 错误处理

### 异常捕获策略

1. **顶层异常捕获**（AppBootstrap.run）：
   - 捕获所有未处理的异常
   - 记录详细日志（如果日志系统可用）
   - 输出到 stderr（如果日志系统不可用）
   - 显示用户友好的错误对话框

2. **阶段性错误处理**：
   - 初始化失败：返回退出码 1
   - 模块加载失败：设置退出码 2，调用清理
   - UI 显示失败：设置退出码 3，调用清理

3. **资源清理保证**：
   - 注册 `app.aboutToQuit` 信号
   - 在所有退出路径都调用 `_cleanup()`
   - 使用 try-finally 确保清理执行

### 错误日志示例

```python
# 应用初始化失败
2025-11-20 01:00:00 - ERROR - 应用初始化失败

# 模块加载失败
2025-11-20 01:00:00 - ERROR - 模块加载失败: AppManager 设置失败

# UI 显示失败
2025-11-20 01:00:00 - ERROR - UI 显示失败: 无法创建主窗口
```

## 兼容性说明

### 向后兼容

Bootstrap 系统完全兼容旧版本：

1. **模块接口**：所有模块接口保持不变
2. **配置文件**：支持旧版配置文件格式
3. **日志格式**：日志输出格式未改变
4. **数据存储**：数据文件位置和格式未改变

### 迁移指南

从旧版本迁移到 Bootstrap 系统：

**无需任何操作**！Bootstrap 系统是对内部实现的重构，对外接口完全兼容。

## 性能优化

### 启动时间优化

1. **异步模块加载**：模块在后台线程加载，不阻塞 UI
2. **延迟 UI 显示**：使用 QTimer 延迟加载，避免阻塞
3. **Splash Screen**：提供视觉反馈，改善用户体验

### 资源管理优化

1. **按需加载**：模块 UI 在首次显示时才创建
2. **并行清理**：使用 ShutdownOrchestrator 并行清理模块
3. **智能释放**：通过 aboutToQuit 信号自动释放资源

## 调试指南

### 启用详细日志

Bootstrap 系统已集成日志系统，所有关键步骤都有日志输出：

```python
# 日志位置
AppData/ue_toolkit/logs/ue_toolkit.log

# 关键日志标记
[INFO] 开始应用初始化阶段
[INFO] 应用初始化阶段完成
[INFO] 开始 UI 准备阶段
[INFO] UI 准备阶段完成
[INFO] 开始异步加载模块
[INFO] 模块加载完成，开始显示 UI
```

### 常见问题排查

**问题 1：应用无法启动**
- 检查日志文件是否有错误信息
- 确认 Qt 依赖是否正确安装
- 验证配置文件是否损坏

**问题 2：模块加载失败**
- 检查 `modules/` 目录是否完整
- 验证模块 `__init__.py` 是否正确
- 查看模块依赖是否满足

**问题 3：单实例不工作**
- 检查是否有防火墙阻止本地服务器
- 验证端口是否被占用
- 查看 SingleInstanceManager 日志

## 扩展指南

### 添加新的启动阶段

在 `AppBootstrap.run()` 中添加新阶段：

```python
def run(self) -> int:
    try:
        # 现有阶段...
        
        # 添加新阶段
        self.logger.info("开始新阶段")
        new_component = NewComponent()
        new_component.execute()
        
        # 继续后续阶段...
    except Exception as e:
        self.logger.error(f"新阶段失败: {e}")
        return 4  # 新的退出码
```

### 添加自定义初始化

在 `AppInitializer.initialize()` 中添加：

```python
def initialize(self):
    # 现有初始化...
    
    # 添加自定义初始化
    self._custom_init()
    
    return self.app, self.single_instance, True

def _custom_init(self):
    """自定义初始化逻辑"""
    pass
```

## 测试建议

### 单元测试

```python
import pytest
from core.bootstrap import AppInitializer

def test_app_initializer():
    initializer = AppInitializer()
    app, single_instance, success = initializer.initialize()
    
    assert app is not None
    assert single_instance is not None
    assert success is True
```

### 集成测试

```python
def test_full_bootstrap():
    from core.bootstrap import AppBootstrap
    
    bootstrap = AppBootstrap()
    exit_code = bootstrap.run()
    
    assert exit_code == 0
```

## 相关文档

- [回滚指南](../ROLLBACK_GUIDE.md)
- [需求文档](../.kiro/specs/startup-refactor/requirements.md)
- [设计文档](../.kiro/specs/startup-refactor/design.md)
- [任务文档](../.kiro/specs/startup-refactor/tasks.md)
