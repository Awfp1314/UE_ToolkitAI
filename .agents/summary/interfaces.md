# UE Toolkit 接口与 API

## 模块接口

### ModuleInterface

**文件**: `core/module_interface.py`

所有功能模块必须实现的标准接口。

```python
class ModuleInterface:
    """模块接口基类"""

    def initialize(self, config_dir: str) -> bool:
        """
        初始化模块

        Args:
            config_dir: 配置目录路径

        Returns:
            bool: 初始化是否成功
        """
        pass

    def get_widget(self) -> QWidget:
        """
        获取模块的 UI 组件

        Returns:
            QWidget: 模块的主界面组件
        """
        pass

    def request_stop(self) -> None:
        """
        请求模块停止运行
        用于优雅关闭，给模块时间保存状态
        """
        pass

    def cleanup(self) -> CleanupResult:
        """
        清理模块资源

        Returns:
            CleanupResult: 清理结果
                - success: 是否成功
                - message: 清理消息
                - warnings: 警告列表
        """
        pass
```

### 模块 Manifest

**文件**: `modules/*/manifest.json`

每个模块必须包含 manifest.json 文件，描述模块元数据。

```json
{
  "name": "module_name",
  "display_name": "模块显示名称",
  "version": "1.0.0",
  "description": "模块描述",
  "author": "作者",
  "dependencies": ["dependency1", "dependency2"],
  "entry_point": "module_file.ModuleClass",
  "icon": "icon.png",
  "enabled": true
}
```

**字段说明**:

- `name`: 模块唯一标识符（必需）
- `display_name`: 显示名称（必需）
- `version`: 版本号（必需）
- `description`: 模块描述
- `author`: 作者
- `dependencies`: 依赖的其他模块列表
- `entry_point`: 模块入口类（必需）
- `icon`: 模块图标文件名
- `enabled`: 是否启用

## 配置接口

### ConfigManager API

**文件**: `core/config/config_manager.py`

#### 加载配置

```python
# 获取模块配置（合并模板和用户配置）
config = config_manager.get_module_config()

# 强制重新加载配置
config = config_manager.get_module_config(force_reload=True)

# 异步获取配置
config_manager.get_module_config_async(
    callback=lambda config: print(config)
)
```

#### 保存配置

```python
# 同步保存（带备份）
success = config_manager.save_user_config(
    config,
    backup_reason="user_change"
)

# 快速保存（无备份）
success = config_manager.save_user_config_fast(config)

# 异步保存
config_manager.save_user_config_async(
    config,
    callback=lambda success: print(f"保存{'成功' if success else '失败'}")
)
```

#### 更新配置值

```python
# 更新单个配置项
success = config_manager.update_config_value(
    "settings.theme",
    "dark"
)
```

#### 配置备份

```python
# 创建备份
success = config_manager.backup_config(reason="before_update")

# 列出所有备份
backups = config_manager.list_backups()
# 返回: [{"path": "...", "timestamp": "...", "reason": "..."}, ...]

# 从备份恢复
success = config_manager.restore_from_backup(backup_index=0)

# 获取备份统计
stats = config_manager.get_backup_stats()
# 返回: {"count": 5, "total_size": 12345, "oldest": "...", "newest": "..."}
```

#### 配置验证

```python
# 验证配置
is_valid = config_manager.validate_config(config)
```

### 配置 Schema

**文件**: `modules/*/config_schema.py`

每个模块可以定义配置 Schema 用于验证。

```python
def get_module_schema() -> ConfigSchema:
    return {
        "type": "object",
        "properties": {
            "setting1": {
                "type": "string",
                "default": "default_value"
            },
            "setting2": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100
            }
        },
        "required": ["setting1"]
    }
```

## 许可证接口

### LicenseManager API

**文件**: `core/security/license_manager.py`

#### 获取许可证状态

```python
from core.security.license_manager import get_license_status

# 获取许可证状态（带缓存）
status = get_license_status()

# 返回: LicenseStatus
# - is_valid: bool (是否有效)
# - is_trial: bool (是否试用)
# - days_remaining: int (剩余天数)
# - tier: str (许可证等级: "free", "pro", "enterprise")
# - features: List[str] (可用功能列表)
```

#### 强制刷新许可证

```python
from core.security.license_manager import force_refresh_license_cache

# 强制刷新许可证状态（跳过缓存）
status = force_refresh_license_cache()
```

#### 激活许可证

```python
license_manager = LicenseManager()

# 激活许可证
success = license_manager.activate(activation_key="XXXX-XXXX-XXXX-XXXX")
```

#### 获取购买链接

```python
from core.security.license_manager import get_purchase_link_cached

# 获取购买链接（带缓存）
link = get_purchase_link_cached()
```

#### 功能权限检查

```python
from core.security.feature_gate import require_license

# 装饰器方式
@require_license(tier="pro")
def premium_feature():
    """付费功能"""
    pass

# 手动检查
from core.security.feature_gate import check_feature_access

if check_feature_access("blueprint_modify"):
    # 执行付费功能
    pass
else:
    # 显示升级提示
    pass
```

