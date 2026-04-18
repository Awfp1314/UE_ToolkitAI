#include "BlueprintAnalyzerSubsystem.h"
#include "Engine/Blueprint.h"
#include "WidgetBlueprint.h"
#include "Blueprint/WidgetTree.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"
#include "EdGraph/EdGraphPin.h"
#include "K2Node.h"
#include "K2Node_FunctionEntry.h"
#include "K2Node_Event.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "Editor.h"
#include "Subsystems/AssetEditorSubsystem.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonWriter.h"
#include "Serialization/JsonSerializer.h"
#include "JsonObjectConverter.h"
#include "Components/Widget.h"
#include "Components/PanelWidget.h"
#include "Misc/App.h"
#include "Misc/EngineVersion.h"

UObject* UBlueprintAnalyzerSubsystem::LoadAssetFromPath(const FString& AssetPath)
{
	// First, try to get the asset from the editor if it's currently open
	// This ensures we get the latest in-memory version, not the saved version on disk
	if (GEditor)
	{
		UAssetEditorSubsystem* AssetEditorSubsystem = GEditor->GetEditorSubsystem<UAssetEditorSubsystem>();
		if (AssetEditorSubsystem)
		{
			TArray<UObject*> EditedAssets = AssetEditorSubsystem->GetAllEditedAssets();
			for (UObject* Asset : EditedAssets)
			{
				if (Asset && Asset->GetPathName() == AssetPath)
				{
					// Found the asset in the editor, return the in-memory version
					return Asset;
				}
			}
		}
	}
	
	// If not found in editor, load from disk
	FSoftObjectPath SoftPath(AssetPath);
	return SoftPath.TryLoad();
}

FString UBlueprintAnalyzerSubsystem::CreateErrorJson(const FString& ErrorMessage)
{
	TSharedPtr<FJsonObject> ErrorObj = MakeShared<FJsonObject>();
	ErrorObj->SetStringField(TEXT("error"), ErrorMessage);
	ErrorObj->SetBoolField(TEXT("success"), false);
	
	FString OutputString;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
	FJsonSerializer::Serialize(ErrorObj.ToSharedRef(), Writer);
	return OutputString;
}

FString UBlueprintAnalyzerSubsystem::ExtractBlueprint(const FString& AssetPath)
{
	// Load blueprint asset
	UObject* Asset = LoadAssetFromPath(AssetPath);
	if (!Asset)
	{
		return CreateErrorJson(FString::Printf(TEXT("Failed to load asset: %s"), *AssetPath));
	}

	UBlueprint* Blueprint = Cast<UBlueprint>(Asset);
	if (!Blueprint)
	{
		return CreateErrorJson(TEXT("Asset is not a Blueprint"));
	}

	// Build JSON response
	TSharedPtr<FJsonObject> RootObj = MakeShared<FJsonObject>();
	RootObj->SetStringField(TEXT("assetPath"), AssetPath);
	RootObj->SetStringField(TEXT("assetName"), Blueprint->GetName());
	RootObj->SetStringField(TEXT("parentClass"), Blueprint->ParentClass ? Blueprint->ParentClass->GetName() : TEXT("None"));
	RootObj->SetBoolField(TEXT("success"), true);

	// Extract variables
	TArray<TSharedPtr<FJsonValue>> VariablesArray = ExtractVariables(Blueprint);
	RootObj->SetArrayField(TEXT("variables"), VariablesArray);

	// Extract functions
	TArray<TSharedPtr<FJsonValue>> FunctionsArray = ExtractFunctions(Blueprint);
	RootObj->SetArrayField(TEXT("functions"), FunctionsArray);

	// Extract graphs
	TArray<TSharedPtr<FJsonValue>> GraphsArray;
	for (UEdGraph* Graph : Blueprint->UbergraphPages)
	{
		if (Graph)
		{
			TSharedPtr<FJsonObject> GraphObj = ExtractGraphData(Graph);
			GraphsArray.Add(MakeShared<FJsonValueObject>(GraphObj));
		}
	}
	RootObj->SetArrayField(TEXT("graphs"), GraphsArray);

	// Serialize to string
	FString OutputString;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
	FJsonSerializer::Serialize(RootObj.ToSharedRef(), Writer);
	return OutputString;
}

