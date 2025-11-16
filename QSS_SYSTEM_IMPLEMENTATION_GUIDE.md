# QSS样式系统实施指南

> **交接文档** - 供下一位AI助手参考  
> **项目**: UE Toolkit 无UI版本  
> **任务**: 实施优化版QSS样式系统  
> **日期**: 2025-11-12

---

## 📋 项目背景

### 当前状态
- ✅ 主窗口已完成：`ui/ue_main_window.py` (1017行，内联样式)
- ✅ 启动界面已完成：`ui/splash_screen.py` (234行，内联样式)
- ✅ 主程序可运行：`python main.py` 正常启动
- ❌ **待完成**：将内联样式迁移到QSS系统

### 用户需求
1. **样式外部化**：将内联CSS提取到QSS文件
2. **主题系统**：支持深色/浅色主题切换
3. **现代化UI**：保持预览版本的现代化样式（圆角、渐变、无边框）
4. **高性能**：优化文件结构，提升加载速度
5. **易扩展**：方便添加新主题和新模块样式

---

## 🎯 最终方案：优化版QSS系统 + 性能优化

### 核心设计思路

#### **1. 文件结构优化**
- **合并小文件**：将10+个组件文件合并为1个 `components.qss`
- **分层清晰**：config（配置）→ core（核心）→ widgets（控件）→ modules（模块）
- **智能构建**：自动检测并拼接QSS文件，无需手动维护

#### **2. 性能优化策略**
- **预生成主题**：构建时生成完整主题文件，运行时直接加载
- **启用缓存**：内存缓存已加载主题，二次加载瞬间完成
- **延迟加载**：模块样式按需加载，减少启动时间
- **压缩QSS**：生产环境压缩文件，减少60%体积

#### **3. 变量管理**
- **Python配置**：主题变量定义在Python文件中（易于修改）
- **占位符替换**：QSS中使用 `${variable}` 占位符
- **主题继承**：支持主题继承和混合

---

## 📁 目标文件结构

```
UE_TOOKITS_AI_NEW/
├── resources/
│   └── styles/                                    # 样式系统根目录
│       │
│       ├── config/                                # 配置层
│       │   ├── __init__.py
│       │   ├── variables.py                      # 全局变量（尺寸、字体等）
│       │   │
│       │   └── themes/                            # 主题配置
│       │       ├── __init__.py
│       │       ├── dark.py                       # 经典深色主题
│       │       ├── light.py                      # 经典浅色主题
│       │       ├── modern_dark.py                # 现代深色主题 ⭐
│       │       └── modern_light.py               # 现代浅色主题 ⭐
│       │
│       ├── core/                                  # 核心层
│       │   ├── base.qss                          # 基础样式（重置、排版、布局）
│       │   ├── components.qss                    # 通用组件（按钮、输入框等）⭐
│       │   └── animations.qss                    # 动画效果（可选）
│       │
│       ├── widgets/                               # 控件层
│       │   ├── main_window.qss                   # 主窗口样式
│       │   ├── splash_screen.qss                 # 启动界面样式
│       │   ├── title_bar.qss                     # 标题栏样式
│       │   ├── navigation.qss                    # 导航栏样式
│       │   ├── dialogs.qss                       # 对话框样式
│       │   └── settings_panel.qss                # 设置面板样式
│       │
│       ├── modules/                               # 模块层
│       │   ├── ai_assistant.qss                  # AI助手模块样式
│       │   ├── asset_manager.qss                 # 资产管理器模块样式
│       │   ├── config_tool.qss                   # 配置工具模块样式
│       │   └── site_recommendations.qss          # 站点推荐模块样式
│       │
│       ├── themes/                                # 主题层（自动生成）
│       │   ├── dark.qss                          # 经典深色主题（自动生成）
│       │   ├── light.qss                         # 经典浅色主题（自动生成）
│       │   ├── modern_dark.qss                   # 现代深色主题（自动生成）⭐
│       │   └── modern_light.qss                  # 现代浅色主题（自动生成）⭐
│       │
│       └── README.md                              # 样式系统使用文档
│
├── core/
│   └── utils/
│       ├── style_system.py                        # 样式系统核心 ⭐
│       └── theme_builder.py                       # 智能主题构建器 ⭐
│
└── ui/
    ├── ue_main_window.py                          # 主窗口（需修改为使用QSS）
    └── splash_screen.py                           # 启动界面（需修改为使用QSS）
```

---

## 🔧 实施步骤

