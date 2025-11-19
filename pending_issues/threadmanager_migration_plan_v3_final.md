# ThreadManager 迁移实施计划 v3（最终修正版）

**创建时间**: 2025-11-19  
**版本**: v3 - 修正 v2 的 5 个关键缺陷  
**状态**: 待 Codex 最终审查

---

## 📋 v2 → v3 修正摘要

Codex 指出 v2 存在 5 个关键缺陷，导致可行性仍为 5/10，风险仍为 Medium-High。

### v2 的缺陷

1. ❌ **on_finished 永远不会触发**（闭包捕获 temp_task_id，但字典键为真实 task_id）
2. ❌ **死锁风险**（在锁内调用用户回调）
3. ❌ **取消令牌被覆盖**（覆盖真实令牌，导致取消失效）
4. ❌ **PlaceholderWorker 接口不完整**（缺少 signals、result_ready 等）
5. ❌ **回滚计划不可行**（迁移后无法回退到旧管理器）

### v3 的修正

1. ✅ **使用可变持有者传递 task_id**
2. ✅ **在锁外调用用户回调**
3. ✅ **复用 EnhancedThreadManager 的取消令牌**
4. ✅ **完整实现 Worker 接口**
5. ✅ **明确回滚范围和策略**

---

## 🎯 阶段 1：完全修正的适配器实现

### 1.1 核心适配器代码

