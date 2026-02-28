# -*- coding: utf-8 -*-

"""
AI模型管理器

负责AI模型的检查、下载和管理
"""

from pathlib import Path
from typing import Dict, Optional
from core.logger import get_logger

logger = get_logger(__name__)


class AIModelManager:
    """AI模型管理器"""
    
    MODEL_NAME = "BAAI/bge-small-zh-v1.5"
    
    @staticmethod
    def check_model_integrity() -> bool:
        """检查AI模型完整性
        
        Returns:
            bool: 模型是否完整可用
        """
        try:
            # 检查模型缓存目录
            cache_dir = Path.home() / '.cache' / 'huggingface' / 'hub'
            model_dir = cache_dir / 'models--BAAI--bge-small-zh-v1.5'
            
            if not model_dir.exists():
                logger.info("AI模型目录不存在")
                return False
            
            # 检查关键文件是否存在（支持新旧格式）
            required_files = ['config.json']
            # 模型文件可以是 pytorch_model.bin 或 model.safetensors
            model_file_options = ['pytorch_model.bin', 'model.safetensors']
            
            snapshots_dir = model_dir / 'snapshots'
            
            if not snapshots_dir.exists():
                logger.info("AI模型snapshots目录不存在")
                return False
            
            # 查找最新的snapshot
            snapshot_dirs = [d for d in snapshots_dir.iterdir() if d.is_dir()]
            if not snapshot_dirs:
                logger.info("AI模型snapshot为空")
                return False
            
            # 检查最新snapshot中的文件
            latest_snapshot = max(snapshot_dirs, key=lambda d: d.stat().st_mtime)
            
            # 检查必需文件
            for file_name in required_files:
                if not (latest_snapshot / file_name).exists():
                    logger.info(f"AI模型缺少文件: {file_name}")
                    return False
            
            # 检查模型文件（至少有一个）
            has_model_file = any((latest_snapshot / model_file).exists() for model_file in model_file_options)
            if not has_model_file:
                logger.info(f"AI模型缺少模型文件（需要以下之一: {', '.join(model_file_options)}）")
                return False
            
            logger.info("AI模型完整性检查通过")
            return True
            
        except Exception as e:
            logger.error(f"检查AI模型完整性失败: {e}", exc_info=True)
            return False
    
    @staticmethod
    def get_model_status() -> Dict[str, any]:
        """获取模型状态信息
        
        Returns:
            dict: 模型状态信息
        """
        try:
            available = AIModelManager.check_model_integrity()
            cache_dir = Path.home() / '.cache' / 'huggingface' / 'hub'
            model_dir = cache_dir / 'models--BAAI--bge-small-zh-v1.5'
            
            status = {
                "available": available,
                "model_name": AIModelManager.MODEL_NAME,
                "cache_path": str(model_dir),
                "size": 0
            }
            
            # 计算模型大小
            if model_dir.exists():
                total_size = sum(f.stat().st_size for f in model_dir.rglob('*') if f.is_file())
                status["size"] = total_size
            
            return status
            
        except Exception as e:
            logger.error(f"获取模型状态失败: {e}", exc_info=True)
            return {
                "available": False,
                "model_name": AIModelManager.MODEL_NAME,
                "cache_path": "",
                "size": 0
            }
    
    @staticmethod
    def ensure_model_available(parent=None) -> bool:
        """确保模型可用（已禁用自动下载）
        
        Args:
            parent: 父窗口（用于对话框）
            
        Returns:
            bool: 模型是否可用
        """
        try:
            # 检查模型是否已可用
            if AIModelManager.check_model_integrity():
                logger.info("AI模型已可用")
                return True
            
            # 模型不可用，但不触发下载，直接返回 False
            logger.info("AI模型不可用，跳过语义搜索功能")
            return False
            
        except Exception as e:
            logger.error(f"检查模型可用性失败: {e}", exc_info=True)
            return False
