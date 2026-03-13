# -*- coding: utf-8 -*-

"""
缩略图管理模块

从 AssetScanner 提取的缩略图相关逻辑，
包括缩略图查找、恢复、迁移等功能。
不包含 Qt 信号和 UI 依赖。
"""

import shutil
import logging
from pathlib import Path
from typing import Optional


class ThumbnailManager:
    """缩略图管理类

    负责缩略图的查找、恢复和迁移操作。
    不包含 Qt 信号、配置持久化逻辑。

    Attributes:
        logger: 日志记录器
    """

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def find_thumbnail_by_asset_id(
        self,
        asset_id: Optional[str],
        thumbnails_dir: Optional[Path]
    ) -> Optional[Path]:
        """根据资产ID在缩略图目录中查找缩略图

        Args:
            asset_id: 资产ID
            thumbnails_dir: 缩略图目录路径

        Returns:
            如果找到缩略图返回Path对象，否则返回None
        """
        if not asset_id or not thumbnails_dir or not thumbnails_dir.exists():
            return None

        try:
            thumbnail_path = thumbnails_dir / f"{asset_id}.png"
            if thumbnail_path.exists():
                self.logger.debug(f"找到了缩略图文件: {thumbnail_path}")
                return thumbnail_path

            self.logger.debug(f"缩略图不存在: {thumbnail_path}")
            return None

        except Exception as e:
            self.logger.warning(f"查找缩略图失败 (asset_id: {asset_id}): {e}")
            return None

    def find_existing_thumbnail_for_new_asset(
        self,
        asset_path: Path,
        thumbnails_dir: Optional[Path]
    ) -> Optional[Path]:
        """为新资产查找已存在的缩略图文件

        Args:
            asset_path: 资产路径
            thumbnails_dir: 缩略图目录路径

        Returns:
            如果找到返回缩略图路径，否则返回None
        """
        if not thumbnails_dir or not thumbnails_dir.exists():
            return None

        try:
            return None
        except Exception as e:
            self.logger.debug(f"查找已存在缩略图失败: {e}")
            return None

    def restore_thumbnail_from_asset(
        self,
        asset_path: Path,
        asset_id: Optional[str],
        thumbnails_dir: Optional[Path]
    ) -> Optional[Path]:
        """从资产包内的preview.png恢复缩略图

        Args:
            asset_path: 资产路径
            asset_id: 资产ID
            thumbnails_dir: 缩略图目录路径

        Returns:
            如果成功复制返回新的缩略图路径，否则返回None
        """
        if not asset_id or not thumbnails_dir:
            return None

        try:
            preview_path = None
            if asset_path.is_dir():
                potential_preview = asset_path / "preview.png"
                if potential_preview.exists():
                    preview_path = potential_preview

            if not preview_path:
                return None

            if not thumbnails_dir.exists():
                thumbnails_dir.mkdir(parents=True, exist_ok=True)

            thumbnail_path = thumbnails_dir / f"{asset_id}.png"
            shutil.copy2(preview_path, thumbnail_path)
            self.logger.info(f"📋 从资产包复制缩略图: {asset_path.name}/preview.png")

            return thumbnail_path

        except Exception as e:
            self.logger.debug(f"从资产包恢复缩略图失败: {e}")
            return None

    # Others 类型资产的文件扩展名分类
    IMAGE_EXTENSIONS = {
        '.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tga', '.tif', '.tiff',
        '.webp', '.svg', '.ico', '.exr', '.hdr',
    }
    VIDEO_EXTENSIONS = {
        '.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm',
    }
    AUDIO_EXTENSIONS = {
        '.mp3', '.wav', '.ogg', '.flac', '.aac', '.wma',
    }

    def generate_others_thumbnail(
        self,
        asset_path: Path,
        asset_id: Optional[str],
        thumbnails_dir: Optional[Path]
    ) -> Optional[Path]:
        """为 Others 类型资产生成缩略图
        
        规则：
        - 图片/纹理：使用自身作为缩略图
        - 视频：生成带 ▶ 的默认图标
        - 音频：生成带 🔊 的默认图标
        - 其他：不生成
        
        Args:
            asset_path: 资产根目录（包装文件夹）
            asset_id: 资产 ID
            thumbnails_dir: 缩略图目录
            
        Returns:
            生成的缩略图路径，或 None
        """
        if not asset_id or not thumbnails_dir:
            return None
        
        try:
            # Others 子目录
            others_dir = asset_path / "Others"
            scan_dir = others_dir if others_dir.exists() else asset_path
            
            first_image = None
            first_video = None
            first_audio = None
            
            for f in scan_dir.rglob("*"):
                if not f.is_file():
                    continue
                ext = f.suffix.lower()
                if ext in self.IMAGE_EXTENSIONS and not first_image:
                    first_image = f
                elif ext in self.VIDEO_EXTENSIONS and not first_video:
                    first_video = f
                elif ext in self.AUDIO_EXTENSIONS and not first_audio:
                    first_audio = f
                # 一旦找到图片就停止，优先用图片做缩略图
                if first_image:
                    break
            
            thumbnails_dir.mkdir(parents=True, exist_ok=True)
            output_path = thumbnails_dir / f"{asset_id}.png"
            
            if first_image:
                # 图片/纹理：用自身生成缩略图
                return self._generate_image_thumbnail(first_image, output_path)
            elif first_video:
                # 视频：生成带 ▶ 的默认图标
                return self._generate_icon_thumbnail(output_path, "▶ VIDEO", (60, 60, 80))
            elif first_audio:
                # 音频：生成带喇叭文字的默认图标
                return self._generate_icon_thumbnail(output_path, "♪ AUDIO", (60, 80, 60))
            
            return None
        except Exception as e:
            self.logger.warning(f"Others 缩略图生成失败: {e}")
            return None
    
    def _generate_image_thumbnail(self, image_path: Path, output_path: Path) -> Optional[Path]:
        """从图片文件生成缩略图"""
        try:
            from PIL import Image
            THUMB_SIZE = (200, 200)
            
            with Image.open(image_path) as img:
                if img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                img.thumbnail(THUMB_SIZE, Image.Resampling.LANCZOS)
                thumb = Image.new('RGB', THUMB_SIZE, (45, 45, 45))
                offset = ((THUMB_SIZE[0] - img.size[0]) // 2,
                         (THUMB_SIZE[1] - img.size[1]) // 2)
                thumb.paste(img, offset)
                thumb.save(output_path, 'PNG', quality=85)
                self.logger.info(f"Others 图片缩略图: {image_path.name}")
                return output_path
        except Exception as e:
            self.logger.warning(f"图片缩略图生成失败: {e}")
            return None
    
    def _generate_icon_thumbnail(self, output_path: Path, text: str,
                                  bg_color: tuple = (60, 60, 60)) -> Optional[Path]:
        """生成带文字的默认图标缩略图"""
        try:
            from PIL import Image, ImageDraw, ImageFont
            THUMB_SIZE = (200, 200)
            
            img = Image.new('RGB', THUMB_SIZE, bg_color)
            draw = ImageDraw.Draw(img)
            draw.rectangle([10, 10, 190, 190], outline=(100, 100, 100), width=2)
            
            try:
                font = ImageFont.truetype("arial.ttf", 28)
            except Exception:
                font = ImageFont.load_default()
            
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            position = ((200 - text_width) // 2, (200 - text_height) // 2)
            draw.text(position, text, fill=(180, 180, 180), font=font)
            
            img.save(output_path, 'PNG')
            self.logger.info(f"Others 图标缩略图: {text}")
            return output_path
        except Exception as e:
            self.logger.warning(f"图标缩略图生成失败: {e}")
            return None

    def migrate_thumbnails_and_docs(self) -> None:
        """迁移缩略图和文档到本地目录

        此方法现在只用于日志记录，实际目录创建发生在需要时：
        - 缩略图目录在生成缩略图时创建
        - 文档目录在创建资产文档时创建
        """
        self.logger.debug("本地缩略图和文档目录已准备好（实际创建将在需要时进行）")
