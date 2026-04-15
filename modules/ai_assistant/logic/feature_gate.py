# -*- coding: utf-8 -*-
"""
功能权限控制
根据 License 状态控制 UE 工具的访问权限
"""

from enum import Enum
from typing import Set
from core.logger import get_logger

logger = get_logger(__name__)


class FeatureTier(Enum):
    """功能等级"""
    FREE = "free"
    PRO = "pro"


class UEFeatureGate:
    """UE 功能权限控制器"""
    
    # 免费功能列表（只读操作）
    FREE_TOOLS: Set[str] = {
        # 提取/读取功能
        "ExtractBlueprint",
        "ExtractWidgetBlueprint",
        "ExtractMaterial",
        "ExtractMaterialInstance",
        "ExtractDataAsset",
        "ExtractDataTable",
        "ExtractCurve",
        "ExtractStateTree",
        "ExtractBehaviorTree",
        "ExtractBlackboard",
        "ExtractAnimSequence",
        "ExtractAnimMontage",
        "ExtractBlendSpace",
        "ExtractUserDefinedStruct",
        "ExtractUserDefinedEnum",
        
        # 搜索/列表功能
        "SearchAssets",
        "ListAssets",
        
        # 编辑器上下文（只读）
        "GetEditorContext",
        "GetProjectAutomationContext",
    }
    
    # 付费功能列表（创建/修改操作）
    PRO_TOOLS: Set[str] = {
        # Blueprint 创建/修改
        "CreateBlueprint",
        "ModifyBlueprintMembers",
        "ModifyBlueprintGraphs",
        
        # Widget 创建/修改
        "CreateWidgetBlueprint",
        "BuildWidgetTree",
        "ModifyWidget",
        "ModifyWidgetBlueprintStructure",
        "CompileWidgetBlueprint",
        "CreateWidgetAnimation",
        "ModifyWidgetAnimation",
        
        # Material 创建/修改
        "CreateMaterial",
        "ModifyMaterial",
        "CreateMaterialFunction",
        "ModifyMaterialFunction",
        "CreateMaterialInstance",
        "ModifyMaterialInstance",
        "CompileMaterialAsset",
        
        # 数据资产创建/修改
        "CreateDataAsset",
        "ModifyDataAsset",
        "CreateDataTable",
        "ModifyDataTable",
        "CreateCurve",
        "ModifyCurve",
        "CreateCurveTable",
        "ModifyCurveTable",
        
        # AI 资产创建/修改
        "CreateStateTree",
        "ModifyStateTree",
        "CreateBehaviorTree",
        "ModifyBehaviorTree",
        "CreateBlackboard",
        "ModifyBlackboard",
        
        # 动画资产创建/修改
        "CreateAnimSequence",
        "ModifyAnimSequence",
        "CreateAnimMontage",
        "ModifyAnimMontage",
        "CreateBlendSpace",
        "ModifyBlendSpace",
        
        # 结构体/枚举创建/修改
        "CreateUserDefinedStruct",
        "ModifyUserDefinedStruct",
        "CreateUserDefinedEnum",
        "ModifyUserDefinedEnum",
        
        # 输入系统
        "CreateInputAction",
        "ModifyInputAction",
        "CreateInputMappingContext",
        "ModifyInputMappingContext",
        
        # 保存操作
        "SaveAssets",
        
        # 导入功能
        "ImportAssets",
        "ReimportAssets",
        "ImportTextures",
        "ImportMeshes",
        "ImportFonts",
        
        # 可视化验证
        "CaptureWidgetPreview",
        "CaptureEditorScreenshot",
        "CaptureRuntimeScreenshot",
        "CaptureWidgetMotionCheckpoints",
        "CompareCaptureToReference",
        
        # 项目控制
        "StartPIE",
        "StopPIE",
        "RelaunchPIE",
        "TriggerLiveCoding",
        "RestartEditor",
        
        # 调试功能
        "StartStateTreeDebugger",
        "StopStateTreeDebugger",
        "ReadStateTreeDebugger",
    }
    
    def __init__(self, license_manager):
        """
        初始化功能权限控制器
        
        Args:
            license_manager: License 管理器实例
        """
        self.license_manager = license_manager
        self.logger = logger
    
    def is_tool_allowed(self, tool_name: str) -> bool:
        """
        检查工具是否允许使用
        
        Args:
            tool_name: 工具名称
            
        Returns:
            bool: 是否允许使用
        """
        # 免费工具始终允许
        if tool_name in self.FREE_TOOLS:
            return True
        
        # 付费工具需要检查 License
        if tool_name in self.PRO_TOOLS:
            return self.license_manager.is_activated()
        
        # 未知工具默认拒绝
        self.logger.warning(f"未知工具: {tool_name}")
        return False
    
    def get_tool_tier(self, tool_name: str) -> FeatureTier:
        """
        获取工具的功能等级
        
        Args:
            tool_name: 工具名称
            
        Returns:
            FeatureTier: 功能等级
        """
        if tool_name in self.FREE_TOOLS:
            return FeatureTier.FREE
        elif tool_name in self.PRO_TOOLS:
            return FeatureTier.PRO
        else:
            return FeatureTier.PRO  # 默认为付费功能
    
    def get_blocked_reason(self, tool_name: str) -> str:
        """
        获取工具被阻止的原因
        
        Args:
            tool_name: 工具名称
            
        Returns:
            str: 阻止原因
        """
        tier = self.get_tool_tier(tool_name)
        
        if tier == FeatureTier.PRO:
            return (
                f"'{tool_name}' 是付费功能，需要激活 Pro 版本才能使用。\n"
                f"免费版只支持资产的读取和分析功能。\n"
                f"请联系开发者获取激活码。"
            )
        
        return "未知错误"
    
    def filter_tools(self, all_tools: list) -> dict:
        """
        根据 License 状态过滤工具列表
        
        Args:
            all_tools: 所有工具列表
            
        Returns:
            dict: {
                "available": [...],  # 可用工具
                "locked": [...]      # 锁定工具
            }
        """
        available = []
        locked = []
        
        for tool in all_tools:
            tool_name = tool.get("name", "")
            if self.is_tool_allowed(tool_name):
                available.append(tool)
            else:
                # 添加锁定标记
                locked_tool = tool.copy()
                locked_tool["locked"] = True
                locked_tool["tier"] = "pro"
                locked.append(locked_tool)
        
        return {
            "available": available,
            "locked": locked
        }
