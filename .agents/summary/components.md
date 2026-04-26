# UE Toolkit 主要组件

## 核心组件

### 1. 应用启动引导 (Bootstrap)

#### AppBootstrap

**文件**: `core/bootstrap/app_bootstrap.py`

**职责**:

- 协调整个应用启动流程
- 管理启动阶段的依赖关系
- 处理启动异常和资源清理

**关键方法**:

- `run()`: 执行完整启动流程
- `_cleanup()`: 清理资源

**启动阶段**:

1. 路径迁移检查
2. 应用初始化
3. UI 准备
4. 更新检查（异步）
5. 模块加载（异步）
6. UI 显示
7. 事件循环启动

#### AppInitializer

**文件**: `core/bootstrap/app_initializer.py`

**职责**:

- 创建 QApplication 实例
- 初始化日志系统
- 设置应用元数据
- 初始化单实例管理器

**关键方法**:

- `initialize()`: 初始化应用程序

#### ModuleLoader

**文件**: `core/bootstrap/module_loader.py`

**职责**:

- 异步加载所有模块
- 报告加载进度
- 处理模块依赖关系

**关键方法**:

- `load_modules(on_progress, on_complete, on_error)`: 异步加载模块

#### UILauncher

**文件**: `core/bootstrap/ui_launcher.py`

**职责**:

- 创建和显示启动画面
- 创建主窗口
- 初始化系统托盘

**关键方法**:

- `prepare_ui(app)`: 准备 UI
- `show_ui(app, module_provider, single_instance)`: 显示主窗口

### 2. 模块管理系统

#### ModuleManager

**文件**: `core/module_manager.py`

**职责**:

- 模块发现和注册
- 依赖关系解析
- 模块生命周期管理

**核心功能**:

**模块发现**:

```python
def discover_modules(self) -> Dict[str, ModuleInfo]:
    """扫描 modules/ 目录，解析 manifest.json"""
```

**依赖解析**:

```python
def resolve_dependencies(self) -> List[str]:
    """
    - 检查自依赖
    - 检测循环依赖
    - 拓扑排序
    """
```

**模块加载**:

```python
def load_modules(self) -> bool:
    """按依赖顺序加载模块"""

def load_modules_async(on_progress, on_complete, on_error):
    """异步加载模块，报告进度"""
```

**模块初始化**:

```python
def initialize_modules(self) -> bool:
    """初始化所有已加载的模块"""
```

**模块状态**:

- `DISCOVERED`: 已发现
- `LOADED`: 已加载
- `INITIALIZED`: 已初始化
- `FAILED`: 失败
- `UNLOADED`: 已卸载

#### ModuleInfo

**文件**: `core/module_manager.py`

**属性**:

- `name`: 模块名称
- `display_name`: 显示名称
- `version`: 版本号
- `description`: 描述
- `author`: 作者
- `dependencies`: 依赖列表
- `module_path`: 模块路径
- `manifest_path`: manifest.json 路径
- `state`: 模块状态
- `instance`: 模块实例

### 3. 配置管理系统

#### ConfigManager

**文件**: `core/config/config_manager.py`

**职责**:

- 配置模板和用户配置管理
- 配置版本管理和升级
- 配置缓存和热重载
- 自动备份和恢复

**核心功能**:

**配置加载**:

```python
def load_template(self) -> Dict[str, Any]:
    """加载配置模板"""

def load_user_config(self) -> Dict[str, Any]:
    """加载用户配置"""

def get_module_config(self, force_reload=False) -> Dict[str, Any]:
    """获取合并后的配置（带缓存）"""
```

**配置保存**:

```python
def save_user_config(self, config, backup_reason="manual_save") -> bool:
    """保存用户配置（同步，带备份）"""

def save_user_config_fast(self, config) -> bool:
    """快速保存（无备份）"""

def save_user_config_async(self, config, callback=None):
    """异步保存"""
```

**配置升级**:

```python
def upgrade_config(self, template, user_config) -> Dict[str, Any]:
    """
    - 检测版本变化
    - 合并新字段
    - 保留用户设置
    """
```

