# BlueprintToAI 快速测试指南

> 5 分钟验证插件是否正常工作

---

## ✅ 测试清单

### 第 1 步：检查 Remote Control API

1. 确保 UE 编辑器正在运行
2. 打开浏览器，访问：`http://127.0.0.1:30010/remote/info`
3. 应该看到 JSON 响应，包含 `HttpRoutes` 和 `ActivePreset`

**✅ 成功**：看到 JSON 响应  
**❌ 失败**：检查 Remote Control Web Server 是否启用

---

### 第 2 步：检查 Python 连接状态

1. 启动 UE Toolkit Python 应用
2. 切换到 "AI 助手" 模块
3. 查看右上角的连接状态指示器

**✅ 成功**：显示 "UE 已连接"（绿色圆点）  
**❌ 失败**：显示 "UE 未连接"（灰色圆点）

**故障排查**：

- 确认 UE 编辑器正在运行
- 确认 Remote Control Web Server 已启用
- 检查端口 30010 是否被占用
- 查看 Python 应用的日志文件

---

### 第 3 步：测试蓝图提取（只读）

在 AI 助手中输入：

```
帮我看看 /Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter 这个蓝图
```

**预期行为**：

1. AI 调用 `extract_blueprint` 工具
2. 返回蓝图的结构信息（节点、变量、组件等）
3. AI 用自然语言描述蓝图的功能

**✅ 成功**：AI 能够读取并描述蓝图  
**❌ 失败**：查看错误信息

**常见错误**：

- `Asset not found` - 蓝图路径不存在，换一个存在的蓝图
- `Connection failed` - 连接问题，回到第 2 步
- `Subsystem not found` - 插件未加载，检查插件是否启用

---

### 第 4 步：测试蓝图创建（写入）

在 AI 助手中输入：

```
帮我创建一个简单的 Actor 蓝图，路径是 /Game/Test/BP_TestActor
```

**预期行为**：

1. AI 调用 `create_blueprint` 工具
2. 在 UE 编辑器中创建新蓝图
3. AI 提示创建成功

**✅ 成功**：在 Content Browser 中看到新蓝图  
**❌ 失败**：查看错误信息

**注意**：

- 确保目标文件夹存在（如 `/Game/Test/`）
- 如果蓝图已存在，会返回错误

---

### 第 5 步：测试蓝图修改（写入）

在 AI 助手中输入：

```
给 /Game/Test/BP_TestActor 添加一个 Health 变量，类型是 float，默认值 100
```

**预期行为**：

1. AI 调用 `modify_blueprint` 工具
2. 在蓝图中添加变量
3. AI 提示修改成功

**✅ 成功**：打开蓝图，看到新变量  
**❌ 失败**：查看错误信息

---

## 🐛 常见问题

### Q1: 连接状态一直显示 "UE 未连接"

**A**: 检查以下几点：

1. UE 编辑器是否正在运行？
2. Remote Control Web Server 是否启用？
   - `编辑 → 项目设置 → Plugins → Remote Control`
   - 勾选 `Enable Remote Control Web Server`
3. 端口是否正确？默认应该是 30010
4. 防火墙是否阻止了连接？

### Q2: 工具调用返回 "Subsystem not found"

**A**: 插件未正确加载：

1. 检查插件是否在 `编辑 → 插件` 中启用
2. 重启 UE 编辑器
3. 检查插件是否编译成功（查看 Output Log）

### Q3: 蓝图路径错误

**A**: 确保路径格式正确：

- ✅ 正确：`/Game/Blueprints/BP_MyActor`
- ❌ 错误：`Content/Blueprints/BP_MyActor`
- ❌ 错误：`BP_MyActor`

### Q4: 创建蓝图失败

**A**: 检查：

1. 目标文件夹是否存在？
2. 蓝图名称是否已存在？
3. 父类路径是否正确？（如 `/Script/Engine.Actor`）

---

## 📊 测试结果记录

| 测试项             | 状态 | 备注 |
| ------------------ | ---- | ---- |
| Remote Control API | ⬜   |      |
| Python 连接状态    | ⬜   |      |
| 蓝图提取（只读）   | ⬜   |      |
| 蓝图创建（写入）   | ⬜   |      |
| 蓝图修改（写入）   | ⬜   |      |

**图例**：

- ⬜ 未测试
- ✅ 通过
- ❌ 失败

---

## 🎯 下一步

如果所有测试都通过：

1. 尝试更复杂的蓝图操作
2. 测试 DSL 语法（如果已实现）
3. 测试保存功能

如果有测试失败：

1. 查看 UE Output Log
2. 查看 Python 应用日志（`logs/runtime/ue_toolkit.log`）
3. 参考 `PYTHON_INTEGRATION.md` 中的故障排查部分

---

**更新日期**：2025-01-XX  
**版本**：v1.0
