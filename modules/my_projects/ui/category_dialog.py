# -*- coding: utf-8 -*-

"""
工程分类管理对话框 - 卡片式布局
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QLineEdit, QWidget, QScrollArea
)
from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from core.logger import get_logger

logger = get_logger(__name__)


class ProjectCategoryDialog(QDialog):
    """工程分类管理对话框"""
    
    categories_updated = pyqtSignal()
    
    def __init__(self, registry, parent=None):
        super().__init__(parent)
        self.registry = registry
        self.drag_position = QPoint()
        self._init_ui()
        self._apply_theme_styles()
        self._load_categories()
    
    def _init_ui(self):
        """初始化UI"""
        self.setModal(True)
        self.setFixedSize(420, 480)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setObjectName("CategoryManagementDialog")
        
        container = QWidget()
        container.setObjectName("CategoryDialogContainer")
        
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        main_layout.addWidget(self._create_title_bar())

        # 内容区域
        content_widget = QWidget()
        content_widget.setObjectName("CategoryDialogContent")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(24, 20, 24, 24)
        content_layout.setSpacing(16)
        
        # 添加分类区域
        add_layout = QHBoxLayout()
        add_layout.setSpacing(8)
        
        self.name_input = QLineEdit()
        self.name_input.setObjectName("CategoryInput")
        self.name_input.setPlaceholderText("输入新分类名称...")
        self.name_input.setFixedHeight(36)
        self.name_input.returnPressed.connect(self._add_category)
        add_layout.addWidget(self.name_input)
        
        add_btn = QPushButton("+ 添加")
        add_btn.setObjectName("AddButton")
        add_btn.setFixedSize(80, 36)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        add_btn.clicked.connect(self._add_category)
        add_layout.addWidget(add_btn)
        
        content_layout.addLayout(add_layout)
        
        # 错误提示
        self.error_label = QLabel("")
        self.error_label.setObjectName("ErrorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.setFixedHeight(20)
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        content_layout.addWidget(self.error_label)
        
        # 分类列表标签
        list_label = QLabel("现有分类")
        list_label.setObjectName("SectionLabel")
        content_layout.addWidget(list_label)

        # 滚动区域
        scroll_area = QScrollArea()
        scroll_area.setObjectName("CategoryScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # 卡片容器
        self.cards_container = QWidget()
        self.cards_container.setObjectName("CategoryCardsContainer")
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(8)
        self.cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        scroll_area.setWidget(self.cards_container)
        content_layout.addWidget(scroll_area)
        
        # 提示信息
        info_label = QLabel("💡 删除分类时，该分类下的工程会移至\"默认\"分类")
        info_label.setObjectName("InfoLabel")
        info_label.setWordWrap(True)
        content_layout.addWidget(info_label)
        
        main_layout.addWidget(content_widget)
        container.setLayout(main_layout)
        
        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(container)

    def _create_title_bar(self):
        """创建标题栏"""
        title_bar = QWidget()
        title_bar.setObjectName("CategoryDialogTitleBar")
        title_bar.setFixedHeight(48)
        title_bar.setCursor(Qt.CursorShape.SizeAllCursor)
        
        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(10)
        
        title = QLabel("工程分类管理")
        title.setObjectName("CategoryDialogTitle")
        layout.addWidget(title)
        layout.addStretch()
        
        close_btn = QPushButton("✕")
        close_btn.setObjectName("CategoryDialogCloseButton")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        
        title_bar.mousePressEvent = self._title_bar_mouse_press
        title_bar.mouseMoveEvent = self._title_bar_mouse_move
        return title_bar

    def _load_categories(self):
        """加载分类列表"""
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        data = self.registry.load_registry()
        categories = data.get("categories", ["默认"])
        if "默认" not in categories:
            categories.insert(0, "默认")
        
        for category in categories:
            card = self._create_category_card(category)
            self.cards_layout.addWidget(card)
    
    def _create_category_card(self, category_name):
        """创建分类卡片"""
        card = QWidget()
        card.setObjectName("CategoryCard")
        card.setFixedHeight(44)
        
        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(8)
        
        name_label = QLabel(category_name)
        name_label.setObjectName("CategoryCardName")
        layout.addWidget(name_label)
        layout.addStretch()
        
        if category_name != "默认":
            delete_btn = QPushButton("删除")
            delete_btn.setObjectName("CategoryCardDeleteButton")
            delete_btn.setFixedSize(56, 28)
            delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            delete_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            delete_btn.clicked.connect(lambda: self._delete_category_by_name(category_name))
            layout.addWidget(delete_btn)
        else:
            default_label = QLabel("默认")
            default_label.setObjectName("CategoryCardDefaultLabel")
            layout.addWidget(default_label)
        
        return card

    def _delete_category_by_name(self, category_name):
        """删除分类"""
        data = self.registry.load_registry()
        projects = data.get("projects", [])
        
        # 统计该分类下的工程数量
        count = sum(1 for p in projects if p.get("category") == category_name)
        
        if count > 0:
            from modules.asset_manager.ui.confirm_dialog import ConfirmDialog
            dialog = ConfirmDialog(
                "确认删除",
                f"分类 \"{category_name}\" 下有 {count} 个工程",
                f"删除后，这些工程将移至\"默认\"分类",
                self
            )
            if hasattr(dialog, 'center_on_parent'):
                dialog.center_on_parent()
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
        
        # 移动工程到默认分类（同时更新注册表和工程配置文件）
        from modules.my_projects.logic.project_registry import TOOLKIT_CONFIG_DIR, PROJECT_CONFIG_FILE
        import json
        from pathlib import Path
        
        for proj in projects:
            if proj.get("category") == category_name:
                proj["category"] = "默认"
                
                # 同步更新工程目录下的配置文件
                config_file = Path(proj["path"]) / TOOLKIT_CONFIG_DIR / PROJECT_CONFIG_FILE
                if config_file.exists():
                    try:
                        with open(config_file, "r", encoding="utf-8") as f:
                            cfg = json.load(f)
                        cfg["category"] = "默认"
                        with open(config_file, "w", encoding="utf-8") as f:
                            json.dump(cfg, f, ensure_ascii=False, indent=2)
                    except Exception as e:
                        logger.warning(f"更新工程配置失败 {proj['path']}: {e}")
        
        # 删除分类
        categories = data.get("categories", [])
        categories = [c for c in categories if c != category_name]
        data["categories"] = categories
        self.registry.save_registry(data)
        
        self._hide_error()
        self._load_categories()
        self.categories_updated.emit()
        logger.info(f"删除工程分类: {category_name}")

    def _add_category(self):
        """添加分类"""
        category_name = self.name_input.text().strip()
        
        if not category_name:
            self._show_error("分类名称不能为空")
            return
        
        data = self.registry.load_registry()
        categories = data.get("categories", ["默认"])
        
        if category_name in categories:
            self._show_error(f"分类 \"{category_name}\" 已存在")
            return
        
        categories.append(category_name)
        data["categories"] = categories
        self.registry.save_registry(data)
        
        self.name_input.clear()
        self._hide_error()
        self._load_categories()
        self.categories_updated.emit()
        logger.info(f"添加工程分类: {category_name}")

    def _apply_theme_styles(self):
        """应用主题样式"""
        try:
            from core.utils.style_system import get_current_theme
            is_light = get_current_theme() == "modern_light"
        except Exception:
            is_light = False
        
        if is_light:
            self.setStyleSheet(self._get_light_styles())
        else:
            self.setStyleSheet(self._get_dark_styles())
    
    def _show_error(self, message):
        self.error_label.setText(f"⚠ {message}")
    
    def _hide_error(self):
        self.error_label.setText("")
    
    def _title_bar_mouse_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
    
    def _title_bar_mouse_move(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def showEvent(self, event):
        super().showEvent(event)
        self.center_on_parent()
    
    def center_on_parent(self):
        """居中显示"""
        if self.parent():
            from PyQt6.QtWidgets import QApplication
            top = self.parent()
            while top.parent():
                top = top.parent()
            geo = top.geometry()
            pos = top.pos()
            x = pos.x() + (geo.width() - self.width()) // 2
            y = pos.y() + (geo.height() - self.height()) // 2
            self.move(x, y)
        else:
            from PyQt6.QtWidgets import QApplication
            screen = QApplication.primaryScreen().availableGeometry()
            self.move(
                screen.x() + (screen.width() - self.width()) // 2,
                screen.y() + (screen.height() - self.height()) // 2
            )

    def _get_dark_styles(self):
        """深色主题样式"""
        return """
            /* 对话框容器 */
            #CategoryDialogContainer {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2a2a2a,
                    stop:0.03 #242424,
                    stop:1 #1e1e1e);
                border: 1px solid #3a3a3a;
                border-radius: 12px;
            }
            
            /* 标题栏 */
            #CategoryDialogTitleBar {
                background: transparent;
                border-bottom: 1px solid #2a2a2a;
            }
            
            #CategoryDialogTitle {
                color: #e0e0e0;
                font-size: 16px;
                font-weight: 600;
                background: transparent;
            }
            
            #CategoryDialogCloseButton {
                background: transparent;
                color: #888888;
                border: none;
                border-radius: 6px;
                font-size: 18px;
            }
            
            #CategoryDialogCloseButton:hover {
                background: #3a3a3a;
                color: #e0e0e0;
            }
            
            #CategoryDialogCloseButton:pressed {
                background: #4a4a4a;
            }
            
            /* 内容区域 */
            #CategoryDialogContent {
                background: transparent;
            }
            
            /* 区域标签 */
            #SectionLabel {
                color: #999999;
                font-size: 13px;
                font-weight: 500;
                background: transparent;
            }
            
            /* 输入框 */
            #CategoryInput {
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 0 12px;
                color: #e0e0e0;
                font-size: 13px;
            }
            
            #CategoryInput:focus {
                background-color: #242424;
                border: 1px solid #2196F3;
            }
            
            /* 添加按钮 */
            #AddButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
            }
            
            #AddButton:hover {
                background-color: #1976D2;
            }
            
            #AddButton:pressed {
                background-color: #1565C0;
            }
            
            /* 错误标签 */
            #ErrorLabel {
                color: #ef4444;
                font-size: 12px;
                background: transparent;
            }
            
            /* 滚动区域 */
            #CategoryScrollArea {
                background-color: transparent;
                border: none;
            }
            
            #CategoryCardsContainer {
                background-color: transparent;
            }
            
            /* 分类卡片 */
            #CategoryCard {
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
            }
            
            #CategoryCard:hover {
                background-color: #323232;
                border: 1px solid #4a4a4a;
            }
            
            #CategoryCardName {
                color: #e0e0e0;
                font-size: 13px;
                font-weight: 500;
                background: transparent;
            }
            
            #CategoryCardDefaultLabel {
                color: #666666;
                font-size: 11px;
                background: transparent;
                padding: 4px 8px;
            }
            
            #CategoryCardDeleteButton {
                background: #ef4444;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 500;
            }
            
            #CategoryCardDeleteButton:hover {
                background: #dc2626;
            }
            
            #CategoryCardDeleteButton:pressed {
                background: #b91c1c;
            }
            
            /* 滚动条 */
            #CategoryScrollArea QScrollBar:vertical {
                background-color: transparent;
                width: 6px;
                margin: 0px;
                border: none;
            }
            
            #CategoryScrollArea QScrollBar::handle:vertical {
                background-color: #3a3a3a;
                border-radius: 3px;
                min-height: 20px;
            }
            
            #CategoryScrollArea QScrollBar::handle:vertical:hover {
                background-color: #4a4a4a;
            }
            
            #CategoryScrollArea QScrollBar::add-line:vertical,
            #CategoryScrollArea QScrollBar::sub-line:vertical {
                height: 0px;
            }
            
            /* 提示信息 */
            #InfoLabel {
                color: #666666;
                font-size: 12px;
                background: transparent;
            }
        """

    def _get_light_styles(self):
        """浅色主题样式"""
        return """
            /* 对话框容器 */
            #CategoryDialogContainer {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f5f5f5,
                    stop:0.03 #fafafa,
                    stop:1 #ffffff);
                border: 1px solid #e0e0e0;
                border-radius: 12px;
            }
            
            /* 标题栏 */
            #CategoryDialogTitleBar {
                background: transparent;
                border-bottom: 1px solid #e0e0e0;
            }
            
            #CategoryDialogTitle {
                color: #212121;
                font-size: 16px;
                font-weight: 600;
                background: transparent;
            }
            
            #CategoryDialogCloseButton {
                background: transparent;
                color: #757575;
                border: none;
                border-radius: 6px;
                font-size: 18px;
            }
            
            #CategoryDialogCloseButton:hover {
                background: #f0f0f0;
                color: #212121;
            }
            
            #CategoryDialogCloseButton:pressed {
                background: #e0e0e0;
            }
            
            /* 内容区域 */
            #CategoryDialogContent {
                background: transparent;
            }
            
            /* 区域标签 */
            #SectionLabel {
                color: #757575;
                font-size: 13px;
                font-weight: 500;
                background: transparent;
            }
            
            /* 输入框 */
            #CategoryInput {
                background-color: #f5f5f5;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 0 12px;
                color: #212121;
                font-size: 13px;
            }
            
            #CategoryInput:focus {
                background-color: #ffffff;
                border: 1px solid #2196F3;
            }
            
            /* 添加按钮 */
            #AddButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
            }
            
            #AddButton:hover {
                background-color: #1976D2;
            }
            
            #AddButton:pressed {
                background-color: #1565C0;
            }
            
            /* 错误标签 */
            #ErrorLabel {
                color: #ef4444;
                font-size: 12px;
                background: transparent;
            }
            
            /* 滚动区域 */
            #CategoryScrollArea {
                background-color: transparent;
                border: none;
            }
            
            #CategoryCardsContainer {
                background-color: transparent;
            }
            
            /* 分类卡片 */
            #CategoryCard {
                background-color: #f5f5f5;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
            }
            
            #CategoryCard:hover {
                background-color: #eeeeee;
                border: 1px solid #d0d0d0;
            }
            
            #CategoryCardName {
                color: #212121;
                font-size: 13px;
                font-weight: 500;
                background: transparent;
            }
            
            #CategoryCardDefaultLabel {
                color: #9e9e9e;
                font-size: 11px;
                background: transparent;
                padding: 4px 8px;
            }
            
            #CategoryCardDeleteButton {
                background: #ef4444;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 500;
            }
            
            #CategoryCardDeleteButton:hover {
                background: #dc2626;
            }
            
            #CategoryCardDeleteButton:pressed {
                background: #b91c1c;
            }
            
            /* 滚动条 */
            #CategoryScrollArea QScrollBar:vertical {
                background-color: transparent;
                width: 6px;
                margin: 0px;
                border: none;
            }
            
            #CategoryScrollArea QScrollBar::handle:vertical {
                background-color: #d0d0d0;
                border-radius: 3px;
                min-height: 20px;
            }
            
            #CategoryScrollArea QScrollBar::handle:vertical:hover {
                background-color: #b0b0b0;
            }
            
            #CategoryScrollArea QScrollBar::add-line:vertical,
            #CategoryScrollArea QScrollBar::sub-line:vertical {
                height: 0px;
            }
            
            /* 提示信息 */
            #InfoLabel {
                color: #9e9e9e;
                font-size: 12px;
                background: transparent;
            }
        """
