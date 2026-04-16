# Blueprint Tools UE5.4

Blueprint extraction and authoring plugin for Unreal Engine 5.4 with MCP (Model Context Protocol) integration.

## Features

- **Extract Blueprint**: Read Blueprint structure (variables, functions, components, graphs)
- **Create Blueprint**: Create new Blueprint assets with optional initial members
- **Modify Blueprint**: Add/remove/modify variables, functions, and components
- **Compile Blueprint**: Compile Blueprint and get error/warning feedback
- **Asset Management**: Search, list, and save Blueprint assets

## Installation

1. Copy the `BlueprintToolsUE54` folder to your project's `Plugins` directory
2. Enable the plugin in your project settings
3. Enable Remote Control Web Server in Project Settings → Remote Control
4. Restart Unreal Editor

## Remote Control API

The plugin exposes all functions through UE's Remote Control API (default port: 30010).

### Example: Extract Blueprint

```bash
curl -X POST http://127.0.0.1:30010/remote/object/call \
  -H "Content-Type: application/json" \
  -d '{
    "objectPath": "/Script/BlueprintToolsUE54.Default__BlueprintToolsSubsystem",
    "functionName": "ExtractBlueprint",
    "parameters": {
      "AssetPath": "/Game/Blueprints/BP_MyActor",
      "Scope": "Full"
    }
  }'
```

### Example: Create Blueprint

```bash
curl -X POST http://127.0.0.1:30010/remote/object/call \
  -H "Content-Type: application/json" \
  -d '{
    "objectPath": "/Script/BlueprintToolsUE54.Default__BlueprintToolsSubsystem",
    "functionName": "CreateBlueprint",
    "parameters": {
      "AssetPath": "/Game/Blueprints/BP_NewActor",
      "ParentClassPath": "/Script/Engine.Actor"
    }
  }'
```

## Python Integration (UE Toolkit)

```python
from modules.ai_assistant.clients.ue_tool_client import UEToolClient

client = UEToolClient(base_url="http://127.0.0.1:30010")

# Extract Blueprint
result = client.execute_tool_rpc(
    "ExtractBlueprint",
    AssetPath="/Game/Blueprints/BP_MyActor",
    Scope="Full"
)

# Create Blueprint
result = client.execute_tool_rpc(
    "CreateBlueprint",
    AssetPath="/Game/Blueprints/BP_NewActor",
    ParentClassPath="/Script/Engine.Actor"
)
```

## API Reference

### ExtractBlueprint

Extracts Blueprint structure to JSON.

**Parameters:**

- `AssetPath` (string): Full asset path
- `Scope` (string): ClassLevel | Variables | Components | FunctionsShallow | Full
- `GraphFilter` (string): Comma-separated graph names (empty = all)
- `bIncludeClassDefaults` (bool): Include CDO property values

**Returns:** JSON with Blueprint structure

### CreateBlueprint

Creates a new Blueprint asset.

**Parameters:**

- `AssetPath` (string): Full asset path for new Blueprint
- `ParentClassPath` (string): Parent class path (e.g., "/Script/Engine.Actor")
- `PayloadJson` (string): Optional JSON with initial members
- `bValidateOnly` (bool): Validate without creating

**Returns:** JSON with creation status

### ModifyBlueprintMembers

Modifies Blueprint members (variables, functions, components).

**Parameters:**

- `AssetPath` (string): Full asset path
- `Operation` (string): add_variable | remove_variable | modify_variable | add_function | remove_function
- `PayloadJson` (string): Operation-specific JSON payload
- `bValidateOnly` (bool): Validate without modifying

**Returns:** JSON with operation status

### CompileBlueprint

Compiles a Blueprint asset.

**Parameters:**

- `AssetPath` (string): Full asset path

**Returns:** JSON with compilation errors/warnings

### SaveAssets

Saves one or more assets.

**Parameters:**

- `AssetPathsJson` (string): JSON array of asset paths

**Returns:** JSON with save status

### SearchAssets

Searches for assets by name.

**Parameters:**

- `Query` (string): Search query
- `ClassFilter` (string): Filter by class (default: "Blueprint")
- `MaxResults` (int32): Maximum results (default: 50)

**Returns:** JSON array of matching assets

### ListAssets

Lists assets in a package path.

**Parameters:**

- `PackagePath` (string): Package path (e.g., "/Game/Blueprints")
- `bRecursive` (bool): Search subdirectories
- `ClassFilter` (string): Filter by class (empty = all)

**Returns:** JSON array of assets

### GetEditorContext

Returns current editor context.

**Returns:** JSON with project info, engine version, plugin version

## Version Support

This plugin is specifically built for **Unreal Engine 5.4**.

For other versions, see:

- UE 4.26: `BlueprintToolsUE426`
- UE 4.27: `BlueprintToolsUE427`
- UE 5.0: `BlueprintToolsUE50`
- UE 5.1: `BlueprintToolsUE51`
- UE 5.2: `BlueprintToolsUE52`
- UE 5.3: `BlueprintToolsUE53`
- UE 5.5: `BlueprintToolsUE55`
- UE 5.6: `BlueprintToolsUE56`
- UE 5.7: `BlueprintToolsUE57`

## License

See LICENSE file in plugin root directory.