TArray<TSharedPtr<FJsonValue>> UBlueprintAnalyzerSubsystem::ExtractVariables(UBlueprint* Blueprint)
{
	TArray<TSharedPtr<FJsonValue>> VariablesArray;
	
	for (const FBPVariableDescription& Variable : Blueprint->NewVariables)
	{
		TSharedPtr<FJsonObject> VarObj = MakeShared<FJsonObject>();
		VarObj->SetStringField(TEXT("name"), Variable.VarName.ToString());
		VarObj->SetStringField(TEXT("type"), Variable.VarType.PinCategory.ToString());
		VarObj->SetStringField(TEXT("category"), Variable.Category.ToString());
		VarObj->SetBoolField(TEXT("isArray"), Variable.VarType.ContainerType == EPinContainerType::Array);
		
		VariablesArray.Add(MakeShared<FJsonValueObject>(VarObj));
	}
	
	return VariablesArray;
}

TArray<TSharedPtr<FJsonValue>> UBlueprintAnalyzerSubsystem::ExtractFunctions(UBlueprint* Blueprint)
{
	TArray<TSharedPtr<FJsonValue>> FunctionsArray;
	
	for (UEdGraph* FunctionGraph : Blueprint->FunctionGraphs)
	{
		if (!FunctionGraph) continue;
		
		TSharedPtr<FJsonObject> FuncObj = MakeShared<FJsonObject>();
		FuncObj->SetStringField(TEXT("name"), FunctionGraph->GetName());
		
		// Find function entry node to get parameters
		TArray<TSharedPtr<FJsonValue>> ParamsArray;
		for (UEdGraphNode* Node : FunctionGraph->Nodes)
		{
			if (UK2Node_FunctionEntry* EntryNode = Cast<UK2Node_FunctionEntry>(Node))
			{
				for (UEdGraphPin* Pin : EntryNode->Pins)
				{
					if (Pin && Pin->Direction == EGPD_Output)
					{
						TSharedPtr<FJsonObject> ParamObj = MakeShared<FJsonObject>();
						ParamObj->SetStringField(TEXT("name"), Pin->PinName.ToString());
						ParamObj->SetStringField(TEXT("type"), Pin->PinType.PinCategory.ToString());
						ParamsArray.Add(MakeShared<FJsonValueObject>(ParamObj));
					}
				}
				break;
			}
		}
		
		FuncObj->SetArrayField(TEXT("parameters"), ParamsArray);
		FuncObj->SetNumberField(TEXT("nodeCount"), FunctionGraph->Nodes.Num());
		
		FunctionsArray.Add(MakeShared<FJsonValueObject>(FuncObj));
	}
	
	return FunctionsArray;
}

TSharedPtr<FJsonObject> UBlueprintAnalyzerSubsystem::ExtractGraphData(UEdGraph* Graph)
{
	TSharedPtr<FJsonObject> GraphObj = MakeShared<FJsonObject>();
	
	if (!Graph)
	{
		return GraphObj;
	}
	
	GraphObj->SetStringField(TEXT("name"), Graph->GetName());
	GraphObj->SetNumberField(TEXT("nodeCount"), Graph->Nodes.Num());
	
	// Extract nodes summary
	TArray<TSharedPtr<FJsonValue>> NodesArray;
	for (UEdGraphNode* Node : Graph->Nodes)
	{
		if (!Node) continue;
		
		TSharedPtr<FJsonObject> NodeObj = MakeShared<FJsonObject>();
		NodeObj->SetStringField(TEXT("title"), Node->GetNodeTitle(ENodeTitleType::FullTitle).ToString());
		NodeObj->SetStringField(TEXT("class"), Node->GetClass()->GetName());
		
		// Check if it's an event node
		if (UK2Node_Event* EventNode = Cast<UK2Node_Event>(Node))
		{
			NodeObj->SetStringField(TEXT("eventName"), EventNode->EventReference.GetMemberName().ToString());
		}
		
		NodesArray.Add(MakeShared<FJsonValueObject>(NodeObj));
	}
	
	GraphObj->SetArrayField(TEXT("nodes"), NodesArray);
	
	return GraphObj;
}

