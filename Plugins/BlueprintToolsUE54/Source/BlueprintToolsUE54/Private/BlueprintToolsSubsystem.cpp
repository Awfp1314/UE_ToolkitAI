#include "BlueprintToolsSubsystem.h"
#include "BlueprintToolsModule.h"
#include "BlueprintToolsHelpers.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "Dom/JsonObject.h"
#include "Engine/Blueprint.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Misc/PackageName.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"

EBlueprintExtractionScope UBlueprintToolsSubsystem::ParseScope(const FString& ScopeString)
{
	if (ScopeString.Equals(TEXT("ClassLevel"), ESearchCase::IgnoreCase))
	{
		return EBlueprintExtractionScope::ClassLevel;
	}
	if (ScopeString.Equals(TEXT("Variables"), ESearchCase::IgnoreCase))
	{
		return EBlueprintExtractionScope::Variables;
	}
	if (ScopeString.Equals(TEXT("Components"), ESearchCase::IgnoreCase))
	{
		return EBlueprintExtractionScope::Components;
	}
	if (ScopeString.Equals(TEXT("FunctionsShallow"), ESearchCase::IgnoreCase))
	{
		return EBlueprintExtractionScope::FunctionsShallow;
	}
	return EBlueprintExtractionScope::Full;
}

FString UBlueprintToolsSubsystem::ExtractBlueprint(
	const FString& AssetPath,
	const FString& Scope,
	const FString& GraphFilter,
	const bool bIncludeClassDefaults)
{
	UE_LOG(LogBlueprintTools, Log, TEXT("ExtractBlueprint: %s (Scope: %s)"), *AssetPath, *Scope);

	// Load the Blueprint asset
	UBlueprint* Blueprint = LoadObject<UBlueprint>(nullptr, *AssetPath);
	if (!Blueprint)
	{
		return FBlueprintToolsHelpers::SerializeJsonObject(
			FBlueprintToolsHelpers::CreateErrorResponse(
				FString::Printf(TEXT("Failed to load Blueprint: %s"), *AssetPath)));
	}

	const EBlueprintExtractionScope ExtractionScope = ParseScope(Scope);
	
	TSharedPtr<FJsonObject> ResultObj = MakeShared<FJsonObject>();
	ResultObj->SetBoolField(TEXT("success"), true);
	ResultObj->SetStringField(TEXT("assetPath"), AssetPath);
	ResultObj->SetStringField(TEXT("assetName"), Blueprint->GetName());
	ResultObj->SetStringField(TEXT("parentClass"), Blueprint->ParentClass ? Blueprint->ParentClass->GetPathName() : TEXT(""));

	// TODO: Implement extraction logic based on scope
	// - ClassLevel: basic metadata
	// - Variables: + member variables
	// - Components: + components
	// - FunctionsShallow: + function signatures
	// - Full: + graph nodes

	return FBlueprintToolsHelpers::SerializeJsonObject(ResultObj);
}

FString UBlueprintToolsSubsystem::CreateBlueprint(
	const FString& AssetPath,
	const FString& ParentClassPath,
	const FString& PayloadJson,
	const bool bValidateOnly)
{
	UE_LOG(LogBlueprintTools, Log, TEXT("CreateBlueprint: %s (Parent: %s, ValidateOnly: %d)"), 
		*AssetPath, *ParentClassPath, bValidateOnly);

	if (bValidateOnly)
	{
		// TODO: Implement validation logic
		TSharedPtr<FJsonObject> ResultObj = FBlueprintToolsHelpers::CreateSuccessResponse();
		ResultObj->SetStringField(TEXT("message"), TEXT("Validation passed"));
		return FBlueprintToolsHelpers::SerializeJsonObject(ResultObj);
	}

	// Load parent class
	UClass* ParentClass = FBlueprintToolsHelpers::ResolveClass(ParentClassPath);
	if (!ParentClass)
	{
		return FBlueprintToolsHelpers::SerializeJsonObject(
			FBlueprintToolsHelpers::CreateErrorResponse(
				FString::Printf(TEXT("Failed to load parent class: %s"), *ParentClassPath)));
	}

	// Create package
	UPackage* Package = CreatePackage(*AssetPath);
	if (!Package)
	{
		return FBlueprintToolsHelpers::SerializeJsonObject(
			FBlueprintToolsHelpers::CreateErrorResponse(
				FString::Printf(TEXT("Failed to create package: %s"), *AssetPath)));
	}

	// Get asset name from package path
	const FName AssetName = FPackageName::GetShortFName(AssetPath);

	// Create Blueprint
	UBlueprint* NewBlueprint = FKismetEditorUtilities::CreateBlueprint(
		ParentClass,
		Package,
		AssetName,
		BPTYPE_Normal,
		UBlueprint::StaticClass(),
		UBlueprintGeneratedClass::StaticClass(),
		NAME_None);

	if (!NewBlueprint)
	{
		return FBlueprintToolsHelpers::SerializeJsonObject(
			FBlueprintToolsHelpers::CreateErrorResponse(TEXT("Failed to create Blueprint")));
	}

	// Mark as modified
	NewBlueprint->Modify();

	// TODO: Apply PayloadJson (variables, functions, components)

	// Compile the Blueprint
	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(NewBlueprint);
	TArray<TSharedPtr<FJsonValue>> Errors, Warnings;
	FBlueprintToolsHelpers::CompileBlueprint(NewBlueprint, Errors, Warnings);

	// Notify asset registry
	FAssetRegistryModule::AssetCreated(NewBlueprint);

	TSharedPtr<FJsonObject> ResultObj = FBlueprintToolsHelpers::CreateSuccessResponse();
	ResultObj->SetStringField(TEXT("assetPath"), NewBlueprint->GetPathName());
	ResultObj->SetStringField(TEXT("assetName"), AssetName.ToString());
	ResultObj->SetStringField(TEXT("message"), TEXT("Blueprint created successfully"));
	return FBlueprintToolsHelpers::SerializeJsonObject(ResultObj);
}

