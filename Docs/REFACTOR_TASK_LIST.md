# UE Toolkit 核心重构执行任务清单（外包交付版）

**文档版本**: v1.0  
**生成时间**: 2026-04-28  
**基于审计报告**: UE Toolkit 代码质量审计报告  
**适用对象**: 外包开发人员  
**执行原则**: 严格按任务范围执行，禁止超范围修改，每个任务独立验收

---

## 📋 任务总览

| 阶段     | 任务编号 | 严重级别 | 预估工时 | 验收要求            |
| -------- | -------- | -------- | -------- | ------------------- |
| 第一阶段 | FIX-01   | 致命     | 8h       | 单元测试 + 压力测试 |
| 第一阶段 | FIX-02   | 致命     | 4h       | 内存分析 + 功能测试 |
| 第一阶段 | FIX-03   | 致命     | 4h       | 并发测试 + 功能测试 |
| 第二阶段 | FIX-04   | 严重     | 6h       | UI 测试 + 性能测试  |
| 第二阶段 | FIX-05   | 严重     | 3h       | 超时测试 + 功能测试 |
| 第二阶段 | FIX-06   | 严重     | 3h       | 网络测试 + 功能测试 |
| 第二阶段 | FIX-07   | 严重     | 2h       | 清理测试 + 功能测试 |
| 第三阶段 | OPT-01   | 一般     | 3h       | 性能测试 + 功能测试 |
| 第三阶段 | OPT-02   | 一般     | 1h       | 代码审查 + 静态检查 |
| 第三阶段 | OPT-03   | 一般     | 2h       | 代码审查 + 静态检查 |
| 第三阶段 | OPT-04   | 一般     | 2h       | 性能测试 + 日志验证 |

**总计**: 11 个任务，预估 38 小时

---

## 🔴 第一阶段：致命级修复

### FIX-01: 修复线程管理器信号量泄漏

**严重级别**: 🔴 致命  
**预估工时**: 8 小时  
**优先级**: P0（最高）

#### 📁 文件范围（禁止超出此范围）

**必须修改**:

- `core/utils/thread_manager.py`
  - `EnhancedThreadManager._start_task()` (Line 108-263)
  - 新增方法：`_is_task_cancelled()`, `_handle_cancelled_task()`, `_create_worker_and_thread()`, `_register_active_task()`

**禁止修改**:

- `core/services/_thread_service.py`（接口保持不变）
- `core/utils/thread_models.py`（数据模型保持不变）
- 其他任何文件

#### 🔧 逻辑重构方案

**问题根源**: `_start_task()` 方法使用 `while True` 循环处理已取消任务，存在多个 return 路径，信号量释放逻辑复杂且容易出错。

**重构目标**: 简化方法结构，确保信号量在所有路径下正确释放。

**核心修改**:

1. **提取子方法（单一职责原则）**:
   - `_is_task_cancelled(meta)`: 检查任务是否已取消
   - `_handle_cancelled_task(meta)`: 处理已取消任务的清理
   - `_create_worker_and_thread(meta)`: 创建 Worker 和 Thread 对象
   - `_register_active_task(meta, worker, thread)`: 注册活跃任务

2. **简化 `_start_task()` 主流程**:
   - 移除 `while True` 循环
   - 使用单一 `semaphore_released` 标志追踪所有权
   - 确保 `finally` 块中释放信号量（如果所有权未转移）

3. **关键代码片段**:

   ```python
   def _start_task(self, meta: dict) -> Tuple[Optional[QThread], Optional[Worker]]:
       semaphore_released = False
       try:
           if self._is_task_cancelled(meta):
               self._handle_cancelled_task(meta)
               return None, None

           worker, thread = self._create_worker_and_thread(meta)
           # ... 连接信号 ...
           self._register_active_task(meta, worker, thread)
           thread.start()

           semaphore_released = True  # 所有权转移
           return thread, worker
       finally:
           if not semaphore_released:
               self._semaphore.release()
   ```

#### ✅ 强制验收标准（Definition of Done）

**代码层面**:

1. **单元测试**: 创建 `tests/core/utils/test_thread_manager_fix01.py`

2. **必须通过的测试用例**:
   - `test_semaphore_leak_on_cancelled_task()`: 5 个任务立即取消，信号量完全释放
   - `test_semaphore_leak_on_exception()`: 任务启动异常，信号量正确释放
   - `test_stress_with_cancellation()`: 1000 个任务（50% 取消率），信号量无泄漏

3. **测试执行**:
   ```bash
   pytest tests/core/utils/test_thread_manager_fix01.py -v
   # 预期: 3/3 passed
   ```

**运行层面**:

1. **日志验证**:
   - 启动应用，AI 助手对话 100 轮
   - 检查 `logs/runtime/ue_toolkit.log`
   - 必须看到配对日志：
     ```
     [DEBUG] Task xxx started, semaphore ownership transferred
     [DEBUG] Semaphore released after task xxx finished
     ```

