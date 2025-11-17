# -*- coding: utf-8 -*-

"""
集成测试配置和 fixtures
"""

import pytest
import tempfile
import shutil
from pathlib import Path
import os


class TestEnvironment:
    """测试环境管理器，提供隔离的测试环境"""
    
    def __init__(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="ue_toolkit_test_"))
        self.config_dir = self.temp_dir / "configs"
        self.log_dir = self.temp_dir / "logs"
        self.config_dir.mkdir(parents=True)
        self.log_dir.mkdir(parents=True)
        
        # 设置测试环境变量
        os.environ['TEST_MODE'] = '1'
        os.environ['UE_TOOLKIT_USER_DATA_DIR'] = str(self.temp_dir)
    
    def cleanup(self):
        """清理测试环境"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
        # 清理环境变量
        os.environ.pop('TEST_MODE', None)
        os.environ.pop('UE_TOOLKIT_USER_DATA_DIR', None)


@pytest.fixture(scope="function")
def test_env():
    """提供隔离的测试环境
    
    每个测试函数都会获得一个独立的测试环境
    """
    env = TestEnvironment()
    yield env
    env.cleanup()


@pytest.fixture(scope="function")
def clean_services():
    """清理所有服务单例
    
    确保每个测试都从干净的状态开始
    """
    # 测试前清理
    from core.services import cleanup_all_services
    cleanup_all_services()
    
    yield
    
    # 测试后清理
    cleanup_all_services()

