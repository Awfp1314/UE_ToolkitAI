"""
运行时钩子：修复编码问题和禁用临时目录清理
确保程序在打包后能正确处理中文字符，并避免退出时的清理警告
"""
import sys
import os
import atexit

# 设置默认编码为 UTF-8
if sys.platform == 'win32':
    # Windows 平台设置
    import locale
    
    # 设置环境变量
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    
    # 尝试设置控制台编码（如果有控制台）
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleCP(65001)  # UTF-8
        kernel32.SetConsoleOutputCP(65001)  # UTF-8
    except:
        pass
    
    # 设置默认编码
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='ignore')
        sys.stderr.reconfigure(encoding='utf-8', errors='ignore')
    except:
        pass

# 禁用 PyInstaller 的临时目录自动清理
if getattr(sys, 'frozen', False):
    def _disable_cleanup():
        """禁用 PyInstaller 的自动清理，避免退出时弹窗"""
        pass
    
    # 清空所有已注册的 atexit 函数中可能的清理函数
    # 这样可以避免 PyInstaller 在退出时尝试删除临时目录
    try:
        # 保存用户注册的 atexit 函数
        user_funcs = []
        if hasattr(atexit, '_exithandlers'):
            # 过滤掉可能的 PyInstaller 清理函数
            for func, args, kwargs in atexit._exithandlers:
                # 保留用户代码注册的函数，过滤掉可能的系统清理函数
                if hasattr(func, '__module__') and func.__module__ and 'PyInstaller' not in func.__module__:
                    user_funcs.append((func, args, kwargs))
            
            # 清空并重新注册用户函数
            atexit._exithandlers.clear()
            for func, args, kwargs in user_funcs:
                atexit.register(func, *args, **kwargs)
    except:
        pass