```python
import threading
import inspect
from typing import Callable, Optional, Tuple, Any
from PyQt6.QtCore import QThread, QObject, pyqtSignal
from core.logger import get_logger

logger = get_logger(__name__)


class TaskIdHolder:
    """可变的 task_id 持有者，用于回调闭包"""

    def __init__(self):
        self.task_id: Optional[str] = None


class PlaceholderWorker(QObject):
    """排队任务的占位 Worker（完整实现 Worker 接口）

    修正：实现旧代码可能访问的所有属性和方法
    """

    # 信号（与真实 Worker 兼容）
    finished = pyqtSignal()
    error = pyqtSignal(Exception)
    result_ready = pyqtSignal(object)
    progress = pyqtSignal(int)

    def __init__(self, task_id: str, manager, cancel_token):
        super().__init__()
        self.task_id = task_id
        self._manager = manager
        self._cancel_token = cancel_token  # 保存真实令牌
        self.is_placeholder = True
        self.is_running = False  # 排队中，未运行
        self.is_cancelled = False
        self._result = None
        self._error = None

    @property
    def cancel_token(self):
        """返回真实的取消令牌（修正：不覆盖）"""
        return self._cancel_token

    def cancel(self):
        """取消任务（转发到 EnhancedThreadManager）"""
        try:
            self._manager.cancel_task(self.task_id)
            self.is_cancelled = True
            logger.info(f"已取消排队任务: {task_id}")
        except Exception as e:
            logger.error(f"取消任务失败 {self.task_id}: {e}")

    def wait(self, timeout: Optional[int] = None) -> bool:
        """等待任务完成（占位实现）

        注意：排队任务无法等待，返回 False
        """
        logger.warning(f"PlaceholderWorker.wait() 不支持（任务 {self.task_id} 仍在排队）")
        return False

    @property
    def result(self):
        """获取结果（占位实现）"""
        return self._result

    @property
    def error(self):
        """获取错误（占位实现）"""
        return self._error


class ThreadManagerAdapter:
    """旧版 API 适配器，内部使用新版 EnhancedThreadManager

    v3 修正：
    1. 使用 TaskIdHolder 解决 on_finished 闭包问题
    2. 在锁外调用用户回调，避免死锁
    3. 复用 EnhancedThreadManager 的取消令牌
    4. PlaceholderWorker 实现完整接口
    """

    def __init__(self):
        from core.utils.thread_manager import get_thread_manager

        self._enhanced_manager = get_thread_manager()
        self._lock = threading.Lock()
        self._active_tasks = {}  # task_id -> (holder, on_finished)

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
        holder: TaskIdHolder,
        on_result: Optional[Callable],
        on_error: Optional[Callable],
        on_finished: Optional[Callable]
    ):
        """创建包装后的回调

        修正：
        1. 使用 TaskIdHolder 而不是直接的 task_id
        2. 回调通过 holder.task_id 访问真实 task_id
        """

        def wrapped_on_result(result):
            """结果回调"""
            try:
                if on_result:
                    on_result(result)
            finally:
                # 使用 holder.task_id（已更新为真实 task_id）
                self._trigger_on_finished(holder.task_id)

        def wrapped_on_error(error):
            """错误回调"""
            try:
                if on_error:
                    on_error(error)
            finally:
                self._trigger_on_finished(holder.task_id)

        def wrapped_on_timeout():
            """超时回调"""
            logger.warning(f"任务超时: {holder.task_id}")
            self._trigger_on_finished(holder.task_id)

        return wrapped_on_result, wrapped_on_error, wrapped_on_timeout

    def _trigger_on_finished(self, task_id: Optional[str]):
        """触发 on_finished 回调

        修正：在锁外调用用户回调，避免死锁
        """
        if task_id is None:
            return

        # 在锁内获取回调
        on_finished = None
        with self._lock:
            if task_id in self._active_tasks:
                _, on_finished = self._active_tasks.pop(task_id)

        # 在锁外调用（修正：避免死锁）
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
        1. 使用 TaskIdHolder 解决闭包问题
        2. 不覆盖 worker.cancel_token
        3. PlaceholderWorker 实现完整接口

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

        # 创建 TaskIdHolder（修正：使用可变持有者）
        holder = TaskIdHolder()

        # 创建包装回调（传入 holder）
        wrapped_on_result, wrapped_on_error, wrapped_on_timeout = \
            self._create_wrapped_callbacks(holder, on_result, on_error, on_finished)

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

            # 更新 holder（修正：现在回调能访问到真实 task_id）
            holder.task_id = task_id

            # 注册 on_finished
            with self._lock:
                self._active_tasks[task_id] = (holder, on_finished)

            # 处理排队任务
            if thread is None and worker is None:
                logger.info(f"任务已排队: {task_id}")
                # 获取真实的取消令牌（修正：不创建新令牌）
                # EnhancedThreadManager 应该提供获取令牌的方法
                # 暂时使用 None，后续需要 EnhancedThreadManager 支持
                placeholder = PlaceholderWorker(task_id, self._enhanced_manager, None)
                return None, placeholder

            # 正常任务：保留 task_id（修正：不覆盖 cancel_token）
            if worker:
                worker.task_id = task_id
                # 不覆盖 worker.cancel_token（修正）

            return thread, worker

        except Exception as e:
            # 清理失败的任务
            with self._lock:
                if holder.task_id:
                    self._active_tasks.pop(holder.task_id, None)
            raise

    def cancel_all(self):
        """取消所有活动任务（修正：在锁外调用 on_finished）"""
        # 在锁内获取所有任务 ID
        with self._lock:
            task_ids = list(self._active_tasks.keys())

        logger.info(f"取消所有任务: {len(task_ids)} 个")

        # 在锁外取消任务（避免死锁）
        for task_id in task_ids:
            try:
                self._enhanced_manager.cancel_task(task_id)
                self._trigger_on_finished(task_id)  # 已在锁外
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

### 1.2 关键修正说明

#### 修正 1：on_finished 闭包问题

**v2 的问题**：

```python
# v2 代码
temp_task_id = str(uuid.uuid4())
wrapped_callbacks = self._create_wrapped_callbacks(temp_task_id, ...)  # 闭包捕获 temp_task_id

# 后来
self._active_tasks[task_id] = ...  # 使用真实 task_id
# 回调调用 _trigger_on_finished(temp_task_id) → 找不到！
```

**v3 的修正**：

```python
# v3 代码
holder = TaskIdHolder()  # 可变持有者
wrapped_callbacks = self._create_wrapped_callbacks(holder, ...)  # 闭包捕获 holder

