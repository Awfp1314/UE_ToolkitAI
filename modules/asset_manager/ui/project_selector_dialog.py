# -*- coding: utf-8 -*-

"""
预览工程选择对话框
用于在预览资产前选择使用哪个预览工程
"""

from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QWidget, QComboBox
)
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QMouseEvent


class ProjectSelectorDialog(QDialog):
    """预览工程选择对话框"""

    def __init__(self, project_list, theme="dark", last_selected_name=None, parent=None):
        """初始化对话框

        Args:
            project_list: 工程列表，格式: [{"name": "工程名", "path": "路径"}, ...]
            theme: 主题 ("dark" 或 "light")
            last_selected_name: 上次选择的工程名称（可选）
            parent: 父窗口
        """
        super().__init__(parent)
        self.project_list = project_list
        self.theme = theme
        self.last_selected_name = last_selected_name
        self.selected_project = None
        self.drag_position = QPoint()

        self.setModal(True)
        self.setFixedSize(400, 220)

        # 无边框 + 透明背景支持
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 设置ObjectName
        self.setObjectName("ProjectSelectorDialog")

        self._init_ui()

        # 设置焦点到下拉框
        QTimer.singleShot(0, lambda: self.combo.setFocus())

    def _init_ui(self):
        """初始化UI"""
        # 创建一个容器widget来承载所有内容
        container = QWidget()
        container.setObjectName("ProjectSelectorContainer")

        # 主布局
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 自定义标题栏
        title_bar = QWidget()
        title_bar.setObjectName("ProjectSelectorTitleBar")
        title_bar.setFixedHeight(45)
        title_bar_layout = QHBoxLayout()
        title_bar_layout.setSpacing(0)
        title_bar_layout.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel("选择预览工程")
        title_label.setObjectName("ProjectSelectorTitleLabel")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_bar_layout.addWidget(title_label, 1)

        title_bar.setLayout(title_bar_layout)
        main_layout.addWidget(title_bar)

        # 内容布局
        content_layout = QVBoxLayout()
        content_layout.setSpacing(12)
        content_layout.setContentsMargins(20, 20, 20, 20)

        # 提示标签
        label = QLabel("请选择需要用哪个工程预览该资产：")
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        content_layout.addWidget(label)

        # 下拉框
        self.combo = QComboBox()
        self.combo.setObjectName("ProjectSelectorCombo")
        # 添加工程名称到下拉框
        for project in self.project_list:
            self.combo.addItem(project.get("name", "未命名工程"))

        # 设置默认选中项：优先使用上次选择，否则选第一个
        if self.last_selected_name:
            # 尝试找到上次选择的工程
            for i, project in enumerate(self.project_list):
                if project.get("name") == self.last_selected_name:
                    self.combo.setCurrentIndex(i)
                    break
            else:
                # 上次选择的工程不在列表中，使用第一个
                self.combo.setCurrentIndex(0)
        else:
            self.combo.setCurrentIndex(0)

        self.combo.setMaxVisibleItems(6)  # 最多显示6个项目，避免列表太长
        content_layout.addWidget(self.combo)

        content_layout.addSpacing(8)

        # 按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addStretch()

        ok_btn = QPushButton("确定")
        ok_btn.setObjectName("ProjectSelectorOkBtn")
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("ProjectSelectorCancelBtn")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        button_layout.addStretch()

        content_layout.addLayout(button_layout)
        main_layout.addLayout(content_layout, 1)

        # 将主布局设置到容器
        container.setLayout(main_layout)

        # 对话框布局
        dialog_layout = QVBoxLayout()
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(container)
        self.setLayout(dialog_layout)



    def get_selected_project(self):
        """获取选中的工程信息

        Returns:
            选中的工程字典，包含name和path，如果取消则返回None
        """
        if self.result() == QDialog.DialogCode.Accepted:
            index = self.combo.currentIndex()
            if 0 <= index < len(self.project_list):
                return self.project_list[index]
        return None

    def center_on_screen(self):
        """将对话框居中显示"""
        from core.logger import get_logger
        logger = get_logger(__name__)

        # 向上查找真正的主窗口
        main_window = None
        parent = self.parent()

        while parent:
            # 查找有窗口标志的顶层窗口
            if parent.isWindow() and parent.isVisible():
                main_window = parent
                break
            parent = parent.parent()

        if main_window:
            # 使用主窗口的屏幕坐标进行居中
            main_geo = main_window.frameGeometry()

            dialog_width = self.width()
            dialog_height = self.height()

            logger.info(f"主窗口几何: x={main_geo.x()}, y={main_geo.y()}, w={main_geo.width()}, h={main_geo.height()}")
            logger.info(f"对话框尺寸: w={dialog_width}, h={dialog_height}")

            # 计算对话框应该出现的位置（相对于主窗口居中）
            dialog_x = main_geo.x() + (main_geo.width() - dialog_width) // 2
            dialog_y = main_geo.y() + (main_geo.height() - dialog_height) // 2

            # 移动对话框到计算出的位置
            self.move(dialog_x, dialog_y)
            logger.info(f"对话框已居中到: ({dialog_x}, {dialog_y})")
        else:
            # 如果没有找到主窗口，相对于屏幕居中
            logger.info("未找到主窗口，使用屏幕居中")
            screen = QApplication.primaryScreen()
            if screen:
                screen_geo = screen.availableGeometry()
                dialog_x = (screen_geo.width() - self.width()) // 2
                dialog_y = (screen_geo.height() - self.height()) // 2
                self.move(dialog_x, dialog_y)
                logger.info(f"对话框相对屏幕居中: ({dialog_x}, {dialog_y})")

    def mousePressEvent(self, event: QMouseEvent):
        """鼠标按下事件 - 记录拖动起始位置"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        """鼠标移动事件 - 实现窗口拖动"""
        if event.buttons() == Qt.MouseButton.LeftButton and not self.drag_position.isNull():
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def showEvent(self, event):
        """显示事件 - 在对话框显示时居中"""
        super().showEvent(event)
        # 在对话框真正显示后再居中（参考工程的做法）
        self.center_on_screen()

