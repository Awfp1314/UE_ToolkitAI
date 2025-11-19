# 设计文档 - 启动流程重构

## 概述

本文档描述了应用程序启动流程重构的详细设计。重构将当前分散在 `main.py` 和 `UEMainWindow` 中的启动逻辑重组为清晰的四阶段启动管线，每个阶段由专门的组件负责。设计遵循门面模式和单一职责原则，最大程度复用现有代码，避免重复实现。

### 设计目标

1. **职责分离**: 将启动逻辑拆分为独立的、可测试的组件
2. **复用现有代码**: 通过门面模式封装现有的 AppManager、ModuleManager 等组件
3. **保持向后兼容**: 不修改现有模块接口和配置格式
4. **提升可维护性**: 清晰的代码组织和明确的依赖关系
5. **支持异步执行**: 保持 UI 响应性，提供进度反馈

### 启动流程概览

```
main.py
  └─> AppBootstrap.run()
       ├─> 1. App Initializer (应用初始化)
       │    ├─ 配置日志系统
       │    ├─ 创建 QApplication
       │    ├─ 单例检查
       │    └─ 返回 SingleInstanceManager
       │
       ├─> 2. UI Launcher - 准备阶段 (UI 准备)
       │    ├─ 创建 Splash Screen
       │    ├─ 注册日志处理器
       │    └─ 加载并应用主题
       │
       ├─> 3. Module Loader (模块加载)
       │    ├─ 调用 AppManager.setup()
       │    ├─ 调用 AppManager.start_async()
       │    ├─ 报告进度到 Splash
       │    └─ 建立模块依赖连接
       │
       └─> 4. UI Launcher - 显示阶段 (UI 显示)
            ├─ 创建主窗口
            ├─ 启动单实例服务器
            ├─ 关闭 Splash
            └─ 显示主窗口
```

## 架构设计

### 组件关系图

```
┌─────────────────────────────────────────────────────────┐
│                      main.py                            │
│                  (入口点，最小化)                        │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                  AppBootstrap                           │
│            (顶层协调器，管理启动流程)                    │
└─┬───────────────┬───────────────┬───────────────────┬───┘
  │               │               │                   │
  ▼               ▼               ▼                   ▼
```

┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ App │ │ UI │ │ Module │ │ UI │
│Initializer│ │ Launcher │ │ Loader │ │ Launcher │
│ │ │ (准备) │ │ │ │ (显示) │
└────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘
│ │ │ │
│ 封装 │ 封装 │ 门面 │ 封装
▼ ▼ ▼ ▼
┌─────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ Logger │ │ Splash │ │ App │ │ Main │
│ Single │ │ Screen │ │ Manager │ │ Window │
│ Instance│ │ Style │ │ Module │ │ Single │
│ Manager │ │ System │ │ Manager │ │ Instance │
└─────────┘ └──────────┘ └──────────┘ └──────────┘

```

### 目录结构

```

core/
└── bootstrap/
├── **init**.py # 导出 AppBootstrap
├── app_bootstrap.py # 顶层协调器
├── app_initializer.py # 应用初始化器
├── module_loader.py # 模块加载器
└── ui_launcher.py # UI 启动器

````

## 组件详细设计

### 1. AppBootstrap (顶层协调器)

**职责**: 协调整个启动流程，管理四个启动阶段的执行顺序和错误处理。

**接口设计**:

