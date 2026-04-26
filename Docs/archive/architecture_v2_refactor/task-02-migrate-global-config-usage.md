# Task 2: 迁移全局配置使用代码

## 目标

将所有使用旧 `core/config_manager.py` 的代码迁移到新的 Facade Pattern 架构。

## 背景

项目中约有 10+ 处代码使用了旧的 `core/config_manager.py`，需要迁移到使用全局配置实例 + 业务逻辑的方式。

## 任务清单

### 阶段 1: 初始化全局配置实例

- [ ] 在 `core/bootstrap/app_initializer.py` 或 `core/module_manager.py` 中初始化全局配置实例
- [ ] 创建全局配置管理器单例或工厂方法
- [ ] 验证全局配置实例可以正常加载

### 阶段 2: 迁移代码（试点）

- [ ] 选择 1-2 个非核心模块进行试点迁移
- [ ] 更新导入语句：`from core.config_manager import ConfigManager` → `from core.config.config_manager import ConfigManager`
- [ ] 替换方法调用（参考迁移示例）
- [ ] 运行应用验证功能正常

### 阶段 3: 批量迁移

- [ ] 迁移 `core/module_manager.py`
- [ ] 迁移其他使用旧配置管理器的代码
- [ ] 更新文档示例（`core/CONFIG_MANAGER_README.md`、`AGENTS.md`）

## 迁移示例

### 旧代码（使用 `core/config_manager.py`）

```python
from core.config_manager import ConfigManager

config_manager = ConfigManager()
user_id = config_manager.get_or_create_user_id()
skipped_versions = config_manager.get_skipped_versions()
config_manager.add_skipped_version("1.2.0")
```

### 新代码（使用全局配置实例）

```python
from core.config.config_manager import ConfigManager
from pathlib import Path
import uuid

# 初始化全局配置实例（在启动时执行一次）
global_config_manager = ConfigManager(
    module_name="global",
    template_path=Path("core/config_templates/global_config_template.json")
)

# 获取或创建用户ID（业务逻辑）
config = global_config_manager.get_module_config()
user_id = config.get("user_id")
if not user_id:
    user_id = str(uuid.uuid4())
    global_config_manager.update_config_value("user_id", user_id)

# 获取跳过的版本列表
skipped_versions = config.get("skipped_versions", [])

# 添加跳过的版本（业务逻辑）
if "1.2.0" not in skipped_versions:
    skipped_versions.append("1.2.0")
    global_config_manager.update_config_value("skipped_versions", skipped_versions)
```

## 需要迁移的代码位置

通过 `grep -r "from core.config_manager import ConfigManager"` 搜索发现：

1. `core/module_manager.py`
2. `core/CONFIG_MANAGER_README.md`（文档示例）
3. `AGENTS.md`（文档示例）

## 验收标准

1. 所有使用旧 `core/config_manager.py` 的代码已迁移
2. 应用能够正常启动
3. 全局配置功能正常（用户ID、跳过版本、待上报事件）
4. 无导入错误或运行时错误

## 依赖

- Task 1: 创建全局配置模板

## 预计时间

2-3 小时

## 优先级

🔴 高优先级
