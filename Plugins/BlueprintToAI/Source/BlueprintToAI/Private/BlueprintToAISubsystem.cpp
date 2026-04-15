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
		// Add variable
		FString VarName = PayloadObject->GetStringField(TEXT("name"));
		FString VarType = PayloadObject->GetStringField(TEXT("type"));
		
		FEdGraphPinType PinType;
		PinType.PinCategory = *VarType;
		
		FBPVariableDescription NewVar;
		NewVar.VarName = *VarName;
		NewVar.VarType = PinType;
		NewVar.PropertyFlags = CPF_Edit | CPF_BlueprintVisible;
		
		Blueprint->NewVariables.Add(NewVar);
		FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
		
		bSuccess = true;
		Message = FString::Printf(TEXT("Variable '%s' added successfully"), *VarName);
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
		// Merge data fields into response
		for (const auto& Pair : Data->Values)
		{
			Response->SetField(Pair.Key, Pair.Value);
		}
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
			// Get the asset path
			FString AssetPath = Blueprint->GetPathName();
			
			// Create response
			TSharedPtr<FJsonObject> ResponseData = MakeShared<FJsonObject>();
			ResponseData->SetStringField(TEXT("assetPath"), AssetPath);
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
