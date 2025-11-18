# Task 5: 类和函数体量重构设计文档

> **文档目的**: 详细规划 AssetManagerLogic 和 UEMainWindow 的重构方案
> **创建日期**: 2025-11-18
> **状态**: 设计阶段

---

## ⚠️ 重要约束与契约

### API 兼容性保证

**核心原则**: 重构后 `AssetManagerLogic` 的**所有公共方法签名和行为必须保持不变**，确保现有调用代码无需修改。

**公共 API 兼容清单** (必须保持不变):

```python
# 资产 CRUD
def add_asset(self, asset_path: Path, asset_type: AssetType, name: str = "",
              category: str = "默认分类", description: str = "",
              create_markdown: bool = False) -> Optional[Asset]

def remove_asset(self, asset_id: str) -> bool

def update_asset_info(self, asset_id: str, name: Optional[str] = None,
                      category: Optional[str] = None,
                      description: Optional[str] = None) -> bool

def update_asset_description(self, asset_id: str, description: str) -> bool

def get_asset(self, asset_id: str) -> Optional[Asset]

def get_all_assets(self, category: Optional[str] = None) -> List[Asset]

def get_all_asset_names(self) -> List[str]

# 分类管理
def add_category(self, category_name: str) -> bool

def remove_category(self, category_name: str) -> bool

def get_all_categories(self) -> List[str]

# 搜索与排序
def search_assets(self, search_text: str, category: Optional[str] = None) -> List[Asset]

def sort_assets(self, assets: List[Asset], sort_method: str) -> List[Asset]

# 预览功能
def preview_asset(self, asset_id: str, progress_callback=None,
                  preview_project_path: Optional[Path] = None) -> bool

def clean_preview_project(self) -> bool

def set_preview_project(self, project_path: Path) -> bool

def set_additional_preview_projects(self, project_paths: List[Path]) -> bool

def set_additional_preview_projects_with_names(self, projects: List[Dict[str, Any]]) -> bool

def get_preview_project() -> Optional[Path]

def get_additional_preview_projects() -> List[Dict[str, Any]]

# 资产迁移
def migrate_asset(self, asset_id: str, target_project: Path,
                  progress_callback=None) -> bool

# 截图处理
def process_screenshot(self, asset_id: str, screenshot_path: Path) -> bool

# 配置管理
def get_asset_library_path(self) -> Optional[Path]

def set_asset_library_path(self, library_path: Path) -> bool

# 信号（PyQt6 Signals）
asset_added: pyqtSignal(object)  # Asset
asset_removed: pyqtSignal(str)  # asset_id
assets_loaded: pyqtSignal(list)  # List[Asset]
preview_started: pyqtSignal(str)  # asset_id
preview_finished: pyqtSignal()
thumbnail_updated: pyqtSignal(str, str)  # asset_id, thumbnail_path
error_occurred: pyqtSignal(str)  # error_message
progress_updated: pyqtSignal(int, int, str)  # current, total, message
asset_selected: pyqtSignal(dict)  # asset info dict
```

**验证方式**:

- 重构前后运行相同的集成测试套件
- 使用 `mypy` 检查类型签名一致性
- 手动验证 UI 调用代码无需修改

### 配置路径与默认值

**全局配置路径**:

- Windows: `%APPDATA%/ue_toolkit/asset_manager.json`
- Linux/Mac: `~/.config/ue_toolkit/asset_manager.json`

**本地配置路径** (资产库目录下):

- 配置文件: `<资产库>/.asset_library.json`
- 缩略图目录: `<资产库>/.thumbnails/`
- 文档目录: `<资产库>/.documents/`
- 备份目录: `<资产库>/.backups/`

**默认配置值**:

```json
{
  "asset_library_path": null,
  "preview_project": null,
  "additional_preview_projects": [],
  "categories": ["默认分类"],
  "backup_interval_seconds": 300,
  "max_backups": 10
}
```

**环境变量**:

- `ASSET_MANAGER_MOCK_MODE`: Mock 模式开关 (0/1)
- `ASSET_LIBRARY_PATH`: 资产库路径（测试用）
- `UE_EDITOR_PATH`: UE 编辑器路径（可选）

**配置注入优先级** (从高到低):

1. **环境变量** (最高优先级)

   - `ASSET_LIBRARY_PATH` → 覆盖配置文件中的 `asset_library_path`
   - `UE_EDITOR_PATH` → 覆盖自动检测的 UE 编辑器路径
   - `ASSET_MANAGER_MOCK_MODE` → 强制启用/禁用 Mock 模式

2. **本地配置文件** (资产库目录下)

   - `<资产库>/.asset_library.json` → 覆盖全局配置

3. **全局配置文件**

   - `~/.config/ue_toolkit/asset_manager.json` → 用户级配置

4. **默认值** (最低优先级)
   - 代码中定义的默认值

**临时目录约定**:

- **生产环境**:

  - 预览临时文件: `<预览工程>/Content/_AssetManagerPreview/`
  - 迁移临时文件: `<目标工程>/Content/_AssetManagerTemp/`

- **测试环境** (Mock 模式):

  - 测试资产库: `<系统临时目录>/asset_manager_test/library/`
  - 测试预览工程: `<系统临时目录>/asset_manager_test/preview_project/`
  - 测试缩略图: `<系统临时目录>/asset_manager_test/thumbnails/`
  - 测试备份: `<系统临时目录>/asset_manager_test/backups/`

- **清理策略**:
  - 测试结束后自动清理临时目录
  - 生产环境的临时文件在操作完成后清理
  - 备份文件保留最近 10 个（可配置）

**硬编码约束**:

- ❌ 禁止硬编码路径（除了配置文件路径）
- ❌ 禁止硬编码 UE 编辑器路径
- ❌ 禁止直接操作真实资产库（测试时必须使用临时目录）
- ✅ 所有路径必须从配置或环境变量获取
- ✅ 所有路径必须使用 `pathlib.Path` 处理
- ✅ 测试时必须检查 `ASSET_MANAGER_MOCK_MODE` 环境变量

---

## 📊 现状分析

### 1. AssetManagerLogic (2350 行)

**基本信息**:

- 总行数: 2350
- 方法数: 53
- 平均方法行数: 42.2 行
- 超过 50 行的方法: 18 个
- 最大方法: `add_asset` (125 行)

