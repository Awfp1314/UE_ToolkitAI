# 需求文档 - 启动流程重构

## 简介

本文档定义了应用程序启动流程重构的需求。当前启动逻辑分散在 `main.py` 和 `UEMainWindow` 中，导致职责不清、难以维护和测试。重构目标是将启动流程拆分为清晰的启动管线，包括应用初始化、UI 准备、模块加载和 UI 显示四个明确阶段，每个阶段由专门的组件负责。其中 UI 准备和 UI 显示阶段共同构成 UI Launcher 组件的职责。

## 术语表

- **Bootstrap System**: 启动系统，负责协调整个应用程序启动流程的顶层组件
- **App Initializer**: 应用初始化器，负责日志配置、配置文件加载和单例检查的组件，封装现有的 `init_logging_system` 和 `SingleInstanceManager`
- **Module Loader**: 模块加载器，作为现有 `AppManager` 和 `ModuleManager` 的门面，不重新实现模块发现和初始化逻辑
- **UI Launcher**: UI 启动器，负责创建主窗口和应用主题的组件，封装 `UEMainWindow` 创建和主题应用逻辑
- **Startup Stage**: 启动阶段，指应用初始化、模块加载或 UI 启动中的一个独立步骤
- **Module**: 模块，指应用程序的功能插件，位于 `modules/` 目录下
- **Exit Code**: 退出码，表示应用程序终止状态的整数值（0=成功，1=初始化失败，2=模块加载失败，3=UI 创建失败）
- **QApplication**: PyQt6 应用程序实例，必须在任何 Qt 组件创建之前初始化
- **Splash Screen**: 启动加载界面，显示启动进度和日志信息
- **AppManager**: 现有的应用程序生命周期管理器，负责服务和模块的初始化
- **ModuleManager**: 现有的模块管理器，负责模块的扫描、加载和初始化
- **SingleInstanceManager**: 现有的单实例管理器，确保应用程序只运行一个实例

## 组件映射表

本重构将创建新的启动组件，这些组件封装和协调现有组件，而不是替换它们：

| 新组件           | 现有组件                                         | 关系                                                |
| ---------------- | ------------------------------------------------ | --------------------------------------------------- |
| Bootstrap System | 无                                               | 新增顶层协调器，管理启动阶段流程                    |
| App Initializer  | `init_logging_system()`, `SingleInstanceManager` | 封装日志和单例检查，返回 SingleInstanceManager 实例 |
| Module Loader    | `AppManager`, `ModuleManager`                    | 门面模式，复用现有逻辑，通过回调通知完成状态        |
| UI Launcher      | `UEMainWindow`, `style_system`, `SplashScreen`   | 封装 UI 创建和主题应用，负责启动单实例服务器        |

## 启动阶段流程

启动流程分为四个明确的阶段：

1. **应用初始化阶段**（App Initializer）

   - 配置日志系统
   - 创建 QApplication
   - 执行单例检查
   - 返回 SingleInstanceManager 实例

2. **UI 准备阶段**（UI Launcher - 第一部分）

   - 创建并显示 Splash Screen
   - 注册日志处理器
   - 加载并应用主题

3. **模块加载阶段**（Module Loader）

   - 异步加载和初始化模块
   - 通过回调报告进度
   - 建立模块间依赖连接
   - 通过 on_complete 回调通知完成

4. **UI 显示阶段**（UI Launcher - 第二部分）
   - 创建主窗口
   - 启动 SingleInstanceManager 服务器
   - 关闭 Splash Screen
   - 显示主窗口

---

## 需求

### 需求 1：启动系统架构

**用户故事**: 作为开发者，我希望有一个清晰的启动系统架构，以便理解和维护应用程序的启动流程。

#### 验收标准

1. THE Bootstrap System SHALL 提供一个统一的入口点来执行完整的启动流程
2. THE Bootstrap System SHALL 按顺序执行以下阶段：应用初始化、UI 准备（创建 Splash Screen）、模块加载、UI 显示
3. THE Bootstrap System SHALL 在应用初始化阶段创建 QApplication 和 SingleInstanceManager
4. THE Bootstrap System SHALL 在 UI 准备阶段创建 Splash Screen 并应用主题
5. THE Bootstrap System SHALL 在模块加载阶段异步加载模块并报告进度
6. THE Bootstrap System SHALL 在 UI 显示阶段创建主窗口、启动单实例服务器并显示主窗口
7. WHEN 任何启动阶段失败时，THE Bootstrap System SHALL 返回非零退出码
8. WHEN 所有启动阶段成功完成时，THE Bootstrap System SHALL 返回零退出码

