# UE Toolkit 代码库基本信息

## 项目概述

**项目名称**: UE Toolkit (虚幻引擎工具箱)  
**版本**: v1.2.52  
**作者**: HUTAO  
**应用ID**: HUTAO.UEToolkit

## 项目描述

UE Toolkit 是一个专为虚幻引擎（Unreal Engine）开发者设计的桌面工具箱应用，提供工程管理、资产管理、AI助手和配置工具等核心功能。该应用采用 PyQt6 构建，支持模块化架构，集成了 AI 能力和 MCP (Model Context Protocol) 协议。

## 技术栈

### 核心框架

- **UI框架**: PyQt6 >= 6.4.0
- **Python版本**: Python 3.8+
- **架构模式**: 模块化插件架构

### 主要依赖

#### UI与图形处理

- PyQt6 (UI框架)
- Pillow (图片处理、缩略图生成)

#### 系统与进程管理

- psutil (进程管理、性能监控)
- watchdog (配置热重载)

#### AI与机器学习

- sentence-transformers (语义意图解析)
- faiss-cpu (向量存储和检索)
- numpy (数值计算，版本锁定 <2.0)
- httpx (Ollama 本地模型支持)

#### 文档与数据处理

- python-docx (Word 文档生成)
- PyYAML (YAML 配置文件支持)
- pypinyin (拼音转换、搜索功能)

#### 网络与API

- requests (HTTP 请求、URL 可达性检查)
- PyGithub (GitHub 代码搜索)

#### 安全与加密

- keyring (系统密钥环集成)
- cryptography (敏感数据加密)

#### 开发工具

- pytest, pytest-qt, pytest-cov (测试框架)
- mypy (类型检查)
- flake8 (代码质量检查)
- bandit (安全扫描)

## 项目结构

```
UE_Toolkit/
├── main.py                    # 应用程序入口
├── version.py                 # 版本号管理（单一真实来源）
├── requirements.txt           # Python 依赖
├── core/                      # 核心模块
│   ├── bootstrap/            # 应用启动引导
│   ├── config/               # 配置管理
│   ├── security/             # 安全与许可证管理
│   ├── services/             # 核心服务
│   ├── utils/                # 工具类
│   └── ai_services/          # AI 服务
├── modules/                   # 功能模块
│   ├── ai_assistant/         # AI 助手模块
│   ├── asset_manager/        # 资产管理模块
│   ├── config_tool/          # 配置工具模块
│   ├── my_projects/          # 工程管理模块
│   └── site_recommendations/ # 站点推荐模块
├── ui/                        # UI 组件
│   ├── dialogs/              # 对话框
│   ├── ue_main_window.py     # 主窗口
│   ├── settings_widget.py    # 设置界面
│   └── system_tray.py        # 系统托盘
├── scripts/                   # 脚本工具
│   ├── package/              # 打包脚本
│   ├── mcp_servers/          # MCP 服务器
│   ├── dev/                  # 开发工具
│   └── maintenance/          # 维护脚本
├── config/                    # 配置文件
│   └── mcp_config_template.json
├── Docs/                      # 文档
│   ├── USER_GUIDE.md         # 用户指南（中文）
│   ├── USER_GUIDE_EN.md      # 用户指南（英文）
│   └── MCP_INTEGRATION.md    # MCP 集成指南
└── logs/                      # 日志文件
    ├── runtime/              # 运行时日志
    ├── mcp/                  # MCP 日志
    └── build/                # 构建日志
```

## 支持的编程语言

- **Python**: 主要开发语言（100%）
- **JSON**: 配置文件
- **YAML**: 配置文件
- **Markdown**: 文档

## 代码统计

- **核心模块**: ~50+ Python 文件
- **功能模块**: 5 个主要模块
- **UI 组件**: ~10+ 组件
- **配置文件**: JSON/YAML 格式

## 许可证模式

- **Freemium 模式**: 基础功能免费，高级功能需要付费许可证
- **许可证验证**: 本地缓存 + 服务器端验证
- **试用机制**: 支持试用期和激活码激活

## 构建与打包

- **打包工具**: PyInstaller
- **目标平台**: Windows (主要)
- **打包配置**: scripts/package/config/ue_toolkit.spec
- **优化策略**: 排除未使用的 AI 依赖以减小体积（311MB → 50-80MB）

## 开发环境

- **推荐 IDE**: VS Code, PyCharm
- **Python 版本**: 3.8+
- **虚拟环境**: 推荐使用 venv 或 conda
- **国内镜像**: 支持清华、阿里云、中科大等镜像源

## 关键特性

1. **模块化架构**: 基于 manifest.json 的插件系统
2. **配置管理**: 支持模板、用户配置分离和自动备份
3. **AI 集成**: 支持多种 LLM 提供商和本地模型
4. **MCP 协议**: 标准化的工具调用接口
5. **单实例控制**: 防止应用重复启动
6. **主题系统**: 支持深色/浅色主题切换
7. **性能监控**: 内置性能监控和资源管理
8. **安全加密**: 敏感数据加密存储

## 更新日期

2026-04-26
