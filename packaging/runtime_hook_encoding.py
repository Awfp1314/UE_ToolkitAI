"""
运行时钩子：修复编码问题
确保程序在打包后能正确处理中文字符
"""
import sys
import os

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