---

### 需求 2：应用初始化

**用户故事**: 作为开发者，我希望应用初始化逻辑独立且可测试，以便在启动早期发现配置问题。

#### 验收标准

1. THE App Initializer SHALL 配置应用程序的日志系统
2. THE App Initializer SHALL 创建 QApplication 实例并配置应用程序元数据
3. THE App Initializer SHALL 创建 SingleInstanceManager 实例
4. THE App Initializer SHALL 执行单例检查以防止多个实例同时运行
5. IF 单例检查检测到另一个实例正在运行，THEN THE App Initializer SHALL 发送激活消息并终止启动流程
6. THE App Initializer SHALL 返回 SingleInstanceManager 实例供后续阶段使用

---

### 需求 3：模块加载

**用户故事**: 作为开发者，我希望模块加载逻辑与其他启动逻辑分离，以便独立测试模块系统。

#### 验收标准

1. THE Module Loader SHALL 接收 on_progress 回调作为参数以报告进度
2. THE Module Loader SHALL 调用 AppManager.setup() 初始化应用程序核心服务
3. THE Module Loader SHALL 调用 AppManager.start_async() 异步加载和初始化模块
4. THE Module Loader SHALL 通过 on_progress 回调报告模块加载进度
5. THE Module Loader SHALL 在 on_complete 回调中建立模块间的依赖连接
6. THE Module Loader SHALL 在 on_complete 回调中返回 ModuleProviderAdapter 实例
7. THE Module Loader SHALL 在 on_error 回调中返回错误信息

---

### 需求 4：UI 启动

**用户故事**: 作为开发者，我希望 UI 启动逻辑独立于应用初始化和模块加载，以便在不同环境中灵活启动 UI。

#### 验收标准

1. THE UI Launcher SHALL 创建并显示 Splash Screen 启动加载界面
2. THE UI Launcher SHALL 注册 Splash Screen 日志处理器以捕获启动日志
3. THE UI Launcher SHALL 从 ui_settings.json 读取用户保存的主题配置
4. IF 主题配置读取失败，THEN THE UI Launcher SHALL 使用默认主题 modern_dark
5. THE UI Launcher SHALL 应用主题到 QApplication 实例
6. THE UI Launcher SHALL 在模块加载完成回调中创建 UEMainWindow 实例
7. THE UI Launcher SHALL 在主窗口创建后启动 SingleInstanceManager 本地服务器
8. THE UI Launcher SHALL 在模块加载完成后关闭 Splash Screen 并显示主窗口

---

### 需求 5：异步执行和进度报告

**用户故事**: 作为用户，我希望在启动过程中看到实时进度更新，以便了解应用程序正在执行的操作。

#### 验收标准

1. THE Bootstrap System SHALL 支持异步执行模块加载阶段以保持 UI 响应
2. THE Bootstrap System SHALL 在模块加载期间保持 QApplication 事件循环运行
3. THE Module Loader SHALL 通过 AppManager.start_async() 的 on_progress 回调推送进度消息和百分比
4. THE Module Loader SHALL 通过 AppManager.start_async() 的 on_complete 回调通知加载完成
5. THE Module Loader SHALL 通过 AppManager.start_async() 的 on_error 回调通知加载失败
6. THE Bootstrap System SHALL 在接收到 on_complete 回调后进入 UI 显示阶段
7. THE Bootstrap System SHALL 在接收到 on_error 回调后执行错误处理并返回退出码 2

---

### 需求 6：错误处理和恢复

**用户故事**: 作为用户，我希望在启动失败时看到清晰的错误信息，以便了解问题所在。

#### 验收标准

1. WHEN 启动阶段发生异常时，THE Bootstrap System SHALL 捕获异常并记录详细错误信息
2. WHEN 启动失败时，THE Bootstrap System SHALL 向用户显示友好的错误消息
3. THE Bootstrap System SHALL 在启动失败时执行必要的清理操作
4. THE Bootstrap System SHALL 返回退出码 0 表示成功，1 表示初始化失败，2 表示模块加载失败，3 表示 UI 创建失败
5. IF 日志系统尚未初始化，THEN THE Bootstrap System SHALL 将错误输出到标准错误流