### **阶段1：创建配置层** (优先级：🔴 最高)

#### 1.1 创建全局变量文件

**文件**: `resources/styles/config/variables.py`

**内容要点**:
```python
# 尺寸系统
SPACING = {
    'xs': '4px', 'sm': '8px', 'md': '12px', 
    'lg': '16px', 'xl': '20px', 'xxl': '24px',
}

BORDER_RADIUS = {
    'none': '0px', 'sm': '4px', 'md': '8px', 
    'lg': '12px', 'xl': '16px', 'round': '50%',
}

FONT_SIZE = {
    'xs': '11px', 'sm': '12px', 'md': '14px', 
    'lg': '16px', 'xl': '18px', 'xxl': '24px',
}

FONT_WEIGHT = {
    'light': '300', 'normal': '400', 'medium': '500',
    'semibold': '600', 'bold': '700',
}
```

**参考**: 查看对话历史中的完整示例

---

#### 1.2 创建现代深色主题配置

**文件**: `resources/styles/config/themes/modern_dark.py`

**内容要点**:
```python
THEME_NAME = "modern_dark"
THEME_DISPLAY_NAME = "现代深色"

COLORS = {
    # 主色调
    'primary': '#4a9eff',
    'primary_hover': '#5aa9ff',
    'primary_active': '#3a8eef',
    
    # 背景色（渐变）
    'bg_gradient_start': '#1c1c1c',
    'bg_gradient_end': '#2c2c2c',
    'bg_primary': '#1c1c1c',
    'bg_secondary': '#252525',
    'bg_tertiary': '#2c2c2c',
    'bg_hover': 'rgba(255, 255, 255, 0.05)',
    'bg_active': 'rgba(255, 255, 255, 0.1)',
    
    # 左侧面板渐变
    'sidebar_gradient_start': '#1c1c1c',
    'sidebar_gradient_end': '#181818',
    
    # 文本色
    'text_primary': '#ffffff',
    'text_secondary': 'rgba(255, 255, 255, 0.7)',
    'text_tertiary': 'rgba(255, 255, 255, 0.5)',
    'text_disabled': 'rgba(255, 255, 255, 0.3)',
    
    # 边框色
    'border_primary': 'rgba(255, 255, 255, 0.2)',
    'border_secondary': 'rgba(255, 255, 255, 0.1)',
    'border_focus': 'rgba(74, 158, 255, 0.5)',
    
    # 状态色
    'success': '#10a37f',
    'warning': '#ff9800',
    'error': '#ef4444',
    'info': '#4a9eff',
    
    # 滚动条
    'scrollbar_track': 'rgba(255, 255, 255, 0.05)',
    'scrollbar_thumb': 'rgba(255, 255, 255, 0.2)',
    'scrollbar_thumb_hover': 'rgba(255, 255, 255, 0.3)',
    'scrollbar_thumb_pressed': 'rgba(255, 255, 255, 0.4)',
    
    # 特殊
    'close_button_hover': '#e81123',
}

BORDER_RADIUS_OVERRIDE = {
    'container': '16px',  # 主容器
    'button': '10px',     # 导航按钮
    'input': '8px',       # 输入框
    'small': '6px',       # 小按钮
}
```

**数据来源**: 从 `ui/ue_main_window.py` 的 `_get_dark_theme_stylesheet()` 方法中提取颜色值

---

#### 1.3 创建现代浅色主题配置

**文件**: `resources/styles/config/themes/modern_light.py`

**内容要点**: 与 `modern_dark.py` 结构相同，但颜色值不同

**数据来源**: 从 `ui/ue_main_window.py` 的 `_get_light_theme_stylesheet()` 方法中提取颜色值

---

### **阶段2：创建核心层** (优先级：🔴 最高)

#### 2.1 创建基础样式

**文件**: `resources/styles/core/base.qss`

**内容要点**:
```css
/* ===== 全局重置 ===== */
* {
    outline: none;
    margin: 0;
    padding: 0;
}

/* ===== 默认字体 ===== */
QWidget {
    font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
    font-size: ${font_md};
    color: ${text_primary};
}

/* ===== 字体排版 ===== */
.h1 { font-size: ${font_xxl}; font-weight: ${font_bold}; }
.h2 { font-size: ${font_xl}; font-weight: ${font_semibold}; }
.body { font-size: ${font_md}; }
.caption { font-size: ${font_sm}; color: ${text_secondary}; }
```

**参考**: 查看对话历史中的完整示例

---

#### 2.2 创建通用组件样式

