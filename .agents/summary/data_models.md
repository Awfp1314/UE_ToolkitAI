# UE Toolkit 数据模型

## 核心数据模型

### 1. 模块相关模型

#### ModuleInfo

**文件**: `core/module_manager.py`

模块信息数据类，描述一个模块的完整信息。

```python
@dataclass
class ModuleInfo:
    """模块信息"""
    name: str                    # 模块名称（唯一标识符）
    display_name: str            # 显示名称
    version: str                 # 版本号
    description: str             # 描述
    author: str                  # 作者
    dependencies: List[str]      # 依赖的其他模块
    module_path: Path            # 模块目录路径
    manifest_path: Path          # manifest.json 路径
    state: ModuleState           # 模块状态
    instance: Optional[Any]      # 模块实例
```

#### ModuleState

**文件**: `core/module_manager.py`

模块状态枚举。

```python
class ModuleState(Enum):
    """模块状态"""
    DISCOVERED = "discovered"      # 已发现
    LOADED = "loaded"              # 已加载
    INITIALIZED = "initialized"    # 已初始化
    FAILED = "failed"              # 失败
    UNLOADED = "unloaded"          # 已卸载
```

### 2. 配置相关模型

#### ConfigSchema

**类型**: `Dict[str, Any]`

配置 Schema 定义，基于 JSON Schema 标准。

```python
ConfigSchema = {
    "type": "object",
    "properties": {
        "setting_name": {
            "type": "string",           # 类型: string, integer, boolean, array, object
            "description": "设置描述",
            "default": "default_value",  # 默认值
            "enum": ["option1", "option2"],  # 可选值（可选）
            "minimum": 0,                # 最小值（数字类型，可选）
            "maximum": 100,              # 最大值（数字类型，可选）
            "pattern": "^[a-z]+$"        # 正则模式（字符串类型，可选）
        }
    },
    "required": ["setting_name"]     # 必需字段
}
```

#### BackupInfo

**类型**: `Dict[str, Any]`

配置备份信息。

```python
BackupInfo = {
    "path": str,          # 备份文件路径
    "timestamp": str,     # 备份时间戳（ISO 8601 格式）
    "reason": str,        # 备份原因
    "size": int           # 文件大小（字节）
}
```

### 3. 许可证相关模型

#### LicenseStatus

**文件**: `core/security/license_manager.py`

许可证状态数据类。

```python
@dataclass
class LicenseStatus:
    """许可证状态"""
    is_valid: bool                    # 是否有效
    is_trial: bool                    # 是否试用
    days_remaining: int               # 剩余天数（-1 表示永久）
    tier: str                         # 许可证等级: "free", "pro", "enterprise"
    features: List[str]               # 可用功能列表
    machine_id: str                   # 机器 ID
    activation_date: Optional[str]    # 激活日期（ISO 8601 格式）
    expiry_date: Optional[str]        # 过期日期（ISO 8601 格式）
    error: Optional[str]              # 错误信息（如果有）
```

#### LicenseTier

**枚举**: 许可证等级

```python
class LicenseTier:
    FREE = "free"              # 免费版
    PRO = "pro"                # 专业版
    ENTERPRISE = "enterprise"  # 企业版
```

### 4. 资产相关模型

#### Asset

**文件**: `modules/asset_manager/logic/asset_model.py`

资产数据模型。

```python
@dataclass
class Asset:
    """资产数据模型"""
    id: str                           # 唯一标识符（UUID）
    name: str                         # 资产名称
    type: AssetType                   # 资产类型
    package_type: PackageType         # 包装类型
    path: str                         # 资产路径（绝对路径）
    thumbnail: Optional[str]          # 缩略图路径
    description: str                  # 描述
    tags: List[str]                   # 标签列表
    ue_version: str                   # UE 版本（如 "5.4", "4.27"）
    size: int                         # 资产大小（字节）
    created_at: datetime              # 创建时间
    updated_at: datetime              # 更新时间
    last_accessed: Optional[datetime] # 最后访问时间
    metadata: Dict[str, Any]          # 元数据

    # 资产特定字段
    content_path: Optional[str]       # Content 目录路径（CONTENT 类型）
    plugin_name: Optional[str]        # 插件名称（PLUGIN 类型）
    project_name: Optional[str]       # 项目名称（PROJECT 类型）
```

#### AssetType

**文件**: `modules/asset_manager/logic/asset_model.py`

资产类型枚举。

