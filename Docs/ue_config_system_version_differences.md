# 虚幻引擎配置系统版本差异文档

## 文档概述

本文档详细记录了虚幻引擎（Unreal Engine）从 UE4 到 UE5 各版本之间配置系统的重要差异，为配置工具开发提供技术参考。

**最后更新**: 2026-04-05  
**适用版本**: UE4.27 - UE5.6+

---

## 一、配置系统基础概念

### 1.1 配置文件类型

虚幻引擎的配置系统包含以下几种配置：

| 配置类型           | 存储位置                                                   | 作用范围   | 是否提交版本控制 |
| ------------------ | ---------------------------------------------------------- | ---------- | ---------------- |
| **项目设置**       | `Config/Default*.ini`                                      | 整个项目   | ✅ 是            |
| **编辑器偏好设置** | `Saved/Config/[Platform]/EditorPerProjectUserSettings.ini` | 单个开发者 | ❌ 否            |
| **游戏用户设置**   | `Saved/Config/[Platform]/GameUserSettings.ini`             | 玩家设置   | ❌ 否            |
| **运行时配置**     | `Saved/Config/[Platform]/*.ini`                            | 运行时修改 | ❌ 否            |

### 1.2 配置层级机制

虚幻引擎使用层级覆盖机制加载配置，后面的层级会覆盖前面的：

```
Engine/Config/Base.ini
  ↓ (覆盖)
Engine/Config/BaseEngine.ini
  ↓ (覆盖)
Engine/Config/[Platform]/[Platform]Engine.ini
  ↓ (覆盖)
[ProjectDirectory]/Config/DefaultEngine.ini      ← 项目默认配置
  ↓ (覆盖)
[ProjectDirectory]/Config/[Platform]/[Platform]Engine.ini
  ↓ (覆盖)
[ProjectDirectory]/Saved/Config/[Platform]/Engine.ini  ← 运行时配置
```

**关键规则**:

- `Config/Default*.ini` - 项目默认配置，作为基准
- `Saved/Config/*.ini` - 运行时配置，只保存与默认值不同的部分（差异存储）
- 不是简单的复制关系，而是增量覆盖

---

## 二、UE4 系列配置系统

### 2.1 UE4.27 及更早版本

#### 配置目录结构

```
[ProjectDirectory]/
├── Config/
│   ├── DefaultEngine.ini
│   ├── DefaultGame.ini
│   ├── DefaultInput.ini
│   └── DefaultEditor.ini
└── Saved/
    └── Config/
        ├── Windows/                    ← 编辑器配置目录
        │   ├── Engine.ini
        │   ├── Game.ini
        │   ├── Input.ini
        │   └── EditorPerProjectUserSettings.ini
        └── WindowsNoEditor/            ← 打包后配置目录
            ├── Engine.ini
            └── Game.ini
```

#### 关键特征

- ✅ 编辑器配置目录：`Saved/Config/Windows/`
- ✅ 打包后配置目录：`Saved/Config/WindowsNoEditor/`
- ✅ 自动保存所有配置修改到 `Saved/Config/`
- ✅ 不需要额外的白名单机制

---

## 三、UE5.0 - UE5.3 配置系统

### 3.1 重大变更：目录名称变更

#### 配置目录结构

```
[ProjectDirectory]/
├── Config/
│   ├── DefaultEngine.ini
│   ├── DefaultGame.ini
│   ├── DefaultInput.ini
│   └── DefaultEditor.ini
└── Saved/
    └── Config/
        ├── WindowsEditor/              ← 新：编辑器配置目录
        │   ├── Engine.ini
        │   ├── Game.ini
        │   ├── Input.ini
        │   └── EditorPerProjectUserSettings.ini
        └── WindowsNoEditor/            ← 保持不变
            ├── Engine.ini
            └── Game.ini
```

#### 关键变更

| 项目           | UE4.27             | UE5.0-5.3          |
| -------------- | ------------------ | ------------------ |
| 编辑器配置目录 | `Windows/`         | `WindowsEditor/`   |
| 打包后配置目录 | `WindowsNoEditor/` | `WindowsNoEditor/` |
| 自动保存机制   | ✅ 是              | ✅ 是              |

#### 兼容性影响

⚠️ **破坏性变更**: 从 UE4 升级到 UE5 时，配置文件路径需要更新

**迁移方案**:

```python
# 检测 UE 版本并使用正确的目录
if engine_version.startswith('4'):
    config_dir = "Saved/Config/Windows"
elif engine_version.startswith('5'):
    config_dir = "Saved/Config/WindowsEditor"
```

---

## 四、UE5.4 配置系统

### 4.1 重大变更：引入 [SectionsToSave] 白名单机制

#### 官方 Bug 报告

- **Issue ID**: UE-252267
- **标题**: "Config not saving correctly in UE 5.4"
- **链接**: https://issues.unrealengine.com/issue/UE-252267

#### 变更描述