**配置备份**:

```python
def backup_config(self, reason="manual") -> bool:
    """创建配置备份"""

def list_backups(self) -> List[Dict[str, Any]]:
    """列出所有备份"""

def restore_from_backup(self, backup_index=0) -> bool:
    """从备份恢复"""
```

**配置缓存**:

- 缓存有效期: 5 分钟
- 自动失效机制
- 强制刷新支持

#### ConfigValidator

**文件**: `core/config/config_validator.py`

**职责**:

- 基于 JSON Schema 验证配置
- 确保配置完整性和正确性

#### ConfigBackup

**文件**: `core/config/config_backup.py`

**职责**:

- 管理配置备份文件
- 支持多版本备份
- 自动清理旧备份

### 4. 安全与许可证管理

#### LicenseManager

**文件**: `core/security/license_manager.py`

**职责**:

- 许可证状态管理
- 本地和服务器端验证
- 试用期管理
- 激活码验证

**核心功能**:

**许可证状态缓存**:

```python
class LicenseStatusCache:
    def __init__(self):
        self._cache_duration = 300  # 5分钟
        self._status = None
        self._last_refresh = 0

    def get_status_sync(self) -> LicenseStatus:
        """获取许可证状态（带缓存）"""

    def force_refresh(self) -> LicenseStatus:
        """强制刷新许可证状态"""
```

**许可证验证**:

```python
def get_license_status(self) -> LicenseStatus:
    """
    返回: LicenseStatus
    - is_valid: 是否有效
    - is_trial: 是否试用
    - days_remaining: 剩余天数
    - tier: 许可证等级
    """

def activate(self, activation_key: str) -> bool:
    """激活许可证"""
```

**API 调用**:

- `/api/v2/license/status`: 获取许可证状态
- `/api/v2/license/activate`: 激活许可证
- `/api/v2/trial/start`: 开始试用
- `/api/v2/trial/reset`: 重置试用（管理员）

#### MachineID

**文件**: `core/security/machine_id.py`

**职责**:

- 生成唯一机器标识
- 基于硬件信息的指纹

**实现**:

- Windows: 使用 wmic 获取主板序列号、CPU ID
- 其他平台: 使用 MAC 地址

#### FeatureGate

**文件**: `core/security/feature_gate.py`

**职责**:

- 功能权限控制
- 免费/付费功能区分

**使用示例**:

```python
@require_license(tier="pro")
def premium_feature():
    """付费功能"""
    pass
```

### 5. 日志系统

#### Logger

**文件**: `core/logger.py`

**职责**:

- 统一日志记录接口
- 多级别日志支持
- 日志文件管理

**日志级别**:

- DEBUG: 调试信息
- INFO: 一般信息
- WARNING: 警告信息
- ERROR: 错误信息
- CRITICAL: 严重错误

**日志文件**:

- `logs/runtime/ue_toolkit.log`: 运行时日志
- `logs/mcp/*.log`: MCP 服务器日志
- `logs/build/*.log`: 构建日志

**使用示例**:

```python
from core.logger import get_logger

logger = get_logger(__name__)
logger.info("应用启动")
logger.error("错误信息", exc_info=True)
```

### 6. AI 服务

#### EmbeddingService

**文件**: `core/ai_services/embedding_service.py`

**职责**:

- 提供语义嵌入向量服务
- 支持文本向量化

**模型**:

- `BAAI/bge-small-zh-v1.5`
- 输出维度: 512

**使用场景**:

- AI 记忆系统的语义检索
- 意图识别

### 7. 工具类

#### ThemeManager

**文件**: `core/utils/theme_builder.py`

**职责**:

- 主题管理
- 深色/浅色主题切换
- 动态加载 QSS 样式

**使用示例**:

```python
from core.utils.theme_builder import ThemeManager

theme_manager = ThemeManager.instance()
theme_manager.set_theme("dark")
```

#### FileUtils

**文件**: `core/utils/file_utils.py`

**职责**:

