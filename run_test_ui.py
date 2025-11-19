"""
测试运行器启动脚本
双击运行即可打开测试界面！
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.test_runner_ui import main

if __name__ == '__main__':
    main()

