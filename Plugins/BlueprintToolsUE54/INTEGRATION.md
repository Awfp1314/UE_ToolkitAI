# Blueprint Tools UE5.4 - UE Toolkit Integration Guide

## Overview

This plugin provides Blueprint extraction and authoring capabilities for UE 5.4, designed to work with the UE Toolkit Python application via Remote Control API.

## Architecture

```
UE Toolkit (Python)
    ↓ HTTP Request (Port 30010)
Remote Control API
    ↓ RPC Call
BlueprintToolsSubsystem (C++)
    ↓ Blueprint Operations
UE Editor
```

## Setup in UE Toolkit

### 1. MCP Configuration

Add to your `config/mcp_config.json`:

```json
{
  "blueprint_tools_ue54": {
    "enabled": true,
    "base_url": "http://127.0.0.1:30010",
    "subsystem_path": "/Script/BlueprintToolsUE54.Default__BlueprintToolsSubsystem",
    "supported_operations": [
      "ExtractBlueprint",
      "CreateBlueprint",
      "ModifyBlueprintMembers",
      "CompileBlueprint",
      "SaveAssets",
      "SearchAssets",
      "ListAssets",
      "GetEditorContext"
    ]
  }
}
```

### 2. Python Client Usage

```python
from modules.ai_assistant.clients.ue_tool_client import UEToolClient

# Initialize client
client = UEToolClient(base_url="http://127.0.0.1:30010")

# Extract Blueprint
blueprint_data = client.execute_tool_rpc(
    "ExtractBlueprint",
    AssetPath="/Game/Blueprints/BP_Character",
    Scope="Full",
    GraphFilter="",
    bIncludeClassDefaults=False
)

# Create new Blueprint
create_result = client.execute_tool_rpc(
    "CreateBlueprint",
    AssetPath="/Game/Blueprints/BP_NewCharacter",
    ParentClassPath="/Script/Engine.Character",
    PayloadJson='{"variables": [{"name": "Health", "type": "float"}]}',
    bValidateOnly=False
)

# Add variable to existing Blueprint
modify_result = client.execute_tool_rpc(
    "ModifyBlueprintMembers",
    AssetPath="/Game/Blueprints/BP_Character",
    Operation="add_variable",
    PayloadJson='{"name": "MaxHealth", "type": "float", "defaultValue": 100.0}',
    bValidateOnly=False
)

# Compile Blueprint
compile_result = client.execute_tool_rpc(
    "CompileBlueprint",
    AssetPath="/Game/Blueprints/BP_Character"
)

# Save assets
save_result = client.execute_tool_rpc(
    "SaveAssets",
    AssetPathsJson='["/Game/Blueprints/BP_Character", "/Game/Blueprints/BP_NewCharacter"]'
)
```

### 3. Connection Detection

```python
import requests

def check_ue_connection():
    try:
        response = requests.get('http://127.0.0.1:30010/remote/info', timeout=1.5)
        return response.status_code == 200
    except:
        return False

# In your UI
if check_ue_connection():
    print("UE Editor connected (Blueprint Tools UE5.4)")
else:
    print("UE Editor not connected")
```

## Payload JSON Formats

### CreateBlueprint PayloadJson

```json
{
  "variables": [
    {
      "name": "Health",
      "type": "float",
      "defaultValue": 100.0,
      "category": "Stats",
      "tooltip": "Current health value"
    }
  ],
  "functions": [
    {
      "name": "TakeDamage",
      "category": "Combat"
    }
  ],
  "components": [
    {
      "name": "MeshComponent",
      "class": "/Script/Engine.StaticMeshComponent"
    }
  ]
}
```

### ModifyBlueprintMembers Operations

#### add_variable

```json
{
  "name": "MaxHealth",
  "type": "float",
  "defaultValue": 100.0,
  "category": "Stats",
  "tooltip": "Maximum health value",
  "replicated": false,
  "exposeOnSpawn": false
}
```

#### modify_variable

```json
{
  "name": "Health",
  "defaultValue": 150.0,
  "category": "Stats Updated",
  "tooltip": "Updated tooltip"
}
```

#### remove_variable

```json
{
  "name": "OldVariable"
}
```

#### add_function

```json
{
  "name": "Heal",
  "category": "Combat",
  "inputs": [{ "name": "Amount", "type": "float" }],
  "outputs": [{ "name": "Success", "type": "bool" }]
}
```

## Error Handling

All functions return JSON with `success` field:

```json
{
  "success": true,
  "assetPath": "/Game/Blueprints/BP_Character",
  "message": "Operation completed"
}
```

On error:

```json
{
  "success": false,
  "error": "Failed to load Blueprint: /Game/Blueprints/BP_Invalid"
}
```

## Logging

Plugin logs to UE Output Log with category `LogBlueprintTools`:

```
LogBlueprintTools: Log: ExtractBlueprint: /Game/Blueprints/BP_Character (Scope: Full)
LogBlueprintTools: Log: CreateBlueprint: /Game/Blueprints/BP_NewCharacter (Parent: /Script/Engine.Actor, ValidateOnly: 0)
```

## Registry File

Plugin writes heartbeat to temp directory:

- Windows: `%TEMP%/BlueprintTools/EditorRegistry/{instance-id}.json`
- Contains: project info, Remote Control port, process ID, plugin version

## Troubleshooting

### Connection Failed

1. Check Remote Control is enabled: Project Settings → Remote Control → Enable Web Server
2. Verify port 30010 is not blocked
3. Check UE Editor is running

### Blueprint Not Found

- Use full asset path: `/Game/Blueprints/BP_Character`
- Not relative path: `BP_Character`

### Compilation Errors

- Check `CompileBlueprint` response for error details
- Verify all referenced assets exist
- Check variable types are valid

## Version Compatibility

This plugin is built for **UE 5.4** specifically. API differences across versions:

- UE 4.x: Different Blueprint API, no Enhanced Input
- UE 5.0-5.3: Some API changes in Blueprint utilities
- UE 5.5+: New features may not be available

Use the corresponding version-specific plugin for your UE version.
