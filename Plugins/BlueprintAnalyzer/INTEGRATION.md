# Blueprint Analyzer - UE Toolkit Integration Guide

## Overview

This document describes how to integrate the Blueprint Analyzer plugin with UE Toolkit's AI Assistant.

## Architecture

```
User → AI Assistant → BlueprintAnalyzerClient → HTTP API → UE Editor (Plugin)
```

## Plugin Side (C++)

### Subsystem Path

```
/Script/BlueprintAnalyzer.Default__BlueprintAnalyzerSubsystem
```

### Available Functions

1. **ExtractBlueprint**
   - Parameters: `AssetPath` (string)
   - Returns: JSON with blueprint structure

2. **ExtractWidgetBlueprint**
   - Parameters: `AssetPath` (string)
   - Returns: JSON with widget hierarchy

3. **GetEditorContext**
   - Parameters: None
   - Returns: JSON with editor state

## Python Client Side

### Client Implementation

Create `modules/ai_assistant/clients/blueprint_analyzer_client.py`:

```python
from modules.ai_assistant.clients.ue_tool_client import UEToolClient

class BlueprintAnalyzerClient(UEToolClient):
    def __init__(self, base_url: str = "http://localhost:30010"):
        super().__init__(base_url)
        self.subsystem_path = "/Script/BlueprintAnalyzer.Default__BlueprintAnalyzerSubsystem"

    def extract_blueprint(self, asset_path: str) -> dict:
        """Extract blueprint structure"""
        return self.execute_tool_rpc("ExtractBlueprint", AssetPath=asset_path)

    def extract_widget_blueprint(self, asset_path: str) -> dict:
        """Extract widget blueprint structure"""
        return self.execute_tool_rpc("ExtractWidgetBlueprint", AssetPath=asset_path)

    def get_editor_context(self) -> dict:
        """Get current editor context"""
        return self.execute_tool_rpc("GetEditorContext")
```

### Tool Registration

Register tools in `ToolsRegistry`:

```python
# In tools_registry.py
{
    "name": "analyze_blueprint",
    "description": "分析蓝图结构，获取变量、函数和节点信息",
    "parameters": {
        "type": "object",
        "properties": {
            "asset_path": {
                "type": "string",
                "description": "蓝图资产路径，例如 /Game/Blueprints/MyBlueprint"
            }
        },
        "required": ["asset_path"]
    }
}
```

## HTTP API Examples

### Extract Blueprint

**Request:**

```http
PUT http://localhost:30010/remote/object/call
Content-Type: application/json

{
  "objectPath": "/Script/BlueprintAnalyzer.Default__BlueprintAnalyzerSubsystem",
  "functionName": "ExtractBlueprint",
  "parameters": {
    "AssetPath": "/Game/Blueprints/PlayerController"
  },
  "generateTransaction": false
}
```

**Response:**

```json
{
  "success": true,
  "assetPath": "/Game/Blueprints/PlayerController",
  "assetName": "PlayerController",
  "parentClass": "PlayerController",
  "variables": [
    {
      "name": "Health",
      "type": "float",
      "category": "Stats",
      "isArray": false
    }
  ],
  "functions": [
    {
      "name": "TakeDamage",
      "parameters": [
        {"name": "Amount", "type": "float"}
      ],
      "nodeCount": 15
    }
  ],
  "graphs": [
    {
      "name": "EventGraph",
      "nodeCount": 25,
      "nodes": [...]
    }
  ]
}
```

### Extract Widget Blueprint

**Request:**

```http
PUT http://localhost:30010/remote/object/call
Content-Type: application/json

{
  "objectPath": "/Script/BlueprintAnalyzer.Default__BlueprintAnalyzerSubsystem",
  "functionName": "ExtractWidgetBlueprint",
  "parameters": {
    "AssetPath": "/Game/UI/MainMenu"
  },
  "generateTransaction": false
}
```

**Response:**

```json
{
  "success": true,
  "assetPath": "/Game/UI/MainMenu",
  "assetName": "MainMenu",
  "widgetTree": {
    "root": {
      "name": "CanvasPanel_0",
      "class": "CanvasPanel",
      "isVariable": false,
      "children": [
        {
          "name": "StartButton",
          "class": "Button",
          "isVariable": true,
          "children": []
        }
      ]
    }
  },
  "variables": [...],
  "functions": [...]
}
```

### Get Editor Context

**Request:**

```http
PUT http://localhost:30010/remote/object/call
Content-Type: application/json

{
  "objectPath": "/Script/BlueprintAnalyzer.Default__BlueprintAnalyzerSubsystem",
  "functionName": "GetEditorContext",
  "parameters": {},
  "generateTransaction": false
}
```

**Response:**

```json
{
  "success": true,
  "projectName": "MyGame",
  "engineVersion": "5.4.0",
  "isPlayInEditor": false,
  "openAssets": [
    {
      "name": "PlayerController",
      "class": "Blueprint",
      "path": "/Game/Blueprints/PlayerController"
    }
  ],
  "totalAssets": 1523,
  "blueprintCount": 45,
  "widgetBlueprintCount": 12
}
```

## Version Compatibility

The plugin is designed to work across UE 5.x versions:

- **Source Distribution**: Plugin is distributed as source code
- **Auto-Compilation**: UE automatically compiles on first load
- **API Stability**: Uses only stable editor APIs
- **No Version Check**: Works with any UE 5.x version

## Testing

### Manual Testing

1. Start UE Editor with the plugin enabled
2. Enable Web Remote Control (default port 30010)
3. Use curl or Postman to test HTTP endpoints
4. Verify JSON responses

### Python Testing

```python
from modules.ai_assistant.clients.blueprint_analyzer_client import BlueprintAnalyzerClient

client = BlueprintAnalyzerClient()
if client.verify_connection():
    result = client.extract_blueprint("/Game/Blueprints/TestBP")
    print(result)
```

## Troubleshooting

### Connection Issues

- Verify UE Editor is running
- Check Web Remote Control is enabled
- Confirm port 30010 is not blocked

### Empty Results

- Use full asset paths (e.g., `/Game/...`)
- Ensure asset exists and is loaded
- Check UE Output Log for errors

### Compilation Errors

- Verify UE version is 5.0+
- Check all module dependencies are available
- Rebuild the plugin manually if needed

## Future Enhancements

Potential additions (not in current scope):

- Animation Blueprint support
- Behavior Tree analysis
- Material Graph extraction
- Asset dependency tracking
