# UE Toolkit - AI Agent 开发指南

> 本文档为 AI 助手提供项目导航和开发指导

## 项目概览

**UE Toolkit** 是一个面向 Unreal Engine 开发者的 AI 驱动桌面工具箱，集成多模型 LLM、Function Calling 和实时 UE 编辑器通信。

- **版本**: v1.2.56
- **语言**: Python 3.9+
- **UI 框架**: PyQt6
- **许可证**: MIT
- **代码量**: ~100,000 行

## 快速导航

### 核心目录

```
Client/
├── main.py                     # 程序入口
├── version.py                  # 版本管理（单一真实来源）
├── core/                       # 核心系统（~20,000 行）
│   ├── bootstrap/              # 启动引导（6 阶段）
│   ├── security/               # 授权系统
│   ├── config/                 # 配置管理
│   ├── services/               # 核心服务
│   └── utils/                  # 工具类
├── modules/                    # 功能模块（~33,000 行）
│   ├── ai_assistant/           # AI 助手（16,129 行）
│   ├── asset_manager/          # 资产管理（11,780 行）
│   ├── my_projects/            # 工程管理（3,715 行）
│   ├── config_tool/            # 配置工具（1,278 行）
│   └── site_recommendations/   # 站点推荐（587 行）
└── Plugins/                    # UE 插件
    └── BlueprintExtractor/     # 蓝图提取插件（112 工具）
```

### 关键入口点

- **应用启动**: `main.py` → `core/bootstrap/app_bootstrap.py`
- **模块管理**: `core/module_manager.py`
- **AI 助手**: `modules/ai_assistant/ai_assistant.py`
- **资产管理**: `modules/asset_manager/asset_manager.py`
- **配置管理**: `core/config/config_manager.py`
- **授权系统**: `core/security/license_manager.py`

## 技术栈

### 核心技术

- **Python 3.9+**: 主要开发语言
- **PyQt6**: GUI 框架
- **SQLite**: 本地数据库
- **Ollama/OpenAI API**: LLM 集成
- **MCP**: Model Context Protocol

### 主要依赖

```python
PyQt6>=6.4.0                    # UI 框架
Pillow>=9.0.0                   # 图片处理
psutil>=5.9.0                   # 进程管理
pypinyin>=0.49.0                # 拼音转换
python-docx>=0.8.11             # Word 文档生成
httpx>=0.24.0                   # Ollama 客户端
keyring>=24.0.0                 # 密钥环集成
cryptography>=41.0.0            # 加密库
```

## 系统架构

### 启动流程（6 阶段）

```
1. 路径迁移检查 (5.1)
   └─> 检查旧版本配置路径，自动迁移

2. 应用初始化 (5.2)
   ├─> 创建 QApplication
   ├─> 初始化日志系统
   ├─> 单实例检查
   └─> 设置应用元数据

3. UI 准备 (5.3)
   └─> 创建 SplashScreen

4. 更新检查 (5.3.5)
   └─> 异步检查更新（非阻塞）

5. 模块加载 (5.4)
   ├─> 异步加载所有模块
   ├─> 进度回调更新 Splash
   └─> 完成后创建主窗口

6. 事件循环启动 (5.6)
   └─> 进入 Qt 事件循环
```

### 模块系统

所有功能模块必须实现 `IModule` 接口：

```python
class IModule(ABC):
    @abstractmethod
    def get_metadata(self) -> ModuleMetadata:
        """获取模块元数据"""
        pass

    @abstractmethod
    def get_widget(self) -> QWidget:
        """获取模块的UI组件"""
        pass

    @abstractmethod
    def initialize(self) -> bool:
        """初始化模块"""
        pass

    @abstractmethod
    def cleanup(self) -> CleanupResult:
        """清理模块资源"""
        pass
```

**模块发现**: 扫描 `modules/` 目录，读取 `manifest.json`

**模块加载**: 动态导入，调用 `initialize()`

**模块显示顺序**:

1. asset_manager（资产管理器）
2. ai_assistant（AI 助手）
3. config_tool（配置工具）
4. site_recommendations（网站推荐）

### 配置系统

**配置层次**:

```
应用配置 (app_config.json)
  └─> 全局配置 (global_config.json)
      └─> 模块配置 (module_config.json)
          └─> MCP 配置 (mcp.json)
```

