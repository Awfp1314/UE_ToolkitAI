# ThreadManager 迁移实施计划 v2（修正版）

**创建时间**: 2025-11-19  
**版本**: v2 - 基于 Codex 审查反馈修正  
**可行性**: 6/10 → 目标 8/10  
**风险等级**: Medium-High → 目标 Medium

---

## 📋 修正摘要

根据 Codex 审查，原计划存在 7 个关键问题：

1. ❌ `on_finished` 回调不完整（取消/超时时不触发）
2. ❌ 排队任务返回 `(None, None)` 导致崩溃
3. ❌ `cancel_all()` 未实现
4. ❌ ThreadService 示例丢失回调
5. ❌ 风险评估遗漏并发/回滚计划
6. ❌ 时间估算不现实（5-7 小时）
7. ❌ 测试计划不足

**本版本修正所有问题**。

---

## 🎯 阶段 1：完善的兼容层适配器

### 1.1 修正后的 ThreadManagerAdapter

```python
import threading
import inspect
from typing import Callable, Optional, Tuple
from PyQt6.QtCore import QThread
from core.logger import get_logger

logger = get_logger(__name__)


class PlaceholderWorker:
    """排队任务的占位 Worker"""

    def __init__(self, task_id: str, cancel_token):
        self.task_id = task_id
        self.cancel_token = cancel_token
        self.is_placeholder = True


class ThreadManagerAdapter:
    """旧版 API 适配器，内部使用新版 EnhancedThreadManager

    修正：
    1. 完整的 on_finished 回调支持（包括取消/超时）
    2. 排队任务返回占位 Worker
    3. 实现 cancel_all()
    4. 线程安全的单例访问
    """

    def __init__(self):
        from core.utils.thread_manager import get_thread_manager
        from core.utils.thread_utils import CancellationToken

        self._enhanced_manager = get_thread_manager()
        self._lock = threading.Lock()
        self._active_tasks = {}  # task_id -> (cancel_token, on_finished)
        self._CancellationToken = CancellationToken

        logger.info("ThreadManagerAdapter 初始化（使用 EnhancedThreadManager）")

    def _infer_module_name(self) -> str:
        """推断调用者的模块名"""
        try:
            # 跳过两层：run_in_thread -> _infer_module_name
            frame = inspect.currentframe().f_back.f_back
            module_name = frame.f_globals.get('__name__', 'unknown')

            if module_name == 'unknown':
                logger.warning("⚠️ 无法推断 module_name，使用 'unknown'")

            return module_name
        except Exception as e:
            logger.warning(f"⚠️ 推断 module_name 失败: {e}")
            return 'unknown'

    def _create_wrapped_callbacks(
        self,
        task_id: str,
        on_result: Optional[Callable],
        on_error: Optional[Callable],
        on_finished: Optional[Callable]
    ):
        """创建包装后的回调，确保 on_finished 总是被调用

        修正：支持取消、超时、错误等所有路径
        """

        def wrapped_on_result(result):
            """结果回调"""
            try:
                if on_result:
                    on_result(result)
            finally:
                self._trigger_on_finished(task_id)

        def wrapped_on_error(error):
            """错误回调"""
            try:
                if on_error:
                    on_error(error)
            finally:
                self._trigger_on_finished(task_id)

        def wrapped_on_timeout():
            """超时回调（新增）"""
            logger.warning(f"任务超时: {task_id}")
            self._trigger_on_finished(task_id)

        return wrapped_on_result, wrapped_on_error, wrapped_on_timeout

    def _trigger_on_finished(self, task_id: str):
        """触发 on_finished 回调（线程安全）"""
        with self._lock:
            if task_id in self._active_tasks:
                _, on_finished = self._active_tasks.pop(task_id)
                if on_finished:
                    try:
                        on_finished()
                    except Exception as e:
                        logger.error(f"on_finished 回调异常: {e}", exc_info=True)

    def run_in_thread(
        self,
        func: Callable,
        on_result: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        on_finished: Optional[Callable] = None,
        on_progress: Optional[Callable] = None,
        *args,
        **kwargs
    ) -> Tuple[Optional[QThread], Optional[object]]:
        """兼容旧版 API 的 run_in_thread

        修正：
        1. 处理排队任务（返回占位 Worker）
        2. on_finished 在所有路径触发
        3. 忽略 on_progress（新版不支持，记录警告）

        Returns:
            (thread, worker): 可能为 (None, PlaceholderWorker) 如果任务排队
        """
        # 推断 module_name
        module_name = self._infer_module_name()

        # on_progress 不支持，记录警告
        if on_progress:
            logger.warning(
                f"⚠️ on_progress 回调不支持（模块: {module_name}）\n"
                "   新版 EnhancedThreadManager 不支持进度回调"
            )

        # 生成临时 task_id（用于跟踪）
        import uuid
        temp_task_id = str(uuid.uuid4())

        # 创建包装回调
        wrapped_on_result, wrapped_on_error, wrapped_on_timeout = \
            self._create_wrapped_callbacks(temp_task_id, on_result, on_error, on_finished)

        # 注册 on_finished（用于取消时触发）
        with self._lock:
            cancel_token = self._CancellationToken()
            self._active_tasks[temp_task_id] = (cancel_token, on_finished)

        try:
            # 调用新版 API
            thread, worker, task_id = self._enhanced_manager.run_in_thread(
                func,
                module_name=module_name,
                task_name=func.__name__,
                on_result=wrapped_on_result,
                on_error=wrapped_on_error,
                on_timeout=wrapped_on_timeout,
                *args,
                **kwargs
            )

            # 更新 task_id
            with self._lock:
                if temp_task_id in self._active_tasks:
                    cancel_token, on_fin = self._active_tasks.pop(temp_task_id)
                    self._active_tasks[task_id] = (cancel_token, on_fin)

            # 处理排队任务（返回占位 Worker）
            if thread is None and worker is None:
                logger.info(f"任务已排队: {task_id}")
                placeholder = PlaceholderWorker(task_id, cancel_token)
                return None, placeholder

            # 正常任务：保留 task_id 和 cancel_token
            if worker:
                worker.task_id = task_id
                worker.cancel_token = cancel_token

            return thread, worker

        except Exception as e:
            # 清理失败的任务
            with self._lock:
                self._active_tasks.pop(temp_task_id, None)
            raise

    def cancel_all(self):
        """取消所有活动任务（修正：已实现）"""
        with self._lock:
            task_ids = list(self._active_tasks.keys())

        logger.info(f"取消所有任务: {len(task_ids)} 个")

        for task_id in task_ids:
            try:
                self._enhanced_manager.cancel_task(task_id)
                self._trigger_on_finished(task_id)
            except Exception as e:
                logger.error(f"取消任务失败 {task_id}: {e}")

    def get_stats(self):
        """获取统计信息"""
        metrics = self._enhanced_manager.monitor.get_metrics()
        return {
            'total_tasks': metrics.total_tasks_executed,
            'active_tasks': metrics.active_tasks,
            'completed': metrics.tasks_completed,
            'failed': metrics.tasks_failed,
            'timeout': metrics.tasks_timeout,
            'cancelled': metrics.tasks_cancelled,
        }


# 线程安全的单例
_global_thread_manager: Optional[ThreadManagerAdapter] = None
_global_lock = threading.Lock()


def get_thread_manager() -> ThreadManagerAdapter:
    """获取全局线程管理器实例（线程安全）

    ⚠️ DEPRECATED: 此函数返回兼容适配器
    建议迁移到: from core.utils.thread_manager import get_thread_manager
    """
    global _global_thread_manager

    if _global_thread_manager is None:
        with _global_lock:
            if _global_thread_manager is None:
                _global_thread_manager = ThreadManagerAdapter()
                logger.warning(
                    "⚠️ 使用旧版 ThreadManager API（通过适配器）\n"
                    "   建议迁移到新版: from core.utils.thread_manager import get_thread_manager"
                )

    return _global_thread_manager
```