FString UBlueprintToolsSubsystem::ModifyBlueprintMembers(
	const FString& AssetPath,
	const FString& Operation,
	const FString& PayloadJson,
	const bool bValidateOnly)
{
	UE_LOG(LogBlueprintTools, Log, TEXT("ModifyBlueprintMembers: %s (Operation: %s, ValidateOnly: %d)"), 
		*AssetPath, *Operation, bValidateOnly);

	UBlueprint* Blueprint = LoadObject<UBlueprint>(nullptr, *AssetPath);
	if (!Blueprint)
	{
		return FBlueprintToolsHelpers::SerializeJsonObject(
			FBlueprintToolsHelpers::CreateErrorResponse(
				FString::Printf(TEXT("Failed to load Blueprint: %s"), *AssetPath)));
	}

	// Parse payload JSON
	TSharedPtr<FJsonObject> PayloadObject;
	if (!PayloadJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PayloadJson);
		if (!FJsonSerializer::Deserialize(Reader, PayloadObject) || !PayloadObject.IsValid())
		{
			return FBlueprintToolsHelpers::SerializeJsonObject(
				FBlueprintToolsHelpers::CreateErrorResponse(TEXT("Invalid PayloadJson format")));
		}
	}

	if (bValidateOnly)
	{
		// TODO: Implement validation logic
		TSharedPtr<FJsonObject> ResultObj = FBlueprintToolsHelpers::CreateSuccessResponse();
		ResultObj->SetStringField(TEXT("message"), TEXT("Validation passed"));
		return FBlueprintToolsHelpers::SerializeJsonObject(ResultObj);
	}

	// Handle different operations
	if (Operation.Equals(TEXT("add_variable"), ESearchCase::IgnoreCase))
	{
		return AddVariable(Blueprint, PayloadObject);
	}
	else if (Operation.Equals(TEXT("remove_variable"), ESearchCase::IgnoreCase))
	{
		return RemoveVariable(Blueprint, PayloadObject);
	}
	else if (Operation.Equals(TEXT("modify_variable"), ESearchCase::IgnoreCase))
	{
		return ModifyVariable(Blueprint, PayloadObject);
	}
	else
	{
		return FBlueprintToolsHelpers::SerializeJsonObject(
			FBlueprintToolsHelpers::CreateErrorResponse(
				FString::Printf(TEXT("Unsupported operation: %s"), *Operation)));
	}
}