**职责分析**:
根据方法分组，AssetManagerLogic 承担了以下职责：

1. **配置管理** (8 个方法)

   - `_load_config`, `_save_config`, `_load_local_config`, `_save_local_config`
   - `_migrate_config`, `_migrate_local_config`, `_migrate_thumbnails_and_docs`
   - `set_asset_library_path`

2. **资产 CRUD 操作** (10 个方法)

   - `add_asset`, `remove_asset`, `update_asset_info`, `update_asset_description`
   - `get_asset`, `get_all_assets`, `get_all_asset_names`
   - `_scan_asset_library`, `_create_asset_markdown`
   - `_move_asset_to_category`

3. **分类管理** (5 个方法)

   - `add_category`, `remove_category`, `get_all_categories`
   - `_sync_category_folders`

4. **搜索与排序** (4 个方法)

   - `search_assets`, `sort_assets`
   - `_get_pinyin`, `_get_asset_pinyin`, `_build_pinyin_cache`

5. **文件操作** (6 个方法)

   - `_safe_copytree`, `_safe_move_tree`, `_safe_move_file`
   - `_get_size`, `_calculate_size`, `_format_size`

6. **预览功能** (7 个方法)

   - `preview_asset`, `_do_preview_asset`, `_launch_unreal_project`
   - `_close_current_preview_if_running`, `_find_ue_process`
   - `clean_preview_project`, `set_preview_project`, `set_additional_preview_projects`

7. **截图处理** (3 个方法)

   - `process_screenshot`, `_find_screenshot`, `_find_thumbnail_by_asset_id`

8. **资产迁移** (1 个方法)

   - `migrate_asset`

9. **备份管理** (1 个方法)
   - `_should_create_backup`

**问题识别**:

- ❌ 职责过多，违反单一职责原则
- ❌ 配置管理、文件操作、预览功能等可以独立出来
- ❌ 大方法难以测试和维护
- ❌ 缺少类型提示

### 2. UEMainWindow (645 行)

**基本信息**:

- 总行数: 645
- 方法数: 17
- 平均方法行数: 35.1 行
- 超过 50 行的方法: 6 个
- 最大方法: `create_title_bar` (71 行)

**职责分析**:

1. **UI 创建** (4 个方法)

   - `create_title_bar`, `create_left_panel`, `create_right_panel`
   - `create_placeholder_page`

2. **模块管理** (3 个方法)

   - `load_initial_module`, `switch_module`, `_ensure_module_loaded`

3. **主题管理** (3 个方法)

   - `toggle_theme`, `_save_theme_setting`, `_update_theme_button_icon`

4. **窗口操作** (3 个方法)

   - `title_bar_mouse_press`, `title_bar_mouse_move`, `center_window`

5. **其他** (2 个方法)
   - `show_settings`, `closeEvent`

**问题识别**:

- ❌ UI 创建方法过长，难以阅读
- ❌ 主题管理逻辑可以提取
- ❌ 缺少类型提示

---

## 🎯 重构目标

### 核心原则

1. **单一职责**: 每个类只负责一个明确的职责
2. **小函数**: 单个函数不超过 50 行
3. **类型提示**: 所有公共方法添加完整的类型提示
4. **可测试性**: 拆分后的类更容易编写单元测试
5. **向后兼容**: 保持公共 API 不变，避免破坏现有代码

### 重构范围

- ✅ AssetManagerLogic: 拆分为多个职责明确的类
- ✅ UEMainWindow: 提取 UI 创建和主题管理逻辑
- ✅ 添加类型提示
- ✅ 编写单元测试

---

## 📐 重构设计

### 方案 A: AssetManagerLogic 重构

#### 新架构设计

```
modules/asset_manager/logic/
├── asset_manager_logic.py       # 主逻辑类（协调器）
├── asset_model.py                # 资产模型（已存在）
├── config_handler.py             # 配置管理器 ⭐ 新增
├── file_operations.py            # 文件操作工具 ⭐ 新增
├── search_engine.py              # 搜索引擎 ⭐ 新增
├── preview_manager.py            # 预览管理器 ⭐ 新增
├── screenshot_processor.py       # 截图处理器 ⭐ 新增
└── asset_migrator.py             # 资产迁移器 ⭐ 新增
```

#### 类职责划分

**⚠️ 重要约束**:

1. **导入路径保持不变**:

   - ✅ 保留 `modules/asset_manager/logic/asset_manager_logic.py` 文件
   - ✅ 保留 `from modules.asset_manager.logic.asset_manager_logic import AssetManagerLogic` 导入路径
   - ✅ 其他模块的导入代码无需修改

2. **接口契约严格执行**:

   - ✅ 所有新增类必须按照下面列出的方法签名实现
   - ❌ 不允许自由发挥添加额外的公共方法
   - ✅ 私有方法可以灵活调整

3. **委托模式实现**:
   - ✅ AssetManagerLogic 保留所有公共方法
   - ✅ 内部委托给新增的子模块类
   - ✅ 信号定义保持不变

---

**1. AssetManagerLogic (主协调器)** 📌 保留文件，内部重构

- 职责: 协调各个子模块，提供统一的公共 API
- **文件路径**: `modules/asset_manager/logic/asset_manager_logic.py` (保持不变)
- **导入路径**: `from modules.asset_manager.logic.asset_manager_logic import AssetManagerLogic` (保持不变)
- 保留方法:
  - 资产 CRUD: `add_asset`, `remove_asset`, `update_asset_info`, `get_asset`, `get_all_assets`
  - 分类管理: `add_category`, `remove_category`, `get_all_categories`
  - 搜索排序: `search_assets`, `sort_assets`
  - 预览: `preview_asset`, `clean_preview_project`
  - 迁移: `migrate_asset`
  - 截图: `process_screenshot`
- 依赖: ConfigHandler, FileOperations, SearchEngine, PreviewManager, ScreenshotProcessor, AssetMigrator
- 预计行数: ~800 行

**2. ConfigHandler (配置管理器)** ⭐ 新增

