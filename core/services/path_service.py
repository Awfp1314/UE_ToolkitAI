"""
PathService - 统一的路径访问服务

封装 PathUtils，提供简化的路径访问接口
Level 0 服务：无依赖
"""

from pathlib import Path
from typing import Union
from core.utils.path_utils import PathUtils


class PathService:
    """统一的路径访问服务
    
    封装 PathUtils，提供简化的路径访问接口
    
    特点：
    - Level 0 服务，无依赖
    - 封装现有 PathUtils 类
    - 线程安全（Path 操作本身是线程安全的）
    """
    
    def __init__(self):
        """初始化路径服务
        
        注意：使用 print() 记录初始化日志，避免循环依赖
        """
        self._path_utils = PathUtils()
        print("[PathService] 初始化完成")
    
    def get_user_data_dir(self, create: bool = True) -> Path:
        """获取用户数据目录
        
        Args:
            create: 是否创建目录（如果不存在）
            
        Returns:
            用户数据目录路径
            
        Example:
            data_dir = path_service.get_user_data_dir()
            print(f"数据目录: {data_dir}")
        """
        path = self._path_utils.get_user_data_dir()
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path
    
    def get_config_dir(self, create: bool = True) -> Path:
        """获取配置目录
        
        Args:
            create: 是否创建目录（如果不存在）
            
        Returns:
            配置目录路径
            
        Example:
            config_dir = path_service.get_config_dir()
            config_file = config_dir / "app_config.json"
        """
        path = self._path_utils.get_user_config_dir()
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path
    
    def get_log_dir(self, create: bool = True) -> Path:
        """获取日志目录
        
        Args:
            create: 是否创建目录（如果不存在）
            
        Returns:
            日志目录路径
            
        Example:
            log_dir = path_service.get_log_dir()
            log_file = log_dir / "app.log"
        """
        path = self._path_utils.get_user_logs_dir()
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path
    
    def get_cache_dir(self, create: bool = True) -> Path:
        """获取缓存目录
        
        Args:
            create: 是否创建目录（如果不存在）
            
        Returns:
            缓存目录路径
            
        Example:
            cache_dir = path_service.get_cache_dir()
            cache_file = cache_dir / "thumbnails.db"
        """
        user_data_dir = self.get_user_data_dir(create=False)
        cache_dir = user_data_dir / "cache"
        if create:
            cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir
    
    def ensure_dir_exists(self, path: Union[str, Path]) -> Path:
        """确保目录存在
        
        Args:
            path: 目录路径
            
        Returns:
            Path 对象
            
        Example:
            my_dir = path_service.ensure_dir_exists("data/exports")
        """
        path_obj = Path(path) if isinstance(path, str) else path
        path_obj.mkdir(parents=True, exist_ok=True)
        return path_obj
    
    def create_user_dirs(self) -> None:
        """创建所有用户目录
        
        创建配置、日志、缓存等标准目录
        
        Example:
            path_service.create_user_dirs()
        """
        self._path_utils.create_dirs()