FString UBlueprintToolsSubsystem::AddVariable(UBlueprint* Blueprint, const TSharedPtr<FJsonObject>& PayloadObject)
{
	if (!Blueprint || !PayloadObject.IsValid())
	{
		return FBlueprintToolsHelpers::SerializeJsonObject(
			FBlueprintToolsHelpers::CreateErrorResponse(TEXT("Invalid Blueprint or payload")));
	}

	// Get variable name
	FString VariableName;
	if (!PayloadObject->TryGetStringField(TEXT("name"), VariableName) || VariableName.IsEmpty())
	{
		return FBlueprintToolsHelpers::SerializeJsonObject(
			FBlueprintToolsHelpers::CreateErrorResponse(TEXT("Variable name is required")));
	}

	// Check if variable already exists
	const int32 ExistingIndex = FBlueprintToolsHelpers::FindVariableIndex(Blueprint, FName(*VariableName));
	if (ExistingIndex != INDEX_NONE)
	{
		return FBlueprintToolsHelpers::SerializeJsonObject(
			FBlueprintToolsHelpers::CreateErrorResponse(
				FString::Printf(TEXT("Variable '%s' already exists"), *VariableName)));
	}

	// Parse variable type
	const TSharedPtr<FJsonObject>* TypeObject = nullptr;
	if (!PayloadObject->TryGetObjectField(TEXT("type"), TypeObject) || !TypeObject || !(*TypeObject).IsValid())
	{
		return FBlueprintToolsHelpers::SerializeJsonObject(
			FBlueprintToolsHelpers::CreateErrorResponse(TEXT("Variable type is required")));
	}

	FEdGraphPinType PinType;
	FString ParseError;
	if (!FBlueprintToolsHelpers::ParsePinType(*TypeObject, PinType, ParseError))
	{
		return FBlueprintToolsHelpers::SerializeJsonObject(
			FBlueprintToolsHelpers::CreateErrorResponse(
				FString::Printf(TEXT("Failed to parse type: %s"), *ParseError)));
	}

	// Get default value (optional)
	FString DefaultValue;
	PayloadObject->TryGetStringField(TEXT("defaultValue"), DefaultValue);

	// Add the variable using official API
	if (!FBlueprintEditorUtils::AddMemberVariable(Blueprint, FName(*VariableName), PinType, DefaultValue))
	{
		return FBlueprintToolsHelpers::SerializeJsonObject(
			FBlueprintToolsHelpers::CreateErrorResponse(
				FString::Printf(TEXT("Failed to add variable '%s'"), *VariableName)));
	}

	// Find the newly added variable
	const int32 VariableIndex = FBlueprintToolsHelpers::FindVariableIndex(Blueprint, FName(*VariableName));
	if (VariableIndex == INDEX_NONE || !Blueprint->NewVariables.IsValidIndex(VariableIndex))
	{
		return FBlueprintToolsHelpers::SerializeJsonObject(
			FBlueprintToolsHelpers::CreateErrorResponse(
				FString::Printf(TEXT("Failed to find variable '%s' after creation"), *VariableName)));
	}

	// Set additional metadata
	FBPVariableDescription& VarDesc = Blueprint->NewVariables[VariableIndex];

	FString Category;
	if (PayloadObject->TryGetStringField(TEXT("category"), Category))
	{
		VarDesc.Category = FText::FromString(Category);
	}

	FString Tooltip;
	if (PayloadObject->TryGetStringField(TEXT("tooltip"), Tooltip))
	{
		VarDesc.SetMetaData(TEXT("tooltip"), *Tooltip);
	}

	bool bExposeOnSpawn = false;
	if (PayloadObject->TryGetBoolField(TEXT("exposeOnSpawn"), bExposeOnSpawn) && bExposeOnSpawn)
	{
		VarDesc.PropertyFlags |= CPF_ExposeOnSpawn;
	}

	bool bInstanceEditable = false;
	if (PayloadObject->TryGetBoolField(TEXT("instanceEditable"), bInstanceEditable))
	{
		if (bInstanceEditable)
		{
			VarDesc.PropertyFlags |= CPF_Edit;
			VarDesc.PropertyFlags |= CPF_BlueprintVisible;
		}
	}

	bool bReplicated = false;
	if (PayloadObject->TryGetBoolField(TEXT("replicated"), bReplicated) && bReplicated)
	{
		VarDesc.PropertyFlags |= CPF_Net;
	}

	// Mark Blueprint as modified
	FBlueprintEditorUtils::MarkBlueprintAsModified(Blueprint);

	// Create success response
	TSharedPtr<FJsonObject> ResultObj = FBlueprintToolsHelpers::CreateSuccessResponse();
	ResultObj->SetStringField(TEXT("message"), FString::Printf(TEXT("Variable '%s' added successfully"), *VariableName));
	ResultObj->SetStringField(TEXT("variableName"), VariableName);
	ResultObj->SetStringField(TEXT("assetPath"), Blueprint->GetPathName());
	return FBlueprintToolsHelpers::SerializeJsonObject(ResultObj);
}

