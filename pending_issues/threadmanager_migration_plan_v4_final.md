# ThreadManager 迁移实施计划 v4（最终修正版）

**创建时间**: 2025-11-19  
**版本**: v4 - 修正 v3 的 4 个关键问题  
**状态**: 待 Codex 最终审查

---

## 📋 v3 → v4 修正摘要

Codex 指出 v3 存在 4 个关键问题，导致可行性仍为 6/10，风险仍为 Medium-High。

### v3 的问题

1. ❌ **PlaceholderWorker.cancel() 有 NameError**（`task_id` 应为 `self.task_id`）
2. ❌ **PlaceholderWorker 的 cancel_token 为 None**（无法获取真实令牌）
3. ❌ **EnhancedThreadManager.get_cancel_token() 未实施**（只是草案，未包含在计划中）
4. ❌ **回滚计划的 legacy 分支未定义**（无法保证回滚正确性）

### v4 的修正

1. ✅ **修正 PlaceholderWorker.cancel() 的 NameError**
2. ✅ **新增阶段 0：实施 EnhancedThreadManager.get_cancel_token()**
3. ✅ **PlaceholderWorker 使用真实的 cancel_token**
4. ✅ **明确回滚策略：放弃完全回滚，只支持阶段 1-2 回滚**

---

## 🎯 阶段 0：EnhancedThreadManager 改进（新增）

### 优先级：最高（必须在阶段 1 之前完成）

### 0.1 实施 get_cancel_token() 方法

**文件**: `core/utils/thread_manager.py`

**代码**：

```python
class EnhancedThreadManager:
    # ... 现有代码 ...

    def get_cancel_token(self, task_id: str) -> Optional['CancellationToken']:
        """获取任务的取消令牌

        此方法用于获取排队或运行中任务的取消令牌，
        主要用于适配器为 PlaceholderWorker 提供真实令牌。

        Args:
            task_id: 任务 ID

        Returns:
            取消令牌，如果任务不存在返回 None

        Thread-safe: 是
        """
        with self._lock:
            # 1. 检查排队任务
            if hasattr(self, '_pending_tasks') and task_id in self._pending_tasks:
                pending_task = self._pending_tasks[task_id]
                # 假设 pending_task 是一个包含 cancel_token 的对象
                if hasattr(pending_task, 'cancel_token'):
                    return pending_task.cancel_token

            # 2. 检查运行中的任务
            if hasattr(self, '_active_workers'):
                for worker in self._active_workers.values():
                    if hasattr(worker, 'task_id') and worker.task_id == task_id:
                        if hasattr(worker, 'cancel_token'):
                            return worker.cancel_token

            # 3. 任务不存在或已完成
            logger.warning(f"无法找到任务的取消令牌: {task_id}")
            return None
```

**注意事项**：

- 需要先查看 `EnhancedThreadManager` 的实际实现
- 确认 `_pending_tasks` 和 `_active_workers` 的数据结构
- 确认如何存储 `cancel_token`

---

### 0.2 编写单元测试

**文件**: `fixtemp/test_enhanced_manager_get_cancel_token.py`

**测试代码**：