FString UBlueprintAnalyzerSubsystem::ExtractWidgetBlueprint(const FString& AssetPath)
{
	// Load widget blueprint asset
	UObject* Asset = LoadAssetFromPath(AssetPath);
	if (!Asset)
	{
		return CreateErrorJson(FString::Printf(TEXT("Failed to load asset: %s"), *AssetPath));
	}

	UWidgetBlueprint* WidgetBP = Cast<UWidgetBlueprint>(Asset);
	if (!WidgetBP)
	{
		return CreateErrorJson(TEXT("Asset is not a Widget Blueprint"));
	}

	// Build JSON response
	TSharedPtr<FJsonObject> RootObj = MakeShared<FJsonObject>();
	RootObj->SetStringField(TEXT("assetPath"), AssetPath);
	RootObj->SetStringField(TEXT("assetName"), WidgetBP->GetName());
	RootObj->SetBoolField(TEXT("success"), true);

	// Extract widget tree
	TSharedPtr<FJsonObject> WidgetTreeObj = ExtractWidgetTree(WidgetBP);
	RootObj->SetObjectField(TEXT("widgetTree"), WidgetTreeObj);

	// Extract variables (same as blueprint)
	TArray<TSharedPtr<FJsonValue>> VariablesArray = ExtractVariables(WidgetBP);
	RootObj->SetArrayField(TEXT("variables"), VariablesArray);

	// Extract functions
	TArray<TSharedPtr<FJsonValue>> FunctionsArray = ExtractFunctions(WidgetBP);
	RootObj->SetArrayField(TEXT("functions"), FunctionsArray);

	// Serialize to string
	FString OutputString;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
	FJsonSerializer::Serialize(RootObj.ToSharedRef(), Writer);
	return OutputString;
}

TSharedPtr<FJsonObject> UBlueprintAnalyzerSubsystem::ExtractWidgetTree(UWidgetBlueprint* WidgetBP)
{
	TSharedPtr<FJsonObject> TreeObj = MakeShared<FJsonObject>();
	
	if (!WidgetBP->WidgetTree)
	{
		TreeObj->SetStringField(TEXT("error"), TEXT("No widget tree found"));
		return TreeObj;
	}

	UWidget* RootWidget = WidgetBP->WidgetTree->RootWidget;
	if (!RootWidget)
	{
		TreeObj->SetStringField(TEXT("error"), TEXT("No root widget"));
		return TreeObj;
	}

	// Recursive function to extract widget hierarchy
	TFunction<TSharedPtr<FJsonObject>(UWidget*)> ExtractWidget;
	ExtractWidget = [&](UWidget* Widget) -> TSharedPtr<FJsonObject>
	{
		TSharedPtr<FJsonObject> WidgetObj = MakeShared<FJsonObject>();
		
		if (!Widget)
		{
			return WidgetObj;
		}
		
		WidgetObj->SetStringField(TEXT("name"), Widget->GetName());
		WidgetObj->SetStringField(TEXT("class"), Widget->GetClass()->GetName());
		WidgetObj->SetBoolField(TEXT("isVariable"), Widget->bIsVariable);
		
		// If it's a panel widget, extract children
		if (UPanelWidget* PanelWidget = Cast<UPanelWidget>(Widget))
		{
			TArray<TSharedPtr<FJsonValue>> ChildrenArray;
			for (int32 i = 0; i < PanelWidget->GetChildrenCount(); ++i)
			{
				UWidget* Child = PanelWidget->GetChildAt(i);
				if (Child)
				{
					TSharedPtr<FJsonObject> ChildObj = ExtractWidget(Child);
					ChildrenArray.Add(MakeShared<FJsonValueObject>(ChildObj));
				}
			}
			WidgetObj->SetArrayField(TEXT("children"), ChildrenArray);
		}
		
		return WidgetObj;
	};

	// Extract root widget and its hierarchy
	TSharedPtr<FJsonObject> RootWidgetObj = ExtractWidget(RootWidget);
	TreeObj->SetObjectField(TEXT("root"), RootWidgetObj);
	
	return TreeObj;
}