2. **性能验证**:
   - 运行 24 小时稳定性测试
   - 使用 `get_semaphore_status()` 监控
   - `available_slots` 始终 <= `total_slots`

3. **UI 验证**:
   - AI 助手对话流畅无卡顿
   - 资产批量导入 100 个成功
   - 应用退出无异常

#### ⚠️ 回归风险提示

**高风险模块**（必须测试）:

- `modules/ai_assistant/`: 长时间对话（100+ 轮）
- `modules/asset_manager/`: 批量导入资产（100+ 个）
- `core/bootstrap/`: 应用启动和退出

**测试清单**:

- [ ] AI 助手：发送 100 条消息，无卡顿
- [ ] 资产管理：批量导入 100 个资产，全部成功
- [ ] 配置工具：配置对比功能正常
- [ ] 应用退出：退出时无异常，进程完全终止
- [ ] 日志检查：无 "Semaphore leak" 警告

---

### FIX-02: 修复上下文管理器内存泄漏

**严重级别**: 🔴 致命  
**预估工时**: 4 小时  
**优先级**: P0（最高）

#### 📁 文件范围（禁止超出此范围）

**必须修改**:

- `modules/ai_assistant/logic/context_manager.py`
  - `ContextManager.__init__()` (Line 56-123)
  - 删除 Line 113: `self._context_cache = {}`
  - 删除 Line 114: `self._cache_ttl = 60`

**禁止修改**:

- `core/utils/lru_cache.py`
- 其他任何文件

#### 🔧 逻辑重构方案

**问题根源**: Line 95 创建的 `ThreadSafeLRUCache` 被 Line 113 的普通字典覆盖，导致 LRU 缓存失效，内存无限增长。

**重构目标**: 移除重复定义，确保 LRU 缓存生效。

**核心修改**:

1. 删除 Line 113: `self._context_cache = {}`
2. 删除 Line 114: `self._cache_ttl = 60`
3. 保留 Line 95 的 LRU 缓存定义

#### ✅ 强制验收标准（Definition of Done）

**代码层面**:

1. **单元测试**: 创建 `tests/modules/ai_assistant/logic/test_context_manager_fix02.py`

2. **必须通过的测试用例**:
   - `test_lru_cache_not_overwritten()`: 验证 `_context_cache` 是 `ThreadSafeLRUCache` 实例
   - `test_memory_leak_with_1000_queries()`: 1000 次查询，内存增长 < 100MB
   - `test_cache_ttl_expiration()`: 缓存在 TTL 后正确过期

3. **内存分析**:
   ```bash
   pip install memory_profiler psutil
   pytest tests/modules/ai_assistant/logic/test_context_manager_fix02.py -v
   # 预期: 3/3 passed, 内存增长 < 100MB
   ```

**运行层面**:

1. **日志验证**:
   - AI 助手对话 500 轮
   - 日志显示: `[INFO] 已初始化上下文缓存（容量: 100, TTL: 60秒）`
   - 无缓存相关错误

2. **内存验证**:
   - 任务管理器监控内存
   - 对话 500 轮后，内存 < 500MB
   - 内存不持续增长

3. **功能验证**:
   - 上下文构建速度 < 100ms
   - 缓存命中率 > 60%

#### ⚠️ 回归风险提示

**高风险模块**: `modules/ai_assistant/`

**测试清单**:

- [ ] AI 助手：长时间对话（500+ 轮），内存稳定
- [ ] 上下文构建：性能无退化（< 100ms）
- [ ] 记忆检索：相关记忆正确返回
- [ ] 闲聊模式：上下文为空或极简
- [ ] 缓存统计：`get_cache_stats()` 返回正确数据

---

### FIX-03: 修复配置管理器竞态条件

**严重级别**: 🔴 致命  
**预估工时**: 4 小时  
**优先级**: P0（最高）

#### 📁 文件范围（禁止超出此范围）

**必须修改**:

- `core/config/config_manager.py`
  - `ConfigManager.__init__()` (Line 26-77): 添加 `self._cache_lock = threading.RLock()`
  - `ConfigManager._is_cache_valid()` (Line 455-479): 添加锁保护
  - `ConfigManager._update_cache()` (Line 479-490): 添加锁保护并深拷贝
  - `ConfigManager.get_module_config()` (Line 344-421): 添加锁保护
  - `ConfigManager.get_module_config_async()` (Line 421-455): 添加锁保护

**禁止修改**:

- `core/config/config_validator.py`
- `core/config/config_backup.py`
- 其他任何文件

#### 🔧 逻辑重构方案

**问题根源**: 缓存读写无锁保护，多线程并发访问导致 TOCTOU 漏洞和数据损坏。

**重构目标**: 引入 `threading.RLock` 保护所有缓存操作。