```python
class AppBootstrap:
    """应用程序启动协调器"""

    def __init__(self):
        """初始化启动协调器"""
        self.app_initializer = AppInitializer()
        self.ui_launcher = UILauncher()
        self.module_loader = ModuleLoader()

        # 状态成员
        self.app: Optional[QApplication] = None
        self.single_instance: Optional[SingleInstanceManager] = None
        self.splash: Optional[SplashScreen] = None
        self.exit_code: int = 0

    def run(self) -> int:
        """执行完整的启动流程

        Returns:
            int: 退出码 (0=成功, 1=初始化失败, 2=模块加载失败, 3=UI创建失败)
        """
        try:
            # 1. 应用初始化
            self.app, self.single_instance, success = self.app_initializer.initialize()
            if not success:
                return 1

            # 2. UI 准备
            self.splash = self.ui_launcher.prepare_ui(self.app)

            # 3. 注册模块加载回调（异步）
            def on_complete(module_provider):
                try:
                    success = self.ui_launcher.show_ui(
                        self.app, module_provider, self.single_instance
                    )
                    if not success:
                        self.exit_code = 3
                        self.app.quit()
                except Exception as e:
                    logger.error(f"UI 显示失败: {e}", exc_info=True)
                    self.exit_code = 3
                    self._cleanup()
                    self.app.quit()

            def on_error(error_msg):
                logger.error(f"模块加载失败: {error_msg}")
                self.exit_code = 2
                self._cleanup()
                self.app.quit()

            def on_progress(percent, message):
                self.splash.update_progress(percent, message)
                self.app.processEvents()

            # 4. 启动异步模块加载
            self.module_loader.load_modules(on_progress, on_complete, on_error)

            # 5. 注册退出清理钩子
            self.app.aboutToQuit.connect(self._cleanup)

            # 6. 立即进入事件循环（让异步回调能够执行）
            self.app.exec()

            return self.exit_code

        except Exception as e:
            logger.error(f"启动失败: {e}", exc_info=True)
            self._cleanup()
            return 1

    def _cleanup(self):
        """清理资源

        调用时机：
        1. 正常退出：通过 aboutToQuit 信号自动调用
        2. 异常退出：在 except 块中显式调用
        3. 模块加载失败：在 on_error 回调中调用
        4. UI 显示失败：在 on_complete 回调中调用
        """
        if self.splash:
            self.splash.close()
        if self.single_instance:
            self.single_instance.cleanup()
```

**关键设计决策**:
- 使用 `aboutToQuit` 信号确保在任何退出路径都会清理资源
- 包括用户关闭窗口、系统关闭、程序调用 quit() 等所有情况
- 不需要在 `_cleanup()` 中调用 `app.quit()`，因为清理是在退出过程中触发的

**状态机设计**:

```
[开始]
  ↓
[应用初始化] → [失败] → 返回退出码 1
  ↓ 成功
[UI 准备] → [失败] → 返回退出码 3
  ↓ 成功
[注册模块加载回调]
  ↓
[进入事件循环] ← 关键：立即进入，让异步回调能够执行
  ↓
  ├─> [模块加载中...] (异步)
  │    ├─> on_progress → 更新 Splash
  │    ├─> on_complete → [UI 显示] → [成功] → 继续运行
  │    └─> on_error → [失败] → 返回退出码 2 → quit()
  │
  └─> [用户交互/事件处理]
       ↓
[用户退出]
  ↓
[结束] → 返回退出码 (0 或之前设置的错误码)
```

**关键设计决策**:
- 模块加载回调注册后**立即进入事件循环**，而不是等待加载完成
- 这确保 QThread 信号能够触发 `on_progress`/`on_complete` 回调
- UI 显示在 `on_complete` 回调中执行，在事件循环内部
- 错误通过设置 `self.exit_code` 并调用 `app.quit()` 来传播

**错误处理策略**:

- 每个阶段失败时记录详细错误日志
- 显示用户友好的错误对话框
- 执行必要的清理操作
- 返回对应的退出码

### 2. AppInitializer (应用初始化器)

**职责**: 封装应用程序的早期初始化逻辑，包括日志配置、QApplication 创建和单例检查。

**接口设计**:

```python
class AppInitializer:
    """应用程序初始化器"""

    def initialize(self) -> tuple[QApplication, SingleInstanceManager, bool]:
        """初始化应用程序

        Returns:
            tuple: (QApplication实例, SingleInstanceManager实例, 是否成功)
        """
        pass

    def _setup_logging(self) -> None:
        """配置日志系统"""
        pass

    def _create_qapplication(self) -> QApplication:
        """创建并配置 QApplication"""
        pass

    def _check_single_instance(self,
                               single_instance: SingleInstanceManager) -> bool:
        """检查单实例

        Returns:
            bool: True=可以继续启动, False=已有实例运行
        """
        pass
```

**实现细节**:

1. **日志配置**:

   - 调用现有的 `init_logging_system()`
   - 配置控制台编码（Windows 平台）

2. **QApplication 创建**:

   - 创建 QApplication 实例
   - 设置应用程序名称: "ue_toolkit"
   - 设置应用程序版本: "1.0.1"
   - 设置应用程序图标: `resources/tubiao.ico`
   - 设置 Windows AppUserModelID（Windows 平台）

3. **单例检查**:
   - 创建 SingleInstanceManager 实例
   - 调用 `is_running()` 检查是否已有实例
   - 如果已有实例，发送激活消息并返回 False
   - 否则返回 True 和 SingleInstanceManager 实例