### 许可证 API 端点

**服务器**: 配置在 `core/security/license_manager.py` 中

#### 获取许可证状态

```
POST /api/v2/license/status
Content-Type: application/json

{
  "machine_id": "unique_machine_id"
}

Response:
{
  "success": true,
  "is_valid": true,
  "is_trial": false,
  "days_remaining": 365,
  "tier": "pro",
  "features": ["blueprint_read", "blueprint_modify"]
}
```

#### 激活许可证

```
POST /api/v2/license/activate
Content-Type: application/json

{
  "machine_id": "unique_machine_id",
  "activation_key": "XXXX-XXXX-XXXX-XXXX"
}

Response:
{
  "success": true,
  "message": "激活成功"
}
```

#### 开始试用

```
POST /api/v2/trial/start
Content-Type: application/json

{
  "machine_id": "unique_machine_id"
}

Response:
{
  "success": true,
  "trial_days": 7
}
```

## AI 助手接口

### LLM 客户端接口

**文件**: `modules/ai_assistant/clients/base_llm_client.py`

所有 LLM 客户端必须实现的基类。

```python
class BaseLLMClient:
    """LLM 客户端基类"""

    def send_message(
        self,
        messages: List[Dict[str, str]],
        stream: bool = False,
        tools: Optional[List[Dict]] = None,
        **kwargs
    ) -> Union[str, Iterator[str]]:
        """
        发送消息到 LLM

        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            stream: 是否流式响应
            tools: 可用工具列表
            **kwargs: 其他参数（model, temperature 等）

        Returns:
            str: 完整响应（非流式）
            Iterator[str]: 响应流（流式）
        """
        pass
```

### LLM 客户端工厂

```python
from modules.ai_assistant.clients.llm_client_factory import LLMClientFactory

# 创建客户端
client = LLMClientFactory.create_client(
    provider="openai",  # openai, claude, gemini, deepseek, ollama
    config={
        "api_key": "your_api_key",
        "model": "gpt-4",
        "base_url": "https://api.openai.com/v1"  # 可选
    }
)

# 发送消息
response = client.send_message(
    messages=[
        {"role": "user", "content": "Hello"}
    ],
    stream=False
)
```

### 工具系统接口

**工具定义格式**:

```python
tool_definition = {
    "name": "tool_name",
    "description": "工具描述",
    "parameters": {
        "type": "object",
        "properties": {
            "param1": {
                "type": "string",
                "description": "参数描述"
            }
        },
        "required": ["param1"]
    }
}
```

**工具调用格式**:

```python
tool_call = {
    "name": "tool_name",
    "arguments": {
        "param1": "value1"
    }
}
```

**工具结果格式**:

```python
tool_result = {
    "success": True,
    "result": "工具执行结果",
    "error": None  # 如果失败，包含错误信息
}
```

## MCP 协议接口

### MCP Bridge API

**文件**: `scripts/mcp_servers/blueprint_extractor_bridge.py`

实现标准的 MCP stdio 协议。

#### 初始化连接

```json
Request:
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {
      "name": "ue_toolkit",
      "version": "1.2.52"
    }
  }
}

Response:
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": {
      "tools": {}
    },
    "serverInfo": {
      "name": "blueprint_extractor_bridge",
      "version": "1.0.0"
    }
  }
}
```

#### 列出工具

```json
Request:
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list",
  "params": {}
}

Response:
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "tools": [
      {
        "name": "ExtractBlueprint",
        "description": "提取指定蓝图的结构",
        "inputSchema": {
          "type": "object",
          "properties": {
            "AssetPath": {
              "type": "string",
              "description": "蓝图资产路径"
            }
          },
          "required": ["AssetPath"]
        }
      }
    ]
  }
}
```

#### 调用工具

```json
Request:
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "ExtractBlueprint",
    "arguments": {
      "AssetPath": "/Game/Blueprints/BP_Character"
    }
  }
}

Response:
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\"status\": \"success\", \"data\": {...}}"
      }
    ]
  }
}
```

### UE Editor HTTP API

**端点**: `http://localhost:30010`

Blueprint Extractor 插件提供的 HTTP API。

#### 提取蓝图

```
POST /BlueprintExtractor/ExtractBlueprint
Content-Type: application/json

{
  "AssetPath": "/Game/Blueprints/BP_Character",
  "Scope": "Full"  // "Minimal", "Full", "Detailed"
}

Response:
{
  "status": "success",
  "data": {
    "name": "BP_Character",
    "parent_class": "Character",
    "variables": [...],
    "functions": [...],
    "components": [...]
  }
}
```

#### 获取活动蓝图

```
POST /BlueprintExtractor/GetActiveBlueprint
Content-Type: application/json

{}

Response:
{
  "status": "success",
  "asset_path": "/Game/Blueprints/BP_Character"
}
```

#### 搜索资产