- 职责: 管理资产库配置（全局配置 + 本地配置）
- **文件路径**: `modules/asset_manager/logic/config_handler.py` (新建)
- **导出符号**: `ConfigHandler` (类名)
- 接口契约:
  ```python
  class ConfigHandler:
      def __init__(self, config_manager: ConfigManager, logger: Logger): ...
      def load_config(self) -> Dict[str, Any]: ...  # 加载全局配置
      def save_config(self, assets: List[Asset], categories: List[str]) -> bool: ...
      def load_local_config(self, library_path: Path) -> Optional[Dict[str, Any]]: ...
      def save_local_config(self, library_path: Path, assets: List[Asset],
                           categories: List[str], create_backup: bool = True) -> bool: ...
      def migrate_config(self, old_config: Dict[str, Any]) -> Dict[str, Any]: ...
      def get_asset_library_path(self) -> Optional[Path]: ...
      def set_asset_library_path(self, library_path: Path) -> bool: ...
  ```
- 异常策略: 配置加载/保存失败时记录错误日志，返回 False 或 None，不抛出异常
- 数据来源:
  - 全局配置: `~/.config/ue_toolkit/asset_manager.json`
  - 本地配置: `<资产库>/.asset_library.json`
  - 备份目录: `<资产库>/.backups/`
- 预计行数: ~300 行

**3. FileOperations (文件操作工具)** ⭐ 新增

- 职责: 提供安全的文件操作（复制、移动、大小计算）
- **文件路径**: `modules/asset_manager/logic/file_operations.py` (新建)
- **导出符号**: `FileOperations` (类名)
- 接口契约:
  ```python
  class FileOperations:
      def __init__(self, logger: Logger): ...
      def safe_copytree(self, src: Path, dst: Path,
                       progress_callback: Optional[Callable] = None) -> bool: ...
      def safe_move_tree(self, src: Path, dst: Path,
                        progress_callback: Optional[Callable] = None) -> bool: ...
      def safe_move_file(self, src: Path, dst: Path,
                        progress_callback: Optional[Callable] = None) -> bool: ...
      def calculate_size(self, path: Path) -> int: ...  # 返回字节数
      def format_size(self, size_bytes: int) -> str: ...  # 返回 "1.5 MB" 格式
  ```
- 异常策略: 文件操作失败时记录错误日志，返回 False，不抛出异常
- 边界条件:
  - 源路径不存在: 记录 ERROR 日志，返回 False
  - 目标路径已存在:
    - `safe_copytree`: 先删除目标目录，再复制（覆盖模式）
    - `safe_move_tree`: 记录 ERROR 日志，返回 False（不覆盖）
    - `safe_move_file`: 先删除目标文件，再移动（覆盖模式）
  - 权限不足: 记录 ERROR 日志，返回 False
  - 磁盘空间不足: 记录 ERROR 日志，返回 False
- Mock 模式行为:
  - 不执行真实文件操作
  - 使用 `tmp_path` fixture 提供的临时目录
  - 返回 True（模拟成功）
- 预计行数: ~250 行

**4. SearchEngine (搜索引擎)** ⭐ 新增

- 职责: 提供资产搜索和排序功能（支持拼音）
- **文件路径**: `modules/asset_manager/logic/search_engine.py` (新建)
- **导出符号**: `SearchEngine` (类名)
- 接口契约:
  ```python
  class SearchEngine:
      def __init__(self, logger: Logger): ...
      def search(self, assets: List[Asset], search_text: str,
                category: Optional[str] = None) -> List[Asset]: ...
      def sort(self, assets: List[Asset], sort_method: str) -> List[Asset]: ...
      def build_pinyin_cache(self, assets: List[Asset]) -> Dict[str, Dict[str, str]]: ...
      def get_pinyin(self, text: str) -> str: ...  # 返回拼音字符串
  ```
- 支持的排序方法: "添加时间（最新）", "添加时间（最旧）", "名称（A-Z）", "名称（Z-A）", "分类（A-Z）", "分类（Z-A）"
- 拼音缓存结构: `{asset_id: {'name_pinyin': str, 'desc_pinyin': str, 'category_pinyin': str}}`
- 拼音依赖降级策略:
  - 如果 `pypinyin` 已安装: 使用拼音排序（中文按拼音，英文按字母）
  - 如果 `pypinyin` 未安装: 记录 WARNING 日志，使用普通字符串排序（可能中文排序不准确）
  - 搜索功能不受影响（仍然支持中文搜索，只是不支持拼音首字母搜索）
- 异常策略: 搜索/排序失败时记录警告日志，返回原列表（不返回空列表，避免丢失数据）
- Mock 模式行为:
  - 正常执行搜索和排序逻辑
  - 使用测试数据（不涉及外部依赖）
- 预计行数: ~200 行

**5. PreviewManager (预览管理器)** ⭐ 新增

- 职责: 管理 UE 工程预览（启动、关闭、进程管理）
- **文件路径**: `modules/asset_manager/logic/preview_manager.py` (新建)
- **导出符号**: `PreviewManager` (类名)
- 接口契约:
  ```python
  class PreviewManager:
      def __init__(self, file_ops: FileOperations, logger: Logger): ...
      def preview_asset(self, asset: Asset, preview_project: Path,
                       progress_callback: Optional[Callable] = None) -> bool: ...
      def launch_unreal_project(self, project_path: Path) -> Optional[subprocess.Popen]: ...
      def close_current_preview(self) -> bool: ...
      def find_ue_process(self, project_path: Path) -> Optional[int]: ...  # 返回进程 PID
      def set_preview_project(self, project_path: Path) -> bool: ...
      def get_preview_project(self) -> Optional[Path]: ...
      def clean_preview_project(self) -> bool: ...  # 清理预览工程的临时文件
  ```
- 异常策略: 预览失败时记录错误日志，返回 False 或 None，不抛出异常
- 依赖外部环境:
  - UE 编辑器路径: 从注册表或环境变量获取
  - 预览工程: 必须是有效的 .uproject 文件
  - 进程管理: 使用 `psutil` 查找进程（如果可用），否则使用 `subprocess`
- Mock 模式行为:
  - `preview_asset`: 记录 INFO 日志，返回 True（不启动真实 UE 进程）
  - `launch_unreal_project`: 记录 INFO 日志，返回 None（不启动真实进程）
  - `close_current_preview`: 记录 INFO 日志，返回 True
  - `find_ue_process`: 返回 None（模拟未找到进程）
  - `clean_preview_project`: 记录 INFO 日志，返回 True
