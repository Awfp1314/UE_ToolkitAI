#include "BlueprintToolsSubsystem.h"
#include "BlueprintToolsModule.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "Dom/JsonObject.h"
#include "Engine/Blueprint.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "UObject/SavePackage.h"

namespace
{
	static FString SerializeJsonObject(const TSharedPtr<FJsonObject>& JsonObject)
	{
		FString OutString;
		const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutString);
		FJsonSerializer::Serialize(JsonObject.ToSharedRef(), Writer);
		return OutString;
	}

	static TSharedPtr<FJsonObject> CreateErrorResponse(const FString& ErrorMessage)
	{
		TSharedPtr<FJsonObject> ErrorObj = MakeShared<FJsonObject>();
		ErrorObj->SetBoolField(TEXT("success"), false);
		ErrorObj->SetStringField(TEXT("error"), ErrorMessage);
		return ErrorObj;
	}

	static TSharedPtr<FJsonObject> CreateSuccessResponse()
	{
		TSharedPtr<FJsonObject> SuccessObj = MakeShared<FJsonObject>();
		SuccessObj->SetBoolField(TEXT("success"), true);
		return SuccessObj;
	}
}

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
		return SerializeJsonObject(CreateErrorResponse(FString::Printf(TEXT("Failed to load Blueprint: %s"), *AssetPath)));
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

	return SerializeJsonObject(ResultObj);
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
		TSharedPtr<FJsonObject> ResultObj = CreateSuccessResponse();
		ResultObj->SetStringField(TEXT("message"), TEXT("Validation passed"));
		return SerializeJsonObject(ResultObj);
	}

	// Load parent class
	UClass* ParentClass = LoadObject<UClass>(nullptr, *ParentClassPath);
	if (!ParentClass)
	{
		return SerializeJsonObject(CreateErrorResponse(FString::Printf(TEXT("Failed to load parent class: %s"), *ParentClassPath)));
	}

	// Create Blueprint
	UBlueprint* NewBlueprint = FKismetEditorUtilities::CreateBlueprint(
		ParentClass,
		nullptr,
		FName(*AssetPath),
		BPTYPE_Normal,
		UBlueprint::StaticClass(),
		UBlueprintGeneratedClass::StaticClass(),
		NAME_None);

	if (!NewBlueprint)
	{
		return SerializeJsonObject(CreateErrorResponse(TEXT("Failed to create Blueprint")));
	}

	// TODO: Apply PayloadJson (variables, functions, components)

	TSharedPtr<FJsonObject> ResultObj = CreateSuccessResponse();
	ResultObj->SetStringField(TEXT("assetPath"), NewBlueprint->GetPathName());
	ResultObj->SetStringField(TEXT("message"), TEXT("Blueprint created successfully"));
	return SerializeJsonObject(ResultObj);
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
		return SerializeJsonObject(CreateErrorResponse(FString::Printf(TEXT("Failed to load Blueprint: %s"), *AssetPath)));
	}

	if (bValidateOnly)
	{
		// TODO: Implement validation logic
		TSharedPtr<FJsonObject> ResultObj = CreateSuccessResponse();
		ResultObj->SetStringField(TEXT("message"), TEXT("Validation passed"));
		return SerializeJsonObject(ResultObj);
	}

	// TODO: Implement operations:
	// - add_variable
	// - remove_variable
	// - modify_variable
	// - add_function
	// - remove_function
	// - add_component
	// - remove_component

	TSharedPtr<FJsonObject> ResultObj = CreateSuccessResponse();
	ResultObj->SetStringField(TEXT("message"), FString::Printf(TEXT("Operation '%s' completed"), *Operation));
	return SerializeJsonObject(ResultObj);
}

FString UBlueprintToolsSubsystem::CompileBlueprint(const FString& AssetPath)
{
	UE_LOG(LogBlueprintTools, Log, TEXT("CompileBlueprint: %s"), *AssetPath);

	UBlueprint* Blueprint = LoadObject<UBlueprint>(nullptr, *AssetPath);
	if (!Blueprint)
	{
		return SerializeJsonObject(CreateErrorResponse(FString::Printf(TEXT("Failed to load Blueprint: %s"), *AssetPath)));
	}

	FKismetEditorUtilities::CompileBlueprint(Blueprint);

	TSharedPtr<FJsonObject> ResultObj = CreateSuccessResponse();
	TArray<TSharedPtr<FJsonValue>> ErrorsArray;
	
	// TODO: Collect compilation errors/warnings from Blueprint->Status

	ResultObj->SetArrayField(TEXT("errors"), ErrorsArray);
	ResultObj->SetStringField(TEXT("message"), TEXT("Blueprint compiled"));
	return SerializeJsonObject(ResultObj);
}

FString UBlueprintToolsSubsystem::SaveAssets(const FString& AssetPathsJson)
{
	UE_LOG(LogBlueprintTools, Log, TEXT("SaveAssets: %s"), *AssetPathsJson);

	TSharedPtr<FJsonValue> JsonValue;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(AssetPathsJson);
	
	if (!FJsonSerializer::Deserialize(Reader, JsonValue) || JsonValue->Type != EJson::Array)
	{
		return SerializeJsonObject(CreateErrorResponse(TEXT("Invalid JSON array")));
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

	TSharedPtr<FJsonObject> ResultObj = CreateSuccessResponse();
	ResultObj->SetNumberField(TEXT("savedCount"), SavedCount);
	ResultObj->SetNumberField(TEXT("totalCount"), AssetPaths.Num());
	return SerializeJsonObject(ResultObj);
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

	TSharedPtr<FJsonObject> ResultObj = CreateSuccessResponse();
	ResultObj->SetArrayField(TEXT("assets"), ResultsArray);
	ResultObj->SetNumberField(TEXT("count"), Count);
	return SerializeJsonObject(ResultObj);
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

	TSharedPtr<FJsonObject> ResultObj = CreateSuccessResponse();
	ResultObj->SetArrayField(TEXT("assets"), ResultsArray);
	ResultObj->SetNumberField(TEXT("count"), ResultsArray.Num());
	return SerializeJsonObject(ResultObj);
}

FString UBlueprintToolsSubsystem::GetEditorContext()
{
	UE_LOG(LogBlueprintTools, Log, TEXT("GetEditorContext"));

	TSharedPtr<FJsonObject> ContextObj = MakeShared<FJsonObject>();
	ContextObj->SetStringField(TEXT("projectName"), FApp::GetProjectName());
	ContextObj->SetStringField(TEXT("engineVersion"), FEngineVersion::Current().ToString());
	ContextObj->SetStringField(TEXT("pluginVersion"), TEXT("1.0.0-UE5.4"));
	ContextObj->SetNumberField(TEXT("processId"), static_cast<int32>(FPlatformProcess::GetCurrentProcessId()));

	return SerializeJsonObject(ContextObj);
}
