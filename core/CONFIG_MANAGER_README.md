# ConfigManager 配置管理器

## 概述

`ConfigManager` 是一个用于管理应用程序配置的模块，提供了统一的接口来管理用户ID、跳过版本列表、待上报事件队列等配置数据。

## 特性

- ✅ 支持 JSON 和 YAML 两种配置文件格式
- ✅ 自动生成和管理用户UUID
- ✅ 跳过版本列表管理
- ✅ 待上报事件队列管理（支持离线场景）
- ✅ 通用配置键值对存储
- ✅ 配置导出和导入功能
- ✅ 自动持久化到磁盘
- ✅ 完整的日志记录

## 安装依赖

```bash
pip install pyyaml
```

## 快速开始

### 基本使用

```python
from core.config_manager import ConfigManager

# 初始化配置管理器（默认使用JSON格式）
config_mgr = ConfigManager()

# 获取或创建用户ID
user_id = config_mgr.get_or_create_user_id()
print(f"用户ID: {user_id}")
```

### 使用YAML格式

```python
# 使用YAML格式
config_mgr = ConfigManager(format="yaml")
```

### 自定义配置文件路径

```python
# 指定配置文件路径
config_mgr = ConfigManager(config_path="/path/to/config.json")
```

## API 文档

### 初始化

```python
ConfigManager(config_path: Optional[str] = None, format: str = "json")
```

**参数:**

- `config_path`: 配置文件路径，默认为 `~/.ue_toolkit/config.json`
- `format`: 配置文件格式，支持 `"json"` 或 `"yaml"`

### 用户ID管理

#### get_user_id()

获取用户ID，如果不存在或无效则返回 `None`。

```python
user_id = config_mgr.get_user_id()
```

#### set_user_id(user_id: str)

设置用户ID（必须是有效的UUID格式）。

```python
config_mgr.set_user_id("550e8400-e29b-41d4-a716-446655440000")
```

#### get_or_create_user_id()

获取或创建用户ID。如果不存在，自动生成新的UUID。

```python
user_id = config_mgr.get_or_create_user_id()
```

### 跳过版本列表管理

#### get_skipped_versions()

获取所有跳过的版本列表。

```python
skipped = config_mgr.get_skipped_versions()
# 返回: ['v1.2.0', 'v1.3.0']
```

#### add_skipped_version(version: str)

添加要跳过的版本。

```python
config_mgr.add_skipped_version("v1.2.0")
```

#### remove_skipped_version(version: str)

移除跳过的版本。

```python
removed = config_mgr.remove_skipped_version("v1.2.0")
# 返回: True if removed, False if not found
```

#### is_version_skipped(version: str)

检查版本是否已跳过。

```python
if config_mgr.is_version_skipped("v1.2.0"):
    print("该版本已被跳过")
```

#### clear_skipped_versions()

清空所有跳过的版本。

```python
config_mgr.clear_skipped_versions()
```

### 待上报事件队列管理

#### get_pending_events()

获取所有待上报的事件。

```python
events = config_mgr.get_pending_events()
```

#### add_pending_event(event: Dict[str, Any])

添加待上报的事件（自动添加时间戳）。

```python
event = {
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "client_version": "v1.3.0",
    "platform": "Windows"
}
config_mgr.add_pending_event(event)
```

#### clear_pending_events()

清空所有待上报的事件。

```python
count = config_mgr.clear_pending_events()
print(f"清空了 {count} 个事件")
```

#### remove_pending_events(indices: List[int])

移除指定索引的事件。

```python
# 移除第0和第2个事件
removed = config_mgr.remove_pending_events([0, 2])
```

### 通用配置管理

#### get_config_value(key: str, default: Any = None)

获取配置值。

```python
api_url = config_mgr.get_config_value("api_url", "http://localhost:5000")
```

#### set_config_value(key: str, value: Any)

设置配置值。

```python
config_mgr.set_config_value("api_url", "http://example.com")
```

#### delete_config_value(key: str)

删除配置值。

```python
deleted = config_mgr.delete_config_value("api_url")
```

#### get_all_config()

获取所有配置（返回副本）。

```python
all_config = config_mgr.get_all_config()
```

### 配置导入导出

#### export_config(export_path: str, format: Optional[str] = None)

导出配置到文件。

```python
config_mgr.export_config("/path/to/backup.json")
# 或导出为YAML格式
config_mgr.export_config("/path/to/backup.yaml", format="yaml")
```

