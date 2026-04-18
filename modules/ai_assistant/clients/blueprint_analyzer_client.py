# -*- coding: utf-8 -*-

"""
Blueprint Analyzer 客户端
用于与虚幻引擎编辑器的 Blueprint Analyzer 插件进行通信
"""

from modules.ai_assistant.clients.ue_tool_client import UEToolClient
from core.logger import get_logger

logger = get_logger(__name__)


class BlueprintAnalyzerClient(UEToolClient):
    """
    Blueprint Analyzer HTTP 客户端
    
    继承自 UEToolClient，提供蓝图分析功能
    
    功能：
    - 提取蓝图结构（变量、函数、图表）
    - 提取 UMG Widget 蓝图
    - 获取编辑器上下文信息
    - 使用标准 HTTP + JSON 格式
    """
    
    def __init__(self, base_url: str = "http://localhost:30010"):
        """
        初始化 Blueprint Analyzer 客户端
        
        Args:
            base_url: Blueprint Analyzer HTTP 服务器基础URL
        """
        super().__init__(base_url)
        # 覆盖 subsystem 路径为 Blueprint Analyzer 插件的路径
        self.subsystem_path = "/Script/BlueprintAnalyzer.Default__BlueprintAnalyzerSubsystem"
        
        logger.info(f"BlueprintAnalyzerClient 初始化完成 (目标: {base_url}, Subsystem: {self.subsystem_path})")
    
    def extract_blueprint(self, asset_path: str) -> dict:
        """
        提取蓝图结构
        
        Args:
            asset_path: 蓝图资产路径，例如 "/Game/Blueprints/MyBlueprint"
            
        Returns:
            dict: 蓝图数据
                成功: {"status": "success", "data": {...}}
                失败: {"status": "error", "message": "..."}
        """
        return self.execute_tool_rpc("ExtractBlueprint", AssetPath=asset_path)
    
    def extract_widget_blueprint(self, asset_path: str) -> dict:
        """
        提取 Widget 蓝图（UMG）结构
        
        Args:
            asset_path: Widget 蓝图资产路径，例如 "/Game/UI/MainMenu"
            
        Returns:
            dict: Widget 数据
                成功: {"status": "success", "data": {...}}
                失败: {"status": "error", "message": "..."}
        """
        return self.execute_tool_rpc("ExtractWidgetBlueprint", AssetPath=asset_path)
    
    def get_editor_context(self) -> dict:
        """
        获取编辑器上下文信息
        
        Returns:
            dict: 编辑器上下文
                成功: {"status": "success", "data": {...}}
                失败: {"status": "error", "message": "..."}
        """
        return self.execute_tool_rpc("GetEditorContext")
    
    def list_assets(self, package_path: str, recursive: bool = True, class_filter: str = "") -> dict:
        """
        列出指定路径下的资产
        
        Args:
            package_path: 包路径，例如 "/Game/Blueprints"
            recursive: 是否递归列出子目录
            class_filter: 可选的类型过滤
            
        Returns:
            dict: 资产列表
                成功: {"status": "success", "data": [...]}
                失败: {"status": "error", "message": "..."}
        """
        return self.execute_tool_rpc("ListAssets", 
                                     PackagePath=package_path, 
                                     bRecursive=recursive, 
                                     ClassFilter=class_filter)