- 文件读写、复制、移动
- 安全的文件操作封装

#### PathUtils

**文件**: `core/utils/path_utils.py`

**职责**:

- 路径规范化
- 相对路径和绝对路径转换

#### ThreadManager

**文件**: `core/utils/thread_manager.py`

**职责**:

- 线程池管理
- 异步任务执行

#### PerformanceMonitor

**文件**: `core/utils/performance_monitor.py`

**职责**:

- 性能指标收集
- 资源使用监控

## 模块组件

### 1. AI 助手模块

#### AIAssistantModule

**文件**: `modules/ai_assistant/ai_assistant.py`

**职责**:

- AI 聊天界面
- LLM 客户端管理
- 工具系统集成
- MCP 协议支持

**核心功能**:

**LLM 客户端**:

- `APILLMClient`: API 调用客户端（OpenAI、Claude、Gemini 等）
- `OllamaLLMClient`: Ollama 本地模型客户端
- `UEToolClient`: UE 工具客户端
- `BlueprintAnalyzerClient`: 蓝图分析客户端

**工具系统**:

```python
def _init_tools_system(self):
    """
    初始化工具系统:
    - 资产管理工具
    - 工程管理工具
    - 配置工具
    - MCP 工具
    """
```

**MCP 集成**:

- 动态工具发现
- 26+ 蓝图操作工具
- 自动权限控制

#### ChatWindow

**文件**: `modules/ai_assistant/ui/chat_window.py`

**职责**:

- 聊天界面
- 消息显示和输入
- 流式响应处理
- 工具调用确认

### 2. 资产管理模块

#### AssetManagerModule

**文件**: `modules/asset_manager/asset_manager.py`

**职责**:

- 资产库管理
- 资产导入导出
- 缩略图生成
- 资产搜索和过滤

**核心组件**:

**AssetManagerLogic** (`logic/asset_manager_logic.py`)

- 业务逻辑层
- 资产操作协调

**AssetCore** (`logic/asset_core.py`)

- 核心数据层
- 资产存储和检索

**AssetController** (`logic/asset_controller.py`)

- 控制器层
- UI 和逻辑的桥梁

**AssetImporter** (`logic/asset_importer.py`)

- 资产导入
- 自动识别资产类型
- 解压和过滤

**AssetExporter** (`logic/asset_exporter.py`)

- 资产导出
- 复制到目标工程

**AssetMigrator** (`logic/asset_migrator.py`)

- 资产迁移
- 路径更新

**资产类型**:

```python
class AssetType(Enum):
    CONTENT = "content"      # 资产包
    PLUGIN = "plugin"        # 插件
    PROJECT = "project"      # 完整工程
    OTHERS = "others"        # 通用多媒体
```

### 3. 工程管理模块

#### MyProjectsModule

**文件**: `modules/my_projects/my_projects.py`

**职责**:

- 扫描本地虚幻引擎项目
- 多版本工程管理
- 快速启动和重命名

**核心功能**:

- 自动扫描磁盘
- 项目路径解析
- UE 版本检测
- 项目启动

### 4. 配置工具模块

#### ConfigToolModule

**文件**: `modules/config_tool/config_tool.py`

**职责**:

- 项目配置提取和应用
- 编辑器偏好设置同步
- 配置备份和回滚

**配置类型**:

- 项目配置 (Project Settings)
- 编辑器偏好设置 (User Preferences)

**核心功能**:

- 配置提取
- 配置应用
- 版本匹配检查
- 配置备份

### 5. 站点推荐模块

#### SiteRecommendationsModule

**文件**: `modules/site_recommendations/site_recommendations.py`

**职责**:

- 推荐相关网站和资源
- 快速访问常用链接

## UI 组件

### 1. 主窗口

#### UEMainWindow

**文件**: `ui/ue_main_window.py`

**职责**:

- 管理模块标签页
- 协调模块间通信
- 处理窗口事件

**核心功能**:

- 动态添加模块标签页
- 模块间消息传递
- 窗口状态管理

### 2. 设置界面

