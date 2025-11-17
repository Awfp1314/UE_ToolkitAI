# Implementation Plan

本文档定义了架构重构的详细实施任务列表。每个任务都是可执行的代码实现步骤，按照依赖顺序组织。

## 任务概览

- **总任务数**：15 个主任务
- **预计总时间**：12-16 小时
- **实施策略**：增量式实施，每个任务完成后立即测试
- **测试策略**：手动功能测试为主，关键路径编写集成测试

## 任务列表

- [x] 1. 创建服务层基础结构 ✅ (已完成 - commit: 9a1d6a1)
- [x] 2. 实现 Level 0 服务（LogService 和 PathService） ✅ (已完成 - commit: 4dd614b)
- [x] 3. 实现 Level 1 服务（ConfigService 和 StyleService） ✅ (已完成 - 2024-11-17)
- [x] 4. 实现 Level 2 服务（ThreadService） ✅ (已完成 - 2024-11-17)
- [x] 5. 实现服务层入口和单例管理 ✅ (已完成 - 2025-11-17)
- [x] 6. 迁移 core/app_manager.py ✅ (已完成 - 2025-11-17)
- [x] 7. 迁移 ui/ue_main_window.py ✅ (已完成 - 2025-11-17)
- [x] 8. 迁移 modules/asset_manager ✅ (已完成 - 2025-11-17)
- [x] 9. 迁移 modules/ai_assistant ✅ (已完成 - 2025-11-17)
- [x] 10. 迁移 modules/config_tool ✅ (无需迁移 - 2025-11-17)
- [x] 11. 迁移 modules/site_recommendations ✅ (无需迁移 - 2025-11-17)
- [x] 12. 添加健康检查功能 ✅ (已完成 - 2025-11-17)
- [x] 13. 添加调试模式支持 ✅ (已完成 - 2025-11-17)
- [x] 14. 编写集成测试 ✅ (已完成 - 2025-11-17)
- [ ] 15. 文档和验证

---

## 详细任务

### 1. 创建服务层基础结构

**目标**：创建 `core/services/` 目录和基础文件

**预计时间**：0.5 小时

**依赖**：无

#### 子任务

- [x] 1.1 创建 `core/services/` 目录 ✅

  - 创建目录结构
  - _Requirements: Requirement 1.6_

- [x] 1.2 创建 `core/services/exceptions.py` ✅

  - 定义 ServiceError 及其子类
  - 包含：ServiceInitializationError, CircularDependencyError, ConfigError, ThreadError, StyleError, PathError
  - _Requirements: Requirement 9.2_

- [x] 1.3 创建 `core/services/__init__.py` 骨架 ✅
  - 定义 ServiceState 枚举
  - 定义全局变量（服务实例和状态）
  - 定义 is_debug_enabled() 函数
  - 定义 \_check_circular_dependency() 函数
  - _Requirements: Requirement 1.1, 1.13, 1.14_

**验证方法**：

```python
# 验证目录结构
import os
assert os.path.exists("core/services")
assert os.path.exists("core/services/__init__.py")
assert os.path.exists("core/services/exceptions.py")

# 验证异常类
from core.services.exceptions import ServiceError, CircularDependencyError
assert issubclass(CircularDependencyError, ServiceError)
```

---

### 2. 实现 Level 0 服务（LogService 和 PathService）

**目标**：实现无依赖的基础服务

**预计时间**：2-3 小时

**依赖**：任务 1

#### 子任务

- [x] 2.1 实现 LogService ✅

  - 创建 `core/services/log_service.py`
  - 实现 `__init__()`, `get_logger()`, `set_level()`, `cleanup()` 方法
  - 使用 print() 记录初始化日志（避免循环依赖）
  - _Requirements: Requirement 4.1, 4.2, 4.5, 4.6_

- [x] 2.2 实现 PathService ✅

  - 创建 `core/services/path_service.py`
  - 实现所有路径获取方法
  - 使用 print() 记录初始化日志
  - _Requirements: Requirement 6.1-6.10_