**核心修改**:

1. **添加锁成员变量**:

   ```python
   import threading

   def __init__(self, ...):
       self._cache_lock = threading.RLock()
   ```

2. **保护缓存检查**:

   ```python
   def _is_cache_valid(self) -> bool:
       with self._cache_lock:
           if self._config_cache is None:
               return False
           if time.time() - self._cache_timestamp > self._cache_ttl:
               return False
           return True
   ```

3. **保护缓存更新（深拷贝）**:

   ```python
   def _update_cache(self, config: Dict[str, Any]) -> None:
       with self._cache_lock:
           import copy
           self._config_cache = copy.deepcopy(config)
           self._cache_timestamp = time.time()
   ```

4. **保护缓存读取（深拷贝）**:
   ```python
   def get_module_config(self, force_reload: bool = False) -> Dict[str, Any]:
       if not force_reload and self._is_cache_valid():
           with self._cache_lock:
               import copy
               return copy.deepcopy(self._config_cache)
       # ... 加载逻辑 ...
   ```

#### ✅ 强制验收标准（Definition of Done）

**代码层面**:

1. **单元测试**: 创建 `tests/core/config/test_config_manager_fix03.py`

2. **必须通过的测试用例**:
   - `test_concurrent_read_write()`: 10 个读线程 + 5 个写线程并发 100 次，无错误
   - `test_cache_isolation()`: 外部修改配置不影响缓存
   - `test_deep_copy_protection()`: 验证深拷贝生效

3. **并发测试**:
   ```bash
   pytest tests/core/config/test_config_manager_fix03.py -v -n 8
   # 预期: 3/3 passed, 无竞态条件
   ```

**运行层面**:

1. **日志验证**:
   - 多模块同时加载配置
   - 无 "Config corrupted" 或 "Race condition" 错误

2. **功能验证**:
   - 所有模块配置加载成功
   - 配置热重载功能正常
   - 配置保存无数据丢失

#### ⚠️ 回归风险提示

**高风险模块**: 所有模块（配置系统是全局依赖）

**测试清单**:

- [ ] 所有模块：配置加载和保存正常
- [ ] AI 助手：配置热重载生效
- [ ] 资产管理：配置迁移成功
- [ ] 配置工具：配置对比和应用正常
- [ ] 并发场景：多线程访问配置无异常

---

## 🟠 第二阶段：稳定性增强

### FIX-04: 资产扫描改为异步执行

**严重级别**: 🟠 严重  
**预估工时**: 6 小时  
**优先级**: P1

#### 📁 文件范围（禁止超出此范围）

**必须修改**:

- `modules/asset_manager/logic/asset_manager_logic.py`
  - `_scan_asset_library()` (Line 245-348): 改为返回异步任务
  - 新增 `_scan_asset_library_impl()`: 实际扫描逻辑（支持取消）
- `modules/asset_manager/ui/asset_manager_widget.py`
  - 添加进度条显示
  - 添加取消按钮

**禁止修改**:

- 资产数据模型
- 其他模块

#### 🔧 逻辑重构方案

**问题根源**: 同步扫描大型资产库（10GB+）导致 UI 卡顿 10-30 秒。

**重构目标**: 改为异步扫描，UI 保持响应，支持取消。

**核心修改**:

1. **改造 `_scan_asset_library()`**:

   ```python
   def _scan_asset_library(self, library_path: Path, ...) -> Tuple[Worker, CancellationToken, str]:
       """异步扫描资产库"""
       from core.services import thread_service

       worker, cancel_token, task_id = thread_service.run_async(
           self._scan_asset_library_impl,
           on_result=lambda assets: self._on_scan_complete(assets),
           on_error=lambda err: self._on_scan_error(err),
           on_progress=lambda p: self.scan_progress.emit(p),
           library_path=library_path
       )

       return worker, cancel_token, task_id
   ```

2. **实现 `_scan_asset_library_impl()`**:

   ```python
   def _scan_asset_library_impl(self, cancel_token, library_path: Path, ...):
       """实际扫描逻辑（支持取消）"""
       assets = []
       folders = list(library_path.iterdir())
       total = len(folders)

       for i, folder in enumerate(folders):
           if cancel_token.is_cancelled():
               logger.info("扫描已取消")
               return None

           # 扫描文件夹
           folder_assets = self._scan_category_folder(folder, ...)
           assets.extend(folder_assets)

           # 报告进度
           progress = int((i + 1) / total * 100)
           # 进度通过 on_progress 回调报告

       return assets
   ```

3. **UI 层适配**:
   - 显示进度条
   - 添加取消按钮
   - 扫描完成后刷新列表

#### ✅ 强制验收标准（Definition of Done）

**代码层面**:

1. **单元测试**: 创建 `tests/modules/asset_manager/logic/test_asset_manager_logic_fix04.py`