```python
class AssetType(Enum):
    """资产类型"""
    CONTENT = "content"    # 资产包（Content 目录）
    PLUGIN = "plugin"      # 插件
    PROJECT = "project"    # 完整工程
    OTHERS = "others"      # 其他资源（模型、纹理等）
```

#### PackageType

**文件**: `modules/asset_manager/logic/asset_model.py`

包装类型枚举。

```python
class PackageType(Enum):
    """包装类型"""
    ARCHIVE = "archive"    # 压缩包（.zip, .rar, .7z）
    FOLDER = "folder"      # 文件夹

    def display_name(self) -> str:
        """显示名称"""
        return {
            PackageType.ARCHIVE: "压缩包",
            PackageType.FOLDER: "文件夹"
        }[self]

    def wrapper_folder(self) -> str:
        """包装文件夹名称"""
        return {
            PackageType.ARCHIVE: "archives",
            PackageType.FOLDER: "folders"
        }[self]
```

#### AssetFilter

**类型**: `Dict[str, Any]`

资产过滤条件。

```python
AssetFilter = {
    "search_text": str,           # 搜索文本
    "asset_type": Optional[AssetType],  # 资产类型
    "tags": List[str],            # 标签列表（AND 关系）
    "ue_version": Optional[str],  # UE 版本
    "min_size": Optional[int],    # 最小大小（字节）
    "max_size": Optional[int],    # 最大大小（字节）
    "date_from": Optional[datetime],  # 起始日期
    "date_to": Optional[datetime]     # 结束日期
}
```

#### AssetSortMethod

**枚举**: 资产排序方式

```python
class AssetSortMethod(Enum):
    """资产排序方式"""
    NAME_ASC = "name_asc"              # 名称升序
    NAME_DESC = "name_desc"            # 名称降序
    DATE_ASC = "date_asc"              # 日期升序
    DATE_DESC = "date_desc"            # 日期降序
    SIZE_ASC = "size_asc"              # 大小升序
    SIZE_DESC = "size_desc"            # 大小降序
    TYPE_ASC = "type_asc"              # 类型升序
    TYPE_DESC = "type_desc"            # 类型降序
```

### 5. 工程相关模型

#### Project

**文件**: `modules/my_projects/logic/project_model.py`

工程数据模型。

```python
@dataclass
class Project:
    """工程数据模型"""
    name: str                         # 工程名称
    path: str                         # 工程路径（.uproject 文件路径）
    directory: str                    # 工程目录路径
    ue_version: str                   # UE 版本（如 "5.4.0"）
    engine_association: str           # 引擎关联（如 "5.4"）
    is_cpp: bool                      # 是否 C++ 工程
    is_plugin: bool                   # 是否插件工程
    last_opened: Optional[datetime]   # 最后打开时间
    created_at: Optional[datetime]    # 创建时间
    size: int                         # 工程大小（字节）

    # 工程配置
    modules: List[str]                # 模块列表
    plugins: List[str]                # 插件列表

    # 元数据
    description: str                  # 描述
    category: str                     # 分类
    tags: List[str]                   # 标签
```

#### ProjectFilter

**类型**: `Dict[str, Any]`

工程过滤条件。

```python
ProjectFilter = {
    "search_text": str,               # 搜索文本
    "ue_version": Optional[str],      # UE 版本
    "is_cpp": Optional[bool],         # 是否 C++ 工程
    "is_plugin": Optional[bool],      # 是否插件工程
    "tags": List[str]                 # 标签列表
}
```

### 6. 配置工具相关模型

#### ConfigSnapshot

**文件**: `modules/config_tool/logic/config_model.py`

配置快照数据模型。

```python
@dataclass
class ConfigSnapshot:
    """配置快照"""
    id: str                           # 唯一标识符（UUID）
    name: str                         # 快照名称
    type: ConfigType                  # 配置类型
    source_project: str               # 源工程名称
    source_path: str                  # 源工程路径
    ue_version: str                   # UE 版本
    created_at: datetime              # 创建时间
    description: str                  # 描述

    # 配置数据
    config_files: Dict[str, str]      # 配置文件映射 {相对路径: 文件内容}

    # 元数据
    file_count: int                   # 文件数量
    total_size: int                   # 总大小（字节）
```

#### ConfigType

**枚举**: 配置类型

```python
class ConfigType(Enum):
    """配置类型"""
    PROJECT_SETTINGS = "project_settings"      # 项目设置
    USER_PREFERENCES = "user_preferences"      # 用户偏好设置
    EDITOR_SETTINGS = "editor_settings"        # 编辑器设置
    INPUT_BINDINGS = "input_bindings"          # 输入绑定
```