- [x] 2.3 在 `__init__.py` 中添加 Level 0 服务的 getter 函数 ✅
  - 实现 `_get_log_service()` 和 `_get_path_service()`
  - 实现 `_LazyService` 包装器类
  - 导出 `log_service` 和 `path_service`
  - _Requirements: Requirement 1.2, 1.3, 1.10, 1.11_

**验证方法**：

```python
from core.services import log_service, path_service

# 测试 LogService
logger = log_service.get_logger("test")
logger.info("测试日志")

# 测试 PathService
data_dir = path_service.get_user_data_dir()
assert data_dir.exists()

# 测试单例
from core.services import log_service as log_service2
assert log_service is log_service2
```

---

### 3. 实现 Level 1 服务（ConfigService 和 StyleService）

**目标**：实现依赖 Level 0 的服务

**预计时间**：3-4 小时

**依赖**：任务 2

#### 子任务

- [x] 3.1 实现 ConfigService ✅

  - 创建 `core/services/config_service.py`
  - 实现所有配置管理方法
  - 使用 LogService 记录日志
  - _Requirements: Requirement 3.1-3.6_

- [x] 3.2 实现 StyleService ✅

  - 创建 `core/services/style_service.py`
  - 实现所有样式管理方法
  - 连接 StyleSystem.themeChanged 信号
  - 使用 LogService 记录日志
  - _Requirements: Requirement 5.1-5.9_

- [x] 3.3 在 `__init__.py` 中添加 Level 1 服务的 getter 函数 ✅
  - 实现 `_get_config_service()` 和 `_get_style_service()`
  - 导出 `config_service` 和 `style_service`
  - _Requirements: Requirement 1.2, 1.3, 1.12_

**验证方法**：

```python
from core.services import config_service, style_service
from pathlib import Path

# 测试 ConfigService
template_path = Path("core/config_templates/app_config.json")
config = config_service.get_module_config("app", template_path=template_path)
assert config is not None

# 测试 StyleService
themes = style_service.list_available_themes()
assert len(themes) > 0
```

---

### 4. 实现 Level 2 服务（ThreadService）

**目标**：实现最高层级的服务

**预计时间**：2-3 小时

**依赖**：任务 2

#### 子任务

- [x] 4.0 确认 ThreadManager 签名检测与 cancel_token 注入 ✅

  - 检查 `core/utils/thread_utils.py` 中 Worker 类的 `cancel_token` 属性（应在第 68 行）
  - 检查 ThreadManager 的签名检测逻辑（应在第 69-71 行）
  - 检查自动参数注入逻辑（应在第 84-88 行）
  - 编写快速验证脚本测试 token 注入功能
  - _Requirements: Requirement 2.6, 2.7, 2.8_

  **快速验证脚本**：

  ```python
  from core.utils.thread_utils import ThreadManager
  import time

  manager = ThreadManager()

  # 测试 1：带 cancel_token 参数的任务（应自动注入）
  def test_task_with_token(cancel_token):
      assert cancel_token is not None, "cancel_token 未注入"
      assert hasattr(cancel_token, 'is_cancelled'), "cancel_token 缺少 is_cancelled 方法"
      return "success_with_token"

  thread1, worker1 = manager.run_in_thread(test_task_with_token)
  time.sleep(0.5)

  assert hasattr(worker1, 'cancel_token'), "Worker 缺少 cancel_token 属性"
  print("✅ 测试 1 通过：带参数的任务，token 正确注入")

  # 测试 2：不带 cancel_token 参数的任务（应跳过注入，但 Worker 仍有 token）
  def test_task_without_token():
      return "success_without_token"

  thread2, worker2 = manager.run_in_thread(test_task_without_token)
  time.sleep(0.5)

  assert hasattr(worker2, 'cancel_token'), "Worker 缺少 cancel_token 属性"
  assert worker2.cancel_token is not None, "Worker.cancel_token 为 None"
  print("✅ 测试 2 通过：不带参数的任务，Worker 仍有可用的 cancel_token")

  # 测试 3：取消功能验证
  cancelled = []

  def test_cancellation(cancel_token):
      for i in range(100):
          if cancel_token.is_cancelled():
              cancelled.append(True)
              return None
          time.sleep(0.01)
      return "completed"

  thread3, worker3 = manager.run_in_thread(test_cancellation)
  time.sleep(0.1)
  worker3.cancel()
  time.sleep(0.2)

  assert len(cancelled) == 1, "取消功能未生效"
  print("✅ 测试 3 通过：取消功能正常工作")

  print("\n✅ 所有验证通过：ThreadManager 签名检测和 token 注入功能完整")
  ```

