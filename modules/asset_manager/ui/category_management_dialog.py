# -*- coding: utf-8 -*-

"""
分类管理对话框
已迁移到QSS样式系统
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QListWidget, QListWidgetItem, QLineEdit, QWidget
)
from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from core.logger import get_logger

logger = get_logger(__name__)


class CategoryManagementDialog(QDialog):
    """分类管理对话框"""
    
    # 信号：分类列表已更新
    categories_updated = pyqtSignal()
    
    def __init__(self, logic, parent=None):
        """初始化对话框
        
        Args:
            logic: AssetManagerLogic 实例
            parent: 父组件
        """
        super().__init__(parent)
        self.logic = logic
        self.drag_position = QPoint()
        self._init_ui()
        self._load_categories()
    
    def _init_ui(self):
        """初始化UI"""
        self.setModal(True)
        self.setFixedSize(500, 600)
        
        # 无边框 + 透明背景
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 设置ObjectName用于QSS
        self.setObjectName("CategoryManagementDialog")
        
        # 主容器
        container = QWidget()
        container.setObjectName("CategoryDialogContainer")
        
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 标题栏
        title_bar = self._create_title_bar()
        main_layout.addWidget(title_bar)
        
        # 内容区域
        content_widget = QWidget()
        content_widget.setObjectName("CategoryDialogContent")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(30, 25, 30, 30)
        content_layout.setSpacing(20)
        
        # 添加分类区域
        add_section = self._create_add_section()
        content_layout.addLayout(add_section)
        
        # 错误提示标签
        self.error_label = QLabel("")
        self.error_label.setObjectName("ErrorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.setFixedHeight(25)
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        content_layout.addWidget(self.error_label)
        
        # 分类列表区域
        list_section = self._create_list_section()
        content_layout.addLayout(list_section)
        
        # 提示信息
        info_label = QLabel("提示：删除分类时，该分类下的资产会移至\"默认分类\"")
        info_label.setObjectName("InfoLabel")
        info_label.setWordWrap(True)
        content_layout.addWidget(info_label)
        
        main_layout.addWidget(content_widget)
        container.setLayout(main_layout)
        
        # 设置对话框布局
        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(container)
    
    def _create_title_bar(self):
        """创建标题栏"""
        title_bar = QWidget()
        title_bar.setObjectName("CategoryDialogTitleBar")
        title_bar.setFixedHeight(50)
        title_bar.setCursor(Qt.CursorShape.SizeAllCursor)
        
        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(25, 0, 25, 0)
        layout.setSpacing(10)
        
        # 标题
        title = QLabel("分类管理")
        title.setObjectName("CategoryDialogTitle")
        layout.addWidget(title)
        
        layout.addStretch()
        
        # 关闭按钮
        close_btn = QPushButton("✕")
        close_btn.setObjectName("CategoryDialogCloseButton")
        close_btn.setFixedSize(32, 32)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        
        # 启用鼠标事件
        title_bar.mousePressEvent = self._title_bar_mouse_press
        title_bar.mouseMoveEvent = self._title_bar_mouse_move
        
        return title_bar
    
    def _create_add_section(self):
        """创建添加分类区域"""
        layout = QVBoxLayout()
        layout.setSpacing(12)
        
        # 标签
        label = QLabel("添加新分类")
        label.setObjectName("SectionLabel")
        layout.addWidget(label)
        
        # 输入框和按钮
        input_layout = QHBoxLayout()
        input_layout.setSpacing(10)
        
        self.name_input = QLineEdit()
        self.name_input.setObjectName("CategoryInput")
        self.name_input.setPlaceholderText("输入分类名称...")
        self.name_input.setFixedHeight(40)
        self.name_input.returnPressed.connect(self._add_category)
        input_layout.addWidget(self.name_input)
        
        add_btn = QPushButton("添加")
        add_btn.setObjectName("AddButton")
        add_btn.setFixedSize(80, 40)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        add_btn.clicked.connect(self._add_category)
        input_layout.addWidget(add_btn)
        
        layout.addLayout(input_layout)
        
        return layout
    
    def _create_list_section(self):
        """创建分类列表区域"""
        layout = QVBoxLayout()
        layout.setSpacing(12)
        
        # 标签
        label = QLabel("现有分类")
        label.setObjectName("SectionLabel")
        layout.addWidget(label)
        
        # 列表
        self.category_list = QListWidget()
        self.category_list.setObjectName("CategoryList")
        self.category_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.category_list)
        
        # 删除按钮
        delete_btn = QPushButton("删除选中分类")
        delete_btn.setObjectName("DeleteButton")
        delete_btn.setFixedHeight(40)
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        delete_btn.clicked.connect(self._delete_category)
        layout.addWidget(delete_btn)
        
        return layout
    
    def _load_categories(self):
        """加载分类列表"""
        self.category_list.clear()
        categories = self.logic.get_all_categories()
        
        for category in categories:
            item = QListWidgetItem(category)
            # 默认分类标记为不可选
            if category == "默认分类":
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.category_list.addItem(item)
    
    def _add_category(self):
        """添加分类"""
        category_name = self.name_input.text().strip()
        
        if not category_name:
            self._show_error("分类名称不能为空")
            return
        
        # 调用逻辑层添加分类
        if self.logic.add_category(category_name):
            # 添加成功
            self.name_input.clear()
            self._hide_error()
            self._load_categories()
            
            # 发射信号通知UI更新
            self.categories_updated.emit()
            
            logger.info(f"添加分类成功: {category_name}")
        else:
            # 添加失败
            self._show_error(f"分类 \"{category_name}\" 已存在或无效")
    
    def _delete_category(self):
        """删除选中的分类"""
        current_item = self.category_list.currentItem()
        
        if not current_item:
            self._show_error("请先选择要删除的分类")
            return
        
        category_name = current_item.text()
        
        # 不能删除默认分类
        if category_name == "默认分类":
            self._show_error("不能删除默认分类")
            return
        
        # 获取该分类下的资产数量
        assets_in_category = [a for a in self.logic.assets if a.category == category_name]
        
        # 如果分类下有资产，显示确认对话框
        if assets_in_category:
            from .confirm_dialog import ConfirmDialog
            asset_count = len(assets_in_category)
            dialog = ConfirmDialog(
                "确认删除",
                f"分类 \"{category_name}\" 下有 {asset_count} 个资产",
                f"删除后，这些资产将移至\"默认分类\"",
                self
            )
            if hasattr(dialog, 'center_on_parent'):
                dialog.center_on_parent()
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
        
        # 调用逻辑层删除分类
        if self.logic.remove_category(category_name):
            # 删除成功
            self._hide_error()
            self._load_categories()
            
            # 发射信号通知UI更新
            self.categories_updated.emit()
            
            logger.info(f"删除分类成功: {category_name}")
        else:
            self._show_error(f"删除分类 \"{category_name}\" 失败")
    
    def _show_error(self, message):
        """显示错误信息"""
        self.error_label.setText(f"⚠ {message}")
    
    def _hide_error(self):
        """隐藏错误信息"""
        self.error_label.setText("")
    
    def _title_bar_mouse_press(self, event):
        """标题栏鼠标按下事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
    
    def _title_bar_mouse_move(self, event):
        """标题栏鼠标移动事件"""
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
    
    def showEvent(self, event):
        """显示事件 - 确保对话框居中"""
        super().showEvent(event)
        self.center_on_parent()
    
    def center_on_parent(self):
        """在父窗口中居中显示"""
        if self.parent():
            parent = self.parent()
            # 获取顶层窗口
            top_window = parent
            while top_window.parent():
                top_window = top_window.parent()
            
            parent_geo = top_window.geometry()
            parent_pos = top_window.pos()
            
            dialog_width = self.width()
            dialog_height = self.height()
            
            x = parent_pos.x() + (parent_geo.width() - dialog_width) // 2
            y = parent_pos.y() + (parent_geo.height() - dialog_height) // 2
            
            self.move(x, y)
        else:
            from PyQt6.QtWidgets import QApplication
            screen = QApplication.primaryScreen().availableGeometry()
            x = screen.x() + (screen.width() - self.width()) // 2
            y = screen.y() + (screen.height() - self.height()) // 2
            self.move(x, y)
