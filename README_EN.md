# UE Toolkit - AI-Powered Unreal Engine Toolbox

<div align="center">

**[中文](README.md) | English**

![Version](https://img.shields.io/badge/version-1.2.52-blue)
![Python](https://img.shields.io/badge/python-3.9+-green)
![License](https://img.shields.io/badge/license-MIT-orange)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)

**An AI-Powered Desktop Toolbox for Unreal Engine Developers**

Integrated with Multi-Model LLM, Function Calling, and Real-time UE Editor Communication

[📖 User Guide](Docs/USER_GUIDE_EN.md) • [Features](#-features) • [Architecture](#-architecture) • [Quick Start](#-quick-start) • [Project Structure](#-project-structure)

</div>

---

## 🎯 Project Overview

UE Toolkit is a desktop toolbox for Unreal Engine developers, designed to improve development efficiency through modern technology stack.

### Key Highlights

- 🤖 **Multi-Model LLM Integration**: Supports Ollama local models and OpenAI/Claude/DeepSeek cloud APIs
- 🛠️ **Function Calling System**: 26+ business tools + 112 UE editor operation tools
- 🔌 **MCP Protocol Integration**: Standardized tool discovery and invocation protocol
- 🔍 **Semantic Search**: Vector retrieval based on sentence-transformers and FAISS
- 🔄 **Real-time Communication**: Bidirectional communication with UE Editor (Socket + HTTP)
- 💎 **Freemium Model**: Free basic features + paid premium features

---

## ✨ Features

### 1. AI Assistant Module

- **Multi-Model Support**: Ollama (local) + OpenAI/Claude (cloud)
- **Streaming Response**: SSE real-time output, ChatGPT-style interaction
- **Tool Calling**:
  - Asset search and management
  - Configuration template comparison
  - UE Blueprint extraction and analysis
  - Log analysis
  - Site recommendations
- **Context Management**: Multi-turn dialogue, session management, intelligent memory

### 2. Asset Management Module

- **Smart Search**: Pinyin search support, fuzzy matching
- **Batch Operations**: Drag-and-drop adding, batch import
- **Preview System**: Auto-generate thumbnails, real-time preview
- **Migration Tool**: One-click asset migration to UE projects
- **Category Management**: Custom categories, tag system

### 3. Project Management Module

- **Auto Discovery**: Scan all UE engines and projects on local machine
- **Quick Creation**: Create new projects from templates (C++/Blueprint)
- **Category Management**: Custom project categories
- **Quick Launch**: Right-click menu for quick project opening

### 4. Configuration Tool Module

- **Template Management**: Save and reuse common configurations
- **Quick Apply**: One-click configuration application to projects
- **Version Comparison**: Compare configuration differences between versions

### 5. Site Recommendations Module

- Curated UE resource sites
- Display by category (Resources, Tools, Forums, Learning)
- One-click access

---

## 🏗️ Architecture

### Tech Stack

```
AI/ML:    Ollama, OpenAI API, sentence-transformers, FAISS, MCP
Frontend: Python 3.9, PyQt6, QSS
Backend:  Flask, Vercel Serverless
Database: SQLite (local), Turso libSQL (cloud)
Plugin:   C++, Unreal Engine 5.6/5.7
Tools:    Git, PyInstaller, pytest, mypy
```

### System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Desktop Client                          │
│  ┌──────────────┐    Socket 9998    ┌────────────────┐  │
│  │  AI Assistant│◄────────────────►│  UE Plugin      │  │
│  │  Python+PyQt6│                  │  C++ + Python   │  │
│  └──────┬───────┘                  └────────────────┘  │
│         │ HTTPS                                         │
└─────────┼───────────────────────────────────────────────┘
          │
          ▼
┌──────────────────┐     libSQL      ┌──────────────┐
│  Web Server      │◄──────────────►│  Turso DB     │
│  Flask + Vercel  │                │  Tokyo Node   │
└──────────────────┘                └──────────────┘
```

### Core Modules

```
Client/
├── core/                       # Core system
│   ├── bootstrap/              # Startup bootstrap (6 phases)
│   ├── security/               # Authorization system
│   ├── config/                 # Configuration management
│   ├── services/               # Core services
│   └── utils/                  # Utilities
├── modules/                    # Feature modules
│   ├── ai_assistant/           # AI Assistant (16,129 lines)
│   ├── asset_manager/          # Asset Management (11,780 lines)
│   ├── my_projects/            # Project Management (3,715 lines)
│   ├── config_tool/            # Config Tool (1,278 lines)
│   └── site_recommendations/   # Site Recommendations (587 lines)
├── ui/                         # UI components
├── resources/                  # Resource files
└── Plugins/                    # UE Plugins
    ├── BlueprintExtractor/     # Blueprint Extractor (112 tools)
    └── BlueprintAnalyzer/      # Blueprint Analyzer (legacy)
```

---

## 🚀 Quick Start

### Requirements

- Windows 10/11
- Python 3.9+
- (Optional) Ollama (for local models)

### Install Dependencies

```bash
# Clone repository
git clone https://github.com/Awfp1314/UE_ToolkitAI.git
cd UE_ToolkitAI/Client

# Install dependencies
pip install -r requirements.txt
```

### Run Application

```bash
# Development mode
python main.py

# Build executable
python -m PyInstaller packaging/ue_toolkit.spec
```

### Configure AI Assistant

1. **Using Ollama (Local Model)**

   ```bash
   # Install Ollama
   # Download: https://ollama.com/

   # Pull model
   ollama pull qwen2.5:7b

   # Select Ollama mode in application settings
   ```

2. **Using API (Cloud Model)**
   - Select API mode in application settings
   - Fill in API Key and API URL
   - Supports OpenAI, Claude, DeepSeek, etc.

---

## 📁 Project Structure

```
Client/
├── main.py                     # Entry point
├── version.py                  # Version number
├── requirements.txt            # Dependencies
├── core/                       # Core system (~20,000 lines)
├── modules/                    # Feature modules (~33,000 lines)
├── ui/                         # UI components
├── resources/                  # Resource files
│   ├── icons/                  # SVG icons
│   └── styles/                 # QSS styles
├── Plugins/                    # UE Plugins
├── Docs/                       # Documentation
└── tests/                      # Tests
```

---

## 🎨 Feature Showcase

### AI Assistant

- Multi-turn dialogue support
- Streaming output
- Markdown rendering
- Tool calling (asset search, config comparison, blueprint analysis)

### Asset Management

- Pinyin search
- Batch adding
- Auto-generate thumbnails
- One-click migration to projects

### Project Management

- Auto-discover UE engines
- Create projects from templates
- Category management
- Quick launch

---

## 🔧 Development Guide

### Code Standards

- File encoding: UTF-8
- Logging: Use `get_logger(__name__)`
- Exception handling: Must log errors
- Type hints: Recommended to use `typing` module

### Module Development

Each module must implement the `IModule` interface:

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

### Testing

```bash
# Run tests
pytest

# Code coverage
pytest --cov=core --cov=modules
```

---

## 📊 Project Statistics

| Metric              | Value                      |
| ------------------- | -------------------------- |
| Total Lines of Code | ~100,000 lines             |
| Number of Modules   | 5                          |
| Number of Tools     | 138 (26 business + 112 UE) |
| Supported UE        | 5.4, 5.6, 5.7              |
| Package Size        | 50-80 MB (optimized)       |

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!

1. Fork this repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'feat: Add some AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Submit Pull Request

### Commit Convention

Use Conventional Commits:

```
feat: Add new feature
fix: Fix bug
docs: Update documentation
refactor: Refactor code
chore: Maintenance tasks
```

---

## 📄 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file for details

---

## 🔗 Links

- **Website**: [unrealenginetookit.top](https://unrealenginetookit.top)
- **Documentation**: [View Docs](Docs/)
- **Issue Tracker**: [GitHub Issues](https://github.com/Awfp1314/UE_ToolkitAI/issues)

---

## 📮 Contact

- **GitHub**: [@Awfp1314](https://github.com/Awfp1314)
- **Website**: [unrealenginetookit.top](https://unrealenginetookit.top)
- **Issues**: [GitHub Issues](https://github.com/Awfp1314/UE_ToolkitAI/issues)

---

## 🙏 Acknowledgments

- [Ollama](https://ollama.com/) - Local LLM runtime
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) - GUI framework
- [sentence-transformers](https://www.sbert.net/) - Text vectorization
- [FAISS](https://github.com/facebookresearch/faiss) - Vector search
- [Blueprint Extractor](https://github.com/SunGrow/ue-blueprint-extractor) - UE Plugin

---

<div align="center">

**⭐ If this project helps you, please give it a Star!**

Made with ❤️ and AI

</div>
