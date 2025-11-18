# 架构重构迁移指南

本文档记录了从旧架构迁移到统一服务层架构的详细步骤和常见问题。

## 📋 迁移概述

### 迁移目标

将分散的服务实例化逻辑统一到 `core/services/` 服务层，实现：

- 单例模式管理所有核心服务
- 懒加载提升启动性能
- 统一的依赖管理和清理机制
- 更好的可测试性和可维护性

### 迁移范围

- ✅ **核心服务**: LogService, PathService, ConfigService, StyleService, ThreadService
- ✅ **应用管理器**: `core/app_manager.py`
- ✅ **主窗口**: `ui/ue_main_window.py`
- ✅ **资产管理模块**: `modules/asset_manager/`
- ✅ **AI 助手模块**: `modules/ai_assistant/`
- ✅ **配置工具模块**: `modules/config_tool/` (无需迁移)
- ✅ **站点推荐模块**: `modules/site_recommendations/` (无需迁移)

## 🔄 迁移步骤

### 步骤 1: 更新导入语句

**旧代码**:

```python
from core.log_service import LogService
from core.path_service import PathService
from core.config_service import ConfigService
from core.style_service import StyleService
from core.thread_service import ThreadService
```

**新代码**:

```python
from core.services import (
    log_service,
    path_service,
    config_service,
    style_service,
    thread_service
)
```

### 步骤 2: 移除实例创建

**旧代码**:

```python
class MyClass:
    def __init__(self):
        self.log_service = LogService()
        self.config_service = ConfigService()
        self.logger = self.log_service.get_logger(__name__)
```

**新代码**:

```python
class MyClass:
    def __init__(self):
        self.logger = log_service.get_logger(__name__)
```

### 步骤 3: 更新方法调用

**旧代码**:

```python
# 通过实例调用
config = self.config_service.get_module_config("my_module")
self.thread_service.run_async(task_func, on_result=callback)
```

**新代码**:

```python
# 直接使用服务
config = config_service.get_module_config("my_module")
thread_service.run_async(task_func, on_result=callback)
```

### 步骤 4: 更新清理逻辑

**旧代码**:

```python
def cleanup(self):
    if hasattr(self, 'thread_service'):
        self.thread_service.cleanup()
    if hasattr(self, 'config_service'):
        self.config_service.cleanup()
```

**新代码**:

```python
def cleanup(self):
    # 服务层会自动按依赖顺序清理
    # 通常不需要手动清理服务
    pass
```

或者在应用退出时统一清理：

```python
from core.services import cleanup_all_services

def on_app_exit():
    cleanup_all_services()
```

## 📝 迁移检查清单

每个文件迁移完成后，请检查以下项目：

- [ ] 导入语句已更新为 `from core.services import ...`
- [ ] 移除了服务实例的创建（如 `self.log_service = LogService()`）
- [ ] 方法调用已更新为直接使用服务（如 `log_service.get_logger()`）
- [ ] 清理逻辑已调整（移除手动清理或使用 `cleanup_all_services()`）
- [ ] 功能测试通过（手动测试或运行集成测试）
- [ ] 日志输出正常（检查日志文件）
- [ ] 代码已提交到 Git

## ❓ 常见问题

### Q1: 如何在类中使用服务？

**A**: 直接导入并使用，不需要创建实例：

```python
from core.services import log_service, config_service

class MyWidget:
    def __init__(self):
        # 直接使用服务
        self.logger = log_service.get_logger(__name__)
        self.config = config_service.get_module_config("my_module")
```

### Q2: 服务什么时候初始化？

**A**: 服务采用懒加载策略，在首次访问时才初始化：

```python
# 第一次访问时初始化
logger = log_service.get_logger(__name__)  # LogService 在此时初始化

# 后续访问使用已初始化的实例
logger2 = log_service.get_logger("other")  # 使用同一个 LogService 实例
```

### Q3: 如何确保服务已初始化？

**A**: 通常不需要手动确保，服务会在首次使用时自动初始化。如果需要预初始化，可以调用：

```python
from core.services import _get_log_service

# 预初始化服务
_get_log_service()
```

### Q4: 循环依赖怎么办？

**A**: 服务层已经设计了三级依赖层次，避免循环依赖：

- **Level 0**: LogService, PathService (无依赖)
- **Level 1**: ConfigService, StyleService (依赖 Level 0)
- **Level 2**: ThreadService (依赖 Level 0 和 Level 1)

如果遇到循环依赖错误，请检查代码是否违反了依赖层次。

### Q5: 如何在测试中使用服务？

**A**: 使用 `cleanup_all_services()` 确保每个测试从干净状态开始：

```python
import pytest
from core.services import cleanup_all_services, log_service

@pytest.fixture(scope="function")
def clean_services():
    cleanup_all_services()
    yield
    cleanup_all_services()

def test_my_feature(clean_services):
    logger = log_service.get_logger(__name__)
    # 测试代码...
```