### 7. AI 助手相关模型

#### Message

**类型**: `Dict[str, str]`

聊天消息模型。

```python
Message = {
    "role": str,      # 角色: "user", "assistant", "system", "tool"
    "content": str,   # 消息内容
    "name": Optional[str],      # 名称（tool 角色使用）
    "tool_call_id": Optional[str]  # 工具调用 ID（tool 角色使用）
}
```

#### ToolDefinition

**类型**: `Dict[str, Any]`

工具定义模型。

```python
ToolDefinition = {
    "name": str,              # 工具名称
    "description": str,       # 工具描述
    "parameters": {           # 参数定义（JSON Schema）
        "type": "object",
        "properties": {
            "param_name": {
                "type": str,
                "description": str
            }
        },
        "required": List[str]
    }
}
```

#### ToolCall

**类型**: `Dict[str, Any]`

工具调用模型。

```python
ToolCall = {
    "id": str,                # 工具调用 ID
    "name": str,              # 工具名称
    "arguments": Dict[str, Any]  # 参数字典
}
```

#### ToolResult

**类型**: `Dict[str, Any]`

工具执行结果模型。

```python
ToolResult = {
    "success": bool,          # 是否成功
    "result": Any,            # 执行结果
    "error": Optional[str]    # 错误信息（如果失败）
}
```

#### ConversationHistory

**类型**: `List[Message]`

对话历史模型。

```python
ConversationHistory = [
    {"role": "system", "content": "系统提示"},
    {"role": "user", "content": "用户消息"},
    {"role": "assistant", "content": "助手回复"},
    # ...
]
```

### 8. MCP 相关模型

#### MCPRequest

**类型**: `Dict[str, Any]`

MCP JSON-RPC 请求模型。

```python
MCPRequest = {
    "jsonrpc": "2.0",
    "id": Union[int, str],
    "method": str,
    "params": Dict[str, Any]
}
```

#### MCPResponse

**类型**: `Dict[str, Any]`

MCP JSON-RPC 响应模型。

```python
MCPResponse = {
    "jsonrpc": "2.0",
    "id": Union[int, str],
    "result": Optional[Dict[str, Any]],
    "error": Optional[Dict[str, Any]]
}
```

#### MCPError

**类型**: `Dict[str, Any]`

MCP 错误模型。

```python
MCPError = {
    "code": int,              # 错误码
    "message": str,           # 错误消息
    "data": Optional[Any]     # 额外数据
}
```

#### MCPTool

**类型**: `Dict[str, Any]`

MCP 工具模型。

```python
MCPTool = {
    "name": str,              # 工具名称
    "description": str,       # 工具描述
    "inputSchema": {          # 输入 Schema（JSON Schema）
        "type": "object",
        "properties": Dict[str, Any],
        "required": List[str]
    }
}
```

### 9. 蓝图相关模型

#### BlueprintData

**类型**: `Dict[str, Any]`

蓝图数据模型（从 UE 提取）。

```python
BlueprintData = {
    "name": str,                      # 蓝图名称
    "path": str,                      # 资产路径
    "parent_class": str,              # 父类
    "variables": List[BlueprintVariable],  # 变量列表
    "functions": List[BlueprintFunction],  # 函数列表
    "components": List[BlueprintComponent], # 组件列表
    "event_graph": Optional[Dict],    # 事件图（可选）
    "metadata": Dict[str, Any]        # 元数据
}
```

#### BlueprintVariable

**类型**: `Dict[str, Any]`

蓝图变量模型。

```python
BlueprintVariable = {
    "name": str,                      # 变量名
    "type": str,                      # 类型
    "category": str,                  # 分类
    "default_value": Optional[Any],   # 默认值
    "is_editable": bool,              # 是否可编辑
    "is_blueprint_readonly": bool,    # 是否只读
    "tooltip": str                    # 工具提示
}
```

#### BlueprintFunction

**类型**: `Dict[str, Any]`

蓝图函数模型。

```python
BlueprintFunction = {
    "name": str,                      # 函数名
    "category": str,                  # 分类
    "inputs": List[Dict],             # 输入参数
    "outputs": List[Dict],            # 输出参数
    "is_pure": bool,                  # 是否纯函数
    "is_const": bool,                 # 是否常量
    "description": str                # 描述
}
```

