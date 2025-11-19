# 实施计划 - 启动流程重构

本文档定义了启动流程重构的实施任务列表。任务按照依赖关系排序，每个任务都包含明确的目标和相关需求。

## 任务列表

- [x] 1. 创建 Bootstrap 目录结构和基础文件

  - 创建 `core/bootstrap/` 目录
  - 创建 `core/bootstrap/__init__.py` 文件
  - 创建空的 `app_initializer.py`、`module_loader.py`、`ui_launcher.py`、`app_bootstrap.py` 文件
  - _需求: 8.1, 8.2, 8.3, 8.4_

- [x] 2. 实现 AppInitializer 组件

  - [x] 2.1 实现日志系统配置

    - 调用 `init_logging_system()` 配置日志
    - 调用 `setup_console_encoding()` 设置控制台编码（Windows）
    - _需求: 2.1_

  - [x] 2.2 实现 QApplication 创建和配置

    - 创建 QApplication 实例
    - 设置应用程序名称为 "ue_toolkit"
    - 设置应用程序版本为 "1.0.1"
    - 设置应用程序图标（`resources/tubiao.ico`）
    - 设置 Windows AppUserModelID（Windows 平台）
    - _需求: 2.2, 12.1, 12.2, 12.3_

  - [x] 2.3 实现单例检查逻辑
    - 创建 SingleInstanceManager 实例
    - 调用 `is_running()` 检查是否已有实例
    - 如果已有实例，发送激活消息并返回 False
    - 返回 (QApplication, SingleInstanceManager, success) 元组
    - _需求: 2.3, 2.4, 2.5, 2.6_

- [x] 3. 实现 UILauncher 组件

  - [x] 3.1 实现主题配置加载

    - 从 `AppData/ue_toolkit/ui_settings.json` 读取主题配置
    - 支持旧版本配置映射（dark → modern_dark, light → modern_light）
    - 失败时使用默认主题 modern_dark
    - _需求: 4.3, 4.4_

  - [x] 3.2 实现 UI 准备阶段（prepare_ui）

    - 应用主题到 QApplication
    - 根据主题选择 Splash 主题（dark 或 light）
    - 创建 SplashScreen 实例
    - 注册日志处理器
    - 显示 Splash 并刷新 UI
    - _需求: 4.1, 4.2, 4.5_

  - [x] 3.3 实现 UI 显示阶段（show_ui）
    - 创建 UEMainWindow 实例并传入 module_provider
    - 启动 SingleInstanceManager 本地服务器
    - 调用 `main_window.load_initial_module()` 加载初始模块
    - 在回调中关闭 Splash 并显示主窗口
    - _需求: 4.6, 4.7, 4.8_

- [x] 4. 实现 ModuleLoader 组件

  - [x] 4.1 实现 AppManager 设置

    - 创建 AppManager 实例
    - 调用 `app_manager.setup()` 初始化核心服务
    - 返回是否成功
    - _需求: 3.2_

  - [x] 4.2 实现异步模块加载

    - 定义内部回调函数处理 on_complete、on_error、on_progress
    - 调用 `app_manager.start_async()` 异步加载模块
    - 在 on_progress 回调中调用外部 on_progress
    - _需求: 3.3, 3.4, 5.3_

  - [x] 4.3 实现模块依赖连接

    - 获取 ai_assistant、asset_manager、config_tool、site_recommendations 模块
    - 将 asset_manager 逻辑层注入 ai_assistant
    - 将 config_tool 逻辑层注入 ai_assistant
    - 将 site_recommendations 逻辑层注入 ai_assistant
    - 如果依赖模块未加载，记录警告并继续
    - _需求: 3.5, 7.1, 7.2, 7.3, 7.4, 7.5_

  - [x] 4.4 实现 ModuleProviderAdapter 创建
    - 在模块加载完成后创建 ModuleProviderAdapter
    - 通过 on_complete 回调返回
    - _需求: 3.6_

