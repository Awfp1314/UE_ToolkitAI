// Copyright Epic Games, Inc. All Rights Reserved.

#include "BlueprintAIToolsLibrary.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "K2Node_CallFunction.h"
#include "K2Node_Event.h"
#include "EdGraphSchema_K2.h"
#include "JsonObjectConverter.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "Subsystems/AssetEditorSubsystem.h"
#include "Editor.h"
#include "Toolkits/AssetEditorToolkit.h"
#include "UnrealEdGlobals.h"
#include "Editor/UnrealEdEngine.h"
#include "Editor/UnrealEdTypes.h"
#include "Selection.h"  // 修复：正确的 USelection 头文件路径

// ========== 蓝图读取接口实现 ==========

// 获取当前打开的蓝图
UBlueprint* UBlueprintAIToolsLibrary::GetCurrentOpenBlueprint()
{
	if (!GEditor)
	{
		return nullptr;
	}

	UAssetEditorSubsystem* AssetEditorSubsystem = GEditor->GetEditorSubsystem<UAssetEditorSubsystem>();
	if (!AssetEditorSubsystem)
	{
		return nullptr;
	}

	TArray<UObject*> EditedAssets = AssetEditorSubsystem->GetAllEditedAssets();

	TArray<UBlueprint*> OpenBlueprints;
	for (UObject* Asset : EditedAssets)
	{
		if (UBlueprint* Blueprint = Cast<UBlueprint>(Asset))
		{
			OpenBlueprints.Add(Blueprint);
		}
	}

	if (OpenBlueprints.Num() == 0)
	{
		return nullptr;
	}

	return OpenBlueprints[0];
}

// 导出蓝图为简化的 JSON
FString UBlueprintAIToolsLibrary::ExportBlueprintSummary(UBlueprint* Blueprint, bool bIncludePinDetails)
{
	if (!Blueprint)
	{
		return TEXT("{\"error\": \"Invalid Blueprint\"}");
	}

	TSharedPtr<FJsonObject> RootObject = MakeShareable(new FJsonObject);

	RootObject->SetStringField(TEXT("name"), Blueprint->GetName());
	RootObject->SetStringField(TEXT("parent_class"), 
		Blueprint->ParentClass ? Blueprint->ParentClass->GetName() : TEXT("None"));
	RootObject->SetStringField(TEXT("blueprint_type"), 
		Blueprint->BlueprintType == BPTYPE_Normal ? TEXT("Normal") :
		Blueprint->BlueprintType == BPTYPE_FunctionLibrary ? TEXT("FunctionLibrary") :
		TEXT("Other"));

	TArray<TSharedPtr<FJsonValue>> GraphsArray;
	TArray<UEdGraph*> AllGraphs;
	Blueprint->GetAllGraphs(AllGraphs);

	for (UEdGraph* Graph : AllGraphs)
	{
		if (Graph)
		{
			TSharedPtr<FJsonObject> GraphObject = MakeShareable(new FJsonObject);
			GraphObject->SetStringField(TEXT("name"), Graph->GetName());
			GraphObject->SetNumberField(TEXT("node_count"), Graph->Nodes.Num());
			
			TArray<TSharedPtr<FJsonValue>> NodesArray;
			for (UEdGraphNode* Node : Graph->Nodes)
			{
				if (Node)
				{
					TSharedPtr<FJsonObject> NodeSummary = ExportNodeSummary(Node, bIncludePinDetails);
					if (NodeSummary.IsValid())
					{
						NodesArray.Add(MakeShareable(new FJsonValueObject(NodeSummary)));
					}
				}
			}
			GraphObject->SetArrayField(TEXT("nodes"), NodesArray);
			
			GraphsArray.Add(MakeShareable(new FJsonValueObject(GraphObject)));
		}
	}
	RootObject->SetArrayField(TEXT("graphs"), GraphsArray);

	TArray<TSharedPtr<FJsonValue>> VariablesArray;
	for (const FBPVariableDescription& Variable : Blueprint->NewVariables)
	{
		TSharedPtr<FJsonObject> VarObject = MakeShareable(new FJsonObject);
		VarObject->SetStringField(TEXT("name"), Variable.VarName.ToString());
		VarObject->SetStringField(TEXT("type"), GetPinTypeString(Variable.VarType));
		
		VariablesArray.Add(MakeShareable(new FJsonValueObject(VarObject)));
	}
	RootObject->SetArrayField(TEXT("variables"), VariablesArray);

	FString OutputString;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
	FJsonSerializer::Serialize(RootObject.ToSharedRef(), Writer);

	return OutputString;
}

