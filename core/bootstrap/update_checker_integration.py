# -*- coding: utf-8 -*-

"""
UpdateCheckerIntegration - 更新检查集成组件

负责在应用启动时异步检查更新，不阻塞主程序启动流程
"""

from typing import Optional
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication

from core.logger import get_logger
from core.update_checker import UpdateChecker
from ui.dialogs.update_dialog import UpdateDialog


class UpdateCheckThread(QThread):
    """更新检查线程"""
    
    # 信号：检查完成，携带版本信息
    update_available = pyqtSignal(dict)
    # 信号：检查失败或无更新
    check_completed = pyqtSignal()
    
    def __init__(self, current_version: str, force_check: bool = False):
        """
        初始化更新检查线程
        
        Args:
            current_version: 当前版本号
            force_check: 是否强制检查（忽略跳过列表）
        """
        super().__init__()
        self.current_version = current_version
        self.force_check = force_check
        self.logger = get_logger(__name__)
        
    def run(self):
        """在后台线程中执行更新检查"""
        try:
            self.logger.info("后台线程开始检查更新")
            
            # 创建更新检测器
            update_checker = UpdateChecker(current_version=self.current_version)
            
            # 获取或创建用户ID
            user_id = update_checker.get_or_create_user_id()
            
            # 上报启动事件（异步，不阻塞）
            update_checker.report_launch(user_id)
            
            # 检查更新
            if self.force_check:
                # 强制检查（忽略跳过列表）
                version_info = update_checker.check_for_updates_force()
            else:
                # 正常检查
                version_info = update_checker.check_for_updates()
            
            if version_info:
                latest_version = version_info.get('version', '')
                
                if self.force_check:
                    # 强制检查时总是显示
                    self.logger.info(f"发现新版本: {latest_version} (强制检查)")
                    self.update_available.emit(version_info)
                else:
                    # 正常检查时需要判断是否跳过
                    if update_checker.should_show_update(latest_version):
                        self.logger.info(f"发现新版本: {latest_version}")
                        self.update_available.emit(version_info)
                    else:
                        self.logger.info(f"版本 {latest_version} 已被跳过")
                        self.check_completed.emit()
            else:
                self.logger.info("没有可用更新")
                self.check_completed.emit()
                
        except Exception as e:
            self.logger.error(f"更新检查失败: {e}", exc_info=True)
            self.check_completed.emit()


