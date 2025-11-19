# ThreadManager 迁移实施计划

**创建时间**: 2025-11-19  
**基于**: Codex 咨询建议  
**目标**: 将所有旧版 ThreadManager 迁移到新版 EnhancedThreadManager

---

## 📋 执行摘要

### 当前状态

- ✅ 新版 `EnhancedThreadManager` 已实现（`core/utils/thread_manager.py`）
- ⚠️ 旧版 `ThreadManager` 仍被 12 个文件使用（`core/utils/thread_utils.py`）
- ❌ 没有文件直接使用新版 `EnhancedThreadManager`

### 迁移策略

**方案 D：分阶段迁移**（Codex 推荐）

1. **阶段 1**：创建兼容层适配器（1-2 小时）
2. **阶段 2**：按优先级逐步迁移模块（3-4 小时）
3. **阶段 3**：清理适配器和旧代码（1 小时）

**总预计时间**: 5-7 小时

---

## 🎯 阶段 1：创建兼容层适配器

### 目标

创建 `ThreadManagerAdapter`，让旧版 API 调用流量转向新版实现，同时保持接口兼容。

### 任务清单

#### 1.1 实现 ThreadManagerAdapter

**文件**: `core/utils/thread_utils.py`

**关键点**：

- ✅ 自动推断 `module_name`（使用 `inspect`）
- ✅ 正确映射回调（`on_finished` ≠ `on_timeout`）
- ✅ 保留 `task_id`（挂到 `worker.task_id`）
- ✅ 返回旧版格式 `(thread, worker)`

**实现代码**：

```python
class ThreadManagerAdapter:
    """旧版 API 适配器，内部使用新版 EnhancedThreadManager"""

    def __init__(self):
        from core.utils.thread_manager import get_thread_manager
        self._enhanced_manager = get_thread_manager()
        self._lock = threading.Lock()
        logger.info("ThreadManagerAdapter 初始化（使用 EnhancedThreadManager）")

    def _infer_module_name(self) -> str:
        """推断调用者的模块名"""
        try:
            import inspect
            frame = inspect.currentframe().f_back.f_back
            module_name = frame.f_globals.get('__name__', 'unknown')
            if module_name == 'unknown':
                logger.warning("⚠️ 无法推断 module_name，使用 'unknown'")
            return module_name
        except Exception as e:
            logger.warning(f"⚠️ 推断 module_name 失败: {e}")
            return 'unknown'

    def _wrap_callbacks(self, on_result, on_error, on_finished):
        """包装回调，确保 on_finished 总是被调用"""
        def wrapped_on_result(result):
            if on_result:
                on_result(result)
            if on_finished:
                on_finished()

        def wrapped_on_error(error):
            if on_error:
                on_error(error)
            if on_finished:
                on_finished()

        return wrapped_on_result, wrapped_on_error

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
        """兼容旧版 API 的 run_in_thread"""
        # 推断 module_name
        module_name = self._infer_module_name()

        # 包装回调
        wrapped_on_result, wrapped_on_error = self._wrap_callbacks(
            on_result, on_error, on_finished
        )

        # 调用新版 API
        thread, worker, task_id = self._enhanced_manager.run_in_thread(
            func,
            module_name=module_name,
            task_name=func.__name__,
            on_result=wrapped_on_result,
            on_error=wrapped_on_error,
            *args,
            **kwargs
        )

        # 保留 task_id
        if worker:
            worker.task_id = task_id

        # 返回旧版格式
        return thread, worker

    def cancel_all(self):
        """取消所有任务"""
        # 新版没有 cancel_all，需要实现
        logger.warning("⚠️ ThreadManagerAdapter.cancel_all() 暂未实现")

    def get_stats(self):
        """获取统计信息"""
        metrics = self._enhanced_manager.monitor.get_metrics()
        return {
            'total_tasks': metrics.total_tasks_executed,
            'active_tasks': metrics.active_tasks,
            'completed': metrics.tasks_completed,
            'failed': metrics.tasks_failed,
        }
```

#### 1.2 修改 get_thread_manager()

**文件**: `core/utils/thread_utils.py`