2. **必须通过的测试用例**:
   - `test_async_scan_with_cancellation()`: 扫描中途取消，立即停止
   - `test_async_scan_progress()`: 进度回调正确触发
   - `test_async_scan_large_library()`: 扫描 1000 个文件，UI 不阻塞

**运行层面**:

1. **UI 验证**:
   - 扫描 10GB 资产库，UI 保持响应（< 100ms 延迟）
   - 进度条实时更新
   - 点击取消按钮，1 秒内停止扫描

2. **性能验证**:
   - 扫描速度无退化
   - 内存占用合理

#### ⚠️ 回归风险提示

**高风险模块**: `modules/asset_manager/`

**测试清单**:

- [ ] 资产添加、删除、搜索功能正常
- [ ] 缩略图生成异步执行
- [ ] 资产迁移功能正常
- [ ] 资产预览功能正常

---

### FIX-05: 添加模块加载超时保护

**严重级别**: 🟠 严重  
**预估工时**: 3 小时  
**优先级**: P1

#### 📁 文件范围（禁止超出此范围）

**必须修改**:

- `core/bootstrap/app_bootstrap.py`
  - `AppBootstrap.run()` (Line 85-110): 添加超时定时器
  - 新增 `_on_module_load_timeout()`: 超时处理

**禁止修改**:

- `core/bootstrap/module_loader.py`
- 其他模块

#### 🔧 逻辑重构方案

**问题根源**: 模块加载无超时机制，某个模块卡死导致应用永久挂起。

**重构目标**: 添加 30 秒超时保护，超时后提供重试/跳过/退出选项。

**核心修改**:

1. **添加超时定时器**:

   ```python
   from PyQt6.QtCore import QTimer

   def run(self) -> int:
       # ... 现有代码 ...

       # 添加超时定时器
       self._module_load_timeout = QTimer()
       self._module_load_timeout.setSingleShot(True)
       self._module_load_timeout.timeout.connect(self._on_module_load_timeout)
       self._module_load_timeout.start(30000)  # 30 秒

       def on_complete(module_provider):
           self._module_load_timeout.stop()  # 停止超时定时器
           # ... 现有代码 ...

       self.module_loader.load_modules(on_progress, on_complete, on_error)
   ```

2. **实现超时处理**:

   ```python
   def _on_module_load_timeout(self):
       """模块加载超时处理"""
       self.logger.error("模块加载超时（30秒）")

       # 显示错误对话框
       from PyQt6.QtWidgets import QMessageBox
       msg = QMessageBox()
       msg.setIcon(QMessageBox.Icon.Warning)
       msg.setWindowTitle("模块加载超时")
       msg.setText("部分模块加载超时，请选择操作：")

       retry_btn = msg.addButton("重试", QMessageBox.ButtonRole.AcceptRole)
       skip_btn = msg.addButton("跳过失败模块", QMessageBox.ButtonRole.ActionRole)
       exit_btn = msg.addButton("退出应用", QMessageBox.ButtonRole.RejectRole)

       msg.exec()

       if msg.clickedButton() == retry_btn:
           # 重新加载模块
           self._retry_module_load()
       elif msg.clickedButton() == skip_btn:
           # 跳过失败模块，继续启动
           self._skip_failed_modules()
       else:
           # 退出应用
           self.exit_code = 1
           if self.app:
               self.app.quit()
   ```

#### ✅ 强制验收标准（Definition of Done）

**代码层面**:

1. **单元测试**: 创建 `tests/core/bootstrap/test_app_bootstrap_fix05.py`

2. **必须通过的测试用例**:
   - `test_module_load_timeout()`: 模拟模块加载卡死，30 秒后触发超时
   - `test_timeout_dialog_options()`: 验证对话框选项功能

**运行层面**:

1. **超时验证**:
   - 模拟模块加载卡死（sleep 60 秒）
   - 30 秒后弹出超时对话框
   - 对话框显示正确的选项

2. **功能验证**:
   - 选择"重试"：重新加载模块
   - 选择"跳过"：应用继续启动（功能降级）
   - 选择"退出"：应用正常退出

#### ⚠️ 回归风险提示

**高风险模块**: 所有模块（启动流程）

**测试清单**:

- [ ] 所有模块正常加载
- [ ] 单个模块失败不影响其他模块
- [ ] Splash Screen 进度条正确更新
- [ ] 更新检查异步执行不阻塞

---

### FIX-06: 授权请求添加重试机制

**严重级别**: 🟠 严重  
**预估工时**: 3 小时  
**优先级**: P1

#### 📁 文件范围（禁止超出此范围）

**必须修改**:

- `core/security/license_manager.py`
  - `LicenseManager._call_api()` (Line 369-414): 添加重试逻辑

**禁止修改**:

- `core/security/license_crypto.py`
- 其他模块

#### 🔧 逻辑重构方案

