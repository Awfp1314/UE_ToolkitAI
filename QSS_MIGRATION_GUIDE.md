# 🎨 QSS样式系统迁移指南

> **目标**：将任何使用内联样式的界面/弹窗迁移到统一的QSS样式系统  
> **原则**：样式100%保持不变，只改变样式的存储位置和应用方式

---

## 📋 目录

1. [系统架构](#系统架构)
2. [迁移步骤](#迁移步骤)
3. [文件结构规范](#文件结构规范)
4. [代码规范](#代码规范)
5. [常见场景示例](#常见场景示例)
6. [验收标准](#验收标准)

---

## 🏗️ 系统架构

### 核心组件

```
QSS样式系统
├── 配置层 (Python)
│   ├── resources/styles/config/variables.py          # 全局变量（间距、圆角、字体等）
│   └── resources/styles/config/themes/               # 主题配置
│       ├── modern_dark.py                            # 深色主题颜色变量
│       └── modern_light.py                           # 浅色主题颜色变量
│
├── 样式层 (QSS)
│   ├── resources/styles/core/                        # 核心样式
│   │   ├── base.qss                                  # 全局基础样式
│   │   └── components.qss                            # 通用组件样式
│   ├── resources/styles/widgets/                     # 控件样式
│   │   ├── main_window.qss                           # 主窗口样式
│   │   ├── dialog.qss                                # 对话框样式
│   │   └── [your_widget].qss                         # 你的控件样式
│   └── resources/styles/modules/                     # 模块样式
│       └── [module_name]/                            # 模块专属样式
│
├── 构建层 (Python)
│   └── core/utils/theme_builder.py                   # 主题构建器（变量替换）
│
├── 运行时层 (Python)
│   └── core/utils/style_system.py                    # 样式系统（加载、缓存、切换）
│
└── 输出层 (生成的QSS)
    └── resources/styles/themes/                      # 构建后的完整主题
        ├── modern_dark.qss                           # 深色主题（已替换变量）
        └── modern_light.qss                          # 浅色主题（已替换变量）
```

### 工作流程

```
1. 编写QSS文件（使用 ${变量名} 占位符）
   ↓
2. 运行 build_themes.py 构建主题（替换变量）
   ↓
3. 应用程序启动时加载主题（style_system.apply_theme()）
   ↓
4. 用户可以动态切换主题（自动重新加载QSS）
```

---

## 🚀 迁移步骤

### 步骤1️⃣：提取内联样式

**目标**：找到所有 `setStyleSheet()` 调用，提取CSS代码

#### 1.1 搜索内联样式

```python
# 在你的Python文件中搜索以下模式：
- setStyleSheet()
- setStyleSheet("""...""")
- setStyleSheet("...")
- setStyleSheet(f"...")
```

#### 1.2 记录样式信息

为每个控件记录：
- **控件类型**：QPushButton / QLabel / QDialog 等
- **ObjectName**：如果有 `setObjectName("xxx")`
- **CSS内容**：完整的样式字符串
- **颜色值**：所有用到的颜色（#rrggbb 或 rgba()）

**示例**：

```python
# 原始代码
btn = QPushButton("确定")
btn.setStyleSheet("""
    QPushButton {
        background: #4a9eff;
        color: #ffffff;
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 8px;
        padding: 8px 16px;
    }
    QPushButton:hover {
        background: #5aa9ff;
    }
""")
```

**记录**：
- 控件：QPushButton
- 背景色：`#4a9eff` (正常), `#5aa9ff` (悬停)
- 文字色：`#ffffff`
- 边框：`rgba(255, 255, 255, 0.2)`
- 圆角：`8px`
- 内边距：`8px 16px`

---

### 步骤2️⃣：创建QSS文件

**目标**：将提取的样式写入独立的QSS文件

#### 2.1 确定文件位置

根据控件类型选择目录：

| 控件类型 | QSS文件位置 | 示例 |
|---------|------------|------|
| 主窗口 | `resources/styles/widgets/main_window.qss` | 已存在 |
| 对话框/弹窗 | `resources/styles/widgets/[dialog_name].qss` | `confirm_dialog.qss` |
| 自定义控件 | `resources/styles/widgets/[widget_name].qss` | `custom_button.qss` |
| 模块专属 | `resources/styles/modules/[module]/[widget].qss` | `ai_assistant/chat_widget.qss` |

#### 2.2 编写QSS文件

**规范**：
1. ✅ 使用 `${变量名}` 占位符代替硬编码颜色
2. ✅ 为控件设置 `#ObjectName` 选择器
3. ✅ 添加清晰的注释
4. ✅ 保持原始样式的所有细节（渐变、阴影、过渡等）

**示例**：

```css
/* ===== 确认按钮 ===== */
#ConfirmButton {
    background: ${primary};
    color: ${text_primary};
    border: 1px solid ${border_primary};
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 14px;
    font-weight: 500;
}

#ConfirmButton:hover {
    background: ${primary_hover};
    border-color: ${primary_border_hover};
}

#ConfirmButton:pressed {
    background: ${primary_active};
}

#ConfirmButton:disabled {
    background: ${bg_tertiary};
    color: ${text_disabled};
    border-color: ${border_tertiary};
}
```

---

### 步骤3️⃣：添加颜色变量

**目标**：将新颜色添加到主题配置文件

#### 3.1 检查现有变量

打开 `resources/styles/config/themes/modern_dark.py`，查看是否已有需要的颜色变量。

**现有变量示例**：
```python
COLORS = {
    'primary': '#4a9eff',              # 主色调
    'primary_hover': '#5aa9ff',        # 主色调悬停
    'text_primary': '#ffffff',         # 主要文字
    'border_primary': 'rgba(255, 255, 255, 0.2)',  # 主要边框
    # ... 更多变量
}
```

#### 3.2 添加新变量（如果需要）

如果你的样式使用了新颜色，添加到 `COLORS` 字典：

```python
# modern_dark.py
COLORS = {
    # ... 现有变量 ...
    
    # 你的新变量
    'dialog_bg': '#2c2c2c',
    'dialog_border': 'rgba(255, 255, 255, 0.15)',
    'dialog_shadow': 'rgba(0, 0, 0, 0.5)',
}
```

**⚠️ 重要**：同时在 `modern_light.py` 中添加对应的浅色版本！

```python
# modern_light.py
COLORS = {
    # ... 现有变量 ...
    
    # 对应的浅色版本
    'dialog_bg': '#ffffff',
    'dialog_border': 'rgba(0, 0, 0, 0.15)',
    'dialog_shadow': 'rgba(0, 0, 0, 0.3)',
}
```

---

### 步骤4️⃣：修改Python代码

**目标**：删除内联样式，使用ObjectName关联QSS

#### 4.1 删除 setStyleSheet() 调用

```python
# ❌ 删除前
btn = QPushButton("确定")
btn.setStyleSheet("""
    QPushButton {
        background: #4a9eff;
        color: #ffffff;
        ...
    }
""")

# ✅ 删除后
btn = QPushButton("确定")
btn.setObjectName("ConfirmButton")  # ⭐ 设置ObjectName关联QSS
```

#### 4.2 特殊情况处理

**情况1：QLabel中的HTML样式**

```python
# ⚠️ 保留 - QSS无法控制HTML内部样式
label = QLabel('<span style="color: #ffffff;">标题</span>')
```

**情况2：动态样式**

```python
# ❌ 不要这样做
def update_color(self, color):
    self.widget.setStyleSheet(f"background: {color};")

# ✅ 应该这样做 - 使用属性 + QSS
def update_color(self, color):
    self.widget.setProperty("color_state", color)
    self.widget.style().unpolish(self.widget)
    self.widget.style().polish(self.widget)

# 在QSS中：
# #Widget[color_state="red"] { background: #ff0000; }
# #Widget[color_state="green"] { background: #00ff00; }
```

---

### 步骤5️⃣：构建主题

**目标**：生成包含你的样式的完整主题文件

#### 5.1 运行构建脚本

```bash
# 构建所有主题
python build_themes.py

# 或构建单个主题
python build_themes.py --theme modern_dark
python build_themes.py --theme modern_light
```

#### 5.2 验证构建结果

检查生成的文件：
- `resources/styles/themes/modern_dark.qss`
- `resources/styles/themes/modern_light.qss`

确认：
- ✅ 文件大小合理（不为空）
- ✅ 所有 `${变量}` 都已被替换
- ✅ 你的样式已包含在内

---

### 步骤6️⃣：应用样式

**目标**：在应用程序中加载新样式

#### 6.1 应用程序级别（推荐）

在 `main.py` 中已经应用了全局主题：

```python
from core.utils.style_system import style_system

# 应用主题到整个应用
style_system.apply_theme(app, "modern_dark")
```

**✅ 你不需要做任何事情** - 新样式会自动生效！

#### 6.2 控件级别（特殊情况）

如果需要为单个控件应用样式：

```python
from core.utils.style_system import style_system

# 应用主题到单个控件
style_system.apply_to_widget(my_widget, "modern_dark")
```

---

## 📁 文件结构规范

### 命名规范

| 文件类型 | 命名规则 | 示例 |
|---------|---------|------|
| QSS文件 | 小写+下划线 | `confirm_dialog.qss` |
| Python配置 | 小写+下划线 | `modern_dark.py` |
| ObjectName | 大驼峰 | `ConfirmButton` |
| 变量名 | 小写+下划线 | `primary_hover` |

### 目录组织

```
resources/styles/
├── config/                    # 配置文件（不要修改现有文件）
│   ├── variables.py           # 全局变量
│   └── themes/
│       ├── modern_dark.py     # 深色主题（添加新颜色变量）
│       └── modern_light.py    # 浅色主题（添加新颜色变量）
│
├── core/                      # 核心样式（谨慎修改）
│   ├── base.qss
│   └── components.qss
│
├── widgets/                   # ⭐ 你的主要工作目录
│   ├── main_window.qss        # 已存在
│   ├── [your_dialog].qss      # 添加你的对话框样式
│   └── [your_widget].qss      # 添加你的控件样式
│
└── modules/                   # 模块专属样式
    └── [module_name]/
        └── [widget].qss
```

---

## 💻 代码规范

### QSS编写规范

#### 1. 选择器规范

```css
/* ✅ 推荐：使用ObjectName选择器 */
#MyButton { ... }

/* ✅ 可以：类型选择器（影响所有同类型控件） */
QPushButton { ... }

/* ✅ 可以：组合选择器 */
#MyDialog QPushButton { ... }

/* ❌ 避免：过于复杂的选择器 */
#MyDialog > QWidget > QHBoxLayout > QPushButton:hover:!pressed { ... }
```

#### 2. 变量使用规范

```css
/* ✅ 推荐：使用语义化变量 */
background: ${primary};
color: ${text_primary};
border: 1px solid ${border_primary};

/* ❌ 避免：硬编码颜色 */
background: #4a9eff;
color: #ffffff;

/* ⚠️ 例外：特殊颜色可以硬编码 */
background: transparent;  /* OK */
color: inherit;           /* OK */
```

#### 3. 注释规范

```css
/* ===== 大标题（组件级别） ===== */

/* ----- 小标题（状态级别） ----- */

/* 单行说明 */
```

#### 4. 格式规范

```css
/* ✅ 推荐：清晰的格式 */
#MyButton {
    background: ${primary};
    color: ${text_primary};
    border: 1px solid ${border_primary};
    border-radius: 8px;
    padding: 8px 16px;
}

/* ❌ 避免：压缩格式 */
#MyButton{background:${primary};color:${text_primary};}
```

### Python代码规范

#### 1. ObjectName设置

```python
# ✅ 推荐：创建控件后立即设置
widget = QWidget()
widget.setObjectName("MyWidget")

# ✅ 推荐：使用有意义的名称
button = QPushButton("确定")
button.setObjectName("ConfirmButton")  # 清晰明确

# ❌ 避免：无意义的名称
button.setObjectName("btn1")  # 不清楚用途
```

#### 2. 样式相关代码删除

```python
# ❌ 删除所有这些
widget.setStyleSheet("...")
widget.setStyleSheet("""...""")
widget.setStyleSheet(f"...")

# ❌ 删除样式方法
def _get_stylesheet(self):
    return "..."

# ✅ 保留：设置ObjectName
widget.setObjectName("MyWidget")

# ✅ 保留：HTML内联样式（QSS无法控制）
label.setText('<span style="color: #fff;">文本</span>')
```

---

## 🎯 常见场景示例

### 场景1：迁移对话框

**原始代码**：

```python
class ConfirmDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QDialog {
                background: #2c2c2c;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 12px;
            }
            QPushButton {
                background: #4a9eff;
                color: #ffffff;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: #5aa9ff;
            }
        """)
```

**迁移步骤**：

1. **创建QSS文件** `resources/styles/widgets/confirm_dialog.qss`：

```css
/* ===== 确认对话框 ===== */
#ConfirmDialog {
    background: ${bg_tertiary};
    border: 1px solid ${border_primary};
    border-radius: 12px;
}

/* ===== 对话框按钮 ===== */
#ConfirmDialog QPushButton {
    background: ${primary};
    color: ${text_primary};
    border-radius: 6px;
    padding: 8px 16px;
}

#ConfirmDialog QPushButton:hover {
    background: ${primary_hover};
}
```

2. **修改Python代码**：

```python
class ConfirmDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ConfirmDialog")  # ⭐ 设置ObjectName
        # ✅ 删除了 setStyleSheet()
```

3. **构建主题**：

```bash
python build_themes.py
```

4. **完成** ✅ - 样式自动生效！

---

### 场景2：迁移自定义控件

**原始代码**：

```python
class StatusLabel(QLabel):
    def __init__(self, text, status="normal"):
        super().__init__(text)
        self.update_status(status)
    
    def update_status(self, status):
        if status == "success":
            self.setStyleSheet("background: #10a37f; color: #ffffff;")
        elif status == "error":
            self.setStyleSheet("background: #ef4444; color: #ffffff;")
        else:
            self.setStyleSheet("background: #4a9eff; color: #ffffff;")
```

**迁移方案**：使用Qt属性

1. **创建QSS文件** `resources/styles/widgets/status_label.qss`：

```css
/* ===== 状态标签 ===== */
#StatusLabel {
    padding: 4px 12px;
    border-radius: 4px;
    font-weight: 500;
}

/* 不同状态 */
#StatusLabel[status="normal"] {
    background: ${info};
    color: ${text_primary};
}

#StatusLabel[status="success"] {
    background: ${success};
    color: ${text_primary};
}

#StatusLabel[status="error"] {
    background: ${error};
    color: ${text_primary};
}
```

2. **修改Python代码**：

```python
class StatusLabel(QLabel):
    def __init__(self, text, status="normal"):
        super().__init__(text)
        self.setObjectName("StatusLabel")  # ⭐ 设置ObjectName
        self.update_status(status)
    
    def update_status(self, status):
        # ✅ 使用属性而不是setStyleSheet
        self.setProperty("status", status)
        # 刷新样式
        self.style().unpolish(self)
        self.style().polish(self)
```

3. **添加颜色变量**（如果需要）：

```python
# modern_dark.py 和 modern_light.py 中已有：
COLORS = {
    'success': '#10a37f',
    'error': '#ef4444',
    'info': '#4a9eff',
}
```

4. **构建并测试** ✅

---

### 场景3：迁移带渐变的复杂样式

**原始代码**：

```python
panel.setStyleSheet("""
    QWidget {
        background: qlineargradient(
            x1:0, y1:0, x2:0, y2:1,
            stop:0 #1c1c1c,
            stop:0.5 #1a1a1a,
            stop:1 #181818
        );
        border-right: 2px solid rgba(255, 255, 255, 0.08);
    }
""")
```

**迁移步骤**：

1. **提取渐变颜色**：
   - `stop:0` → `#1c1c1c`
   - `stop:0.5` → `#1a1a1a`
   - `stop:1` → `#181818`

2. **添加到主题配置**：

```python
# modern_dark.py
COLORS = {
    'panel_gradient_start': '#1c1c1c',
    'panel_gradient_mid': '#1a1a1a',
    'panel_gradient_end': '#181818',
    'panel_border': 'rgba(255, 255, 255, 0.08)',
}
```

3. **创建QSS**：

```css
#MyPanel {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 ${panel_gradient_start},
        stop:0.5 ${panel_gradient_mid},
        stop:1 ${panel_gradient_end}
    );
    border-right: 2px solid ${panel_border};
}
```

4. **修改代码**：

```python
panel.setObjectName("MyPanel")
# ✅ 删除 setStyleSheet()
```

---

## ✅ 验收标准

### 必须满足

- [ ] **所有 `setStyleSheet()` 已删除**（除了HTML内联样式）
- [ ] **所有控件都设置了 `setObjectName()`**
- [ ] **QSS文件使用 `${变量}` 占位符**（不硬编码颜色）
- [ ] **深色和浅色主题都已更新**
- [ ] **主题构建成功**（无错误）
- [ ] **视觉效果100%一致**（与迁移前完全相同）

### 推荐检查

- [ ] QSS文件有清晰的注释
- [ ] ObjectName命名有意义
- [ ] 新变量已添加到两个主题
- [ ] 代码格式规范
- [ ] 没有重复的样式定义

### 测试清单

- [ ] 启动应用程序，界面正常显示
- [ ] 切换深色/浅色主题，样式正确切换
- [ ] 所有交互状态正常（hover、pressed、disabled等）
- [ ] 没有控制台错误或警告
- [ ] 性能无明显下降

---

## 🆘 常见问题

### Q1: 变量没有被替换？

**原因**：主题未重新构建

**解决**：
```bash
python build_themes.py
```

### Q2: 样式没有生效？

**检查**：
1. ObjectName是否设置正确？
2. QSS选择器是否匹配？
3. 主题是否重新构建？
4. 应用程序是否重启？

### Q3: 如何调试QSS？

**方法**：
1. 查看生成的 `resources/styles/themes/modern_dark.qss`
2. 确认你的样式是否包含在内
3. 确认变量是否正确替换
4. 使用Qt的样式表调试工具

### Q4: 可以混用内联样式和QSS吗？

**不推荐**！
- ❌ 内联样式优先级更高，会覆盖QSS
- ❌ 导致主题切换失效
- ✅ 全部迁移到QSS系统

---

## 📚 参考资源

- **主窗口迁移示例**：`ui/ue_main_window.py`（已完成迁移）
- **QSS语法参考**：[Qt Style Sheets Reference](https://doc.qt.io/qt-6/stylesheet-reference.html)
- **主题构建器**：`core/utils/theme_builder.py`
- **样式系统**：`core/utils/style_system.py`

---

## 🎉 迁移完成！

恭喜！你已经成功将界面迁移到QSS样式系统。

**下一步**：
- 测试所有功能
- 提交代码
- 继续迁移其他界面

**有问题？** 参考 `ui/ue_main_window.py` 的迁移实现！