```python
# 全局单例
_global_thread_manager: Optional[ThreadManagerAdapter] = None

def get_thread_manager() -> ThreadManagerAdapter:
    """获取全局线程管理器实例（返回适配器）

    ⚠️ DEPRECATED: 此函数返回兼容适配器，建议迁移到新版 API
    使用 `from core.utils.thread_manager import get_thread_manager` 获取新版
    """
    global _global_thread_manager
    if _global_thread_manager is None:
        _global_thread_manager = ThreadManagerAdapter()
        logger.warning(
            "⚠️ 使用旧版 ThreadManager API（通过适配器）\n"
            "   建议迁移到新版: from core.utils.thread_manager import get_thread_manager"
        )
    return _global_thread_manager
```

#### 1.3 编写单元测试

**文件**: `fixtemp/test_threadmanager_adapter.py`（临时测试）

**测试内容**：

- ✅ `module_name` 推断正确性
- ✅ 回调触发顺序（`on_result` → `on_finished`）
- ✅ 回调触发顺序（`on_error` → `on_finished`）
- ✅ `task_id` 正确挂载到 `worker`
- ✅ 返回值格式兼容（`(thread, worker)`）

#### 1.4 验证现有代码

**步骤**：

1. 运行主程序 `python main.py`
2. 检查日志中的 `module_name` 推断情况
3. 检查是否有 `unknown` 模块名
4. 验证功能正常（AI 助手、资产管理器）

---

## 🚀 阶段 2：逐步迁移模块

### 迁移优先级

根据 Codex 建议，按以下顺序迁移：

#### 优先级 1：核心服务层（最高优先级）

**文件**: `core/services/_thread_service.py`

**原因**：

- 这是所有调用的集线器
- 尽早适配可以让下游只依赖服务层
- 影响范围可控

**迁移步骤**：

1. 修改导入：`from core.utils.thread_manager import get_thread_manager`
2. 修改 `__init__`：使用新版 `EnhancedThreadManager`
3. 修改 `run_async`：
   - 添加 `module_name` 参数（可选，默认 `"core.services.thread_service"`）
   - 处理新版返回值 `(thread, worker, task_id)`
   - 保持向后兼容
4. 添加 deprecation warning

**代码示例**：

```python
class ThreadService:
    def __init__(self):
        from core.utils.thread_manager import get_thread_manager
        self._thread_manager = get_thread_manager()  # 新版
        print("[ThreadService] 使用 EnhancedThreadManager")

    def run_async(
        self,
        task_func: Callable,
        module_name: Optional[str] = None,  # 新增参数
        on_result: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        on_finished: Optional[Callable] = None,
        on_progress: Optional[Callable] = None,
        *args,
        **kwargs
    ):
        # 默认 module_name
        if module_name is None:
            module_name = "core.services.thread_service"

        # 调用新版 API
        thread, worker, task_id = self._thread_manager.run_in_thread(
            task_func,
            module_name=module_name,
            task_name=task_func.__name__,
            on_result=on_result,
            on_error=on_error,
            *args,
            **kwargs
        )

        # 保持向后兼容的返回值
        if worker:
            worker.task_id = task_id
        return worker, worker.cancel_token if worker else None
```

---

#### 优先级 2：核心管理器

**文件**：

1. `core/module_manager.py`
2. `core/config/config_manager.py`

**原因**：

- 调度量大，受益于任务超时和监控
- 变更影响范围可控

**迁移步骤**（每个文件）：

1. 修改导入：`from core.utils.thread_manager import get_thread_manager`
2. 修改调用：添加 `module_name` 参数
3. 处理返回值：`thread, worker, task_id = ...`
4. 测试验证

---

#### 优先级 3：AI 助手模块

**文件**：

1. `modules/ai_assistant/logic/api_client.py`
2. `modules/ai_assistant/logic/api_client_streaming.py`
3. `modules/ai_assistant/logic/async_memory_compressor.py`
4. `modules/ai_assistant/logic/function_calling_coordinator.py`
5. `modules/ai_assistant/logic/local_nlu.py`
6. `modules/ai_assistant/logic/non_streaming_worker.py`

**原因**：

- 高频模块，线程任务多
- 可利用 backpressure 和监控

**迁移步骤**（每个文件）：