> "Up to UE 5.3, when the user made changes to property pages, UE would automatically save every change to the 'Saved/Config/<CATEGORY>.ini' file. However, starting with UE 5.4, these settings are no longer automatically saved to the 'Saved/Config' folder unless their sections are explicitly opted-in by being added to a special [SectionsToSave] section."

#### 影响范围

❌ **默认行为变更**:

- UE 5.4+ 默认不再自动保存配置到 `Saved/Config/`
- 用户修改的设置在重启编辑器后会丢失
- 影响所有未明确添加到白名单的配置项

#### 解决方案

**方案 1: 全局启用自动保存**

在 `Config/DefaultGame.ini` 中添加：

```ini
[SectionsToSave]
bCanSaveAllSections=true
```

**方案 2: 指定允许保存的类**

```ini
[SectionsToSave]
+Classes=/Script/MyModule.MyClass
+Classes=/Script/Engine.GameUserSettings
```

#### 配置文件示例

```ini
; Config/DefaultGame.ini

[/Script/EngineSettings.GeneralProjectSettings]
ProjectID=12345678-1234-1234-1234-123456789012
ProjectName=MyProject

[SectionsToSave]
bCanSaveAllSections=true
```

---

## 五、UE5.5+ 配置系统

### 5.1 重大变更：配置加载机制重构

#### 关键变更

1. **强制要求 Default\*.ini 文件存在**
   - 如果 Hierarchy 中（除第一个条目外）没有实际存在的文件，则不会加载 Final ini 文件
   - 必须在 `Config/` 目录下创建对应的 `Default*.ini` 文件

2. **模块配置默认值变更**
   - `bCanSaveAllSections` 默认值从 `true` 改为 `false`（继承自 `Base.ini`）
   - 必须在 `Config/Default*.ini` 中显式设置 `bCanSaveAllSections=true`

3. **插件配置限制**
   - 插件只能使用插件名作为配置文件名（除非使用已知类别如 Engine、Game）
   - 必须在插件目录下创建 `Config/Default{PluginName}.ini`

#### 配置加载规则

```
模块配置 Hierarchy:
1. Engine/Config/Base.ini                          ← bCanSaveAllSections=false
2. Engine/Config/BaseEngine.ini
3. [ProjectDirectory]/Config/DefaultEngine.ini     ← 必须存在
4. [ProjectDirectory]/Saved/Config/[Platform]/Engine.ini

插件配置 Hierarchy:
1. Engine/Config/PluginBase.ini                    ← bCanSaveAllSections=true
2. [PluginDirectory]/Config/Default{PluginName}.ini ← 必须存在
3. [ProjectDirectory]/Saved/Config/[Platform]/{PluginName}.ini
```

#### 兼容性影响

⚠️ **破坏性变更**: 如果没有 `Default*.ini` 文件，`Saved/Config/` 中的配置不会被加载

**迁移方案**:

```python
def ensure_default_ini_exists(project_path):
    """确保 Default*.ini 文件存在（UE 5.5+）"""
    config_dir = project_path / "Config"
    config_dir.mkdir(exist_ok=True)

    # 确保基本的 Default 文件存在
    for ini_name in ["DefaultEngine.ini", "DefaultGame.ini"]:
        ini_file = config_dir / ini_name
        if not ini_file.exists():
            ini_file.write_text(
                "[SectionsToSave]\n"
                "bCanSaveAllSections=true\n"
            )
```

---

## 六、版本对比总表

| 特性                               | UE4.27     | UE5.0-5.3        | UE5.4             | UE5.5+            |
| ---------------------------------- | ---------- | ---------------- | ----------------- | ----------------- |
| 编辑器配置目录                     | `Windows/` | `WindowsEditor/` | `WindowsEditor/`  | `WindowsEditor/`  |
| 自动保存到 Saved/                  | ✅ 是      | ✅ 是            | ❌ 否（需白名单） | ❌ 否（需白名单） |
| 需要 [SectionsToSave]              | ❌ 否      | ❌ 否            | ✅ 是             | ✅ 是             |
| 需要 Default\*.ini                 | 推荐       | 推荐             | 推荐              | 强制              |
| 插件配置限制                       | 无         | 无               | 无                | 只能用插件名      |
| bCanSaveAllSections 默认值（模块） | true       | true             | false             | false             |
| bCanSaveAllSections 默认值（插件） | true       | true             | true              | true              |

---

## 七、配置工具开发建议

### 7.1 版本检测

```python
def detect_engine_version(project_path):
    """检测 UE 项目版本"""
    uproject_file = next(project_path.glob("*.uproject"))
    with open(uproject_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data.get("EngineAssociation", "5.0")
```

### 7.2 配置目录选择

```python
def get_config_directory(project_path, engine_version):
    """根据引擎版本获取正确的配置目录"""
    major_version = int(engine_version.split('.')[0])

    if major_version >= 5:
        return project_path / "Saved" / "Config" / "WindowsEditor"
    else:
        return project_path / "Saved" / "Config" / "Windows"
```

### 7.3 UE 5.4+ 兼容性处理