**依赖关系**:

- `core.logger.init_logging_system()`
- `core.logger.setup_console_encoding()`
- `core.single_instance.SingleInstanceManager`
- `PyQt6.QtWidgets.QApplication`
- `PyQt6.QtGui.QIcon`

### 3. UILauncher (UI 启动器)

**职责**: 管理 UI 相关的启动逻辑，分为准备阶段和显示阶段。

**接口设计**:

```python
class UILauncher:
    """UI 启动器"""

    def __init__(self):
        self.splash: Optional[SplashScreen] = None
        self.main_window: Optional[UEMainWindow] = None
        self.current_theme: str = "modern_dark"

    def prepare_ui(self, app: QApplication) -> SplashScreen:
        """准备 UI（创建 Splash Screen 并应用主题）

        Args:
            app: QApplication 实例

        Returns:
            SplashScreen: Splash Screen 实例
        """
        pass

    def show_ui(self,
                app: QApplication,
                module_provider: ModuleProviderAdapter,
                single_instance: SingleInstanceManager) -> bool:
        """显示 UI（创建主窗口并显示）

        Args:
            app: QApplication 实例
            module_provider: 模块提供者
            single_instance: 单实例管理器

        Returns:
            bool: 是否成功
        """
        pass

    def _load_theme_config(self) -> str:
        """加载主题配置"""
        pass

    def _apply_theme(self, app: QApplication, theme: str) -> None:
        """应用主题"""
        pass

    def _create_splash(self, theme: str) -> SplashScreen:
        """创建 Splash Screen"""
        pass

    def _create_main_window(self,
                           module_provider: ModuleProviderAdapter) -> UEMainWindow:
        """创建主窗口"""
        pass
```

**准备阶段实现细节**:

1. **加载主题配置**:

   - 从 `AppData/ue_toolkit/ui_settings.json` 读取主题设置
   - 支持旧版本配置映射: `dark` → `modern_dark`, `light` → `modern_light`
   - 失败时使用默认主题 `modern_dark`

2. **应用主题**:

   - 调用 `style_system.apply_theme(app, theme)`
   - 在创建任何窗口之前应用

3. **创建 Splash Screen**:
   - 根据主题选择 Splash 主题: `dark` 或 `light`
   - 创建 SplashScreen 实例
   - 注册日志处理器: `splash.register_log_handler()`
   - 显示 Splash: `splash.show()`
   - 刷新 UI: `app.processEvents()`

**显示阶段实现细节**:

1. **创建主窗口**:

   - 创建 UEMainWindow 实例并传入 module_provider
   - 不立即显示

2. **启动单实例服务器**:

   - 调用 `single_instance.start_server(main_window)`
   - 传入主窗口引用以支持激活功能

3. **加载初始模块**:

   - 调用 `main_window.load_initial_module(on_complete=callback)`
   - 在回调中关闭 Splash 并显示主窗口

4. **显示主窗口**:
   - 关闭 Splash: `splash.finish()`
   - 显示主窗口: `main_window.show()`
   - 激活窗口: `main_window.raise_()`, `main_window.activateWindow()`

**依赖关系**:

- `ui.splash_screen.SplashScreen`
- `ui.ue_main_window.UEMainWindow`
- `core.utils.style_system.style_system`
- `core.single_instance.SingleInstanceManager`
- `PyQt6.QtCore.QStandardPaths`

### 4. ModuleLoader (模块加载器)

**职责**: 作为 AppManager 和 ModuleManager 的门面，协调模块加载流程并建立模块间依赖。

**接口设计**:

```python
class ModuleLoader:
    """模块加载器（AppManager 的门面）"""

    def __init__(self):
        self.app_manager: Optional[AppManager] = None
        self.module_provider: Optional[ModuleProviderAdapter] = None

    def load_modules(self,
                    on_progress: Callable[[int, str], None],
                    on_complete: Callable[[ModuleProviderAdapter], None],
                    on_error: Callable[[str], None]) -> None:
        """异步加载模块

        Args:
            on_progress: 进度回调 (percent: int, message: str) -> None
            on_complete: 完成回调，传入 ModuleProviderAdapter
            on_error: 错误回调，传入错误消息
        """
        pass

    def _setup_app_manager(self) -> bool:
        """设置 AppManager"""
        pass

    def _start_async_loading(self,
                            on_progress: Callable,
                            on_complete: Callable,
                            on_error: Callable) -> None:
        """启动异步加载"""
        pass

    def _connect_module_dependencies(self) -> None:
        """建立模块间的依赖连接"""
        pass
```