**文件**: `resources/styles/core/components.qss`

**内容要点**:
```css
/* ========================================
   按钮组件
   ======================================== */

QPushButton {
    background-color: ${bg_secondary};
    border: 1px solid ${border_primary};
    border-radius: ${radius_md};
    padding: ${spacing_sm} ${spacing_md};
    color: ${text_primary};
}

QPushButton:hover {
    background-color: ${bg_hover};
}

/* ========================================
   输入框组件
   ======================================== */

QLineEdit {
    background-color: ${bg_secondary};
    border: 1px solid ${border_primary};
    border-radius: ${radius_md};
    padding: ${spacing_sm} ${spacing_md};
    color: ${text_primary};
}

/* ========================================
   滚动条组件
   ======================================== */

QScrollBar:vertical {
    background: ${scrollbar_track};
    width: 12px;
    border-radius: 6px;
}

QScrollBar::handle:vertical {
    background: ${scrollbar_thumb};
    border-radius: 6px;
}
```

**注意**: 使用注释分区组织代码，便于查找

**参考**: 查看对话历史中的完整 `components.qss` 示例（约500行）

---

### **阶段3：创建控件层** (优先级：🟡 高)

#### 3.1 提取主窗口样式

**文件**: `resources/styles/widgets/main_window.qss`

**数据来源**: 从 `ui/ue_main_window.py` 的 `_get_dark_theme_stylesheet()` 方法中提取

**提取步骤**:
1. 打开 `ui/ue_main_window.py`
2. 找到 `_get_dark_theme_stylesheet()` 方法
3. 复制所有CSS规则
4. 将硬编码颜色替换为变量占位符

**示例转换**:
```css
/* 原始（内联样式） */
#MainContainer {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #1c1c1c, stop:1 #2c2c2c);
}

/* 转换后（QSS文件） */
#MainContainer {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 ${bg_gradient_start}, stop:1 ${bg_gradient_end});
}
```

---

#### 3.2 提取启动界面样式

**文件**: `resources/styles/widgets/splash_screen.qss`

**数据来源**: 从 `ui/splash_screen.py` 的内联样式中提取

**提取步骤**:
1. 打开 `ui/splash_screen.py`
2. 找到 `_init_ui()` 方法中的 `setStyleSheet()` 调用
3. 复制CSS规则
4. 将硬编码颜色替换为变量占位符

---

### **阶段4：创建构建器** (优先级：🔴 最高)

#### 4.1 创建智能主题构建器

**文件**: `core/utils/theme_builder.py`

**核心功能**:
1. 自动检测 `core/`, `widgets/`, `modules/` 目录下的QSS文件
2. 按固定顺序拼接（core → widgets → modules）
3. 从Python配置加载主题变量
4. 替换QSS中的 `${variable}` 占位符
5. 生成完整主题文件到 `themes/` 目录

**完整代码**: 查看对话历史中的 `ThemeBuilder` 类实现（约200行）

**关键方法**:
- `build_theme(theme_name)`: 构建单个主题
- `save_theme(theme_name)`: 构建并保存主题
- `build_all_themes()`: 构建所有主题
- `_load_layer_qss(layer_dir)`: 加载某一层的QSS文件
- `_load_theme_variables(theme_name)`: 加载主题变量
- `_replace_variables(qss, variables)`: 替换变量占位符

---

#### 4.2 创建样式系统核心

**文件**: `core/utils/style_system.py`

**核心功能**:
1. 统一入口：加载和应用主题
2. 缓存机制：内存缓存已加载主题
3. 预加载：启动时预加载常用主题
4. 主题切换：运行时切换主题

**完整代码**: 查看对话历史中的 `StyleSystem` 类实现（约150行）

**关键方法**:
- `load_theme(theme_name)`: 加载主题（带缓存）
- `apply_theme(app, theme_name)`: 应用主题到应用程序
- `apply_to_widget(widget, theme_name)`: 应用主题到控件
- `_preload_themes(theme_names)`: 预加载主题

---

### **阶段5：修改主程序** (优先级：🟡 高)

#### 5.1 修改主窗口

**文件**: `ui/ue_main_window.py`

**修改步骤**:
1. 删除 `_get_stylesheet()`, `_get_dark_theme_stylesheet()`, `_get_light_theme_stylesheet()` 方法
2. 删除 `self.is_dark_theme` 属性
3. 修改 `init_ui()` 方法，移除 `self.setStyleSheet(self._get_stylesheet())`
4. 修改 `toggle_theme()` 方法，使用 `StyleSystem` 切换主题