FString UBlueprintToolsSubsystem::RemoveVariable(UBlueprint* Blueprint, const TSharedPtr<FJsonObject>& PayloadObject)
{
	if (!Blueprint || !PayloadObject.IsValid())
	{
		return FBlueprintToolsHelpers::SerializeJsonObject(
			FBlueprintToolsHelpers::CreateErrorResponse(TEXT("Invalid Blueprint or payload")));
	}

	FString VariableName;
	if (!PayloadObject->TryGetStringField(TEXT("name"), VariableName) || VariableName.IsEmpty())
	{
		return FBlueprintToolsHelpers::SerializeJsonObject(
			FBlueprintToolsHelpers::CreateErrorResponse(TEXT("Variable name is required")));
	}

	const int32 VariableIndex = FBlueprintToolsHelpers::FindVariableIndex(Blueprint, FName(*VariableName));
	if (VariableIndex == INDEX_NONE)
	{
		return FBlueprintToolsHelpers::SerializeJsonObject(
			FBlueprintToolsHelpers::CreateErrorResponse(
				FString::Printf(TEXT("Variable '%s' not found"), *VariableName)));
	}

	// Remove the variable using official API
	FBlueprintEditorUtils::RemoveMemberVariable(Blueprint, FName(*VariableName));

	// Mark Blueprint as modified
	FBlueprintEditorUtils::MarkBlueprintAsModified(Blueprint);

	TSharedPtr<FJsonObject> ResultObj = FBlueprintToolsHelpers::CreateSuccessResponse();
	ResultObj->SetStringField(TEXT("message"), FString::Printf(TEXT("Variable '%s' removed successfully"), *VariableName));
	return FBlueprintToolsHelpers::SerializeJsonObject(ResultObj);
}

FString UBlueprintToolsSubsystem::ModifyVariable(UBlueprint* Blueprint, const TSharedPtr<FJsonObject>& PayloadObject)
{
	if (!Blueprint || !PayloadObject.IsValid())
	{
		return FBlueprintToolsHelpers::SerializeJsonObject(
			FBlueprintToolsHelpers::CreateErrorResponse(TEXT("Invalid Blueprint or payload")));
	}

	FString VariableName;
	if (!PayloadObject->TryGetStringField(TEXT("name"), VariableName) || VariableName.IsEmpty())
	{
		return FBlueprintToolsHelpers::SerializeJsonObject(
			FBlueprintToolsHelpers::CreateErrorResponse(TEXT("Variable name is required")));
	}

	int32 VariableIndex = FBlueprintToolsHelpers::FindVariableIndex(Blueprint, FName(*VariableName));
	if (VariableIndex == INDEX_NONE)
	{
		return FBlueprintToolsHelpers::SerializeJsonObject(
			FBlueprintToolsHelpers::CreateErrorResponse(
				FString::Printf(TEXT("Variable '%s' not found"), *VariableName)));
	}

	FBPVariableDescription& VarDesc = Blueprint->NewVariables[VariableIndex];

	// Update default value
	FString DefaultValue;
	if (PayloadObject->TryGetStringField(TEXT("defaultValue"), DefaultValue))
	{
		VarDesc.DefaultValue = DefaultValue;
	}

	// Update category
	FString Category;
	if (PayloadObject->TryGetStringField(TEXT("category"), Category))
	{
		VarDesc.Category = FText::FromString(Category);
	}

	// Update tooltip
	FString Tooltip;
	if (PayloadObject->TryGetStringField(TEXT("tooltip"), Tooltip))
	{
		VarDesc.SetMetaData(TEXT("tooltip"), *Tooltip);
	}

	// Update flags
	bool bExposeOnSpawn;
	if (PayloadObject->TryGetBoolField(TEXT("exposeOnSpawn"), bExposeOnSpawn))
	{
		if (bExposeOnSpawn)
		{
			VarDesc.PropertyFlags |= CPF_ExposeOnSpawn;
		}
		else
		{
			VarDesc.PropertyFlags &= ~CPF_ExposeOnSpawn;
		}
	}

	bool bInstanceEditable;
	if (PayloadObject->TryGetBoolField(TEXT("instanceEditable"), bInstanceEditable))
	{
		if (bInstanceEditable)
		{
			VarDesc.PropertyFlags |= CPF_Edit;
			VarDesc.PropertyFlags |= CPF_BlueprintVisible;
		}
		else
		{
			VarDesc.PropertyFlags &= ~CPF_Edit;
			VarDesc.PropertyFlags &= ~CPF_BlueprintVisible;
		}
	}

	// Mark Blueprint as modified
	FBlueprintEditorUtils::MarkBlueprintAsModified(Blueprint);

	TSharedPtr<FJsonObject> ResultObj = FBlueprintToolsHelpers::CreateSuccessResponse();
	ResultObj->SetStringField(TEXT("message"), FString::Printf(TEXT("Variable '%s' modified successfully"), *VariableName));
	return FBlueprintToolsHelpers::SerializeJsonObject(ResultObj);
}

