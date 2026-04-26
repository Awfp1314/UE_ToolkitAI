# UE Toolkit 工作流程

## 应用启动流程

### 完整启动流程

```mermaid
sequenceDiagram
    participant User
    participant Main
    participant Bootstrap
    participant Initializer
    participant ModuleLoader
    participant UILauncher
    participant MainWindow

    User->>Main: 启动应用
    Main->>Main: 设置工作目录
    Main->>Main: 清理临时目录
    Main->>Bootstrap: run()

    Bootstrap->>Bootstrap: 路径迁移检查
    Bootstrap->>Initializer: initialize()
    Initializer->>Initializer: 创建 QApplication
    Initializer->>Initializer: 初始化日志系统
    Initializer->>Initializer: 设置应用元数据
    Initializer->>Initializer: 初始化单实例管理器
    Initializer-->>Bootstrap: app, single_instance

    Bootstrap->>UILauncher: prepare_ui(app)
    UILauncher->>UILauncher: 创建启动画面
    UILauncher-->>Bootstrap: splash_screen

    Bootstrap->>Bootstrap: 启动更新检查（异步）

    Bootstrap->>ModuleLoader: load_modules_async()

    loop 模块加载
        ModuleLoader->>ModuleLoader: 发现模块
        ModuleLoader->>ModuleLoader: 解析依赖
        ModuleLoader->>ModuleLoader: 加载模块
        ModuleLoader-->>Bootstrap: on_progress(percent, message)
        Bootstrap->>UILauncher: update_splash()
    end

    ModuleLoader-->>Bootstrap: on_complete(module_provider)
    Bootstrap->>UILauncher: show_ui()
    UILauncher->>MainWindow: 创建主窗口
    UILauncher->>MainWindow: 添加模块标签页
    UILauncher->>MainWindow: 显示窗口
    UILauncher-->>Bootstrap: main_window

    Bootstrap->>Bootstrap: 进入事件循环
    Bootstrap-->>User: 应用就绪
```

### 启动阶段详解

#### 1. 预初始化阶段

- 设置 Python 路径
- 设置工作目录
- 清理旧临时目录
- 处理命令行参数

#### 2. 路径迁移阶段

- 检查旧版本数据路径
- 迁移配置文件
- 迁移用户数据

#### 3. 应用初始化阶段

- 创建 QApplication 实例
- 初始化日志系统
- 设置应用元数据（名称、版本、图标）
- 初始化单实例管理器
- 加载应用图标和样式

#### 4. UI 准备阶段

- 创建启动画面
- 显示启动画面
- 设置启动画面样式

#### 5. 更新检查阶段（异步）

- 后台检查更新
- 获取最新版本信息
- 比较版本号
- 准备更新通知

#### 6. 模块加载阶段

- 扫描 modules 目录
- 解析 manifest.json
- 构建依赖图
- 检测循环依赖
- 拓扑排序
- 按顺序加载模块
- 初始化模块
- 报告加载进度

#### 7. UI 显示阶段

- 创建主窗口
- 添加模块标签页
- 初始化系统托盘
- 关闭启动画面
- 显示主窗口

#### 8. 事件循环阶段

- 进入 Qt 事件循环
- 处理用户交互
- 执行后台任务

## 模块生命周期

### 模块加载流程

```mermaid
stateDiagram-v2
    [*] --> Discovered: 扫描目录
    Discovered --> Loaded: 加载成功
    Discovered --> Failed: 加载失败
    Loaded --> Initialized: 初始化成功
    Loaded --> Failed: 初始化失败
    Initialized --> Running: 开始运行
    Running --> Stopping: 请求停止
    Stopping --> Unloaded: 清理完成
    Unloaded --> [*]
    Failed --> [*]
```

### 模块发现

1. 扫描 `modules/` 目录
2. 查找 `manifest.json` 文件
3. 解析模块元数据
4. 验证模块结构
5. 注册模块信息

### 模块加载

1. 检查依赖关系
2. 导入模块 Python 包
3. 实例化模块类
4. 验证接口实现
5. 更新模块状态

### 模块初始化

1. 调用 `initialize(config_dir)` 方法
2. 加载模块配置
3. 初始化模块资源
4. 创建 UI 组件
5. 注册事件处理器

### 模块运行

1. 响应用户交互
2. 执行业务逻辑
3. 更新 UI 状态
4. 保存配置变更

