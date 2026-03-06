# -*- coding: utf-8 -*-

"""
添加资产对话框
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QComboBox, QLineEdit,
    QFileDialog, QWidget, QMenu
)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QMouseEvent, QCursor
from pathlib import Path
from typing import Optional, List, Tuple

from core.logger import get_logger
from core.utils.custom_widgets import NoContextMenuLineEdit
from ..logic.asset_model import AssetType
from .custom_checkbox import CustomCheckBox

logger = get_logger(__name__)


class AddAssetDialog(QDialog):
    """添加资产对话框"""
    
    def __init__(self, existing_asset_names: List[str], categories: List[str], 
                 prefill_path: Optional[str] = None, prefill_type: Optional[AssetType] = None,
                 prefill_category: Optional[str] = None, prefill_name: Optional[str] = None, parent=None):
        """初始化对话框
        
        Args:
            existing_asset_names: 已存在的资产名称列表
            categories: 已有的分类列表
            prefill_path: 预填充的资产路径（可选）
            prefill_type: 预填充的资产类型（可选）
            prefill_category: 预填充的分类（可选）
            prefill_name: 预填充的资产名称（可选）
            parent: 父组件
        """
        super().__init__(parent)
        
        self.existing_asset_names = existing_asset_names
        self.categories = categories
        self.asset_path = None
        self.asset_type = None
        self.prefill_path = prefill_path
        self.prefill_type = prefill_type
        self.prefill_category = prefill_category
        self.prefill_name = prefill_name
        self.drag_position = QPoint()
        
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        self.setModal(True)
        self.setFixedSize(550, 480)
        
        # 无边框
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 设置ObjectName
        self.setObjectName("AddAssetDialog")
        
        # 主容器
        container = QWidget()
        container.setObjectName("AddAssetDialogContainer")
        
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 标题栏
        title_bar = QWidget()
        title_bar.setObjectName("AddAssetDialogTitleBar")
        title_bar.setFixedHeight(50)
        title_bar_layout = QHBoxLayout()
        title_bar_layout.setContentsMargins(20, 0, 20, 0)
        
        title_icon = QLabel("📦")
        title_icon.setObjectName("AddAssetDialogTitleIcon")
        title_bar_layout.addWidget(title_icon)
        
        title_label = QLabel("添加资产")
        title_label.setObjectName("AddAssetDialogTitleLabel")
        title_bar_layout.addWidget(title_label)
        title_bar_layout.addStretch()
        
        title_bar.setLayout(title_bar_layout)
        main_layout.addWidget(title_bar)
        
        # 内容区域
        content_widget = QWidget()
        content_widget.setObjectName("AddAssetDialogContent")
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(30, 20, 30, 25)
        content_layout.setSpacing(15)
        
        # 资产路径选择
        path_label = QLabel("资产路径")
        path_label.setObjectName("AddAssetDialogLabel")
        content_layout.addWidget(path_label)
        
        path_row = QHBoxLayout()
        path_row.setSpacing(10)
        
        self.path_display = NoContextMenuLineEdit()
        self.path_display.setObjectName("AddAssetDialogPathInput")
        self.path_display.setPlaceholderText("请选择资产路径...")
        self.path_display.setReadOnly(True)
        path_row.addWidget(self.path_display, 1)
        
        browse_btn = QPushButton("浏览")
        browse_btn.setObjectName("AddAssetDialogBrowseBtn")
        browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        browse_btn.clicked.connect(self._select_asset_path)
        path_row.addWidget(browse_btn)
        
        content_layout.addLayout(path_row)
        
        # 资产名称
        name_label = QLabel("资产名称")
        name_label.setObjectName("AddAssetDialogLabel")
        content_layout.addWidget(name_label)
        
        self.name_input = NoContextMenuLineEdit()
        self.name_input.setObjectName("AddAssetDialogInput")
        self.name_input.setPlaceholderText("输入资产名称...")
        self.name_input.textChanged.connect(self._on_name_changed)
        content_layout.addWidget(self.name_input)
        
        # 资产分类
        category_label = QLabel("资产分类")
        category_label.setObjectName("AddAssetDialogLabel")
        content_layout.addWidget(category_label)
        
        category_row = QHBoxLayout()
        self.category_combo = QComboBox()
        self.category_combo.setObjectName("AddAssetDialogCombo")
        self.category_combo.setEditable(False)
        self.category_combo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.category_combo.addItems(self.categories if self.categories else ["默认分类"])
        self.category_combo.setCurrentText("默认分类")
        self.category_combo.setMinimumWidth(180)
        self.category_combo.setMaximumWidth(280)
        category_row.addWidget(self.category_combo)
        category_row.addStretch()
        content_layout.addLayout(category_row)
        
        # 选项
        self.create_doc_checkbox = CustomCheckBox("自动创建说明文档")
        self.create_doc_checkbox.setObjectName("AddAssetDialogCheckbox")
        self.create_doc_checkbox.setChecked(True)
        content_layout.addWidget(self.create_doc_checkbox)
        
        # 错误提示
        self.error_label = QLabel("")
        self.error_label.setObjectName("AddAssetDialogErrorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        content_layout.addWidget(self.error_label)
        
        content_layout.addStretch()
        
        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addStretch()
        
        self.add_btn = QPushButton("添加")
        self.add_btn.setObjectName("AddAssetDialogAddBtn")
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.add_btn.setFixedSize(100, 40)
        self.add_btn.clicked.connect(self._on_add_clicked)
        button_layout.addWidget(self.add_btn)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("AddAssetDialogCancelBtn")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        cancel_btn.setFixedSize(100, 40)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        content_layout.addLayout(button_layout)
        
        content_widget.setLayout(content_layout)
        main_layout.addWidget(content_widget, 1)
        
        container.setLayout(main_layout)
        
        # 对话框布局
        dialog_layout = QVBoxLayout()
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(container)
        self.setLayout(dialog_layout)
        
        # 如果有预填数据，则填充
        if self.prefill_path:
            self.path_display.setText(self.prefill_path)
            self.asset_path = Path(self.prefill_path)
            self.asset_type = self.prefill_type
            
            # 如果有预填名称，使用预填名称
            if self.prefill_name:
                self.name_input.setText(self.prefill_name)
            # 如果有预填路径但没有预填名称，自动填充名称
            elif self.prefill_path:
                path = Path(self.prefill_path)
                if self.prefill_type == AssetType.FILE:
                    auto_name = path.stem
                else:
                    auto_name = path.name
                self.name_input.setText(auto_name)
        
        # 如果有预填分类，设置默认分类
        if self.prefill_category:
            index = self.category_combo.findText(self.prefill_category)
            if index >= 0:
                self.category_combo.setCurrentIndex(index)
    
    def mousePressEvent(self, event: QMouseEvent):
        """鼠标按下事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """鼠标移动事件"""
        if event.buttons() == Qt.MouseButton.LeftButton and not self.drag_position.isNull():
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
    
    def _select_asset_path(self):
        """选择资产路径"""
        menu = QMenu(self)
        menu.setObjectName("AddAssetDialogMenu")
        
        package_action = menu.addAction("📦 选择资源包（文件夹）")
        file_action = menu.addAction("📄 选择资源文件")
        
        action = menu.exec(QCursor.pos())
        
        if action == package_action:
            self._select_package()
        elif action == file_action:
            self._select_file()
    
    def _select_package(self):
        """选择资源包"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "选择资源包文件夹",
            "",
            QFileDialog.Option.ShowDirsOnly
        )
        
        if dir_path:
            self.asset_path = Path(dir_path)
            self.asset_type = AssetType.PACKAGE
            self.path_display.setText(str(self.asset_path))
            
            # 自动填充名称
            if not self.name_input.text():
                self.name_input.setText(self.asset_path.name)
    
    def _select_file(self):
        """选择资源文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择资产文件",
            "",
            "所有文件 (*);;模型文件 (*.fbx *.obj *.gltf);;贴图文件 (*.png *.jpg *.tga *.bmp)"
        )
        
        if file_path:
            self.asset_path = Path(file_path)
            self.asset_type = AssetType.FILE
            self.path_display.setText(str(self.asset_path))
            
            # 自动填充名称
            if not self.name_input.text():
                self.name_input.setText(self.asset_path.stem)
    
    def _on_name_changed(self, text):
        """名称改变时隐藏错误提示"""
        if text:
            self.error_label.hide()
    
    def validate_input(self) -> Tuple[bool, str]:
        """验证输入
        
        Returns:
            (是否有效, 错误信息)
        """
        if not self.asset_path:
            return False, "请先选择资产路径"
        
        name = self.name_input.text().strip()
        if not name:
            return False, "资产名称不能为空"
        
        if name in self.existing_asset_names:
            return False, f"资产名称 \"{name}\" 已存在，请使用其他名称"
        
        return True, ""
    
    def _on_add_clicked(self):
        """点击添加按钮"""
        logger.info("点击添加按钮")
        
        valid, error_msg = self.validate_input()
        if not valid:
            self.error_label.setText(f"❌ {error_msg}")
            self.error_label.show()
            return
        
        self.accept()
    
    def get_asset_info(self) -> dict:
        """获取资产信息"""
        return {
            "path": self.asset_path,
            "type": self.asset_type,
            "name": self.name_input.text().strip(),
            "category": self.category_combo.currentText().strip(),
            "create_doc": self.create_doc_checkbox.isChecked()
        }
    
    def showEvent(self, event):
        """显示事件 - 在这里居中显示"""
        super().showEvent(event)
        # 在对话框显示时居中
        self._center_dialog()
    
    def _center_dialog(self):
        """居中对话框"""
        if self.parent():
            # 获取父窗口
            parent = self.parent()
            
            # 需要向上查找到顶层窗口
            top_window = parent
            while top_window.parent():
                top_window = top_window.parent()
            
            # 获取顶层窗口的全局位置和大小
            parent_geo = top_window.geometry()
            parent_pos = top_window.pos()
            
            # 获取对话框大小
            dialog_width = self.width()
            dialog_height = self.height()
            
            # 计算居中位置（全局坐标）
            x = parent_pos.x() + (parent_geo.width() - dialog_width) // 2
            y = parent_pos.y() + (parent_geo.height() - dialog_height) // 2
            
            self.move(x, y)
        else:
            # 如果没有父窗口，居中到屏幕
            from PyQt6.QtWidgets import QApplication
            screen = QApplication.primaryScreen().availableGeometry()
            x = screen.x() + (screen.width() - self.width()) // 2
            y = screen.y() + (screen.height() - self.height()) // 2
            self.move(x, y)
    
    def center_on_parent(self):
        """在父窗口中居中显示（兼容旧调用）"""
        # 这个方法保留以兼容现有调用，但实际居中在showEvent中完成
        pass
