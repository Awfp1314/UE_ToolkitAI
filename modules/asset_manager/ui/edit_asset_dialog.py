# -*- coding: utf-8 -*-

"""
编辑资产信息对话框
已迁移到QSS样式系统
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QLineEdit, QComboBox, QWidget
)
from PyQt6.QtCore import Qt, QPoint
from typing import List
from pathlib import Path
import subprocess
import sys
from core.logger import get_logger

logger = get_logger(__name__)


class EditAssetDialog(QDialog):
    """编辑资产信息对话框"""
    
    def __init__(self, logic, asset_name: str, asset_category: str, 
                 existing_names: List[str], categories: List[str], 
                 has_documentation: bool = False, parent=None):
        """初始化对话框
        
        Args:
            logic: AssetManagerLogic 实例
            asset_name: 当前资产名称
            asset_category: 当前资产分类
            existing_names: 已存在的资产名称列表（用于检查重名）
            categories: 可用的分类列表
            has_documentation: 是否有文档
            parent: 父组件
        """
        super().__init__(parent)
        self.logic = logic
        self.asset_name = asset_name
        self.asset_category = asset_category
        self.existing_names = [name for name in existing_names if name != asset_name]  # 排除当前名称
        self.categories = categories
        self.has_documentation = has_documentation
        self.drag_position = QPoint()
        
        # 找到当前资产对象
        self.current_asset = None
        for asset in self.logic.assets:
            if asset.name == asset_name:
                self.current_asset = asset
                break
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        self.setModal(True)
        self.setFixedSize(450, 350)
        
        # 无边框 + 透明背景
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 设置ObjectName用于QSS
        self.setObjectName("EditAssetDialog")
        
        # 主容器
        container = QWidget()
        container.setObjectName("EditAssetDialogContainer")
        
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 标题栏
        title_bar = self._create_title_bar()
        main_layout.addWidget(title_bar)
        
        # 内容区域
        content_widget = QWidget()
        content_widget.setObjectName("EditAssetDialogContent")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(30, 25, 30, 30)
        content_layout.setSpacing(20)
        
        # 资产名称区域
        name_section = self._create_name_section()
        content_layout.addLayout(name_section)
        
        # 分类选择区域
        category_section = self._create_category_section()
        content_layout.addLayout(category_section)
        
        # 错误提示标签
        self.error_label = QLabel("")
        self.error_label.setObjectName("ErrorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.setFixedHeight(25)
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        content_layout.addWidget(self.error_label)
        
        content_layout.addStretch()
        
        # 底部按钮
        button_layout = self._create_button_layout()
        content_layout.addLayout(button_layout)
        
        main_layout.addWidget(content_widget)
        container.setLayout(main_layout)
        
        # 设置对话框布局
        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(container)
    
    def _create_title_bar(self):
        """创建标题栏"""
        title_bar = QWidget()
        title_bar.setObjectName("EditAssetDialogTitleBar")
        title_bar.setFixedHeight(50)
        title_bar.setCursor(Qt.CursorShape.SizeAllCursor)
        
        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(25, 0, 25, 0)
        layout.setSpacing(10)
        
        # 标题
        title = QLabel("编辑资产信息")
        title.setObjectName("EditAssetDialogTitle")
        layout.addWidget(title)
        
        layout.addStretch()
        
        # 关闭按钮
        close_btn = QPushButton("✕")
        close_btn.setObjectName("EditAssetDialogCloseButton")
        close_btn.setFixedSize(32, 32)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        close_btn.clicked.connect(self.reject)
        layout.addWidget(close_btn)
        
        # 启用鼠标事件
        title_bar.mousePressEvent = self._title_bar_mouse_press
        title_bar.mouseMoveEvent = self._title_bar_mouse_move
        
        return title_bar
    
    def _create_name_section(self):
        """创建资产名称区域"""
        layout = QVBoxLayout()
        layout.setSpacing(12)
        
        # 标签
        label = QLabel("资产名称")
        label.setObjectName("SectionLabel")
        layout.addWidget(label)
        
        # 输入框
        self.name_input = QLineEdit()
        self.name_input.setObjectName("EditAssetInput")
        self.name_input.setText(self.asset_name)
        self.name_input.setPlaceholderText("输入资产名称...")
        self.name_input.setFixedHeight(36)
        self.name_input.textChanged.connect(self._on_name_changed)
        layout.addWidget(self.name_input)
        
        return layout
    
    def _create_category_section(self):
        """创建分类选择区域"""
        layout = QVBoxLayout()
        layout.setSpacing(12)
        
        # 标签
        label = QLabel("资产分类")
        label.setObjectName("SectionLabel")
        layout.addWidget(label)
        
        # 分类选择框
        self.category_combo = QComboBox()
        self.category_combo.setObjectName("EditAssetCategoryCombo")
        self.category_combo.setEditable(False)  # 不可编辑
        self.category_combo.addItems(self.categories)
        self.category_combo.setCurrentText(self.asset_category)
        self.category_combo.setFixedHeight(36)  # 缩短高度
        self.category_combo.setMaximumWidth(250)  # 设置最大宽度
        
        # 彻底去除下拉框的系统阴影
        combo_view = self.category_combo.view()
        combo_view.window().setWindowFlags(
            Qt.WindowType.Popup | 
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.NoDropShadowWindowHint
        )
        combo_view.window().setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        
        layout.addWidget(self.category_combo)
        
        return layout
    

    def _create_button_layout(self):
        """创建底部按钮布局"""
        layout = QHBoxLayout()
        layout.setSpacing(15)
        layout.addStretch()
        
        # 取消按钮
        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("CancelButton")
        cancel_btn.setFixedSize(100, 40)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)
        
        # 确定按钮
        ok_btn = QPushButton("确定")
        ok_btn.setObjectName("OkButton")
        ok_btn.setFixedSize(100, 40)
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        ok_btn.clicked.connect(self._on_ok_clicked)
        layout.addWidget(ok_btn)
        
        return layout
    
    def _on_name_changed(self, text: str):
        """名称输入框内容改变时的处理"""
        # 清除错误提示
        self.error_label.setText("")
    
    def _on_ok_clicked(self):
        """确定按钮点击事件"""
        new_name = self.name_input.text().strip()
        new_category = self.category_combo.currentText().strip()
        
        if not new_name:
            self._show_error("资产名称不能为空")
            return
        
        if new_name in self.existing_names:
            self._show_error(f"资产名称 \"{new_name}\" 已存在")
            return
        
        if not new_category:
            self._show_error("分类名称不能为空")
            return
        
        self.accept()
    
    def get_asset_info(self) -> dict:
        """获取编辑后的资产信息
        
        Returns:
            包含name和category的字典
        """
        return {
            "name": self.name_input.text().strip(),
            "category": self.category_combo.currentText().strip()
        }
    
    def _show_error(self, message):
        """显示错误信息"""
        self.error_label.setText(f"⚠ {message}")
    
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
