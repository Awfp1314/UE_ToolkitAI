# -*- coding: utf-8 -*-

"""
工程配置界面
"""

import sys
import os
import threading
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QScrollArea, QFrame, QGridLayout, QMenu,
    QFileDialog, QDialog, QApplication, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal as Signal, QTimer, QObject, QEvent, QPoint
from PyQt6.QtGui import QFont, QCursor, QAction
from typing import List, Optional

from core.logger import get_logger

logger = get_logger(__name__)


def _open_folder_async(folder_path: Path):
    """在独立线程中异步打开文件夹"""
    try:
        folder_str = str(folder_path)
        if sys.platform == "win32":
            os.startfile(folder_str)
        elif sys.platform == "darwin":
            import subprocess
            subprocess.Popen(['open', folder_str], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            import subprocess
            subprocess.Popen(['xdg-open', folder_str], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logger.info(f"成功打开文件夹: {folder_str}")
    except Exception as e:
        logger.error(f"打开文件夹时出错: {e}", exc_info=True)


class _MenuAutoClose(QObject):
    """右键菜单自动关闭 - 鼠标离开菜单区域时关闭"""

    def __init__(self, menu, card):
        super().__init__()
        self.menu = menu
        self.card = card
        self._was_inside = True
        app = QApplication.instance()
        if app:
            app.installEventFilter(self)
        self._timer = QTimer()
        self._timer.timeout.connect(self._check)
        self._timer.start(50)

    def eventFilter(self, obj, event):
        try:
            if not self.menu or not self.menu.isVisible():
                return False
        except RuntimeError:
            return False
        if event and event.type() == QEvent.Type.MouseButtonPress:
            pos = QCursor.pos()
            rect = self.menu.rect().translated(self.menu.mapToGlobal(self.menu.rect().topLeft()))
            if not rect.contains(pos):
                self._close()
        return False

    def _check(self):
        try:
            if not self.menu or not self.menu.isVisible():
                self._timer.stop()
                return
        except RuntimeError:
            self._timer.stop()
            return
        pos = QCursor.pos()
        rect = self.menu.rect().translated(self.menu.mapToGlobal(self.menu.rect().topLeft()))
        inside = rect.contains(pos)
        if self._was_inside and not inside:
            self._close()
        if inside:
            self._was_inside = True

    def _close(self):
        try:
            if self.menu and self.menu.isVisible():
                self._timer.stop()
                app = QApplication.instance()
                if app:
                    app.removeEventFilter(self)
                self.menu.hide()
                self.menu.deleteLater()
                self.menu = None
        except RuntimeError:
            self._timer.stop()
            self.menu = None


from modules.asset_manager.ui.message_dialog import MessageDialog
from modules.asset_manager.ui.confirm_dialog import ConfirmDialog


class ConfigNameEditDialog(QDialog):
    """统一风格：配置重命名输入框"""

    def __init__(self, current_name: str, parent=None):
        super().__init__(parent)
        self.drag_position = QPoint()
        self._result_name = current_name

        self.setModal(True)
        self.setFixedSize(460, 230)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setObjectName("AddAssetDialog")

        container = QWidget()
        container.setObjectName("AddAssetDialogContainer")

        root = QVBoxLayout(container)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        title_bar = QWidget()
        title_bar.setObjectName("AddAssetDialogTitleBar")
        title_bar.setFixedHeight(48)
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(20, 0, 20, 0)
        title_layout.setSpacing(10)

        icon = QLabel("✏️")
        icon.setObjectName("AddAssetDialogTitleIcon")
        title_layout.addWidget(icon)

        title = QLabel("重命名配置")
        title.setObjectName("AddAssetDialogTitleLabel")
        title_layout.addWidget(title)
        title_layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setObjectName("CategoryDialogCloseButton")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        close_btn.clicked.connect(self.reject)
        title_layout.addWidget(close_btn)

        title_bar.mousePressEvent = self._title_bar_mouse_press
        title_bar.mouseMoveEvent = self._title_bar_mouse_move
        root.addWidget(title_bar)

        content = QWidget()
        content.setObjectName("AddAssetDialogContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 18, 24, 22)
        content_layout.setSpacing(12)

        name_label = QLabel("配置名称")
        name_label.setObjectName("AddAssetDialogLabel")
        content_layout.addWidget(name_label)

        self.name_input = QLineEdit()
        self.name_input.setObjectName("AddAssetDialogInput")
        self.name_input.setMinimumHeight(38)
        self.name_input.setText(current_name)
        content_layout.addWidget(self.name_input)

        self.error_label = QLabel("")
        self.error_label.setObjectName("AddAssetDialogErrorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        content_layout.addWidget(self.error_label)

        content_layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("AddAssetDialogCancelBtn")
        cancel_btn.setFixedSize(100, 38)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        ok_btn = QPushButton("确定")
        ok_btn.setObjectName("AddAssetDialogAddBtn")
        ok_btn.setFixedSize(100, 38)
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        ok_btn.clicked.connect(self._on_accept)
        btn_row.addWidget(ok_btn)

        content_layout.addLayout(btn_row)
        root.addWidget(content, 1)

        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(container)

    def _title_bar_mouse_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def _title_bar_mouse_move(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and not self.drag_position.isNull():
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def _on_accept(self):
        text = (self.name_input.text() or "").strip()
        if not text:
            self.error_label.setText("配置名称不能为空")
            self.error_label.show()
            return
        self._result_name = text
        self.accept()

    def get_name(self) -> str:
        return self._result_name

    def showEvent(self, event):
        super().showEvent(event)
        self.center_on_parent()
        self.name_input.setFocus()
        self.name_input.selectAll()

    def center_on_parent(self):
        if self.parent():
            p = self.parent()
            while p.parent():
                p = p.parent()
            geo = p.frameGeometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + (geo.height() - self.height()) // 2
            self.move(x, y)



class ConfigTemplateCard(QWidget):
    """配置模板卡片组件"""
    
    clicked = Signal(object)  # 点击信号，传递模板对象
    rename_requested = Signal(object)  # 重命名请求信号
    delete_requested = Signal(object)  # 删除请求信号
    open_folder_requested = Signal(object)  # 打开文件夹请求信号
    
    def __init__(self, template, parent=None):
        super().__init__(parent)
        self.template = template
        self.setup_ui()
        
    def setup_ui(self):
        """设置UI"""
        self.setObjectName("ConfigTemplateCard")
        self.setFixedSize(200, 110)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)  # 让 QSS 背景和 hover 生效
        
        # 启用右键菜单
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)
        
        # 模板名称
        name_label = QLabel(self.template.name)
        name_label.setObjectName("ConfigTemplateCardName")
        name_label.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        layout.addWidget(name_label)
        
        # 模板描述
        desc_label = QLabel(self.template.description)
        desc_label.setObjectName("ConfigTemplateCardDesc")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        layout.addStretch()
        
        # 底部信息行
        info_layout = QHBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(8)
        
        # 修改时间
        time_label = QLabel(f"📅 {self.template.last_modified}")
        time_label.setObjectName("ConfigTemplateCardInfo")
        info_layout.addWidget(time_label)
        
        info_layout.addStretch()
        
        layout.addLayout(info_layout)
        self.setLayout(layout)
        
        # 设置工具提示
        self.setToolTip(f"点击应用配置: {self.template.name}\n{self.template.description}")
        
    def mousePressEvent(self, event):
        """点击事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.template)
            logger.info(f"点击配置模板: {self.template.name}")
    
    def _show_context_menu(self, pos):
        """显示右键菜单"""
        menu = QMenu(self)
        menu.setObjectName("ConfigTemplateCardMenu")
        
        apply_action = QAction("应用配置", self)
        apply_action.triggered.connect(lambda: self.clicked.emit(self.template))
        menu.addAction(apply_action)
        
        menu.addSeparator()
        
        open_folder_action = QAction("打开配置文件夹", self)
        open_folder_action.triggered.connect(lambda: self.open_folder_requested.emit(self.template))
        menu.addAction(open_folder_action)
        
        menu.addSeparator()
        
        rename_action = QAction("重命名", self)
        rename_action.triggered.connect(lambda: self.rename_requested.emit(self.template))
        menu.addAction(rename_action)
        
        delete_action = QAction("删除", self)
        delete_action.triggered.connect(lambda: self.delete_requested.emit(self.template))
        menu.addAction(delete_action)
        
        self._menu_filter = _MenuAutoClose(menu, self)
        menu.exec(self.mapToGlobal(pos))


class ConfigToolUI(QWidget):
    """工程配置界面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logic = None
        self.config_templates: List = []
        self.template_widgets: List[QWidget] = []
        self.add_config_button: Optional[QPushButton] = None
        self.setup_ui()
        logger.info("工程配置 UI 初始化完成")
        
    def setup_ui(self):
        """设置UI"""
        self.setObjectName("ConfigToolUI")
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(25, 20, 25, 20)
        main_layout.setSpacing(15)
        
        # ===== 顶部标题栏 =====
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        
        # 标题
        title_label = QLabel("⚙️ 工程配置")
        title_label.setObjectName("ConfigToolTitle")
        title_label.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        # 添加配置按钮
        self.add_config_button = QPushButton("＋ 添加配置")
        self.add_config_button.setObjectName("ConfigToolAddBtn")
        self.add_config_button.setFixedHeight(36)
        self.add_config_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.add_config_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        title_layout.addWidget(self.add_config_button)
        
        main_layout.addLayout(title_layout)
        
        # 分隔线
        separator = QFrame()
        separator.setObjectName("ConfigToolSeparator")
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFixedHeight(1)
        main_layout.addWidget(separator)
        
        # ===== 滚动区域 =====
        scroll_area = QScrollArea()
        scroll_area.setObjectName("ConfigToolScroll")
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # 内容容器
        self.content_widget = QWidget()
        self.content_widget.setObjectName("ConfigToolContent")
        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(0, 10, 10, 0)
        self.content_layout.setSpacing(15)
        self.content_widget.setLayout(self.content_layout)
        
        # 配置卡片网格
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(15)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.content_layout.addLayout(self.grid_layout)
        
        # 空状态标签
        self.empty_label = QLabel("暂无配置模板\n点击右上角按钮添加配置")
        self.empty_label.setObjectName("ConfigToolEmptyLabel")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.hide()
        self.content_layout.addWidget(self.empty_label)
        
        self.content_layout.addStretch()
        
        scroll_area.setWidget(self.content_widget)
        main_layout.addWidget(scroll_area)
        
        self.setLayout(main_layout)
    
    def set_logic(self, logic):
        """设置业务逻辑层"""
        self.logic = logic
    
    def update_config_buttons(self):
        """更新配置卡片显示"""
        # 清空现有卡片
        for widget in self.template_widgets:
            widget.deleteLater()
        self.template_widgets.clear()
        
        # 清空网格布局
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 如果没有配置模板，显示空状态
        if not self.config_templates:
            self.empty_label.show()
            logger.info("没有配置模板，显示空状态")
            return
        
        self.empty_label.hide()
        
        # 每行4个卡片
        cards_per_row = 4
        
        for i, template in enumerate(self.config_templates):
            row = i // cards_per_row
            col = i % cards_per_row
            
            card = ConfigTemplateCard(template)
            card.clicked.connect(self._on_template_clicked)
            card.rename_requested.connect(self._on_rename_requested)
            card.delete_requested.connect(self._on_delete_requested)
            card.open_folder_requested.connect(self._on_open_folder_requested)
            self.grid_layout.addWidget(card, row, col)
            self.template_widgets.append(card)
        
        logger.info(f"更新了 {len(self.config_templates)} 个配置卡片")
    
    def on_add_config_clicked(self):
        """添加配置按钮点击事件"""
        logger.info("添加配置按钮被点击")
        
        try:
            # 1. 弹出工程选择窗口（会自动扫描工程）
            selected_project = self._select_ue_project(None)
            if not selected_project:
                return
            
            # 2. 打开文件选择对话框 - 定位到工程的配置目录
            project_root = selected_project.project_path.parent
            config_base = project_root / "Saved" / "Config"
            
            logger.info(f"工程根目录: {project_root}")
            
            # UE4/UE5 配置目录可能的路径（按优先级排序）
            possible_config_dirs = [
                config_base / "WindowsEditor",    # UE5 编辑器
                config_base / "Windows",          # UE4 编辑器
                config_base / "WindowsNoEditor",  # UE5 打包后
                config_base,                      # 直接使用 Config 目录
            ]
            
            config_dir = None
            for dir_path in possible_config_dirs:
                if dir_path.exists():
                    config_dir = dir_path
                    logger.info(f"找到配置目录: {config_dir}")
                    break
            
            if not config_dir:
                config_dir = config_base  # 默认使用 Config 目录
                logger.warning(f"未找到配置目录，使用默认路径: {config_dir}")
            
            files = self._select_config_files(config_dir)
            if not files:
                return
            
            # 3. 弹出名称和描述设置弹窗
            config_name, config_desc = self._show_name_dialog()
            if not config_name:
                return
            
            # 4. 复制文件到目标目录
            if self.logic:
                success = self.logic.add_config_template(config_name, files, config_desc)
                if success:
                    self.refresh_config_list()
                    self.show_success_message("配置添加成功！")
                else:
                    self.show_error_message("添加配置失败")
            else:
                self.show_error_message("逻辑层未初始化")
        except Exception as e:
            logger.error(f"添加配置时发生错误: {e}")
            self.show_error_message(f"添加配置时发生错误: {str(e)}")
    
    def _select_ue_project(self, ue_projects):
        """选择UE工程 - 弹出工程搜索窗口"""
        from modules.asset_manager.ui.project_search_window import ProjectSearchWindow
        from PyQt6.QtCore import QEventLoop
        
        self._selected_project_path = None
        loop = QEventLoop()
        
        window = ProjectSearchWindow(parent=None, mode="select")  # 使用选择模式
        
        # 连接选择信号
        def on_project_selected(project_path: str):
            self._selected_project_path = project_path
            window.close()
            loop.quit()
        
        window.project_selected.connect(on_project_selected)
        
        # 窗口关闭时退出事件循环
        window.destroyed.connect(loop.quit)
        
        window.show()
        loop.exec()
        
        # 返回选中的工程
        if self._selected_project_path:
            # 创建一个简单的工程对象
            from types import SimpleNamespace
            project_path = Path(self._selected_project_path)
            uproject_files = list(project_path.glob("*.uproject"))
            if uproject_files:
                return SimpleNamespace(
                    project_path=uproject_files[0],
                    name=project_path.name,
                    pid=0
                )
        return None
    
    def _select_config_files(self, config_dir: Path) -> List[Path]:
        """选择配置文件，只选择.ini文件"""
        if not config_dir.exists():
            config_dir = Path.home()
        
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        file_dialog.setDirectory(str(config_dir))
        file_dialog.setNameFilter("配置文件 (*.ini)")
        file_dialog.setModal(True)
        file_dialog.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        
        result = file_dialog.exec()
        if result == QFileDialog.DialogCode.Accepted:
            selected_files = file_dialog.selectedFiles()
            ini_files = [Path(f) for f in selected_files if Path(f).suffix.lower() == '.ini']
            non_ini_files = [f for f in selected_files if Path(f).suffix.lower() != '.ini']
            if non_ini_files:
                logger.info(f"跳过 {len(non_ini_files)} 个非.ini文件")
            return ini_files
        return []
    
    def _show_name_dialog(self) -> tuple:
        """显示名称和描述设置弹窗，返回 (name, description) 或 ("", "")"""
        existing_names = [template.name for template in self.config_templates]
        
        dialog = QDialog(self)
        dialog.setWindowTitle("添加配置")
        dialog.setFixedSize(400, 200)
        dialog.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(10)
        
        # 名称输入
        name_label = QLabel("配置名称:")
        layout.addWidget(name_label)
        from PyQt6.QtWidgets import QLineEdit
        name_input = QLineEdit()
        name_input.setPlaceholderText("请输入配置名称")
        layout.addWidget(name_input)
        
        # 描述输入
        desc_label = QLabel("配置描述 (可选):")
        layout.addWidget(desc_label)
        desc_input = QLineEdit()
        desc_input.setPlaceholderText("简要描述这个配置的用途")
        layout.addWidget(desc_input)
        
        layout.addStretch()
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        ok_btn = QPushButton("确定")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)
        
        while True:
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return "", ""
            
            name = name_input.text().strip()
            if not name:
                MessageDialog("提示", "配置名称不能为空", "warning", parent=self).exec()
                continue
            if name in existing_names:
                MessageDialog("提示", f"配置名称 \"{name}\" 已存在", "warning", parent=self).exec()
                continue
            
            return name, desc_input.text().strip()
    
    def _on_template_clicked(self, template):
        """配置模板点击 - 应用配置到UE工程"""
        logger.info(f"选择配置模板: {template.name}")
        
        try:
            # 1. 弹出工程选择窗口
            selected_project = self._select_ue_project(None)
            if not selected_project:
                return
            
            # 2. 检查工程是否正在运行
            if hasattr(selected_project, 'pid') and selected_project.pid > 0:
                MessageDialog("警告", "当前工程正在运行无法导入配置文件，请关闭保存工程后重试", "warning", parent=self).exec()
                return
            
            # 3. 显示确认对话框
            from modules.asset_manager.ui.confirm_dialog import ConfirmDialog
            
            source_files = []
            if template.path and template.path.exists():
                source_files = list(template.path.glob("*.ini"))
            
            file_list = "\n".join([f.name for f in source_files]) if source_files else "无配置文件"
            
            dialog = ConfirmDialog(
                "确认应用配置",
                f"确定要将配置 \"{template.name}\" 应用到工程吗？",
                f"目标工程: {selected_project.project_path}\n\n将复制以下文件:\n{file_list}\n\n注意: 这些文件将覆盖目标工程中已存在的同名文件",
                self
            )
            
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            
            # 4. 复制配置文件
            if self.logic:
                success = self.logic.copy_config_files_from_template(template, selected_project.project_path)
                if success:
                    self.show_success_message("配置应用成功！")
                else:
                    self.show_error_message("配置应用失败！")
            else:
                self.show_error_message("逻辑层未初始化")
                
        except Exception as e:
            logger.error(f"应用配置时发生错误: {e}")
            self.show_error_message(f"应用配置时发生错误: {str(e)}")
    
    def _on_rename_requested(self, template):
        """重命名请求"""
        logger.info(f"请求重命名: {template.name}")

        existing_names = [t.name for t in self.config_templates if t != template]

        while True:
            dialog = ConfigNameEditDialog(template.name, self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return

            new_name = (dialog.get_name() or "").strip()
            if not new_name:
                MessageDialog("提示", "配置名称不能为空", "warning", parent=self).exec()
                continue

            if new_name in existing_names:
                MessageDialog("提示", f"配置名称 \"{new_name}\" 已存在", "warning", parent=self).exec()
                continue

            if new_name != template.name:
                template.name = new_name
                if self.logic:
                    self.logic.save_config()
                self.update_config_buttons()
                logger.info(f"配置已重命名为: {new_name}")
            return
    
    def _on_delete_requested(self, template):
        """删除请求"""
        logger.info(f"请求删除: {template.name}")
        
        dialog = ConfirmDialog(
            "确认删除",
            f"确定要删除配置 \"{template.name}\" 吗？",
            "此操作不可恢复。",
            self
        )
        if hasattr(dialog, 'center_on_parent'):
            dialog.center_on_parent()

        if dialog.exec() == QDialog.DialogCode.Accepted:
            if self.logic:
                self.logic.remove_template(template)
                self.refresh_config_list()
                logger.info(f"配置已删除: {template.name}")
    
    def _on_open_folder_requested(self, template):
        """打开配置文件夹"""
        if not template.path or not template.path.exists():
            MessageDialog("警告", "配置文件路径不存在", "warning", parent=self).exec()
            return
        
        folder_path = template.path
        thread = threading.Thread(target=_open_folder_async, args=(folder_path,), daemon=True)
        thread.start()
        logger.debug(f"已启动打开文件夹线程: {folder_path}")
    
    def show_error_message(self, message: str):
        """显示错误消息"""
        MessageDialog("错误", message, "error", parent=self).exec()
    
    def show_success_message(self, message: str = "操作成功"):
        """显示成功消息"""
        MessageDialog("成功", message, "success", parent=self).exec()
    
    def show_no_ue_project_message(self):
        """显示没有找到UE工程的消息"""
        MessageDialog("提示", "未检测到正在运行的UE工程，请先启动UE编辑器。", "info", parent=self).exec()
    
    def refresh_config_list(self):
        """刷新配置列表"""
        if self.logic:
            self.config_templates = self.logic.get_templates()
            self.update_config_buttons()
    
    def refresh_theme(self):
        """刷新主题样式 - 在主题切换时调用"""
        # QSS 样式由 style_system 统一管理
        logger.info("工程配置主题已刷新")