```python
def ensure_sections_to_save(project_path, engine_version):
    """确保 [SectionsToSave] 存在（UE 5.4+）"""
    major_version = int(engine_version.split('.')[0])
    minor_version = int(engine_version.split('.')[1]) if '.' in engine_version else 0

    # 只对 UE 5.4+ 处理
    if not (major_version == 5 and minor_version >= 4):
        return

    default_game_ini = project_path / "Config" / "DefaultGame.ini"

    if not default_game_ini.exists():
        default_game_ini.write_text(
            "[SectionsToSave]\n"
            "bCanSaveAllSections=true\n"
        )
    else:
        content = default_game_ini.read_text()
        if "[SectionsToSave]" not in content:
            content += "\n[SectionsToSave]\nbCanSaveAllSections=true\n"
            default_game_ini.write_text(content)
```

### 7.4 UE 5.5+ 兼容性处理

```python
def ensure_default_ini_exists(project_path, engine_version):
    """确保 Default*.ini 文件存在（UE 5.5+）"""
    major_version = int(engine_version.split('.')[0])
    minor_version = int(engine_version.split('.')[1]) if '.' in engine_version else 0

    # 只对 UE 5.5+ 处理
    if not (major_version == 5 and minor_version >= 5):
        return

    config_dir = project_path / "Config"
    config_dir.mkdir(exist_ok=True)

    # 确保基本的 Default 文件存在
    for ini_name in ["DefaultEngine.ini", "DefaultGame.ini"]:
        ini_file = config_dir / ini_name
        if not ini_file.exists():
            ini_file.write_text(
                "[SectionsToSave]\n"
                "bCanSaveAllSections=true\n"
            )
```

### 7.5 完整的配置应用流程

```python
def apply_config_to_project(template_path, project_path):
    """应用配置到 UE 工程（版本兼容）"""

    # 1. 检测 UE 版本
    engine_version = detect_engine_version(project_path)
    major_version = int(engine_version.split('.')[0])
    minor_version = int(engine_version.split('.')[1]) if '.' in engine_version else 0

    # 2. 确定目标目录
    target_config_dir = get_config_directory(project_path, engine_version)
    target_config_dir.mkdir(parents=True, exist_ok=True)

    # 3. 复制配置文件到 Config/ 目录（而不是 Saved/Config/）
    source_config_dir = template_path / "Config"
    project_config_dir = project_path / "Config"
    project_config_dir.mkdir(exist_ok=True)

    for ini_file in source_config_dir.glob("*.ini"):
        shutil.copy2(ini_file, project_config_dir / ini_file.name)

    # 4. UE 5.4+ 特殊处理
    if major_version == 5 and minor_version >= 4:
        ensure_sections_to_save(project_path, engine_version)

    # 5. UE 5.5+ 特殊处理
    if major_version == 5 and minor_version >= 5:
        ensure_default_ini_exists(project_path, engine_version)

    return True
```

---

## 八、常见问题 (FAQ)

### Q1: 为什么我的配置在 UE 5.4 中不保存了？

**A**: UE 5.4 引入了 `[SectionsToSave]` 白名单机制。需要在 `Config/DefaultGame.ini` 中添加：

```ini
[SectionsToSave]
bCanSaveAllSections=true
```

### Q2: 配置工具应该操作 Config/ 还是 Saved/Config/？

**A**: 应该操作 `Config/Default*.ini`（项目默认配置），而不是 `Saved/Config/`（运行时配置）。原因：

- `Saved/Config/` 会被引擎覆盖
- `Config/Default*.ini` 是配置的基准
- 引擎会自动将差异保存到 `Saved/Config/`

### Q3: UE4 项目升级到 UE5 后配置丢失怎么办？

**A**: 需要迁移配置目录：

```bash
# 复制配置文件
cp -r Saved/Config/Windows/* Saved/Config/WindowsEditor/
```

### Q4: UE 5.5 中为什么配置不生效？

**A**: UE 5.5 强制要求 `Config/Default*.ini` 文件存在。如果没有，创建最小化的文件：

```ini
[SectionsToSave]
bCanSaveAllSections=true
```

---

## 九、参考资料

### 官方文档

- [UE Configuration Files Documentation](https://docs.unrealengine.com/en-US/ProductionPipelines/ConfigurationFiles/)
- [UE Issue Tracker: UE-252267](https://issues.unrealengine.com/issue/UE-252267)

### 社区资源

- [UE Forum: Config not saving correctly in UE 5.4](https://forums.unrealengine.com/)
- [hyaniner.com: If SaveConfig() does not save ini in UE 5.4](https://hyaniner.com/en/blog/config-ini-of-ue-5.5-20250218/)
- [cnblogs: Unreal中ini配置文件的hierarchy](https://www.cnblogs.com/)

---

## 十、更新日志

| 日期       | 版本 | 更新内容                       |
| ---------- | ---- | ------------------------------ |
| 2026-04-05 | 1.0  | 初始版本，覆盖 UE4.27 - UE5.6+ |

---

**文档维护者**: UE Toolkit 开发团队  
**联系方式**: [项目仓库](https://github.com/your-repo)
