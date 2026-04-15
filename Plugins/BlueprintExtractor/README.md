# Blueprint Extractor Plugin

This is the Blueprint Extractor plugin for Unreal Engine, integrated into UE Toolkit.

## About

Blueprint Extractor is an open-source Unreal Engine plugin that provides structured JSON extraction and authoring capabilities for UE assets including Blueprints, Widgets, Materials, AI assets, and more.

- **Original Project**: [ue-blueprint-extractor](https://github.com/SunGrow/ue-blueprint-extractor)
- **License**: MIT License
- **Supported UE Versions**: 5.6, 5.7

## Features

The plugin exposes 112 tools covering:

- Blueprint extraction and authoring
- UMG Widget operations
- Material creation and modification
- AI assets (Behavior Trees, Blackboards, State Trees)
- Data assets and tables
- Animation assets
- Import operations
- Project automation
- Visual verification

## Integration with UE Toolkit

This plugin is integrated with UE Toolkit's AI Assistant through a tiered access model:

### Free Tier (18 Read-Only Tools)

- Extract Blueprint, Widget, Material structures
- Search and list assets
- Get editor context
- Extract data tables, enums, structs
- Extract animation and AI assets

### Pro Tier (94 Creation/Modification Tools)

- Create and modify Blueprints
- Create and modify Widgets
- Material authoring
- Asset import
- Save operations
- PIE control
- Live coding

## Requirements

The following Unreal Engine plugins must be enabled:

- EnhancedInput
- PropertyBindingUtils
- StateTree
- Web Remote Control

## Usage

The plugin communicates with UE Toolkit via HTTP Remote Control API on port 30010 (default).

All tool access is controlled by UE Toolkit's License Manager - free tools are available to all users, while pro tools require an activated license.

## Documentation

For detailed integration documentation, see:

- `BLUEPRINT_EXTRACTOR_INTEGRATION.md` in the Plugins directory
- Original project documentation at https://github.com/SunGrow/ue-blueprint-extractor

## License

This plugin is licensed under the MIT License. See LICENSE file for details.