**实现细节**:

1. **设置 AppManager**:

   - 创建 AppManager 实例
   - 调用 `app_manager.setup()`
   - 返回是否成功

2. **异步加载模块**:

   - 定义内部回调函数处理 `on_complete`、`on_error`、`on_progress`
   - 调用 `app_manager.start_async(on_complete=..., on_error=..., on_progress=...)`
   - 在 `on_progress` 回调中调用外部传入的 `on_progress` 回调（由 AppBootstrap 负责更新 Splash）

3. **建立模块依赖连接**:

   - 获取 ai_assistant、asset_manager、config_tool、site_recommendations 模块
   - 将 asset_manager 逻辑层注入 ai_assistant: `ai_assistant.set_asset_manager_logic(asset_logic)`
   - 将 config_tool 逻辑层注入 ai_assistant: `ai_assistant.set_config_tool_logic(config_logic)`
   - 将 site_recommendations 逻辑层注入 ai_assistant: `ai_assistant.site_recommendations_logic = site_logic`
   - 如果依赖模块未加载，记录警告并继续

4. **创建 ModuleProviderAdapter**:
   - 在模块加载完成后创建 `ModuleProviderAdapter(module_manager)`
   - 通过 `on_complete` 回调返回

**依赖关系**:

- `core.app_manager.AppManager`
- `core.module_interface.ModuleProviderAdapter`
- 不依赖 UI 层（通过回调解耦）

## 数据流设计

### 启动流程数据流

```
main.py
  │
  └─> AppBootstrap.run()
       │
       ├─> 1. app_initializer.initialize()
       │    └─> 返回: (QApplication, SingleInstanceManager, success)
       │
       ├─> 2. ui_launcher.prepare_ui(app)
       │    └─> 返回: SplashScreen
       │
       ├─> 3. 注册模块加载回调
       │    │
       │    ├─> on_progress(percent, message)
       │    │    ├─> splash.update_progress(percent, message)
       │    │    └─> app.processEvents()
       │    │
       │    ├─> on_complete(module_provider)
       │    │    └─> ui_launcher.show_ui(app, module_provider, single_instance)
       │    │         ├─> 创建 UEMainWindow
       │    │         ├─> single_instance.start_server(main_window)
       │    │         ├─> main_window.load_initial_module(on_complete)
       │    │         │    └─> on_complete()
       │    │         │         ├─> splash.finish()
       │    │         │         └─> main_window.show()
       │    │         └─> 成功则继续运行，失败则 quit()
       │    │
       │    └─> on_error(error_message)
       │         ├─> 记录错误
       │         ├─> 设置 exit_code = 2
       │         ├─> _cleanup()
       │         └─> app.quit()
       │
       ├─> 4. module_loader.load_modules(on_progress, on_complete, on_error)
       │    │
       │    ├─> AppManager.setup()
       │    │
       │    └─> AppManager.start_async(on_complete, on_error, on_progress)
       │         │
       │         ├─> on_progress(percent, message)
       │         │    └─> 调用外部 on_progress
       │         │
       │         ├─> on_complete(success)
       │         │    ├─> _connect_module_dependencies()
       │         │    └─> 创建 ModuleProviderAdapter
       │         │         └─> 调用外部 on_complete(module_provider)
       │         │
       │         └─> on_error(error_message)
       │              └─> 调用外部 on_error(error_message)
       │
       └─> 5. app.exec() ← 立即进入事件循环，让异步回调能够执行
            │
            └─> 事件循环运行中...
                 ├─> 处理 QThread 信号
                 ├─> 触发 on_progress/on_complete/on_error 回调
                 └─> 用户交互
```

### 错误传播路径

```
任何阶段异常
  │
  ├─> 捕获异常
  │
  ├─> 记录详细日志
  │
  ├─> 显示错误对话框
  │
  ├─> 执行清理操作
  │    ├─> 关闭 Splash (如果存在)
  │    ├─> 清理 SingleInstance (如果存在)
  │    └─> 退出 QApplication
  │
  └─> 返回对应退出码
       ├─> 1: 初始化失败
       ├─> 2: 模块加载失败
       └─> 3: UI 创建失败
```

## 接口契约