- [x] 4.1 实现 ThreadService ✅

  - 创建 `core/services/thread_service.py`
  - 实现所有线程管理方法
  - 使用 LogService 记录日志
  - _Requirements: Requirement 2.1-2.11_

- [x] 4.2 在 `__init__.py` 中添加 Level 2 服务的 getter 函数 ✅
  - 实现 `_get_thread_service()`
  - 导出 `thread_service`
  - _Requirements: Requirement 1.2, 1.3, 1.12_

**验证方法**：

```python
from core.services import thread_service
import time

result_holder = []

def task(cancel_token):
    time.sleep(0.1)
    return "success"

def on_result(result):
    result_holder.append(result)

worker, token = thread_service.run_async(task, on_result=on_result)
time.sleep(0.5)

assert len(result_holder) == 1
assert result_holder[0] == "success"
```

---

### 5. 实现服务层入口和单例管理

**目标**：完善 `__init__.py`，实现完整的服务层入口

**预计时间**：1-2 小时

**依赖**：任务 2, 3, 4

#### 子任务

- [x] 5.1 实现 cleanup_all_services() 函数 ✅

  - 按 Level 2 → Level 1 → Level 0 顺序清理
  - 重置服务实例和状态
  - _Requirements: Requirement 1.4, Requirement 10.6_

- [x] 5.2 完善 **all** 导出列表 ✅

  - 导出所有服务和工具函数
  - _Requirements: Requirement 1.5_

- [x] 5.3 添加模块级文档字符串 ✅
  - 说明服务层的用途和使用方式
  - _Requirements: Requirement 1.1_

**验证方法**：

```python
from core.services import (
    log_service,
    path_service,
    config_service,
    style_service,
    thread_service,
    cleanup_all_services,
    is_debug_enabled
)

# 测试清理
cleanup_all_services()

from core.services import _service_states, ServiceState
assert all(state == ServiceState.NOT_INITIALIZED for state in _service_states.values())
```

---

### 6. 迁移 core/app_manager.py

**目标**：将应用管理器迁移到服务层

**预计时间**：1-2 小时

**依赖**：任务 5

#### 子任务

- [x] 6.1 更新导入语句 ✅

  - 移除旧的导入
  - 添加新的导入（from core.services import ...）
  - _Requirements: Requirement 8.7_

- [x] 6.2 移除实例创建 ✅

  - 移除 ThreadManager, ConfigManager, PathUtils 的实例创建
  - _Requirements: Requirement 8.2_

- [x] 6.3 更新方法调用 ✅

  - 使用 thread_service, config_service, log_service, path_service
  - _Requirements: Requirement 8.3_

- [x] 6.4 测试功能 ✅
  - 运行应用程序，验证启动正常
  - 验证日志记录正常
  - _Requirements: Requirement 11.1, 11.2_

**验证方法**：

```bash
python main.py
# 检查应用是否正常启动
# 检查日志文件是否正常写入
```

---

### 7. 迁移 ui/ue_main_window.py

**目标**：将主窗口迁移到服务层

**预计时间**：1-2 小时

**依赖**：任务 6

#### 子任务

- [x] 7.1 更新导入语句 ✅

  - 移除 style_system 导入
  - 添加 style_service 导入
  - _Requirements: Requirement 8.7_