**修改后的 `toggle_theme()` 方法**:
```python
def toggle_theme(self):
    """切换主题"""
    from core.utils.style_system import style_system
    
    # 切换主题
    new_theme = 'modern_light' if style_system.current_theme == 'modern_dark' else 'modern_dark'
    
    # 应用主题
    app = QApplication.instance()
    style_system.apply_theme(app, new_theme)
    
    # 更新主题按钮图标
    if new_theme == 'modern_dark':
        self.theme_button.setText("🌙")
        self.theme_button.setToolTip("切换到浅色模式")
    else:
        self.theme_button.setText("☀️")
        self.theme_button.setToolTip("切换到深色模式")
```

---

#### 5.2 修改启动界面

**文件**: `ui/splash_screen.py`

**修改步骤**:
1. 删除 `_init_ui()` 方法中的 `setStyleSheet()` 调用
2. 样式由全局主题控制（无需单独设置）

---

#### 5.3 修改主入口

**文件**: `main.py`

**修改步骤**:
1. 在创建 `QApplication` 后，立即应用主题
2. 在显示主窗口前，确保主题已加载

**修改后的代码**:
```python
def main():
    app = QApplication(sys.argv)
    
    # ⭐ 应用主题
    from core.utils.style_system import style_system
    style_system.apply_theme(app, "modern_dark")
    
    # 创建启动界面
    splash = SplashScreen()
    splash.show()
    
    # ... 其他初始化代码 ...
    
    # 创建主窗口
    main_window = UEMainWindow(module_provider)
    main_window.show()
    
    # 关闭启动界面
    splash.finish()
    
    sys.exit(app.exec())
```

---

### **阶段6：构建和测试** (优先级：🟡 高)

#### 6.1 构建主题文件

**创建构建脚本**: `build_themes.py`

```python
# -*- coding: utf-8 -*-
"""构建所有主题"""

from pathlib import Path
import sys

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from core.utils.theme_builder import ThemeBuilder

def main():
    """构建所有主题"""
    styles_root = Path(__file__).parent / "resources" / "styles"
    
    builder = ThemeBuilder(styles_root)
    
    # 构建所有主题
    output_files = builder.build_all_themes()
    
    print(f"\n✅ 成功构建 {len(output_files)} 个主题:")
    for file in output_files:
        print(f"   - {file.name}")

if __name__ == "__main__":
    main()
```

**运行构建**:
```bash
python build_themes.py
```

**预期输出**:
```
🎨 发现 4 个主题配置:
   - dark
   - light
   - modern_dark
   - modern_light

🎨 开始构建主题: dark
📦 加载主题变量...
   ✅ 加载了 45 个变量
📂 加载 core/ 目录...
   📄 base.qss
   📄 components.qss
   ✅ 加载了 15000 字符
...
✅ 主题构建完成！

✅ 成功构建 4/4 个主题:
   - dark.qss
   - light.qss
   - modern_dark.qss
   - modern_light.qss
```

---

#### 6.2 测试主题加载

**创建测试脚本**: `test_themes.py`

```python
# -*- coding: utf-8 -*-
"""测试主题系统"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget
from core.utils.style_system import style_system

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("主题测试")
        self.resize(400, 300)
        
        # 创建测试按钮
        central = QWidget()
        layout = QVBoxLayout(central)
        
        btn_dark = QPushButton("切换到深色主题")
        btn_dark.clicked.connect(lambda: self.switch_theme("modern_dark"))
        layout.addWidget(btn_dark)
        
        btn_light = QPushButton("切换到浅色主题")
        btn_light.clicked.connect(lambda: self.switch_theme("modern_light"))
        layout.addWidget(btn_light)
        
        self.setCentralWidget(central)
    
    def switch_theme(self, theme_name):
        app = QApplication.instance()
        style_system.apply_theme(app, theme_name)
        print(f"✅ 已切换到主题: {theme_name}")

def main():
    app = QApplication(sys.argv)
    
    # 应用默认主题
    style_system.apply_theme(app, "modern_dark")
    
    window = TestWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
```

**运行测试**:
```bash
python test_themes.py
```

---

## ⚠️ 注意事项

### 1. 样式一致性
- **必须保证**: 提取后的QSS样式与原内联样式**完全一致**
- **验证方法**: 对比运行前后的UI截图，确保无差异
- **关键点**: 圆角、渐变、颜色、间距都不能变