FString UBlueprintToolsSubsystem::CompileBlueprint(const FString& AssetPath)
{
	UE_LOG(LogBlueprintTools, Log, TEXT("CompileBlueprint: %s"), *AssetPath);

	UBlueprint* Blueprint = LoadObject<UBlueprint>(nullptr, *AssetPath);
	if (!Blueprint)
	{
		return FBlueprintToolsHelpers::SerializeJsonObject(
			FBlueprintToolsHelpers::CreateErrorResponse(
				FString::Printf(TEXT("Failed to load Blueprint: %s"), *AssetPath)));
	}

	TArray<TSharedPtr<FJsonValue>> ErrorsArray;
	TArray<TSharedPtr<FJsonValue>> WarningsArray;
	
	const bool bSuccess = FBlueprintToolsHelpers::CompileBlueprint(Blueprint, ErrorsArray, WarningsArray);

	TSharedPtr<FJsonObject> ResultObj = FBlueprintToolsHelpers::CreateSuccessResponse();
	ResultObj->SetBoolField(TEXT("success"), bSuccess);
	ResultObj->SetArrayField(TEXT("errors"), ErrorsArray);
	ResultObj->SetArrayField(TEXT("warnings"), WarningsArray);
	ResultObj->SetStringField(TEXT("message"), bSuccess ? TEXT("Blueprint compiled successfully") : TEXT("Blueprint compilation failed"));
	return FBlueprintToolsHelpers::SerializeJsonObject(ResultObj);
}

FString UBlueprintToolsSubsystem::SaveAssets(const FString& AssetPathsJson)
{
	UE_LOG(LogBlueprintTools, Log, TEXT("SaveAssets: %s"), *AssetPathsJson);

	TSharedPtr<FJsonValue> JsonValue;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(AssetPathsJson);
	
	if (!FJsonSerializer::Deserialize(Reader, JsonValue) || JsonValue->Type != EJson::Array)
	{
		return FBlueprintToolsHelpers::SerializeJsonObject(
			FBlueprintToolsHelpers::CreateErrorResponse(TEXT("Invalid JSON array")));
	}

	const TArray<TSharedPtr<FJsonValue>> AssetPaths = JsonValue->AsArray();
	int32 SavedCount = 0;

	for (const TSharedPtr<FJsonValue>& PathValue : AssetPaths)
	{
		const FString AssetPath = PathValue->AsString();
		UObject* Asset = LoadObject<UObject>(nullptr, *AssetPath);
		
		if (Asset && Asset->GetPackage())
		{
			UPackage* Package = Asset->GetPackage();
			const FString PackageFileName = FPackageName::LongPackageNameToFilename(
				Package->GetName(),
				FPackageName::GetAssetPackageExtension());

			FSavePackageArgs SaveArgs;
			SaveArgs.TopLevelFlags = RF_Public | RF_Standalone;
			
			if (UPackage::SavePackage(Package, nullptr, *PackageFileName, SaveArgs))
			{
				SavedCount++;
			}
		}
	}

	TSharedPtr<FJsonObject> ResultObj = FBlueprintToolsHelpers::CreateSuccessResponse();
	ResultObj->SetNumberField(TEXT("savedCount"), SavedCount);
	ResultObj->SetNumberField(TEXT("totalCount"), AssetPaths.Num());
	return FBlueprintToolsHelpers::SerializeJsonObject(ResultObj);
}