- 边界条件:
  - UE 编辑器路径不存在: 记录 ERROR 日志，返回 False
  - 预览工程路径无效: 记录 ERROR 日志，返回 False
  - 进程已存在: 记录 WARNING 日志，先关闭旧进程再启动新进程
- 预计行数: ~350 行

**6. ScreenshotProcessor (截图处理器)** ⭐ 新增

- 职责: 处理 UE 截图，生成缩略图
- **文件路径**: `modules/asset_manager/logic/screenshot_processor.py` (新建)
- **导出符号**: `ScreenshotProcessor` (类名)
- 接口契约:
  ```python
  class ScreenshotProcessor:
      def __init__(self, logger: Logger): ...
      def process_screenshot(self, asset: Asset, screenshot_path: Path,
                            thumbnails_dir: Path) -> bool: ...
      def find_screenshot(self, project_path: Path, timeout: int = 30) -> Optional[Path]: ...
      def find_thumbnail(self, asset_id: str, thumbnails_dir: Path) -> Optional[Path]: ...
  ```
- 截图查找策略:
  - 查找路径: `<UE项目>/Saved/Screenshots/Windows/`
  - 超时时间: 默认 30 秒
  - 文件格式: `.png`, `.jpg`
- 缩略图生成:
  - 目标大小: 256x256 (保持宽高比)
  - 保存路径: `<资产库>/.thumbnails/<asset_id>.png`
- 异常策略: 处理失败时记录警告日志，返回 False 或 None，不抛出异常
- Mock 模式行为:
  - `process_screenshot`: 记录 INFO 日志，复制测试图片到缩略图目录，返回 True
  - `find_screenshot`: 返回测试图片路径（`tests/fixtures/test_screenshot.png`）
  - `find_thumbnail`: 返回模拟的缩略图路径
- 边界条件:
  - 截图文件不存在: 记录 WARNING 日志，返回 None
  - 缩略图目录不存在: 自动创建目录
  - 图片格式不支持: 记录 ERROR 日志，返回 False
- 预计行数: ~200 行

**7. AssetMigrator (资产迁移器)** ⭐ 新增

- 职责: 将资产迁移到其他 UE 工程
- **文件路径**: `modules/asset_manager/logic/asset_migrator.py` (新建)
- **导出符号**: `AssetMigrator` (类名)
- 接口契约:
  ```python
  class AssetMigrator:
      def __init__(self, file_ops: FileOperations, logger: Logger): ...
      def migrate_asset(self, asset: Asset, target_project: Path,
                       progress_callback: Optional[Callable] = None) -> bool: ...
  ```
- 迁移策略:
  - 目标路径: `<目标工程>/Content/<资产名>`
  - 冲突处理: 如果目标已存在，先删除再复制（覆盖模式）
  - 进度报告: 通过 `progress_callback(current, total, message)` 报告
- 异常策略: 迁移失败时记录错误日志，返回 False，不抛出异常
- 回滚机制: 如果复制失败，不删除源文件（保护数据安全）
- Mock 模式行为:
  - 记录 INFO 日志，模拟文件复制过程
  - 调用 `progress_callback` 报告进度（如果提供）
  - 返回 True（模拟成功）
- 边界条件:
  - 目标工程路径无效: 记录 ERROR 日志，返回 False
  - 资产路径不存在: 记录 ERROR 日志，返回 False
  - 目标磁盘空间不足: 记录 ERROR 日志，返回 False
- 预计行数: ~100 行

#### 方法迁移映射表

**从 AssetManagerLogic 迁移到新类的方法清单**:

| 旧方法 (AssetManagerLogic)          | 新类                | 新方法                   | 状态 |
| ----------------------------------- | ------------------- | ------------------------ | ---- |
| `_load_config`                      | ConfigHandler       | `load_config`            | 迁移 |
| `_save_config`                      | ConfigHandler       | `save_config`            | 迁移 |
| `_load_local_config`                | ConfigHandler       | `load_local_config`      | 迁移 |
| `_save_local_config`                | ConfigHandler       | `save_local_config`      | 迁移 |
| `_migrate_config`                   | ConfigHandler       | `migrate_config`         | 迁移 |
| `get_asset_library_path`            | ConfigHandler       | `get_asset_library_path` | 委托 |
| `set_asset_library_path`            | ConfigHandler       | `set_asset_library_path` | 委托 |
| `_safe_copytree`                    | FileOperations      | `safe_copytree`          | 迁移 |
| `_safe_move_tree`                   | FileOperations      | `safe_move_tree`         | 迁移 |
| `_safe_move_file`                   | FileOperations      | `safe_move_file`         | 迁移 |
| `_calculate_size`                   | FileOperations      | `calculate_size`         | 迁移 |
| `_format_size`                      | FileOperations      | `format_size`            | 迁移 |
| `_get_pinyin`                       | SearchEngine        | `get_pinyin`             | 迁移 |
| `_build_pinyin_cache`               | SearchEngine        | `build_pinyin_cache`     | 迁移 |
| `search_assets`                     | SearchEngine        | `search`                 | 委托 |
| `sort_assets`                       | SearchEngine        | `sort`                   | 委托 |
| `_do_preview_asset`                 | PreviewManager      | `preview_asset`          | 迁移 |
| `_launch_unreal_project`            | PreviewManager      | `launch_unreal_project`  | 迁移 |
| `_close_current_preview_if_running` | PreviewManager      | `close_current_preview`  | 迁移 |
| `_find_ue_process`                  | PreviewManager      | `find_ue_process`        | 迁移 |
| `clean_preview_project`             | PreviewManager      | `clean_preview_project`  | 委托 |
| `set_preview_project`               | PreviewManager      | `set_preview_project`    | 委托 |
| `process_screenshot`                | ScreenshotProcessor | `process_screenshot`     | 委托 |
| `_find_screenshot`                  | ScreenshotProcessor | `find_screenshot`        | 迁移 |
| `_find_thumbnail_by_asset_id`       | ScreenshotProcessor | `find_thumbnail`         | 迁移 |
| `migrate_asset`                     | AssetMigrator       | `migrate_asset`          | 委托 |

**说明**:

- **迁移**: 方法完全移动到新类，AssetManagerLogic 中删除
- **委托**: AssetManagerLogic 保留公共方法，内部委托给新类实现
- **保留**: 方法保留在 AssetManagerLogic 中（如 `add_asset`, `remove_asset` 等核心 CRUD）

