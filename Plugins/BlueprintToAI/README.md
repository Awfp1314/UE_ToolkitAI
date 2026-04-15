# BlueprintToAI Plugin

> Enable AI to read, create and modify Blueprints via Remote Control API

---

## 🎯 Features

- ✅ Extract Blueprint structure (nodes, variables, components)
- ✅ Create new Blueprints
- ✅ Modify existing Blueprints
- ✅ Save Blueprints to disk
- ✅ Works via UE Remote Control API (HTTP)
- ✅ No external dependencies (pure C++)

---

## 📦 Installation

### Step 1: Copy Plugin

```bash
YourProject/
└── Plugins/
    └── BlueprintToAI/  ← Copy this folder here
```

### Step 2: Enable Required Plugins

Open your project in UE Editor:

1. Edit → Plugins
2. Search for "Web Remote Control"
3. Enable it
4. Restart editor

### Step 3: Regenerate Project Files

Right-click on `.uproject` → Generate Visual Studio project files

### Step 4: Compile

Open the `.sln` file and build in Development Editor configuration.

---

## 🚀 Usage

### Enable Remote Control API

1. Edit → Project Settings
2. Search for "Remote Control"
3. Enable "Enable Remote Control Web Server"
4. Set port to 30010 (default)
5. Restart editor

### Test Connection

Open browser and navigate to:

```
http://127.0.0.1:30010/remote/info
```

You should see JSON response with server info.

---

## 🔧 API Reference

### Extract Blueprint

**Endpoint**: `/remote/object/call`

**Request**:

```json
{
  "objectPath": "/Script/BlueprintToAI.Default__BlueprintToAISubsystem",
  "functionName": "ExtractBlueprint",
  "parameters": {
    "AssetPath": "/Game/Blueprints/BP_MyActor",
    "Scope": "Compact"
  }
}
```

**Response**:

```json
{
  "success": true,
  "operation": "ExtractBlueprint",
  "blueprint": {
    "name": "BP_MyActor",
    "parentClass": "/Script/Engine.Actor",
    "graphs": [...],
    "variables": [...]
  }
}
```

**Scope Options**:

- `Minimal` - Only node types and connections (saves tokens)
- `Compact` - Adds positions and basic properties (default)
- `Full` - All information (for debugging)

### Create Blueprint

**Request**:

```json
{
  "objectPath": "/Script/BlueprintToAI.Default__BlueprintToAISubsystem",
  "functionName": "CreateBlueprint",
  "parameters": {
    "AssetPath": "/Game/Blueprints/BP_NewActor",
    "ParentClass": "/Script/Engine.Actor",
    "GraphDSL": "",
    "PayloadJson": "{}"
  }
}
```

**Response**:

```json
{
  "success": true,
  "operation": "CreateBlueprint",
  "assetPath": "/Game/Blueprints/BP_NewActor",
  "message": "Blueprint created successfully"
}
```

### Modify Blueprint

**Request (Add Variable)**:

```json
{
  "objectPath": "/Script/BlueprintToAI.Default__BlueprintToAISubsystem",
  "functionName": "ModifyBlueprint",
  "parameters": {
    "AssetPath": "/Game/Blueprints/BP_MyActor",
    "Operation": "add_variable",
    "PayloadJson": "{\"name\":\"Health\",\"type\":\"float\"}"
  }
}
```

**Request (Reparent)**:

```json
{
  "objectPath": "/Script/BlueprintToAI.Default__BlueprintToAISubsystem",
  "functionName": "ModifyBlueprint",
  "parameters": {
    "AssetPath": "/Game/Blueprints/BP_MyActor",
    "Operation": "reparent",
    "PayloadJson": "{\"parentClassPath\":\"/Script/Engine.Pawn\"}"
  }
}
```

### Save Blueprints

**Request**:

```json
{
  "objectPath": "/Script/BlueprintToAI.Default__BlueprintToAISubsystem",
  "functionName": "SaveBlueprints",
  "parameters": {
    "AssetPaths": [
      "/Game/Blueprints/BP_MyActor",
      "/Game/Blueprints/BP_MyCharacter"
    ]
  }
}
```

