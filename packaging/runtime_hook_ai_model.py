# -*- coding: utf-8 -*-
"""
PyInstaller 运行时钩子 - AI模型初始化

在程序启动时，将打包的AI模型复制到正确的缓存目录
避免符号链接权限问题
"""

import os
import sys
import shutil
from pathlib import Path


def setup_ai_model():
    """设置AI模型到正确的缓存目录"""
    try:
        # 获取打包后的模型路径
        if getattr(sys, 'frozen', False):
            # 打包后的路径
            base_path = Path(sys._MEIPASS)
            packed_model_dir = base_path / 'ai_models' / 'models--BAAI--bge-small-zh-v1.5'
            
            if packed_model_dir.exists():
                # 目标缓存目录
                cache_dir = Path.home() / '.cache' / 'huggingface' / 'hub'
                target_model_dir = cache_dir / 'models--BAAI--bge-small-zh-v1.5'
                
                # 如果目标目录不存在，复制模型
                if not target_model_dir.exists():
                    print(f"[AI模型] 首次运行，正在初始化AI模型...")
                    cache_dir.mkdir(parents=True, exist_ok=True)
                    
                    # 复制整个模型目录
                    shutil.copytree(packed_model_dir, target_model_dir)
                    print(f"[AI模型] 模型初始化完成: {target_model_dir}")
                else:
                    print(f"[AI模型] 模型已存在，跳过初始化")
            else:
                print(f"[AI模型] 打包中未包含模型，将在首次使用时自动下载")
    except Exception as e:
        print(f"[AI模型] 初始化失败: {e}")
        # 不阻止程序启动，让模型在首次使用时自动下载


# 在导入任何其他模块之前执行
setup_ai_model()