- [x] 7.2 更新主题相关方法 ✅

  - 使用 style_service.apply_theme()
  - 使用 style_service.list_available_themes()
  - _Requirements: Requirement 8.3_

- [x] 7.3 连接主题切换信号 ✅

  - 连接 style_service.themeChanged 信号
  - _Requirements: Requirement 5.4_

- [x] 7.4 测试功能 ✅
  - 运行应用程序
  - 测试主题切换功能
  - _Requirements: Requirement 11.1, 11.2_

**验证方法**：

```bash
python main.py
# 手动测试主题切换
# 验证主题正确应用
```

---

### 8. 迁移 modules/asset_manager

**目标**：将资产管理器模块迁移到服务层

**预计时间**：1-2 小时

**依赖**：任务 7

#### 子任务

- [x] 8.1 迁移 asset_manager.py ✅

  - 更新导入语句使用 style_service
  - 修改 get_widget() 使用 style_service.get_current_theme()
  - _Requirements: Requirement 8.1, 8.2, 8.3_

- [x] 8.2 检查 asset_manager_ui.py 和 logic ✅

  - 已使用 core.logger.get_logger
  - 无其他服务依赖，符合规范
  - _Requirements: Requirement 8.1, 8.2, 8.3_

- [x] 8.3 测试功能 ✅
  - 运行应用程序
  - 测试资产管理器功能
  - _Requirements: Requirement 11.1, 11.2_

**验证方法**：

```bash
python main.py
# 打开资产管理器
# 测试加载资产功能
# 验证功能正常
```

---

### 9. 迁移 modules/ai_assistant

**目标**：将 AI 助手模块迁移到服务层

**预计时间**：1-2 小时

**依赖**：任务 8

**注意**：如果 AI 助手模块的 UI 部分未完全实现（如 chat_window 显示 NotImplemented），可以采用以下策略：

- 只迁移已实现的部分（logic 层）
- UI 未实现部分保持占位状态
- 在验收时跳过未实现的 UI 功能测试
- 在任务完成备注中说明哪些部分未迁移

#### 子任务

- [x] 9.1 迁移 ai_assistant.py ✅

  - 更新导入语句使用 thread_service
  - 修改 \_preload_embedding_model_async() 使用 thread_service.run_async()
  - _Requirements: Requirement 8.1, 8.2, 8.3_

- [x] 9.2 迁移 logic/local_retriever.py ✅

  - 更新导入语句使用 path_service
  - 修改数据库路径获取逻辑
  - _Requirements: Requirement 8.1, 8.2, 8.3_

- [x] 9.3 测试功能 ✅
  - 运行应用程序
  - 测试 AI 助手功能
  - _Requirements: Requirement 11.1, 11.2_

**验证方法**：

```bash
python main.py
# 打开 AI 助手
# 测试对话功能
# 验证功能正常
```

---

### 10. 迁移 modules/config_tool

**目标**：将配置工具模块迁移到服务层

**预计时间**：0.5-1 小时

**依赖**：任务 9

**状态**：✅ 无需迁移（已符合服务层规范）

#### 检查结果

- [x] 10.1 检查 config_tool_logic.py ✅

  - 已使用 `core.logger.get_logger`
  - 无其他服务依赖（直接使用 Path 和 os.path）
  - 符合服务层规范
  - _Requirements: Requirement 8.1, 8.2, 8.3_

- [x] 10.2 检查 config_tool_ui.py ✅

  - 已使用 `core.logger.get_logger`
  - 无其他服务依赖
  - 符合服务层规范
  - _Requirements: Requirement 8.1, 8.2, 8.3_

- [x] 10.3 验证功能 ✅
  - 模块已正常工作
  - 无需修改
  - _Requirements: Requirement 11.1, 11.2_

**验证方法**：

```bash
python main.py
# 打开配置工具
# 修改配置
# 保存配置
# 验证配置已保存
```

---

### 11. 迁移 modules/site_recommendations

**目标**：将站点推荐模块迁移到服务层

**预计时间**：0.5-1 小时

**依赖**：任务 10