1. 修改导入
2. 添加 `module_name="ai_assistant"`
3. 处理返回值
4. 测试 AI 助手功能

---

#### 优先级 4：资产管理模块

**文件**：

1. `modules/asset_manager/logic/lazy_asset_loader.py`
2. `modules/asset_manager/logic/thumbnail_generator.py`

**原因**：

- 业务较轻
- 依赖服务层封装
- 风险低

**迁移步骤**：

1. 修改导入
2. 添加 `module_name="asset_manager"`
3. 处理返回值
4. 测试资产加载功能

---

### 迁移检查清单

每个文件迁移后，需要完成以下检查：

- [ ] 导入语句已修改
- [ ] `module_name` 参数已添加
- [ ] 返回值处理正确（`task_id`）
- [ ] 功能测试通过
- [ ] 日志中 `module_name` 正确
- [ ] 运行 `check_threadmanager_usage.py` 验证

---

## 🧹 阶段 3：清理阶段

### 目标

删除适配器和旧代码，完全使用新版 `EnhancedThreadManager`。

### 任务清单

#### 3.1 验证迁移完成

**步骤**：

1. 运行 `fixtemp/check_threadmanager_usage.py`
2. 确认输出：
   ```
   ✅ 使用新版 EnhancedThreadManager: 12 个文件
   ⚠️  使用旧版 ThreadManager: 0 个文件
   ```

#### 3.2 删除 ThreadManagerAdapter

**文件**: `core/utils/thread_utils.py`

**删除内容**：

- `ThreadManagerAdapter` 类
- 旧版 `ThreadManager` 类
- 旧版 `get_thread_manager()` 函数

**保留内容**：

- `Worker` 类（新版依赖）
- `CancellationToken` 类（新版依赖）

#### 3.3 更新 get_thread_manager()

**文件**: `core/utils/thread_utils.py`

**新实现**：

```python
def get_thread_manager():
    """获取全局线程管理器实例

    ⚠️ DEPRECATED: 请直接使用新版 API
    from core.utils.thread_manager import get_thread_manager
    """
    from core.utils.thread_manager import get_thread_manager as get_enhanced_manager
    logger.warning(
        "⚠️ 使用已废弃的 thread_utils.get_thread_manager()\n"
        "   请改用: from core.utils.thread_manager import get_thread_manager"
    )
    return get_enhanced_manager()
```

#### 3.4 更新文档

**文件**：

- `core/README.md` - 更新 `thread_utils.py` 说明
- `REFACTORING_PLAN.md` - 标记问题 2 完成
- `fixtemp/problem2_completion_summary.md` - 更新完成状态

#### 3.5 运行完整测试

**步骤**：

1. 运行主程序 `python main.py`
2. 测试所有模块功能
3. 检查日志中的 `module_name`
4. 验证任务监控数据

---

## ⚠️ 风险与缓解措施

### 风险 1：module_name 推断不准确

**影响**: 监控数据失真

**缓解措施**：

1. 在适配器中 fallback 为 `unknown`
2. 打日志 + 统计
3. 逐步迁移时显式传入 `module_name`
4. 对关键路径手动覆盖

### 风险 2：on_finished 回调映射错误

**影响**: 回调未被触发

**缓解措施**：

1. 在适配器中包装回调
2. 确保 `on_result` 和 `on_error` 后都触发 `on_finished`
3. 编写单元测试验证

### 风险 3：返回值不兼容

**影响**: 调用代码出错

**缓解措施**：

1. 适配器返回旧版格式 `(thread, worker)`
2. 将 `task_id` 挂到 `worker.task_id`
3. 逐步迁移时处理新版返回值

### 风险 4：backpressure 导致任务排队

**影响**: 任务延迟

**缓解措施**：

1. 在服务层添加日志（排队时记录）
2. 允许配置更高的队列深度
3. 监控排队指标

### 风险 5：迁移引入 regression

**影响**: 功能异常

**缓解措施**：

1. 每阶段运行现有测试
2. 关键模块迁移后执行冒烟测试
3. 在 CI 中加入 lint 检查

---

## 📊 进度跟踪

### 阶段 1：兼容层适配器

- [ ] 实现 `ThreadManagerAdapter`
- [ ] 修改 `get_thread_manager()`
- [ ] 编写单元测试
- [ ] 验证现有代码