FString UBlueprintAnalyzerSubsystem::GetEditorContext()
{
	TSharedPtr<FJsonObject> ContextObj = MakeShared<FJsonObject>();
	
	// Project information
	ContextObj->SetStringField(TEXT("projectName"), FApp::GetProjectName());
	ContextObj->SetStringField(TEXT("engineVersion"), FEngineVersion::Current().ToString());
	
	// Editor state
	if (GEditor)
	{
		ContextObj->SetBoolField(TEXT("isPlayInEditor"), GEditor->PlayWorld != nullptr);
		
		// Get currently open assets
		TArray<TSharedPtr<FJsonValue>> OpenAssetsArray;
		TArray<UObject*> EditedAssets = GEditor->GetEditorSubsystem<UAssetEditorSubsystem>()->GetAllEditedAssets();
		
		for (UObject* Asset : EditedAssets)
		{
			if (Asset)
			{
				TSharedPtr<FJsonObject> AssetObj = MakeShared<FJsonObject>();
				AssetObj->SetStringField(TEXT("name"), Asset->GetName());
				AssetObj->SetStringField(TEXT("class"), Asset->GetClass()->GetName());
				AssetObj->SetStringField(TEXT("path"), Asset->GetPathName());
				
				OpenAssetsArray.Add(MakeShared<FJsonValueObject>(AssetObj));
			}
		}
		
		ContextObj->SetArrayField(TEXT("openAssets"), OpenAssetsArray);
	}
	
	// Asset registry stats
	FAssetRegistryModule& AssetRegistryModule = FModuleManager::LoadModuleChecked<FAssetRegistryModule>("AssetRegistry");
	IAssetRegistry& AssetRegistry = AssetRegistryModule.Get();
	
	// Get only project assets (exclude engine content)
	TArray<FAssetData> AllAssets;
	AssetRegistry.GetAssetsByPath(FName("/Game"), AllAssets, true);
	
	ContextObj->SetNumberField(TEXT("totalAssets"), AllAssets.Num());
	
	// Count blueprints using correct class name
	int32 BlueprintCount = 0;
	int32 WidgetBlueprintCount = 0;
	
	for (const FAssetData& AssetData : AllAssets)
	{
		FString ClassName = AssetData.AssetClassPath.GetAssetName().ToString();
		
		if (ClassName == TEXT("Blueprint") || ClassName == TEXT("BlueprintGeneratedClass"))
		{
			BlueprintCount++;
		}
		else if (ClassName == TEXT("WidgetBlueprint"))
		{
			WidgetBlueprintCount++;
		}
	}
	
	ContextObj->SetNumberField(TEXT("blueprintCount"), BlueprintCount);
	ContextObj->SetNumberField(TEXT("widgetBlueprintCount"), WidgetBlueprintCount);
	ContextObj->SetBoolField(TEXT("success"), true);
	
	// Serialize to string
	FString OutputString;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
	FJsonSerializer::Serialize(ContextObj.ToSharedRef(), Writer);
	return OutputString;
}

FString UBlueprintAnalyzerSubsystem::ListAssets(const FString& PackagePath, const bool bRecursive, const FString& ClassFilter)
{
	TArray<TSharedPtr<FJsonValue>> ResultArray;

	// When non-recursive, include immediate subdirectories so users can browse the folder tree
	if (!bRecursive)
	{
		TArray<FString> SubPaths;
		IAssetRegistry::Get()->GetSubPaths(PackagePath, SubPaths, false);
		for (const FString& SubPath : SubPaths)
		{
			const FString FolderName = FPaths::GetCleanFilename(SubPath);
			const TSharedPtr<FJsonObject> FolderObj = MakeShared<FJsonObject>();
			FolderObj->SetStringField(TEXT("path"), SubPath);
			FolderObj->SetStringField(TEXT("name"), FolderName);
			FolderObj->SetStringField(TEXT("class"), TEXT("Folder"));
			ResultArray.Add(MakeShared<FJsonValueObject>(FolderObj));
		}
	}

	TArray<FAssetData> AssetDatas;
	IAssetRegistry::Get()->GetAssetsByPath(FName(*PackagePath), AssetDatas, bRecursive);

	for (const FAssetData& AssetData : AssetDatas)
	{
		const FString AssetClass = AssetData.AssetClassPath.GetAssetName().ToString();

		if (!ClassFilter.IsEmpty() && AssetClass != ClassFilter)
		{
			continue;
		}

		const TSharedPtr<FJsonObject> AssetObj = MakeShared<FJsonObject>();
		AssetObj->SetStringField(TEXT("path"),  AssetData.GetObjectPathString());
		AssetObj->SetStringField(TEXT("name"),  AssetData.AssetName.ToString());
		AssetObj->SetStringField(TEXT("class"), AssetClass);
		ResultArray.Add(MakeShared<FJsonValueObject>(AssetObj));
	}

	FString OutString;
	const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutString);
	FJsonSerializer::Serialize(ResultArray, Writer);
	return OutString;
}
