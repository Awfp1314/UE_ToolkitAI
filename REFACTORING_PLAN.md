# 🔧 UE Toolkit AI 项目重构计划

> **文档目的**：列出当前项目存在的架构问题，供 AI 助手制定重构计划
> **创建日期**：2025-11-16
> **最后更新**：2025-11-17
> **项目状态**：统一服务层已完成，剩余 5 个问题待优化

> **已完成工作**：问题 1（统一服务层）和问题 3（横切逻辑）已解决
> **详细记录**：参见 `.kiro/specs/architecture-refactoring/tasks.md`

---

## 📋 当前存在的问题

### 🔴 高优先级问题

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

### 🟡 中优先级问题

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

### 🔵 低优先级问题

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
| 🔴 高  | 2. 线程管理不统一 | 全局     | 中       | 1-2 天   |
| 🟡 中  | 4. 启动流程复杂   | 启动     | 中       | 1-2 天   |
| 🟡 中  | 5. 类函数体量大   | 局部     | 高       | 3-5 天   |
| 🔵 低  | 6. 测试覆盖率低   | 质量     | 高       | 5-10 天  |
| 🔵 低  | 7. 注释风格不统一 | 可读性   | 低       | 1-2 天   |

---

**文档创建时间**：2025-11-16
**最后更新时间**：2025-11-17
**文档状态**：列出当前待解决问题
**下一步**：根据需要选择问题进行优化
