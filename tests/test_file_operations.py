"""
测试 FileOperations 类
"""

import os
import pytest
from pathlib import Path
from logging import Logger
from modules.asset_manager.logic.file_operations import FileOperations


@pytest.fixture
def logger():
    """创建测试用的 logger"""
    import logging
    return logging.getLogger('test_file_operations')


@pytest.fixture
def file_ops(logger):
    """创建 FileOperations 实例"""
    return FileOperations(logger)


@pytest.fixture
def mock_file_ops(logger, monkeypatch):
    """创建 Mock 模式的 FileOperations 实例"""
    monkeypatch.setenv('ASSET_MANAGER_MOCK_MODE', '1')
    return FileOperations(logger)


class TestSafeCopytree:
    """测试 safe_copytree 方法"""
    
    def test_copy_directory_success(self, file_ops, tmp_path):
        """测试成功复制目录"""
        # 创建源目录和文件
        src = tmp_path / "source"
        src.mkdir()
        (src / "file1.txt").write_text("content1")
        (src / "file2.txt").write_text("content2")
        
        # 目标目录
        dst = tmp_path / "destination"
        
        # 执行复制
        result = file_ops.safe_copytree(src, dst)
        
        # 验证
        assert result is True
        assert dst.exists()
        assert (dst / "file1.txt").read_text() == "content1"
        assert (dst / "file2.txt").read_text() == "content2"
    
    def test_copy_source_not_exists(self, file_ops, tmp_path):
        """测试源路径不存在"""
        src = tmp_path / "nonexistent"
        dst = tmp_path / "destination"
        
        result = file_ops.safe_copytree(src, dst)
        
        assert result is False
        assert not dst.exists()
    
    def test_copy_overwrite_existing(self, file_ops, tmp_path):
        """测试覆盖已存在的目标目录"""
        # 创建源目录
        src = tmp_path / "source"
        src.mkdir()
        (src / "new_file.txt").write_text("new content")
        
        # 创建已存在的目标目录
        dst = tmp_path / "destination"
        dst.mkdir()
        (dst / "old_file.txt").write_text("old content")
        
        # 执行复制
        result = file_ops.safe_copytree(src, dst)
        
        # 验证：目标目录被覆盖
        assert result is True
        assert dst.exists()
        assert (dst / "new_file.txt").exists()
        assert not (dst / "old_file.txt").exists()
    
    def test_copy_with_progress_callback(self, file_ops, tmp_path):
        """测试进度回调"""
        # 创建源目录
        src = tmp_path / "source"
        src.mkdir()
        (src / "file.txt").write_text("content")
        
        dst = tmp_path / "destination"
        
        # 进度回调
        progress_calls = []
        def progress_callback(current, total, message):
            progress_calls.append((current, total, message))
        
        # 执行复制
        result = file_ops.safe_copytree(src, dst, progress_callback)
        
        # 验证
        assert result is True
        assert len(progress_calls) > 0
        assert progress_calls[0][0] == 1
        assert progress_calls[0][1] == 1
    
    def test_copy_mock_mode(self, mock_file_ops, tmp_path):
        """测试 Mock 模式"""
        src = tmp_path / "source"
        dst = tmp_path / "destination"
        
        # Mock 模式下不需要源路径存在
        result = mock_file_ops.safe_copytree(src, dst)
        
        # 验证：返回 True，但不执行真实复制
        assert result is True
        assert not dst.exists()
    
    def test_copy_mock_mode_with_callback(self, mock_file_ops, tmp_path):
        """测试 Mock 模式的进度回调"""
        src = tmp_path / "source"
        dst = tmp_path / "destination"
        
        progress_calls = []
        def progress_callback(current, total, message):
            progress_calls.append((current, total, message))
        
        result = mock_file_ops.safe_copytree(src, dst, progress_callback)
        
        assert result is True
        assert len(progress_calls) == 1
        assert "Mock" in progress_calls[0][2]