**配置位置**: `%APPDATA%/ue_toolkit/`

**配置管理器**: `core/config/config_manager.py`

**配置验证**: 基于 JSON Schema

### AI 助手架构

**组件层次**:

```
ChatWindow (UI 层)
  └─> ContextManager (逻辑层)
      ├─> ToolsRegistry (工具注册表)
      ├─> LLMClientFactory (客户端工厂)
      │   ├─> OllamaLLMClient (本地模型)
      │   ├─> APILLMClient (云端 API)
      │   └─> UEToolClient (UE 编辑器工具)
      └─> MCPClient (MCP 协议客户端)
          └─> BlueprintExtractorBridge (MCP 桥接)
```

**工具系统**:

- 本地工具：资产搜索、配置对比、日志分析
- UE 工具：112 个（18 免费 + 10 付费，通过 MCP）

**对话流程**:

```
用户输入 → ChatWindow → ContextManager
  → 检查工具调用 → ToolsRegistry
  → 调用 LLM → 流式响应 → 更新 UI
```

## 开发模式

### 代码规范

- **文件编码**: UTF-8
- **日志**: 使用 `get_logger(__name__)`
- **异常处理**: 必须记录日志
- **类型提示**: 推荐使用 `typing` 模块

### Git 提交规范

```
feat: 新增功能
fix: 修复问题
docs: 文档更新
refactor: 重构
chore: 杂项维护
```

**提交信息格式**: `[类型] 描述` 或 `[类型] 描述 v版本号`

**功能性修改**: 需要更新 `version.py` 中的版本号

### 版本号管理

**位置**: `version.py`（单一真实来源）

**格式**: MAJOR.MINOR.PATCH

**更新规则**:

- MAJOR: 重大变更、不兼容的 API 修改
- MINOR: 新功能、向后兼容
- PATCH: bug 修复、小改进

### 日志系统

**使用方式**:

```python
from core.logger import get_logger
logger = get_logger(__name__)

logger.info("消息")
logger.warning("警告")
logger.error("错误", exc_info=True)
```

**日志位置**: `logs/runtime/ue_toolkit.log`

**日志级别**: DEBUG、INFO、WARNING、ERROR

## 常见开发任务

### 添加新模块

1. 在 `modules/` 创建模块目录
2. 创建 `manifest.json`:
   ```json
   {
     "name": "my_module",
     "display_name": "我的模块",
     "version": "1.0.0",
     "description": "模块描述",
     "author": "作者",
     "entry_point": "__main__:MyModule"
   }
   ```
3. 实现 `IModule` 接口
4. 创建 UI 组件
5. 实现业务逻辑
6. 测试模块加载

### 添加 AI 工具

1. 在 `modules/ai_assistant/logic/` 创建工具类
2. 实现工具方法:
   ```python
   class MyTool:
       def execute(self, **kwargs) -> Dict:
           return {"success": True, "data": {}}
   ```
3. 在 `ToolsRegistry` 注册工具
4. 定义工具 JSON Schema
5. 测试工具调用

### 修改配置

1. 更新配置模板 (`config_templates/`)
2. 更新 JSON Schema（如需要）
3. 添加配置升级逻辑（如需要）
4. 测试配置加载和保存

### 修改数据库

1. 设计新的表结构
2. 编写迁移脚本
3. 更新数据库接口
4. 测试数据库操作

## 重要约定

### 模块间通信

**通过逻辑层引用**:

```python
# AI 助手获取资产管理逻辑层引用
ai_assistant.set_asset_manager_logic(asset_manager_logic)
```

**通过信号槽**:

```python
# 发送信号
self.config_changed.emit(config_data)

# 连接信号
config_manager.config_changed.connect(self.on_config_changed)
```

### 线程管理

**使用 ThreadService**:

```python
from core.services import thread_service

def task(cancel_token):
    if cancel_token.is_cancelled():
        return
    # 执行任务

thread_service.run_async(
    task,
    on_result=lambda: print("完成"),
    on_error=lambda err: print(f"错误: {err}")
)
```

### 资源清理

**实现 cleanup 方法**:

```python
def cleanup(self) -> CleanupResult:
    try:
        # 清理资源
        return CleanupResult.success_result()
    except Exception as e:
        return CleanupResult.failure_result(str(e))
```

