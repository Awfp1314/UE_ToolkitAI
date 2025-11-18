"""
截图处理器类

处理 UE 截图，生成缩略图。
"""

import os
import time
from pathlib import Path
from typing import Optional
from logging import Logger


class ScreenshotProcessor:
    """截图处理器类
    
    提供截图处理功能：
    - 查找 UE 项目截图
    - 生成缩略图
    - 查找已有缩略图
    """
    
    # 支持的图片格式
    SUPPORTED_FORMATS = ['.png', '.jpg', '.jpeg']
    
    # 缩略图大小
    THUMBNAIL_SIZE = (256, 256)
    
    # 截图目录相对路径
    SCREENSHOT_DIR = "Saved/Screenshots/Windows"
    
    def __init__(self, logger: Logger):
        """初始化截图处理器
        
        Args:
            logger: 日志记录器
        """
        self._logger = logger
        self._mock_mode = os.environ.get('ASSET_MANAGER_MOCK_MODE') == '1'
        
        # 尝试导入 PIL
        self._pil_available = False
        try:
            from PIL import Image
            self._Image = Image
            self._pil_available = True
            self._logger.info("PIL is available, thumbnail generation enabled")
        except ImportError:
            self._logger.warning(
                "PIL not installed, thumbnail generation disabled. "
                "Install with: pip install Pillow"
            )
        
        if self._mock_mode:
            self._logger.info("ScreenshotProcessor: Mock mode enabled")
    
    def find_screenshot(
        self,
        project_path: Path,
        timeout: int = 30
    ) -> Optional[Path]:
        """查找 UE 项目截图
        
        Args:
            project_path: UE 项目路径
            timeout: 超时时间（秒）
        
        Returns:
            Optional[Path]: 截图路径，未找到返回 None
        """
        if self._mock_mode:
            # Mock 模式：返回测试图片路径
            test_screenshot = Path("tests/fixtures/test_screenshot.png")
            self._logger.info(f"Mock mode: returning test screenshot: {test_screenshot}")
            return test_screenshot if test_screenshot.exists() else None
        
        try:
            screenshot_dir = project_path / self.SCREENSHOT_DIR
            if not screenshot_dir.exists():
                self._logger.warning(f"Screenshot directory not found: {screenshot_dir}")
                return None
            
            # 查找最新的截图文件
            start_time = time.time()
            latest_screenshot = None
            latest_time = 0
            
            while time.time() - start_time < timeout:
                for ext in self.SUPPORTED_FORMATS:
                    for screenshot in screenshot_dir.glob(f"*{ext}"):
                        mtime = screenshot.stat().st_mtime
                        if mtime > latest_time:
                            latest_time = mtime
                            latest_screenshot = screenshot
                
                if latest_screenshot:
                    self._logger.info(f"Found screenshot: {latest_screenshot}")
                    return latest_screenshot
                
                time.sleep(0.5)
            
            self._logger.warning(f"No screenshot found in {timeout} seconds")
            return None
            
        except Exception as e:
            self._logger.warning(f"Failed to find screenshot: {e}")
            return None
    
    def find_thumbnail(
        self,
        asset_id: str,
        thumbnails_dir: Path
    ) -> Optional[Path]:
        """查找资产缩略图
        
        Args:
            asset_id: 资产 ID
            thumbnails_dir: 缩略图目录
        
        Returns:
            Optional[Path]: 缩略图路径，未找到返回 None
        """
        try:
            thumbnail_path = thumbnails_dir / f"{asset_id}.png"
            if thumbnail_path.exists():
                return thumbnail_path
            return None
        except Exception as e:
            self._logger.warning(f"Failed to find thumbnail: {e}")
            return None
    
    def process_screenshot(
        self,
        asset,
        screenshot_path: Path,
        thumbnails_dir: Path
    ) -> bool:
        """处理截图，生成缩略图

        Args:
            asset: 资产对象
            screenshot_path: 截图路径
            thumbnails_dir: 缩略图目录

        Returns:
            bool: 成功返回 True，失败返回 False
        """
        try:
            # 检查截图文件是否存在
            if not screenshot_path.exists():
                self._logger.warning(f"Screenshot file not found: {screenshot_path}")
                return False

            # 检查文件格式
            if screenshot_path.suffix.lower() not in self.SUPPORTED_FORMATS:
                self._logger.error(f"Unsupported image format: {screenshot_path.suffix}")
                return False

            # 创建缩略图目录
            thumbnails_dir.mkdir(parents=True, exist_ok=True)

            # 获取资产 ID
            asset_id = getattr(asset, 'id', str(id(asset)))
            thumbnail_path = thumbnails_dir / f"{asset_id}.png"

            if self._mock_mode:
                # Mock 模式：复制测试图片
                import shutil
                shutil.copy2(screenshot_path, thumbnail_path)
                self._logger.info(f"Mock mode: copied screenshot to {thumbnail_path}")
                return True

            # 检查 PIL 是否可用
            if not self._pil_available:
                self._logger.error("PIL not available, cannot generate thumbnail")
                return False

            # 生成缩略图
            with self._Image.open(screenshot_path) as img:
                # 保持宽高比缩放
                img.thumbnail(self.THUMBNAIL_SIZE, self._Image.Resampling.LANCZOS)
                # 保存为 PNG
                img.save(thumbnail_path, "PNG")

            self._logger.info(f"Generated thumbnail: {thumbnail_path}")
            return True

        except Exception as e:
            self._logger.warning(f"Failed to process screenshot: {e}")
            return False

