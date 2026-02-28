# -*- coding: utf-8 -*-

"""
AI模型下载对话框

显示AI模型下载进度，支持：
- 检查模型完整性
- 显示下载进度
- 取消下载
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QWidget, QProgressBar, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from core.logger import get_logger

logger = get_logger(__name__)


class ModelDownloadThread(QThread):
    """模型下载线程"""
    
    # 信号
    progress = pyqtSignal(int, str)  # 进度百分比, 状态消息
    finished = pyqtSignal(bool, str)  # 是否成功, 消息
    
    def __init__(self, model_name="BAAI/bge-small-zh-v1.5"):
        super().__init__()
        self.model_name = model_name
        self.cancelled = False
        self.logger = get_logger(__name__)
        
    def run(self):
        """执行下载"""
        try:
            self.progress.emit(0, "正在初始化下载...")
            
            if self.cancelled:
                self.finished.emit(False, "下载已取消")
                return
            
            self.progress.emit(10, "正在连接服务器...")
            
            # 设置使用国内镜像站
            import os
            os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
            
            # 导入sentence_transformers
            from sentence_transformers import SentenceTransformer
            
            if self.cancelled:
                self.finished.emit(False, "下载已取消")
                return
            
            self.progress.emit(30, f"正在下载模型: {self.model_name}")
            self.logger.info(f"开始下载AI模型: {self.model_name} (使用镜像站)")
            
            # 下载模型（sentence_transformers会自动处理）
            # 这个过程会下载约100MB的数据
            model = SentenceTransformer(self.model_name)
            
            if self.cancelled:
                self.finished.emit(False, "下载已取消")
                return
            
            self.progress.emit(90, "正在验证模型...")
            
            # 验证模型是否可用
            test_embedding = model.encode("测试", show_progress_bar=False)
            if test_embedding is not None:
                self.progress.emit(100, "下载完成！")
                self.logger.info("AI模型下载并验证成功")
                self.finished.emit(True, "AI模型下载成功！")
            else:
                self.logger.error("AI模型验证失败")
                self.finished.emit(False, "模型验证失败")
            
        except Exception as e:
            self.logger.error(f"模型下载失败: {e}", exc_info=True)
            error_msg = str(e)
            if "connection" in error_msg.lower() or "network" in error_msg.lower():
                self.finished.emit(False, "网络连接失败，请检查网络后重试")
            else:
                self.finished.emit(False, f"下载失败: {error_msg}")
    
    def cancel(self):
        """取消下载"""
        self.cancelled = True
        self.logger.info("用户取消AI模型下载")


class AIModelDownloadDialog(QDialog):
    """AI模型下载对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.download_thread = None
        self.init_ui()
        
    def init_ui(self):
        """初始化界面"""
        # 设置窗口图标
        from pathlib import Path
        from PyQt6.QtGui import QIcon
        icon_path = Path(__file__).parent.parent.parent / "resources" / "tubiao.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        
        # 无边框，透明背景
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedSize(450, 220)
        
        # 应用内联样式
        self.setStyleSheet(self._get_inline_styles())
        
        # 主容器
        main_container = QWidget()
        main_container.setObjectName("DownloadDialogContainer")
        
        # 添加阴影效果
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setColor(Qt.GlobalColor.black)
        shadow.setOffset(0, 8)
        main_container.setGraphicsEffect(shadow)
        
        main_layout = QVBoxLayout(main_container)
        main_layout.setContentsMargins(32, 28, 32, 28)
        main_layout.setSpacing(20)
        
        # 标题
        title_label = QLabel("下载AI资源")
        title_label.setObjectName("DownloadDialogTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        main_layout.addWidget(title_label)
        
        # 状态文本
        self.status_label = QLabel("准备下载...")
        self.status_label.setObjectName("DownloadDialogStatus")
        self.status_label.setWordWrap(True)
        main_layout.addWidget(self.status_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("DownloadProgressBar")
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        main_layout.addWidget(self.progress_bar)
        
        main_layout.addSpacing(8)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        button_layout.addStretch()
        
        # 取消按钮
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setObjectName("DownloadDialogCancelButton")
        self.cancel_btn.setMinimumHeight(40)
        self.cancel_btn.setMinimumWidth(100)
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        button_layout.addWidget(self.cancel_btn)
        
        # 确定按钮（下载完成后显示）
        self.ok_btn = QPushButton("确定")
        self.ok_btn.setObjectName("DownloadDialogOkButton")
        self.ok_btn.setMinimumHeight(40)
        self.ok_btn.setMinimumWidth(100)
        self.ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ok_btn.clicked.connect(self.accept)
        self.ok_btn.hide()
        button_layout.addWidget(self.ok_btn)
        
        main_layout.addLayout(button_layout)
        
        # 设置主布局
        container_layout = QVBoxLayout(self)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.addWidget(main_container)
        
    def start_download(self):
        """开始下载"""
        self.download_thread = ModelDownloadThread()
        self.download_thread.progress.connect(self._on_progress)
        self.download_thread.finished.connect(self._on_finished)
        self.download_thread.start()
        
    def _on_progress(self, percent, message):
        """更新进度"""
        self.progress_bar.setValue(percent)
        self.status_label.setText(message)
        
    def _on_finished(self, success, message):
        """下载完成"""
        self.status_label.setText(message)
        self.cancel_btn.hide()
        self.ok_btn.show()
        
        if success:
            logger.info("AI模型下载成功")
        else:
            logger.error(f"AI模型下载失败: {message}")
    
    def _on_cancel_clicked(self):
        """取消下载"""
        if self.download_thread and self.download_thread.isRunning():
            self.download_thread.cancel()
            self.download_thread.wait()
        self.reject()
        
    def center_on_parent(self):
        """居中显示在父窗口"""
        if self.parent():
            parent_geometry = self.parent().frameGeometry()
            x = parent_geometry.x() + (parent_geometry.width() - self.width()) // 2
            y = parent_geometry.y() + (parent_geometry.height() - self.height()) // 2
            self.move(x, y)
    
    def showEvent(self, event):
        """显示事件"""
        super().showEvent(event)
        self.center_on_parent()
        # 自动开始下载
        self.start_download()
        
    @staticmethod
    def download_model(parent=None):
        """静态方法：显示对话框并下载模型
        
        Returns:
            bool: 是否下载成功
        """
        dialog = AIModelDownloadDialog(parent)
        result = dialog.exec()
        return result == QDialog.DialogCode.Accepted
    
    def _get_inline_styles(self):
        """获取内联样式"""
        try:
            from core.utils.style_system import get_current_theme
            is_light = get_current_theme() == "modern_light"
        except Exception:
            is_light = False
        
        if is_light:
            return """
                #DownloadDialogContainer {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f5f5f5, stop:1 #eeeeee);
                    border: 1px solid rgba(0, 0, 0, 0.12); border-radius: 14px;
                }
                #DownloadDialogTitle { color: #1a1a1a; font-size: 20px; font-weight: 600; background: transparent; }
                #DownloadDialogStatus { color: rgba(0, 0, 0, 0.55); font-size: 14px; background: transparent; }
                #DownloadProgressBar {
                    border: 1px solid rgba(0, 0, 0, 0.1); border-radius: 6px;
                    background: rgba(0, 0, 0, 0.05); text-align: center; color: #1a1a1a; font-size: 12px; height: 24px;
                }
                #DownloadProgressBar::chunk {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4a9eff, stop:1 #5aa9ff); border-radius: 5px;
                }
                #DownloadDialogCancelButton {
                    background: rgba(0, 0, 0, 0.05); border: 1px solid rgba(0, 0, 0, 0.1);
                    border-radius: 8px; color: rgba(0, 0, 0, 0.6); font-size: 13px; font-weight: 500; padding: 0px 16px;
                }
                #DownloadDialogCancelButton:hover { background: rgba(0, 0, 0, 0.08); color: rgba(0, 0, 0, 0.8); }
                #DownloadDialogCancelButton:pressed { background: rgba(0, 0, 0, 0.12); }
                #DownloadDialogOkButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4a9eff, stop:1 #5aa9ff);
                    border: none; border-radius: 8px; color: #ffffff; font-size: 13px; font-weight: 600; padding: 0px 18px;
                }
                #DownloadDialogOkButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5aa9ff, stop:1 #6bb6ff); }
                #DownloadDialogOkButton:pressed { background: #3a8eef; }
            """
        return """
            /* 主容器 */
            #DownloadDialogContainer {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2a2a2a,
                    stop:1 #242424
                );
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 14px;
            }
            
            /* 标题 */
            #DownloadDialogTitle {
                color: #ffffff;
                font-size: 20px;
                font-weight: 600;
                background: transparent;
                letter-spacing: 0.3px;
            }
            
            /* 状态文本 */
            #DownloadDialogStatus {
                color: rgba(255, 255, 255, 0.65);
                font-size: 14px;
                background: transparent;
                line-height: 1.5;
            }
            
            /* 进度条 */
            #DownloadProgressBar {
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                background: rgba(255, 255, 255, 0.05);
                text-align: center;
                color: #ffffff;
                font-size: 12px;
                height: 24px;
            }
            
            #DownloadProgressBar::chunk {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4a9eff,
                    stop:1 #5aa9ff
                );
                border-radius: 5px;
            }
            
            /* 取消按钮 */
            #DownloadDialogCancelButton {
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                color: rgba(255, 255, 255, 0.7);
                font-size: 13px;
                font-weight: 500;
                padding: 0px 16px;
            }
            
            #DownloadDialogCancelButton:hover {
                background: rgba(255, 255, 255, 0.1);
                border-color: rgba(255, 255, 255, 0.15);
                color: rgba(255, 255, 255, 0.9);
            }
            
            #DownloadDialogCancelButton:pressed {
                background: rgba(255, 255, 255, 0.15);
            }
            
            /* 确定按钮 */
            #DownloadDialogOkButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4a9eff,
                    stop:1 #5aa9ff
                );
                border: none;
                border-radius: 8px;
                color: #ffffff;
                font-size: 13px;
                font-weight: 600;
                padding: 0px 18px;
            }
            
            #DownloadDialogOkButton:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #5aa9ff,
                    stop:1 #6bb6ff
                );
            }
            
            #DownloadDialogOkButton:pressed {
                background: #3a8eef;
            }
        """
