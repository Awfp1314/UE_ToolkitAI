# Migration Guide Supplement

## 前后代码对照 + 常见坑

### 1. ThreadService 迁移

#### 前后对照

**旧代码（❌）**：

```python
from core.utils.thread_utils import ThreadManager

class AssetManagerLogic:
    def __init__(self):
        self.thread_manager = ThreadManager()  # 每个模块创建自己的实例

    def load_assets(self):
        def task():
            # 不支持取消
            return self.fetch_assets()

        self.thread_manager.run_in_thread(task, on_result=self.on_assets_loaded)

    def cleanup(self):
        self.thread_manager.cleanup()  # 需要手动清理
```

**新代码（✅）**：

```python
from core.services import thread_service

class AssetManagerLogic:
    def __init__(self):
        pass  # 不需要创建 ThreadManager

    def load_assets(self):
        def task(cancel_token):
            # 支持取消
            if cancel_token.is_cancelled():
                return None
            return self.fetch_assets()

        worker, token = thread_service.run_async(task, on_result=self.on_assets_loaded)
        self.current_task_token = token  # 保存 token 用于取消

    def cancel_loading(self):
        if hasattr(self, 'current_task_token'):
            thread_service.cancel_task(self.current_task_token)

    def cleanup(self):
        self.cancel_loading()  # 取消当前任务
        # 不需要手动清理 ThreadService（由服务层统一管理）
```

#### 常见坑

**坑 1：忘记保存 token**

```python
# ❌ 错误：没有保存 token，无法取消任务
worker, token = thread_service.run_async(task)

# ✅ 正确：保存 token
self.task_token = token
```

**坑 2：任务函数不检查取消标志**

```python
# ❌ 错误：任务函数不检查 cancel_token
def task(cancel_token):
    for i in range(1000):
        # 没有检查 cancel_token
        do_work()

# ✅ 正确：定期检查取消标志
def task(cancel_token):
    for i in range(1000):
        if cancel_token.is_cancelled():
            return None
        do_work()
```

**坑 3：在非主线程调用 Qt 控件**

```python
# ❌ 错误：在任务线程中直接更新 UI
def task():
    self.label.setText("完成")  # 会崩溃

# ✅ 正确：使用回调在主线程更新 UI
def task():
    return "完成"

def on_result(result):
    self.label.setText(result)  # 在主线程执行

thread_service.run_async(task, on_result=on_result)
```

### 2. ConfigService 迁移

#### 前后对照

**旧代码（❌）**：

```python
from core.config.config_manager import ConfigManager
from pathlib import Path

class AssetManagerLogic:
    def __init__(self):
        template_path = Path("core/config_templates/asset_manager_config.json")
        self.config_manager = ConfigManager("asset_manager", template_path=template_path)

    def load_config(self):
        return self.config_manager.get_module_config()

    def save_config(self, config):
        self.config_manager.save_user_config(config)
```

**新代码（✅）**：

```python
from core.services import config_service
from pathlib import Path

class AssetManagerLogic:
    def __init__(self):
        self.module_name = "asset_manager"
        self.template_path = Path("core/config_templates/asset_manager_config.json")

    def load_config(self):
        return config_service.get_module_config(
            self.module_name,
            template_path=self.template_path
        )

    def save_config(self, config):
        config_service.save_module_config(self.module_name, config)
```

#### 常见坑

**坑 1：首次访问忘记提供 template_path**

```python
# ❌ 错误：首次访问没有提供 template_path
config = config_service.get_module_config("my_module")  # 会失败

# ✅ 正确：首次访问提供 template_path
config = config_service.get_module_config(
    "my_module",
    template_path=Path("core/config_templates/my_module_config.json")
)
```

**坑 2：直接修改配置字典后忘记保存**

```python
# ❌ 错误：修改配置后没有保存
config = config_service.get_module_config("my_module")
config["key"] = "new_value"  # 只修改了内存中的副本

# ✅ 正确：修改后保存
config = config_service.get_module_config("my_module")
config["key"] = "new_value"
config_service.save_module_config("my_module", config)

# ✅ 更好：使用 update_config_value
config_service.update_config_value("my_module", "key", "new_value")
```

**坑 3：配置文件损坏后不知道如何恢复**

```python
# ✅ 正确：ConfigService 会自动从备份恢复
# 如果自动恢复失败，可以手动删除配置文件，让系统重新初始化
import os
config_path = config_service._config_managers["my_module"].user_config_path
if config_path.exists():
    os.remove(config_path)
config = config_service.get_module_config("my_module", force_reload=True)
```

### 3. LogService 迁移

#### 前后对照

**旧代码（❌）**：

```python
from core.logger import get_logger

class AssetManagerLogic:
    def __init__(self):
        self.logger = get_logger(__name__)

    def do_something(self):
        self.logger.info("执行操作")
```

**新代码（✅）**：

```python
from core.services import log_service

class AssetManagerLogic:
    def __init__(self):
        self.logger = log_service.get_logger(__name__)

    def do_something(self):
        self.logger.info("执行操作")
```

#### 常见坑

**坑 1：在模块级别创建 logger**

```python
# ❌ 不推荐：模块级别创建 logger（可能在服务初始化前）
from core.services import log_service
logger = log_service.get_logger(__name__)  # 可能触发过早初始化

# ✅ 推荐：在类或函数中创建 logger
class MyClass:
    def __init__(self):
        self.logger = log_service.get_logger(__name__)
```

