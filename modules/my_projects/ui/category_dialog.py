# -*- coding: utf-8 -*-

"""
工程分类管理对话框 - 复用资产库分类管理的 QSS 样式
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem, QLineEdit, QWidget
)
from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtWidgets import QApplication

from core.logger import get_logger

logger = get_logger(__name__)

DEFAULT_CATEGORY = "默认"


class ProjectCategoryDialog(QDialog):
    """工程分类管理对话框"""

    categories_updated = pyqtSignal()

    def __init__(self, registry, parent=None):
        super().__init__(parent)
        self.registry = registry
        self.drag_position = QPoint()
        self._init_ui()
        self._load_categories()

    def _init_ui(self):
        self.setModal(True)
        self.setFixedSize(500, 600)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setObjectName("CategoryManagementDialog")

        container = QWidget()
        container.setObjectName("CategoryDialogContainer")

        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 标题栏
        main_layout.addWidget(self._create_title_bar())

        # 内容
        content = QWidget()
        content.setObjectName("CategoryDialogContent")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(30, 25, 30, 30)
        cl.setSpacing(20)

        # 添加分类
        cl.addLayout(self._create_add_section())

        # 错误提示
        self.error_label = QLabel("")
        self.error_label.setObjectName("ErrorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.setFixedHeight(25)
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        cl.addWidget(self.error_label)

        # 分类列表
        cl.addLayout(self._create_list_section())

        # 提示
        info = QLabel("提示：删除分类后，对应工程会移至\"默认\"分类")
        info.setObjectName("InfoLabel")
        info.setWordWrap(True)
        cl.addWidget(info)

        main_layout.addWidget(content)
        container.setLayout(main_layout)

        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(container)

    def _create_title_bar(self):
        bar = QWidget()
        bar.setObjectName("CategoryDialogTitleBar")
        bar.setFixedHeight(50)
        bar.setCursor(Qt.CursorShape.SizeAllCursor)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(25, 0, 25, 0)
        layout.setSpacing(10)

        title = QLabel("工程分类管理")
        title.setObjectName("CategoryDialogTitle")
        layout.addWidget(title)
        layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setObjectName("CategoryDialogCloseButton")
        close_btn.setFixedSize(32, 32)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        bar.mousePressEvent = self._title_mouse_press
        bar.mouseMoveEvent = self._title_mouse_move
        return bar

    def _create_add_section(self):
        layout = QVBoxLayout()
        layout.setSpacing(12)

        label = QLabel("添加新分类")
        label.setObjectName("SectionLabel")
        layout.addWidget(label)

        row = QHBoxLayout()
        row.setSpacing(10)

        self.name_input = QLineEdit()
        self.name_input.setObjectName("CategoryInput")
        self.name_input.setPlaceholderText("输入分类名称...")
        self.name_input.setFixedHeight(40)
        self.name_input.returnPressed.connect(self._add_category)
        row.addWidget(self.name_input)

        add_btn = QPushButton("添加")
        add_btn.setObjectName("AddButton")
        add_btn.setFixedSize(80, 40)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        add_btn.clicked.connect(self._add_category)
        row.addWidget(add_btn)

        layout.addLayout(row)
        return layout

    def _create_list_section(self):
        layout = QVBoxLayout()
        layout.setSpacing(12)

        label = QLabel("现有分类")
        label.setObjectName("SectionLabel")
        layout.addWidget(label)

        self.category_list = QListWidget()
        self.category_list.setObjectName("CategoryList")
        self.category_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.category_list)

        del_btn = QPushButton("删除选中分类")
        del_btn.setObjectName("DeleteButton")
        del_btn.setFixedHeight(40)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        del_btn.clicked.connect(self._delete_category)
        layout.addWidget(del_btn)

        return layout

    # ── 数据操作 ──

    def _load_categories(self):
        self.category_list.clear()
        categories = self._get_categories()
        for cat in categories:
            item = QListWidgetItem(cat)
            if cat == DEFAULT_CATEGORY:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.category_list.addItem(item)

    def _get_categories(self):
        """从注册表获取所有分类"""
        data = self.registry.load_registry()
        cats = data.get("categories", [DEFAULT_CATEGORY])
        if DEFAULT_CATEGORY not in cats:
            cats.insert(0, DEFAULT_CATEGORY)
        return cats

    def _save_categories(self, categories):
        """保存分类到注册表"""
        data = self.registry.load_registry()
        data["categories"] = categories
        self.registry.save_registry(data)

    def _add_category(self):
        name = self.name_input.text().strip()
        if not name:
            self._show_error("分类名称不能为空")
            return

        cats = self._get_categories()
        if name in cats:
            self._show_error(f"分类 \"{name}\" 已存在")
            return

        cats.append(name)
        self._save_categories(cats)
        self.name_input.clear()
        self.error_label.setText("")
        self._load_categories()
        self.categories_updated.emit()
        logger.info(f"添加工程分类: {name}")

    def _delete_category(self):
        item = self.category_list.currentItem()
        if not item:
            self._show_error("请先选择要删除的分类")
            return

        name = item.text()
        if name == DEFAULT_CATEGORY:
            self._show_error("不能删除默认分类")
            return

        # 将该分类下的工程移到默认分类
        data = self.registry.load_registry()
        for proj in data.get("projects", []):
            if proj.get("category") == name:
                proj["category"] = DEFAULT_CATEGORY

        cats = self._get_categories()
        cats = [c for c in cats if c != name]
        data["categories"] = cats
        self.registry.save_registry(data)

        self.error_label.setText("")
        self._load_categories()
        self.categories_updated.emit()
        logger.info(f"删除工程分类: {name}")

    def _show_error(self, msg):
        self.error_label.setText(f"⚠ {msg}")

    # ── 拖动 ──

    def _title_mouse_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def _title_mouse_move(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def showEvent(self, event):
        super().showEvent(event)
        self._center_on_parent()

    def _center_on_parent(self):
        if self.parent():
            top = self.parent()
            while top.parent():
                top = top.parent()
            geo = top.geometry()
            pos = top.pos()
            x = pos.x() + (geo.width() - self.width()) // 2
            y = pos.y() + (geo.height() - self.height()) // 2
            self.move(x, y)
        else:
            screen = QApplication.primaryScreen().availableGeometry()
            self.move(
                screen.x() + (screen.width() - self.width()) // 2,
                screen.y() + (screen.height() - self.height()) // 2
            )
