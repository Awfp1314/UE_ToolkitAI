"""
截图处理器类

处理 UE 截图，生成缩略图。
"""

import os
import time
from pathlib import Path
from typing import Optional
from logging import Logger

# 导入常量
from modules.asset_manager.constants import THUMBNAIL_SIZE_PX


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
    THUMBNAIL_SIZE = (THUMBNAIL_SIZE_PX, THUMBNAIL_SIZE_PX)
    
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
        thumbnail_source: Optional[str] = None
    ) -> tuple[Optional[Path], Optional[str]]:
        """查找 UE 项目截图
        
        查找策略：
        1. 优先在 {预览工程}/Saved/Screenshots/ 及其子文件夹下查找用户主动截图
        2. 如果已获取过 Saved/Screenshots/ 的图片，只有新图片才更新
        3. 如果找不到，在 {预览工程}/Saved/ 下查找自动保存的截图
        
        Args:
            project_path: UE 项目路径
            thumbnail_source: 缩略图来源（screenshots 或 autosave，用于判断是否需要更新）
        
        Returns:
            元组 (截图文件路径, 来源)，如果未找到返回 (None, None)
            来源值为 "screenshots" 或 "autosave"
        """
        if self._mock_mode:
            # Mock 模式：返回测试图片路径
            test_screenshot = Path("tests/fixtures/test_screenshot.png")
            self._logger.info(f"Mock mode: returning test screenshot: {test_screenshot}")
            return (test_screenshot, "screenshots") if test_screenshot.exists() else (None, None)
        
        try:
            # 第一步：查找用户截图
            screenshots_dir = project_path / "Saved" / "Screenshots"
            
            if screenshots_dir.exists():
                latest_screenshot = None
                latest_mtime = 0
                
                # 扫描 Screenshots 当前目录
                for file_path in screenshots_dir.glob("*.png"):
                    mtime = file_path.stat().st_mtime
                    if mtime > latest_mtime:
                        latest_mtime = mtime
                        latest_screenshot = file_path
                
                # 扫描所有子文件夹
                for subdir in screenshots_dir.iterdir():
                    if subdir.is_dir():
                        for file_path in subdir.glob("*.png"):
                            mtime = file_path.stat().st_mtime
                            if mtime > latest_mtime:
                                latest_mtime = mtime
                                latest_screenshot = file_path
                
                if latest_screenshot:
                    self._logger.info(f"找到用户截图: {latest_screenshot}")
                    return latest_screenshot, "screenshots"
            
            # 第二步：如果已获取过 Saved/Screenshots/ 的图片，不再查找自动保存图
            if thumbnail_source == "screenshots":
                self._logger.debug(f"已获取过用户截图，不再查找自动保存的截图")
                return None, None
            
            # 第三步：查找自动保存的截图
            saved_dir = project_path / "Saved"
            
            if saved_dir.exists():
                latest_autosave = None
                latest_mtime = 0
                
                # 在 Saved 目录下查找所有 PNG 文件（包括 Saved 根目录和所有子目录）
                for file_path in saved_dir.rglob("*.png"):
                    # 跳过 Screenshots 子目录中的文件（已在第一步检查过）
                    if "Screenshots" in str(file_path):
                        continue
                    
                    mtime = file_path.stat().st_mtime
                    if mtime > latest_mtime:
                        latest_mtime = mtime
                        latest_autosave = file_path
                
                if latest_autosave:
                    self._logger.info(f"找到自动保存的截图: {latest_autosave}")
                    return latest_autosave, "autosave"
            
            self._logger.debug(f"未找到任何截图")
            return None, None
            
        except Exception as e:
            self._logger.warning(f"Failed to find screenshot: {e}")
            return None, None
    
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

