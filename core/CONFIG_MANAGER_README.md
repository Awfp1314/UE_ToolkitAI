# ConfigManager 配置管理器

## 概述

`ConfigManager` 是一个基于模板的配置管理系统，位于 `core/config/config_manager.py`。

**重要**: 旧的 `core/config_manager.py` 已废弃并删除。所有配置管理现在通过 Facade 模式实现：

- 全局配置（用户ID、跳过版本等）通过全局配置模板管理
- 模块配置通过各自的配置模板管理
- 本地数据文件（如资产库配置）直接使用 `ConfigUtils` 操作

## 架构原则

✅ **Facade 模式**: `ConfigManager` 作为唯一的配置管理器，通过 `module_name` 参数区分用途  
✅ **按需实例化**: 不创建全局单例，各模块按需创建实例  
✅ **业务逻辑分离**: 业务特定逻辑（如资产验证）回归业务模块  
✅ **直接文件操作**: 本地数据文件使用 `ConfigUtils` 直接读写，不经过 ConfigManager

## 特性

- ✅ 基于 JSON 模板的配置管理
- ✅ 模板和用户配置分离
- ✅ 自动版本升级
- ✅ 配置缓存机制（5分钟）
- ✅ 自动备份和恢复
- ✅ 配置验证
- ✅ 异步保存支持

## 快速开始

### 全局配置使用（用户ID、跳过版本等）

```python
from core.config.config_manager import ConfigManager
from pathlib import Path
import uuid

# 初始化全局配置管理器
global_config_manager = ConfigManager(
    module_name="global",
    template_path=Path("core/config_templates/global_config_template.json")
)

# 获取配置
config = global_config_manager.get_module_config()

# 获取或创建用户ID
user_id = config.get("user_id")
if not user_id:
    user_id = str(uuid.uuid4())
    global_config_manager.update_config_value("user_id", user_id)

# 获取跳过的版本列表
skipped_versions = config.get("skipped_versions", [])

# 添加跳过的版本
if version not in skipped_versions:
    skipped_versions.append(version)
    global_config_manager.update_config_value("skipped_versions", skipped_versions)

print(f"用户ID: {user_id}")
```

### 模块配置使用

```python
from core.config.config_manager import ConfigManager
from pathlib import Path

# 初始化模块配置管理器
module_config_manager = ConfigManager(
    module_name="my_module",
    template_path=Path("modules/my_module/config_template.json")
)

# 获取配置
config = module_config_manager.get_module_config()

# 更新配置值
module_config_manager.update_config_value("settings.theme", "dark")

# 保存配置（带备份）
module_config_manager.save_user_config(config, backup_reason="user_change")
```

### 本地数据文件操作（AssetManager 模式）

对于本地数据文件（如资产库的 `.asset_config/config.json`），直接使用 `ConfigUtils`：

```python
from core.utils.config_utils import ConfigUtils
from pathlib import Path

class AssetManagerLogic:
    def __init__(self):
        # 全局配置（资产库列表、预览工程列表）
        self.config_manager = ConfigManager(
            module_name="asset_manager",
            template_path=Path("modules/asset_manager/config_template.json")
        )

        # 本地配置路径（资产库内的数据文件）
        self.local_config_path: Optional[Path] = None

    def _setup_local_paths(self, asset_library_path: str) -> None:
        """设置本地配置路径"""
        asset_config_dir = Path(asset_library_path) / ".asset_config"
        self.local_config_path = asset_config_dir / "config.json"

    def _load_local_config(self) -> Optional[Dict[str, Any]]:
        """加载本地配置（直接使用 ConfigUtils）"""
        if not self.local_config_path or not self.local_config_path.exists():
            return None
        return ConfigUtils.read_json(self.local_config_path, default=None)

    def _save_local_config(self, config: Dict[str, Any], create_backup: bool = False) -> bool:
        """保存本地配置（直接使用 ConfigUtils）"""
        if not self.local_config_path:
            return False

        # 业务逻辑：验证配置
        if not self._validate_config(config):
            self.logger.error("配置验证失败，拒绝保存")
            return False

        # 业务逻辑：智能备份
        if create_backup and self._should_create_backup():
            self._backup_current_config()

        ConfigUtils.write_json(self.local_config_path, config, create_backup=False)
        return True

    def _validate_config(self, config: Dict[str, Any]) -> bool:
        """业务逻辑：验证配置（资产数量检查）"""
        assets = config.get("assets", [])
        current_asset_count = len(self.assets)

        if current_asset_count > 0 and len(assets) == 0:
            return False
        if current_asset_count > 5 and len(assets) < current_asset_count * 0.5:
            return False
        return True

    def _should_create_backup(self) -> bool:
        """业务逻辑：智能备份策略"""
        # 基于资产数量和时间间隔的备份策略
        # ...
        pass
```

## API 文档

### 核心方法

#### get_module_config(force_reload: bool = False)

获取模块配置（带缓存）。

```python
config = config_manager.get_module_config()
```

#### save_user_config(config: Dict[str, Any], backup_reason: str = "")

保存用户配置（带备份）。

```python
config_manager.save_user_config(config, backup_reason="user_change")
```

#### update_config_value(key: str, value: Any)

更新配置值（支持点号路径）。

```python
config_manager.update_config_value("settings.theme", "dark")
config_manager.update_config_value("user_id", "550e8400-e29b-41d4-a716-446655440000")
```

#### backup_config(reason: str = "")

手动备份配置。

```python
config_manager.backup_config(reason="before_migration")
```

#### restore_from_backup(backup_index: int = 0)

从备份恢复配置。