**问题根源**: 网络请求无重试，网络抖动导致授权验证失败。

**重构目标**: 添加指数退避重试，区分可重试错误和不可重试错误。

**核心修改**:

```python
def _call_api(self, endpoint: str, data: Dict, max_retries: int = 3) -> Tuple[bool, str, Optional[Dict]]:
    """调用授权 API（支持重试）"""
    import time
    import requests

    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=data, timeout=10)

            if response.status_code == 200:
                return True, "成功", response.json()
            elif response.status_code >= 500:
                # 服务器错误，可重试
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # 指数退避
                    logger.warning(f"服务器错误（{response.status_code}），{wait_time}秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    return False, f"服务器错误（{response.status_code}）", None
            else:
                # 客户端错误（如授权无效），不重试
                return False, f"授权验证失败（{response.status_code}）", None

        except requests.Timeout:
            if attempt < max_retries - 1:
                logger.warning(f"网络超时，{2 ** attempt}秒后重试...")
                time.sleep(2 ** attempt)
                continue
            return False, "网络超时，请检查网络连接", None

        except requests.RequestException as e:
            if attempt < max_retries - 1:
                logger.warning(f"网络错误: {e}，{2 ** attempt}秒后重试...")
                time.sleep(2 ** attempt)
                continue
            return False, f"网络错误: {e}", None

    return False, "重试次数已用尽", None
```

#### ✅ 强制验收标准（Definition of Done）

**代码层面**:

1. **单元测试**: 创建 `tests/core/security/test_license_manager_fix06.py`

2. **必须通过的测试用例**:
   - `test_retry_on_network_error()`: 模拟网络抖动，自动重试成功
   - `test_no_retry_on_client_error()`: 模拟授权无效（401），不重试
   - `test_exponential_backoff()`: 验证指数退避生效

**运行层面**:

1. **网络测试**:
   - 模拟 50% 丢包率，授权验证成功率 > 95%
   - 模拟服务器 500 错误，自动重试 3 次
   - 模拟授权无效（401），立即返回错误

2. **日志验证**:
   - 日志显示重试次数和原因
   - 错误信息明确区分网络错误和授权错误

#### ⚠️ 回归风险提示

**高风险模块**: `core/security/`

**测试清单**:

- [ ] 授权激活功能正常
- [ ] 授权验证功能正常
- [ ] 试用申请功能正常
- [ ] Freemium 模式：免费功能正常使用
- [ ] 付费功能：授权验证后解锁

---

### FIX-07: 线程服务清理超时优化

**严重级别**: 🟠 严重  
**预估工时**: 2 小时  
**优先级**: P1

#### 📁 文件范围（禁止超出此范围）

**必须修改**:

- `core/services/_thread_service.py`
  - `ThreadService.cleanup()` (Line 133-158): 优化清理逻辑
- `core/utils/thread_manager.py`
  - `EnhancedThreadManager.cleanup()` (Line 532-558): 添加详细日志

**禁止修改**:

- 其他模块

#### 🔧 逻辑重构方案

**问题根源**: 清理超时后无详细信息，无法判断哪些任务未完成。

**重构目标**: 记录未完成任务详情，优化轮询间隔。

**核心修改**:

1. **优化清理方法**:

   ```python
   def cleanup(self, timeout_ms: Optional[int] = 5000) -> None:
       """清理所有线程资源（优化版）"""
       logger.info("开始清理线程资源...")

       usage = self.get_thread_usage()
       active_count = usage.get('active', 0)

       if active_count > 0:
           logger.info(f"发现 {active_count} 个活跃线程，正在取消...")

           # 记录活跃任务详情
           active_threads = self._thread_manager.get_active_threads()
           for thread_info in active_threads:
               logger.info(
                   f"  - 任务: {thread_info.module_name}.{thread_info.task_name}, "
                   f"运行时长: {thread_info.elapsed_ms}ms"
               )

       # 调用底层清理
       success = self._thread_manager.cleanup(timeout_ms=timeout_ms)

       if success:
           logger.info("线程资源清理完成")
       else:
           # 记录未完成任务
           remaining = self._thread_manager.get_active_threads()
           logger.warning(f"线程资源清理超时（{len(remaining)} 个任务未完成）：")
           for thread_info in remaining:
               logger.warning(
                   f"  - 任务: {thread_info.module_name}.{thread_info.task_name}, "
                   f"运行时长: {thread_info.elapsed_ms}ms, "
                   f"状态: {thread_info.state}"
               )
   ```

2. **优化轮询间隔**:
   ```python
   # 在 EnhancedThreadManager.cleanup() 中
   while self._active_tasks and (time.time() - start) * 1000 < timeout_ms:
       time.sleep(0.1)  # 从 50ms 改为 100ms
   ```

#### ✅ 强制验收标准（Definition of Done）

**代码层面**:

1. **单元测试**: 创建 `tests/core/services/test_thread_service_fix07.py`

2. **必须通过的测试用例**:
   - `test_cleanup_with_timeout()`: 超时后记录未完成任务
   - `test_cleanup_normal()`: 正常清理，5 秒内完成

**运行层面**:

1. **日志验证**:
   - 正常退出：日志显示 "线程资源清理完成"
   - 超时退出：日志显示未完成任务的详细信息

2. **功能验证**:
   - 正常退出时所有线程在 5 秒内清理完成
   - 超时时进程在 6 秒内终止

#### ⚠️ 回归风险提示

**高风险模块**: 所有模块（退出流程）

**测试清单**:

- [ ] 正常退出流程
- [ ] 异常退出流程
- [ ] 长时间任务运行中退出
- [ ] 退出后进程完全终止

---

## 🟡 第三阶段：性能与规范优化

### OPT-01: 拼音缓存持久化

**严重级别**: 🟡 一般  
**预估工时**: 3 小时  
**优先级**: P2

#### 📁 文件范围（禁止超出此范围）

**必须修改**:

- `modules/asset_manager/logic/asset_manager_logic.py`
  - 新增 `_load_pinyin_cache()`: 从磁盘加载缓存
  - 新增 `_save_pinyin_cache()`: 保存缓存到磁盘
  - 修改 `_build_pinyin_cache()` (Line 2439): 调用加载方法
  - 修改 `add_asset()`: 增量更新缓存

**禁止修改**:

- 搜索引擎逻辑
- 其他模块

#### 🔧 逻辑重构方案

**问题根源**: 拼音缓存每次启动重新计算，1000 个资产耗时 2-5 秒。

**重构目标**: 缓存持久化到磁盘，启动时直接加载。

**核心修改**:

```python
def _load_pinyin_cache(self) -> Dict[str, Dict[str, str]]:
    """从磁盘加载拼音缓存"""
    cache_file = self.local_config_dir / "pinyin_cache.json"
    if cache_file.exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                logger.info(f"已加载拼音缓存（{len(cache_data)} 条）")
                return cache_data
        except Exception as e:
            logger.warning(f"加载拼音缓存失败: {e}")
    return {}

def _save_pinyin_cache(self):
    """保存拼音缓存到磁盘"""
    cache_file = self.local_config_dir / "pinyin_cache.json"
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(self._pinyin_cache_data, f, ensure_ascii=False, indent=2)
        logger.info(f"已保存拼音缓存（{len(self._pinyin_cache_data)} 条）")
    except Exception as e:
        logger.error(f"保存拼音缓存失败: {e}")
```

#### ✅ 强制验收标准（Definition of Done）

**代码层面**:

1. **单元测试**: 创建 `tests/modules/asset_manager/logic/test_asset_manager_logic_opt01.py`

2. **必须通过的测试用例**:
   - `test_pinyin_cache_persistence()`: 缓存保存和加载正确
   - `test_incremental_update()`: 添加资产时增量更新缓存

**运行层面**:

1. **性能验证**:
   - 首次启动：计算拼音缓存
   - 后续启动：直接加载缓存（< 100ms）
   - 添加 1000 个资产后，缓存自动更新

2. **文件验证**:
   - 缓存文件位置：`{local_config_dir}/pinyin_cache.json`
   - 缓存文件大小 < 1MB

#### ⚠️ 回归风险提示

**高风险模块**: `modules/asset_manager/`

**测试清单**:

- [ ] 拼音搜索功能正常
- [ ] 模糊搜索功能正常
- [ ] 缓存迁移功能正常
- [ ] 搜索性能无退化（< 50ms）

---

### OPT-02: 清理 AI 幻觉残留代码

**严重级别**: 🟡 一般  
**预估工时**: 1 小时  
**优先级**: P2

#### 📁 文件范围（禁止超出此范围）

**必须修改**:

- `modules/ai_assistant/logic/tools_registry.py`
  - 删除 `_tool_diff_config()` (Line 740-743)
  - 从工具列表中移除配置对比工具
- `modules/site_recommendations/__main__.py` (Line 27)
- `modules/config_tool/__main__.py` (Line 18)
- `modules/ai_assistant/ai_assistant.py` (Line 48)

**禁止修改**:

- 工具调用逻辑
- 其他模块

#### 🔧 逻辑重构方案

**问题根源**: 代码中存在 TODO 注释和占位符实现，误导开发者。

**重构目标**: 移除所有 TODO 和占位符，统一类型注释。

**核心修改**:

1. **移除占位符工具**:
   - 删除 `_tool_diff_config()` 方法
   - 从工具列表中移除

2. **统一类型注释**:

   ```python
   # 修改前
   self.ui: Optional[QWidget] = None  # TODO: 改为具体的 UI 类型

   # 修改后
   self.ui: Optional[QWidget] = None  # UI 组件（延迟初始化）
   ```