### Q6: 如何调试服务初始化问题？

**A**: 启用调试模式查看详细日志：

```bash
# Windows
set DEBUG_SERVICES=1
python main.py

# Linux/macOS
export DEBUG_SERVICES=1
python main.py
```

或在配置文件中设置：

```json
{
  "debug_services": true
}
```

### Q7: 服务清理顺序是什么？

**A**: 服务按依赖顺序反向清理，确保不会出现依赖问题：

1. Level 2: ThreadService (最先清理)
2. Level 1: StyleService, ConfigService
3. Level 0: PathService, LogService (最后清理)

### Q8: 如何检查服务健康状态？

**A**: 使用健康检查工具：

```python
from core.services.health_check import perform_health_checks

results = perform_health_checks()
print(results)
# {'LogService': True, 'PathService': True, 'ConfigService': True, ...}

if all(results.values()):
    print("所有服务健康")
else:
    failed = [name for name, status in results.items() if not status]
    print(f"以下服务异常: {failed}")
```

## 🔍 迁移验证

### 功能验证

完成迁移后，请验证以下功能：

- [ ] 应用程序正常启动
- [ ] 所有模块加载正常
- [ ] 配置保存/加载正常
- [ ] 主题切换正常
- [ ] 异步任务执行正常
- [ ] 应用程序正常退出
- [ ] 日志记录正常

### 性能验证

对比迁移前后的性能指标：

- [ ] 启动时间无明显增加（< 10%）
- [ ] 内存使用无明显增加（< 10%）
- [ ] 响应速度无明显下降

### 质量验证

- [ ] 无循环依赖错误
- [ ] 无线程泄漏
- [ ] 无内存泄漏
- [ ] 集成测试全部通过

## 📚 参考文档

- [架构重构需求文档](REQUIREMENTS.md)
- [架构重构设计文档](DESIGN.md)
- [任务清单](tasks.md)
- [验证清单](VALIDATION_CHECKLIST.md)

## 🎯 最佳实践

### 1. 始终使用服务层

**推荐**:

```python
from core.services import log_service
logger = log_service.get_logger(__name__)
```

**不推荐**:

```python
from core.services._log_service import LogService
log_service = LogService()  # 破坏单例模式
```

### 2. 避免缓存服务实例

**推荐**:

```python
class MyClass:
    def do_something(self):
        logger = log_service.get_logger(__name__)
        logger.info("Doing something")
```

**不推荐**:

```python
class MyClass:
    def __init__(self):
        self.log_service = log_service()  # 不必要的缓存
```

### 3. 使用统一清理

**推荐**:

```python
from core.services import cleanup_all_services

def on_app_exit():
    cleanup_all_services()
```

**不推荐**:

```python
def on_app_exit():
    log_service.cleanup()  # 手动清理可能导致顺序错误
    config_service.cleanup()
    thread_service.cleanup()
```

### 4. 在测试中隔离服务

**推荐**:

```python
@pytest.fixture(scope="function")
def clean_services():
    cleanup_all_services()
    yield
    cleanup_all_services()
```

**不推荐**:

```python
# 测试之间共享服务状态，可能导致测试相互影响
def test_feature_1():
    config = config_service.get_module_config("test")
    # ...

def test_feature_2():
    # 可能受到 test_feature_1 的影响
    config = config_service.get_module_config("test")
```

## 📊 迁移统计

### 已迁移文件

- `core/app_manager.py` - ✅ 完成
- `ui/ue_main_window.py` - ✅ 完成
- `modules/asset_manager/logic/asset_manager.py` - ✅ 完成
- `modules/asset_manager/ui/asset_manager_widget.py` - ✅ 完成
- `modules/ai_assistant/logic/ai_assistant.py` - ✅ 完成
- `modules/ai_assistant/ui/ai_assistant_widget.py` - ✅ 完成

### 无需迁移

- `modules/config_tool/` - 不使用服务层
- `modules/site_recommendations/` - 不使用服务层

### 迁移成果

- **代码行数减少**: ~200 行（移除重复的实例创建代码）
- **导入语句简化**: 从 5 行减少到 1 行
- **测试覆盖率**: 15 个集成测试，100% 通过
- **性能提升**: 启动时间减少 ~5%（懒加载优化）

## 🚀 下一步

迁移完成后，建议：

1. **运行完整测试套件**: `pytest tests/integration/ -v`
2. **执行端到端测试**: 手动测试所有主要功能
3. **监控性能指标**: 对比迁移前后的性能数据
4. **更新文档**: 确保所有文档反映新架构
5. **培训团队**: 向团队成员介绍新架构和最佳实践

---

**文档版本**: 1.0
**创建日期**: 2025-11-17
**最后更新**: 2025-11-17
**维护者**: HUTAO