### 模块停止

1. 调用 `request_stop()` 方法
2. 停止后台任务
3. 保存当前状态
4. 释放资源

### 模块卸载

1. 调用 `cleanup()` 方法
2. 清理临时文件
3. 关闭数据库连接
4. 释放内存资源
5. 更新模块状态

## 配置管理流程

### 配置加载流程

```mermaid
graph TB
    Start[开始] --> LoadTemplate[加载配置模板]
    LoadTemplate --> LoadUser[加载用户配置]
    LoadUser --> CheckVersion{版本一致?}
    CheckVersion -->|是| Merge[合并配置]
    CheckVersion -->|否| Upgrade[升级配置]
    Upgrade --> Merge
    Merge --> Validate[验证配置]
    Validate --> CheckValid{验证通过?}
    CheckValid -->|是| Cache[缓存配置]
    CheckValid -->|否| UseDefault[使用默认配置]
    UseDefault --> Cache
    Cache --> Return[返回配置]
    Return --> End[结束]
```

### 配置保存流程

```mermaid
graph TB
    Start[开始] --> Validate[验证配置]
    Validate --> CheckValid{验证通过?}
    CheckValid -->|否| Error[返回错误]
    CheckValid -->|是| Backup[创建备份]
    Backup --> Save[保存配置文件]
    Save --> CheckSuccess{保存成功?}
    CheckSuccess -->|否| Restore[从备份恢复]
    CheckSuccess -->|是| UpdateCache[更新缓存]
    UpdateCache --> Notify[通知配置变更]
    Notify --> Success[返回成功]
    Restore --> Error
    Error --> End[结束]
    Success --> End
```

### 配置升级流程

1. 检测版本差异
2. 加载迁移规则
3. 应用迁移规则
4. 保留用户设置
5. 添加新字段默认值
6. 删除废弃字段
7. 验证升级后的配置
8. 保存升级后的配置

## 资产管理流程

### 资产导入流程

```mermaid
sequenceDiagram
    participant User
    participant UI
    participant Importer
    participant Detector
    participant FileOps
    participant AssetCore

    User->>UI: 拖入文件/选择文件
    UI->>Importer: import_asset(path)
    Importer->>Detector: detect_asset_type(path)
    Detector->>Detector: 检查文件结构
    Detector-->>Importer: asset_type

    alt 压缩包
        Importer->>FileOps: extract_archive(path)
        FileOps-->>Importer: extracted_path
    end

    Importer->>Importer: 过滤广告文件
    Importer->>Importer: 识别 UE 版本
    Importer->>Importer: 生成元数据
    Importer->>FileOps: copy_to_library(path)
    FileOps-->>Importer: library_path

    Importer->>AssetCore: add_asset(asset)
    AssetCore->>AssetCore: 保存资产数据
    AssetCore-->>Importer: success

    Importer-->>UI: import_result
    UI-->>User: 显示导入结果
```

### 资产导出流程

```mermaid
sequenceDiagram
    participant User
    participant UI
    participant Exporter
    participant AssetCore
    participant FileOps
    participant UE

    User->>UI: 选择资产
    User->>UI: 选择目标工程
    UI->>Exporter: export_asset(asset, project)

    Exporter->>AssetCore: get_asset(asset_id)
    AssetCore-->>Exporter: asset

    Exporter->>Exporter: 检查版本兼容性
    Exporter->>Exporter: 确定目标路径

    alt CONTENT 类型
        Exporter->>FileOps: copy_to_content(asset, project)
    else PLUGIN 类型
        Exporter->>FileOps: copy_to_plugins(asset, project)
    else PROJECT 类型
        Exporter->>Exporter: 不支持导出
    end

    FileOps-->>Exporter: success

    opt 自动打开 UE
        Exporter->>UE: open_project(project)
    end

    Exporter-->>UI: export_result
    UI-->>User: 显示导出结果
```

### 资产预览流程

1. 选择资产
2. 选择预览工程
3. 复制资产到预览工程
4. 启动 UE 编辑器
5. 打开预览工程
6. 用户预览资产
7. 关闭 UE 编辑器
8. 可选：设置缩略图

## AI 助手工作流程

### 对话流程