---

### 1.2 修正后的 ThreadService 迁移示例

```python
class ThreadService:
    """统一的线程调度服务（修正版）

    修正：
    1. 正确处理 on_finished 回调
    2. 支持 module_name 覆盖
    3. 处理排队任务
    """

    def __init__(self):
        from core.utils.thread_manager import get_thread_manager
        self._thread_manager = get_thread_manager()
        print("[ThreadService] 使用 EnhancedThreadManager")

    def run_async(
        self,
        task_func: Callable,
        module_name: Optional[str] = None,
        on_result: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        on_finished: Optional[Callable] = None,
        on_progress: Optional[Callable] = None,
        *args,
        **kwargs
    ):
        """异步运行任务（修正版）

        Args:
            module_name: 模块名（可选，默认 "core.services.thread_service"）
            on_finished: 完成回调（无论成功、失败、超时都会调用）
        """
        # 默认 module_name
        if module_name is None:
            module_name = "core.services.thread_service"

        # on_progress 不支持
        if on_progress:
            logger.warning("⚠️ ThreadService 不支持 on_progress 回调")

        # 包装回调以支持 on_finished
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

        def wrapped_on_timeout():
            logger.warning(f"任务超时: {task_func.__name__}")
            if on_finished:
                on_finished()

        # 调用新版 API
        thread, worker, task_id = self._thread_manager.run_in_thread(
            task_func,
            module_name=module_name,
            task_name=task_func.__name__,
            on_result=wrapped_on_result,
            on_error=wrapped_on_error,
            on_timeout=wrapped_on_timeout,
            *args,
            **kwargs
        )

        # 处理排队任务
        if worker is None:
            logger.info(f"任务已排队: {task_id}")
            # 返回占位对象
            from core.utils.thread_utils import CancellationToken
            cancel_token = CancellationToken()

            class QueuedWorker:
                def __init__(self, tid, token):
                    self.task_id = tid
                    self.cancel_token = token
                    self.is_queued = True

            return QueuedWorker(task_id, cancel_token), cancel_token

        # 正常任务
        worker.task_id = task_id
        return worker, worker.cancel_token
```

