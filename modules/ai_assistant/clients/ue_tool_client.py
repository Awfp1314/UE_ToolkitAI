# -*- coding: utf-8 -*-

"""
UE工具客户端
用于与虚幻引擎编辑器的 Remote Control API 进行通信
"""

import requests
from typing import Optional, Dict, Any
from core.logger import get_logger

logger = get_logger(__name__)


class UEToolClient:
    """
    虚幻引擎工具 HTTP 客户端
    
    功能：
    - 与UE编辑器的 Remote Control API 通信
    - 使用标准 HTTP + JSON 格式
    - 支持调用 EditorSubsystem 函数
    """
    
    def __init__(self, base_url: str = "http://127.0.0.1:30010"):
        """
        初始化UE工具客户端
        
        Args:
            base_url: Remote Control API 基础URL
        """
        self.base_url = base_url.rstrip('/')
        self._connected = False
        
        logger.info(f"UEToolClient 初始化完成 (目标: {base_url})")
    
    def _check_connection(self) -> bool:
        """
        检查与UE服务器的连接
        
        Returns:
            bool: 连接是否成功
        """
        try:
            response = requests.get(f"{self.base_url}/remote/info", timeout=2.0)
            if response.status_code == 200:
                data = response.json()
                if 'HttpRoutes' in data or 'ActivePreset' in data:
                    self._connected = True
                    logger.info(f"[UE-HTTP] 成功连接到 {self.base_url}")
                    return True
            
            self._connected = False
            return False
            
        except requests.exceptions.Timeout:
            logger.warning(f"[UE-HTTP] 连接超时: {self.base_url}")
            self._connected = False
            return False
        except requests.exceptions.ConnectionError:
            logger.warning(f"[UE-HTTP] 连接被拒绝: {self.base_url} (UE服务器可能未启动)")
            self._connected = False
            return False
        except Exception as e:
            logger.error(f"[UE-HTTP] 连接失败: {e}", exc_info=True)
            self._connected = False
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
                logger.info("[UE-HTTP] 尝试连接到UE服务器...")
                if not self._check_connection():
                    return {
                        "status": "error",
                        "message": f"无法连接到UE编辑器 ({self.base_url})。请确保UE编辑器已启动并启用了 Remote Control Web Server。"
                    }
            
            # 2. 构建请求
            # 调用 BlueprintToAISubsystem 的函数
            subsystem_path = "/Script/BlueprintToAI.Default__BlueprintToAISubsystem"
            
            request_data = {
                "objectPath": subsystem_path,
                "functionName": tool_name,
                "parameters": kwargs
            }
            
            logger.info(f"[UE-HTTP] 执行工具: {tool_name}")
            logger.debug(f"[UE-HTTP] 请求参数: {kwargs}")
            
            # 3. 发送请求
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


