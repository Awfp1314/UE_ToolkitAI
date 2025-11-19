"""
启动测试运行器服务器
双击此文件即可启动！
"""
import sys
from pathlib import Path
import webbrowser
import time
import threading

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.test_server import start_server


def open_browser():
    """延迟打开浏览器"""
    time.sleep(1.5)
    webbrowser.open('http://localhost:8000/test_runner.html')


if __name__ == '__main__':
    print("""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║   🎉 正在启动测试运行器...                               ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    # 在后台线程中打开浏览器
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()
    
    # 启动服务器（阻塞）
    start_server(port=8000)