---

### 需求 7：模块装配和依赖连接

**用户故事**: 作为开发者，我希望模块间的依赖关系在启动时自动建立，以便模块能够正确互操作。

#### 验收标准

1. THE Module Loader SHALL 在模块初始化完成后建立模块间的依赖连接
2. THE Module Loader SHALL 将 asset_manager 逻辑层注入到 ai_assistant 模块
3. THE Module Loader SHALL 将 config_tool 逻辑层注入到 ai_assistant 模块
4. THE Module Loader SHALL 将 site_recommendations 逻辑层注入到 ai_assistant 模块
5. IF 依赖模块未加载，THEN THE Module Loader SHALL 记录警告并继续启动流程

---

### 需求 8：代码组织和可维护性

**用户故事**: 作为开发者，我希望启动相关代码组织清晰，以便快速定位和修改启动逻辑。

#### 验收标准

1. THE Bootstrap System SHALL 将所有启动相关代码组织在 `core/bootstrap/` 目录下
2. THE App Initializer SHALL 实现在 `core/bootstrap/app_initializer.py` 文件中
3. THE Module Loader SHALL 实现在 `core/bootstrap/module_loader.py` 文件中
4. THE UI Launcher SHALL 实现在 `core/bootstrap/ui_launcher.py` 文件中
5. THE `main.py` 文件 SHALL 仅包含 Bootstrap System 的调用和退出码处理

---

### 需求 9：向后兼容性

**用户故事**: 作为用户，我希望重构后的应用程序保持相同的功能和行为，以便无缝升级。

#### 验收标准

1. THE Bootstrap System SHALL 保持与现有模块接口的兼容性
2. THE Bootstrap System SHALL 保持与现有配置文件格式的兼容性
3. THE Bootstrap System SHALL 保持相同的启动行为和用户体验
4. THE Bootstrap System SHALL 保持相同的日志输出格式和位置
5. THE Bootstrap System SHALL 支持所有现有的命令行参数和环境变量

---

### 需求 10：测试能力

**用户故事**: 作为开发者，我希望启动流程的每个阶段都可以独立测试，以便提高代码质量和可靠性。

#### 验收标准

1. THE App Initializer SHALL 提供可测试的公共接口
2. THE Module Loader SHALL 提供可测试的公共接口
3. THE UI Launcher SHALL 提供可测试的公共接口
4. THE Bootstrap System SHALL 允许在测试环境中模拟各个启动阶段
5. THE Bootstrap System SHALL 允许在不启动完整应用的情况下测试单个启动阶段

---

### 需求 11：资源清理和生命周期管理

**用户故事**: 作为开发者，我希望应用程序在退出时正确清理所有资源，以便避免资源泄漏和后续启动问题。

#### 验收标准

1. THE Bootstrap System SHALL 注册 QApplication.aboutToQuit 信号以在退出时清理资源
2. WHEN 应用程序正常退出时，THE Bootstrap System SHALL 清理 Splash Screen 和 SingleInstanceManager 资源
3. WHEN 应用程序异常退出时，THE Bootstrap System SHALL 清理 Splash Screen 和 SingleInstanceManager 资源
4. THE Bootstrap System SHALL 确保 SingleInstanceManager.cleanup() 在所有退出路径中被调用
5. THE Bootstrap System SHALL 确保资源清理不会阻塞应用程序退出

---

### 需求 12：QApplication 生命周期管理

**用户故事**: 作为开发者，我希望 QApplication 的创建和销毁时机明确，以便避免 Qt 相关的初始化问题。

#### 验收标准

1. THE App Initializer SHALL 在任何 Qt 组件创建之前创建 QApplication 实例
2. THE App Initializer SHALL 配置 QApplication 的应用程序名称和版本
3. THE App Initializer SHALL 设置应用程序图标
4. THE Bootstrap System SHALL 确保 QApplication 事件循环在模块加载期间保持运行
5. THE Bootstrap System SHALL 在应用程序退出时正确清理 QApplication 资源
