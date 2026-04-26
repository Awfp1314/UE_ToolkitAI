# Task 3: 重构 AssetManager 配置逻辑

## 目标

将 AssetManager 中的配置逻辑从 `asset_local_config_manager.py` 迁移到 AssetManager 内部，直接使用 `ConfigUtils`。

## 背景

`modules/asset_manager/logic/asset_local_config_manager.py` 包含了大量资产管理器特定的业务逻辑（如资产数量验证、智能备份策略），这些逻辑不属于基础设施，应该回归 AssetManager。

## 任务清单

### 阶段 1: 分析现有逻辑

- [ ] 阅读 `asset_local_config_manager.py` 的所有方法
- [ ] 识别哪些是业务逻辑（需要迁移到 AssetManager）
- [ ] 识别哪些是配置操作（可以直接使用 ConfigUtils）

### 阶段 2: 迁移业务逻辑到 AssetManager

- [ ] 在 `AssetManagerLogic` 中添加本地配置路径管理
- [ ] 迁移 `setup_local_paths()` 方法
- [ ] 迁移 `load_local_config()` 方法（使用 ConfigUtils）
- [ ] 迁移 `save_local_config()` 方法（使用 ConfigUtils）
- [ ] 迁移 `validate_config_before_save()` 方法（业务逻辑）
- [ ] 迁移 `should_create_backup()` 方法（业务逻辑）
- [ ] 迁移 `migrate_global_config()` 方法（业务逻辑）
- [ ] 迁移 `save_full_config()` 方法（业务逻辑）

### 阶段 3: 更新 AssetManager 调用

- [ ] 更新 `AssetManagerLogic.__init__()` 中的配置管理器初始化
- [ ] 移除 `AssetLocalConfigManager` 的导入和实例化
- [ ] 更新所有调用 `asset_local_config_manager` 的代码
- [ ] 验证资产导入、导出、预览功能正常

### 阶段 4: 测试

- [ ] 测试资产库切换功能
- [ ] 测试资产导入功能
- [ ] 测试资产导出功能
- [ ] 测试配置迁移功能（v1.0 → v2.0）
- [ ] 测试配置备份和恢复功能

## 迁移示例

### 旧代码（使用 `asset_local_config_manager.py`）

```python
from modules.asset_manager.logic.asset_local_config_manager import AssetLocalConfigManager

class AssetManagerLogic:
    def __init__(self, config_manager, logger):
        self.local_config_manager = AssetLocalConfigManager(config_manager, logger)

    def switch_asset_library(self, library_path):
        self.local_config_manager.setup_local_paths(library_path)
        config = self.local_config_manager.load_local_config()
        # ...
```

### 新代码（业务逻辑回归 AssetManager）

```python
from core.utils.config_utils import ConfigUtils
from pathlib import Path

class AssetManagerLogic:
    def __init__(self, config_manager, logger):
        self.config_manager = config_manager  # 全局配置管理器
        self.logger = logger
        self.local_config_path = None

    def setup_local_paths(self, asset_library_path: Path):
        """设置本地配置路径"""
        asset_config_dir = asset_library_path / ".asset_config"
        self.local_config_path = asset_config_dir / "config.json"

    def load_local_config(self) -> dict:
        """加载本地配置"""
        if not self.local_config_path or not self.local_config_path.exists():
            return {}
        return ConfigUtils.read_json(self.local_config_path, default={})

    def save_local_config(self, config: dict, create_backup: bool = False):
        """保存本地配置"""
        if not self.local_config_path:
            return

        # 业务逻辑：验证配置
        if not self._validate_config(config):
            self.logger.error("配置验证失败，拒绝保存")
            return

        # 业务逻辑：智能备份
        if create_backup and self._should_create_backup():
            self._backup_current_config()

        ConfigUtils.write_json(self.local_config_path, config, create_backup=False)

    def _validate_config(self, config: dict) -> bool:
        """业务逻辑：验证配置"""
        # 资产数量检查等业务逻辑
        pass

    def _should_create_backup(self) -> bool:
        """业务逻辑：智能备份策略"""
        # 基于资产数量和时间间隔的备份策略
        pass
```

## 验收标准

1. `AssetManagerLogic` 不再依赖 `AssetLocalConfigManager`
2. 所有资产管理器功能正常（导入、导出、预览）
3. 配置迁移功能正常（v1.0 → v2.0）
4. 配置备份和恢复功能正常
5. 无运行时错误或数据丢失

## 依赖

- Task 2: 迁移全局配置使用代码

## 预计时间

3-4 小时

## 优先级

🟡 中优先级

## 风险

⚠️ 高风险：涉及资产数据操作，需要仔细测试以防止数据丢失