class UpdateCheckerIntegration:
    """更新检查集成器"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.update_thread: Optional[UpdateCheckThread] = None
        self.update_checker: Optional[UpdateChecker] = None
        self.main_window = None  # 保存主窗口引用
        self.pending_update_info = None  # 缓存待显示的更新信息
        
    def cleanup(self):
        """清理更新检查线程，确保退出时不会残留"""
        if self.update_thread and self.update_thread.isRunning():
            self.logger.info("等待更新检查线程完成...")
            if not self.update_thread.wait(3000):  # 最多等 3 秒
                self.logger.warning("更新检查线程超时，强制终止")
                self.update_thread.terminate()
                self.update_thread.wait(1000)
        self.update_thread = None

    def check_for_updates_async(self, app: QApplication, main_window=None):
        """
        异步检查更新，不阻塞主程序启动
        
        Args:
            app: QApplication 实例
            main_window: 主窗口实例（可选，用于更新UI）
        """
        try:
            # 保存主窗口引用
            self.main_window = main_window
            
            # 获取当前版本号
            current_version = app.applicationVersion()
            
            self.logger.info(f"启动异步更新检查，当前版本: {current_version}")
            
            # 首先检查是否有待处理的强制更新
            update_checker = UpdateChecker(current_version=current_version)
            pending_force_update = update_checker.get_pending_force_update()
            
            if pending_force_update:
                # 有待处理的强制更新，即使断网也要显示
                self.logger.warning("检测到待处理的强制更新，立即显示更新对话框")
                self._show_update_dialog(pending_force_update, app, is_pending_force=True)
                return
            
            # 创建更新检查线程
            self.update_thread = UpdateCheckThread(current_version, force_check=False)
            
            # 连接信号
            self.update_thread.update_available.connect(
                lambda version_info: self._show_update_dialog(version_info, app)
            )
            self.update_thread.check_completed.connect(
                lambda: self.logger.info("更新检查完成")
            )
            
            # 启动线程
            self.update_thread.start()
            
        except Exception as e:
            self.logger.error(f"启动更新检查失败: {e}", exc_info=True)
    
    def check_for_updates_manual(self, app: QApplication, main_window=None):
        """
        手动检查更新（用户点击按钮触发）
        强制检查，忽略跳过列表
        
        Args:
            app: QApplication 实例
            main_window: 主窗口实例（可选，用于更新UI）
        """
        try:
            # 保存主窗口引用
            self.main_window = main_window
            
            # 获取当前版本号
            current_version = app.applicationVersion()
            
            self.logger.info(f"手动检查更新，当前版本: {current_version}")
            
            # 创建更新检查线程（强制检查）
            self.update_thread = UpdateCheckThread(current_version, force_check=True)
            
            # 连接信号
            self.update_thread.update_available.connect(
                lambda version_info: self._show_update_dialog(version_info, app, is_manual=True)
            )
            self.update_thread.check_completed.connect(
                lambda: self._on_manual_check_completed()
            )
            
            # 启动线程
            self.update_thread.start()
            
        except Exception as e:
            self.logger.error(f"手动检查更新失败: {e}", exc_info=True)
    
    def _on_manual_check_completed(self):
        """手动检查完成但没有更新时的处理"""
        self.logger.info("手动检查完成，没有可用更新")
        # 可以在这里显示一个提示消息
        if self.main_window:
            from modules.asset_manager.ui.message_dialog import MessageDialog
            MessageDialog(
                "检查更新",
                "当前已是最新版本！",
                "info",
                parent=self.main_window
            ).exec()
    
    def _show_update_dialog(self, version_info: dict, app: QApplication, is_manual: bool = False, is_pending_force: bool = False):
        """
        显示更新对话框
        
        Args:
            version_info: 版本信息字典
            app: QApplication 实例
            is_manual: 是否为手动检查触发
            is_pending_force: 是否为待处理的强制更新
        """
        try:
            self.logger.info("显示更新对话框")
            
            # 缓存更新信息
            self.pending_update_info = version_info
            
            # 更新主窗口的检查更新按钮文字
            if self.main_window and hasattr(self.main_window, 'check_update_btn'):
                self.main_window.check_update_btn.setText("有新版本")
                self.logger.info("已更新主窗口的检查更新按钮文字")
            else:
                self.logger.info("主窗口尚未创建，更新信息已缓存，将在主窗口创建后更新按钮")
            
            # 获取强制更新标志
            force_update = version_info.get('force_update', False)
            
            # 显示更新对话框
            result = UpdateDialog.show_update_dialog(
                version_info=version_info,
                force_update=force_update,
                parent=self.main_window  # 使用主窗口作为父窗口
            )
            
            # 处理用户选择
            if result == UpdateDialog.RESULT_SKIP:
                # 用户选择跳过此版本
                if force_update:
                    # 强制更新不允许跳过，但如果用户关闭了对话框，保持标记
                    self.logger.warning("强制更新不允许跳过，保持待处理标记")
                elif not is_manual:
                    # 只有自动检查时才记录跳过
                    self._skip_version(version_info.get('version', ''), app.applicationVersion())
                    self.logger.info("已记录跳过版本（自动检查）")
                else:
                    # 手动检查时不记录跳过，但给出提示
                    self.logger.info("手动检查时跳过版本，不记录到跳过列表")
                # 清除缓存的更新信息
                self.pending_update_info = None
            elif result == UpdateDialog.RESULT_UPDATE:
                # 用户选择立即更新
                # 注意：不清除强制更新标记，因为每个版本都是独立的
                # 标记只会在检测到当前版本已满足要求时自动清除（在 get_pending_force_update 中）
                self.logger.info("用户选择立即更新，标记将在新版本启动时自动清除")
            elif result == UpdateDialog.RESULT_LATER:
                # 用户选择稍后提醒
                if force_update:
                    # 强制更新时选择稍后，保持标记
                    self.logger.warning("强制更新选择稍后，保持待处理标记")
                
        except Exception as e:
            self.logger.error(f"显示更新对话框失败: {e}", exc_info=True)
    
    def set_main_window(self, main_window):
        """
        设置主窗口引用，并检查是否有待显示的更新
        
        Args:
            main_window: 主窗口实例
        """
        self.main_window = main_window
        
        # 如果有缓存的更新信息，立即更新按钮状态和显示小红点
        if self.pending_update_info:
            if hasattr(main_window, 'check_update_btn'):
                main_window.check_update_btn.setText("有新版本")
                self.logger.info("主窗口已创建，更新了检查更新按钮文字为'有新版本'")
            
            # 显示小红点
            if hasattr(main_window, 'show_update_badge'):
                main_window.show_update_badge()
                self.logger.info("主窗口已创建，显示了更新小红点")
    
    
    def _skip_version(self, version: str, current_version: str):
        """
        记录跳过的版本
        
        Args:
            version: 要跳过的版本号
            current_version: 当前版本号
        """
        try:
            # 创建更新检测器实例
            if self.update_checker is None:
                self.update_checker = UpdateChecker(current_version=current_version)
            
            # 记录跳过的版本
            self.update_checker.skip_version(version)
            self.logger.info(f"已记录跳过版本: {version}")
            
        except Exception as e:
            self.logger.error(f"记录跳过版本失败: {e}", exc_info=True)

