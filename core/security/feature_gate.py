# -*- coding: utf-8 -*-

"""
Feature Gate 权限控制系统

实现基于 License 的功能分级：
- 免费工具（FREE_TOOLS）: 18 个只读工具，无需激活
- 付费工具（PRO_TOOLS）: 94 个创建/修改工具，需要激活

所有权限控制在 Python 层实现，不修改插件源码以保持开源合规。
"""

import logging
from typing import Dict, Set
from .license_manager import LicenseManager

logger = logging.getLogger(__name__)

# 免费工具集合（18 个只读工具）
FREE_TOOLS: Set[str] = {
    # Blueprint 提取
    "ExtractBlueprint",
    "ExtractActiveBlueprint",
    "GetActiveBlueprint",
    
    # UMG 提取
    "ExtractWidgetBlueprint",
    
    # Material 提取
    "ExtractMaterial",
    
    # 资产搜索和列表
    "SearchAssets",
    "ListAssets",
    
    # 编辑器上下文
    "GetEditorContext",
    
    # 其他提取工具
    "ExtractDataTable",
    "ExtractEnum",
    "ExtractStruct",
    "ExtractAnimBlueprint",
    "ExtractBehaviorTree",
    "ExtractBlackboard",
    "ExtractStateMachine",
    "ExtractAnimMontage",
    "ExtractAnimSequence",
    "ExtractSoundCue",
}

# 付费工具集合（94 个创建/修改工具）
PRO_TOOLS: Set[str] = {
    # Blueprint 创建和修改
    "CreateBlueprint",
    "ModifyBlueprintMembers",
    "AddBlueprintVariable",
    "AddBlueprintFunction",
    "ModifyBlueprintGraph",
    "RemoveBlueprintVariable",
    "RemoveBlueprintFunction",
    "RenameBlueprintVariable",
    "RenameBlueprintFunction",
    "SetBlueprintVariableValue",
    "AddBlueprintNode",
    "RemoveBlueprintNode",
    "ConnectBlueprintNodes",
    "DisconnectBlueprintNodes",
    
    # UMG 创建和修改
    "CreateWidgetBlueprint",
    "ModifyWidget",
    "AddWidgetToCanvas",
    "RemoveWidgetFromCanvas",
    "SetWidgetProperty",
    "AddWidgetBinding",
    "RemoveWidgetBinding",
    
    # 资产保存
    "SaveAssets",
    "SaveAllAssets",
    "SavePackage",
    
    # 导入工具
    "ImportTexture",
    "ImportMesh",
    "ImportSound",
    "ImportAnimation",
    "ImportMaterial",
    "ImportDataTable",
    
    # Material 创建和修改
    "CreateMaterial",
    "ModifyMaterial",
    "AddMaterialNode",
    "RemoveMaterialNode",
    "ConnectMaterialNodes",
    
    # 截图和验证
    "CaptureViewport",
    "CaptureWidget",
    "CaptureScreenshot",
    
    # PIE 控制
    "StartPIE",
    "StopPIE",
    "PausePIE",
    "ResumePIE",
    
    # LiveCoding
    "CompileLiveCode",
    "ReloadModule",
    
    # 资产创建
    "CreateAsset",
    "DeleteAsset",
    "RenameAsset",
    "DuplicateAsset",
    "MoveAsset",
    
    # DataTable 操作
    "CreateDataTable",
    "ModifyDataTable",
    "AddDataTableRow",
    "RemoveDataTableRow",
    "SetDataTableCell",
    
    # Enum 和 Struct 操作
    "CreateEnum",
    "ModifyEnum",
    "AddEnumValue",
    "RemoveEnumValue",
    "CreateStruct",
    "ModifyStruct",
    "AddStructMember",
    "RemoveStructMember",
    
    # 动画操作
    "CreateAnimBlueprint",
    "ModifyAnimBlueprint",
    "CreateAnimMontage",
    "ModifyAnimMontage",
    "CreateAnimSequence",
    "ModifyAnimSequence",
    
    # AI 操作
    "CreateBehaviorTree",
    "ModifyBehaviorTree",
    "CreateBlackboard",
    "ModifyBlackboard",
    "CreateStateMachine",
    "ModifyStateMachine",
    
    # Sound 操作
    "CreateSoundCue",
    "ModifySoundCue",
    "ImportSoundWave",
    
    # Level 操作
    "CreateLevel",
    "SaveLevel",
    "LoadLevel",
    "AddActorToLevel",
    "RemoveActorFromLevel",
    
    # Actor 操作
    "SpawnActor",
    "DestroyActor",
    "SetActorLocation",
    "SetActorRotation",
    "SetActorScale",
    "SetActorProperty",
}