#### 过渡适配层实现示例

**委托模式实现** (保持公共 API 不变):

```python
# modules/asset_manager/logic/asset_manager_logic.py
class AssetManagerLogic(QObject):
    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        # 初始化子模块
        self._logger = get_log_service()
        self._config_handler = ConfigHandler(config_manager, self._logger)
        self._file_ops = FileOperations(self._logger)
        self._search_engine = SearchEngine(self._logger)
        self._preview_manager = PreviewManager(self._file_ops, self._logger)
        self._screenshot_processor = ScreenshotProcessor(self._logger)
        self._asset_migrator = AssetMigrator(self._file_ops, self._logger)

        # 原有属性
        self.assets: List[Asset] = []
        self.categories: List[str] = []

    # 公共 API - 委托给子模块
    def search_assets(self, search_text: str, category: Optional[str] = None) -> List[Asset]:
        """搜索资产 - 委托给 SearchEngine"""
        return self._search_engine.search(self.assets, search_text, category)

    def sort_assets(self, assets: List[Asset], sort_method: str) -> List[Asset]:
        """排序资产 - 委托给 SearchEngine"""
        return self._search_engine.sort(assets, sort_method)

    def preview_asset(self, asset_id: str, progress_callback=None,
                     preview_project_path: Optional[Path] = None) -> bool:
        """预览资产 - 委托给 PreviewManager"""
        asset = self.get_asset(asset_id)
        if not asset:
            self._logger.error(f"Asset not found: {asset_id}")
            return False

        preview_project = preview_project_path or self._preview_manager.get_preview_project()
        if not preview_project:
            self._logger.error("Preview project not set")
            return False

        self.preview_started.emit(asset_id)
        success = self._preview_manager.preview_asset(asset, preview_project, progress_callback)
        if success:
            self.preview_finished.emit()
        return success

    def migrate_asset(self, asset_id: str, target_project: Path,
                     progress_callback=None) -> bool:
        """迁移资产 - 委托给 AssetMigrator"""
        asset = self.get_asset(asset_id)
        if not asset:
            self._logger.error(f"Asset not found: {asset_id}")
            return False

        return self._asset_migrator.migrate_asset(asset, target_project, progress_callback)
```

**导入路径保持不变**:

```python
# UI 代码无需修改
from modules.asset_manager.logic.asset_manager_logic import AssetManagerLogic

logic = AssetManagerLogic(config_manager)
logic.search_assets("test")  # 仍然可用
logic.preview_asset("asset_id")  # 仍然可用
```

**信号定义保持不变**:

```python
# AssetManagerLogic 中的信号定义不变
asset_added = pyqtSignal(object)
asset_removed = pyqtSignal(str)
preview_started = pyqtSignal(str)
preview_finished = pyqtSignal()
# ... 其他信号
```

#### 实施强制约束

**在开始实施前，必须遵守以下约束**:

1. **文件创建约束**:

   - ✅ 只创建设计文档中明确列出的新文件：
     - `modules/asset_manager/logic/config_handler.py`
     - `modules/asset_manager/logic/file_operations.py`
     - `modules/asset_manager/logic/search_engine.py`
     - `modules/asset_manager/logic/preview_manager.py`
     - `modules/asset_manager/logic/screenshot_processor.py`
     - `modules/asset_manager/logic/asset_migrator.py`
   - ✅ 保留现有文件：`modules/asset_manager/logic/asset_manager_logic.py`
   - ❌ 不创建额外的辅助类（除非获得批准）
   - ❌ 不创建新的配置文件
   - ✅ 测试文件必须与源文件一一对应

2. **方法签名约束**:

   - ✅ 严格按照设计文档中的接口契约实现
   - ❌ 不修改公共方法签名（除非获得批准）
   - ✅ 私有方法可以灵活调整
   - ✅ 所有方法必须有类型提示

3. **依赖注入约束**:

   - ✅ 所有依赖通过构造函数注入
   - ❌ 不使用全局变量（除了 logger 获取）
   - ✅ 使用 `from core.services import _get_log_service` 获取 logger
   - ❌ 不在类内部创建其他类的实例（除非是数据类）

4. **错误处理约束**:

   - ✅ 所有方法返回 `bool`, `Optional[T]`, 或 `List[T]`
   - ❌ 不抛出异常到调用方
   - ✅ 所有异常在方法内部捕获并记录日志
   - ✅ 失败时返回 `False`, `None`, 或 `[]`

5. **测试约束**:

   - ✅ 所有测试必须在 Mock 模式下运行
   - ❌ 测试不操作真实文件系统（使用 `tmp_path` fixture）
   - ❌ 测试不启动真实 UE 进程
   - ✅ 测试结束后必须清理临时文件

6. **性能约束**:

   - ✅ 单个方法执行时间 < 100ms（除了文件操作和 UE 启动）
   - ✅ 搜索 1000 个资产 < 500ms
   - ✅ 加载配置 < 100ms

7. **代码体量约束** ⚠️ 严格执行:

   - ✅ 每个类 < 500 行（**硬性要求**，超过必须拆分）
   - ✅ 每个方法 < 50 行（**硬性要求**，超过必须拆分）
   - ✅ 如果超过限制，必须拆分成更小的类或方法
   - ✅ 实施时使用工具检查：`wc -l <文件>` 或 IDE 统计
   - ✅ PR 审查时必须验证体量符合要求
   - ⚠️ 特殊情况（如复杂业务逻辑）需要在 PR 中说明并获得批准

8. **文档约束**:
   - ✅ 所有公共方法必须有文档字符串
   - ✅ 文档字符串必须包含：描述、参数、返回值、异常（如果有）
   - ✅ 使用 Google 风格文档字符串

#### 实施提示

**⚠️ 代码体量控制**:

在实施过程中，必须时刻关注代码体量：

1. **编写前规划**:

   - 在编写每个类之前，先列出需要实现的方法
   - 估算每个方法的行数（参考设计文档中的接口契约）
   - 如果预计超过 500 行，考虑进一步拆分

2. **编写时检查**:

   - 每完成一个方法，检查行数（IDE 右下角显示）
   - 如果方法超过 50 行，立即拆分成更小的私有方法
   - 使用 IDE 的代码折叠功能，快速查看方法体量

