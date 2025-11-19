# 启动流程重构实施任务 - Windsurf 提示词

## 🎯 任务目标

你需要根据 **任务文档** (`C:\Users\wang\Desktop\UI TO NEW\UE_TOOKITS_AI_NEW\.kiro\specs\startup-refactor\tasks.md`) 对项目进行启动流程重构。

任务文档已经过 Codex 审阅并批准（评分 9/10），包含 8 个主任务和 41 个子任务，是你实施的唯一依据。

---

## 📋 工作流程

### 对于每一个任务，你必须按照以下流程执行：

1. **阅读任务** - 从 `tasks.md` 中读取当前任务的详细要求
2. **理解需求** - 查看任务中标注的需求编号（如 `_需求: 2.1, 2.2_`），必要时参考需求文档
3. **实施任务** - 编写代码或修改文件，完成任务要求
4. **更新状态** - 将 `tasks.md` 中该任务的状态从 `- [ ]` 改为 `- [x]`
5. **提交 Git** - 使用清晰的 commit message 提交本次任务的所有更改
6. **继续下一个** - 重复以上步骤，直到所有任务完成

---

## ⚠️ 重要约束

### 1. 严格按顺序执行
- ✅ **必须**按照 `tasks.md` 中的任务顺序执行（任务 1 → 2 → 3 → ... → 8）
- ✅ 子任务也必须按顺序执行（如 2.1 → 2.2 → 2.3）
- ❌ **不要**跳过任务或改变顺序

### 2. 每个任务独立提交
- ✅ **每完成一个任务**就提交一次 Git
- ✅ Commit message 格式：`refactor(startup): 完成任务 X.Y - 任务简短描述`
  - 示例：`refactor(startup): 完成任务 1 - 创建 Bootstrap 目录结构`
  - 示例：`refactor(startup): 完成任务 2.1 - 实现日志系统配置`
- ✅ 每次提交必须包含：
  - 代码更改
  - `tasks.md` 状态更新（`- [ ]` → `- [x]`）

### 3. 确保可回滚
- ✅ 每次提交前确保代码可以运行（至少不会崩溃）
- ✅ 如果某个任务失败，可以通过 `git reset --hard HEAD~1` 回退
- ✅ 任务 6 要求保留旧代码作为注释，必须严格执行

### 4. 参考文档
- **主要依据**：`tasks.md` - 任务列表和实施步骤
- **需求参考**：`.kiro/specs/startup-refactor/requirements.md` - 理解需求背景
- **设计参考**：`.kiro/specs/startup-refactor/design.md` - 理解架构设计
- **代码参考**：现有的 `main.py`、`core/` 目录下的代码

---

## 📂 关键文件位置

```
UE_TOOKITS_AI_NEW/
├── .kiro/specs/startup-refactor/
│   ├── tasks.md           ← 任务文档（你的工作清单）
│   ├── requirements.md    ← 需求文档（参考）
│   └── design.md          ← 设计文档（参考）
├── main.py                ← 当前启动入口（任务 6 会修改）
├── core/
│   ├── bootstrap/         ← 任务 1 会创建这个目录
│   ├── app_manager.py     ← 现有的应用管理器
│   ├── module_manager.py  ← 现有的模块管理器
│   └── utils/
│       └── thread_utils.py
└── ui/
    ├── main_window.py     ← UEMainWindow
    └── splash_screen.py   ← SplashScreen
```

---

## 🔍 任务文档结构说明

`tasks.md` 包含 8 个主任务：

```markdown
- [ ] 1. 创建 Bootstrap 目录结构和基础文件
  - 创建 `core/bootstrap/` 目录
  - 创建 `core/bootstrap/__init__.py` 文件
  - ...
  - _需求: 8.1, 8.2, 8.3, 8.4_

- [ ] 2. 实现 AppInitializer 组件
  - [ ] 2.1 实现日志系统配置
    - 调用 `init_logging_system()` 配置日志
    - ...
    - _需求: 2.1_
  - [ ] 2.2 实现 QApplication 创建和配置
    - ...
  - [ ] 2.3 实现单例检查逻辑
    - ...

... (共 8 个主任务，41 个子任务)
```

**状态标记**：
- `- [ ]` = 未完成
- `- [x]` = 已完成

---

## 💡 实施建议

### 阶段 1：基础设施（任务 1）
- 创建目录和空文件
- 这是最简单的任务，用来熟悉流程

### 阶段 2：核心组件（任务 2-4）
- 实现 AppInitializer（封装日志、QApplication、单例检查）
- 实现 UILauncher（封装主题、Splash、主窗口）
- 实现 ModuleLoader（封装 AppManager 和 ModuleManager）
- **注意**：这些组件是独立的，可以逐个实现和测试

### 阶段 3：协调器（任务 5）
- 实现 AppBootstrap（协调四个阶段的启动流程）
- **注意**：这是最复杂的任务，包含 9 个子任务

### 阶段 4：集成（任务 6）
- 修改 `main.py`，使用新的 Bootstrap 系统
- **重要**：必须保留旧代码作为注释

### 阶段 5：测试（任务 7）
- 单元测试（7.1-7.4）
- 集成测试（7.5）
- 兼容性测试（7.6）
- 回滚测试（7.7）

### 阶段 6：收尾（任务 8）
- 更新文档
- 清理注释

---

## 🚨 常见问题和注意事项

### Q1: 如果不确定某个任务的具体实现？
**A**: 查看设计文档 (`design.md`)，里面有详细的接口设计和伪代码。

### Q2: 如果任务中提到的函数或类不存在？
**A**: 检查现有代码，可能需要从现有代码中提取或封装。

### Q3: 如果某个任务失败了怎么办？
**A**: 
1. 不要继续下一个任务
2. 分析失败原因
3. 修复问题
4. 重新提交
5. 如果无法修复，使用 `git reset --hard HEAD~1` 回退

### Q4: 测试任务（任务 7）需要写测试代码吗？
**A**: 是的，需要编写完整的测试代码，包括单元测试和集成测试。

### Q5: 如何验证任务完成？
**A**: 
- 代码符合任务要求
- 没有语法错误
- 相关的导入和依赖正确
- `tasks.md` 状态已更新
- Git 已提交

---

## 📝 Commit Message 模板

```bash
# 主任务
refactor(startup): 完成任务 1 - 创建 Bootstrap 目录结构

# 子任务
refactor(startup): 完成任务 2.1 - 实现日志系统配置
refactor(startup): 完成任务 2.2 - 实现 QApplication 创建和配置
refactor(startup): 完成任务 5.7 - 实现异常捕获和用户提示

# 测试任务
test(startup): 完成任务 7.1 - 单元测试 AppInitializer
test(startup): 完成任务 7.5.1 - 测试完整启动流程

# 文档任务
docs(startup): 完成任务 8 - 文档更新和清理
```

---

## ✅ 开始实施

现在请开始执行任务：

1. **首先**，阅读 `tasks.md` 的任务 1
2. **然后**，创建 `core/bootstrap/` 目录和相关文件
3. **接着**，更新 `tasks.md` 中任务 1 的状态为 `- [x]`
4. **最后**，提交 Git：`refactor(startup): 完成任务 1 - 创建 Bootstrap 目录结构`

**记住**：每个任务都要独立提交，确保可以安全回退！

---

**任务文档位置**: `C:\Users\wang\Desktop\UI TO NEW\UE_TOOKITS_AI_NEW\.kiro\specs\startup-refactor\tasks.md`

**开始吧！** 🚀

