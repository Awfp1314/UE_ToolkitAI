# AGENTS.md

Quick reference for AI agents working on UE Toolkit.

## Project Overview

UE Toolkit is a PyQt6 desktop app for Unreal Engine developers with AI assistant, asset management, and UE editor integration. ~100k lines Python, modular architecture, Windows-only.

## Critical Commands

### Development

```bash
# Run from Client/ directory
python main.py

# Reset license (testing)
python main.py --reset-license
```

### Packaging

```bash
# Build single-file EXE (from Client/)
python -m PyInstaller scripts/package/config/ue_toolkit.spec

# Build installer (requires Inno Setup)
# Edit version in scripts/package/config/UeToolkitpack.iss first
# Output: Desktop/UE_Toolkit_Setup_v{version}.exe
```

### Testing

No automated test suite. Manual testing only. Test files exist but are not run via pytest/CI.

## Version Management

**Single source of truth**: `version.py`

Update version in ONE place:

```python
VERSION = "1.2.56"  # Only edit this line
```

Version must also be updated in:

- `scripts/package/config/UeToolkitpack.iss` (line 6: `#define MyAppVersion`)
- `README.md` badge (line 7)

## Architecture

### Bootstrap Sequence (6 phases)

1. Path migration check (`core/bootstrap/path_migration.py`)
2. App initialization (`core/bootstrap/app_initializer.py`)
3. UI preparation with splash screen (`core/bootstrap/ui_launcher.py`)
4. Async module loading (`core/bootstrap/module_loader.py`)
5. Update check (non-blocking, `core/bootstrap/update_checker_integration.py`)
6. Event loop start

### Module System

All modules must implement `IModule` interface (`core/module_interface.py`):

- `get_metadata()` → ModuleMetadata
- `get_widget()` → QWidget
- `initialize()` → bool
- `cleanup()` → CleanupResult (not None!)
- Optional: `request_stop()` for graceful shutdown

Module discovery: `modules/*/manifest.json` required. Skip if `"_template": true`.

Module loading order determined by dependency resolution (topological sort with cycle detection).

### Key Directories

```
Client/
├── core/                    # Framework (config, security, services, utils)
│   ├── bootstrap/           # 6-phase startup
│   ├── config/              # ConfigManager (template + user config)
│   └── security/            # License, machine ID, feature gates
├── modules/                 # Feature modules (5 total)
│   ├── ai_assistant/        # LLM chat, MCP tools, 26 business tools
│   ├── asset_manager/       # Asset search, thumbnails, migration
│   ├── my_projects/         # UE project management
│   ├── config_tool/         # Config templates
│   └── site_recommendations/
├── ui/                      # Main window, splash, widgets
├── resources/               # Icons (SVG), styles (QSS)
├── scripts/
│   ├── mcp_servers/         # MCP bridge for UE plugin (stdio)
│   └── package/config/      # PyInstaller spec, Inno Setup script
└── Plugins/                 # UE C++ plugins (BlueprintExtractor)
```

## MCP Integration

AI assistant uses Model Context Protocol to call UE editor tools.

**Bridge**: `scripts/mcp_servers/blueprint_extractor_bridge.py` (stdio)
**Tools**: 26 defined in `blueprint_extractor_tools.json`
**Config**: `config/mcp_config.json` (template at `mcp_config_template.json`)

UE plugin must be running on `localhost:30010` (HTTP).

Free tools: read-only (18). Paid tools: create/modify (8).

## Configuration System

**Template-based**: Each module has `config_template.json` (defaults).
**User config**: Stored in `%APPDATA%/ue_toolkit/{module_name}/`
**Manager**: `core/config/config_manager.py` handles load/save/upgrade/backup

Never hardcode API keys, paths, or thresholds. Use config or `.env`.

## Packaging Quirks

**Single-file mode**: `runtime_tmpdir=None` uses `%TEMP%` (not Program Files, avoids permission issues)

**AI dependencies excluded**: `torch`, `transformers`, `sentence_transformers`, `faiss` removed from build to reduce size (311MB → 50-80MB). Ollama/API chat still works (uses `httpx`/`requests`). Semantic features disabled.

**7-Zip integration**: Installer optionally downloads 7-Zip (1.5MB) for 3-5x faster asset extraction.

## Commit Convention

Use Conventional Commits:

```
feat: 新增功能
fix: 修复问题
docs: 文档更新
refactor: 重构
chore: 杂项维护
```

Functional changes require version bump in `version.py`.

Format: `[类型] 描述` or `[类型] 描述 v版本号`

## Common Pitfalls

1. **Don't modify adjacent code**: Lock surgical radius. Only change what's required.
2. **Don't add unrequested features**: Absolute minimalism. No premature abstraction.
3. **Cleanup must return CleanupResult**: Old modules returning `None` are wrapped by `ModuleAdapter`.
4. **Module order matters**: Defined in `core/module_interface.py` ModuleProviderAdapter (asset_manager, ai_assistant, config_tool, site_recommendations).
5. **Windows paths**: Use `PathUtils` from `core/utils/path_utils.py`. Handle backslashes correctly.
6. **Thread safety**: Use `get_thread_manager()` from `core/utils/thread_manager.py` for async ops.
7. **Logging**: Always use `get_logger(__name__)` from `core/logger.py`. Never print().

## License System

Freemium model: Free features work without license. Paid features check license on use (not at startup).

License stored in 3 places: `%APPDATA%`, `%USERPROFILE%/.ue_toolkit_license`, registry `HKCU\Software\UEToolkit`.

Machine ID: `core/security/machine_id.py` (hardware-based, persistent).

## External Dependencies

**Required**: PyQt6, Pillow, psutil, pypinyin, python-docx, watchdog, requests, PyYAML, httpx, PyGithub, keyring, cryptography

**Optional (dev only)**: numpy, sentence-transformers, faiss-cpu (excluded from build)

**国内镜像**: Use Tsinghua mirror for faster pip installs:

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/
```

## Documentation

- User guide: `Docs/USER_GUIDE.md` (中文), `Docs/USER_GUIDE_EN.md` (English)
- MCP integration: `Docs/MCP_INTEGRATION.md`
- Core architecture: `core/README.md`
- Config system: `core/CONFIG_MANAGER_README.md`
- Update checker: `core/UPDATE_CHECKER_README.md`

## When Stuck

1. Check logs: `logs/runtime/ue_toolkit.log`, `logs/mcp/*.log`
2. Read module's `manifest.json` for metadata
3. Check `config_template.json` for expected config structure
4. Review `core/README.md` for architecture patterns
5. Search for similar patterns in existing modules (grep for method names)