class FeatureGate:
    """
    Feature Gate 权限控制系统
    
    基于 License 状态控制工具访问权限：
    - 免费工具：无需激活即可使用
    - 付费工具：需要激活 License（permanent 或 daily）
    - 非 UE 工具：跳过权限检查
    """
    
    def __init__(self, license_manager: LicenseManager):
        """
        初始化 Feature Gate
        
        Args:
            license_manager: License Manager 实例，用于检查激活状态
        """
        self.license_manager = license_manager
        logger.info(f"Feature Gate 初始化完成: 免费工具 {len(FREE_TOOLS)} 个, 付费工具 {len(PRO_TOOLS)} 个")

    def is_ue_tool(self, tool_name: str) -> bool:
        """
        判断是否为 UE 工具（需要权限检查）
        
        Args:
            tool_name: 工具名称
            
        Returns:
            True: 是 UE 工具（在 FREE_TOOLS 或 PRO_TOOLS 中）
            False: 不是 UE 工具
        """
        return tool_name in FREE_TOOLS or tool_name in PRO_TOOLS
    
    def check_tool_permission(self, tool_name: str) -> Dict[str, any]:
        """
        检查工具访问权限
        
        Args:
            tool_name: 工具名称（如 "CreateBlueprint"）
            
        Returns:
            权限检查结果字典:
            {
                "allowed": bool,      # 是否允许访问
                "locked": bool,       # 是否被锁定（付费功能未激活）
                "tier": str,          # 所需层级（"free" 或 "pro"）
                "message": str        # 提示信息（如果被锁定）
            }
        """
        # 非 UE 工具，跳过权限检查
        if not self.is_ue_tool(tool_name):
            return {
                "allowed": True,
                "locked": False,
                "tier": "none",
                "message": ""
            }
        
        # 免费工具，无需激活即可使用
        if tool_name in FREE_TOOLS:
            return {
                "allowed": True,
                "locked": False,
                "tier": "free",
                "message": ""
            }
        
        # 付费工具，检查 License 激活状态
        if tool_name in PRO_TOOLS:
            license_status = self.license_manager.get_license_status()
            
            # License 已激活（permanent 或 daily）
            if license_status in ("permanent", "daily"):
                return {
                    "allowed": True,
                    "locked": False,
                    "tier": "pro",
                    "message": ""
                }
            
            # License 未激活或已过期，返回友好的中文错误消息
            if license_status == "expired":
                message = (
                    f"工具 '{tool_name}' 是专业版功能，您的授权已过期。\n"
                    "请访问设置页面续费您的授权以继续使用专业版功能。"
                )
            else:
                message = (
                    f"工具 '{tool_name}' 是专业版功能，需要激活授权才能使用。\n"
                    "请访问设置页面激活您的授权，或使用免费版的只读功能。"
                )
            
            return {
                "allowed": False,
                "locked": True,
                "tier": "pro",
                "message": message
            }
        
        # 未知工具（理论上不应该到达这里）
        logger.warning(f"未知工具: {tool_name}")
        return {
            "allowed": False,
            "locked": False,
            "tier": "unknown",
            "message": f"未知工具: {tool_name}"
        }