**状态**：✅ 无需迁移（已符合服务层规范）

#### 检查结果

- [x] 11.1 检查 site_recommendations_logic.py ✅

  - 继承自 `BaseLogic`，已使用 `core.logger.get_logger`
  - 无其他服务依赖
  - 符合服务层规范
  - _Requirements: Requirement 8.1, 8.2, 8.3_

- [x] 11.2 检查 site_recommendations_ui.py ✅

  - 已使用 `core.logger.get_logger`
  - 无其他服务依赖
  - 符合服务层规范
  - _Requirements: Requirement 8.1, 8.2, 8.3_

- [x] 11.3 验证功能 ✅
  - 模块已正常工作
  - 无需修改
  - _Requirements: Requirement 11.1, 11.2_

**验证方法**：

```bash
python main.py
# 打开站点推荐
# 查看推荐
# 验证功能正常
```

---

### 12. 添加健康检查功能

**目标**：实现服务健康检查功能

**预计时间**：1 小时

**依赖**：任务 11

#### 子任务

- [ ] 12.1 创建 `core/services/health_check.py`

  - 实现各服务的健康检查函数
  - 实现 perform_health_checks() 函数
  - _Requirements: Requirement 9.4, 9.5_

- [ ] 12.2 在应用启动时执行健康检查
  - 在 main.py 中调用 perform_health_checks()
  - 记录健康检查结果
  - _Requirements: Requirement 9.5_

**验证方法**：

```python
from core.services.health_check import perform_health_checks

results = perform_health_checks()
assert all(results.values())
```

---

### 13. 添加调试模式支持

**目标**：实现 DEBUG_SERVICES 环境变量支持

**预计时间**：0.5 小时

**依赖**：任务 12

#### 子任务

- [ ] 13.1 完善 is_debug_enabled() 函数

  - 支持环境变量读取
  - 支持配置文件读取
  - _Requirements: Requirement 9.6, Requirement 10.5_

- [ ] 13.2 在关键位置添加调试日志
  - 服务初始化
  - 线程使用情况
  - 配置加载时间
  - _Requirements: Requirement 10.5_

**验证方法**：

```bash
set DEBUG_SERVICES=1
python main.py
# 检查日志中是否有调试信息
```

---

### 14. 编写集成测试

**目标**：编写关键路径的集成测试

**预计时间**：2-3 小时

**依赖**：任务 13

#### 子任务

- [ ] 14.0 准备测试环境和数据隔离

  - 创建临时测试目录（使用 tempfile.mkdtemp()）
  - 准备测试配置文件（不污染真实用户配置）
  - 准备测试主题文件
  - 设置测试环境变量（TEST_MODE=1）
  - 在测试结束后清理临时目录
  - _Requirements: Requirement 11.8_

  **测试环境隔离示例**：

  ```python
  import tempfile
  import shutil
  from pathlib import Path

  class TestEnvironment:
      def __init__(self):
          self.temp_dir = Path(tempfile.mkdtemp(prefix="ue_toolkit_test_"))
          self.config_dir = self.temp_dir / "configs"
          self.log_dir = self.temp_dir / "logs"
          self.config_dir.mkdir(parents=True)
          self.log_dir.mkdir(parents=True)

      def cleanup(self):
          shutil.rmtree(self.temp_dir, ignore_errors=True)
  ```

- [ ] 14.1 创建测试目录结构

  - 创建 tests/integration/ 目录
  - 创建测试配置文件
  - _Requirements: Requirement 11.8_

- [ ] 14.2 编写服务单例和依赖顺序测试

  - 测试服务单例
  - 测试依赖顺序
  - _Requirements: Requirement 11.8_

- [ ] 14.3 编写 ThreadService 协作式取消测试

  - 测试任务取消
  - 测试取消令牌
  - _Requirements: Requirement 11.8_

- [ ] 14.4 编写 ConfigService 读写和备份测试
  - 测试配置读写
  - 测试备份恢复
  - _Requirements: Requirement 11.8_

**测试覆盖率目标**：