```python
import pytest
import time
from core.utils.thread_manager import EnhancedThreadManager
from core.utils.thread_utils import CancellationToken


class TestGetCancelToken:
    """测试 EnhancedThreadManager.get_cancel_token() 方法"""

    def test_get_token_for_running_task(self):
        """测试获取运行中任务的取消令牌"""
        manager = EnhancedThreadManager()

        def long_task():
            time.sleep(5)

        # 启动任务
        thread, worker, task_id = manager.run_in_thread(
            long_task,
            module_name="test",
            task_name="long_task"
        )

        # 获取取消令牌
        token = manager.get_cancel_token(task_id)

        # 验证
        assert token is not None
        assert isinstance(token, CancellationToken)
        assert token is worker.cancel_token  # 应该是同一个对象

        # 清理
        token.cancel()
        if thread:
            thread.wait()

    def test_get_token_for_queued_task(self):
        """测试获取排队任务的取消令牌"""
        manager = EnhancedThreadManager()

        # 填满线程池，使任务排队
        def blocking_task():
            time.sleep(10)

        # 启动多个任务填满线程池
        tasks = []
        for i in range(manager.config.max_workers + 5):
            thread, worker, task_id = manager.run_in_thread(
                blocking_task,
                module_name="test",
                task_name=f"task_{i}"
            )
            tasks.append((thread, worker, task_id))

        # 找到一个排队的任务（thread 为 None）
        queued_task_id = None
        for thread, worker, task_id in tasks:
            if thread is None:
                queued_task_id = task_id
                break

        assert queued_task_id is not None, "应该有排队的任务"

        # 获取排队任务的取消令牌
        token = manager.get_cancel_token(queued_task_id)

        # 验证
        assert token is not None
        assert isinstance(token, CancellationToken)

        # 清理：取消所有任务
        for thread, worker, task_id in tasks:
            manager.cancel_task(task_id)

    def test_get_token_for_nonexistent_task(self):
        """测试获取不存在任务的取消令牌"""
        manager = EnhancedThreadManager()

        # 获取不存在的任务
        token = manager.get_cancel_token("nonexistent-task-id")

        # 验证
        assert token is None

    def test_cancel_via_retrieved_token(self):
        """测试通过获取的令牌取消任务"""
        manager = EnhancedThreadManager()
        task_cancelled = False

        def cancellable_task(cancel_token):
            nonlocal task_cancelled
            for i in range(100):
                if cancel_token.is_cancelled:
                    task_cancelled = True
                    return
                time.sleep(0.1)

        # 启动任务
        from core.utils.thread_utils import CancellationToken
        cancel_token = CancellationToken()
        thread, worker, task_id = manager.run_in_thread(
            cancellable_task,
            module_name="test",
            task_name="cancellable_task",
            cancel_token
        )

        # 获取令牌
        retrieved_token = manager.get_cancel_token(task_id)
        assert retrieved_token is not None

        # 通过获取的令牌取消
        time.sleep(0.2)
        retrieved_token.cancel()

        # 等待任务完成
        if thread:
            thread.wait()

        # 验证任务被取消
        assert task_cancelled
```

---

### 0.3 验证和文档

**验证步骤**：

1. 运行测试：`pytest fixtemp/test_enhanced_manager_get_cancel_token.py -v`
2. 检查所有测试通过
3. 验证排队任务可以获取令牌
4. 验证取消功能正常

**文档更新**：

- 更新 `core/utils/thread_manager.py` 的文档字符串
- 添加使用示例

---

### 0.4 阶段 0 完成标准

- [ ] `get_cancel_token()` 方法已实现
- [ ] 所有单元测试通过
- [ ] 排队任务可以获取取消令牌
- [ ] 运行中任务可以获取取消令牌
- [ ] 不存在的任务返回 None
- [ ] 通过获取的令牌可以取消任务
- [ ] 代码审查通过
- [ ] 文档已更新

**预计时间**: 0.5-1 天

---

## 🎯 阶段 1：完全修正的适配器实现

### 1.1 修正后的 PlaceholderWorker

**文件**: `core/utils/thread_utils.py`

**代码**：

```python
class PlaceholderWorker(QObject):
    """排队任务的占位 Worker（完整实现 Worker 接口）

    v4 修正：
    1. cancel() 方法使用 self.task_id（修正 NameError）
    2. 接受真实的 cancel_token（不再是 None）
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
        self._cancel_token = cancel_token  # 真实的取消令牌（不再是 None）
        self.is_placeholder = True
        self.is_running = False
        self.is_cancelled = False
        self._result = None
        self._error = None

    @property
    def cancel_token(self):
        """返回真实的取消令牌"""
        return self._cancel_token

    def cancel(self):
        """取消任务（转发到 EnhancedThreadManager）

        v4 修正：使用 self.task_id 而不是 task_id
        """
        try:
            self._manager.cancel_task(self.task_id)  # ✅ 修正：self.task_id
            self.is_cancelled = True
            logger.info(f"已取消排队任务: {self.task_id}")  # ✅ 修正：self.task_id
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
```

---

### 1.2 修正后的 ThreadManagerAdapter

**关键修正**：使用真实的 cancel_token

