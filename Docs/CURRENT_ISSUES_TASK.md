# UE Toolkit 当前问题清单

**文档版本**: v1.0  
**生成时间**: 2026-05-01  
**状态**: 待修复  
**说明**: 本文档仅记录问题，不包含解决方案

---

## 🔴 致命级问题

### ISSUE-01: 线程管理器信号量泄漏（已修复）

**状态**: ✅ 已修复（v5.3.0）  
**文件**: `core/utils/thread_manager.py`  
**位置**: `_start_task()` 方法（Line 108-263）

**问题描述**:

- 原问题：使用 `while True` 循环处理已取消任务，存在多个 return 路径，信号量释放逻辑复杂且容易出错
- 当前状态：已使用 `semaphore_acquired` 标志追踪所有权，确保在 `finally` 块中正确释放信号量
- 验证：代码中已有 `try-finally` 模式和详细的日志记录

**影响范围**:

- AI 助手长时间对话
- 资产批量导入
- 所有异步任务执行

---

### ISSUE-02: 上下文管理器内存泄漏（已修复）

**状态**: ✅ 已修复（v1.2.57）  
**文件**: `modules/ai_assistant/logic/context_manager.py`  
**位置**: `__init__()` 方法（Line 56-123）

**问题描述**:

- Line 95 创建了 `ThreadSafeLRUCache` 实例并赋值给 `self._context_cache`
- Line 113 又用普通字典 `{}` 覆盖了 `self._context_cache`
- Line 114 定义了 `self._cache_ttl = 60`
- 导致 LRU 缓存失效，内存无限增长

**修复方案**:

- 删除 Line 113-114 的重复赋值代码
- 保留 Line 95 的 `ThreadSafeLRUCache` 初始化
- 验证：所有缓存使用代码（`.get()`, `.set()`, `.clear()`, `.get_stats()`）完全兼容

**影响范围**:

- AI 助手长时间对话（500+ 轮）
- 上下文构建性能
- 内存持续增长

---

### ISSUE-03: 配置管理器竞态条件

**状态**: ❌ 未修复  
**文件**: `core/config/config_manager.py`  
**位置**:

- `_is_cache_valid()` 方法（Line 455-479）
- `_update_cache()` 方法（Line 479-490）
- `get_module_config()` 方法（Line 344-421）
- `get_module_config_async()` 方法（Line 421-455）

**问题描述**:

- 缓存读写操作无锁保护
- 多线程并发访问导致 TOCTOU（Time-of-check to time-of-use）漏洞
- 可能导致配置数据损坏或读取到不一致的数据
- 缺少深拷贝保护，外部修改会影响缓存

**影响范围**:

- 所有模块（配置系统是全局依赖）
- 多线程并发场景
- 配置热重载功能

---

## 🟠 严重级问题

### ISSUE-04: 资产扫描同步执行导致 UI 卡顿

**状态**: ⚠️ 部分修复  
**文件**: `modules/asset_manager/logic/asset_manager_logic.py`  
**位置**: `_scan_asset_library()` 方法（Line 245-348）

**问题描述**:

- 主扫描方法 `_scan_asset_library()` 是同步执行
- 扫描大型资产库（10GB+）时 UI 卡顿 10-30 秒
- 虽然有 `rescan_in_background()` 异步方法，但首次扫描仍是同步的
- 无法取消正在进行的扫描操作
- 无进度条显示

**影响范围**:

- 资产库首次加载
- 切换资产库
- 用户体验

---

### ISSUE-05: 模块加载无超时保护

**状态**: ❌ 未修复  
**文件**: `core/bootstrap/app_bootstrap.py`  
**位置**: `run()` 方法（Line 85-110）

**问题描述**:

- 模块加载过程无超时机制
- 某个模块卡死会导致应用永久挂起
- 用户无法判断是正常加载还是已卡死
- 无重试/跳过/退出选项

**影响范围**:

- 应用启动流程
- 所有模块加载
- 用户体验

---

### ISSUE-06: 授权请求无重试机制

**状态**: ❌ 未修复  
**文件**: `core/security/license_manager.py`  
**位置**: `_call_api()` 方法（Line 369-414）

**问题描述**:

- 网络请求无重试逻辑
- 网络抖动或临时故障导致授权验证失败
- 未区分可重试错误（网络超时、服务器 500）和不可重试错误（授权无效 401）
- 无指数退避策略

**影响范围**:

- 授权激活
- 授权验证
- 试用申请
- 网络不稳定环境

---

### ISSUE-07: 线程服务清理超时信息不足（已修复）

**状态**: ✅ 已修复（v1.2.59）  
**文件**:

- `core/services/_thread_service.py` - `cleanup()` 方法（Line 133-185）
- `core/utils/thread_manager.py` - `cleanup()` 方法（Line 532-560）

**问题描述**:

- 原问题：清理超时后无详细信息，无法判断哪些任务未完成及运行时长
- 当前状态：已增强日志输出，复用 `get_active_threads()` 方法获取详细任务信息
- 验证：日志格式测试通过，包含任务 ID、模块名、任务名、运行时长、开始时间、状态

**修复方案**:

1. `ThreadService.cleanup()`: 清理前记录所有活跃任务详情（模块名、任务名、运行时长、开始时间、任务 ID）
2. `EnhancedThreadManager.cleanup()`: 超时时记录未完成任务详情（增加状态字段）
3. 日志格式：结构化、grep 友好、包含完整追踪信息
4. 轮询间隔保持 50ms（适合清理场景）