### 阶段 2：逐步迁移

**优先级 1：核心服务层**

- [ ] `core/services/_thread_service.py`

**优先级 2：核心管理器**

- [ ] `core/module_manager.py`
- [ ] `core/config/config_manager.py`

**优先级 3：AI 助手模块**

- [ ] `modules/ai_assistant/logic/api_client.py`
- [ ] `modules/ai_assistant/logic/api_client_streaming.py`
- [ ] `modules/ai_assistant/logic/async_memory_compressor.py`
- [ ] `modules/ai_assistant/logic/function_calling_coordinator.py`
- [ ] `modules/ai_assistant/logic/local_nlu.py`
- [ ] `modules/ai_assistant/logic/non_streaming_worker.py`

**优先级 4：资产管理模块**

- [ ] `modules/asset_manager/logic/lazy_asset_loader.py`
- [ ] `modules/asset_manager/logic/thumbnail_generator.py`

### 阶段 3：清理

- [ ] 验证迁移完成
- [ ] 删除 `ThreadManagerAdapter`
- [ ] 删除旧版 `ThreadManager`
- [ ] 更新 `get_thread_manager()`
- [ ] 更新文档
- [ ] 运行完整测试

---

## 📝 附录

### A. 相关文件清单

**核心文件**：

- `core/utils/thread_utils.py` - 旧版 ThreadManager（需修改）
- `core/utils/thread_manager.py` - 新版 EnhancedThreadManager
- `core/services/_thread_service.py` - 线程服务（需迁移）

**需迁移的文件**（12 个）：

1. `core/module_manager.py`
2. `core/config/config_manager.py`
3. `core/services/_thread_service.py`
4. `modules/ai_assistant/logic/api_client.py`
5. `modules/ai_assistant/logic/api_client_streaming.py`
6. `modules/ai_assistant/logic/async_memory_compressor.py`
7. `modules/ai_assistant/logic/function_calling_coordinator.py`
8. `modules/ai_assistant/logic/local_nlu.py`
9. `modules/ai_assistant/logic/non_streaming_worker.py`
10. `modules/asset_manager/logic/lazy_asset_loader.py`
11. `modules/asset_manager/logic/thumbnail_generator.py`
12. `core/utils/thread_utils.py` (自身)

**工具脚本**：

- `fixtemp/check_threadmanager_usage.py` - 使用情况检查
- `fixtemp/test_threadmanager_adapter.py` - 适配器测试（待创建）

### B. API 对比

**旧版 API**：

```python
thread, worker = thread_manager.run_in_thread(
    func,
    on_result=callback,
    on_error=error_callback,
    on_finished=finished_callback
)
```

**新版 API**：

```python
thread, worker, task_id = thread_manager.run_in_thread(
    func,
    module_name="my_module",
    task_name="my_task",
    timeout=30000,
    on_result=callback,
    on_error=error_callback,
    on_timeout=timeout_callback
)
```

### C. 参考文档

- `REFACTORING_PLAN.md` - 重构计划（问题 2）
- `fixtemp/codex_consultation_threadmanager_migration.md` - Codex 咨询
- `docs/CLEANUP_CONTRACT_GUIDE.md` - 清理契约指南
- `docs/CANCELLATION_AWARE_TASKS_GUIDE.md` - 取消机制指南
- `docs/TIMEOUT_CONFIGURATION_GUIDE.md` - 超时配置指南

---

## ✅ 完成标准

迁移完成的标准：

1. ✅ 所有 12 个文件都使用新版 `EnhancedThreadManager`
2. ✅ `check_threadmanager_usage.py` 显示 0 个旧版使用
3. ✅ 旧版 `ThreadManager` 类已删除
4. ✅ `ThreadManagerAdapter` 已删除
5. ✅ 所有功能测试通过
6. ✅ 监控数据中 `module_name` 正确
7. ✅ 文档已更新
8. ✅ `REFACTORING_PLAN.md` 标记问题 2 完成

---

**预计总时间**: 5-7 小时
**风险等级**: 中（通过分阶段迁移降低风险）
**优先级**: 高（完成问题 2 的关键步骤）
