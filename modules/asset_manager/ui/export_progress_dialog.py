# -*- coding: utf-8 -*-

"""
导出进度对话框
显示资产压缩导出的进度
"""

from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QProgressBar, QFileDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

import zipfile
import os
import logging

logger = logging.getLogger(__name__)


class ExportWorker(QThread):
    """导出工作线程"""
    
    progress_updated = pyqtSignal(int, str)  # 进度百分比, 当前文件名
    export_finished = pyqtSignal(bool, str)  # 成功/失败, 消息
    
    def __init__(self, source_path: Path, target_path: Path, package_type: str):
        super().__init__()
        self.source_path = source_path
        self.target_path = target_path
        self.package_type = package_type  # "content", "plugin", "project"
        self._is_cancelled = False
    
    def cancel(self):
        """取消导出"""
        self._is_cancelled = True
    
    def run(self):
        """执行导出"""
        try:
            # 根据资产类型确定源内容路径和目标结构
            if self.package_type == "content":
                # 资产包：导出 Content 文件夹内容到 自定义名称/Content/
                content_path = self.source_path / "Content"
                if not content_path.exists():
                    self.export_finished.emit(False, "资产包 Content 文件夹不存在")
                    return
                source_content_path = content_path
                target_wrapper = "Content"
                
            elif self.package_type == "plugin":
                # 插件：导出 Plugins 文件夹内容到 自定义名称/Plugins/
                plugins_path = self.source_path / "Plugins"
                if not plugins_path.exists():
                    self.export_finished.emit(False, "插件 Plugins 文件夹不存在")
                    return
                source_content_path = plugins_path
                target_wrapper = "Plugins"
                
            elif self.package_type == "project":
                # 工程资产：找到 Project 下的工程文件夹，导出其 Content 到 自定义名称/Content/
                project_dir = self.source_path / "Project"
                if not project_dir.exists():
                    self.export_finished.emit(False, "工程资产 Project 文件夹不存在")
                    return
                
                # 查找包含 .uproject 文件的工程文件夹
                project_folder = None
                for item in project_dir.iterdir():
                    if item.is_dir():
                        uproject_files = list(item.glob("*.uproject"))
                        if uproject_files:
                            project_folder = item
                            break
                
                if not project_folder:
                    self.export_finished.emit(False, "未找到工程文件夹")
                    return
                
                content_path = project_folder / "Content"
                if not content_path.exists():
                    self.export_finished.emit(False, "工程 Content 文件夹不存在")
                    return
                
                source_content_path = content_path
                target_wrapper = "Content"
                
            elif self.package_type == "others":
                # 其他资源：导出 Others 文件夹内容到 自定义名称/Others/
                others_path = self.source_path / "Others"
                if others_path.exists() and others_path.is_dir():
                    # 新结构：有 Others 文件夹
                    source_content_path = others_path
                else:
                    # 兼容旧结构：直接从根目录导出
                    source_content_path = self.source_path
                target_wrapper = "Others"
                
            else:
                # 未知类型：直接导出整个文件夹
                source_content_path = self.source_path
                target_wrapper = None
            
            # 收集所有文件
            all_files = []
            for root, dirs, files in os.walk(source_content_path):
                for file in files:
                    file_path = Path(root) / file
                    all_files.append(file_path)
            
            if not all_files:
                self.export_finished.emit(False, "资产目录为空")
                return
            
            total_files = len(all_files)
            logger.info(f"开始导出，共 {total_files} 个文件")
            
            # 获取自定义名称（压缩包名去掉 .zip）
            custom_name = self.target_path.stem
            
            # 创建 ZIP 文件
            with zipfile.ZipFile(self.target_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for i, file_path in enumerate(all_files):
                    if self._is_cancelled:
                        self.export_finished.emit(False, "导出已取消")
                        # 删除未完成的文件
                        if self.target_path.exists():
                            self.target_path.unlink()
                        return
                    
                    # 计算相对路径
                    rel_path = file_path.relative_to(source_content_path)
                    
                    # 构建目标路径：自定义名称/Content(或Plugins)/相对路径
                    if target_wrapper:
                        zip_path = Path(custom_name) / target_wrapper / rel_path
                    else:
                        zip_path = Path(custom_name) / rel_path
                    
                    # 添加到 ZIP
                    zipf.write(file_path, zip_path)
                    
                    # 更新进度
                    progress = int((i + 1) / total_files * 100)
                    self.progress_updated.emit(progress, file_path.name)
            
            # 获取文件大小
            zip_size = self.target_path.stat().st_size
            size_str = self._format_size(zip_size)
            
            self.export_finished.emit(True, f"导出成功！文件大小: {size_str}")
            logger.info(f"导出完成: {self.target_path}, 大小: {size_str}")
            
        except Exception as e:
            logger.error(f"导出失败: {e}", exc_info=True)
            self.export_finished.emit(False, f"导出失败: {str(e)}")
    
    def _format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


class ExportProgressDialog(QDialog):
    """导出进度对话框"""
    
    def __init__(self, asset_name: str, source_path: Path, package_type: str, parent=None):
        super().__init__(parent)
        self.asset_name = asset_name
        self.source_path = source_path
        self.package_type = package_type  # "content", "plugin", "project"
        self.target_path = None
        self.worker = None
        
        self.setWindowTitle("导出资产")
        self.setFixedSize(450, 200)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 标题
        title_label = QLabel(f"📤 导出资产: {self.asset_name}")
        title_label.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        layout.addWidget(title_label)
        
        # 状态标签
        self.status_label = QLabel("准备导出...")
        self.status_label.setObjectName("ExportStatusLabel")
        layout.addWidget(self.status_label)
        
        # 当前文件标签
        self.file_label = QLabel("")
        self.file_label.setObjectName("ExportFileLabel")
        self.file_label.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(self.file_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(24)
        layout.addWidget(self.progress_bar)
        
        layout.addStretch()
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setFixedWidth(80)
        self.cancel_btn.clicked.connect(self._on_cancel)
        btn_layout.addWidget(self.cancel_btn)
        
        self.close_btn = QPushButton("关闭")
        self.close_btn.setFixedWidth(80)
        self.close_btn.clicked.connect(self.accept)
        self.close_btn.hide()
        btn_layout.addWidget(self.close_btn)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)
    
    def start_export(self):
        """开始导出 - 先选择保存目录"""
        # 弹出目录选择对话框（只选择目录，文件名使用源文件夹名）
        export_dir = QFileDialog.getExistingDirectory(
            self,
            "选择导出目录",
            str(Path.home() / "Desktop"),
            QFileDialog.Option.ShowDirsOnly
        )
        
        if not export_dir:
            self.reject()
            return
        
        # 使用源文件夹名作为压缩包名（如 AGhostaghost.zip）
        folder_name = self.source_path.name
        self.target_path = Path(export_dir) / f"{folder_name}.zip"
        
        # 如果文件已存在，询问是否覆盖
        if self.target_path.exists():
            from .confirm_dialog import ConfirmDialog
            dialog = ConfirmDialog(
                "文件已存在",
                f"文件 \"{folder_name}.zip\" 已存在，是否覆盖？",
                "覆盖后将替换原有压缩包。",
                self
            )
            if hasattr(dialog, 'center_on_parent'):
                dialog.center_on_parent()
            if dialog.exec() != ConfirmDialog.DialogCode.Accepted:
                self.reject()
                return
        
        # 更新状态
        self.status_label.setText("正在压缩...")
        
        # 创建并启动工作线程
        self.worker = ExportWorker(self.source_path, self.target_path, self.package_type)
        self.worker.progress_updated.connect(self._on_progress_updated)
        self.worker.export_finished.connect(self._on_export_finished)
        self.worker.start()
    
    def _on_progress_updated(self, progress: int, filename: str):
        """进度更新"""
        self.progress_bar.setValue(progress)
        self.file_label.setText(f"正在处理: {filename}")
    
    def _on_export_finished(self, success: bool, message: str):
        """导出完成"""
        if success:
            self.status_label.setText("✅ " + message)
            self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        else:
            self.status_label.setText("❌ " + message)
            self.status_label.setStyleSheet("color: #F44336; font-weight: bold;")
        
        self.file_label.setText("")
        self.cancel_btn.hide()
        self.close_btn.show()
    
    def _on_cancel(self):
        """取消导出"""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.status_label.setText("正在取消...")
        else:
            self.reject()
    
    def closeEvent(self, event):
        """关闭事件"""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(2000)
        event.accept()