**影响范围**:

- 应用退出流程 ✅
- 调试和故障排查 ✅
- 性能优化 ✅

---

## 🟡 一般级问题

### ISSUE-08: 拼音缓存未持久化

**状态**: ❌ 未实现  
**文件**: `modules/asset_manager/logic/asset_manager_logic.py`  
**位置**: 拼音缓存相关方法

**问题描述**:

- 拼音缓存每次启动重新计算
- 1000 个资产耗时 2-5 秒
- 缓存数据未保存到磁盘
- 增量更新未实现

**影响范围**:

- 应用启动速度
- 资产搜索性能
- 用户体验

---

### ISSUE-09: AI 幻觉残留代码（已修复）

**状态**: ✅ 已修复（v1.2.58）  
**文件**:

- `modules/ai_assistant/logic/tools_registry.py` - Line 162-166
- `modules/site_recommendations/__main__.py` - Line 27
- `modules/config_tool/__main__.py` - Line 18
- `modules/ai_assistant/ai_assistant.py` - Line 48
- `ui/settings_widget.py` - Line 2088

**问题描述**:

- 代码中存在多处 TODO 注释
- 部分 TODO 注释内容不明确或已过时
- 类型注释使用 `Optional[QWidget]` 而非具体类型
- 误导开发者和代码审查

**修复方案**:

1. `tools_registry.py`: 删除未实现的配置读取 TODO 注释块（Line 163-166）
2. `site_recommendations/__main__.py`: 修改类型为 `Optional['SiteRecommendationsUI']`，删除 TODO
3. `config_tool/__main__.py`: 修改类型为 `Optional['ConfigToolUI']`，删除 TODO
4. `ai_assistant.py`: 修改类型为 `Optional['ChatWindow']`，删除 TODO
5. `settings_widget.py`: 重写注释，删除"TODO"和"暂时"等暗示性词汇

**影响范围**:

- 代码可读性 ✅
- 类型检查 ✅
- 开发体验 ✅

---

### ISSUE-10: 变量命名不统一

**状态**: ⚠️ 需要全局检查  
**文件**: 多个文件

**问题描述**:

- 混用 `snake_case` 和 `camelCase` 命名
- 不符合 Python PEP 8 规范
- 降低代码可读性
- 可能存在的命名示例：
  - `assetId` vs `asset_id`
  - `configDir` vs `config_dir`
  - `moduleProvider` vs `module_provider`

**影响范围**:

- 代码规范性
- 代码可读性
- 团队协作

---

### ISSUE-11: 缺少性能监控埋点

**状态**: ❌ 未实现  
**文件**:

- `core/utils/performance_monitor.py`（需要新增）
- 关键路径需要添加埋点

**问题描述**:

- 无性能监控机制
- 无法及时发现性能退化
- 缺少关键操作耗时统计
- 无性能数据导出功能

**需要监控的关键路径**:

- 应用启动时间
- 资产库扫描时间
- AI 上下文构建时间
- 配置加载时间
- 模块初始化时间

**影响范围**:

- 性能优化
- 问题诊断
- 用户体验监控

---

## 📊 问题统计

| 严重级别 | 数量 | 已修复 | 未修复 | 部分修复 |
| -------- | ---- | ------ | ------ | -------- |
| 🔴 致命  | 3    | 2      | 1      | 0        |
| 🟠 严重  | 4    | 1      | 3      | 0        |
| 🟡 一般  | 4    | 1      | 2      | 1        |
| **总计** | 11   | 4      | 6      | 1        |

---

## 🎯 优先级建议

### P0（最高优先级）- 必须立即修复

1. ~~ISSUE-02: 上下文管理器内存泄漏~~ ✅ 已修复
2. ISSUE-03: 配置管理器竞态条件

### P1（高优先级）- 尽快修复

3. ISSUE-04: 资产扫描同步执行
4. ISSUE-05: 模块加载无超时保护
5. ISSUE-06: 授权请求无重试机制

### P2（中优先级）- 计划修复

6. ~~ISSUE-07: 线程服务清理超时信息不足~~ ✅ 已修复
7. ISSUE-08: 拼音缓存未持久化
8. ~~ISSUE-09: AI 幻觉残留代码~~ ✅ 已修复

### P3（低优先级）- 可选修复

9. ISSUE-10: 变量命名不统一
10. ISSUE-11: 缺少性能监控埋点

---

## 📝 备注

1. **ISSUE-01** 已在 v5.3.0 版本修复，使用 `try-finally` 模式确保信号量正确释放
2. **ISSUE-02** 已在 v1.2.57 版本修复，删除重复的缓存初始化代码，恢复 LRU 缓存功能
3. **ISSUE-03** 在多线程环境下可能导致配置数据损坏，需要尽快修复
4. **ISSUE-04** 虽然有异步扫描方法，但首次加载仍会卡顿，影响用户体验
5. **ISSUE-07** 已在 v1.2.59 版本修复，增强线程清理日志，包含完整任务追踪信息
6. **ISSUE-09** 已在 v1.2.58 版本修复，清理所有误导性 TODO 注释，修正类型注解

---

**文档状态**: ✅ 已完成  
**最后更新**: 2026-05-02 (ISSUE-07 已修复)  
**维护者**: UE Toolkit 开发团队
