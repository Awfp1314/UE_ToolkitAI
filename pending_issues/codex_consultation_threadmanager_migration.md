# Codex 咨询：ThreadManager 迁移策略

## 📋 背景说明

我们正在重构 UE_TOOKITS_AI_NEW 项目，目标是统一线程与资源管理（REFACTORING_PLAN.md 中的问题 2）。

### 当前状态

项目中存在**两个版本**的 ThreadManager：

1. **旧版 ThreadManager** (`core/utils/thread_utils.py`)
   - 基础线程管理功能
   - 线程池管理
   - 最大线程数限制
   - 提供 `Worker` 和 `CancellationToken` 工具类
   - 提供 `get_thread_manager()` 单例访问函数

2. **新版 EnhancedThreadManager** (`core/utils/thread_manager.py`)
   - 继承旧版的 `Worker` 和 `CancellationToken`
   - 新增队列管理（backpressure）
   - 新增超时机制
   - 新增任务监控（ThreadMonitor）
   - 新增配置系统（ThreadConfiguration）
   - 提供 `get_thread_manager()` 单例访问函数

### 问题发现

通过自动化检查脚本（`fixtemp/check_threadmanager_usage.py`）发现：

```
✅ 使用新版 EnhancedThreadManager: 0 个文件
⚠️  使用旧版 ThreadManager: 12 个文件
❌ 混合使用: 1 个文件
```

**使用旧版的关键文件**：
- `core/services/_thread_service.py` - **核心服务层**，封装 ThreadManager 供其他模块使用
- `core/module_manager.py` - 模块管理器
- `core/config/config_manager.py` - 配置管理器
- `modules/ai_assistant/logic/*.py` - AI 助手模块（6 个文件）
- `modules/asset_manager/logic/*.py` - 资产管理模块（2 个文件）

---

## 🤔 核心问题

### 问题 1：API 兼容性

**旧版 ThreadManager API**：
```python
def run_in_thread(
    self,
    func: Callable,
    on_result: Optional[Callable] = None,
    on_error: Optional[Callable] = None,
    on_finished: Optional[Callable] = None,
    on_progress: Optional[Callable] = None,
    *args,
    **kwargs
) -> Tuple[QThread, Worker]:
    """返回 (thread, worker)"""
```

**新版 EnhancedThreadManager API**：
```python
def run_in_thread(
    self,
    func: Callable,
    module_name: str,  # ⚠️ 新增必需参数
    task_name: Optional[str] = None,  # ⚠️ 新增可选参数
    timeout: Optional[int] = None,  # ⚠️ 新增可选参数
    on_result: Optional[Callable] = None,
    on_error: Optional[Callable] = None,
    on_timeout: Optional[Callable] = None,  # ⚠️ 新增回调
    *args,
    **kwargs,
) -> Tuple[Optional[QThread], Optional[Worker], str]:
    """返回 (thread, worker, task_id)"""
```

**不兼容点**：
1. 新版需要 `module_name` 参数（必需）
2. 新版返回值多了 `task_id`
3. 新版有 `on_timeout` 回调，旧版有 `on_finished` 回调
4. 新版可能返回 `(None, None, task_id)` 如果任务被排队

### 问题 2：服务层封装

`core/services/_thread_service.py` 是统一的线程调度服务，封装了 ThreadManager：

```python
class ThreadService:
    def __init__(self):
        self._thread_manager = ThreadManager()  # ⚠️ 使用旧版
    
    def run_async(self, task_func, on_result=None, on_error=None, ...):
        thread, worker = self._thread_manager.run_in_thread(...)
        return worker, worker.cancel_token
```

**问题**：
- 如果改为新版，需要调整 `run_async()` 的接口
- 可能影响所有使用 `ThreadService` 的代码

### 问题 3：代码依赖关系

```
新版 EnhancedThreadManager (thread_manager.py)
    ↓ 依赖
旧版 Worker + CancellationToken (thread_utils.py)
    ↑ 被使用
旧版 ThreadManager (thread_utils.py)
    ↑ 被使用
12 个文件（通过 get_thread_manager()）
```

**问题**：
- 新版依赖旧版的工具类（`Worker`, `CancellationToken`）
- 旧版的 `ThreadManager` 类本身应该废弃
- 但不能删除整个 `thread_utils.py` 文件

---

## 💡 可能的迁移方案

### 方案 A：修改旧版 `get_thread_manager()` 返回新版