3. **提交前验证**:

   - 使用 `wc -l <文件>` 检查文件总行数
   - 使用工具检查每个方法的行数（如 `radon cc` 或 IDE 插件）
   - 确保所有类 < 500 行，所有方法 < 50 行

4. **拆分技巧**:
   - 提取重复代码为私有方法
   - 将复杂逻辑拆分为多个步骤
   - 使用辅助函数处理边界条件
   - 将数据处理和业务逻辑分离

#### 重构策略

**阶段 1: 提取独立工具类（低风险）**

1. 创建 `FileOperations` 类
2. 创建 `SearchEngine` 类
3. 创建 `ScreenshotProcessor` 类
4. 创建 `AssetMigrator` 类
5. 编写单元测试

**阶段 2: 提取配置管理（中风险）**

1. 创建 `ConfigHandler` 类
2. 在 `AssetManagerLogic` 中集成
3. 编写单元测试

**阶段 3: 提取预览管理（中风险）**

1. 创建 `PreviewManager` 类
2. 在 `AssetManagerLogic` 中集成
3. 编写单元测试

**阶段 4: 重构主类（高风险）**

1. 简化 `AssetManagerLogic`，委托给子模块
2. 拆分大方法（`add_asset`, `_scan_asset_library` 等）
3. 添加类型提示
4. 编写集成测试

**阶段 5: 验证与优化**

1. 运行完整测试套件
2. 性能测试
3. 代码审查

---

### 方案 B: UEMainWindow 重构

#### 新架构设计

```
ui/
├── ue_main_window.py             # 主窗口（简化版）
├── components/                   # UI组件 ⭐ 新增目录
│   ├── __init__.py
│   ├── title_bar.py              # 标题栏组件 ⭐ 新增
│   ├── navigation_panel.py       # 导航面板组件 ⭐ 新增
│   └── content_panel.py          # 内容面板组件 ⭐ 新增
└── managers/                     # 管理器 ⭐ 新增目录
    ├── __init__.py
    ├── module_loader.py          # 模块加载器 ⭐ 新增
    └── theme_controller.py       # 主题控制器 ⭐ 新增
```

#### 类职责划分

**1. UEMainWindow (主窗口)**

- 职责: 组装 UI 组件，协调各个管理器
- 保留方法:
  - `__init__`, `init_ui`
  - `load_initial_module`, `switch_module`
  - `toggle_theme`, `show_settings`
  - `closeEvent`, `center_window`
- 依赖: TitleBar, NavigationPanel, ContentPanel, ModuleLoader, ThemeController
- 预计行数: ~250 行

**2. TitleBar (标题栏组件)** ⭐ 新增

- 职责: 创建和管理标题栏 UI
- 方法:
  - `__init__()`: 初始化标题栏
  - `create_ui()`: 创建 UI 元素
  - `on_mouse_press()`: 鼠标按下事件
  - `on_mouse_move()`: 鼠标移动事件
- 预计行数: ~100 行

**3. NavigationPanel (导航面板组件)** ⭐ 新增

- 职责: 创建和管理左侧导航栏
- 方法:
  - `__init__()`: 初始化导航面板
  - `create_ui()`: 创建 UI 元素
  - `add_module_button()`: 添加模块按钮
  - `set_active_button()`: 设置激活按钮
- 预计行数: ~100 行

**4. ContentPanel (内容面板组件)** ⭐ 新增

- 职责: 创建和管理右侧内容区
- 方法:
  - `__init__()`: 初始化内容面板
  - `create_ui()`: 创建 UI 元素
  - `create_placeholder()`: 创建占位页面
  - `switch_page()`: 切换页面
- 预计行数: ~100 行

**5. ModuleLoader (模块加载器)** ⭐ 新增

- 职责: 管理模块的懒加载
- 方法:
  - `load_module()`: 加载模块
  - `is_module_loaded()`: 检查模块是否已加载
  - `get_module_widget()`: 获取模块 UI
- 预计行数: ~100 行

**6. ThemeController (主题控制器)** ⭐ 新增

- 职责: 管理主题切换和保存
- 方法:
  - `toggle_theme()`: 切换主题
  - `save_theme_setting()`: 保存主题设置
  - `update_theme_icon()`: 更新主题图标
- 预计行数: ~80 行

#### 重构策略

**阶段 1: 提取 UI 组件（低风险）**

1. 创建 `TitleBar` 组件
2. 创建 `NavigationPanel` 组件
3. 创建 `ContentPanel` 组件
4. 编写 UI 测试

**阶段 2: 提取管理器（中风险）**

1. 创建 `ModuleLoader` 类
2. 创建 `ThemeController` 类
3. 编写单元测试

**阶段 3: 重构主窗口（高风险）**

1. 简化 `UEMainWindow`，使用新组件
2. 添加类型提示
3. 编写集成测试

**阶段 4: 验证与优化**

1. 运行完整测试套件
2. UI 测试
3. 代码审查

---

## 🔧 实施计划

### 优先级排序

**P0 (高优先级)**

1. AssetManagerLogic - FileOperations (独立工具类，低风险)
2. AssetManagerLogic - SearchEngine (独立工具类，低风险)
3. UEMainWindow - TitleBar (独立组件，低风险)

**P1 (中优先级)** 4. AssetManagerLogic - ConfigHandler (中风险) 5. AssetManagerLogic - PreviewManager (中风险) 6. UEMainWindow - NavigationPanel + ContentPanel (中风险)

**P2 (低优先级)** 7. AssetManagerLogic - 主类重构 (高风险) 8. UEMainWindow - 主窗口重构 (高风险)

### 时间估算

- **阶段 1 (P0)**: 2-3 天
- **阶段 2 (P1)**: 3-4 天
- **阶段 3 (P2)**: 2-3 天
- **测试与验证**: 1-2 天
- **总计**: 8-12 天

### 风险评估

**高风险项**:

- AssetManagerLogic 主类重构（可能影响现有功能）
- UEMainWindow 主窗口重构（可能影响 UI 显示）

**缓解措施**:

- 保持公共 API 不变
- 编写完整的单元测试和集成测试
- 分阶段提交，每个阶段都要验证
- 使用 Git 标签标记每个阶段

---

## 🧪 测试要求

### 单元测试清单

**ConfigHandler 测试**:

- [ ] `test_load_config_success`: 成功加载配置
- [ ] `test_load_config_file_not_found`: 配置文件不存在时的处理
- [ ] `test_save_config_success`: 成功保存配置
- [ ] `test_save_config_permission_denied`: 权限不足时的处理
- [ ] `test_load_local_config_success`: 成功加载本地配置
- [ ] `test_save_local_config_with_backup`: 保存配置并创建备份
- [ ] `test_migrate_config_old_to_new`: 旧配置迁移到新版本
- [ ] `test_set_asset_library_path_invalid`: 设置无效路径时的处理

**FileOperations 测试**:

- [ ] `test_safe_copytree_success`: 成功复制目录树
- [ ] `test_safe_copytree_src_not_exist`: 源路径不存在时的处理
- [ ] `test_safe_copytree_permission_denied`: 权限不足时的处理
- [ ] `test_safe_move_tree_success`: 成功移动目录树
- [ ] `test_safe_move_file_success`: 成功移动文件
- [ ] `test_calculate_size_file`: 计算文件大小
- [ ] `test_calculate_size_directory`: 计算目录大小
- [ ] `test_format_size_various_units`: 格式化各种大小单位

**SearchEngine 测试**:

- [ ] `test_search_by_name`: 按名称搜索
- [ ] `test_search_by_pinyin`: 按拼音搜索
- [ ] `test_search_by_category`: 按分类搜索
- [ ] `test_search_empty_text`: 空搜索文本返回所有资产
- [ ] `test_sort_by_time_newest`: 按时间排序（最新）
- [ ] `test_sort_by_name_az`: 按名称排序（A-Z）
- [ ] `test_build_pinyin_cache`: 构建拼音缓存
- [ ] `test_get_pinyin_chinese`: 中文转拼音

**PreviewManager 测试**:

- [ ] `test_preview_asset_success`: 成功预览资产（Mock 模式）
- [ ] `test_preview_asset_project_not_exist`: 预览工程不存在时的处理
- [ ] `test_launch_unreal_project_mock`: 启动 UE 工程（Mock 模式）
- [ ] `test_close_current_preview`: 关闭当前预览
- [ ] `test_find_ue_process`: 查找 UE 进程
- [ ] `test_clean_preview_project`: 清理预览工程临时文件

**ScreenshotProcessor 测试**:

- [ ] `test_process_screenshot_success`: 成功处理截图
- [ ] `test_find_screenshot_timeout`: 查找截图超时
- [ ] `test_find_thumbnail_exist`: 查找已存在的缩略图
- [ ] `test_find_thumbnail_not_exist`: 缩略图不存在时返回 None

**AssetMigrator 测试**:

- [ ] `test_migrate_asset_success`: 成功迁移资产
- [ ] `test_migrate_asset_target_not_exist`: 目标工程不存在时的处理
- [ ] `test_migrate_asset_conflict_handling`: 目标已存在时的冲突处理

### 集成测试清单

- [ ] `test_asset_manager_full_workflow`: 完整工作流（添加 → 搜索 → 预览 → 迁移 → 删除）
- [ ] `test_config_persistence`: 配置持久化（保存 → 重启 → 加载）
- [ ] `test_multiple_assets_operations`: 批量资产操作
- [ ] `test_error_recovery`: 错误恢复机制

---

## 📋 日志与错误处理约束

### 日志级别规范

**DEBUG**: 详细的调试信息

- 方法调用参数
- 中间状态变化
- 缓存命中/未命中

**INFO**: 重要的业务事件

- 资产添加/删除成功
- 配置加载/保存成功
- 预览启动/关闭

**WARNING**: 可恢复的异常情况

- 配置文件格式错误（使用默认值）
- 截图查找超时（使用默认缩略图）
- 拼音库未安装（降级到简单搜索）

**ERROR**: 不可恢复的错误

- 文件操作失败（权限不足、磁盘满）
- 配置保存失败
- 预览启动失败

### 错误处理策略

**原则**: 不抛出异常到调用方，通过返回值和日志传递错误信息

**返回值约定**:

- 成功操作: 返回 `True` 或有效对象
- 失败操作: 返回 `False` 或 `None`
- 列表操作: 失败时返回空列表 `[]`

**重试策略**:

- 文件操作: 不重试（避免长时间阻塞）
- 网络操作: 无（当前版本无网络操作）
- 进程操作: 不重试

**回滚机制**:

- 文件移动: 失败时不删除源文件
- 配置保存: 失败时保留旧配置
- 资产迁移: 失败时不修改源资产

### 环境依赖与 Mock

**外部依赖**:

- UE 编辑器: 通过环境变量 `UE_EDITOR_PATH` 或注册表获取
- pypinyin 库: 可选依赖，未安装时降级到简单搜索
- psutil 库: 可选依赖，未安装时使用 subprocess

**Mock 模式**:

- 环境变量 `ASSET_MANAGER_MOCK_MODE=1`: 启用 Mock 模式
- Mock 模式下:
  - 不启动真实 UE 进程
  - 不执行真实文件操作（使用临时目录）
  - 不查找真实截图（使用测试图片）

**测试环境配置**:

```python
# tests/conftest.py
import os
os.environ['ASSET_MANAGER_MOCK_MODE'] = '1'
os.environ['ASSET_LIBRARY_PATH'] = '/tmp/test_asset_library'
```

---

## ✅ 验收标准

### 代码质量

**⚠️ 代码体量（硬性要求，必须通过）**:

- [ ] **所有类不超过 500 行**（使用 `wc -l <文件>` 验证）
  - ConfigHandler: < 500 行
  - FileOperations: < 500 行
  - SearchEngine: < 500 行
  - PreviewManager: < 500 行
  - ScreenshotProcessor: < 500 行
  - AssetMigrator: < 500 行
  - AssetManagerLogic（重构后）: < 500 行
- [ ] **所有方法不超过 50 行**（使用 IDE 或 `radon cc` 验证）
  - 如果超过 50 行，必须拆分成更小的方法
  - 特殊情况需要在 PR 中说明并获得批准

**代码规范**:

- [ ] 所有公共方法有类型提示
- [ ] 所有公共方法有文档字符串
- [ ] 所有新增类有完整的接口契约文档

### 测试覆盖