// 导出蓝图为完整 JSON
FString UBlueprintAIToolsLibrary::ExportBlueprintToJson(UBlueprint* Blueprint)
{
	if (!Blueprint)
	{
		return TEXT("{\"error\": \"Invalid Blueprint\"}");
	}

	TSharedPtr<FJsonObject> RootObject = MakeShareable(new FJsonObject);

	RootObject->SetStringField(TEXT("name"), Blueprint->GetName());
	RootObject->SetStringField(TEXT("path"), Blueprint->GetPathName());
	
	if (Blueprint->ParentClass)
	{
		RootObject->SetStringField(TEXT("parent_class"), Blueprint->ParentClass->GetName());
	}

	RootObject->SetStringField(TEXT("blueprint_type"), 
		Blueprint->BlueprintType == BPTYPE_Normal ? TEXT("Normal") :
		Blueprint->BlueprintType == BPTYPE_FunctionLibrary ? TEXT("FunctionLibrary") :
		TEXT("Other"));

	TArray<TSharedPtr<FJsonValue>> GraphsArray;
	TArray<UEdGraph*> AllGraphs;
	Blueprint->GetAllGraphs(AllGraphs);

	for (UEdGraph* Graph : AllGraphs)
	{
		if (Graph)
		{
			TSharedPtr<FJsonObject> GraphObject = MakeShareable(new FJsonObject);
			GraphObject->SetStringField(TEXT("name"), Graph->GetName());
			GraphObject->SetStringField(TEXT("graph_type"), Graph->GetSchema()->GetClass()->GetName());
			
			FString GraphJson = ExportGraphToJson(Graph);
			TSharedPtr<FJsonObject> GraphData;
			TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(GraphJson);
			if (FJsonSerializer::Deserialize(Reader, GraphData))
			{
				GraphObject->SetObjectField(TEXT("data"), GraphData);
			}

			GraphsArray.Add(MakeShareable(new FJsonValueObject(GraphObject)));
		}
	}
	RootObject->SetArrayField(TEXT("graphs"), GraphsArray);

	TArray<TSharedPtr<FJsonValue>> VariablesArray;
	for (const FBPVariableDescription& Variable : Blueprint->NewVariables)
	{
		TSharedPtr<FJsonObject> VarObject = MakeShareable(new FJsonObject);
		VarObject->SetStringField(TEXT("name"), Variable.VarName.ToString());
		VarObject->SetStringField(TEXT("type"), GetPinTypeString(Variable.VarType));
		VarObject->SetStringField(TEXT("category"), Variable.Category.ToString());
		
		VariablesArray.Add(MakeShareable(new FJsonValueObject(VarObject)));
	}
	RootObject->SetArrayField(TEXT("variables"), VariablesArray);

	FString OutputString;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
	FJsonSerializer::Serialize(RootObject.ToSharedRef(), Writer);

	return OutputString;
}

