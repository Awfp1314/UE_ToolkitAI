# 如何构建主题

## 📝 什么时候需要构建主题？

当你修改了以下文件后，需要重新构建主题：

- ✅ `resources/styles/config/themes/*.py` - 主题配置文件（颜色变量）
- ✅ `resources/styles/core/*.qss` - 核心样式文件
- ✅ `resources/styles/widgets/*.qss` - 控件样式文件
- ✅ `resources/styles/modules/*.qss` - 模块样式文件

## 🚀 如何构建？

### 方法1：使用批处理脚本（推荐）

双击运行：

```
scripts/build/build_themes.bat
```

### 方法2：使用Python脚本

```bash
cd UE_TOOKITS_AI_NEW
python scripts/build/build_themes.py
```

## 📦 构建结果

构建完成后，会在 `resources/styles/themes/` 目录下生成：

- ✅ `modern_dark.qss` - 深色主题
- ✅ `modern_light.qss` - 浅色主题

## ⚠️ 注意事项

1. **不要直接修改** `resources/styles/themes/` 目录下的 `.qss` 文件
   - 这些文件是自动生成的，会被覆盖

2. **修改样式的正确方式**：
   - 修改 `resources/styles/widgets/` 或 `resources/styles/modules/` 下的源文件
   - 然后运行构建脚本

3. **修改颜色的正确方式**：
   - 修改 `resources/styles/config/themes/modern_dark.py` 或 `modern_light.py`
   - 然后运行构建脚本

## 🎨 主题系统架构

```
resources/styles/
├── config/
│   ├── themes/
│   │   ├── modern_dark.py    # 深色主题配置（颜色变量）
│   │   └── modern_light.py   # 浅色主题配置（颜色变量）
│   └── variables.py           # 全局变量（尺寸、字体等）
├── core/                      # 核心样式（基础样式）
├── widgets/                   # 控件样式（按钮、对话框等）
├── modules/                   # 模块样式（资产管理器、AI助手等）
└── themes/                    # 生成的主题文件（自动生成，不要手动修改）
    ├── modern_dark.qss
    └── modern_light.qss
```

## 💡 示例：添加新按钮样式

1. 在 `resources/styles/widgets/main_window.qss` 中添加：

```css
#CheckUpdateButton {
    background: transparent;
    color: ${text_tertiary};
}
```

2. 运行构建脚本：

```bash
python scripts/build/build_themes.py
```

3. 重启程序，新样式生效！

---

**就这么简单！** 🎉