---

## 🚀 阶段 2：试点迁移（新增）

### 2.1 试点模块选择

**选择**: `modules/asset_manager/logic/thumbnail_generator.py`

**原因**：

- ✅ 叶子模块，依赖少
- ✅ 功能简单，易于验证
- ✅ 不影响核心服务

### 2.2 试点迁移步骤

1. **修改导入**

   ```python
   from core.utils.thread_manager import get_thread_manager
   ```

2. **修改调用**

   ```python
   thread, worker, task_id = thread_manager.run_in_thread(
       func,
       module_name="asset_manager",
       task_name="generate_thumbnail",
       on_result=callback,
       on_error=error_callback
   )
   ```

3. **处理返回值**

   ```python
   if worker is None:
       logger.info(f"缩略图生成任务已排队: {task_id}")
       return

   worker.task_id = task_id
   ```

4. **验证**
   - 运行资产管理器
   - 生成缩略图
   - 检查日志中的 `module_name`
   - 验证任务监控数据

### 2.3 试点成功标准

- [ ] 功能正常（缩略图生成成功）
- [ ] `module_name` 正确（显示为 "asset_manager"）
- [ ] 无崩溃或异常
- [ ] 监控数据正确
- [ ] 排队机制正常（如果触发）

---

## 🔄 阶段 3：核心服务迁移

### 3.1 迁移 ThreadService

使用上面修正后的实现（1.2 节）。

### 3.2 迁移优先级（调整后）

1. **试点模块**（已完成）

   - `modules/asset_manager/logic/thumbnail_generator.py`

2. **核心服务层**

   - `core/services/_thread_service.py`

3. **其他叶子模块**

   - `modules/asset_manager/logic/lazy_asset_loader.py`

4. **核心管理器**

   - `core/module_manager.py`
   - `core/config/config_manager.py`

5. **AI 助手模块**
   - 6 个文件（按依赖顺序）

---

## ⚠️ 风险与缓解措施（扩展版）

### 风险 1：并发/锁问题

**影响**: 数据竞争、死锁

**缓解措施**：

- ✅ 适配器使用 `_lock` 保护共享状态
- ✅ 单例使用双重检查锁
- ✅ 编写并发测试

### 风险 2：排队任务导致 None 句柄

**影响**: 代码解引用崩溃

**缓解措施**：

- ✅ 返回 `PlaceholderWorker`
- ✅ 文档说明排队行为
- ✅ 监控排队频率

### 风险 3：on_finished 回调丢失

**影响**: 资源泄漏、状态不一致

**缓解措施**：

- ✅ 所有路径触发 `on_finished`
- ✅ 编写回调测试
- ✅ 监控回调执行

### 风险 4：module_name 推断不准确

**影响**: 监控数据失真

**缓解措施**：

- ✅ Fallback 为 "unknown"
- ✅ 记录警告日志
- ✅ 收集遥测数据
- ✅ 逐步迁移时显式传入

### 风险 5：迁移引入 regression

**影响**: 功能异常

**缓解措施**：

- ✅ 试点迁移验证
- ✅ 每阶段运行测试
- ✅ 特性开关（见下文）

### 风险 6：回滚困难（新增）

**影响**: 无法快速恢复

**缓解措施**：

- ✅ 特性开关控制适配器
- ✅ Git 分支隔离
- ✅ 回滚检查清单

---

## 🔧 回滚计划（新增）

### 特性开关实现