```python
class ThreadManagerAdapter:
    """旧版 API 适配器，内部使用新版 EnhancedThreadManager

    v4 修正：
    1. 使用 TaskIdHolder 解决 on_finished 闭包问题
    2. 在锁外调用用户回调，避免死锁
    3. 使用真实的 cancel_token（通过 get_cancel_token()）
    4. PlaceholderWorker 实现完整接口
    """

    def __init__(self):
        from core.utils.thread_manager import get_thread_manager

        self._enhanced_manager = get_thread_manager()
        self._lock = threading.Lock()
        self._active_tasks = {}  # task_id -> (holder, on_finished)

        logger.info("ThreadManagerAdapter 初始化（使用 EnhancedThreadManager）")

    # ... _infer_module_name, _create_wrapped_callbacks, _trigger_on_finished 保持不变 ...

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

        v4 修正：
        1. 使用 TaskIdHolder 解决闭包问题
        2. 不覆盖 worker.cancel_token
        3. PlaceholderWorker 使用真实的 cancel_token（通过 get_cancel_token()）

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

            # 处理排队任务（v4 修正：使用真实的 cancel_token）
            if thread is None and worker is None:
                logger.info(f"任务已排队: {task_id}")

                # ✅ v4 修正：获取真实的取消令牌
                cancel_token = self._enhanced_manager.get_cancel_token(task_id)

                if cancel_token is None:
                    logger.error(f"⚠️ 无法获取排队任务的取消令牌: {task_id}")
                    # 创建一个新令牌作为后备（不理想，但避免崩溃）
                    from core.utils.thread_utils import CancellationToken
                    cancel_token = CancellationToken()

                placeholder = PlaceholderWorker(task_id, self._enhanced_manager, cancel_token)
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
```

---

## 🔄 阶段 2-5：保持不变

阶段 2-5 的内容与 v3 相同：

- 阶段 2：试点迁移
- 阶段 3：核心服务迁移
- 阶段 4：批量迁移
- 阶段 5：清理

---

## 🔧 回滚策略（v4 修正）

### v3 的问题

v3 提出的回滚策略（适配器内部切换）存在问题：

- legacy 分支需要接受新参数（`module_name`、`task_name`、`on_timeout`）
- 但没有定义如何实现
- 无法保证回滚正确性

### v4 的修正：明确回滚范围

**策略：分阶段回滚，放弃完全回滚**

#### 阶段 0-2：可以完全回滚

**条件**：

- 只修改了 EnhancedThreadManager（添加 `get_cancel_token()`）
- 只创建了适配器（未迁移模块）
- 只迁移了试点模块（1-2 个文件）

**回滚步骤**：

1. 删除适配器代码
2. 恢复试点模块的修改
3. 回退 EnhancedThreadManager 的修改（如果需要）
4. 恢复旧版 `get_thread_manager()`

**可行性**: ✅ 高

---

#### 阶段 3+：无法完全回滚

**原因**：

- 已迁移的模块使用新 API（`module_name`、`task_id`）
- 旧版 ThreadManager 无法满足这些参数
- 无法回退到纯旧版实现

**替代方案**：

1. **修复 bug**：如果发现问题，修复适配器或 EnhancedThreadManager
2. **暂停迁移**：停止迁移新模块，保持当前状态
3. **前进修复**：继续完成迁移，在新版中修复问题

**可行性**: ❌ 无法回滚，只能前进

---

#### 缓解措施

**阶段 0-2 的充分测试**：

- 在阶段 0 充分测试 `get_cancel_token()`
- 在阶段 1 充分测试适配器
- 在阶段 2 充分测试试点模块
- **只有在所有测试通过后才进入阶段 3**

**阶段 3 的决策点**：

- 在进入阶段 3 前，明确告知：**此后无法回滚**
- 评估风险，确认可以接受
- 获得明确的批准

**监控和快速响应**：

- 每个阶段都监控错误日志
- 发现问题立即暂停
- 在阶段 0-2 发现问题时立即回滚

---

### 回滚决策树

```
发现问题
├─ 在阶段 0-2？
│  ├─ 是 → 完全回滚（删除所有修改）
│  └─ 否 → 进入阶段 3+
│
└─ 在阶段 3+？
   ├─ 问题严重？
   │  ├─ 是 → 暂停迁移，修复问题
   │  └─ 否 → 继续迁移，并行修复
   │
   └─ 无法修复？
      └─ 前进完成迁移（无法回退）
```

---

## 📊 v4 时间估算

### 阶段 0：EnhancedThreadManager 改进

**时间**: 0.5-1 天

**任务**：

- 实现 `get_cancel_token()` 方法（0.5 天）
- 编写单元测试（0.5 天）
- 验证功能（0.5 天）

### 阶段 1：完善适配器

**时间**: 2-3 天

**任务**：

- 修正 PlaceholderWorker（0.5 天）
- 修正 ThreadManagerAdapter（0.5 天）
- 编写单元测试（1 天）
- 验证功能（0.5-1 天）

### 阶段 2：试点迁移

**时间**: 0.5-1 天

### 阶段 3：核心服务迁移

**时间**: 1-1.5 天

### 阶段 4：批量迁移

**时间**: 2-3 天

### 阶段 5：清理

**时间**: 0.5-1 天

**总计**: 7-10.5 天（含缓冲）

---

## 🧪 v4 测试计划