// 导出图表为 JSON
FString UBlueprintAIToolsLibrary::ExportGraphToJson(UEdGraph* Graph)
{
	if (!Graph)
	{
		return TEXT("{\"error\": \"Invalid Graph\"}");
	}

	TSharedPtr<FJsonObject> RootObject = MakeShareable(new FJsonObject);

	RootObject->SetStringField(TEXT("name"), Graph->GetName());
	RootObject->SetNumberField(TEXT("node_count"), Graph->Nodes.Num());

	TArray<TSharedPtr<FJsonValue>> NodesArray;
	for (UEdGraphNode* Node : Graph->Nodes)
	{
		if (Node)
		{
			TSharedPtr<FJsonObject> NodeObject = ExportNodeToJson(Node);
			if (NodeObject.IsValid())
			{
				NodesArray.Add(MakeShareable(new FJsonValueObject(NodeObject)));
			}
		}
	}
	RootObject->SetArrayField(TEXT("nodes"), NodesArray);

	FString OutputString;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
	FJsonSerializer::Serialize(RootObject.ToSharedRef(), Writer);

	return OutputString;
}

// 只导出 EventGraph
FString UBlueprintAIToolsLibrary::ExportEventGraphOnly(UBlueprint* Blueprint, bool bIncludePinDetails)
{
	if (!Blueprint)
	{
		Blueprint = GetCurrentOpenBlueprint();
	}

	if (!Blueprint)
	{
		return TEXT("{\"error\": \"Invalid Blueprint\"}");
	}

	UEdGraph* EventGraph = nullptr;
	TArray<UEdGraph*> AllGraphs;
	Blueprint->GetAllGraphs(AllGraphs);

	for (UEdGraph* Graph : AllGraphs)
	{
		if (Graph && Graph->GetName() == TEXT("EventGraph"))
		{
			EventGraph = Graph;
			break;
		}
	}

	if (!EventGraph)
	{
		return TEXT("{\"error\": \"EventGraphNotFound\"}");
	}

	TSharedPtr<FJsonObject> RootObject = MakeShareable(new FJsonObject);
	
	RootObject->SetStringField(TEXT("blueprint_name"), Blueprint->GetName());
	RootObject->SetStringField(TEXT("graph_name"), EventGraph->GetName());
	RootObject->SetNumberField(TEXT("node_count"), EventGraph->Nodes.Num());

	TArray<TSharedPtr<FJsonValue>> NodesArray;
	for (UEdGraphNode* Node : EventGraph->Nodes)
	{
		if (Node)
		{
			TSharedPtr<FJsonObject> NodeSummary = ExportNodeSummary(Node, bIncludePinDetails);
			if (NodeSummary.IsValid())
			{
				NodesArray.Add(MakeShareable(new FJsonValueObject(NodeSummary)));
			}
		}
	}
	RootObject->SetArrayField(TEXT("nodes"), NodesArray);

	TArray<TSharedPtr<FJsonValue>> VariablesArray;
	for (const FBPVariableDescription& Variable : Blueprint->NewVariables)
	{
		TSharedPtr<FJsonObject> VarObject = MakeShareable(new FJsonObject);
		VarObject->SetStringField(TEXT("name"), Variable.VarName.ToString());
		VarObject->SetStringField(TEXT("type"), GetPinTypeString(Variable.VarType));
		
		VariablesArray.Add(MakeShareable(new FJsonValueObject(VarObject)));
	}
	RootObject->SetArrayField(TEXT("variables"), VariablesArray);

	FString OutputString;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
	FJsonSerializer::Serialize(RootObject.ToSharedRef(), Writer);

	return OutputString;
}

