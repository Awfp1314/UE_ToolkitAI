# -*- coding: utf-8 -*-

"""
工程配置界面 - 主界面

集成所有 UI 组件：
- ConfigTypeDialog: 配置类型选择对话框
- ConfigInfoDialog: 配置信息输入对话框
- ConfigCard: 配置卡片组件
- ApplyProgressDialog: 应用进度弹窗
"""

import sys
import os
import threading
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QScrollArea, QFrame, QGridLayout,
    QDialog, QApplication, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal as Signal, QTimer
from PyQt6.QtGui import QFont, QCursor, QAction
from typing import List, Optional

from core.logger import get_logger
from .config_type_dialog import ConfigTypeDialog
from .config_info_dialog import ConfigInfoDialog
from .apply_progress_dialog import ApplyProgressDialog
from ..logic.config_model import ConfigType, ConfigTemplate
from modules.asset_manager.ui.message_dialog import MessageDialog
from modules.asset_manager.ui.confirm_dialog import ConfirmDialog

logger = get_logger(__name__)


class ConfigTemplateCard(QWidget):
    """配置模板卡片组件 - 小卡片样式"""
    
    apply_clicked = Signal(str)  # 应用配置信号，传递配置名称
    delete_clicked = Signal(str)  # 删除配置信号，传递配置名称
    
    def __init__(self, template: ConfigTemplate, parent=None):
        super().__init__(parent)
        self.template = template
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        self.setObjectName("ConfigTemplateCard")
        self.setFixedSize(220, 120)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        
        # 启用右键菜单
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)
        
        # 配置名称
        name_label = QLabel(self.template.name)
        name_label.setObjectName("ConfigTemplateCardName")
        name_label.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        name_label.setWordWrap(True)
        layout.addWidget(name_label)
        
        # 配置描述
        if self.template.description:
            desc_label = QLabel(self.template.description)
            desc_label.setObjectName("ConfigTemplateCardDesc")
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)
        
        layout.addStretch()
        
        # 底部信息行
        info_layout = QHBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(8)
        
        # 配置类型图标
        type_icon = "📋" if self.template.type == ConfigType.PROJECT_SETTINGS else "⚙️"
        type_label = QLabel(type_icon)
        type_label.setObjectName("ConfigTemplateCardInfo")
        info_layout.addWidget(type_label)
        
        # UE版本
        version_label = QLabel(f"UE {self.template.config_version}")
        version_label.setObjectName("ConfigTemplateCardInfo")
        info_layout.addWidget(version_label)
        
        info_layout.addStretch()
        
        layout.addLayout(info_layout)
        self.setLayout(layout)
        
        # 设置工具提示
        tooltip = f"{self.template.name}\n"
        if self.template.description:
            tooltip += f"{self.template.description}\n"
        tooltip += f"类型: {self.template.type.display_name}\n"
        tooltip += f"版本: UE {self.template.config_version}"
        self.setToolTip(tooltip)
    
    def mousePressEvent(self, event):
        """鼠标点击事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.apply_clicked.emit(self.template.name)
            logger.info(f"点击配置模板: {self.template.name}")
    
    def _show_context_menu(self, pos):
        """显示右键菜单"""
        menu = QMenu(self)
        menu.setObjectName("ConfigTemplateCardMenu")
        
        # 应用配置
        apply_action = QAction("应用配置", self)
        apply_action.triggered.connect(lambda: self.apply_clicked.emit(self.template.name))
        menu.addAction(apply_action)
        
        menu.addSeparator()
        
        # 打开配置所在路径
        open_folder_action = QAction("打开配置所在路径", self)
        open_folder_action.triggered.connect(self._open_config_folder)
        menu.addAction(open_folder_action)
        
        menu.addSeparator()
        
        # 删除配置
        delete_action = QAction("删除", self)
        delete_action.triggered.connect(lambda: self.delete_clicked.emit(self.template.name))
        menu.addAction(delete_action)
        
        # 显示菜单
        menu.exec(self.mapToGlobal(pos))
    
    def _open_config_folder(self):
        """打开配置所在文件夹"""
        import subprocess
        import platform
        
        # 使用模板的 template_path 属性
        config_dir = self.template.template_path
        
        if config_dir.exists():
            try:
                if platform.system() == "Windows":
                    subprocess.run(["explorer", str(config_dir)])
                elif platform.system() == "Darwin":  # macOS
                    subprocess.run(["open", str(config_dir)])
                else:  # Linux
                    subprocess.run(["xdg-open", str(config_dir)])
                logger.info(f"打开配置文件夹: {config_dir}")
            except Exception as e:
                logger.error(f"打开文件夹失败: {e}")
        else:
            logger.warning(f"配置文件夹不存在: {config_dir}")


def _get_theme() -> str:
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


def _get_theme() -> str:
    """获取当前主题"""
    try:
        from core.style_system import StyleSystem
        style_system = StyleSystem()
        return style_system.current_theme
    except:
        return "dark"


class ConfigToolUI(QWidget):
    """工程配置界面 - 主界面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logic = None
        self.config_templates: List[ConfigTemplate] = []
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
        self.add_config_button.clicked.connect(self.on_add_config_clicked)
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
        
        # 每行5个小卡片
        cards_per_row = 5
        
        for i, template in enumerate(self.config_templates):
            row = i // cards_per_row
            col = i % cards_per_row
            
            card = ConfigTemplateCard(template)
            card.apply_clicked.connect(self._on_apply_clicked)
            card.delete_clicked.connect(self._on_delete_clicked)
            self.grid_layout.addWidget(card, row, col)
            self.template_widgets.append(card)
            card.show()
        
        logger.info(f"更新了 {len(self.config_templates)} 个配置卡片")
    
    def on_add_config_clicked(self):
        """添加配置按钮点击事件"""
        logger.info("添加配置按钮被点击")
        
        try:
            # 1. 显示配置类型选择对话框
            type_dialog = ConfigTypeDialog(self)
            
            selected_type = None
            
            def on_type_selected(config_type: ConfigType):
                nonlocal selected_type
                selected_type = config_type
            
            type_dialog.type_selected.connect(on_type_selected)
            
            result = type_dialog.exec()
            logger.info(f"配置类型对话框返回结果: {result}, Accepted={QDialog.DialogCode.Accepted}, selected_type={selected_type}")
            
            if result != QDialog.DialogCode.Accepted or not selected_type:
                logger.info("用户取消了配置类型选择，退出添加流程")
                return
            
            logger.info(f"选择的配置类型: {selected_type.display_name}")
            
            # 2. 显示项目选择窗口
            selected_project = self._select_ue_project()
            if not selected_project:
                return
            
            logger.info(f"选择的项目: {selected_project}")
            
            # 3. 显示配置信息输入对话框
            info_dialog = ConfigInfoDialog(self)
            
            config_name = None
            config_desc = None
            
            def on_info_confirmed(name: str, description: str):
                nonlocal config_name, config_desc
                config_name = name
                config_desc = description
            
            info_dialog.info_confirmed.connect(on_info_confirmed)
            
            if info_dialog.exec() != QDialog.DialogCode.Accepted or not config_name:
                return
            
            logger.info(f"配置名称: {config_name}, 描述: {config_desc}")
            
            # 4. 保存配置
            if self.logic:
                from ..logic.config_saver import ConfigSaver
                saver = ConfigSaver(self.logic.storage)
                
                success, message = saver.save_config(
                    name=config_name,
                    description=config_desc,
                    config_type=selected_type,
                    source_project=Path(selected_project)
                )
                
                if success:
                    self.refresh_config_list()
                    self.show_success_message("配置添加成功！")
                else:
                    self.show_error_message(f"添加配置失败: {message}")
            else:
                self.show_error_message("逻辑层未初始化")
                
        except Exception as e:
            logger.error(f"添加配置时发生错误: {e}", exc_info=True)
            self.show_error_message(f"添加配置时发生错误: {str(e)}")
    
    def _select_ue_project(self) -> Optional[str]:
        """选择UE工程 - 弹出工程搜索窗口
        
        Returns:
            项目路径（字符串），如果取消则返回 None
        """
        from modules.asset_manager.ui.project_search_window import ProjectSearchWindow
        from PyQt6.QtCore import QEventLoop
        
        self._selected_project_path = None
        loop = QEventLoop()
        
        window = ProjectSearchWindow(parent=None, mode="select")
        
        def on_project_selected(project_path: str):
            self._selected_project_path = project_path
            window.close()
            loop.quit()
        
        window.project_selected.connect(on_project_selected)
        window.destroyed.connect(loop.quit)
        
        window.show()
        loop.exec()
        
        return self._selected_project_path
    
    def _on_apply_clicked(self, config_name: str):
        """应用按钮被点击"""
        logger.info(f"应用配置: {config_name}")
        
        try:
            # 查找配置模板
            template = None
            for t in self.config_templates:
                if t.name == config_name:
                    template = t
                    break
            
            if not template:
                self.show_error_message(f"未找到配置: {config_name}")
                return
            
            # 1. 选择目标项目
            target_project = self._select_ue_project()
            if not target_project:
                return
            
            logger.info(f"目标项目: {target_project}")
            
            # 2. 创建 ConfigApplier 实例进行版本验证
            from ..logic.version_matcher import VersionMatcher
            from ..logic.config_applier import ConfigApplier
            
            matcher = VersionMatcher()
            applier = ConfigApplier(self.logic.storage, matcher)
            
            # 获取目标项目版本
            target_version = applier._get_project_version(Path(target_project))
            
            if not target_version:
                self.show_error_message("无法获取目标项目版本")
                return
            
            is_compatible, message = matcher.validate_version(
                template.config_version,
                target_version
            )
            
            if not is_compatible:
                self.show_error_message(f"版本不兼容: {message}")
                return
            
            # 3. 询问是否备份
            backup_dialog = ConfirmDialog(
                "备份确认",
                "是否在应用配置前备份原配置？",
                "建议备份以便在出现问题时恢复",
                self
            )
            
            backup = backup_dialog.exec() == QDialog.DialogCode.Accepted
            
            # 4. 显示进度弹窗并应用配置
            from ..ui.apply_progress_dialog import _ApplyProgressController
            
            progress_dialog = ApplyProgressDialog(
                config_name,
                Path(target_project).name,
                self
            )
            progress_dialog.show()
            
            # 获取主窗口以显示状态指示器
            main_window = None
            widget = self
            while widget:
                if hasattr(widget, 'show_status'):
                    main_window = widget
                    break
                widget = widget.parent()
            
            # 创建进度控制器
            total_stages = len(ApplyProgressDialog.STAGE_NAMES)
            controller = _ApplyProgressController(total_stages, main_window, progress_dialog)
            
            # 设置详情按钮回调
            if main_window:
                main_window.set_status_detail_callback(lambda: progress_dialog.show())
            
            # 启动控制器
            controller.start()
            
            def progress_callback(stage: int, title: str, detail: str):
                """进度回调，使用控制器管理平滑动画"""
                # 进入阶段
                controller.enter_stage(stage, title, detail)
                
                # 离开阶段（会自动等待最小时长）
                controller.leave_stage(stage)
            
            try:
                success, result_message = applier.apply_config(
                    template,
                    Path(target_project),
                    backup,
                    progress_callback
                )
                
                # 完成
                controller.finish(success, result_message)
            except Exception as e:
                controller.stop()
                if main_window:
                    main_window.hide_status()
                    main_window.set_status_detail_callback(None)
                raise
            
            # 清理
            if main_window:
                main_window.set_status_detail_callback(None)
            
            if success:
                self.refresh_config_list()
            
        except Exception as e:
            logger.error(f"应用配置时发生错误: {e}", exc_info=True)
            self.show_error_message(f"应用配置时发生错误: {str(e)}")
    
    def _on_delete_clicked(self, config_name: str):
        """删除按钮被点击"""
        logger.info(f"删除配置: {config_name}")
        
        # 显示确认对话框
        dialog = ConfirmDialog(
            "确认删除",
            f"确定要删除配置 \"{config_name}\" 吗？",
            "此操作不可恢复",
            self
        )
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if self.logic:
                # 查找并删除配置
                template = None
                for t in self.config_templates:
                    if t.name == config_name:
                        template = t
                        break
                
                if template:
                    success = self.logic.storage.delete_template(template.name)
                    if success:
                        self.refresh_config_list()
                        self.show_success_message("配置已删除")
                    else:
                        self.show_error_message("删除配置失败")
                else:
                    self.show_error_message(f"未找到配置: {config_name}")
            else:
                self.show_error_message("逻辑层未初始化")
    
    def show_error_message(self, message: str):
        """显示错误消息"""
        MessageDialog("错误", message, "error", parent=self).exec()
    
    def show_success_message(self, message: str = "操作成功"):
        """显示成功消息"""
        MessageDialog("成功", message, "success", parent=self).exec()
    
    def refresh_config_list(self):
        """刷新配置列表"""
        if self.logic:
            self.config_templates = self.logic.storage.list_templates()
            self.update_config_buttons()
    
    def refresh_theme(self):
        """刷新主题样式 - 在主题切换时调用"""
        self.update_config_buttons()
        logger.info("工程配置主题已刷新")