#### import_config(import_path: str, merge: bool = False)

从文件导入配置。

```python
# 替换当前配置
config_mgr.import_config("/path/to/backup.json")

# 合并配置
config_mgr.import_config("/path/to/backup.json", merge=True)
```

#### reset_config()

重置配置为默认值。

```python
config_mgr.reset_config()
```

## 使用示例

### 示例1: 更新检测器集成

```python
from core.config_manager import ConfigManager

class UpdateChecker:
    def __init__(self):
        self.config_mgr = ConfigManager()
        self.user_id = self.config_mgr.get_or_create_user_id()

    def check_for_updates(self, latest_version):
        # 检查版本是否已跳过
        if self.config_mgr.is_version_skipped(latest_version):
            return None

        # 返回更新信息
        return {"version": latest_version}

    def skip_version(self, version):
        self.config_mgr.add_skipped_version(version)

    def report_launch(self):
        event = {
            "user_id": self.user_id,
            "client_version": "v1.3.0",
            "platform": "Windows"
        }

        try:
            # 尝试上报
            self._send_to_server(event)
        except NetworkError:
            # 网络失败，添加到待上报队列
            self.config_mgr.add_pending_event(event)
```

### 示例2: 批量上报待上报事件

```python
def report_pending_events(config_mgr):
    """批量上报待上报的事件"""
    events = config_mgr.get_pending_events()

    if not events:
        return

    successful_indices = []

    for idx, event in enumerate(events):
        try:
            # 尝试上报
            send_to_server(event)
            successful_indices.append(idx)
        except NetworkError:
            # 上报失败，保留在队列中
            pass

    # 移除成功上报的事件
    if successful_indices:
        config_mgr.remove_pending_events(successful_indices)
```

### 示例3: 配置备份和恢复

```python
from core.config_manager import ConfigManager
from datetime import datetime

# 备份配置
config_mgr = ConfigManager()
backup_path = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
config_mgr.export_config(backup_path)

# 恢复配置
config_mgr.import_config(backup_path)
```

## 配置文件结构

### JSON 格式

```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "skipped_versions": ["v1.2.0", "v1.3.0"],
  "pending_events": [
    {
      "user_id": "550e8400-e29b-41d4-a716-446655440000",
      "client_version": "v1.3.0",
      "platform": "Windows",
      "timestamp": "2024-01-28T10:30:00"
    }
  ],
  "last_check": "2024-01-28T10:30:00",
  "created_at": "2024-01-28T10:00:00",
  "updated_at": "2024-01-28T10:30:00"
}
```

### YAML 格式

```yaml
user_id: 550e8400-e29b-41d4-a716-446655440000
skipped_versions:
  - v1.2.0
  - v1.3.0
pending_events:
  - user_id: 550e8400-e29b-41d4-a716-446655440000
    client_version: v1.3.0
    platform: Windows
    timestamp: "2024-01-28T10:30:00"
last_check: "2024-01-28T10:30:00"
created_at: "2024-01-28T10:00:00"
updated_at: "2024-01-28T10:30:00"
```

## 注意事项

1. **线程安全**: 当前实现不是线程安全的。如果需要在多线程环境中使用，请添加适当的锁机制。

2. **队列大小限制**: 待上报事件队列最多保留100个事件，超过后会自动删除最旧的事件。

3. **配置文件位置**: 默认配置文件位于 `~/.ue_toolkit/config.json`，确保应用程序有读写权限。

4. **UUID验证**: 用户ID必须是有效的UUIDv4格式，否则会抛出 `ValueError`。

5. **自动保存**: 所有修改配置的操作都会自动保存到磁盘。

## 错误处理

```python
from core.config_manager import ConfigManager

try:
    config_mgr = ConfigManager()
    config_mgr.set_user_id("invalid-uuid")  # 会抛出 ValueError
except ValueError as e:
    print(f"无效的UUID格式: {e}")

try:
    config_mgr.import_config("nonexistent.json")  # 会抛出 FileNotFoundError
except FileNotFoundError as e:
    print(f"文件不存在: {e}")
```

## 测试

运行测试脚本验证功能：

```bash
cd UE_TOOKITS_AI_NEW
python test_config_manager.py
```

## 相关文档

- [UpdateChecker 更新检测器](UPDATE_CHECKER_README.md)
- [Logger 日志系统](logger.py)

## 许可证

与主项目相同