// 导出节点为完整 JSON 对象
TSharedPtr<FJsonObject> UBlueprintAIToolsLibrary::ExportNodeToJson(UEdGraphNode* Node)
{
	if (!Node)
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> NodeObject = MakeShareable(new FJsonObject);

	NodeObject->SetStringField(TEXT("guid"), Node->NodeGuid.ToString());
	NodeObject->SetStringField(TEXT("class"), Node->GetClass()->GetName());
	NodeObject->SetStringField(TEXT("title"), Node->GetNodeTitle(ENodeTitleType::FullTitle).ToString());
	
	TSharedPtr<FJsonObject> PositionObject = MakeShareable(new FJsonObject);
	PositionObject->SetNumberField(TEXT("x"), Node->NodePosX);
	PositionObject->SetNumberField(TEXT("y"), Node->NodePosY);
	NodeObject->SetObjectField(TEXT("position"), PositionObject);

	TArray<TSharedPtr<FJsonValue>> PinsArray;
	for (UEdGraphPin* Pin : Node->Pins)
	{
		if (Pin)
		{
			TSharedPtr<FJsonObject> PinObject = ExportPinToJson(Pin);
			if (PinObject.IsValid())
			{
				PinsArray.Add(MakeShareable(new FJsonValueObject(PinObject)));
			}
		}
	}
	NodeObject->SetArrayField(TEXT("pins"), PinsArray);

	if (UK2Node_CallFunction* CallFunctionNode = Cast<UK2Node_CallFunction>(Node))
	{
		if (CallFunctionNode->FunctionReference.GetMemberName() != NAME_None)
		{
			NodeObject->SetStringField(TEXT("function_name"), 
				CallFunctionNode->FunctionReference.GetMemberName().ToString());
		}
	}

	return NodeObject;
}

// 导出节点为简化 JSON 对象
TSharedPtr<FJsonObject> UBlueprintAIToolsLibrary::ExportNodeSummary(UEdGraphNode* Node, bool bIncludePinDetails)
{
	if (!Node)
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> NodeObject = MakeShareable(new FJsonObject);

	NodeObject->SetStringField(TEXT("guid"), Node->NodeGuid.ToString());
	NodeObject->SetStringField(TEXT("class"), Node->GetClass()->GetName());
	NodeObject->SetStringField(TEXT("title"), Node->GetNodeTitle(ENodeTitleType::ListView).ToString());
	
	TArray<TSharedPtr<FJsonValue>> PosArray;
	PosArray.Add(MakeShareable(new FJsonValueNumber(Node->NodePosX)));
	PosArray.Add(MakeShareable(new FJsonValueNumber(Node->NodePosY)));
	NodeObject->SetArrayField(TEXT("pos"), PosArray);

	if (bIncludePinDetails)
	{
		TArray<TSharedPtr<FJsonValue>> PinsArray;
		for (UEdGraphPin* Pin : Node->Pins)
		{
			if (Pin)
			{
				TSharedPtr<FJsonObject> PinSimple = MakeShareable(new FJsonObject);
				PinSimple->SetStringField(TEXT("name"), Pin->PinName.ToString());
				PinSimple->SetStringField(TEXT("type"), GetPinTypeString(Pin->PinType));
				PinSimple->SetStringField(TEXT("dir"), Pin->Direction == EGPD_Input ? TEXT("in") : TEXT("out"));
				
				// 添加默认值（修复：AI无法看到引脚默认值的问题）
				if (!Pin->DefaultValue.IsEmpty())
				{
					PinSimple->SetStringField(TEXT("default_value"), Pin->DefaultValue);
				}
				if (!Pin->DefaultTextValue.IsEmpty())
				{
					PinSimple->SetStringField(TEXT("default_text_value"), Pin->DefaultTextValue.ToString());
				}
				// 添加对象引用（用于资产引用类型的引脚）
				if (Pin->DefaultObject != nullptr)
				{
					PinSimple->SetStringField(TEXT("default_object"), Pin->DefaultObject->GetPathName());
				}
				
				if (Pin->LinkedTo.Num() > 0)
				{
					TArray<TSharedPtr<FJsonValue>> LinkedGuids;
					for (UEdGraphPin* LinkedPin : Pin->LinkedTo)
					{
						if (LinkedPin && LinkedPin->GetOwningNode())
						{
							LinkedGuids.Add(MakeShareable(new FJsonValueString(
								LinkedPin->GetOwningNode()->NodeGuid.ToString())));
						}
					}
					PinSimple->SetArrayField(TEXT("links"), LinkedGuids);
				}
				
				PinsArray.Add(MakeShareable(new FJsonValueObject(PinSimple)));
			}
		}
		NodeObject->SetArrayField(TEXT("pins"), PinsArray);
	}
	else
	{
		int32 InputCount = 0;
		int32 OutputCount = 0;
		for (UEdGraphPin* Pin : Node->Pins)
		{
			if (Pin)
			{
				if (Pin->Direction == EGPD_Input)
					InputCount++;
				else
					OutputCount++;
			}
		}
		NodeObject->SetNumberField(TEXT("inputs"), InputCount);
		NodeObject->SetNumberField(TEXT("outputs"), OutputCount);
	}

	if (UK2Node_CallFunction* CallFunctionNode = Cast<UK2Node_CallFunction>(Node))
	{
		if (CallFunctionNode->FunctionReference.GetMemberName() != NAME_None)
		{
			NodeObject->SetStringField(TEXT("func"), 
				CallFunctionNode->FunctionReference.GetMemberName().ToString());
		}
	}

	return NodeObject;
}