```
POST /BlueprintExtractor/SearchAssets
Content-Type: application/json

{
  "SearchTerm": "Character",
  "AssetClass": "Blueprint",
  "MaxResults": 10
}

Response:
{
  "status": "success",
  "assets": [
    {
      "path": "/Game/Blueprints/BP_Character",
      "name": "BP_Character",
      "class": "Blueprint"
    }
  ]
}
```

## 日志接口

### Logger API

**文件**: `core/logger.py`

```python
from core.logger import get_logger

# 获取日志记录器
logger = get_logger(__name__)

# 记录不同级别的日志
logger.debug("调试信息")
logger.info("一般信息")
logger.warning("警告信息")
logger.error("错误信息")
logger.critical("严重错误")

# 记录异常
try:
    # 代码
    pass
except Exception as e:
    logger.error("操作失败", exc_info=True)
```

## 事件与信号

### PyQt6 信号

模块间通信使用 PyQt6 的信号槽机制。

```python
from PyQt6.QtCore import pyqtSignal, QObject

class MyModule(QObject):
    # 定义信号
    data_changed = pyqtSignal(dict)
    operation_completed = pyqtSignal(bool, str)

    def some_operation(self):
        # 发射信号
        self.data_changed.emit({"key": "value"})
        self.operation_completed.emit(True, "操作成功")

# 连接信号
module = MyModule()
module.data_changed.connect(lambda data: print(data))
module.operation_completed.connect(
    lambda success, msg: print(f"{'成功' if success else '失败'}: {msg}")
)
```

### 常用信号

**主窗口信号**:

- `module_changed`: 模块切换
- `settings_changed`: 设置变更

**配置管理器信号**:

- `config_changed`: 配置变更
- `config_saved`: 配置保存

**许可证管理器信号**:

- `license_status_changed`: 许可证状态变更

## 数据模型

### Asset 模型

**文件**: `modules/asset_manager/logic/asset_model.py`

```python
class Asset:
    """资产数据模型"""

    id: str                    # 唯一标识符
    name: str                  # 资产名称
    type: AssetType            # 资产类型
    path: str                  # 资产路径
    thumbnail: Optional[str]   # 缩略图路径
    description: str           # 描述
    tags: List[str]            # 标签
    ue_version: str            # UE 版本
    created_at: datetime       # 创建时间
    updated_at: datetime       # 更新时间
    metadata: Dict[str, Any]   # 元数据
```

### Project 模型

**文件**: `modules/my_projects/logic/project_model.py`

```python
class Project:
    """工程数据模型"""

    name: str                  # 工程名称
    path: str                  # 工程路径
    ue_version: str            # UE 版本
    engine_association: str    # 引擎关联
    is_cpp: bool               # 是否 C++ 工程
    last_opened: datetime      # 最后打开时间
```

### Config 模型

**文件**: `modules/config_tool/logic/config_model.py`

```python
class ConfigSnapshot:
    """配置快照模型"""

    id: str                    # 唯一标识符
    name: str                  # 快照名称
    type: ConfigType           # 配置类型
    source_project: str        # 源工程
    ue_version: str            # UE 版本
    created_at: datetime       # 创建时间
    config_data: Dict[str, Any] # 配置数据
```

## 错误处理

### 异常类型

**文件**: `core/exceptions.py`

```python
class UEToolkitException(Exception):
    """基础异常类"""
    pass

class ConfigError(UEToolkitException):
    """配置错误"""
    pass

class ModuleError(UEToolkitException):
    """模块错误"""
    pass

class LicenseError(UEToolkitException):
    """许可证错误"""
    pass

class AssetError(UEToolkitException):
    """资产错误"""
    pass
```

### 错误处理模式

```python
from core.exceptions import ConfigError
from core.logger import get_logger

logger = get_logger(__name__)

try:
    # 操作
    pass
except ConfigError as e:
    logger.error(f"配置错误: {e}", exc_info=True)
    # 显示用户友好的错误消息
except Exception as e:
    logger.error(f"未知错误: {e}", exc_info=True)
    # 显示通用错误消息
```

## 性能监控接口

### PerformanceMonitor API

**文件**: `core/utils/performance_monitor.py`

```python
from core.utils.performance_monitor import PerformanceMonitor

monitor = PerformanceMonitor()

# 开始监控
monitor.start("operation_name")

# 执行操作
# ...

# 结束监控
duration = monitor.end("operation_name")
print(f"操作耗时: {duration}ms")

# 获取统计信息
stats = monitor.get_stats("operation_name")
# 返回: {"count": 10, "total": 1000, "avg": 100, "min": 50, "max": 200}
```

## 线程管理接口

### ThreadManager API

**文件**: `core/utils/thread_manager.py`

```python
from core.utils.thread_manager import ThreadManager

thread_manager = ThreadManager()

# 提交任务
future = thread_manager.submit(
    func=my_function,
    args=(arg1, arg2),
    kwargs={"key": "value"}
)

# 等待结果
result = future.result()

# 批量提交
futures = thread_manager.map(
    func=my_function,
    iterable=[item1, item2, item3]
)

# 等待所有完成
results = [f.result() for f in futures]
```