#### ✅ 强制验收标准（Definition of Done）

**代码层面**:

1. **静态检查**:

   ```bash
   # 检查 TODO 注释
   grep -r "TODO" --include="*.py" modules/ core/
   # 预期: 无结果（或仅有明确实现计划的 TODO）

   # 类型检查
   mypy modules/ core/ --ignore-missing-imports
   # 预期: 无错误

   # 代码风格检查
   flake8 modules/ core/
   # 预期: 无警告
   ```

**运行层面**:

1. **功能验证**:
   - AI 助手所有工具正常调用
   - 移除的工具不可调用
   - 应用启动无异常

#### ⚠️ 回归风险提示

**高风险模块**: `modules/ai_assistant/`

**测试清单**:

- [ ] AI 助手所有可用工具测试
- [ ] 工具列表正确显示
- [ ] 类型检查通过
- [ ] 代码风格检查通过

---

### OPT-03: 统一变量命名规范

**严重级别**: 🟡 一般  
**预估工时**: 2 小时  
**优先级**: P2

#### 📁 文件范围（禁止超出此范围）

**必须修改**:

- 所有 Python 文件中的变量命名
- 使用 IDE 重构功能批量重命名

**禁止修改**:

- JSON 配置文件中的键名
- 数据库字段名
- API 接口参数名

#### 🔧 逻辑重构方案

**问题根源**: 混用 `snake_case` 和 `camelCase`，不符合 Python 规范。

**重构目标**: 统一使用 `snake_case` 命名。

**核心修改**:

1. **批量重命名**:
   - `assetId` → `asset_id`
   - `configDir` → `config_dir`
   - `moduleProvider` → `module_provider`

2. **使用 IDE 重构功能**:
   - VS Code: F2 重命名符号
   - PyCharm: Shift+F6 重命名

3. **添加 `.pylintrc` 配置**:
   ```ini
   [BASIC]
   variable-naming-style=snake_case
   function-naming-style=snake_case
   class-naming-style=PascalCase
   const-naming-style=UPPER_CASE
   ```

#### ✅ 强制验收标准（Definition of Done）

**代码层面**:

1. **静态检查**:
   ```bash
   pylint modules/ core/ --rcfile=.pylintrc
   # 预期: 无命名规范警告
   ```

**运行层面**:

1. **功能验证**:
   - 所有模块功能正常
   - API 兼容性无影响
   - 配置文件正常加载

#### ⚠️ 回归风险提示

**高风险模块**: 所有模块

**测试清单**:

- [ ] 所有模块完整功能测试
- [ ] API 兼容性测试
- [ ] 配置文件加载测试
- [ ] 数据库操作测试

---

### OPT-04: 添加性能监控埋点

**严重级别**: 🟡 一般  
**预估工时**: 2 小时  
**优先级**: P2

#### 📁 文件范围（禁止超出此范围）

**必须修改**:

- `core/utils/performance_monitor.py`
  - 新增 `@performance_monitor` 装饰器
  - 新增 `export_performance_data()` 方法
- 关键路径添加埋点:
  - `core/bootstrap/app_bootstrap.py`: 启动时间
  - `modules/asset_manager/logic/asset_manager_logic.py`: 扫描时间
  - `modules/ai_assistant/logic/context_manager.py`: 上下文构建时间

**禁止修改**:

- 业务逻辑
- 其他模块

#### 🔧 逻辑重构方案

**问题根源**: 无性能监控，无法及时发现性能退化。

**重构目标**: 添加关键路径性能埋点，定期输出报告。

**核心修改**:

```python
import time
import functools
from typing import Dict, List

class PerformanceMonitor:
    def __init__(self):
        self._metrics: Dict[str, List[float]] = {}

    def record(self, operation: str, duration_ms: float):
        """记录性能数据"""
        if operation not in self._metrics:
            self._metrics[operation] = []
        self._metrics[operation].append(duration_ms)

    def get_stats(self, operation: str) -> Dict[str, float]:
        """获取统计数据"""
        if operation not in self._metrics:
            return {}

        data = sorted(self._metrics[operation])
        count = len(data)

        return {
            "count": count,
            "p50": data[int(count * 0.5)],
            "p95": data[int(count * 0.95)],
            "p99": data[int(count * 0.99)],
            "avg": sum(data) / count,
        }

def performance_monitor(operation: str):
    """性能监控装饰器"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                duration_ms = (time.time() - start) * 1000
                monitor.record(operation, duration_ms)

                # 超过阈值告警
                if duration_ms > 1000:  # 1 秒
                    logger.warning(f"{operation} 耗时 {duration_ms:.2f}ms（超过阈值）")
        return wrapper
    return decorator

# 全局实例
monitor = PerformanceMonitor()
```

#### ✅ 强制验收标准（Definition of Done）

