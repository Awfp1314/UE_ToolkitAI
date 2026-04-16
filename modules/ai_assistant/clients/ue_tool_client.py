# -*- coding: utf-8 -*-

"""
UE工具客户端
用于与虚幻引擎编辑器的 Blueprint Extractor 插件进行通信
"""

import requests
import time
from typing import Optional, Dict, Any
from core.logger import get_logger

logger = get_logger(__name__)


class UEToolClient:
    """
    虚幻引擎工具 HTTP 客户端
    
    功能：
    - 与UE编辑器的 Blueprint Extractor 插件通信
    - 使用标准 HTTP + JSON 格式
    - 支持调用 BlueprintExtractorSubsystem 函数
    - 实现重试机制（最多3次，指数退避）
    """
    
    MAX_RETRIES = 3
    RETRY_DELAYS = [1, 2, 4]  # 指数退避：1秒, 2秒, 4秒
    
    def __init__(self, base_url: str = "http://localhost:30010"):
        """
        初始化UE工具客户端
        
        Args:
            base_url: Blueprint Extractor HTTP 服务器基础URL
        """
        self.base_url = base_url.rstrip('/')
        self.subsystem_path = "/Script/BlueprintToolsUE54.Default__BlueprintToolsSubsystem"
        self._connected = False
        
        logger.info(f"UEToolClient 初始化完成 (目标: {base_url}, Subsystem: {self.subsystem_path})")
    
    def verify_connection(self) -> bool:
        """
        验证与 Blueprint Extractor 插件的连接
        验证 Subsystem 是否可访问
        
        Returns:
            bool: 连接是否成功且 Subsystem 可访问
        """
        try:
            # 尝试调用一个简单的测试方法来验证 Subsystem 可访问性（使用 PUT 方法）
            response = requests.put(
                f"{self.base_url}/remote/object/call",
                json={
                    "objectPath": self.subsystem_path,
                    "functionName": "GetEditorContext",
                    "parameters": {},
                    "generateTransaction": False
                },
                timeout=5.0
            )
            
            if response.status_code == 200:
                self._connected = True
                logger.info(f"[UE-HTTP] 成功连接到 Blueprint Extractor (Subsystem: {self.subsystem_path})")
                return True
            else:
                self._connected = False
                logger.warning(f"[UE-HTTP] Subsystem 不可访问: HTTP {response.status_code}")
                return False
            
        except requests.exceptions.Timeout:
            logger.warning(f"[UE-HTTP] 连接超时: {self.base_url}")
            self._connected = False
            return False
        except requests.exceptions.ConnectionError:
            logger.warning(f"[UE-HTTP] 连接被拒绝: {self.base_url} (UE编辑器可能未运行)")
            self._connected = False
            return False
        except Exception as e:
            logger.error(f"[UE-HTTP] 连接验证失败: {e}", exc_info=True)
            self._connected = False
            return False
    
    def _check_connection(self) -> bool:
        """
        检查与UE服务器的连接（内部使用）
        
        Returns:
            bool: 连接是否成功
        """
        return self.verify_connection()
    
    def _retry_connection(self) -> bool:
        """
        使用重试机制尝试连接
        最多重试 3 次，使用指数退避（1s, 2s, 4s）
        
        Returns:
            bool: 连接是否成功
        """
        for attempt in range(self.MAX_RETRIES):
            logger.info(f"[UE-HTTP] 连接尝试 {attempt + 1}/{self.MAX_RETRIES}...")
            
            if self.verify_connection():
                return True
            
            # 如果不是最后一次尝试，等待后重试
            if attempt < self.MAX_RETRIES - 1:
                delay = self.RETRY_DELAYS[attempt]
                logger.info(f"[UE-HTTP] 等待 {delay} 秒后重试...")
                time.sleep(delay)
        
        logger.error(f"[UE-HTTP] 连接失败，已重试 {self.MAX_RETRIES} 次")
        return False
    
    def execute_tool_rpc(self, tool_name: str, **kwargs) -> dict:
        """
        执行UE工具的RPC调用（供ToolRegistry使用）
        
        Args:
            tool_name: 工具名称 (如 "ExtractBlueprint")
            **kwargs: 工具参数
            
        Returns:
            dict: 响应
                成功: {"status": "success", "data": {...}}
                失败: {"status": "error", "message": "..."}
        """
        try:
            # 1. 检查连接状态
            if not self._connected:
                logger.info("[UE-HTTP] 尝试连接到UE编辑器...")
                if not self._retry_connection():
                    return {
                        "status": "error",
                        "message": f"无法连接到虚幻引擎编辑器（已重试 {self.MAX_RETRIES} 次）。\n\n请确保：\n1. UE编辑器正在运行\n2. Blueprint Extractor 插件已启用\n3. HTTP 服务器正在监听 {self.base_url}\n\n如果问题持续存在，请检查插件配置。"
                    }
            
            # 2. 构建请求
            # 调用 BlueprintExtractor Subsystem 的函数
            
            request_data = {
                "objectPath": self.subsystem_path,
                "functionName": tool_name,
                "parameters": kwargs,
                "generateTransaction": False
            }
            
            logger.info(f"[UE-HTTP] 执行工具: {tool_name}")
            logger.debug(f"[UE-HTTP] 请求参数: {kwargs}")
            
            # 3. 发送请求（使用 PUT 方法，不是 POST）
            response = requests.put(
                f"{self.base_url}/remote/object/call",
                json=request_data,
                timeout=30.0
            )
            
            if response.status_code != 200:
                self._connected = False
                return {
                    "status": "error",
                    "message": f"HTTP 请求失败: {response.status_code} - {response.text}"
                }
            
            # 4. 解析响应
            result = response.json()
            
            logger.info(f"[UE-HTTP] 工具执行完成: {tool_name}")
            return result
            
        except requests.exceptions.Timeout:
            logger.error(f"[UE-HTTP] 请求超时: {tool_name}")
            self._connected = False
            return {
                "status": "error",
                "message": f"请求超时。工具: {tool_name}"
            }
        except Exception as e:
            logger.error(f"[UE-HTTP] RPC调用异常: {e}", exc_info=True)
            self._connected = False
            return {
                "status": "error",
                "message": f"RPC调用异常: {str(e)}"
            }
    
    def close(self):
        """关闭连接（HTTP 无需显式关闭）"""
        self._connected = False
        logger.info("[UE-HTTP] 客户端已关闭")
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._connected
    
    def test_connection(self) -> bool:
        """测试连接是否正常
        
        Returns:
            bool: 连接是否正常
        """
        return self._check_connection()