// 导出 Pin 为 JSON 对象
TSharedPtr<FJsonObject> UBlueprintAIToolsLibrary::ExportPinToJson(UEdGraphPin* Pin)
{
	if (!Pin)
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> PinObject = MakeShareable(new FJsonObject);

	PinObject->SetStringField(TEXT("name"), Pin->PinName.ToString());
	PinObject->SetStringField(TEXT("pin_id"), Pin->PinId.ToString());
	
	PinObject->SetStringField(TEXT("direction"), 
		Pin->Direction == EGPD_Input ? TEXT("Input") : TEXT("Output"));

	PinObject->SetStringField(TEXT("type"), GetPinTypeString(Pin->PinType));

	if (!Pin->DefaultValue.IsEmpty())
	{
		PinObject->SetStringField(TEXT("default_value"), Pin->DefaultValue);
	}
	if (!Pin->DefaultTextValue.IsEmpty())
	{
		PinObject->SetStringField(TEXT("default_text_value"), Pin->DefaultTextValue.ToString());
	}

	if (Pin->LinkedTo.Num() > 0)
	{
		TArray<TSharedPtr<FJsonValue>> LinkedArray;
		for (UEdGraphPin* LinkedPin : Pin->LinkedTo)
		{
			if (LinkedPin && LinkedPin->GetOwningNode())
			{
				TSharedPtr<FJsonObject> LinkedObject = MakeShareable(new FJsonObject);
				LinkedObject->SetStringField(TEXT("node_guid"), 
					LinkedPin->GetOwningNode()->NodeGuid.ToString());
				LinkedObject->SetStringField(TEXT("pin_id"), LinkedPin->PinId.ToString());
				LinkedObject->SetStringField(TEXT("pin_name"), LinkedPin->PinName.ToString());
				
				LinkedArray.Add(MakeShareable(new FJsonValueObject(LinkedObject)));
			}
		}
		PinObject->SetArrayField(TEXT("linked_to"), LinkedArray);
	}

	return PinObject;
}

// 获取节点字典
FString UBlueprintAIToolsLibrary::GetAvailableNodeTypes()
{
	FString PluginContentDir = FPaths::ProjectPluginsDir() / TEXT("BlueprintAITools/Content/Python/");
	FString JsonFilePath = PluginContentDir + TEXT("node_dictionary.json");
	
	FString JsonContent;
	if (FFileHelper::LoadFileToString(JsonContent, *JsonFilePath))
	{
		return JsonContent;
	}
	else
	{
		TSharedPtr<FJsonObject> FallbackObject = MakeShareable(new FJsonObject);
		FallbackObject->SetStringField(TEXT("error"), TEXT("DictionaryFileNotFound"));
		FallbackObject->SetStringField(TEXT("message"), TEXT("节点字典文件未找到"));
		
		FString OutputString;
		TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
		FJsonSerializer::Serialize(FallbackObject.ToSharedRef(), Writer);
		
		return OutputString;
	}
}