### AppBootstrap.run() 契约

**前置条件**:

- 无

**后置条件**:

- 返回退出码 (0-3)
- 如果成功，QApplication 事件循环正在运行
- 如果失败，所有资源已清理

**异常处理**:

- 捕获所有异常
- 记录日志
- 显示错误对话框
- 返回非零退出码

### AppInitializer.initialize() 契约

**前置条件**:

- 无

**后置条件**:

- 日志系统已配置
- QApplication 已创建并配置
- SingleInstanceManager 已创建
- 如果返回 success=False，表示已有实例运行

**返回值**:

- `(QApplication, SingleInstanceManager, bool)`: 应用实例、单例管理器、是否可以继续

**异常处理**:

- 抛出异常由 AppBootstrap 处理

### UILauncher.prepare_ui() 契约

**前置条件**:

- QApplication 已创建

**后置条件**:

- Splash Screen 已创建并显示
- 日志处理器已注册
- 主题已应用

**返回值**:

- `SplashScreen`: Splash Screen 实例

**异常处理**:

- 抛出异常由 AppBootstrap 处理

### ModuleLoader.load_modules() 契约

**前置条件**:

- AppManager 尚未初始化
- QApplication 事件循环即将启动

**后置条件**:

- 模块异步加载中
- 进度通过 `on_progress` 回调通知
- 完成或失败通过回调通知

**参数**:

- `on_progress`: 进度回调 `(percent: int, message: str) -> None`
- `on_complete`: 完成回调 `(ModuleProviderAdapter) -> None`
- `on_error`: 错误回调 `(str) -> None`

**回调时机**:

- `on_progress`: 每个模块加载时（在 QThread 中）
- `on_complete`: 所有模块加载完成且依赖连接建立后（在 QThread 中）
- `on_error`: 任何阶段失败时（在 QThread 中）

**异常处理**:

- 内部捕获异常并通过 `on_error` 回调通知

**关键设计**:

- 不依赖 UI 层，通过纯回调接口解耦
- 回调在 QThread 中触发，需要事件循环运行才能传播到主线程

### UILauncher.show_ui() 契约

**前置条件**:

- 模块已加载完成
- ModuleProviderAdapter 已创建
- SingleInstanceManager 已创建

**后置条件**:

- 主窗口已创建并显示
- 单实例服务器已启动
- Splash Screen 已关闭

**返回值**:

- `bool`: 是否成功

**异常处理**:

- 抛出异常由 AppBootstrap 处理

## 错误处理设计

### 错误分类

1. **初始化错误** (退出码 1):

   - 日志系统配置失败
   - QApplication 创建失败
   - 图标文件不存在（警告，不中断）

2. **模块加载错误** (退出码 2):

   - AppManager.setup() 失败
   - AppManager.start_async() 失败
   - 模块依赖连接失败（警告，不中断）

3. **UI 创建错误** (退出码 3):
   - Splash Screen 创建失败
   - 主题加载失败（回退到默认主题）
   - 主窗口创建失败
   - 单实例服务器启动失败（警告，不中断）

### 错误处理流程

```python
try:
    # 执行启动阶段
    result = stage.execute()
except Exception as e:
    # 1. 记录详细错误
    logger.error(f"阶段失败: {e}", exc_info=True)

    # 2. 显示用户友好的错误对话框
    QMessageBox.critical(
        None,
        "启动失败",
        f"启动过程中发生错误:\n{str(e)}"
    )

    # 3. 执行清理
    self._cleanup()

    # 4. 返回退出码
    return exit_code
```

### 清理策略

```python
def _cleanup(self):
    """清理资源"""
    # 1. 关闭 Splash Screen
    if self.splash:
        self.splash.close()

    # 2. 清理 SingleInstance
    if self.single_instance:
        self.single_instance.cleanup()
```

**注意**: 不需要调用 `app.quit()`，因为清理通常在错误处理中调用，而错误处理会在调用 `_cleanup()` 后显式调用 `app.quit()`。

## 测试策略

### 单元测试

1. **AppInitializer 测试**:

   - 测试日志系统配置
   - 测试 QApplication 创建
   - 测试单例检查逻辑
   - 模拟已有实例运行的情况

2. **UILauncher 测试**:

   - 测试主题配置加载
   - 测试主题回退逻辑
   - 测试 Splash Screen 创建
   - 模拟主窗口创建

