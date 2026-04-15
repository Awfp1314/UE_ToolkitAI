// Copyright HUTAO. All Rights Reserved.

#include "BlueprintToAISubsystem.h"
#include "Engine/Blueprint.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "AssetToolsModule.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "EdGraphSchema_K2.h"
#include "K2Node_Event.h"
#include "K2Node_CallFunction.h"
#include "K2Node_VariableGet.h"
#include "K2Node_VariableSet.h"
#include "K2Node_DynamicCast.h"
#include "K2Node_IfThenElse.h"
#include "Json.h"
#include "JsonUtilities.h"
#include "Misc/PackageName.h"
#include "UObject/SavePackage.h"
#include "FileHelpers.h"
#include "UObject/StructOnScope.h"

void UBlueprintToAISubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	UE_LOG(LogTemp, Log, TEXT("BlueprintToAI Subsystem initialized (UE 5.6+)"));
}

void UBlueprintToAISubsystem::Deinitialize()
{
	UE_LOG(LogTemp, Log, TEXT("BlueprintToAI Subsystem deinitialized"));
	Super::Deinitialize();
}

FString UBlueprintToAISubsystem::ExtractBlueprint(const FString& AssetPath, const FString& Scope)
{
	FString ErrorMsg;
	UBlueprint* Blueprint = LoadBlueprintAsset(AssetPath, ErrorMsg);
	if (!Blueprint)
	{
		return CreateErrorResponse(TEXT("ExtractBlueprint"), ErrorMsg);
	}

	// Create JSON response
	TSharedPtr<FJsonObject> BlueprintJson = MakeShared<FJsonObject>();
	BlueprintJson->SetStringField(TEXT("name"), Blueprint->GetName());
	
	// Get parent class
	if (Blueprint->ParentClass)
	{
		BlueprintJson->SetStringField(TEXT("parentClass"), Blueprint->ParentClass->GetPathName());
	}

	// Extract graphs
	TArray<TSharedPtr<FJsonValue>> GraphsArray;
	for (UEdGraph* Graph : Blueprint->UbergraphPages)
	{
		if (!Graph) continue;

		TSharedPtr<FJsonObject> GraphJson = MakeShared<FJsonObject>();
		GraphJson->SetStringField(TEXT("graphName"), Graph->GetName());
		
		// Extract nodes
		TArray<TSharedPtr<FJsonValue>> NodesArray;
		for (UEdGraphNode* Node : Graph->Nodes)
		{
			if (!Node) continue;

			TSharedPtr<FJsonObject> NodeJson = MakeShared<FJsonObject>();
			NodeJson->SetStringField(TEXT("nodeGuid"), Node->NodeGuid.ToString());
			NodeJson->SetStringField(TEXT("nodeClass"), Node->GetClass()->GetName());
			NodeJson->SetStringField(TEXT("nodeTitle"), Node->GetNodeTitle(ENodeTitleType::FullTitle).ToString());
			NodeJson->SetNumberField(TEXT("posX"), Node->NodePosX);
			NodeJson->SetNumberField(TEXT("posY"), Node->NodePosY);

			// Extract pins (only in Compact or Full mode)
			if (Scope != TEXT("Minimal"))
			{
				TArray<TSharedPtr<FJsonValue>> PinsArray;
				for (UEdGraphPin* Pin : Node->Pins)
				{
					if (!Pin) continue;

					TSharedPtr<FJsonObject> PinJson = MakeShared<FJsonObject>();
					PinJson->SetStringField(TEXT("pinName"), Pin->PinName.ToString());
					PinJson->SetStringField(TEXT("direction"), Pin->Direction == EGPD_Input ? TEXT("Input") : TEXT("Output"));
					PinJson->SetStringField(TEXT("category"), Pin->PinType.PinCategory.ToString());

					// Extract connections
					TArray<TSharedPtr<FJsonValue>> ConnectionsArray;
					for (UEdGraphPin* LinkedPin : Pin->LinkedTo)
					{
						if (!LinkedPin || !LinkedPin->GetOwningNode()) continue;

						TSharedPtr<FJsonObject> ConnectionJson = MakeShared<FJsonObject>();
						ConnectionJson->SetStringField(TEXT("nodeGuid"), LinkedPin->GetOwningNode()->NodeGuid.ToString());
						ConnectionJson->SetStringField(TEXT("pinName"), LinkedPin->PinName.ToString());
						ConnectionsArray.Add(MakeShared<FJsonValueObject>(ConnectionJson));
					}
					PinJson->SetArrayField(TEXT("connections"), ConnectionsArray);

					PinsArray.Add(MakeShared<FJsonValueObject>(PinJson));
				}
				NodeJson->SetArrayField(TEXT("pins"), PinsArray);
			}

			NodesArray.Add(MakeShared<FJsonValueObject>(NodeJson));
		}
		GraphJson->SetArrayField(TEXT("nodes"), NodesArray);
		GraphsArray.Add(MakeShared<FJsonValueObject>(GraphJson));
	}
	BlueprintJson->SetArrayField(TEXT("graphs"), GraphsArray);

	// Extract variables (only in Compact or Full mode)
	if (Scope != TEXT("Minimal"))
	{
		TArray<TSharedPtr<FJsonValue>> VariablesArray;
		for (const FBPVariableDescription& Variable : Blueprint->NewVariables)
		{
			TSharedPtr<FJsonObject> VarJson = MakeShared<FJsonObject>();
			VarJson->SetStringField(TEXT("name"), Variable.VarName.ToString());
			VarJson->SetStringField(TEXT("type"), Variable.VarType.PinCategory.ToString());
			VariablesArray.Add(MakeShared<FJsonValueObject>(VarJson));
		}
		BlueprintJson->SetArrayField(TEXT("variables"), VariablesArray);
	}

	// Create response
	TSharedPtr<FJsonObject> ResponseData = MakeShared<FJsonObject>();
	ResponseData->SetObjectField(TEXT("blueprint"), BlueprintJson);
	
	return CreateSuccessResponse(TEXT("ExtractBlueprint"), ResponseData);
}

