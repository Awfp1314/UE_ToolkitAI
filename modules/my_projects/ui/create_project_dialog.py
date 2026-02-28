# -*- coding: utf-8 -*-

"""
创建工程向导 - 三步流程：
1. 选择项目类型
2. 选择模板
3. 设置名称、路径、代码类型、初学者内容包
"""

from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QComboBox, QWidget,
    QFileDialog, QGridLayout, QFrame, QScrollArea,
    QStackedWidget, QApplication
)
from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QThread
from PyQt6.QtGui import QFont

from core.logger import get_logger
from modules.my_projects.logic.engine_scanner import (
    EngineInfo, TemplateInfo, PROJECT_CATEGORIES, EngineScanner
)
from modules.my_projects.logic.project_creator import ProjectCreator
from modules.asset_manager.ui.custom_checkbox import CustomCheckBox

logger = get_logger(__name__)


class _EngineScanThread(QThread):
    """后台扫描引擎线程"""
    finished = pyqtSignal(list)

    def run(self):
        self.finished.emit(EngineScanner.scan_installed_engines())


# ── 可复用的卡片组件 ──

class _ClickableCard(QFrame):
    """可点击的卡片基类"""
    clicked = pyqtSignal(object)

    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.data = data
        self._selected = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_selected(self, selected: bool):
        self._selected = selected
        if selected:
            self.setStyleSheet(f"""
                QFrame#{self.objectName()} {{
                    border: 2px solid #e8a025;
                    border-radius: 6px;
                    background: rgba(232, 160, 37, 0.15);
                }}
                QFrame#{self.objectName()} QLabel {{
                    background: transparent;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame#{self.objectName()} {{
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 6px;
                    background: rgba(255, 255, 255, 0.03);
                }}
                QFrame#{self.objectName()}:hover {{
                    border: 1px solid rgba(255, 255, 255, 0.2);
                    background: rgba(255, 255, 255, 0.06);
                }}
                QFrame#{self.objectName()} QLabel {{
                    background: transparent;
                }}
            """)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.data)
        super().mousePressEvent(event)


class _CategoryCard(_ClickableCard):
    """项目类型卡片（大卡片）"""

    _ICONS = {
        "游戏": "🎮",
        "影视与现场活动": "🎬",
        "建筑、工程与施工": "🏗️",
        "汽车、产品设计和制造": "🚗",
        "空白工程": "📄",
    }
    _DESCS = {
        "游戏": "使用关键职业、关卡和示例开始游戏开发",
        "影视与现场活动": "适用于 nDisplay、VR 探查和虚拟制片",
        "建筑、工程与施工": "照片级建筑设计可视化和阳光研究",
        "汽车、产品设计和制造": "产品配置器和 Photobooth 工作室",
        "空白工程": "创建一个空白的虚幻引擎工程",
    }

    def __init__(self, category: str, parent=None):
        super().__init__(category, parent)
        self.setObjectName("CategoryCard")
        self.setFixedHeight(70)
        self._init_ui(category)
        self.set_selected(False)

    def _init_ui(self, category):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(14)

        icon = QLabel(self._ICONS.get(category, "📁"))
        icon.setStyleSheet("font-size: 28px; background: transparent;")
        icon.setFixedWidth(40)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        title = QLabel(category)
        title.setStyleSheet("font-size: 14px; font-weight: bold; background: transparent;")
        text_layout.addWidget(title)

        desc = QLabel(self._DESCS.get(category, ""))
        desc.setStyleSheet("font-size: 11px; color: rgba(255,255,255,0.5); background: transparent;")
        desc.setWordWrap(True)
        text_layout.addWidget(desc)

        layout.addLayout(text_layout, 1)


class _TemplateCard(_ClickableCard):
    """模板卡片 - 显示引擎自带的模板缩略图"""

    def __init__(self, template: TemplateInfo, parent=None):
        super().__init__(template, parent)
        self.setObjectName("TemplateCard")
        self.setMinimumSize(150, 130)
        self.setMaximumHeight(140)
        self._init_ui(template)
        self.set_selected(False)

    def _init_ui(self, template):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 缩略图（优先使用引擎自带图标）
        thumb_label = QLabel()
        thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb_label.setFixedSize(138, 90)
        thumb_label.setStyleSheet("background: rgba(0,0,0,0.3); border-radius: 4px;")

        loaded = False
        if template.thumbnail:
            from PyQt6.QtGui import QPixmap
            pixmap = QPixmap(template.thumbnail)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    138, 90,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                thumb_label.setPixmap(scaled)
                thumb_label.setStyleSheet("background: rgba(0,0,0,0.3); border-radius: 4px;")
                loaded = True

        if not loaded:
            thumb_label.setText("📁")
            thumb_label.setStyleSheet("background: rgba(0,0,0,0.3); border-radius: 4px; font-size: 32px; color: rgba(255,255,255,0.4);")

        layout.addWidget(thumb_label)

        # 名称
        name = QLabel(template.name)
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setWordWrap(True)
        name.setStyleSheet("font-size: 11px; background: transparent; color: rgba(255,255,255,0.85);")
        name.setFixedHeight(22)
        layout.addWidget(name)