- [ ] 新增类的单元测试覆盖率 > 80%
- [ ] 所有单元测试通过
- [ ] 集成测试通过
- [ ] UI 测试通过（手动验证）

### 功能验证

- [ ] 所有现有功能正常工作
- [ ] 所有公共 API 签名保持不变
- [ ] 性能无明显下降（< 10% 性能损失）
- [ ] 无新增 bug

### 文档

- [ ] 更新 README
- [ ] 更新架构文档
- [ ] 添加迁移指南
- [ ] 补充新增类的 API 文档

---

## � PR 审查检查清单

**⚠️ 优先检查项（必须通过才能继续审查）**:

1. **代码体量硬性要求**:

   - [ ] 所有类 < 500 行（使用 `wc -l <文件>` 验证）
   - [ ] 所有方法 < 50 行（使用 IDE 或 `radon cc` 验证）
   - [ ] 如果超过限制，PR 必须被拒绝或要求修改

2. **接口契约一致性**:
   - [ ] 所有新增类的方法签名与设计文档一致
   - [ ] 所有公共 API 保持不变

### 代码规范检查

**类体量检查** ⚠️ 硬性要求:

- [ ] ConfigHandler < 500 行（预计 ~300 行）
- [ ] FileOperations < 500 行（预计 ~250 行）
- [ ] SearchEngine < 500 行（预计 ~200 行）
- [ ] PreviewManager < 500 行（预计 ~350 行）
- [ ] ScreenshotProcessor < 500 行（预计 ~200 行）
- [ ] AssetMigrator < 500 行（预计 ~100 行）
- [ ] AssetManagerLogic（重构后）< 500 行（预计 ~800 行，需要进一步拆分）
- [ ] 如果超过 500 行，必须说明原因并获得批准

**方法体量检查** ⚠️ 硬性要求:

- [ ] 所有新增方法 < 50 行
- [ ] 所有重构后的方法 < 50 行
- [ ] 使用工具验证：`radon cc -s modules/asset_manager/logic/`
- [ ] 如果超过 50 行，必须说明原因（如复杂的业务逻辑）并获得批准

**类型提示检查**:

- [ ] 所有公共方法有完整的类型提示（参数 + 返回值）
- [ ] 所有私有方法有类型提示（推荐）
- [ ] 使用 `mypy` 检查类型一致性：`mypy modules/asset_manager/`

**文档字符串检查**:

- [ ] 所有公共方法有文档字符串
- [ ] 文档字符串包含：简短描述、参数说明、返回值说明、异常说明（如果有）
- [ ] 使用 Google 风格或 NumPy 风格（保持一致）

### 功能验证检查

**API 兼容性检查**:

- [ ] 运行现有的集成测试套件（全部通过）
- [ ] 手动验证 UI 调用代码无需修改
- [ ] 检查所有公共方法签名与设计文档一致
- [ ] 检查所有信号定义保持不变

**单元测试检查**:

- [ ] 每个新增类都有对应的测试文件
- [ ] 测试覆盖率 > 80%（使用 `pytest --cov`）
- [ ] 所有测试用例通过
- [ ] 测试用例覆盖正常流程 + 异常流程

**集成测试检查**:

- [ ] 完整工作流测试通过（添加 → 搜索 → 预览 → 迁移 → 删除）
- [ ] 配置持久化测试通过（保存 → 重启 → 加载）
- [ ] 批量操作测试通过
- [ ] 错误恢复测试通过

**Mock 模式检查**:

- [ ] 所有测试在 Mock 模式下运行
- [ ] 测试不操作真实资产库
- [ ] 测试不启动真实 UE 进程
- [ ] 测试结束后清理临时目录

### 代码质量检查

**依赖注入检查**:

- [ ] 所有新增类通过构造函数注入依赖（不使用全局变量）
- [ ] 所有新增类接收 `logger` 参数
- [ ] 避免循环依赖

**错误处理检查**:

- [ ] 所有文件操作有错误处理
- [ ] 所有外部调用有错误处理（UE 进程、配置加载等）
- [ ] 错误信息记录到日志（使用正确的日志级别）
- [ ] 不抛出异常到调用方（返回 False 或 None）

**日志检查**:

- [ ] 关键操作有 INFO 级别日志（资产添加、预览启动等）
- [ ] 错误情况有 ERROR 级别日志
- [ ] 警告情况有 WARNING 级别日志
- [ ] 调试信息有 DEBUG 级别日志
- [ ] 日志信息清晰、有上下文

**路径处理检查**:

- [ ] 所有路径使用 `pathlib.Path`
- [ ] 没有硬编码路径（除了配置文件路径）
- [ ] 路径拼接使用 `/` 运算符（不使用字符串拼接）
- [ ] 路径存在性检查（使用 `path.exists()`）

### 性能检查

**性能对比**:

- [ ] 重构前后性能对比（添加 1000 个资产的时间）
- [ ] 搜索性能对比（搜索 1000 个资产的时间）
- [ ] 性能损失 < 10%

**资源使用**:

- [ ] 内存使用无明显增加
- [ ] 无内存泄漏（长时间运行测试）

### 提交规范检查

**Commit 信息**:

- [ ] Commit 信息清晰、描述准确
- [ ] 使用约定式提交格式：`feat:`, `refactor:`, `test:`, `docs:`
- [ ] 每个 Commit 只做一件事（原子性）

**分支管理**:

- [ ] 在独立分支上开发：`refactor/task5-large-classes`
- [ ] 定期从主分支合并最新代码
- [ ] 解决所有冲突

**代码审查**:

- [ ] 自我审查：检查所有修改的代码
- [ ] 移除调试代码（`print`, `console.log` 等）
- [ ] 移除注释掉的代码
- [ ] 代码格式化（使用 `black` 或 IDE 格式化）

---

## �📝 下一步行动

1. **获得批准**: 让 Codex 审查此设计文档
2. **创建分支**: `git checkout -b refactor/task5-large-classes`
3. **开始实施**: 从 P0 优先级开始
4. **持续验证**: 每个阶段完成后运行测试
5. **代码审查**: 每个阶段完成后提交审查

---

## 🎓 参考资料

- [SOLID 原则](https://en.wikipedia.org/wiki/SOLID)
- [重构：改善既有代码的设计](https://refactoring.com/)
- [Clean Code](https://www.oreilly.com/library/view/clean-code-a/9780136083238/)
