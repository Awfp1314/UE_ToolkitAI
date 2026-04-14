// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Engine/Blueprint.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"
#include "EdGraph/EdGraphPin.h"
#include "Dom/JsonObject.h"
#include "BlueprintAIToolsLibrary.generated.h"

/**
 * Blueprint AI Tools Library - 只读模式
 * 提供蓝图读取和分析的 C++ API，专注于稳定性
 */
UCLASS()
class BLUEPRINTAITOOLS_API UBlueprintAIToolsLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	// ========== 蓝图读取接口 ==========
	
	/**
	 * 获取当前在编辑器中打开的蓝图
	 * @return 当前打开的蓝图，如果没有则返回 nullptr
	 */
	UFUNCTION(BlueprintCallable, Category = "Blueprint AI Tools")
	static UBlueprint* GetCurrentOpenBlueprint();

	/**
	 * 导出蓝图为简化的 JSON 格式（推荐，节省 40-50% token）
	 * @param Blueprint 要导出的蓝图
	 * @param bIncludePinDetails 是否包含 Pin 详细信息
	 * @return JSON 字符串
	 */
	UFUNCTION(BlueprintCallable, Category = "Blueprint AI Tools")
	static FString ExportBlueprintSummary(UBlueprint* Blueprint, bool bIncludePinDetails = true);

	/**
	 * 导出蓝图为完整 JSON 格式（调试用）
	 * @param Blueprint 要导出的蓝图
	 * @return JSON 字符串
	 */
	UFUNCTION(BlueprintCallable, Category = "Blueprint AI Tools")
	static FString ExportBlueprintToJson(UBlueprint* Blueprint);

	/**
	 * 导出单个图表为 JSON
	 * @param Graph 要导出的图表
	 * @return JSON 字符串
	 */
	UFUNCTION(BlueprintCallable, Category = "Blueprint AI Tools")
	static FString ExportGraphToJson(UEdGraph* Graph);

	/**
	 * 只导出 EventGraph（节省 token）
	 * @param Blueprint 蓝图对象
	 * @param bIncludePinDetails 是否包含 Pin 详细信息
	 * @return JSON 字符串
	 */
	UFUNCTION(BlueprintCallable, Category = "Blueprint AI Tools")
	static FString ExportEventGraphOnly(UBlueprint* Blueprint, bool bIncludePinDetails = true);

	// ========== 辅助工具 ==========

	/**
	 * 获取可用的蓝图节点类型字典
	 * @return JSON 字符串，包含常用节点的分类和说明
	 */
	UFUNCTION(BlueprintCallable, Category = "Blueprint AI Tools")
	static FString GetAvailableNodeTypes();

	/**
	 * 验证蓝图的连接错误
	 * @param Blueprint 要验证的蓝图
	 * @return JSON 字符串，包含错误和警告列表
	 */
	UFUNCTION(BlueprintCallable, Category = "Blueprint AI Tools")
	static FString ValidateBlueprint(UBlueprint* Blueprint);

	/**
	 * 获取蓝图编辑器中选中的节点（实验性）
	 * @param Blueprint 蓝图对象
	 * @return JSON 字符串，包含选中节点的 GUID 列表
	 */
	UFUNCTION(BlueprintCallable, Category = "Blueprint AI Tools")
	static FString GetSelectedNodes(UBlueprint* Blueprint);

private:
	/**
	 * 导出单个节点为 JSON 对象（完整版）
	 */
	static TSharedPtr<FJsonObject> ExportNodeToJson(UEdGraphNode* Node);

	/**
	 * 导出单个节点为简化的 JSON 对象（节省 token）
	 */
	static TSharedPtr<FJsonObject> ExportNodeSummary(UEdGraphNode* Node, bool bIncludePinDetails);
	
	/**
	 * 导出 Pin 信息为 JSON 对象
	 */
	static TSharedPtr<FJsonObject> ExportPinToJson(UEdGraphPin* Pin);

	/**
	 * 获取 Pin 类型的字符串表示
	 */
	static FString GetPinTypeString(const FEdGraphPinType& PinType);
};