FString UBlueprintToolsSubsystem::SearchAssets(
	const FString& Query,
	const FString& ClassFilter,
	const int32 MaxResults)
{
	UE_LOG(LogBlueprintTools, Log, TEXT("SearchAssets: Query='%s', ClassFilter='%s', MaxResults=%d"), 
		*Query, *ClassFilter, MaxResults);

	FAssetRegistryModule& AssetRegistryModule = FModuleManager::LoadModuleChecked<FAssetRegistryModule>("AssetRegistry");
	IAssetRegistry& AssetRegistry = AssetRegistryModule.Get();

	FARFilter Filter;
	if (!ClassFilter.IsEmpty())
	{
		Filter.ClassPaths.Add(FTopLevelAssetPath(TEXT("/Script/Engine"), *ClassFilter));
	}
	Filter.bRecursiveClasses = true;

	TArray<FAssetData> AssetDataList;
	AssetRegistry.GetAssets(Filter, AssetDataList);

	TArray<TSharedPtr<FJsonValue>> ResultsArray;
	int32 Count = 0;

	for (const FAssetData& AssetData : AssetDataList)
	{
		if (Count >= MaxResults)
		{
			break;
		}

		const FString AssetName = AssetData.AssetName.ToString();
		if (Query.IsEmpty() || AssetName.Contains(Query))
		{
			TSharedPtr<FJsonObject> AssetObj = MakeShared<FJsonObject>();
			AssetObj->SetStringField(TEXT("assetPath"), AssetData.GetObjectPathString());
			AssetObj->SetStringField(TEXT("assetName"), AssetName);
			AssetObj->SetStringField(TEXT("assetClass"), AssetData.AssetClassPath.ToString());
			ResultsArray.Add(MakeShared<FJsonValueObject>(AssetObj));
			Count++;
		}
	}

	TSharedPtr<FJsonObject> ResultObj = FBlueprintToolsHelpers::CreateSuccessResponse();
	ResultObj->SetArrayField(TEXT("assets"), ResultsArray);
	ResultObj->SetNumberField(TEXT("count"), Count);
	return FBlueprintToolsHelpers::SerializeJsonObject(ResultObj);
}

FString UBlueprintToolsSubsystem::ListAssets(
	const FString& PackagePath,
	const bool bRecursive,
	const FString& ClassFilter)
{
	UE_LOG(LogBlueprintTools, Log, TEXT("ListAssets: Path='%s', Recursive=%d, ClassFilter='%s'"), 
		*PackagePath, bRecursive, *ClassFilter);

	FAssetRegistryModule& AssetRegistryModule = FModuleManager::LoadModuleChecked<FAssetRegistryModule>("AssetRegistry");
	IAssetRegistry& AssetRegistry = AssetRegistryModule.Get();

	FARFilter Filter;
	Filter.PackagePaths.Add(FName(*PackagePath));
	Filter.bRecursivePaths = bRecursive;
	
	if (!ClassFilter.IsEmpty())
	{
		Filter.ClassPaths.Add(FTopLevelAssetPath(TEXT("/Script/Engine"), *ClassFilter));
	}
	Filter.bRecursiveClasses = true;

	TArray<FAssetData> AssetDataList;
	AssetRegistry.GetAssets(Filter, AssetDataList);

	TArray<TSharedPtr<FJsonValue>> ResultsArray;
	for (const FAssetData& AssetData : AssetDataList)
	{
		TSharedPtr<FJsonObject> AssetObj = MakeShared<FJsonObject>();
		AssetObj->SetStringField(TEXT("assetPath"), AssetData.GetObjectPathString());
		AssetObj->SetStringField(TEXT("assetName"), AssetData.AssetName.ToString());
		AssetObj->SetStringField(TEXT("assetClass"), AssetData.AssetClassPath.ToString());
		AssetObj->SetStringField(TEXT("packagePath"), AssetData.PackagePath.ToString());
		ResultsArray.Add(MakeShared<FJsonValueObject>(AssetObj));
	}

	TSharedPtr<FJsonObject> ResultObj = FBlueprintToolsHelpers::CreateSuccessResponse();
	ResultObj->SetArrayField(TEXT("assets"), ResultsArray);
	ResultObj->SetNumberField(TEXT("count"), ResultsArray.Num());
	return FBlueprintToolsHelpers::SerializeJsonObject(ResultObj);
}

FString UBlueprintToolsSubsystem::GetEditorContext()
{
	UE_LOG(LogBlueprintTools, Log, TEXT("GetEditorContext"));

	TSharedPtr<FJsonObject> ContextObj = MakeShared<FJsonObject>();
	ContextObj->SetStringField(TEXT("projectName"), FApp::GetProjectName());
	ContextObj->SetStringField(TEXT("engineVersion"), FEngineVersion::Current().ToString());
	ContextObj->SetStringField(TEXT("pluginVersion"), TEXT("1.0.0-UE5.4"));
	ContextObj->SetNumberField(TEXT("processId"), static_cast<int32>(FPlatformProcess::GetCurrentProcessId()));

	return FBlueprintToolsHelpers::SerializeJsonObject(ContextObj);
}