#### SettingsWidget

**文件**: `ui/settings_widget.py`

**职责**:

- 全局设置管理
- 模块配置界面
- 主题切换

**设置类别**:

- 通用设置
- AI 助手设置
- 资产管理设置
- 工程管理设置
- 配置工具设置

### 3. 系统托盘

#### SystemTray

**文件**: `ui/system_tray.py`

**职责**:

- 后台运行支持
- 快捷操作菜单
- 通知显示

**菜单项**:

- 显示/隐藏主窗口
- 快速操作
- 退出应用

### 4. 启动画面

#### SplashScreen

**文件**: `ui/splash_screen.py`

**职责**:

- 显示启动画面
- 显示加载进度
- 显示加载消息

### 5. 对话框

**MessageDialog** (`ui/dialogs/message_dialog.py`)

- 消息提示对话框
- 支持多种类型（info、warning、error、success）

**AssetPathSetupDialog** (`ui/asset_path_setup_dialog.py`)

- 资产路径设置对话框
- 首次运行时引导用户设置资产库路径

## 服务组件

### 1. MCP 桥接服务

#### BlueprintExtractorBridge

**文件**: `scripts/mcp_servers/blueprint_extractor_bridge.py`

**职责**:

- 实现 MCP stdio 协议
- 连接 UE Editor HTTP API
- 提供蓝图操作工具

**协议实现**:

- `initialize`: 初始化连接
- `tools/list`: 列出所有工具
- `tools/call`: 调用工具

**工具定义**:

- 文件: `scripts/mcp_servers/blueprint_extractor_tools.json`
- 工具数量: 26+
- 分类: 免费工具（18个）、付费工具（8个）

### 2. 更新检查服务

#### UpdateChecker

**文件**: `core/update_checker.py`

**职责**:

- 后台检查更新
- 版本比较
- 更新通知

**检查流程**:

1. 获取远程版本信息
2. 比较本地版本
3. 显示更新通知
4. 提供下载链接

#### UpdateCheckerIntegration

**文件**: `core/bootstrap/update_checker_integration.py`

**职责**:

- 集成更新检查到启动流程
- 管理更新检查线程
- 显示更新对话框

### 3. 单实例管理

#### SingleInstanceManager

**文件**: `core/single_instance.py`

**职责**:

- 防止应用重复启动
- 进程间通信

**实现**:

- 使用文件锁机制
- 检测已运行实例
- 激活已运行窗口

## 工具脚本

### 1. 打包脚本

**目录**: `scripts/package/`

**核心文件**:

- `ue_toolkit.spec`: PyInstaller 配置
- `build.py`: 构建脚本
- `config/UeToolkitpack.iss`: Inno Setup 配置

**打包流程**:

1. 清理旧构建
2. 运行 PyInstaller
3. 复制资源文件
4. 创建安装程序

### 2. 开发工具

**目录**: `scripts/dev/`

**工具**:

- 代码生成器
- 测试工具
- 调试脚本

### 3. 维护脚本

**目录**: `scripts/maintenance/`

**工具**:

- 日志清理
- 缓存清理
- 数据库维护

## 组件间通信

### 1. 信号槽机制

- 使用 PyQt6 的信号槽
- 松耦合的事件驱动

### 2. 直接调用

- 模块间通过接口直接调用
- 通过 ModuleManager 获取模块实例

### 3. 配置共享

- 通过 ConfigManager 共享配置
- 配置变更通知

### 4. 消息传递

- 主窗口协调模块间消息
- 支持跨模块操作

## 组件生命周期

### 启动阶段

1. 创建 QApplication
2. 初始化日志系统
3. 加载配置
4. 发现模块
5. 解析依赖
6. 加载模块
7. 初始化模块
8. 显示 UI

### 运行阶段

1. 处理用户交互
2. 执行业务逻辑
3. 更新 UI
4. 保存配置
5. 后台任务

### 关闭阶段

1. 请求模块停止
2. 清理模块资源
3. 保存配置
4. 关闭日志
5. 释放资源
6. 退出应用