**代码层面**:

1. **单元测试**: 创建 `tests/core/utils/test_performance_monitor_opt04.py`

2. **必须通过的测试用例**:
   - `test_performance_monitor_decorator()`: 装饰器正确记录耗时
   - `test_performance_stats()`: 统计数据正确计算

**运行层面**:

1. **日志验证**:
   - 日志显示关键操作耗时
   - 超过阈值时显示告警

2. **数据导出**:
   - 性能数据可导出为 JSON
   - 包含 P50、P95、P99 指标

#### ⚠️ 回归风险提示

**高风险模块**: 所有模块

**测试清单**:

- [ ] 所有模块功能正常
- [ ] 性能无退化
- [ ] 日志大小合理（< 10MB/天）
- [ ] 监控开销 < 1ms

---

## 📝 执行流程与规范

### 任务执行流程

1. **任务领取**:
   - 从第一阶段开始，按顺序执行
   - 每次只领取一个任务
   - 完成验收后才能领取下一个

2. **代码修改**:
   - 严格按照文件范围修改
   - 禁止超出范围的修改
   - 使用 Git 分支管理（`fix/FIX-01`）

3. **单元测试**:
   - 必须编写单元测试
   - 测试覆盖率 > 80%
   - 所有测试必须通过

4. **功能测试**:
   - 按照验收标准执行测试
   - 记录测试结果
   - 截图或录屏关键步骤

5. **回归测试**:
   - 测试关联模块功能
   - 确保无破坏性修改
   - 记录测试结果

6. **代码审查**:
   - 提交 Pull Request
   - 等待代码审查
   - 根据反馈修改

7. **合并代码**:
   - 审查通过后合并到主分支
   - 更新版本号
   - 生成 Release Notes

### 提交规范

```
[fix] 修复线程管理器信号量泄漏 (FIX-01)

- 简化 _start_task 方法，消除 while True 循环
- 提取子方法确保单一职责
- 使用 semaphore_released 标志追踪所有权
- 确保所有异常路径释放信号量

验收:
- 单元测试: 3/3 passed
- 压力测试: 1000 任务通过
- 回归测试: AI 助手、资产管理、配置工具测试通过

v1.2.57
```

### 禁止事项

- ❌ 禁止一次修改多个任务
- ❌ 禁止跳过单元测试
- ❌ 禁止跳过回归测试
- ❌ 禁止修改公共接口（除非必要）
- ❌ 禁止删除现有功能（除非明确要求）
- ❌ 禁止引入新的依赖（除非必要）
- ❌ 禁止修改数据库结构（除非必要）

### 质量标准

1. **代码质量**:
   - 遵循 PEP 8 规范
   - 类型提示完整
   - 注释清晰
   - 无 TODO 残留

2. **测试质量**:
   - 单元测试覆盖率 > 80%
   - 功能测试完整
   - 回归测试通过
   - 性能测试达标

3. **文档质量**:
   - 提交信息清晰
   - 代码注释完整
   - 更新相关文档
   - Release Notes 详细

---

## 🎯 里程碑与交付

### 里程碑

| 里程碑             | 完成标准                      | 预期时间 | 交付物          |
| ------------------ | ----------------------------- | -------- | --------------- |
| M1: 致命修复完成   | FIX-01/02/03 全部验收通过     | 第 1 周  | 代码 + 测试报告 |
| M2: 稳定性增强完成 | FIX-04/05/06/07 全部验收通过  | 第 2 周  | 代码 + 测试报告 |
| M3: 性能优化完成   | OPT-01/02/03/04 全部验收通过  | 第 3 周  | 代码 + 测试报告 |
| M4: 生产环境发布   | 所有任务完成 + 7 天稳定性测试 | 第 4 周  | v1.3.0 Release  |

### 交付清单

每个任务完成后需要提交：

1. **代码**:
   - 修改的源代码
   - 单元测试代码
   - Git 提交记录

2. **测试报告**:
   - 单元测试结果
   - 功能测试结果
   - 回归测试结果
   - 性能测试结果（如适用）

3. **文档**:
   - 提交信息
   - 代码注释
   - 更新的文档（如适用）

4. **截图/录屏**:
   - 关键功能测试截图
   - 性能测试数据
   - 日志验证截图

---

## 📞 联系与支持

### 技术支持

- **问题反馈**: 通过 GitHub Issues 提交
- **代码审查**: 通过 Pull Request 进行
- **技术讨论**: 通过项目 Wiki 或邮件

### 参考资源

- **项目文档**: `Docs/` 目录
- **架构文档**: `.agents/summary/` 目录
- **开发指南**: `AGENTS.md`
- **代码规范**: `CONTRIBUTING.md`（如有）

---

**文档状态**: ✅ 已完成  
**最后更新**: 2026-04-28  
**维护者**: UE Toolkit 开发团队
