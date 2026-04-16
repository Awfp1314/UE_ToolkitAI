# -*- coding: utf-8 -*-

"""
Blueprint Tools UE5.4 客户端
用于与虚幻引擎 5.4 编辑器的 Blueprint Tools 插件进行通信
"""

from modules.ai_assistant.clients.ue_tool_client import UEToolClient
from core.logger import get_logger

logger = get_logger(__name__)


class BlueprintToolsUE54Client(UEToolClient):
    """
    Blueprint Tools UE5.4 HTTP 客户端
    
    继承自 UEToolClient，只需要修改 subsystem_path
    
    功能：
    - 与 UE 5.4 编辑器的 Blueprint Tools 插件通信
    - 支持核心蓝图操作（创建、变量管理、编译）
    - 使用标准 HTTP + JSON 格式
    """
    
    def __init__(self, base_url: str = "http://localhost:30010"):
        """
        初始化 Blueprint Tools UE5.4 客户端
        
        Args:
            base_url: Blueprint Tools HTTP 服务器基础URL
        """
        super().__init__(base_url)
        # 覆盖 subsystem 路径为 UE5.4 插件的路径
        self.subsystem_path = "/Script/BlueprintToolsUE54.Default__BlueprintToolsSubsystem"
        
        logger.info(f"BlueprintToolsUE54Client 初始化完成 (目标: {base_url}, Subsystem: {self.subsystem_path})")