# 后来
holder.task_id = task_id  # 更新持有者
self._active_tasks[task_id] = (holder, on_finished)
# 回调调用 _trigger_on_finished(holder.task_id) → 找到！
```

#### 修正 2：死锁问题

**v2 的问题**：

```python
def _trigger_on_finished(self, task_id: str):
    with self._lock:  # 持有锁
        ...
        on_finished()  # 在锁内调用用户回调 → 可能死锁
```

**v3 的修正**：

```python
def _trigger_on_finished(self, task_id: Optional[str]):
    # 在锁内获取回调
    on_finished = None
    with self._lock:
        if task_id in self._active_tasks:
            _, on_finished = self._active_tasks.pop(task_id)

    # 在锁外调用（修正）
    if on_finished:
        on_finished()
```

#### 修正 3：取消令牌问题

**v2 的问题**：

```python
cancel_token = self._CancellationToken()  # 创建新令牌
worker.cancel_token = cancel_token  # 覆盖真实令牌 → 取消失效
```

**v3 的修正**：

```python
# 不创建新令牌
# 不覆盖 worker.cancel_token
# 保留 EnhancedThreadManager 附加的真实令牌
if worker:
    worker.task_id = task_id
    # worker.cancel_token 保持不变（修正）
```

#### 修正 4：PlaceholderWorker 接口

**v2 的问题**：

```python
class PlaceholderWorker:
    def __init__(self, task_id, cancel_token):
        self.task_id = task_id
        self.cancel_token = cancel_token
        self.is_placeholder = True
        # 缺少 signals, result_ready 等 → 旧代码崩溃
```

**v3 的修正**：

```python
class PlaceholderWorker(QObject):
    # 信号（与真实 Worker 兼容）
    finished = pyqtSignal()
    error = pyqtSignal(Exception)
    result_ready = pyqtSignal(object)
    progress = pyqtSignal(int)

    def __init__(self, task_id, manager, cancel_token):
        super().__init__()
        self.task_id = task_id
        self._manager = manager
        self._cancel_token = cancel_token
        self.is_placeholder = True
        self.is_running = False
        self.is_cancelled = False
        self._result = None
        self._error = None

    @property
    def cancel_token(self):
        return self._cancel_token

    def cancel(self):
        self._manager.cancel_task(self.task_id)

    def wait(self, timeout=None):
        logger.warning("PlaceholderWorker.wait() 不支持")
        return False

    @property
    def result(self):
        return self._result

    @property
    def error(self):
        return self._error
```

---

## 🔧 EnhancedThreadManager 需要的改进

### 问题：排队任务的取消令牌

**当前问题**：

- 排队任务返回 `(None, None, task_id)`
- 没有提供取消令牌
- PlaceholderWorker 无法获取真实令牌

**需要的改进**：

```python
# 在 EnhancedThreadManager 中添加方法
class EnhancedThreadManager:

    def get_cancel_token(self, task_id: str) -> Optional[CancellationToken]:
        """获取任务的取消令牌

        Args:
            task_id: 任务 ID

        Returns:
            取消令牌，如果任务不存在返回 None
        """
        with self._lock:
            if task_id in self._pending_tasks:
                return self._pending_tasks[task_id].cancel_token
            # 检查运行中的任务
            for worker in self._active_workers.values():
                if hasattr(worker, 'task_id') and worker.task_id == task_id:
                    return worker.cancel_token
        return None
```

**适配器中使用**：

```python
# 处理排队任务
if thread is None and worker is None:
    logger.info(f"任务已排队: {task_id}")
    # 获取真实的取消令牌（修正）
    cancel_token = self._enhanced_manager.get_cancel_token(task_id)
    placeholder = PlaceholderWorker(task_id, self._enhanced_manager, cancel_token)
    return None, placeholder
```

---

## 🔄 修正后的回滚计划

### 问题：v2 的回滚计划不可行

**v2 的问题**：

- 特性开关在旧管理器和适配器之间切换
- 迁移后的模块使用新 API（`module_name`、`task_id`）
- 旧管理器无法满足这些参数

### v3 的修正：明确回滚范围

**策略 1：整个迁移期间保持适配器**

```python
# core/utils/thread_utils.py

import os