**支持协作式取消**:

```python
def request_stop(self) -> None:
    # 设置停止标志
    self._stop_flag = True
```

## 性能优化

### 启动优化

- 异步模块加载
- 延迟初始化 AI 模型
- 预创建 ChatWindow
- 非阻塞更新检查

### 运行时优化

- 线程池管理
- 资源懒加载
- LRU 缓存
- 数据库连接池

### 打包优化

- 排除 AI 库（numpy、torch、transformers）
- 使用 PyInstaller spec 文件
- 打包体积：50-80 MB（优化后）

## 安全注意事项

### 数据加密

- 授权数据：RSA 签名
- API 密钥：系统密钥环存储
- 敏感配置：AES 加密

### 通信安全

- HTTPS：云端通信
- 本地 Socket：仅监听 localhost
- 授权验证：每次工具调用检查

### 权限控制

- 模块级权限
- 工具级权限
- 功能分级（免费/付费）

## 测试

### 运行测试

```bash
pytest
```

### 代码覆盖率

```bash
pytest --cov=core --cov=modules
```

### 类型检查

```bash
mypy core/ modules/
```

### 代码风格

```bash
flake8 core/ modules/
```

### 安全扫描

```bash
bandit -r core/ modules/
```

## 故障排查

### 启动失败

- 检查日志：`logs/runtime/ue_toolkit.log`
- 检查依赖：`pip list`
- 检查配置：`%APPDATA%/ue_toolkit/`

### 模块加载失败

- 检查 `manifest.json` 格式
- 检查模块是否实现 `IModule` 接口
- 检查模块依赖是否安装

### AI 对话失败

- 检查 LLM 配置（Ollama 或 API）
- 检查网络连接
- 检查 API 密钥
- 检查日志中的错误信息

### UE 编辑器连接失败

- 确保 UE 编辑器正在运行
- 确保 Blueprint Extractor 插件已启用
- 检查端口 30010 和 9998 是否被占用

## 参考资源

### 文档

- **用户指南**: `Docs/USER_GUIDE.md`
- **MCP 集成**: `Docs/MCP_INTEGRATION.md`
- **核心系统**: `core/README.md`
- **配置管理**: `core/CONFIG_MANAGER_README.md`
- **更新检查**: `core/UPDATE_CHECKER_README.md`

### 详细文档（.agents/summary/）

- **代码库信息**: `codebase_info.md`
- **系统架构**: `architecture.md`
- **组件说明**: `components.md`
- **接口定义**: `interfaces.md`
- **数据模型**: `data_models.md`
- **工作流程**: `workflows.md`
- **依赖说明**: `dependencies.md`
- **知识库索引**: `index.md`

### 外部链接