**实现**：
```python
# core/utils/thread_utils.py
def get_thread_manager():
    """获取全局线程管理器实例（返回新版 EnhancedThreadManager）"""
    from core.utils.thread_manager import get_thread_manager as get_enhanced_manager
    return get_enhanced_manager()
```

**优点**：
- ✅ 无需修改调用代码
- ✅ 平滑迁移

**缺点**：
- ❌ API 不兼容（`module_name` 参数缺失）
- ❌ 返回值不兼容（多了 `task_id`）
- ❌ 会导致运行时错误

### 方案 B：创建兼容层适配器

**实现**：
```python
# core/utils/thread_utils.py
class ThreadManagerAdapter:
    """旧版 API 适配器，内部使用新版 EnhancedThreadManager"""
    
    def __init__(self):
        from core.utils.thread_manager import get_thread_manager
        self._enhanced_manager = get_thread_manager()
    
    def run_in_thread(self, func, on_result=None, on_error=None, on_finished=None, on_progress=None, *args, **kwargs):
        """兼容旧版 API"""
        # 自动推断 module_name（从调用栈）
        import inspect
        frame = inspect.currentframe().f_back
        module_name = frame.f_globals.get('__name__', 'unknown')
        
        # 调用新版 API
        thread, worker, task_id = self._enhanced_manager.run_in_thread(
            func,
            module_name=module_name,
            on_result=on_result,
            on_error=on_error,
            on_timeout=on_finished,  # 映射回调
            *args,
            **kwargs
        )
        
        # 返回旧版格式
        return thread, worker

def get_thread_manager():
    """返回兼容适配器"""
    global _global_thread_manager
    if _global_thread_manager is None:
        _global_thread_manager = ThreadManagerAdapter()
    return _global_thread_manager
```

**优点**：
- ✅ 完全兼容旧版 API
- ✅ 无需修改调用代码
- ✅ 内部使用新版实现

**缺点**：
- ⚠️ 增加了一层适配器
- ⚠️ 自动推断 `module_name` 可能不准确
- ⚠️ 无法使用新版的高级功能（超时、任务监控等）

### 方案 C：逐个迁移所有文件

**实现**：
1. 修改所有 12 个文件的导入和调用
2. 添加 `module_name` 参数
3. 处理新的返回值格式

**优点**：
- ✅ 彻底迁移，代码清晰
- ✅ 可以使用新版的所有功能

**缺点**：
- ❌ 工作量大（12 个文件）
- ❌ 容易出错
- ❌ 需要大量测试

### 方案 D：分阶段迁移

**阶段 1**：创建兼容层（方案 B）
**阶段 2**：逐步迁移关键模块到新版 API
**阶段 3**：废弃兼容层，完全使用新版

**优点**：
- ✅ 风险可控
- ✅ 可以逐步验证
- ✅ 最终达到彻底迁移

**缺点**：
- ⚠️ 需要较长时间
- ⚠️ 中间状态复杂

---

## ❓ 请 Codex 评审和建议

### 问题 1：推荐哪个方案？
- 考虑项目的稳定性、可维护性、迁移成本

### 问题 2：如果选择方案 B（兼容层），有什么潜在风险？
- 自动推断 `module_name` 是否可靠？
- 回调映射（`on_finished` → `on_timeout`）是否合理？

### 问题 3：如果选择方案 C（逐个迁移），优先级如何排序？
- 哪些文件应该优先迁移？
- 哪些文件可以暂缓？

### 问题 4：是否应该保留旧版 ThreadManager 类？
- 作为向后兼容？
- 还是直接废弃？

### 问题 5：`core/services/_thread_service.py` 应该如何处理？
- 是否应该重构为使用新版 API？
- 还是保持现状，通过兼容层间接使用新版？

---

## 📊 附加信息

### 项目规模
- 总文件数：130 个 Python 文件
- 使用旧版 ThreadManager：12 个文件
- 核心服务层：1 个文件（`_thread_service.py`）

### 测试覆盖
- 新版 EnhancedThreadManager 有完整的单元测试
- 旧版 ThreadManager 没有专门的测试

### 时间约束
- 希望尽快完成迁移，但不能影响项目稳定性

---

## 🎯 期望的回复

请 Codex 提供：
1. **推荐方案**（A/B/C/D 或其他）
2. **详细理由**（技术、风险、成本分析）
3. **实施步骤**（如果需要分阶段）
4. **潜在风险**和**缓解措施**
5. **是否需要额外的测试**或**验证步骤**

感谢 Codex 的专业建议！🙏

