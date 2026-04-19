# UE Toolkit - AI-Powered Unreal Engine Toolbox

<div align="center">

![Version](https://img.shields.io/badge/version-1.2.9-blue)
![Python](https://img.shields.io/badge/python-3.9+-green)
![License](https://img.shields.io/badge/license-MIT-orange)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)

**一款面向虚幻引擎开发者的 AI 驱动桌面工具箱**

集成多模型 LLM、Function Calling 和实时 UE 编辑器通信

[功能特性](#-功能特性) • [技术架构](#-技术架构) • [快速开始](#-快速开始) • [项目结构](#-项目结构)

</div>

---

## 🎯 项目简介

UE Toolkit 是一个面向 Unreal Engine 开发者的 AI 助手桌面应用，旨在通过 AI 技术提升开发效率。

### 核心亮点

- 🤖 **多模型 LLM 集成**：支持 Ollama 本地模型和 OpenAI/Claude/DeepSeek 云端 API
- 🛠️ **Function Calling 系统**：26+ 业务工具 + 112 个 UE 编辑器操作工具
- 🔌 **MCP 协议集成**：标准化的工具发现和调用协议
- 🔍 **语义检索**：基于 sentence-transformers 和 FAISS 的向量检索
- 🔄 **实时通信**：与 UE 编辑器的双向通信（Socket + HTTP）
- 💎 **Freemium 模式**：免费基础功能 + 付费高级功能

---

## ✨ 功能特性

### 1. AI 助手模块

- **多模型支持**：Ollama（本地）+ OpenAI/Claude（云端）
- **流式响应**：SSE 实时输出，ChatGPT 风格交互
- **工具调用**：
  - 资产搜索与管理
  - 配置模板对比
  - UE 蓝图提取与分析
  - 日志分析
  - 站点推荐
- **上下文管理**：多轮对话、会话管理、智能记忆

### 2. 资产管理模块

- **智能搜索**：支持拼音搜索、模糊匹配
- **批量操作**：拖放添加、批量导入
- **预览系统**：自动生成缩略图、实时预览
- **迁移工具**：一键迁移资产到 UE 工程
- **分类管理**：自定义分类、标签系统

### 3. 工程管理模块

- **自动发现**：扫描本机所有 UE 引擎和工程
- **快速创建**：从模板创建新工程（C++/蓝图）
- **分类管理**：自定义工程分类
- **快速启动**：右键菜单快速打开工程

### 4. 配置工具模块

- **模板管理**：保存和复用常用配置
- **快速应用**：一键应用配置到工程
- **版本对比**：对比不同版本的配置差异

### 5. 站点推荐模块

- 精选 UE 资源站点
- 按分类展示（资源、工具、论坛、学习）
- 一键访问

---

## 🏗️ 技术架构

### 技术栈

```
AI/ML:    Ollama, OpenAI API, sentence-transformers, FAISS, MCP
前端:     Python 3.9, PyQt6, QSS
后端:     Flask, Vercel Serverless
数据库:   SQLite (本地), Turso libSQL (云端)
插件:     C++, Unreal Engine 5.6/5.7
工具:     Git, PyInstaller, pytest, mypy
```

### 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    桌面客户端                             │
│  ┌──────────────┐    Socket 9998    ┌────────────────┐  │
│  │  AI 助手      │◄────────────────►│  UE 插件        │  │
│  │  Python+PyQt6 │                  │  C++ + Python   │  │
│  └──────┬───────┘                  └────────────────┘  │
│         │ HTTPS                                         │
└─────────┼───────────────────────────────────────────────┘
          │
          ▼
┌──────────────────┐     libSQL      ┌──────────────┐
│  Web 服务端       │◄──────────────►│  Turso 数据库  │
│  Flask + Vercel   │                │  东京节点      │
└──────────────────┘                └──────────────┘
```

### 核心模块

```
Client/
├── core/                       # 核心系统
│   ├── bootstrap/              # 启动引导（6 阶段）
│   ├── security/               # 授权系统
│   ├── config/                 # 配置管理
│   ├── services/               # 核心服务
│   └── utils/                  # 工具类
├── modules/                    # 功能模块
│   ├── ai_assistant/           # AI 助手（16,129 行）
│   ├── asset_manager/          # 资产管理（11,780 行）
│   ├── my_projects/            # 工程管理（3,715 行）
│   ├── config_tool/            # 配置工具（1,278 行）
│   └── site_recommendations/   # 站点推荐（587 行）
├── ui/                         # UI 组件
├── resources/                  # 资源文件
└── Plugins/                    # UE 插件
    ├── BlueprintExtractor/     # 蓝图提取插件（112 工具）
    └── BlueprintAnalyzer/      # 蓝图分析插件（旧版）
```

---

## 🚀 快速开始

### 环境要求

- Windows 10/11
- Python 3.9+
- （可选）Ollama（用于本地模型）

### 安装依赖

```bash
# 克隆仓库
git clone https://github.com/Awfp1314/UE_ToolkitAI.git
cd UE_ToolkitAI/Client

# 安装依赖（推荐使用国内镜像）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/
```

### 运行程序

```bash
# 开发模式
python main.py

# 打包为可执行文件
python -m PyInstaller packaging/ue_toolkit.spec
```

### 配置 AI 助手

1. **使用 Ollama（本地模型）**

   ```bash
   # 安装 Ollama
   # 下载：https://ollama.com/

   # 拉取模型
   ollama pull qwen2.5:7b

   # 在程序设置中选择 Ollama 模式
   ```

2. **使用 API（云端模型）**
   - 在程序设置中选择 API 模式
   - 填写 API Key 和 API URL
   - 支持 OpenAI、Claude、DeepSeek 等

---

## 📁 项目结构

```
Client/
├── main.py                     # 程序入口
├── version.py                  # 版本号
├── requirements.txt            # 依赖列表
├── core/                       # 核心系统（~20,000 行）
├── modules/                    # 功能模块（~33,000 行）
├── ui/                         # UI 组件
├── resources/                  # 资源文件
│   ├── icons/                  # SVG 图标
│   └── styles/                 # QSS 样式
├── Plugins/                    # UE 插件
├── Docs/                       # 文档
└── tests/                      # 测试
```

---

## 🎨 功能演示

### AI 助手

- 支持多轮对话
- 流式输出
- Markdown 渲染
- 工具调用（资产搜索、配置对比、蓝图分析）

### 资产管理

- 拼音搜索
- 批量添加
- 自动生成缩略图
- 一键迁移到工程

### 工程管理

- 自动发现 UE 引擎
- 从模板创建工程
- 分类管理
- 快速启动

---

## 🔧 开发指南

### 代码规范

- 文件编码：UTF-8
- 日志：使用 `get_logger(__name__)`
- 异常处理：必须记录日志
- 类型提示：推荐使用 `typing` 模块

### 模块开发

每个模块必须实现 `IModule` 接口：

```python
from core.module_interface import IModule

class MyModule(IModule):
    def get_metadata(self) -> ModuleMetadata:
        pass

    def get_widget(self) -> QWidget:
        pass

    def initialize(self) -> bool:
        pass

    def cleanup(self) -> CleanupResult:
        pass
```

### 测试

```bash
# 运行测试
pytest

# 代码覆盖率
pytest --cov=core --cov=modules
```

---

## 📊 项目统计

| 指标           | 数值                       |
| -------------- | -------------------------- |
| 总代码量       | ~100,000 行                |
| 模块数量       | 5 个                       |
| 工具数量       | 138 个（26 业务 + 112 UE） |
| 支持的 UE 版本 | 5.4, 5.6, 5.7              |
| 打包体积       | 50-80 MB（优化后）         |

---

## 🤝 贡献指南

欢迎贡献代码、报告问题或提出建议！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'feat: Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

### Commit 规范

使用 Conventional Commits：

```
feat: 新增功能
fix: 修复问题
docs: 文档更新
refactor: 重构
chore: 杂项维护
```

---

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

---

## 🔗 相关链接

- **官网**：[unrealenginetookit.top](https://unrealenginetookit.top)
- **文档**：[查看文档](Docs/)
- **问题反馈**：[GitHub Issues](https://github.com/Awfp1314/UE_ToolkitAI/issues)

---

## 📮 联系方式

- **GitHub**：[@Awfp1314](https://github.com/Awfp1314)
- **官网**：[unrealenginetookit.top](https://unrealenginetookit.top)
- **问题反馈**：[GitHub Issues](https://github.com/Awfp1314/UE_ToolkitAI/issues)

---

## 🙏 致谢

- [Ollama](https://ollama.com/) - 本地 LLM 运行时
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) - GUI 框架
- [sentence-transformers](https://www.sbert.net/) - 文本向量化
- [FAISS](https://github.com/facebookresearch/faiss) - 向量检索
- [Blueprint Extractor](https://github.com/SunGrow/ue-blueprint-extractor) - UE 插件

---

<div align="center">

**⭐ 如果这个项目对你有帮助，请给个 Star！**

Made with ❤️ and AI

</div>