- **官网**: [unrealenginetookit.top](https://unrealenginetookit.top)
- **GitHub**: [Awfp1314/UE_ToolkitAI](https://github.com/Awfp1314/UE_ToolkitAI)
- **问题反馈**: [GitHub Issues](https://github.com/Awfp1314/UE_ToolkitAI/issues)

## Custom Instructions

<!-- This section is maintained by developers and agents during day-to-day work.
     It is NOT auto-generated by codebase-summary and MUST be preserved during refreshes.
     Add project-specific conventions, gotchas, and workflow requirements here. -->

### 可用技能库 (Available Skills)

本项目可以使用以下技能库来辅助开发：

#### 1. aicoding

**用途**: AI 编码协作核心准则  
**何时使用**: 所有代码修改任务  
**核心原则**:

- Think Before Coding: 声明上下文边界，暴露假设
- Simplicity First: 绝对极简主义，禁止过早抽象
- Precise Modifications: 锁定手术半径，禁止附带重构
- Goal-Driven Execution: 定义成功标准，循环验证

#### 2. code-assist

**用途**: TDD 驱动的代码实现  
**何时使用**: 实现新功能、修复 bug  
**工作流程**: Explore → Plan → Code → Commit  
**特点**: 测试驱动开发，遵循现有模式，避免过度工程

#### 3. code-task-generator

**用途**: 生成结构化代码任务文件  
**何时使用**: 将需求转换为可执行任务  
**输入**: 粗略描述、想法或 PDD 实现计划  
**输出**: Amazon 格式的代码任务文件

#### 4. codebase-summary

**用途**: 分析代码库并生成文档  
**何时使用**: 初始化项目文档、更新文档  
**输出**: AGENTS.md、架构文档、组件说明等  
**特点**: 自动生成 Mermaid 图表，保留 Custom Instructions

#### 5. pdd

**用途**: Prompt-Driven Development 方法论  
**何时使用**: 将粗略想法转换为详细设计  
**工作流程**: 需求澄清 → 研究 → 设计 → 实现计划  
**输出**: 详细设计文档 + 实现计划 + TODO 列表

#### 6. eval

**用途**: EvalKit 评估框架  
**何时使用**: 创建 AI 模型评估、生成测试数据  
**特点**: 对话式评估，使用 Strands Evals SDK

#### 7. agent-sop-author

**用途**: 创建和验证 Agent SOP  
**何时使用**: 定义复杂的多步骤工作流程  
**输出**: RFC 2119 约束的 markdown 工作流程文档

### 项目特定约定

#### 模块开发约定

- 所有模块必须实现 `IModule` 接口
- 模块目录必须包含 `manifest.json`
- 模块初始化失败不应影响其他模块

#### 配置管理约定

- 配置文件必须包含 `_version` 字段
- 配置更改必须通过 `ConfigManager`
- 敏感配置使用系统密钥环存储

#### 线程管理约定

- 长时间任务必须使用 `ThreadService`
- 支持协作式取消（`CancelToken`）
- 线程间通信使用 Qt 信号槽

#### 日志记录约定

- 使用 `get_logger(__name__)` 获取日志器
- 异常必须记录完整堆栈 `exc_info=True`
- 日志级别：DEBUG（开发）、INFO（生产）

#### Git 工作流约定

- 功能分支命名：`feature/功能名称`
- 修复分支命名：`fix/问题描述`
- 提交前必须通过 `pytest` 和 `flake8`
- 功能性修改必须更新 `version.py`

#### 性能约定

- 启动时间目标：< 3 秒
- UI 响应时间目标：< 100ms
- 大文件操作必须异步处理
- 缓存策略：LRU，最大 100 项

#### 安全约定

- API 密钥禁止硬编码
- 授权检查在工具调用时进行
- 本地 Socket 仅监听 localhost
- 敏感数据传输使用 HTTPS

### 常见陷阱 (Gotchas)

#### 1. PyQt6 父子关系

**问题**: Widget 没有设置 parent 会成为独立窗口  
**解决**: 创建 Widget 时必须传递 parent 参数

#### 2. 线程安全

**问题**: 在非主线程更新 UI 导致崩溃  
**解决**: 使用 Qt 信号槽跨线程通信

#### 3. 模块加载顺序

**问题**: 模块间依赖导致初始化失败  
**解决**: 使用 `set_xxx_logic()` 延迟注入依赖

#### 4. 配置热重载

**问题**: watchdog 未安装导致热重载失败  
**解决**: 检查 watchdog 是否安装，失败时优雅降级

#### 5. AI 模型加载

**问题**: 首次加载模型导致 UI 卡顿  
**解决**: 使用延迟加载策略，在后台线程加载

#### 6. MCP 工具调用

**问题**: UE 编辑器未运行导致工具调用失败  
**解决**: 调用前检查编辑器连接状态

#### 7. 打包体积

**问题**: 包含 AI 库导致体积超过 300MB  
**解决**: 在 spec 文件中排除 numpy、torch、transformers

### 工作流程建议

#### 添加新功能

1. 使用 `pdd` 技能库生成设计文档
2. 使用 `code-task-generator` 生成任务文件
3. 使用 `code-assist` 技能库实现功能（TDD）
4. 更新相关文档
5. 提交代码并更新版本号

#### 修复 Bug

1. 使用 `aicoding` 技能库分析问题
2. 定位问题代码（锁定手术半径）
3. 编写测试用例复现问题
4. 修复问题（精确修改）
5. 验证修复并提交

#### 重构代码

1. 明确重构目标和范围
2. 编写测试用例保护现有功能
3. 小步重构，频繁验证
4. 更新相关文档
5. 提交代码

#### 更新文档

1. 使用 `codebase-summary` 技能库重新生成
2. 检查 Custom Instructions 是否保留
3. 手动补充项目特定约定
4. 提交文档更新