FString UBlueprintToAISubsystem::CreateBlueprint(const FString& AssetPath, const FString& ParentClass, 
                                                const FString& GraphDSL, const FString& PayloadJson)
{
	// Load parent class
	UClass* ParentClassObj = LoadObject<UClass>(nullptr, *ParentClass);
	if (!ParentClassObj)
	{
		return CreateErrorResponse(TEXT("CreateBlueprint"), 
		                          FString::Printf(TEXT("Failed to load parent class: %s"), *ParentClass));
	}

	// Create Blueprint
	FString PackageName = AssetPath;
	FString AssetName = FPackageName::GetLongPackageAssetName(PackageName);
	
	UPackage* Package = CreatePackage(*PackageName);
	if (!Package)
	{
		return CreateErrorResponse(TEXT("CreateBlueprint"), TEXT("Failed to create package"));
	}

	UBlueprint* NewBlueprint = FKismetEditorUtilities::CreateBlueprint(
		ParentClassObj,
		Package,
		*AssetName,
		BPTYPE_Normal,
		UBlueprint::StaticClass(),
		UBlueprintGeneratedClass::StaticClass(),
		NAME_None
	);

	if (!NewBlueprint)
	{
		return CreateErrorResponse(TEXT("CreateBlueprint"), TEXT("Failed to create Blueprint"));
	}

	// TODO: Parse and apply GraphDSL (Phase 2)
	// TODO: Parse and apply PayloadJson for variables/components (Phase 2)

	// Mark package as dirty
	Package->MarkPackageDirty();
	
	// Notify asset registry
	FAssetRegistryModule::AssetCreated(NewBlueprint);

	TSharedPtr<FJsonObject> ResponseData = MakeShared<FJsonObject>();
	ResponseData->SetStringField(TEXT("assetPath"), AssetPath);
	ResponseData->SetStringField(TEXT("message"), TEXT("Blueprint created successfully"));
	
	return CreateSuccessResponse(TEXT("CreateBlueprint"), ResponseData);
}

