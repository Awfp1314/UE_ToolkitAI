#include "Authoring/DataAssetAuthoring.h"

#include "Authoring/AssetMutationHelpers.h"
#include "PropertySerializer.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "Engine/DataAsset.h"
#include "Misc/PackageName.h"
#include "UObject/Package.h"
#include "UObject/UObjectGlobals.h"

namespace DataAssetAuthoringInternal
{

static UClass* ResolveDataAssetClass(const FString& AssetClassPath)
{
	if (AssetClassPath.IsEmpty())
	{
		return nullptr;
	}

	if (UClass* LoadedClass = StaticLoadClass(UDataAsset::StaticClass(), nullptr, *AssetClassPath))
	{
		return LoadedClass;
	}

	return FindObject<UClass>(nullptr, *AssetClassPath);
}

static bool ValidateProperties(UObject* Target,
                               const TSharedPtr<FJsonObject>& PropertiesJson,
                               FAssetMutationContext& Context)
{
	TArray<FString> ValidationErrors;
	const bool bValid = FPropertySerializer::ApplyPropertiesFromJson(
		Target,
		PropertiesJson,
		ValidationErrors,
		true,
		true);

	Context.SetValidationSummary(
		bValid,
		bValid ? TEXT("DataAsset payload validated.") : TEXT("DataAsset payload failed validation."),
		ValidationErrors);

	for (const FString& Error : ValidationErrors)
	{
		Context.AddError(TEXT("validation_error"), Error, Target ? Target->GetPathName() : FString());
	}

	return bValid;
}

static bool IsEnhancedInputDataAssetClass(const UClass* AssetClass)
{
	if (!AssetClass)
	{
		return false;
	}

	const FString ClassPath = AssetClass->GetPathName();
	return ClassPath.StartsWith(TEXT("/Script/EnhancedInput."));
}

static void CleanupFailedCreate(UObject* CreatedObject, UPackage* /*Package*/)
{
	CleanupFailedCreateAsset(CreatedObject);
}

} // namespace DataAssetAuthoringInternal