// 验证蓝图
FString UBlueprintAIToolsLibrary::ValidateBlueprint(UBlueprint* Blueprint)
{
	if (!Blueprint)
	{
		Blueprint = GetCurrentOpenBlueprint();
	}

	if (!Blueprint)
	{
		return TEXT("{\"error\": \"Invalid Blueprint\"}");
	}

	TSharedPtr<FJsonObject> RootObject = MakeShareable(new FJsonObject);
	RootObject->SetStringField(TEXT("blueprint_name"), Blueprint->GetName());
	
	TArray<TSharedPtr<FJsonValue>> ErrorsArray;
	TArray<TSharedPtr<FJsonValue>> WarningsArray;

	// ========== 方法 1：获取编译器日志中的错误和警告 ==========
	TArray<UEdGraph*> AllGraphs;
	Blueprint->GetAllGraphs(AllGraphs);

	for (UEdGraph* Graph : AllGraphs)
	{
		if (!Graph)
			continue;

		for (UEdGraphNode* Node : Graph->Nodes)
		{
			if (!Node)
				continue;

			// 检查节点自身是否有错误
			if (Node->bHasCompilerMessage)
			{
				TSharedPtr<FJsonObject> MsgObj = MakeShareable(new FJsonObject);
				MsgObj->SetStringField(TEXT("node_guid"), Node->NodeGuid.ToString());
				MsgObj->SetStringField(TEXT("node_title"), Node->GetNodeTitle(ENodeTitleType::ListView).ToString());
				MsgObj->SetStringField(TEXT("message"), Node->ErrorMsg.IsEmpty() ? TEXT("未知错误") : Node->ErrorMsg);
				
				// 根据错误类型分类
				if (Node->ErrorType <= EMessageSeverity::Error)
				{
					MsgObj->SetStringField(TEXT("severity"), TEXT("error"));
					ErrorsArray.Add(MakeShareable(new FJsonValueObject(MsgObj)));
				}
				else if (Node->ErrorType == EMessageSeverity::Warning || Node->ErrorType == EMessageSeverity::PerformanceWarning)
				{
					MsgObj->SetStringField(TEXT("severity"), TEXT("warning"));
					WarningsArray.Add(MakeShareable(new FJsonValueObject(MsgObj)));
				}
			}

			// ========== 方法 2：手动检查 Pin 类型不匹配 ==========
			for (UEdGraphPin* Pin : Node->Pins)
			{
				if (!Pin)
					continue;

				for (UEdGraphPin* LinkedPin : Pin->LinkedTo)
				{
					if (LinkedPin && !LinkedPin->PinType.PinCategory.IsEqual(Pin->PinType.PinCategory))
					{
						const UEdGraphSchema_K2* K2Schema = GetDefault<UEdGraphSchema_K2>();
						if (!K2Schema->ArePinsCompatible(Pin, LinkedPin, nullptr))
						{
							TSharedPtr<FJsonObject> ErrorObj = MakeShareable(new FJsonObject);
							ErrorObj->SetStringField(TEXT("severity"), TEXT("error"));
							ErrorObj->SetStringField(TEXT("node_guid"), Node->NodeGuid.ToString());
							ErrorObj->SetStringField(TEXT("node_title"), Node->GetNodeTitle(ENodeTitleType::ListView).ToString());
							ErrorObj->SetStringField(TEXT("pin_name"), Pin->PinName.ToString());
							ErrorObj->SetStringField(TEXT("message"), 
								FString::Printf(TEXT("Pin 类型不匹配：%s -> %s"), 
									*GetPinTypeString(Pin->PinType),
									*GetPinTypeString(LinkedPin->PinType)));
							ErrorsArray.Add(MakeShareable(new FJsonValueObject(ErrorObj)));
						}
					}
				}
			}
		}
	}

	RootObject->SetArrayField(TEXT("errors"), ErrorsArray);
	RootObject->SetArrayField(TEXT("warnings"), WarningsArray);
	RootObject->SetNumberField(TEXT("error_count"), ErrorsArray.Num());
	RootObject->SetNumberField(TEXT("warning_count"), WarningsArray.Num());

	FString OutputString;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
	FJsonSerializer::Serialize(RootObject.ToSharedRef(), Writer);

	return OutputString;
}