FString UBlueprintToAISubsystem::ModifyBlueprint(const FString& AssetPath, const FString& Operation, 
                                                const FString& PayloadJson)
{
	FString ErrorMsg;
	UBlueprint* Blueprint = LoadBlueprintAsset(AssetPath, ErrorMsg);
	if (!Blueprint)
	{
		return CreateErrorResponse(TEXT("ModifyBlueprint"), ErrorMsg);
	}

	// Parse payload JSON
	TSharedPtr<FJsonObject> PayloadObject;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PayloadJson);
	if (!FJsonSerializer::Deserialize(Reader, PayloadObject) || !PayloadObject.IsValid())
	{
		return CreateErrorResponse(TEXT("ModifyBlueprint"), TEXT("Invalid JSON payload"));
	}

	bool bSuccess = false;
	FString Message;

	if (Operation == TEXT("add_variable"))
	{
		// Add variable using official Blueprint Editor API
		FString VarName = PayloadObject->GetStringField(TEXT("name"));
		FString VarType = PayloadObject->GetStringField(TEXT("type"));
		
		// 构建正确的 PinType
		FEdGraphPinType PinType;
		PinType.ResetToDefaults();
		
		// 根据类型字符串设置正确的 PinCategory 和 PinSubCategoryObject
		if (VarType.Equals(TEXT("bool"), ESearchCase::IgnoreCase))
		{
			PinType.PinCategory = UEdGraphSchema_K2::PC_Boolean;
		}
		else if (VarType.Equals(TEXT("int"), ESearchCase::IgnoreCase) || VarType.Equals(TEXT("integer"), ESearchCase::IgnoreCase))
		{
			PinType.PinCategory = UEdGraphSchema_K2::PC_Int;
		}
		else if (VarType.Equals(TEXT("int64"), ESearchCase::IgnoreCase))
		{
			PinType.PinCategory = UEdGraphSchema_K2::PC_Int64;
		}
		else if (VarType.Equals(TEXT("byte"), ESearchCase::IgnoreCase))
		{
			PinType.PinCategory = UEdGraphSchema_K2::PC_Byte;
		}
		else if (VarType.Equals(TEXT("float"), ESearchCase::IgnoreCase) || VarType.Equals(TEXT("real"), ESearchCase::IgnoreCase))
		{
			PinType.PinCategory = UEdGraphSchema_K2::PC_Real;
			PinType.PinSubCategory = UEdGraphSchema_K2::PC_Float;
		}
		else if (VarType.Equals(TEXT("double"), ESearchCase::IgnoreCase))
		{
			PinType.PinCategory = UEdGraphSchema_K2::PC_Real;
			PinType.PinSubCategory = UEdGraphSchema_K2::PC_Double;
		}
		else if (VarType.Equals(TEXT("string"), ESearchCase::IgnoreCase))
		{
			PinType.PinCategory = UEdGraphSchema_K2::PC_String;
		}
		else if (VarType.Equals(TEXT("name"), ESearchCase::IgnoreCase))
		{
			PinType.PinCategory = UEdGraphSchema_K2::PC_Name;
		}
		else if (VarType.Equals(TEXT("text"), ESearchCase::IgnoreCase))
		{
			PinType.PinCategory = UEdGraphSchema_K2::PC_Text;
		}
		else if (VarType.Equals(TEXT("vector"), ESearchCase::IgnoreCase))
		{
			PinType.PinCategory = UEdGraphSchema_K2::PC_Struct;
			PinType.PinSubCategoryObject = TBaseStructure<FVector>::Get();
		}
		else if (VarType.Equals(TEXT("rotator"), ESearchCase::IgnoreCase))
		{
			PinType.PinCategory = UEdGraphSchema_K2::PC_Struct;
			PinType.PinSubCategoryObject = TBaseStructure<FRotator>::Get();
		}
		else if (VarType.Equals(TEXT("transform"), ESearchCase::IgnoreCase))
		{
			PinType.PinCategory = UEdGraphSchema_K2::PC_Struct;
			PinType.PinSubCategoryObject = TBaseStructure<FTransform>::Get();
		}
		else if (VarType.Equals(TEXT("color"), ESearchCase::IgnoreCase) || VarType.Equals(TEXT("linearcolor"), ESearchCase::IgnoreCase))
		{
			PinType.PinCategory = UEdGraphSchema_K2::PC_Struct;
			PinType.PinSubCategoryObject = TBaseStructure<FLinearColor>::Get();
		}
		else
		{
			// 不支持的类型
			Message = FString::Printf(TEXT("Unsupported variable type: %s. Supported types: bool, byte, int, int64, float, double, string, name, text, vector, rotator, transform, color"), *VarType);
			bSuccess = false;
		}
		
		if (bSuccess || Message.IsEmpty())
		{
			// 使用官方 API 添加变量，这会自动处理所有必要的初始化
			FString DefaultValue;
			PayloadObject->TryGetStringField(TEXT("defaultValue"), DefaultValue);
			
			if (FBlueprintEditorUtils::AddMemberVariable(Blueprint, FName(*VarName), PinType, DefaultValue))
			{
				bSuccess = true;
				Message = FString::Printf(TEXT("Variable '%s' (type: %s) added successfully"), *VarName, *VarType);
			}
			else
			{
				bSuccess = false;
				Message = FString::Printf(TEXT("Failed to add variable '%s'. The variable may already exist or the type is invalid."), *VarName);
			}
		}
	}
	else if (Operation == TEXT("reparent"))
	{
		// Change parent class
		FString NewParentClass = PayloadObject->GetStringField(TEXT("parentClassPath"));
		UClass* NewParentClassObj = LoadObject<UClass>(nullptr, *NewParentClass);
		
		if (NewParentClassObj)
		{
			Blueprint->ParentClass = NewParentClassObj;
			FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
			bSuccess = true;
			Message = FString::Printf(TEXT("Parent class changed to '%s'"), *NewParentClass);
		}
		else
		{
			Message = FString::Printf(TEXT("Failed to load parent class: %s"), *NewParentClass);
		}
	}
	else
	{
		Message = FString::Printf(TEXT("Unknown operation: %s"), *Operation);
	}

	if (bSuccess)
	{
		TSharedPtr<FJsonObject> ResponseData = MakeShared<FJsonObject>();
		ResponseData->SetStringField(TEXT("message"), Message);
		return CreateSuccessResponse(TEXT("ModifyBlueprint"), ResponseData);
	}
	else
	{
		return CreateErrorResponse(TEXT("ModifyBlueprint"), Message);
	}
}

