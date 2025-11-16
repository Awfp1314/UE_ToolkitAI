# 🔧 UE Toolkit AI 项目重构计划

> **文档目的**：列出当前项目存在的架构问题，供 AI 助手制定重构计划  
> **创建日期**：2025-11-16  
> **项目状态**：功能完整，可正常运行，但架构复杂度较高

---

## 📋 问题清单

### 🔴 高优先级问题（建议优先解决）

#### 问题 1：共用服务分散，缺乏统一入口

**现状**：

- `ThreadManager` 在 `core/utils/thread_utils.py`
- `ConfigManager` 每个模块都自己创建实例
- `Logger` 通过 `get_logger(__name__)` 分散调用
- `StyleSystem` 在 `core/utils/style_system.py`
- 各模块直接访问这些工具，耦合度高

**问题**：

- 模块之间职责不清，重复代码多
- 难以统一管理和监控
- 修改一个服务可能影响多个模块
- 测试困难（无法 mock）

**期望改进**：
创建统一的服务层 `core/services/`，提供单例访问接口：

```python
# 统一服务层结构
core/services/
├── __init__.py              # 导出所有服务
├── thread_service.py        # 线程调度服务（封装 ThreadManager）
├── config_service.py        # 配置访问服务（封装 ConfigManager）
├── log_service.py           # 日志服务（封装 Logger）
└── style_service.py         # 样式服务（封装 StyleSystem）

# 使用方式
from core.services import thread_service, config_service, log_service

# 线程调度
thread_service.run_async(task_func, callback)
thread_service.cancel_task(task_id)

# 配置访问
config = config_service.get_module_config("asset_manager")
config_service.save_module_config("asset_manager", config)

# 日志记录
log_service.info("模块启动")
log_service.error("发生错误", exc_info=True)
```

**改进收益**：

- ✅ 降低模块间耦合
- ✅ 统一管理和监控
- ✅ 便于测试和 mock
- ✅ 代码更清晰易读

---

#### 问题 2：线程与资源管理不统一

**现状**：

- 有 `ThreadManager` 统一管理线程
- 但部分模块仍使用裸 `QThread`
- 取消机制不一致（有 `CancellationToken`，但不是所有任务都支持）
- 清理契约不统一（有 `ThreadCleanupMixin`，但不是所有模块都用）

**问题**：

- 线程泄漏风险
- 取消任务不可靠
- 退出时可能卡顿或崩溃
- 难以追踪和调试线程问题

**期望改进**：

1. **强制使用 ThreadManager**：禁止直接创建 `QThread`
2. **统一取消机制**：所有耗时任务必须支持 `CancellationToken`
3. **统一清理契约**：所有模块必须实现 `cleanup()` 方法
4. **添加超时机制**：长时间运行的任务自动超时

```python
# 规范示例
class MyModule(IModule, ThreadCleanupMixin):
    def __init__(self):
        super().__init__()
        self.thread_manager = ThreadManager()

    def long_task(self, cancel_token):
        """所有耗时任务必须接受 cancel_token"""
        for i in range(100):
            if cancel_token.is_cancelled():
                return None
            # 执行任务
        return result

    def cleanup(self):
        """必须实现清理方法"""
        self.thread_manager.cleanup()
```

**改进收益**：

- ✅ 消除线程泄漏
- ✅ 可靠的任务取消
- ✅ 稳定的退出流程
- ✅ 便于调试和监控

---

#### 问题 3：配置/路径/主题等横切逻辑混用

**现状**：

- 路径获取混用 `QStandardPaths`、`PathUtils`、环境变量
- 配置访问有时用 `ConfigManager`，有时直接读 JSON
- 主题应用有时用 `StyleSystem`，有时直接 `setStyleSheet()`

**问题**：

- 逻辑分散，难以维护
- 潜在的平台兼容性问题
- 修改路径策略需要改多处代码

**期望改进**：

1. **统一路径访问**：所有路径通过 `PathService` 获取
2. **统一配置访问**：所有配置通过 `ConfigService` 访问
3. **统一样式应用**：所有样式通过 `StyleService` 应用

```python
# 禁止直接访问 OS API
# ❌ 错误示例
user_dir = QStandardPaths.writableLocation(...)
with open("config.json") as f: ...

# ✅ 正确示例
from core.services import path_service, config_service
user_dir = path_service.get_user_data_dir()
config = config_service.load("my_module")
```