**坑 2：忘记设置日志级别**

```python
# ❌ 错误：DEBUG 日志不显示
logger.debug("调试信息")  # 默认级别是 INFO，不会显示

# ✅ 正确：设置日志级别
log_service.set_level(logging.DEBUG)
logger.debug("调试信息")  # 现在会显示
```

### 4. StyleService 迁移

#### 前后对照

**旧代码（❌）**：

```python
from core.utils.style_system import style_system
from PyQt6.QtWidgets import QApplication

class UEMainWindow:
    def apply_theme(self, theme_name):
        app = QApplication.instance()
        style_system.apply_theme(app, theme_name)

    def get_themes(self):
        return style_system.discover_themes()
```

**新代码（✅）**：

```python
from core.services import style_service

class UEMainWindow:
    def apply_theme(self, theme_name):
        style_service.apply_theme(theme_name)  # 自动获取 QApplication

    def get_themes(self):
        return style_service.list_available_themes()
```

#### 常见坑

**坑 1：在非主线程调用 apply_theme**

```python
# ❌ 错误：在工作线程中应用主题
def task():
    style_service.apply_theme("dark")  # 会失败或崩溃

# ✅ 正确：在主线程应用主题
def task():
    return "dark"

def on_result(theme_name):
    style_service.apply_theme(theme_name)

thread_service.run_async(task, on_result=on_result)
```

**坑 2：主题文件不存在时没有错误处理**

```python
# ❌ 错误：没有检查返回值
style_service.apply_theme("non_existent_theme")

# ✅ 正确：检查返回值并处理错误
if not style_service.apply_theme("my_theme"):
    print("主题应用失败，使用默认主题")
    style_service.apply_theme("default")
```

### 5. PathService 迁移

#### 前后对照

**旧代码（❌）**：

```python
from core.utils.path_utils import PathUtils

class AssetManagerLogic:
    def __init__(self):
        self.path_utils = PathUtils()

    def get_data_dir(self):
        return self.path_utils.get_user_data_dir()
```

**新代码（✅）**：

```python
from core.services import path_service

class AssetManagerLogic:
    def __init__(self):
        pass  # 不需要创建 PathUtils

    def get_data_dir(self):
        return path_service.get_user_data_dir()
```

#### 常见坑

**坑 1：权限不足时没有错误处理**

```python
# ❌ 错误：没有处理 OSError
data_dir = path_service.get_user_data_dir()

# ✅ 正确：处理权限错误
try:
    data_dir = path_service.get_user_data_dir()
except OSError as e:
    print(f"无法创建数据目录: {e}")
    # 使用临时目录作为备用
    import tempfile
    data_dir = Path(tempfile.gettempdir()) / "ue_toolkit"
```

**坑 2：假设目录已存在**

```python
# ❌ 错误：假设目录已存在
data_dir = path_service.get_user_data_dir(create=False)
file_path = data_dir / "data.json"
with open(file_path, 'w') as f:  # 可能失败
    json.dump(data, f)

# ✅ 正确：确保目录存在
data_dir = path_service.get_user_data_dir(create=True)
file_path = data_dir / "data.json"
with open(file_path, 'w') as f:
    json.dump(data, f)
```

## 回滚步骤

### 如果迁移出现问题，如何回滚？

#### 步骤 1：恢复旧代码

```bash
# 使用 git 恢复到迁移前的提交
git log --oneline  # 查找迁移前的提交
git checkout <commit-hash> -- <file-path>

# 或者恢复整个分支
git reset --hard <commit-hash>
```

#### 步骤 2：验证功能

```bash
# 运行应用程序
python main.py

# 运行测试
pytest tests/
```

#### 步骤 3：记录问题

创建问题报告，包含：

- 迁移的文件和模块
- 出现的错误信息
- 复现步骤
- 预期行为 vs 实际行为

## 迁移验收清单

### 每个文件迁移完成后检查：

- [ ] **导入语句已更新**

  - [ ] 移除旧的导入（ThreadManager, ConfigManager, etc.）
  - [ ] 添加新的导入（from core.services import ...）

- [ ] **实例创建已移除**

  - [ ] 移除 `self.thread_manager = ThreadManager()`
  - [ ] 移除 `self.config_manager = ConfigManager(...)`
  - [ ] 移除 `self.path_utils = PathUtils()`

- [ ] **方法调用已更新**

  - [ ] ThreadManager.run_in_thread → thread_service.run_async
  - [ ] ConfigManager.get_module_config → config_service.get_module_config
  - [ ] get_logger(**name**) → log_service.get_logger(**name**)
  - [ ] style_system.apply_theme → style_service.apply_theme
  - [ ] PathUtils.get_user_data_dir → path_service.get_user_data_dir

- [ ] **清理逻辑已调整**

  - [ ] 移除手动清理 ThreadManager 的代码
  - [ ] 移除手动清理 ConfigManager 的代码
  - [ ] 保留模块特定的清理逻辑

- [ ] **功能测试通过**

  - [ ] 应用启动正常
  - [ ] 模块功能正常
  - [ ] 配置保存/加载正常
  - [ ] 主题切换正常
  - [ ] 异步任务执行正常

- [ ] **日志输出正常**

  - [ ] 日志文件正常写入
  - [ ] 日志级别正确
  - [ ] 没有异常日志

- [ ] **代码已提交**
  - [ ] git add <file>
  - [ ] git commit -m "迁移 <file> 到服务层"