FString UBlueprintToAISubsystem::SaveBlueprints(const TArray<FString>& AssetPaths)
{
	TArray<UPackage*> PackagesToSave;
	TArray<FString> SavedPaths;
	TArray<FString> FailedPaths;

	for (const FString& AssetPath : AssetPaths)
	{
		FString ErrorMsg;
		UBlueprint* Blueprint = LoadBlueprintAsset(AssetPath, ErrorMsg);
		if (Blueprint && Blueprint->GetOutermost())
		{
			PackagesToSave.Add(Blueprint->GetOutermost());
			SavedPaths.Add(AssetPath);
		}
		else
		{
			FailedPaths.Add(AssetPath);
		}
	}

	// Save packages
	if (PackagesToSave.Num() > 0)
	{
		FEditorFileUtils::PromptForCheckoutAndSave(PackagesToSave, false, false);
	}

	TSharedPtr<FJsonObject> ResponseData = MakeShared<FJsonObject>();
	ResponseData->SetNumberField(TEXT("savedCount"), SavedPaths.Num());
	ResponseData->SetNumberField(TEXT("failedCount"), FailedPaths.Num());
	
	TArray<TSharedPtr<FJsonValue>> SavedArray;
	for (const FString& Path : SavedPaths)
	{
		SavedArray.Add(MakeShared<FJsonValueString>(Path));
	}
	ResponseData->SetArrayField(TEXT("saved"), SavedArray);
	
	if (FailedPaths.Num() > 0)
	{
		TArray<TSharedPtr<FJsonValue>> FailedArray;
		for (const FString& Path : FailedPaths)
		{
			FailedArray.Add(MakeShared<FJsonValueString>(Path));
		}
		ResponseData->SetArrayField(TEXT("failed"), FailedArray);
	}

	return CreateSuccessResponse(TEXT("SaveBlueprints"), ResponseData);
}

UBlueprint* UBlueprintToAISubsystem::LoadBlueprintAsset(const FString& AssetPath, FString& OutError)
{
	UObject* LoadedAsset = LoadObject<UObject>(nullptr, *AssetPath);
	if (!LoadedAsset)
	{
		OutError = FString::Printf(TEXT("Failed to load asset: %s"), *AssetPath);
		return nullptr;
	}

	UBlueprint* Blueprint = Cast<UBlueprint>(LoadedAsset);
	if (!Blueprint)
	{
		OutError = FString::Printf(TEXT("Asset is not a Blueprint: %s"), *AssetPath);
		return nullptr;
	}

	return Blueprint;
}

