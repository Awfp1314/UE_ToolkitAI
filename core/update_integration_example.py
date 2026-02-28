# -*- coding: utf-8 -*-

"""
更新检测器集成示例
展示如何在主程序中集成更新检测功能
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.update_checker import UpdateChecker
from core.version import VERSION
from core.logger import get_logger

logger = get_logger(__name__)


def check_and_report_on_startup():
    """
    在程序启动时检查更新并上报统计
    这个函数应该在主程序启动时调用
    
    Returns:
        version_info: 如果有新版本，返回版本信息字典；否则返回None
    """
    try:
        # 创建更新检测器实例
        checker = UpdateChecker(current_version=VERSION)
        
        # 1. 首先上报启动事件（不阻塞程序启动）
        user_id = checker.get_or_create_user_id()
        checker.report_launch(user_id)
        
        # 2. 检查更新
        version_info = checker.check_for_updates()
        
        if version_info:
            latest_version = version_info.get('version', '')
            force_update = version_info.get('force_update', False)
            
            # 检查是否应该显示更新提示
            if force_update or checker.should_show_update(latest_version):
                logger.info(f"New version available: {latest_version}")
                return version_info
            else:
                logger.info(f"Version {latest_version} was skipped by user")
                return None
        else:
            logger.info("No updates available")
            return None
            
    except Exception as e:
        logger.error(f"Error during update check: {e}")
        # 即使出错也不阻塞程序启动
        return None


def handle_update_dialog_result(checker: UpdateChecker, version_info: dict, user_choice: str):
    """
    处理更新对话框的用户选择
    
    Args:
        checker: UpdateChecker实例
        version_info: 版本信息字典
        user_choice: 用户选择 ('update', 'skip', 'later')
    """
    latest_version = version_info.get('version', '')
    
    if user_choice == 'update':
        # 用户选择立即更新
        # 这里应该打开浏览器到下载页面
        import webbrowser
        download_url = version_info.get('download_url', 'http://localhost:5000')
        webbrowser.open(download_url)
        logger.info(f"Opening download page: {download_url}")
        
    elif user_choice == 'skip':
        # 用户选择跳过此版本
        checker.skip_version(latest_version)
        logger.info(f"User skipped version {latest_version}")
        
    elif user_choice == 'later':
        # 用户选择稍后提醒
        logger.info("User chose to be reminded later")
        
    else:
        logger.warning(f"Unknown user choice: {user_choice}")


# 使用示例
if __name__ == "__main__":
    print("=" * 60)
    print("更新检测器集成示例")
    print("=" * 60)
    print()
    
    # 在程序启动时调用
    version_info = check_and_report_on_startup()
    
    if version_info:
        print(f"\n发现新版本: {version_info.get('version')}")
        print(f"更新日志: {version_info.get('changelog', 'N/A')}")
        print(f"强制更新: {version_info.get('force_update', False)}")
        print(f"下载地址: {version_info.get('download_url', 'N/A')}")
        print()
        print("提示: 在实际应用中，这里应该显示更新对话框")
        print("      用户可以选择: 立即更新 / 跳过此版本 / 稍后提醒")
    else:
        print("\n当前已是最新版本或无法连接到更新服务器")
    
    print()
    print("=" * 60)
