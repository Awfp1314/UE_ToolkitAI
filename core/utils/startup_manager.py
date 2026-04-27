# -*- coding: utf-8 -*-
"""
启动管理器 - 统一管理开机自启动逻辑

提供注册表操作和启动参数检测的公共函数
"""

import sys
from pathlib import Path
from core.logger import get_logger

logger = get_logger(__name__)

# 启动参数常量
ARG_MINIMIZED = "--minimized"

# Windows 注册表常量
AUTOSTART_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
AUTOSTART_NAME = "UEToolkit"


def is_autostart_enabled() -> bool:
    """检查开机自启动是否已启用
    
    Returns:
        bool: True 表示已启用，False 表示未启用
    """
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, AUTOSTART_KEY,
            0, winreg.KEY_READ
        )
        winreg.QueryValueEx(key, AUTOSTART_NAME)
        winreg.CloseKey(key)
        return True
    except Exception:
        return False


def set_autostart_enabled(enabled: bool) -> None:
    """设置开机自启动状态
    
    Args:
        enabled: True 启用自启动，False 禁用自启动
        
    Raises:
        Exception: 注册表操作失败时抛出异常
    """
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, AUTOSTART_KEY,
            0, winreg.KEY_SET_VALUE
        )
        
        if enabled:
            if getattr(sys, 'frozen', False):
                # 打包环境：使用 exe 绝对路径 + --minimized 参数（静默启动）
                cmd = f'"{sys.executable}" {ARG_MINIMIZED}'
            else:
                # 开发环境：用 pythonw.exe 启动 main.py（隐藏命令行窗口）
                pythonw = Path(sys.executable).parent / "pythonw.exe"
                if not pythonw.exists():
                    pythonw = Path(sys.executable)
                # 获取项目根目录的 main.py
                main_py = Path(__file__).resolve().parents[2] / "main.py"
                cmd = f'"{pythonw}" "{main_py}" {ARG_MINIMIZED}'
            
            winreg.SetValueEx(
                key, AUTOSTART_NAME,
                0, winreg.REG_SZ, cmd
            )
            logger.info(f"开机自启动已启用: {cmd}")
        else:
            try:
                winreg.DeleteValue(key, AUTOSTART_NAME)
                logger.info("开机自启动已禁用")
            except FileNotFoundError:
                pass  # 注册表项不存在，无需删除
        
        winreg.CloseKey(key)
        
    except Exception as e:
        logger.error(f"设置开机自启动失败: {e}")
        raise


def is_minimized_start() -> bool:
    """检查当前是否为最小化启动（开机自启动模式）
    
    Returns:
        bool: True 表示最小化启动，False 表示正常启动
    """
    return ARG_MINIMIZED in sys.argv