#### BlueprintComponent

**类型**: `Dict[str, Any]`

蓝图组件模型。

```python
BlueprintComponent = {
    "name": str,                      # 组件名
    "class": str,                     # 组件类
    "parent": Optional[str],          # 父组件
    "properties": Dict[str, Any]      # 属性
}
```

### 10. 清理结果模型

#### CleanupResult

**文件**: `core/utils/cleanup_result.py`

清理操作结果模型。

```python
@dataclass
class CleanupResult:
    """清理结果"""
    success: bool                     # 是否成功
    message: str                      # 消息
    warnings: List[str]               # 警告列表
    errors: List[str]                 # 错误列表
    cleaned_items: List[str]          # 已清理项目列表
    failed_items: List[str]           # 清理失败项目列表
```

### 11. 性能监控模型

#### PerformanceMetrics

**类型**: `Dict[str, Any]`

性能指标模型。

```python
PerformanceMetrics = {
    "operation": str,                 # 操作名称
    "count": int,                     # 执行次数
    "total_time": float,              # 总耗时（毫秒）
    "avg_time": float,                # 平均耗时（毫秒）
    "min_time": float,                # 最小耗时（毫秒）
    "max_time": float,                # 最大耗时（毫秒）
    "last_time": float                # 最后一次耗时（毫秒）
}
```

### 12. 更新检查模型

#### UpdateInfo

**类型**: `Dict[str, Any]`

更新信息模型。

```python
UpdateInfo = {
    "version": str,                   # 版本号
    "release_date": str,              # 发布日期（ISO 8601）
    "download_url": str,              # 下载链接
    "changelog": str,                 # 更新日志
    "is_critical": bool,              # 是否关键更新
    "min_version": str                # 最低兼容版本
}
```

## 数据持久化

### 1. JSON 文件

大多数配置和数据使用 JSON 格式存储。

**位置**:

- 用户配置: `%APPDATA%/ue_toolkit/`
- 模块配置: `%APPDATA%/ue_toolkit/modules/`
- 资产数据: 资产库目录下的 `.ue_toolkit/`

**示例**:

```json
{
  "version": "1.0.0",
  "settings": {
    "theme": "dark",
    "language": "zh_CN"
  },
  "modules": {
    "ai_assistant": {
      "enabled": true,
      "config": {}
    }
  }
}
```

### 2. SQLite 数据库（未来计划）

计划使用 SQLite 存储资产索引和搜索数据。

**表结构**:

- `assets`: 资产表
- `tags`: 标签表
- `asset_tags`: 资产标签关联表
- `projects`: 工程表

### 3. 缓存

**位置**: `%APPDATA%/ue_toolkit/cache/`

**类型**:

- 缩略图缓存
- 配置缓存
- 许可证状态缓存

## 数据验证

### JSON Schema 验证

所有配置数据使用 JSON Schema 进行验证。

**示例**:

```python
from core.config.config_validator import ConfigValidator

validator = ConfigValidator(schema)
is_valid = validator.validate(config)
errors = validator.get_errors()
```

### 数据完整性检查

- 必需字段检查
- 类型检查
- 范围检查
- 格式检查（如日期、URL）

## 数据迁移

### 配置迁移

当配置 Schema 版本变化时，自动迁移旧配置。

**迁移策略**:

1. 检测版本差异
2. 应用迁移规则
3. 保留用户设置
4. 添加新字段默认值
5. 删除废弃字段

### 数据库迁移（未来）

使用 Alembic 或类似工具管理数据库 Schema 迁移。

## 数据导入导出

### 配置导出

```python
# 导出配置
config_manager.export_config("config_backup.json")

# 导入配置
config_manager.import_config("config_backup.json")
```

### 资产导出

```python
# 导出资产元数据
asset_manager.export_assets("assets_backup.json")

# 导入资产元数据
asset_manager.import_assets("assets_backup.json")
```

## 数据安全

### 敏感数据加密

API 密钥等敏感数据使用 `cryptography` 库加密存储。

```python
from core.security.secure_config_manager import SecureConfigManager

secure_config = SecureConfigManager()
secure_config.set_secret("api_key", "your_api_key")
api_key = secure_config.get_secret("api_key")
```

### 系统密钥环

使用 `keyring` 库将凭证存储在系统密钥环中。

```python
import keyring

keyring.set_password("ue_toolkit", "api_key", "your_api_key")
api_key = keyring.get_password("ue_toolkit", "api_key")
```