```python
# 恢复最新备份
config_manager.restore_from_backup(0)

# 恢复第二新的备份
config_manager.restore_from_backup(1)
```

### 业务逻辑实现示例

业务特定逻辑应该在业务模块中实现，而不是在 ConfigManager 中：

```python
class MyBusinessLogic:
    def __init__(self):
        self.config_manager = ConfigManager(
            module_name="my_module",
            template_path=Path("modules/my_module/config_template.json")
        )

    def get_or_create_user_id(self) -> str:
        """业务逻辑：获取或创建用户ID"""
        config = self.config_manager.get_module_config()
        user_id = config.get("user_id")

        if not user_id:
            import uuid
            user_id = str(uuid.uuid4())
            self.config_manager.update_config_value("user_id", user_id)

        return user_id

    def add_skipped_version(self, version: str) -> None:
        """业务逻辑：添加跳过的版本"""
        config = self.config_manager.get_module_config()
        skipped_versions = config.get("skipped_versions", [])

        if version not in skipped_versions:
            skipped_versions.append(version)
            self.config_manager.update_config_value("skipped_versions", skipped_versions)
```

## 使用示例

### 示例1: 更新检测器集成

```python
from core.config.config_manager import ConfigManager
from pathlib import Path
import uuid

class UpdateChecker:
    def __init__(self):
        self.config_manager = ConfigManager(
            module_name="global",
            template_path=Path("core/config_templates/global_config_template.json")
        )
        self.user_id = self._get_or_create_user_id()

    def _get_or_create_user_id(self) -> str:
        """获取或创建用户ID"""
        config = self.config_manager.get_module_config()
        user_id = config.get("user_id")

        if not user_id:
            user_id = str(uuid.uuid4())
            self.config_manager.update_config_value("user_id", user_id)

        return user_id

    def check_for_updates(self, latest_version: str):
        """检查更新"""
        config = self.config_manager.get_module_config()
        skipped_versions = config.get("skipped_versions", [])

        # 检查版本是否已跳过
        if latest_version in skipped_versions:
            return None

        return {"version": latest_version}

    def skip_version(self, version: str):
        """跳过版本"""
        config = self.config_manager.get_module_config()
        skipped_versions = config.get("skipped_versions", [])

        if version not in skipped_versions:
            skipped_versions.append(version)
            self.config_manager.update_config_value("skipped_versions", skipped_versions)
```

### 示例2: AssetManager 配置管理

```python
from core.config.config_manager import ConfigManager
from core.utils.config_utils import ConfigUtils
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import shutil

class AssetManagerLogic:
    def __init__(self):
        # 全局配置管理器（资产库列表、预览工程列表）
        self.config_manager = ConfigManager(
            module_name="asset_manager",
            template_path=Path("modules/asset_manager/config_template.json")
        )

        # 本地配置路径（按需初始化）
        self.local_config_path: Optional[Path] = None
        self.thumbnails_dir: Optional[Path] = None

        # 备份策略状态
        self._last_backup_time: Optional[datetime] = None
        self._last_backup_asset_count: int = 0
        self._backup_interval_seconds: int = 300

    def _setup_local_paths(self, asset_library_path: str) -> None:
        """设置本地配置路径"""
        asset_config_dir = Path(asset_library_path) / ".asset_config"
        self.local_config_path = asset_config_dir / "config.json"
        self.thumbnails_dir = asset_config_dir / "thumbnails"

    def _load_local_config(self) -> Optional[Dict[str, Any]]:
        """加载本地配置"""
        if not self.local_config_path or not self.local_config_path.exists():
            return None
        return ConfigUtils.read_json(self.local_config_path, default=None)

    def _save_local_config(self, config: Dict[str, Any], create_backup: bool = False) -> bool:
        """保存本地配置"""
        if not self.local_config_path:
            return False

        # 业务逻辑：验证配置
        if not self._validate_config(config):
            return False

        # 业务逻辑：智能备份
        if create_backup and self._should_create_backup():
            self._backup_current_config()

        ConfigUtils.write_json(self.local_config_path, config, create_backup=False)
        return True

    def _validate_config(self, config: Dict[str, Any]) -> bool:
        """验证配置完整性"""
        assets = config.get("assets", [])
        current_asset_count = len(self.assets)

        if current_asset_count > 0 and len(assets) == 0:
            return False
        if current_asset_count > 5 and len(assets) < current_asset_count * 0.5:
            return False

        return True

    def _should_create_backup(self) -> bool:
        """判断是否需要创建备份"""
        if self._last_backup_asset_count != len(self.assets):
            return True

        if self._last_backup_time is None:
            return True

        time_since_last_backup = (datetime.now() - self._last_backup_time).total_seconds()
        return time_since_last_backup >= self._backup_interval_seconds

    def _backup_current_config(self) -> bool:
        """备份当前配置"""
        if not self.local_config_path or not self.local_config_path.exists():
            return False

        backup_dir = self.local_config_path.parent / "backup"
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"config_{timestamp}.json"

        shutil.copy2(self.local_config_path, backup_path)
        return True
```

### 示例3: 配置备份和恢复

```python
from core.config.config_manager import ConfigManager
from pathlib import Path

# 初始化配置管理器
config_manager = ConfigManager(
    module_name="my_module",
    template_path=Path("modules/my_module/config_template.json")
)

# 手动备份配置
config_manager.backup_config(reason="before_migration")

# 修改配置
config = config_manager.get_module_config()
config["some_setting"] = "new_value"
config_manager.save_user_config(config, backup_reason="user_change")

# 如果需要恢复
config_manager.restore_from_backup(0)  # 恢复最新备份
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