```mermaid
sequenceDiagram
    participant User
    participant ChatWindow
    participant LLMClient
    participant ToolSystem
    participant Module

    User->>ChatWindow: 输入消息
    ChatWindow->>ChatWindow: 添加到历史
    ChatWindow->>LLMClient: send_message(messages, tools)

    alt 流式响应
        loop 接收流
            LLMClient-->>ChatWindow: 响应片段
            ChatWindow->>ChatWindow: 显示响应
        end
    else 非流式响应
        LLMClient-->>ChatWindow: 完整响应
        ChatWindow->>ChatWindow: 显示响应
    end

    opt 工具调用
        ChatWindow->>ChatWindow: 解析工具调用
        ChatWindow->>User: 请求确认
        User-->>ChatWindow: 确认
        ChatWindow->>ToolSystem: execute_tool(tool_call)
        ToolSystem->>Module: 调用模块功能
        Module-->>ToolSystem: 执行结果
        ToolSystem-->>ChatWindow: tool_result
        ChatWindow->>LLMClient: send_message(tool_result)
        LLMClient-->>ChatWindow: 最终响应
    end

    ChatWindow-->>User: 显示完整对话
```

### 工具调用流程

1. LLM 识别需要调用工具
2. 返回工具调用请求
3. 解析工具名称和参数
4. 请求用户确认（可选）
5. 执行工具函数
6. 获取执行结果
7. 将结果发送回 LLM
8. LLM 生成最终响应

### MCP 工具调用流程

```mermaid
sequenceDiagram
    participant AI as AI助手
    participant MCP as MCP客户端
    participant Bridge as MCP桥接
    participant UE as UE编辑器

    AI->>MCP: 调用工具
    MCP->>Bridge: JSON-RPC请求
    Bridge->>Bridge: 解析请求
    Bridge->>UE: HTTP API调用
    UE->>UE: 执行操作
    UE-->>Bridge: 返回结果
    Bridge->>Bridge: 格式化响应
    Bridge-->>MCP: JSON-RPC响应
    MCP-->>AI: 工具结果
    AI->>AI: 生成最终响应
```

## 工程管理流程

### 工程扫描流程

1. 扫描配置的磁盘路径
2. 查找 `.uproject` 文件
3. 解析工程文件
4. 识别 UE 版本
5. 检测工程类型（C++/蓝图）
6. 提取工程元数据
7. 保存工程信息
8. 更新 UI 显示

### 工程启动流程

1. 选择工程
2. 检查 UE 版本
3. 查找 UE 编辑器路径
4. 构建启动命令
5. 启动 UE 编辑器
6. 监控进程状态
7. 更新最后打开时间

### 工程重命名流程

1. 选择工程
2. 输入新名称
3. 验证名称合法性
4. 关闭 UE 编辑器（如果打开）
5. 重命名工程文件
6. 更新工程文件内容
7. 重命名工程目录
8. 更新工程信息
9. 刷新 UI 显示

## 配置工具流程

### 配置提取流程

1. 选择源工程
2. 选择配置类型
3. 定位配置文件
4. 读取配置文件
5. 创建配置快照
6. 保存快照元数据
7. 显示提取结果

### 配置应用流程

```mermaid
sequenceDiagram
    participant User
    participant UI
    participant ConfigTool
    participant VersionMatcher
    participant FileOps

    User->>UI: 选择配置快照
    User->>UI: 选择目标工程
    UI->>ConfigTool: apply_config(snapshot, project)

    ConfigTool->>VersionMatcher: check_compatibility(snapshot, project)
    VersionMatcher-->>ConfigTool: is_compatible

    alt 不兼容
        ConfigTool-->>UI: 显示警告
        UI->>User: 请求确认
        User-->>UI: 确认/取消
    end

    opt 创建备份
        ConfigTool->>FileOps: backup_config(project)
    end

    ConfigTool->>FileOps: copy_config_files(snapshot, project)
    FileOps-->>ConfigTool: success

    ConfigTool-->>UI: apply_result
    UI-->>User: 显示应用结果
```

## 许可证验证流程

### 许可证状态检查流程