TSharedPtr<FJsonObject> FDataAssetAuthoring::Create(const FString& AssetPath,
                                                    const FString& AssetClassPath,
                                                    const TSharedPtr<FJsonObject>& PropertiesJson,
                                                    const bool bValidateOnly)
{
	using namespace DataAssetAuthoringInternal;

	FAssetMutationContext Context(TEXT("create_data_asset"), AssetPath, TEXT("DataAsset"), bValidateOnly);

	UClass* AssetClass = ResolveDataAssetClass(AssetClassPath);
	if (!AssetClass)
	{
		Context.AddError(TEXT("asset_class_not_found"),
		                 FString::Printf(TEXT("DataAsset class not found: %s"), *AssetClassPath),
		                 AssetClassPath);
		return Context.BuildResult(false);
	}

	if (!AssetClass->IsChildOf(UDataAsset::StaticClass()) || AssetClass->HasAnyClassFlags(CLASS_Abstract))
	{
		Context.AddError(TEXT("invalid_asset_class"),
		                 FString::Printf(TEXT("Class '%s' is not a concrete UDataAsset subclass."), *AssetClass->GetName()),
		                 AssetClassPath);
		return Context.BuildResult(false);
	}

	if (IsEnhancedInputDataAssetClass(AssetClass))
	{
		Context.AddError(TEXT("unsupported_asset_class"),
		                 TEXT("Generic DataAsset authoring does not support Enhanced Input assets. Use the dedicated InputAction/InputMappingContext tools."),
		                 AssetClass->GetPathName());
		return Context.BuildResult(false);
	}

	if (DoesAssetExist(AssetPath))
	{
		Context.AddError(TEXT("asset_exists"),
		                 FString::Printf(TEXT("Asset already exists: %s"), *AssetPath),
		                 AssetPath);
		return Context.BuildResult(false);
	}

	UObject* PreviewObject = NewObject<UObject>(GetTransientPackage(), AssetClass);
	if (!PreviewObject)
	{
		Context.AddError(TEXT("preview_create_failed"), TEXT("Failed to create preview DataAsset instance."));
		return Context.BuildResult(false);
	}

	if (!ValidateProperties(PreviewObject, PropertiesJson, Context))
	{
		return Context.BuildResult(false);
	}

	if (bValidateOnly)
	{
		return Context.BuildResult(true);
	}

	Context.BeginTransaction(FText::FromString(TEXT("Create DataAsset")));

	UPackage* Package = CreatePackage(*AssetPath);
	if (!Package)
	{
		Context.AddError(TEXT("package_create_failed"),
		                 FString::Printf(TEXT("Failed to create package: %s"), *AssetPath),
		                 AssetPath);
		return Context.BuildResult(false);
	}

	const FName AssetName = FPackageName::GetShortFName(AssetPath);
	UDataAsset* DataAsset = NewObject<UDataAsset>(Package, AssetClass, AssetName, RF_Public | RF_Standalone);
	if (!DataAsset)
	{
		Context.AddError(TEXT("asset_create_failed"),
		                 FString::Printf(TEXT("Failed to create DataAsset asset: %s"), *AssetPath),
		                 AssetPath);
		return Context.BuildResult(false);
	}

	DataAsset->Modify();

	TArray<FString> ApplyErrors;
	const bool bApplySuccess = FPropertySerializer::ApplyPropertiesFromJson(
		DataAsset,
		PropertiesJson,
		ApplyErrors,
		false,
		true);
	for (const FString& Error : ApplyErrors)
	{
		Context.AddError(TEXT("apply_error"), Error, AssetPath);
	}
	if (!bApplySuccess)
	{
		CleanupFailedCreate(DataAsset, Package);
		return Context.BuildResult(false);
	}

	FAssetRegistryModule::AssetCreated(DataAsset);
	Package->MarkPackageDirty();
	Context.TrackDirtyObject(DataAsset);

	TSharedPtr<FJsonObject> Result = Context.BuildResult(true);
	Result->SetStringField(TEXT("createdAssetClass"), AssetClass->GetPathName());
	return Result;
}

TSharedPtr<FJsonObject> FDataAssetAuthoring::Modify(UDataAsset* DataAsset,
                                                    const TSharedPtr<FJsonObject>& PropertiesJson,
                                                    const bool bValidateOnly)
{
	const FString AssetPath = DataAsset ? DataAsset->GetPathName() : FString();
	FAssetMutationContext Context(TEXT("modify_data_asset"), AssetPath, TEXT("DataAsset"), bValidateOnly);

	if (!DataAsset)
	{
		Context.AddError(TEXT("asset_not_found"), TEXT("DataAsset is null."));
		return Context.BuildResult(false);
	}

	if (DataAssetAuthoringInternal::IsEnhancedInputDataAssetClass(DataAsset->GetClass()))
	{
		Context.AddError(TEXT("unsupported_asset_class"),
		                 TEXT("Generic DataAsset mutation does not support Enhanced Input assets. Use the dedicated InputAction/InputMappingContext tools."),
		                 DataAsset->GetClass()->GetPathName());
		return Context.BuildResult(false);
	}

	if (!DataAssetAuthoringInternal::ValidateProperties(DataAsset, PropertiesJson, Context))
	{
		return Context.BuildResult(false);
	}

	if (bValidateOnly)
	{
		return Context.BuildResult(true);
	}

	Context.BeginTransaction(FText::FromString(TEXT("Modify DataAsset")));
	DataAsset->Modify();

	TArray<FString> ApplyErrors;
	const bool bApplySuccess = FPropertySerializer::ApplyPropertiesFromJson(
		DataAsset,
		PropertiesJson,
		ApplyErrors,
		false,
		true);
	for (const FString& Error : ApplyErrors)
	{
		Context.AddError(TEXT("apply_error"), Error, AssetPath);
	}
	if (!bApplySuccess)
	{
		return Context.BuildResult(false);
	}

	DataAsset->MarkPackageDirty();
	Context.TrackDirtyObject(DataAsset);
	return Context.BuildResult(true);
}
