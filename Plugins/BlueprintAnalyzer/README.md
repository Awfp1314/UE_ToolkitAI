# Blueprint Analyzer Plugin

A lightweight Unreal Engine plugin that provides read-only blueprint analysis capabilities for AI assistant integration.

## Features

This plugin exposes 3 core tools through an Editor Subsystem:

1. **ExtractBlueprint** - Extracts blueprint structure (variables, functions, graphs, nodes)
2. **ExtractWidgetBlueprint** - Extracts UMG widget hierarchy and properties
3. **GetEditorContext** - Returns current editor state and project information

## Supported Versions

- **Minimum**: Unreal Engine 5.0
- **Tested**: 5.0, 5.4, 5.6, 5.7
- **Expected**: All UE 5.x versions (source-based compatibility)

## Installation

1. Copy the `BlueprintAnalyzer` folder to your project's `Plugins` directory
2. Restart Unreal Editor
3. The plugin will automatically compile on first load
4. Enable "Web Remote Control" plugin if not already enabled

## Usage

### Via Remote Control API (HTTP)

The plugin integrates with UE's Web Remote Control API (default port: 30010).

Example HTTP request:

```http
PUT http://localhost:30010/remote/object/call
Content-Type: application/json

{
  "objectPath": "/Script/BlueprintAnalyzer.Default__BlueprintAnalyzerSubsystem",
  "functionName": "ExtractBlueprint",
  "parameters": {
    "AssetPath": "/Game/Blueprints/MyBlueprint"
  }
}
```

### Via Blueprint/C++

```cpp
UBlueprintAnalyzerSubsystem* Subsystem = GEditor->GetEditorSubsystem<UBlueprintAnalyzerSubsystem>();
FString Result = Subsystem->ExtractBlueprint(TEXT("/Game/Blueprints/MyBlueprint"));
```

## Output Format

All functions return JSON strings with the following structure:

**Success:**

```json
{
  "success": true,
  "assetPath": "/Game/Blueprints/MyBlueprint",
  "assetName": "MyBlueprint",
  "variables": [...],
  "functions": [...],
  "graphs": [...]
}
```

**Error:**

```json
{
  "success": false,
  "error": "Error message here"
}
```

## Integration with UE Toolkit

This plugin is designed to work with UE Toolkit's AI Assistant module. The Python client communicates with the plugin via HTTP Remote Control API.

## License

MIT License - See LICENSE file for details

## Requirements

- Unreal Engine 5.0 or higher
- Web Remote Control plugin (included with UE)
- Editor-only (not for packaged games)

## Development

Built with minimal dependencies for maximum compatibility across UE5 versions. Only uses stable editor APIs:

- `UEditorSubsystem`
- `BlueprintGraph`
- `UMG/UMGEditor`
- `AssetRegistry`
- `Json/JsonUtilities`

## Troubleshooting

**Plugin won't load:**

- Ensure you're using UE 5.0 or higher
- Check that Web Remote Control plugin is enabled
- Rebuild the plugin if switching engine versions

**Empty results:**

- Verify the asset path is correct (use full path like `/Game/...`)
- Ensure the asset is a Blueprint or Widget Blueprint
- Check the Output Log for error messages

## Support

For issues and questions, please refer to the UE Toolkit documentation.