3. **ModuleLoader 测试**:

   - 测试 AppManager.setup() 调用
   - 测试异步回调机制
   - 测试模块依赖连接
   - 模拟模块加载失败

4. **AppBootstrap 测试**:
   - 测试完整启动流程
   - 测试各阶段失败处理
   - 测试退出码返回
   - 测试清理逻辑

### 集成测试

1. **完整启动流程测试**:

   - 测试从 main.py 到主窗口显示的完整流程
   - 验证所有模块正确加载
   - 验证模块依赖正确建立

2. **错误恢复测试**:

   - 模拟各阶段失败
   - 验证错误处理和清理
   - 验证退出码正确性

3. **单实例测试**:
   - 测试第二次启动时的激活行为
   - 验证服务器正确启动和清理

### 测试工具

- **Mock 对象**: 模拟 QApplication、Splash Screen、AppManager 等
- **Fixture**: 提供测试环境和清理
- **参数化测试**: 测试不同的错误场景

## 迁移策略

### 迁移步骤

1. **阶段 1: 创建新组件**

   - 创建 `core/bootstrap/` 目录
   - 实现 AppInitializer
   - 实现 UILauncher
   - 实现 ModuleLoader
   - 实现 AppBootstrap

2. **阶段 2: 修改 main.py**

   - 简化 main.py，只保留 AppBootstrap 调用
   - 保留原有代码作为注释（便于回滚）

3. **阶段 3: 测试验证**

   - 运行单元测试
   - 运行集成测试
   - 手动测试启动流程
   - 验证所有功能正常

4. **阶段 4: 清理**
   - 删除 main.py 中的旧代码注释
   - 更新文档

### 回滚计划

如果迁移失败，可以通过以下步骤回滚：

1. 恢复 main.py 的原始版本
2. 删除 `core/bootstrap/` 目录
3. 重启应用验证

### 风险点和应对措施

1. **风险**: 模块依赖连接失败

   - **应对**: 详细日志记录，逐个模块验证

2. **风险**: Splash Screen 显示异常

   - **应对**: 保留原有的 Splash 创建逻辑作为参考

3. **风险**: 单实例功能失效

   - **应对**: 独立测试单实例功能

4. **风险**: 主题应用失败
   - **应对**: 确保回退到默认主题

## 性能考虑

### 启动时间优化

1. **异步加载**: 模块加载使用异步方式，保持 UI 响应
2. **延迟加载**: 主窗口创建后才加载初始模块
3. **进度反馈**: 通过 Splash Screen 提供实时反馈

### 内存优化

1. **按需创建**: 组件只在需要时创建
2. **及时清理**: 不再需要的资源及时释放
3. **避免重复**: 复用现有的 AppManager 和 ModuleManager

### 性能指标

- **目标启动时间**: < 1 秒（从启动到主窗口显示）
- **内存占用**: 与原实现相当
- **CPU 使用**: 启动期间 < 50%

## 向后兼容性

### 保持兼容的方面

1. **模块接口**: 不修改任何模块的接口
2. **配置格式**: 保持所有配置文件格式不变
3. **日志格式**: 保持日志输出格式和位置
4. **命令行参数**: 支持所有现有的命令行参数
5. **环境变量**: 支持所有现有的环境变量

### 不兼容的方面

- 无（完全向后兼容）

## 文档更新

### 需要更新的文档

1. **README.md**: 更新启动流程说明
2. **开发者文档**: 添加 Bootstrap 系统说明
3. **架构文档**: 更新架构图
4. **故障排除指南**: 添加新的错误码说明

### 代码注释

- 每个组件添加详细的类和方法注释
- 关键逻辑添加行内注释
- 复杂的异步流程添加流程图注释

## 总结

本设计通过引入清晰的四阶段启动流程和专门的组件，将原本分散在 `main.py` 和 `UEMainWindow` 中的启动逻辑重组为可维护、可测试的结构。设计遵循以下原则：

1. **单一职责**: 每个组件只负责一个明确的启动阶段
2. **门面模式**: ModuleLoader 作为 AppManager 的门面，避免重复实现
3. **依赖注入**: 通过参数传递依赖，便于测试
4. **异步执行**: 保持 UI 响应性，提供良好的用户体验
5. **错误处理**: 完善的错误处理和清理机制
6. **向后兼容**: 不破坏现有功能和接口

实现后，启动流程将更加清晰，代码更易维护，测试更加容易，为后续功能扩展打下良好基础。
````