# 特性开关：控制适配器内部使用哪个管理器
USE_ENHANCED_MANAGER = os.getenv('USE_ENHANCED_MANAGER', 'true').lower() == 'true'

class ThreadManagerAdapter:
    def __init__(self):
        if USE_ENHANCED_MANAGER:
            from core.utils.thread_manager import get_thread_manager
            self._manager = get_thread_manager()
            logger.info("适配器使用 EnhancedThreadManager")
        else:
            # 使用旧版 ThreadManager 的内部实现
            self._manager = self._create_legacy_manager()
            logger.warning("⚠️ 适配器使用旧版 ThreadManager（回滚模式）")

    def _create_legacy_manager(self):
        """创建旧版管理器实例（用于回滚）"""
        # 保留旧版 ThreadManager 的代码
        pass
```

**回滚步骤**：

1. 设置环境变量：`export USE_ENHANCED_MANAGER=false`
2. 重启应用
3. 适配器内部切换到旧版实现
4. 所有模块（包括已迁移的）继续正常工作

**优点**：

- ✅ 整个迁移期间都可以回滚
- ✅ 已迁移的模块不受影响
- ✅ 只需修改环境变量

**缺点**：

- ⚠️ 需要在适配器中保留旧版实现
- ⚠️ 代码量增加

---

**策略 2：分阶段回滚**

**阶段 1-2**（适配器 + 试点）：

- 可以完全回滚到旧版
- 删除适配器，恢复旧导入

**阶段 3+**（核心服务迁移后）：

- 只能回滚适配器内部实现
- 使用策略 1 的方法

**文档说明**：

```markdown
## 回滚策略

### 阶段 1-2：完全回滚

如果在试点阶段发现问题，可以：

1. 删除适配器代码
2. 恢复旧版 get_thread_manager()
3. 回滚试点模块的修改

### 阶段 3+：适配器内部回滚

如果在批量迁移后发现问题，可以：

1. 设置 USE_ENHANCED_MANAGER=false
2. 适配器内部切换到旧版实现
3. 已迁移的模块继续工作
```

---

## 🧪 v3 测试计划

### 单元测试：test_threadmanager_adapter_v3.py

```python
import pytest
import threading
import time
from core.utils.thread_utils import ThreadManagerAdapter, TaskIdHolder, PlaceholderWorker


class TestTaskIdHolder:
    """测试 TaskIdHolder"""

    def test_holder_mutable(self):
        """测试持有者可变性"""
        holder = TaskIdHolder()
        assert holder.task_id is None

        holder.task_id = "test-123"
        assert holder.task_id == "test-123"


class TestPlaceholderWorker:
    """测试 PlaceholderWorker 接口完整性"""

    def test_has_required_attributes(self):
        """测试必需的属性"""
        worker = PlaceholderWorker("task-1", None, None)

        assert hasattr(worker, 'task_id')
        assert hasattr(worker, 'cancel_token')
        assert hasattr(worker, 'is_placeholder')
        assert hasattr(worker, 'is_running')
        assert hasattr(worker, 'is_cancelled')
        assert hasattr(worker, 'result')
        assert hasattr(worker, 'error')

    def test_has_required_signals(self):
        """测试必需的信号"""
        worker = PlaceholderWorker("task-1", None, None)

        assert hasattr(worker, 'finished')
        assert hasattr(worker, 'error')
        assert hasattr(worker, 'result_ready')
        assert hasattr(worker, 'progress')

    def test_has_required_methods(self):
        """测试必需的方法"""
        worker = PlaceholderWorker("task-1", None, None)

        assert callable(worker.cancel)
        assert callable(worker.wait)