**改进收益**：

- ✅ 统一管理，易于修改
- ✅ 更好的平台兼容性
- ✅ 减少重复代码

---

### 🟡 中优先级问题（逐步优化）

#### 问题 4：启动流程复杂，逻辑混杂

**现状**：

- `main.py` 包含：应用初始化、日志配置、模块加载、UI 启动、错误处理
- `UEMainWindow` 包含：UI 创建、模块管理、主题切换、窗口拖动
- 两个文件都很长，职责不清

**问题**：

- 单文件复杂度高，难以阅读
- 启动流程不清晰
- 难以测试和调试
- 修改启动逻辑风险大

**期望改进**：
拆分启动管线到独立文件：

```python
core/bootstrap/
├── __init__.py
├── app_initializer.py     # 应用初始化（日志、配置、单例检查）
├── module_loader.py       # 模块装载（扫描、加载、初始化）
└── ui_launcher.py         # UI 启动（创建窗口、应用主题）

# main.py 变得超简单
from core.bootstrap import AppBootstrap

def main():
    bootstrap = AppBootstrap()
    exit_code = bootstrap.run()
    sys.exit(exit_code)
```

**改进收益**：

- ✅ 代码更清晰
- ✅ 职责分离
- ✅ 便于测试
- ✅ 降低维护成本

---

#### 问题 5：类和函数体量较大

**现状**：

- `UEMainWindow` 超过 1000 行
- `AssetManagerLogic` 超过 2300 行
- 单个方法超过 100 行的情况较多
- 缺少类型提示

**问题**：

- 阅读负担大
- 难以理解和修改
- 容易引入 bug
- IDE 提示不友好

**期望改进**：

1. **拆分大类**：将大类拆分为多个小类
2. **提取小函数**：单个函数不超过 50 行
3. **添加类型提示**：所有公共方法添加类型提示

```python
# ❌ 错误示例
def process_data(self, data):
    # 100+ 行代码
    ...

# ✅ 正确示例
def process_data(self, data: Dict[str, Any]) -> ProcessResult:
    """处理数据

    Args:
        data: 输入数据

    Returns:
        处理结果
    """
    validated_data = self._validate_data(data)
    transformed_data = self._transform_data(validated_data)
    return self._save_result(transformed_data)

def _validate_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
    """验证数据（私有方法，逻辑简单）"""
    ...
```

**改进收益**：

- ✅ 代码更易读
- ✅ 更好的 IDE 支持
- ✅ 降低 bug 风险
- ✅ 便于单元测试

---

### 🔵 低优先级问题（长期优化）

#### 问题 6：测试覆盖率低

**现状**：

- `tests/` 目录有一些测试文件
- 但主要测试旧的 UI 样式和特定功能
- 核心逻辑（配置、模块装载、线程管理、主题应用）缺少测试
- 没有集成测试

**问题**：

- 修改代码时心里没底
- 容易引入回归 bug
- 重构风险大

**期望改进**：
补充核心路径的基础测试：

```python
tests/
├── unit/                    # 单元测试
│   ├── test_config_service.py
│   ├── test_thread_service.py
│   ├── test_module_loader.py
│   └── test_style_service.py
├── integration/             # 集成测试
│   ├── test_app_startup.py
│   ├── test_module_loading.py
│   └── test_theme_switching.py
└── fixtures/                # 测试数据
    └── test_config.json
```

**改进收益**：

- ✅ 提高代码质量
- ✅ 降低回归风险
- ✅ 重构更有信心
- ✅ 文档化代码行为

**注意**：

- 对于 AI 生成的项目，测试的性价比不高（代码可能还会大改）
- 建议等核心架构稳定后再补充测试
- 优先测试关键路径（启动、模块加载、配置读写）

---

#### 问题 7：注释过多且风格不统一

**现状**：

- 大量中文注释和 emoji
- 有些注释是"流程作文"式的详细说明
- 缺少标准的 docstring
- 类型提示不完整

**问题**：

- 注释掩盖了真正的接口设计
- 过多注释反而增加阅读负担
- 不符合 Python 规范

**期望改进**：

1. **减少流程注释**：用清晰的代码代替注释
2. **添加标准 docstring**：使用 Google 或 NumPy 风格
3. **完善类型提示**：所有公共接口添加类型提示
4. **减少 emoji**：保持专业性