FString UBlueprintToAISubsystem::CreateSuccessResponse(const FString& Operation, const TSharedPtr<FJsonObject>& Data)
{
	TSharedPtr<FJsonObject> Response = MakeShared<FJsonObject>();
	Response->SetBoolField(TEXT("success"), true);
	Response->SetStringField(TEXT("operation"), Operation);
	
	if (Data.IsValid())
	{
		// Put data in a nested "data" field for consistency
		Response->SetObjectField(TEXT("data"), Data);
	}

	FString OutputString;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
	FJsonSerializer::Serialize(Response.ToSharedRef(), Writer);
	return OutputString;
}

FString UBlueprintToAISubsystem::CreateErrorResponse(const FString& Operation, const FString& ErrorMessage)
{
	TSharedPtr<FJsonObject> Response = MakeShared<FJsonObject>();
	Response->SetBoolField(TEXT("success"), false);
	Response->SetStringField(TEXT("operation"), Operation);
	Response->SetStringField(TEXT("error"), ErrorMessage);

	FString OutputString;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
	FJsonSerializer::Serialize(Response.ToSharedRef(), Writer);
	return OutputString;
}

FString UBlueprintToAISubsystem::GetActiveBlueprint()
{
	// Get the active asset editor
	UAssetEditorSubsystem* AssetEditorSubsystem = GEditor->GetEditorSubsystem<UAssetEditorSubsystem>();
	if (!AssetEditorSubsystem)
	{
		return CreateErrorResponse(TEXT("GetActiveBlueprint"), TEXT("AssetEditorSubsystem not available"));
	}

	// Get all open assets
	TArray<UObject*> EditedAssets = AssetEditorSubsystem->GetAllEditedAssets();
	
	// Find the first Blueprint in the list (usually the focused one)
	for (UObject* Asset : EditedAssets)
	{
		if (UBlueprint* Blueprint = Cast<UBlueprint>(Asset))
		{
			// Get the package path (without the object name suffix)
			FString FullPath = Blueprint->GetPathName();
			FString PackagePath = FullPath;
			
			// Remove the ".ObjectName" suffix if present
			int32 DotIndex;
			if (FullPath.FindLastChar('.', DotIndex))
			{
				PackagePath = FullPath.Left(DotIndex);
			}
			
			// Create response
			TSharedPtr<FJsonObject> ResponseData = MakeShared<FJsonObject>();
			ResponseData->SetStringField(TEXT("assetPath"), PackagePath);
			ResponseData->SetStringField(TEXT("name"), Blueprint->GetName());
			ResponseData->SetStringField(TEXT("parentClass"), Blueprint->ParentClass ? Blueprint->ParentClass->GetPathName() : TEXT(""));
			
			return CreateSuccessResponse(TEXT("GetActiveBlueprint"), ResponseData);
		}
	}

	return CreateErrorResponse(TEXT("GetActiveBlueprint"), TEXT("No Blueprint is currently open in the editor"));
}

FString UBlueprintToAISubsystem::ExtractActiveBlueprint(const FString& Scope)
{
	// First, get the active Blueprint
	FString ActiveBlueprintJson = GetActiveBlueprint();
	
	// Parse the response to check if it succeeded
	TSharedPtr<FJsonObject> JsonObject;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(ActiveBlueprintJson);
	
	if (!FJsonSerializer::Deserialize(Reader, JsonObject) || !JsonObject.IsValid())
	{
		return CreateErrorResponse(TEXT("ExtractActiveBlueprint"), TEXT("Failed to parse GetActiveBlueprint response"));
	}

	bool bSuccess = JsonObject->GetBoolField(TEXT("success"));
	if (!bSuccess)
	{
		// Return the error from GetActiveBlueprint
		return ActiveBlueprintJson;
	}

	// Extract the asset path
	TSharedPtr<FJsonObject> DataObject = JsonObject->GetObjectField(TEXT("data"));
	if (!DataObject.IsValid())
	{
		return CreateErrorResponse(TEXT("ExtractActiveBlueprint"), TEXT("Invalid response data"));
	}

	FString AssetPath = DataObject->GetStringField(TEXT("assetPath"));
	
	// Now extract the Blueprint using the asset path
	return ExtractBlueprint(AssetPath, Scope);
}