```mermaid
graph TB
    Start[开始] --> CheckCache{缓存有效?}
    CheckCache -->|是| ReturnCache[返回缓存状态]
    CheckCache -->|否| GetMachineID[获取机器ID]
    GetMachineID --> CallAPI[调用许可证API]
    CallAPI --> CheckResponse{API成功?}
    CheckResponse -->|否| ReturnError[返回错误状态]
    CheckResponse -->|是| ParseStatus[解析许可证状态]
    ParseStatus --> UpdateCache[更新缓存]
    UpdateCache --> ReturnStatus[返回许可证状态]
    ReturnCache --> End[结束]
    ReturnError --> End
    ReturnStatus --> End
```

### 许可证激活流程

1. 用户输入激活码
2. 验证激活码格式
3. 获取机器 ID
4. 调用激活 API
5. 服务器验证激活码
6. 绑定机器 ID
7. 返回激活结果
8. 保存许可证信息
9. 刷新许可证状态
10. 显示激活结果

### 试用流程

1. 检查是否已试用
2. 获取机器 ID
3. 调用试用 API
4. 服务器记录试用
5. 返回试用期限
6. 保存试用信息
7. 刷新许可证状态
8. 显示试用信息

## 更新检查流程

### 更新检查流程

```mermaid
sequenceDiagram
    participant App
    participant UpdateChecker
    participant Server
    participant User

    App->>UpdateChecker: 启动更新检查（异步）
    UpdateChecker->>Server: 获取最新版本信息
    Server-->>UpdateChecker: 版本信息

    UpdateChecker->>UpdateChecker: 比较版本号

    alt 有新版本
        UpdateChecker->>UpdateChecker: 准备更新通知
        UpdateChecker->>User: 显示更新对话框
        User->>User: 查看更新日志

        alt 用户选择更新
            User->>UpdateChecker: 点击下载
            UpdateChecker->>Server: 打开下载链接
        else 用户选择跳过
            User->>UpdateChecker: 关闭对话框
        end
    else 已是最新版本
        UpdateChecker->>UpdateChecker: 不显示通知
    end
```

## 错误处理流程

### 全局错误处理

1. 捕获异常
2. 记录详细日志
3. 分析错误类型
4. 生成用户友好消息
5. 显示错误对话框
6. 提供解决建议
7. 可选：发送错误报告

### 模块错误处理

1. 模块内部捕获异常
2. 记录模块日志
3. 尝试恢复操作
4. 如果无法恢复，向上传播
5. 更新模块状态
6. 通知用户

### 网络错误处理

1. 检测网络连接
2. 设置超时时间
3. 捕获网络异常
4. 重试机制（可选）
5. 降级处理
6. 通知用户

## 资源清理流程

### 应用退出流程

```mermaid
sequenceDiagram
    participant User
    participant MainWindow
    participant Bootstrap
    participant ModuleManager
    participant Module

    User->>MainWindow: 关闭窗口/退出
    MainWindow->>Bootstrap: aboutToQuit信号
    Bootstrap->>Bootstrap: _cleanup()

    Bootstrap->>ModuleManager: request_stop_all()
    loop 每个模块
        ModuleManager->>Module: request_stop()
        Module->>Module: 停止后台任务
        Module->>Module: 保存状态
        Module-->>ModuleManager: 完成
    end

    Bootstrap->>ModuleManager: cleanup_all()
    loop 每个模块
        ModuleManager->>Module: cleanup()
        Module->>Module: 释放资源
        Module-->>ModuleManager: CleanupResult
    end

    Bootstrap->>Bootstrap: 关闭启动画面
    Bootstrap->>Bootstrap: 清理单实例管理器
    Bootstrap->>Bootstrap: 停止更新检查
    Bootstrap-->>MainWindow: 清理完成
    MainWindow->>User: 应用退出
```

### 资源清理顺序

1. 请求所有模块停止
2. 等待模块停止完成
3. 清理模块资源
4. 关闭启动画面
5. 清理单实例管理器
6. 停止更新检查线程
7. 保存应用状态
8. 关闭日志系统
9. 释放 QApplication 资源
10. 退出应用

## 性能优化流程

### 启动优化

1. 延迟加载非关键模块
2. 异步加载模块
3. 预加载常用资源
4. 缓存配置数据
5. 并行初始化

### 运行时优化

1. 使用配置缓存
2. 懒加载 AI 模型
3. 异步执行耗时操作
4. 使用线程池
5. 定期清理缓存

### 内存优化

1. 及时释放不用的资源
2. 使用弱引用
3. 限制缓存大小
4. 监控内存使用
5. 定期垃圾回收