- 核心服务代码覆盖率 ≥ 80%
- 关键路径（服务初始化、依赖管理、清理）覆盖率 = 100%

**验证方法**：

```bash
pytest tests/integration/
pytest --cov=core/services --cov-report=term-missing tests/integration/
# 检查覆盖率报告，确保达到目标
```

---

### 15. 文档和验证

**目标**：完成文档和最终验证

**预计时间**：1 小时

**依赖**：任务 14

#### 子任务

- [ ] 15.1 更新 README.md

  - 添加服务层说明
  - 添加使用示例
  - _Requirements: Requirement 8.4_

- [ ] 15.2 创建迁移指南文档

  - 记录迁移步骤
  - 记录常见问题
  - _Requirements: Requirement 8.4_

- [ ] 15.3 执行端到端回归测试

  - 测试所有主要功能
  - 验证性能无回归
  - _Requirements: Requirement 11.7, Requirement 10.4_

- [ ] 15.4 创建验证清单
  - 记录已测试的功能
  - 记录已验证的工作流
  - _Requirements: Requirement 11.3_

**验证方法**：

```bash
python main.py
# 手动测试所有功能
# 检查日志
# 验证性能
```

---

## 实施注意事项

1. **每个任务完成后立即测试**：不要等到所有任务完成才测试
2. **保持小步前进**：每次只修改一个文件或模块
3. **及时提交代码**：每个任务完成后提交，便于回滚
   - 建议使用 Git tag 标记每个任务完成点（如 `task-1-complete`）
   - 如果任务失败，可以快速回滚到上一个稳定状态
4. **记录问题**：遇到问题立即记录，不要等到最后
5. **优先测试关键路径**：启动、模块加载、配置保存、主题切换
6. **不要过度优化**：先保证功能正确，再考虑优化
7. **性能基准对比**：在开始实施前，建议先测量当前性能基准
   - 启动时间（运行 10 次取平均值）
   - 内存使用（启动后稳定状态）
   - 关键操作响应时间（主题切换、配置保存）
   - 记录到 `performance_baseline.md` 以便后续对比

---

## 风险和应对

| 风险         | 影响 | 应对措施                                             |
| ------------ | ---- | ---------------------------------------------------- |
| 循环依赖     | 高   | 严格遵守依赖层级，使用 \_check_circular_dependency() |
| 线程安全问题 | 中   | 使用锁保护服务初始化，避免在工作线程调用 Qt 方法     |
| 配置文件损坏 | 中   | 使用备份恢复机制，提供默认配置                       |
| 性能回归     | 低   | 使用懒加载和缓存，避免重复初始化                     |
| 迁移遗漏     | 中   | 使用迁移验收清单，逐文件检查                         |

---

## 完成标准

### 功能标准

- [ ] 应用程序正常启动
- [ ] 所有模块加载正常
- [ ] 配置保存/加载正常
- [ ] 主题切换正常
- [ ] 异步任务执行正常
- [ ] 应用程序正常退出

### 质量标准

- [ ] 无循环依赖
- [ ] 无线程泄漏
- [ ] 无内存泄漏
- [ ] 日志记录正常
- [ ] 错误处理完善

### 性能标准

- [ ] 启动时间无明显增加（< 10%）
- [ ] 内存使用无明显增加（< 10%）
- [ ] 响应速度无明显下降

---

## 迁移验收清单

每个文件迁移完成后检查：

- [ ] 导入语句已更新
- [ ] 实例创建已移除
- [ ] 方法调用已更新
- [ ] 清理逻辑已调整
- [ ] 功能测试通过
- [ ] 日志输出正常
- [ ] 代码已提交

---

**任务列表版本**：1.2
**创建日期**：2024-11-16
**预计完成周期**：2-3 个工作日（12-16 小时）
**最后更新**：2024-11-16

**版本更新说明**：

- v1.2: 修复任务 14 格式问题，添加测试覆盖率目标，补充性能基准和回滚策略说明
- v1.1: 初始版本
