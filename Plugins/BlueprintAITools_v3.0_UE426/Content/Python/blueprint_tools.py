# -*- coding: utf-8 -*-

"""
BlueprintAITools - 只读模式
专注于蓝图分析和错误检测，100% 稳定
"""

import unreal
import json
import traceback

def get_current_blueprint_summary():
    """
    [AI 工具] 获取当前蓝图的完整信息
    
    返回：
    JSON 字符串，包含蓝图结构（节点、连接、变量等）
    """
    
    try:
        # 获取当前打开的蓝图
        blueprint = unreal.BlueprintAIToolsLibrary.get_current_open_blueprint()
        
        if not blueprint:
            return json.dumps({
                "error": "NoBlueprint", 
                "message": "请在 UE 编辑器中打开一个蓝图"
            })
        
        unreal.log("[BPTools] 导出蓝图: {}".format(blueprint.get_name()))

        # 导出简化版蓝图（节省 token）
        json_str = unreal.BlueprintAIToolsLibrary.export_blueprint_summary(blueprint, True)
        
        unreal.log("[BPTools] 导出成功，JSON 大小: {} 字节 (~{} tokens)".format(len(json_str), len(json_str)//3))
        
        return json_str

    except Exception as e:
        err_msg = "导出蓝图失败: {}".format(e)
        unreal.log_error("[BPTools] {}".format(err_msg))
        unreal.log_error("[BPTools] 详细错误: {}".format(traceback.format_exc()))
        return json.dumps({"error": "ExportBlueprintError", "message": err_msg})


def query_available_nodes(category="", node_name=""):
    """
    [AI 工具] 智能查询蓝图节点信息（超级节省 token）
    
    参数：
    - category (可选): 查询整个分类（如 "ai_behavior_tree"）
    - node_name (可选): 只查询单个节点（如 "Branch", "PrintString"）
    
    优先级：
    1. 如果 node_name 存在，只返回该节点信息（~100 tokens）
    2. 如果 category 存在，返回该分类（~1,000-2,500 tokens）
    3. 都不存在，返回分类索引（~300 tokens）
    
    返回：
    JSON 字符串
    """
    try:
        # 读取完整字典
        json_str = unreal.BlueprintAIToolsLibrary.get_available_node_types()
        data = json.loads(json_str)
        
        # 优先级 1：查询单个节点（最省 token）
        if node_name:
            # 在所有分类中搜索该节点
            for cat_key, cat_data in data.get("categories", {}).items():
                for node in cat_data.get("nodes", []):
                    # 支持多种匹配方式
                    display_name = node.get("display_name", "")
                    class_name = node.get("class", "")
                    func_name = node.get("function_name", "")
                    
                    # 模糊匹配（不区分大小写）
                    if (node_name.lower() in display_name.lower() or
                        node_name.lower() in class_name.lower() or
                        node_name.lower() in func_name.lower()):
                        
                        result = {
                            "query": node_name,
                            "found": True,
                            "category": cat_key,
                            "node": node
                        }
                        result_json = json.dumps(result, ensure_ascii=False)
                        unreal.log("[BPTools] 返回节点 [{}] 详情，大小: {} 字节".format(node_name, len(result_json)))
                        return result_json
            
            # 节点未找到
            return json.dumps({
                "query": node_name,
                "found": False,
                "message": "未找到节点 '{}'，可能 AI 已经知道这个节点，或者节点名拼写错误".format(node_name),
                "suggestion": "尝试查询分类索引或使用更通用的名称"
            })
        
        # 优先级 2：查询整个分类
        if category:
            if category in data.get("categories", {}):
                category_detail = {
                    "category": category,
                    "data": data["categories"][category]
                }
                result = json.dumps(category_detail, ensure_ascii=False)
                unreal.log("[BPTools] 返回分类 [{}] 详情，大小: {} 字节".format(category, len(result)))
                return result
            
            # 特殊查询
            if category == "error_patterns":
                result = json.dumps({"common_error_patterns": data.get("common_error_patterns", {})}, ensure_ascii=False)
                return result
            
            if category == "best_practices":
                result = json.dumps({"best_practices": data.get("best_practices", {})}, ensure_ascii=False)
                return result
            
            if category == "feature_mapping":
                result = json.dumps({"feature_to_nodes_mapping": data.get("feature_to_nodes_mapping", {})}, ensure_ascii=False)
                return result
            
            # 分类不存在
            return json.dumps({
                "error": "CategoryNotFound",
                "message": "分类 '{}' 不存在".format(category),
                "available_categories": list(data.get("categories", {}).keys())
            })
        
        # 优先级 3：返回分类索引
        categories_summary = {
            "version": data.get("version"),
            "description": "节点分类索引 - 使用 category 或 node_name 参数查询详细信息",
            "categories": {}
        }
        
        for cat_key, cat_data in data.get("categories", {}).items():
            categories_summary["categories"][cat_key] = {
                "name": cat_data.get("name"),
                "description": cat_data.get("description"),
                "node_count": len(cat_data.get("nodes", []))
            }
        
        result = json.dumps(categories_summary, ensure_ascii=False)
        unreal.log("[BPTools] 返回分类索引，大小: {} 字节".format(len(result)))
        return result
    
    except Exception as e:
        err_msg = "获取节点字典失败: {}".format(e)
        unreal.log_error("[BPTools] {}".format(err_msg))
        return json.dumps({"error": "GetNodeTypesError", "message": err_msg})


def validate_blueprint():
    """
    [AI 工具] 验证当前蓝图的连接和逻辑错误
    
    返回：
    JSON 字符串，包含错误和警告列表
    """
    try:
        blueprint = unreal.BlueprintAIToolsLibrary.get_current_open_blueprint()
        
        if not blueprint:
            return json.dumps({
                "error": "NoBlueprint",
                "message": "请在 UE 编辑器中打开一个蓝图"
            })
        
        unreal.log("[BPTools] 验证蓝图: {}".format(blueprint.get_name()))
        
        json_str = unreal.BlueprintAIToolsLibrary.validate_blueprint(blueprint)
        
        # 显示摘要
        result = json.loads(json_str)
        error_count = result.get("error_count", 0)
        warning_count = result.get("warning_count", 0)
        
        unreal.log("[BPTools] 验证完成：{} 个错误，{} 个警告".format(error_count, warning_count))
        
        return json_str
    except Exception as e:
        err_msg = "验证蓝图失败: {}".format(e)
        unreal.log_error("[BPTools] {}".format(err_msg))
        return json.dumps({"error": "ValidateBlueprintError", "message": err_msg})


def get_selected_nodes():
    """
    [AI 工具] 获取蓝图编辑器中选中的节点（实验性）
    
    返回：
    JSON 字符串，包含选中节点的 GUID、标题和类名
    """
    try:
        blueprint = unreal.BlueprintAIToolsLibrary.get_current_open_blueprint()
        
        if not blueprint:
            return json.dumps({
                "error": "NoBlueprint",
                "message": "请在 UE 编辑器中打开一个蓝图"
            })
        
        unreal.log("[BPTools] 获取选中节点: {}".format(blueprint.get_name()))
        
        json_str = unreal.BlueprintAIToolsLibrary.get_selected_nodes(blueprint)
        
        # 显示摘要
        result = json.loads(json_str)
        count = result.get("count", 0)
        
        unreal.log("[BPTools] 找到 {} 个选中节点".format(count))
        
        return json_str
    except Exception as e:
        err_msg = "获取选中节点失败: {}".format(e)
        unreal.log_error("[BPTools] {}".format(err_msg))
        return json.dumps({"error": "GetSelectedNodesError", "message": err_msg})


def apply_blueprint_changes(changes_json=""):
    """
    [已禁用] 蓝图修改功能
    
    当前版本为只读模式，不支持修改蓝图。
    AI 只能分析蓝图并给出修改建议，需要用户手动在 UE 中修改。
    """
    return json.dumps({
        "status": "error",
        "message": "蓝图修改功能在只读模式下不可用。当前版本专注于稳定的蓝图分析和错误检测。如需修改，请在 UE 编辑器中手动操作。"
    })


if __name__ == '__main__':
    try:
        unreal.log("=" * 80)
        unreal.log("BlueprintAITools 测试 - 只读模式")
        unreal.log("=" * 80)
        result = get_current_blueprint_summary()
        unreal.log(result[:500] + "...")
        unreal.log("=" * 80)
    except Exception as e:
        unreal.log_error("测试失败: {}\n{}".format(e, traceback.format_exc()))
