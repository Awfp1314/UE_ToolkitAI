# Bootstrap 系统回滚指南

如果需要回滚到旧的启动逻辑，请按照以下步骤操作：

## 方法 1：使用 Git 回滚

```bash
# 回滚 main.py 到重构前的版本
git checkout 357897a -- main.py

# 或者回滚整个重构分支
git reset --hard 357897a
```

## 方法 2：查看旧代码但不回滚

```bash
# 查看旧版本的 main.py
git show 357897a:main.py

# 将旧版本导出到临时文件
git show 357897a:main.py > main_old_reference.py
```

## 方法 3：手动禁用 Bootstrap 系统

如果只是想临时测试，可以在 main.py 中注释掉 Bootstrap 调用：

```python
def main():
    # 新的 Bootstrap 方式
    # bootstrap = AppBootstrap()
    # return bootstrap.run()
    
    # 临时使用旧逻辑（需要手动复制旧代码）
    pass
```

## Bootstrap 系统与旧系统的对应关系

| 旧系统 | 新系统 (Bootstrap) |
|--------|-------------------|
| `setup_console_encoding()` | `AppInitializer._setup_logging()` |
| `init_logging_system()` | `AppInitializer._setup_logging()` |
| 创建 QApplication | `AppInitializer._create_qapplication()` |
| 单例检查 | `AppInitializer._check_single_instance()` |
| 主题加载 | `UILauncher._load_theme_config()` |
| 创建 Splash | `UILauncher._create_splash()` |
| 模块加载 | `ModuleLoader.load_modules()` |
| 模块依赖连接 | `ModuleLoader._connect_module_dependencies()` |
| 创建主窗口 | `UILauncher._create_main_window()` |

## 注意事项

- Bootstrap 系统是对原有代码的重构，功能完全相同
- 所有模块依赖关系保持不变
- 配置文件和数据格式完全兼容
- 如有问题，可以随时通过 Git 回滚