- [ ] 5. 实现 AppBootstrap 协调器

  - [ ] 5.1 实现状态成员初始化

    - 初始化 app_initializer、ui_launcher、module_loader
    - 声明状态成员：app、single_instance、splash、exit_code
    - _需求: 1.1_

  - [ ] 5.2 实现应用初始化阶段

    - 调用 `app_initializer.initialize()`
    - 检查返回的 success 标志
    - 如果失败，返回退出码 1
    - _需求: 1.2, 1.3, 6.4_

  - [ ] 5.3 实现 UI 准备阶段

    - 调用 `ui_launcher.prepare_ui(app)`
    - 保存返回的 Splash Screen 实例
    - _需求: 1.4_

  - [ ] 5.4 实现模块加载回调注册

    - 定义 on_progress 回调（更新 Splash 并刷新事件）
    - 定义 on_complete 回调（调用 show_ui）
    - 定义 on_error 回调（设置退出码并清理）
    - 调用 `module_loader.load_modules()` 注册回调
    - _需求: 1.5, 5.1, 5.2, 5.3, 5.4, 5.5_

  - [ ] 5.5 实现退出清理钩子

    - 注册 `app.aboutToQuit` 信号到 `_cleanup()` 方法
    - _需求: 11.1, 11.2, 11.3, 11.4_

  - [ ] 5.6 实现事件循环启动

    - 调用 `app.exec()` 进入事件循环
    - 返回 exit_code
    - _需求: 1.6, 5.6, 12.4_

  - [ ] 5.7 实现异常捕获和用户提示

    - 捕获所有异常并记录详细日志
    - 如果日志系统未初始化，将错误输出到 stderr
    - 显示用户友好的错误对话框
    - _需求: 6.1, 6.2, 6.3, 6.5_

  - [ ] 5.8 实现退出码管理和资源清理

    - 根据错误类型设置对应的退出码
    - 调用 `_cleanup()` 清理资源
    - 返回退出码
    - _需求: 6.4_

  - [ ] 5.9 实现资源清理方法
    - 关闭 Splash Screen（如果存在）
    - 清理 SingleInstanceManager（如果存在）
    - 确保 QApplication 资源正确释放（通过 aboutToQuit 信号自动处理）
    - 验证事件循环已停止
    - _需求: 11.2, 11.3, 11.4, 11.5, 12.5_

- [ ] 6. 修改 main.py 简化启动逻辑

  - 保留原有代码作为注释（便于回滚）
  - 导入 AppBootstrap
  - 在 main() 函数中创建 AppBootstrap 实例
  - 调用 `bootstrap.run()` 并返回退出码
  - _需求: 8.5, 9.1, 9.2, 9.3, 9.4, 9.5_

- [ ] 7. 测试和验证

  - [ ] 7.1 单元测试 AppInitializer

    - 测试日志系统配置
    - 测试 QApplication 创建
    - 测试单例检查逻辑
    - 模拟已有实例运行的情况
    - _需求: 10.1, 10.4, 10.5_

  - [ ] 7.2 单元测试 UILauncher

    - 测试主题配置加载
    - 测试主题回退逻辑
    - 测试 Splash Screen 创建
    - 模拟主窗口创建
    - _需求: 10.2, 10.4, 10.5_

  - [ ] 7.3 单元测试 ModuleLoader

    - 测试 AppManager.setup() 调用
    - 测试异步回调机制
    - 测试模块依赖连接
    - 模拟模块加载失败
    - _需求: 10.2, 10.4, 10.5_

  - [ ] 7.4 单元测试 AppBootstrap

    - 测试完整启动流程
    - 测试各阶段失败处理
    - 测试退出码返回
    - 测试清理逻辑
    - 测试日志系统未初始化时的 stderr 输出
    - 测试 QApplication 资源释放
    - _需求: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ] 7.5 集成测试

    - [ ] 7.5.1 测试完整启动流程

      - 测试从 main.py 到主窗口显示的完整流程
      - 验证所有阶段按顺序执行
      - _需求: 9.3_

    - [ ] 7.5.2 测试模块加载和依赖

      - 验证所有模块正确加载
      - 验证模块依赖正确建立
      - _需求: 7.1, 7.2, 7.3, 7.4, 7.5_

    - [ ] 7.5.3 测试单实例功能

      - 测试第二次启动时的激活行为
      - 验证服务器正确启动和清理
      - _需求: 2.3, 2.4, 2.5, 2.6_

    - [ ] 7.5.4 测试错误恢复

      - 测试各阶段失败的错误处理
      - 验证清理逻辑正确执行
      - 验证退出码正确返回
      - _需求: 6.1, 6.2, 6.3, 6.4_

    - [ ] 7.5.5 测试日志 fallback
      - 测试日志系统未初始化时的 stderr 输出
      - _需求: 6.5_

  - [ ] 7.6 兼容性验证测试

    - [ ] 7.6.1 验证模块接口兼容性

      - 测试所有现有模块能正常加载
      - 验证模块接口未被修改
      - _需求: 9.1_

    - [ ] 7.6.2 验证配置文件兼容性

      - 使用旧版配置文件启动应用
      - 验证所有配置项正确读取
      - _需求: 9.2_

    - [ ] 7.6.3 验证日志格式兼容性

      - 验证日志输出格式未改变
      - 验证日志文件位置未改变
      - _需求: 9.4_

    - [ ] 7.6.4 验证命令行参数和环境变量
      - 测试所有现有命令行参数
      - 测试所有现有环境变量
      - _需求: 9.5_

  - [ ] 7.7 回滚验证测试
    - 恢复 main.py 的原始版本（从注释中）
    - 验证应用能正常启动
    - 验证所有功能正常工作
    - 删除 `core/bootstrap/` 目录
    - 再次验证应用正常
    - _需求: 9.3_

- [ ] 8. 文档更新和清理
  - 更新 README.md 中的启动流程说明
  - 添加 Bootstrap 系统的开发者文档
  - 更新架构文档和架构图
  - 添加新的错误码说明到故障排除指南
  - 删除 main.py 中的旧代码注释
  - _需求: 9.3, 9.4_