// 获取 Pin 类型字符串
FString UBlueprintAIToolsLibrary::GetPinTypeString(const FEdGraphPinType& PinType)
{
	FString TypeString = PinType.PinCategory.ToString();

	if (PinType.PinSubCategoryObject.IsValid())
	{
		TypeString += TEXT("<") + PinType.PinSubCategoryObject->GetName() + TEXT(">");
	}
	else if (!PinType.PinSubCategory.IsNone())
	{
		TypeString += TEXT("<") + PinType.PinSubCategory.ToString() + TEXT(">");
	}

	if (PinType.ContainerType == EPinContainerType::Array)
	{
		TypeString = TEXT("Array<") + TypeString + TEXT(">");
	}
	else if (PinType.ContainerType == EPinContainerType::Set)
	{
		TypeString = TEXT("Set<") + TypeString + TEXT(">");
	}
	else if (PinType.ContainerType == EPinContainerType::Map)
	{
		TypeString = TEXT("Map<") + TypeString + TEXT(">");
	}

	return TypeString;
}

// 获取蓝图编辑器中选中的节点（实验性）
FString UBlueprintAIToolsLibrary::GetSelectedNodes(UBlueprint* Blueprint)
{
	if (!Blueprint)
	{
		Blueprint = GetCurrentOpenBlueprint();
	}

	if (!Blueprint)
	{
		return TEXT("{\"error\": \"Invalid Blueprint\"}");
	}

	TSharedPtr<FJsonObject> RootObject = MakeShareable(new FJsonObject);
	RootObject->SetStringField(TEXT("blueprint_name"), Blueprint->GetName());
	
	TArray<TSharedPtr<FJsonValue>> SelectedNodesArray;

	// 方法 1：尝试通过 AssetEditorSubsystem 获取编辑器实例
	if (GEditor)
	{
		UAssetEditorSubsystem* AssetEditorSubsystem = GEditor->GetEditorSubsystem<UAssetEditorSubsystem>();
		if (AssetEditorSubsystem)
		{
			IAssetEditorInstance* EditorInstance = AssetEditorSubsystem->FindEditorForAsset(Blueprint, false);
			if (EditorInstance)
			{
				// 尝试获取选中的对象（通用方法）
				TArray<UObject*> SelectedObjects;
				if (GEditor->GetSelectedObjects())
				{
					GEditor->GetSelectedObjects()->GetSelectedObjects(SelectedObjects);
					
					for (UObject* SelectedObject : SelectedObjects)
					{
						if (UEdGraphNode* Node = Cast<UEdGraphNode>(SelectedObject))
						{
							TSharedPtr<FJsonObject> NodeObj = MakeShareable(new FJsonObject);
							NodeObj->SetStringField(TEXT("guid"), Node->NodeGuid.ToString());
							NodeObj->SetStringField(TEXT("title"), Node->GetNodeTitle(ENodeTitleType::ListView).ToString());
							NodeObj->SetStringField(TEXT("class"), Node->GetClass()->GetName());
							SelectedNodesArray.Add(MakeShareable(new FJsonValueObject(NodeObj)));
						}
					}
				}
			}
		}
	}

	// 注意：UE5 中 UEdGraphNode 不再有 bSelected 成员变量
	// 只能通过 GEditor->GetSelectedObjects() 获取选中的节点（方法1）

	RootObject->SetArrayField(TEXT("selected_nodes"), SelectedNodesArray);
	RootObject->SetNumberField(TEXT("count"), SelectedNodesArray.Num());

	FString OutputString;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
	FJsonSerializer::Serialize(RootObject.ToSharedRef(), Writer);

	return OutputString;
}