### 2. 变量命名
- **统一规范**: 使用 `bg_*`, `text_*`, `border_*` 等前缀
- **避免冲突**: 确保变量名在所有主题中一致
- **清晰明了**: 变量名要能表达含义

### 3. 文件编码
- **统一使用**: UTF-8 编码
- **避免BOM**: 不要使用 UTF-8 with BOM
- **换行符**: 统一使用 LF（\n）

### 4. 性能优化
- **预生成主题**: 构建时生成，运行时直接加载
- **启用缓存**: 避免重复加载
- **按需加载**: 模块样式延迟加载

### 5. 调试技巧
- **查看生成的主题文件**: `resources/styles/themes/modern_dark.qss`
- **检查变量替换**: 确保没有未替换的 `${variable}`
- **使用Qt样式表调试器**: Qt Creator 的样式表编辑器

---

## 📊 验收标准

### 功能验收
- [ ] 主题文件成功生成（`themes/modern_dark.qss`, `themes/modern_light.qss`）
- [ ] 主程序正常启动（`python main.py`）
- [ ] 主题切换正常（点击主题按钮，UI立即切换）
- [ ] 样式完全一致（与原内联样式对比，无差异）
- [ ] 所有模块正常显示（资产库、AI助手等）

### 性能验收
- [ ] 启动时间 < 100ms（从加载主题到显示主窗口）
- [ ] 主题切换 < 50ms（点击按钮到UI更新完成）
- [ ] 内存占用合理（< 1MB用于样式缓存）

### 代码质量
- [ ] 无硬编码颜色（所有颜色都使用变量）
- [ ] 注释完整（每个文件都有文件头注释）
- [ ] 代码规范（符合PEP 8）
- [ ] 无警告错误（运行时无Python警告）

---

## 🔗 参考资料

### 对话历史关键内容
1. **方案A完整结构**: 搜索 "方案A - 完整文件结构"
2. **ThemeBuilder实现**: 搜索 "智能主题构建器"
3. **StyleSystem实现**: 搜索 "样式系统核心"
4. **性能优化方案**: 搜索 "终极优化方案"
5. **components.qss示例**: 搜索 "core/components.qss"

### 现有文件
- `ui/ue_main_window.py`: 主窗口（包含完整的深色/浅色主题CSS）
- `ui/splash_screen.py`: 启动界面（包含内联CSS）
- `UI_Review/main_window_preview.py`: 预览版本（参考样式）

### Qt文档
- [Qt Style Sheets Reference](https://doc.qt.io/qt-6/stylesheet-reference.html)
- [Qt Style Sheets Examples](https://doc.qt.io/qt-6/stylesheet-examples.html)

---

## 🚀 快速开始

### 最小可行实现（MVP）

如果时间紧迫，可以先实现最小版本：

1. **只创建 modern_dark 主题**（跳过其他主题）
2. **只提取主窗口样式**（跳过其他控件）
3. **手动构建主题**（跳过自动构建脚本）

**步骤**:
```bash
# 1. 创建配置
mkdir -p resources/styles/config/themes
# 创建 variables.py 和 modern_dark.py

# 2. 创建核心样式
mkdir -p resources/styles/core
# 创建 base.qss 和 components.qss

# 3. 创建主窗口样式
mkdir -p resources/styles/widgets
# 创建 main_window.qss（从 ue_main_window.py 提取）

# 4. 手动合并生成主题
cat core/base.qss core/components.qss widgets/main_window.qss > themes/modern_dark.qss
# 手动替换变量（Ctrl+H批量替换）

# 5. 修改主程序使用QSS
# 修改 main.py 和 ue_main_window.py

# 6. 测试
python main.py
```

---

## 📝 总结

### 核心要点
1. **文件结构**: config → core → widgets → modules → themes
2. **变量系统**: Python配置 + QSS占位符
3. **智能构建**: 自动检测、拼接、替换
4. **性能优化**: 预生成 + 缓存 + 延迟加载
5. **样式一致**: 必须与原内联样式完全相同

### 预期成果
- ✅ 样式外部化，易于维护
- ✅ 主题系统完善，易于扩展
- ✅ 性能优化到位，启动快速
- ✅ 代码质量高，结构清晰

### 下一步
完成QSS系统后，可以继续：
1. 添加更多主题（赛博朋克、护眼绿等）
2. 实现模块UI（AI助手、资产管理器等）
3. 添加主题编辑器（让用户自定义主题）

---

**祝实施顺利！** 🎉

如有疑问，请参考对话历史或查看现有代码。