```python
# core/utils/thread_utils.py

# 特性开关（环境变量控制）
import os
USE_LEGACY_THREAD_MANAGER = os.getenv('USE_LEGACY_THREAD_MANAGER', 'false').lower() == 'true'

def get_thread_manager():
    """获取线程管理器（支持特性开关）"""
    if USE_LEGACY_THREAD_MANAGER:
        logger.warning("⚠️ 使用旧版 ThreadManager（特性开关启用）")
        return _get_legacy_thread_manager()
    else:
        return _get_adapter_thread_manager()
```

### 回滚步骤

1. **设置环境变量**

   ```bash
   export USE_LEGACY_THREAD_MANAGER=true
   ```

2. **重启应用**

3. **验证功能**

4. **调查问题**

5. **修复后重新启用**
   ```bash
   export USE_LEGACY_THREAD_MANAGER=false
   ```

---

## 🧪 测试计划（扩展版）

### 单元测试

**文件**: `fixtemp/test_threadmanager_adapter.py`

**测试内容**：

- ✅ `module_name` 推断（正常、失败）
- ✅ 回调触发（成功、失败、超时、取消）
- ✅ 排队任务返回 `PlaceholderWorker`
- ✅ `cancel_all()` 功能
- ✅ 并发安全（多线程调用）
- ✅ 单例正确性

### 集成测试

**文件**: `fixtemp/test_threadservice_integration.py`

**测试内容**：

- ✅ ThreadService 与适配器集成
- ✅ 模块迁移后的端到端测试
- ✅ 排队机制验证

### 性能测试

**文件**: `fixtemp/test_backpressure.py`

**测试内容**：

- ✅ 高负载下的排队行为
- ✅ 背压机制验证
- ✅ 内存使用监控

### 回归测试

**策略**：

- ✅ 每个模块迁移后运行功能测试
- ✅ 对比迁移前后的行为
- ✅ 自动化检查（CI）

### 遥测验证

**步骤**：

1. 在测试环境运行应用
2. 收集 `module_name` 频率
3. 检查 "unknown" 出现次数
4. 验证监控数据准确性

---

## 📊 时间估算（修正版）

### 阶段 1：完善适配器（2-3 天）

- 实现修正后的 `ThreadManagerAdapter`（1 天）
- 编写单元测试（0.5 天）
- 编写集成测试（0.5 天）
- 验证和调试（0.5-1 天）

### 阶段 2：试点迁移（0.5-1 天）

- 迁移 `thumbnail_generator.py`（0.5 天）
- 验证和监控（0.5 天）

### 阶段 3：核心服务迁移（1-1.5 天）

- 迁移 `ThreadService`（0.5 天）
- 迁移其他叶子模块（0.5 天）
- 验证（0.5 天）

### 阶段 4：批量迁移（2-3 天）

- 迁移核心管理器（0.5 天）
- 迁移 AI 助手模块（1-1.5 天）
- 验证和调试（0.5-1 天）

### 阶段 5：清理（0.5-1 天）

- 删除旧代码（0.5 天）
- 更新文档（0.5 天）

**总计**: 6.5-9.5 天（含缓冲）

---

## ✅ 完成标准（扩展版）

### 功能标准

1. ✅ 所有 12 个文件使用新版 API
2. ✅ `check_threadmanager_usage.py` 显示 0 个旧版使用
3. ✅ 所有功能测试通过

### 质量标准

4. ✅ 单元测试覆盖率 > 80%
5. ✅ 集成测试通过
6. ✅ 无 "unknown" module_name（或 < 5%）

### 监控标准

7. ✅ 队列深度告警 < 阈值
8. ✅ 任务超时率 < 1%
9. ✅ 监控数据准确

### 文档标准

10. ✅ `REFACTORING_PLAN.md` 更新
11. ✅ API 文档更新
12. ✅ 迁移指南完成

---

## 📝 总结

### 主要修正

1. ✅ **on_finished 完整支持**（所有路径）
2. ✅ **排队任务返回占位 Worker**
3. ✅ **cancel_all() 已实现**
4. ✅ **ThreadService 正确处理回调**
5. ✅ **并发安全（使用锁）**
6. ✅ **回滚计划（特性开关）**
7. ✅ **完整测试计划**
8. ✅ **现实的时间估算**

### 风险降低

- **可行性**: 6/10 → **8/10**
- **风险等级**: Medium-High → **Medium**

### 下一步

1. 审查修正后的计划
2. 实施阶段 1（完善适配器）
3. 编写测试
4. 试点迁移

---

**预计总时间**: 6.5-9.5 天
**风险等级**: Medium（可控）
**优先级**: 高