**Response**:

```json
{
  "success": true,
  "operation": "SaveBlueprints",
  "savedCount": 2,
  "failedCount": 0,
  "saved": ["/Game/Blueprints/BP_MyActor", "/Game/Blueprints/BP_MyCharacter"]
}
```

---

## 🐍 Python Integration

### Example: BlueprintTool Class

```python
import requests

class BlueprintTool:
    def __init__(self, host="127.0.0.1", port=30010):
        self.base_url = f"http://{host}:{port}"
        self.subsystem_path = "/Script/BlueprintToAI.Default__BlueprintToAISubsystem"

    def extract_blueprint(self, asset_path, scope="Compact"):
        return self._call("ExtractBlueprint", {
            "AssetPath": asset_path,
            "Scope": scope
        })

    def create_blueprint(self, asset_path, parent_class):
        return self._call("CreateBlueprint", {
            "AssetPath": asset_path,
            "ParentClass": parent_class,
            "GraphDSL": "",
            "PayloadJson": "{}"
        })

    def modify_blueprint(self, asset_path, operation, payload):
        import json
        return self._call("ModifyBlueprint", {
            "AssetPath": asset_path,
            "Operation": operation,
            "PayloadJson": json.dumps(payload)
        })

    def save_blueprints(self, asset_paths):
        return self._call("SaveBlueprints", {
            "AssetPaths": asset_paths
        })

    def _call(self, function_name, params):
        response = requests.post(
            f"{self.base_url}/remote/object/call",
            json={
                "objectPath": self.subsystem_path,
                "functionName": function_name,
                "parameters": params
            }
        )
        return response.json()

# Usage
tool = BlueprintTool()

# Read Blueprint
result = tool.extract_blueprint("/Game/Blueprints/BP_MyActor")
print(result)

# Create Blueprint
result = tool.create_blueprint(
    "/Game/Blueprints/BP_NewActor",
    "/Script/Engine.Actor"
)

# Add variable
result = tool.modify_blueprint(
    "/Game/Blueprints/BP_NewActor",
    "add_variable",
    {"name": "Health", "type": "float"}
)

# Save
result = tool.save_blueprints(["/Game/Blueprints/BP_NewActor"])
```

---

## 🔄 Supported UE Versions

- ✅ UE 5.4
- 🚧 UE 5.0 (coming soon)
- 🚧 UE 4.27 (coming soon)
- 🚧 UE 4.26 (coming soon)

---

## 📝 Current Status

### Phase 1: Core Framework ✅

- [x] Plugin structure
- [x] Subsystem implementation
- [x] Extract Blueprint (Minimal/Compact/Full)
- [x] Create Blueprint (basic)
- [x] Modify Blueprint (add_variable, reparent)
- [x] Save Blueprints

### Phase 2: DSL Support 🚧

- [ ] DSL parser
- [ ] Support Event nodes
- [ ] Support CallFunction nodes
- [ ] Support Variable nodes
- [ ] Support Cast nodes
- [ ] Support Branch nodes

### Phase 3: Advanced Features 🚧

- [ ] Add components
- [ ] Add functions
- [ ] Modify graphs with DSL
- [ ] More node types

---

## 🐛 Troubleshooting

### Plugin not loading

- Check that Web Remote Control plugin is enabled
- Regenerate project files
- Rebuild in Development Editor

### Remote Control not responding

- Check that Remote Control Web Server is enabled in Project Settings
- Check port 30010 is not blocked by firewall
- Restart editor

### Blueprint not found

- Use full content path (e.g., `/Game/Blueprints/BP_MyActor`)
- Check asset exists in Content Browser
- Check spelling and case sensitivity

---

## 📄 License

MIT License - Copyright (c) 2025 HUTAO

---

## 🤝 Contributing

This is a focused plugin for Blueprint AI operations. Contributions welcome!

---

**Author**: HUTAO  
**Version**: 1.0.0  
**Date**: 2025-01-XX