### 阶段 0 测试

**文件**: `fixtemp/test_enhanced_manager_get_cancel_token.py`

**测试内容**：

- ✅ 获取运行中任务的取消令牌
- ✅ 获取排队任务的取消令牌
- ✅ 获取不存在任务的取消令牌（返回 None）
- ✅ 通过获取的令牌取消任务

### 阶段 1 测试

**文件**: `fixtemp/test_threadmanager_adapter_v4.py`

**测试内容**：

- ✅ PlaceholderWorker.cancel() 无 NameError
- ✅ PlaceholderWorker.cancel_token 不为 None
- ✅ 排队任务可以通过 worker.cancel() 取消
- ✅ 排队任务可以通过 worker.cancel_token.cancel() 取消
- ✅ on_finished 在所有路径触发
- ✅ 回调中调度任务不死锁
- ✅ 取消令牌不被覆盖

**测试代码示例**：

```python
def test_placeholder_worker_cancel_no_error(self):
    """测试 PlaceholderWorker.cancel() 无 NameError"""
    adapter = ThreadManagerAdapter()

    # 填满线程池，使任务排队
    # ...

    thread, worker = adapter.run_in_thread(task)

    if worker and worker.is_placeholder:
        # 调用 cancel() 不应抛出 NameError
        worker.cancel()
        assert worker.is_cancelled

def test_placeholder_worker_has_real_cancel_token(self):
    """测试 PlaceholderWorker 有真实的 cancel_token"""
    adapter = ThreadManagerAdapter()

    # 填满线程池，使任务排队
    # ...

    thread, worker = adapter.run_in_thread(task)

    if worker and worker.is_placeholder:
        # cancel_token 不应为 None
        assert worker.cancel_token is not None
        assert isinstance(worker.cancel_token, CancellationToken)

        # 可以通过 token 取消
        worker.cancel_token.cancel()
        assert worker.cancel_token.is_cancelled
```

---

## ✅ v4 完成标准

### 阶段 0 完成标准

1. ✅ `EnhancedThreadManager.get_cancel_token()` 已实现
2. ✅ 所有单元测试通过
3. ✅ 排队任务可以获取取消令牌
4. ✅ 运行中任务可以获取取消令牌
5. ✅ 不存在的任务返回 None
6. ✅ 通过获取的令牌可以取消任务

### 阶段 1 完成标准

7. ✅ PlaceholderWorker.cancel() 无 NameError
8. ✅ PlaceholderWorker.cancel_token 不为 None
9. ✅ 排队任务可以通过 worker.cancel() 取消
10. ✅ 排队任务可以通过 worker.cancel_token.cancel() 取消
11. ✅ on_finished 在所有路径触发
12. ✅ 回调中调度任务不死锁
13. ✅ 取消令牌不被覆盖
14. ✅ 所有测试通过

### 整体完成标准

15. ✅ Codex 审查通过（可行性 ≥ 8/10）
16. ✅ 风险降低到 Medium 或更低
17. ✅ 可以开始阶段 0 实施

---

## 📝 v4 总结

### 主要修正

1. ✅ **新增阶段 0**：实施 `EnhancedThreadManager.get_cancel_token()`
2. ✅ **修正 PlaceholderWorker.cancel()**：使用 `self.task_id`
3. ✅ **使用真实 cancel_token**：通过 `get_cancel_token()` 获取
4. ✅ **明确回滚策略**：阶段 0-2 可回滚，阶段 3+ 无法回滚

### 与 v3 的区别

| 项目                           | v3                    | v4                         |
| ------------------------------ | --------------------- | -------------------------- |
| 阶段 0                         | ❌ 无                 | ✅ 实施 get_cancel_token() |
| PlaceholderWorker.cancel()     | ❌ NameError          | ✅ 使用 self.task_id       |
| PlaceholderWorker.cancel_token | ❌ None               | ✅ 真实令牌                |
| 回滚策略                       | ❌ 未定义 legacy 分支 | ✅ 明确阶段 0-2 可回滚     |
| 可行性                         | 6/10                  | 目标 8/10                  |
| 风险                           | Medium-High           | 目标 Medium                |

### 待 Codex 确认

- ✅ 所有 4 个问题是否已正确修复？
- ✅ 阶段 0 的设计是否合理？
- ✅ 回滚策略是否可接受？
- ✅ 可行性是否达到 8/10？
- ✅ 是否可以开始实施阶段 0？

---

**预计总时间**: 7-10.5 天
**目标可行性**: 8/10
**目标风险**: Medium
**状态**: 待 Codex 最终审查