```python
# ❌ 过多注释
def process_data(self, data):
    # 🎯 第一步：验证数据
    # 检查数据是否为空
    # 检查数据格式是否正确
    # 检查必填字段是否存在
    if not data:
        return None
    # 🎯 第二步：转换数据
    # 将数据转换为内部格式
    # 处理特殊字符
    ...

# ✅ 清晰的代码 + 简洁的 docstring
def process_data(self, data: Dict[str, Any]) -> Optional[ProcessedData]:
    """处理输入数据并返回处理结果

    Args:
        data: 原始输入数据

    Returns:
        处理后的数据，如果验证失败则返回 None

    Raises:
        ValueError: 数据格式不正确
    """
    if not self._validate(data):
        return None
    return self._transform(data)
```

**改进收益**：

- ✅ 代码更专业
- ✅ 更好的 IDE 支持
- ✅ 符合 Python 规范
- ✅ 便于生成文档

**注意**：

- 中文注释对中文开发者友好，可以保留
- 关键是减少冗余注释，不是消除所有注释
- 优先级较低，不影响功能

---

## 📊 问题优先级总结

| 优先级 | 问题              | 影响范围 | 改进难度 | 建议时间 |
| ------ | ----------------- | -------- | -------- | -------- |
| 🔴 高  | 1. 共用服务分散   | 全局     | 中       | 1-2 天   |
| 🔴 高  | 2. 线程管理不统一 | 全局     | 中       | 1-2 天   |
| 🔴 高  | 3. 横切逻辑混用   | 全局     | 低       | 0.5-1 天 |
| 🟡 中  | 4. 启动流程复杂   | 启动     | 中       | 1-2 天   |
| 🟡 中  | 5. 类函数体量大   | 局部     | 高       | 3-5 天   |
| 🔵 低  | 6. 测试覆盖率低   | 质量     | 高       | 5-10 天  |
| 🔵 低  | 7. 注释风格不统一 | 可读性   | 低       | 1-2 天   |

---

## 🎯 重构建议

### 方案 A：最小改动（推荐）

**目标**：解决最明显的问题，风险最小

**改进内容**：

- ✅ 问题 1：创建统一服务层
- ✅ 问题 3：统一横切逻辑访问

**预计时间**：1-2 天
**风险等级**：低
**收益**：大幅降低复杂度

---

### 方案 B：中等改动

**目标**：解决核心架构问题

**改进内容**：

- ✅ 问题 1：创建统一服务层
- ✅ 问题 2：统一线程管理
- ✅ 问题 3：统一横切逻辑访问
- ✅ 问题 4：拆分启动流程

**预计时间**：3-5 天
**风险等级**：中
**收益**：显著提升代码质量

---

### 方案 C：全面重构

**目标**：彻底解决所有问题

**改进内容**：

- ✅ 所有 7 个问题

**预计时间**：10-15 天
**风险等级**：高
**收益**：项目质量达到生产级别

**注意**：不推荐现在做全面重构，因为：

- 时间成本太高
- 可能引入新 bug
- 对于 AI 生成的项目，过早优化意义不大

---

## 📝 给 Kiro 的建议

### 制定计划时考虑：

1. **当前项目状态**：

   - ✅ 功能完整，可正常运行
   - ⚠️ 架构复杂，但不影响使用
   - ❓ 是否需要立即重构？

2. **重构时机**：

   - 如果项目还在快速迭代，建议暂缓重构
   - 如果遇到频繁 bug 或难以添加新功能，建议立即重构
   - 如果准备发布稳定版本，建议做方案 B

3. **重构策略**：

   - 优先解决高优先级问题（问题 1-3）
   - 逐步优化中优先级问题（问题 4-5）
   - 长期优化低优先级问题（问题 6-7）

4. **风险控制**：
   - 每次改动前先提交代码
   - 改动后立即测试
   - 出问题可以快速回滚

---

## ✅ 检查清单

Kiro 制定计划后，请检查以下内容：

- [ ] 是否明确了重构目标？
- [ ] 是否评估了时间成本？
- [ ] 是否考虑了风险？
- [ ] 是否有回滚方案？
- [ ] 是否有测试计划？
- [ ] 是否分阶段进行？
- [ ] 是否保留了原有功能？

---

**文档创建时间**：2025-11-16
**文档状态**：待 Kiro 制定计划
**下一步**：Kiro 根据此文档制定详细的重构计划