# ── 三步向导主对话框 ──

class CreateProjectWizard(QDialog):
    """创建工程向导"""

    project_created = pyqtSignal(str)

    def __init__(self, engine: EngineInfo, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.selected_category = None
        self.selected_template = None
        self._cards = []
        self.drag_position = QPoint()

        self._init_ui()
        self._show_page(0)

    def _init_ui(self):
        self.setModal(True)
        self.setFixedSize(620, 540)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setObjectName("AddAssetDialog")

        container = QWidget()
        container.setObjectName("AddAssetDialogContainer")
        main = QVBoxLayout()
        main.setSpacing(0)
        main.setContentsMargins(0, 0, 0, 0)

        # 标题栏
        main.addWidget(self._build_title_bar())

        # 内容（三页堆叠）
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_page_category())   # 0
        self.stack.addWidget(self._build_page_template())    # 1
        self.stack.addWidget(self._build_page_settings())    # 2
        main.addWidget(self.stack)

        container.setLayout(main)
        dlg = QVBoxLayout(self)
        dlg.setContentsMargins(0, 0, 0, 0)
        dlg.addWidget(container)

    # ── 标题栏 ──

    def _build_title_bar(self):
        bar = QWidget()
        bar.setObjectName("AddAssetDialogTitleBar")
        bar.setFixedHeight(50)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(25, 0, 25, 0)

        icon = QLabel("🎮")
        icon.setObjectName("AddAssetDialogTitleIcon")
        layout.addWidget(icon)

        self.title_label = QLabel("创建工程 — 选择项目类型")
        self.title_label.setObjectName("AddAssetDialogTitleLabel")
        layout.addWidget(self.title_label)
        layout.addStretch()

        # 引擎版本标签
        ver = QLabel(f"UE {self.engine.version}")
        ver.setStyleSheet("color: rgba(255,255,255,0.4); font-size: 12px;")
        layout.addWidget(ver)

        close = QPushButton("✕")
        close.setObjectName("CategoryDialogCloseButton")
        close.setFixedSize(32, 32)
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        close.clicked.connect(self.reject)
        layout.addWidget(close)

        bar.mousePressEvent = self._title_press
        bar.mouseMoveEvent = self._title_move
        return bar

    # ── 第1页：项目类型 ──

    def _build_page_category(self):
        page = QWidget()
        page.setObjectName("AddAssetDialogContent")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(10)

        lbl = QLabel("选择项目类型")
        lbl.setObjectName("AddAssetDialogLabel")
        lbl.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(lbl)

        # 项目类型卡片列表
        available = set(t.category for t in self.engine.templates)
        categories = [c for c in PROJECT_CATEGORIES if c in available]
        categories.insert(0, "空白工程")

        self._cat_cards = []
        for cat in categories:
            card = _CategoryCard(cat)
            card.clicked.connect(self._on_category_picked)
            layout.addWidget(card)
            self._cat_cards.append(card)

        layout.addStretch()

        # 取消按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("取消")
        cancel.setObjectName("AddAssetDialogCancelBtn")
        cancel.setFixedSize(100, 38)
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        layout.addLayout(btn_row)

        return page

    # ── 第2页：模板选择 ──

    def _build_page_template(self):
        page = QWidget()
        page.setObjectName("AddAssetDialogContent")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(15, 20, 15, 20)
        layout.setSpacing(10)

        self.tmpl_title = QLabel("选择模板")
        self.tmpl_title.setObjectName("AddAssetDialogLabel")
        self.tmpl_title.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(self.tmpl_title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollArea > QWidget > QWidget { background: transparent; }
            QWidget#_tmplContainer { background: transparent; }
        """)
        scroll.viewport().setStyleSheet("background: transparent;")

        self.tmpl_container = QWidget()
        self.tmpl_container.setObjectName("_tmplContainer")
        self.tmpl_grid = QGridLayout(self.tmpl_container)
        self.tmpl_grid.setContentsMargins(0, 0, 0, 0)
        self.tmpl_grid.setSpacing(12)
        self.tmpl_grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self.tmpl_container)
        layout.addWidget(scroll, 1)

        # 返回 / 下一步
        btn_row = QHBoxLayout()
        back = QPushButton("← 返回")
        back.setObjectName("AddAssetDialogCancelBtn")
        back.setFixedSize(100, 38)
        back.setCursor(Qt.CursorShape.PointingHandCursor)
        back.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        back.clicked.connect(lambda: self._show_page(0))
        btn_row.addWidget(back)
        btn_row.addStretch()

        self.tmpl_next_btn = QPushButton("下一步 →")
        self.tmpl_next_btn.setObjectName("AddAssetDialogAddBtn")
        self.tmpl_next_btn.setFixedSize(110, 38)
        self.tmpl_next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tmpl_next_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.tmpl_next_btn.clicked.connect(self._go_to_settings)
        btn_row.addWidget(self.tmpl_next_btn)
        layout.addLayout(btn_row)

        return page

    # ── 第3页：设置 ──

    def _build_page_settings(self):
        page = QWidget()
        page.setObjectName("AddAssetDialogContent")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(12)

        lbl = QLabel("工程设置")
        lbl.setObjectName("AddAssetDialogLabel")
        lbl.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(lbl)

        # 工程名称
        n_lbl = QLabel("工程名称")
        n_lbl.setObjectName("AddAssetDialogLabel")
        layout.addWidget(n_lbl)
        self.name_input = QLineEdit()
        self.name_input.setObjectName("AddAssetDialogInput")
        self.name_input.setPlaceholderText("输入工程名称...")
        self.name_input.setFixedHeight(36)
        layout.addWidget(self.name_input)

        # 工程路径
        p_lbl = QLabel("工程路径")
        p_lbl.setObjectName("AddAssetDialogLabel")
        layout.addWidget(p_lbl)
        path_row = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setObjectName("AddAssetDialogPathInput")
        self.path_input.setPlaceholderText("选择工程存放路径...")
        self.path_input.setFixedHeight(36)
        self.path_input.setText(str(Path.home() / "Documents" / "Unreal Projects"))
        path_row.addWidget(self.path_input)
        browse = QPushButton("浏览")
        browse.setObjectName("AddAssetDialogBrowseBtn")
        browse.setFixedSize(70, 36)
        browse.setCursor(Qt.CursorShape.PointingHandCursor)
        browse.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        browse.clicked.connect(self._browse_path)
        path_row.addWidget(browse)
        layout.addLayout(path_row)

        # 代码类型
        code_row = QHBoxLayout()
        c_lbl = QLabel("代码类型")
        c_lbl.setObjectName("AddAssetDialogLabel")
        code_row.addWidget(c_lbl)
        self.code_combo = QComboBox()
        self.code_combo.setObjectName("AddAssetDialogCombo")
        self.code_combo.setFixedHeight(32)
        self.code_combo.setMinimumWidth(120)
        self.code_combo.addItems(["蓝图", "C++"])
        code_row.addWidget(self.code_combo)
        code_row.addStretch()
        layout.addLayout(code_row)

        # 初学者内容包（CustomCheckBox 对勾样式）
        self.starter_cb = CustomCheckBox("包含初学者内容包")
        self.starter_cb.setObjectName("AddAssetDialogCheckbox")
        layout.addWidget(self.starter_cb)

        # 错误提示
        self.error_label = QLabel("")
        self.error_label.setObjectName("AddAssetDialogErrorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)

        layout.addStretch()

        # 返回 / 创建
        btn_row = QHBoxLayout()
        back = QPushButton("← 返回")
        back.setObjectName("AddAssetDialogCancelBtn")
        back.setFixedSize(100, 38)
        back.setCursor(Qt.CursorShape.PointingHandCursor)
        back.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        back.clicked.connect(self._back_from_settings)
        btn_row.addWidget(back)
        btn_row.addStretch()

        create = QPushButton("创建并打开")
        create.setObjectName("AddAssetDialogAddBtn")
        create.setFixedSize(120, 38)
        create.setCursor(Qt.CursorShape.PointingHandCursor)
        create.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        create.clicked.connect(self._on_create)
        btn_row.addWidget(create)
        layout.addLayout(btn_row)

        return page

    # ── 页面切换 ──

    def _show_page(self, index):
        self.stack.setCurrentIndex(index)
        titles = [
            "创建工程 — 选择项目类型",
            "创建工程 — 选择模板",
            "创建工程 — 工程设置",
        ]
        self.title_label.setText(titles[index])

    def _on_category_picked(self, category: str):
        self.selected_category = category
        for card in self._cat_cards:
            card.set_selected(card.data == category)

        if category == "空白工程":
            # 空白工程跳过模板选择，直接到设置页
            self.selected_template = None
            self._show_page(2)
        else:
            self._populate_templates(category)
            self._show_page(1)

    def _populate_templates(self, category):
        # 清除旧卡片
        for c in self._cards:
            c.setParent(None)
            c.deleteLater()
        self._cards.clear()
        self.selected_template = None

        self.tmpl_title.setText(f"选择模板 — {category}")

        templates = [t for t in self.engine.templates if t.category == category]
        cols = 3
        for i, tmpl in enumerate(templates):
            card = _TemplateCard(tmpl)
            card.clicked.connect(self._on_template_picked)
            card.set_selected(False)
            row, col = divmod(i, cols)
            self.tmpl_grid.addWidget(card, row, col)
            self._cards.append(card)

        # 让列均匀分布
        for c in range(cols):
            self.tmpl_grid.setColumnStretch(c, 1)

        # 自动选中第一个
        if templates:
            self._on_template_picked(templates[0])

    def _on_template_picked(self, template):
        self.selected_template = template
        for card in self._cards:
            if isinstance(card, _TemplateCard):
                card.set_selected(card.data == template)

    def _go_to_settings(self):
        if not self.selected_template:
            return
        self._show_page(2)

    def _back_from_settings(self):
        if self.selected_category == "空白工程":
            self._show_page(0)
        else:
            self._show_page(1)

    # ── 创建 ──

    def _browse_path(self):
        path = QFileDialog.getExistingDirectory(self, "选择工程存放路径", self.path_input.text())
        if path:
            self.path_input.setText(path)

    def _on_create(self):
        name = self.name_input.text().strip()
        path_str = self.path_input.text().strip()

        if not name:
            self._show_error("请输入工程名称")
            return
        if not path_str:
            self._show_error("请选择工程路径")
            return

        invalid = set(' <>:"/\\|?*')
        if any(c in invalid for c in name):
            self._show_error("工程名称包含非法字符")
            return

        project_path = Path(path_str)
        if (project_path / name).exists():
            self._show_error(f"目录 {project_path / name} 已存在")
            return

        template_path = self.selected_template.path if self.selected_template else None
        is_cpp = self.code_combo.currentText() == "C++"
        include_starter = self.starter_cb.isChecked()
        starter_path = self.engine.starter_content_path if include_starter else None

        uproject = ProjectCreator.create_project(
            project_name=name,
            project_path=project_path,
            engine_version=self.engine.version,
            template_path=template_path,
            is_cpp=is_cpp,
            include_starter_content=include_starter,
            starter_content_path=starter_path,
        )

        if not uproject:
            self._show_error("工程创建失败，请检查路径权限")
            return

        ProjectCreator.open_project(self.engine.editor_path, uproject)
        self.project_created.emit(str(uproject))
        self.accept()

    def _show_error(self, msg):
        self.error_label.setText(f"⚠ {msg}")
        self.error_label.show()

    # ── 拖动 + 居中 ──

    def _title_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def _title_move(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)

    def showEvent(self, event):
        super().showEvent(event)
        # 更新初学者内容包可用性
        self.starter_cb.setEnabled(self.engine.has_starter_content)
        if not self.engine.has_starter_content:
            self.starter_cb.setChecked(False)
            self.starter_cb.setToolTip("当前引擎版本未找到初学者内容包")
        self._center()

    def _center(self):
        if self.parent():
            top = self.parent()
            while top.parent():
                top = top.parent()
            geo = top.geometry()
            pos = top.pos()
            self.move(
                pos.x() + (geo.width() - self.width()) // 2,
                pos.y() + (geo.height() - self.height()) // 2,
            )
        else:
            screen = QApplication.primaryScreen().availableGeometry()
            self.move(
                screen.x() + (screen.width() - self.width()) // 2,
                screen.y() + (screen.height() - self.height()) // 2,
            )