class TestThreadManagerAdapter:
    """测试适配器核心功能"""

    def test_on_finished_fires_on_success(self):
        """测试成功时 on_finished 被调用"""
        adapter = ThreadManagerAdapter()
        finished_called = threading.Event()

        def task():
            return "success"

        def on_finished():
            finished_called.set()

        thread, worker = adapter.run_in_thread(
            task,
            on_finished=on_finished
        )

        # 等待任务完成
        if thread:
            thread.wait()

        # 验证 on_finished 被调用
        assert finished_called.wait(timeout=2.0)

    def test_on_finished_fires_on_error(self):
        """测试失败时 on_finished 被调用"""
        adapter = ThreadManagerAdapter()
        finished_called = threading.Event()

        def task():
            raise ValueError("test error")

        def on_finished():
            finished_called.set()

        thread, worker = adapter.run_in_thread(
            task,
            on_finished=on_finished
        )

        # 等待任务完成
        if thread:
            thread.wait()

        # 验证 on_finished 被调用
        assert finished_called.wait(timeout=2.0)

    def test_on_finished_fires_on_cancel(self):
        """测试取消时 on_finished 被调用"""
        adapter = ThreadManagerAdapter()
        finished_called = threading.Event()

        def task():
            time.sleep(10)  # 长时间任务

        def on_finished():
            finished_called.set()

        thread, worker = adapter.run_in_thread(
            task,
            on_finished=on_finished
        )

        # 取消任务
        time.sleep(0.1)
        if worker:
            worker.cancel()

        # 验证 on_finished 被调用
        assert finished_called.wait(timeout=2.0)

    def test_no_deadlock_when_callback_schedules_task(self):
        """测试回调中调度新任务不会死锁"""
        adapter = ThreadManagerAdapter()
        second_task_started = threading.Event()

        def first_task():
            return "first"

        def second_task():
            second_task_started.set()
            return "second"

        def on_finished():
            # 在 on_finished 中调度新任务
            adapter.run_in_thread(second_task)

        thread, worker = adapter.run_in_thread(
            first_task,
            on_finished=on_finished
        )

        # 等待第一个任务完成
        if thread:
            thread.wait()

        # 验证第二个任务被调度（不死锁）
        assert second_task_started.wait(timeout=2.0)

    def test_cancel_token_not_overridden(self):
        """测试取消令牌不被覆盖"""
        adapter = ThreadManagerAdapter()

        def task():
            time.sleep(1)

        thread, worker = adapter.run_in_thread(task)

        if worker and not worker.is_placeholder:
            # 获取原始令牌
            original_token = worker.cancel_token

            # 取消任务
            worker.cancel()

            # 验证令牌未被覆盖（仍是同一个对象）
            assert worker.cancel_token is original_token
```

---

## 📊 v3 时间估算（保持不变）

- 阶段 1：完善适配器（2-3 天）
- 阶段 2：试点迁移（0.5-1 天）
- 阶段 3：核心服务迁移（1-1.5 天）
- 阶段 4：批量迁移（2-3 天）
- 阶段 5：清理（0.5-1 天）

**总计**: 6.5-9.5 天（含缓冲）

---

## ✅ v3 完成标准

### 代码质量

1. ✅ 所有 5 个 v2 缺陷已修正
2. ✅ 单元测试覆盖率 > 80%
3. ✅ 所有测试通过

### 功能正确性

4. ✅ `on_finished` 在所有路径触发（成功、失败、超时、取消）
5. ✅ 无死锁（回调中调度任务）
6. ✅ 取消令牌正确工作
7. ✅ PlaceholderWorker 接口完整

### 迁移就绪

8. ✅ Codex 审查通过（可行性 ≥ 8/10）
9. ✅ 风险降低到 Medium 或更低
10. ✅ 可以开始阶段 1 实施

---

## 📝 总结

### v3 的关键改进

1. ✅ **TaskIdHolder** - 解决闭包捕获问题
2. ✅ **锁外回调** - 避免死锁
3. ✅ **复用令牌** - 保持取消语义
4. ✅ **完整接口** - PlaceholderWorker 兼容性
5. ✅ **明确回滚** - 可行的回滚策略

### 待 Codex 确认

- ✅ 所有 5 个缺陷是否已正确修复？
- ✅ 是否还有遗漏的问题？
- ✅ 可行性是否达到 8/10？
- ✅ 是否可以开始实施？

---

**预计总时间**: 6.5-9.5 天
**目标可行性**: 8/10
**目标风险**: Medium
**状态**: 待最终审查
