#include "Extractors/DataAssetExtractor.h"
#include "BlueprintExtractorModule.h"
#include "BlueprintExtractorVersion.h"
#include "Engine/DataAsset.h"
#include "PropertySerializer.h"

TSharedPtr<FJsonObject> FDataAssetExtractor::Extract(const UDataAsset* DataAsset)
{
	if (!ensureMsgf(DataAsset, TEXT("DataAssetExtractor: null DataAsset")))
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetStringField(TEXT("schemaVersion"), BlueprintExtractor::SchemaVersion);

	TSharedPtr<FJsonObject> DAObj = MakeShared<FJsonObject>();
	DAObj->SetStringField(TEXT("assetPath"), DataAsset->GetPathName());
	DAObj->SetStringField(TEXT("assetName"), DataAsset->GetName());
	DAObj->SetStringField(TEXT("dataAssetClass"), DataAsset->GetClass()->GetName());

	// Determine which base classes to skip (only extract user-defined properties)
	static const UClass* DataAssetBase         = UDataAsset::StaticClass();
	static const UClass* PrimaryDataAssetBase  = FindObject<UClass>(nullptr, TEXT("/Script/Engine.PrimaryDataAsset"));
	static const UClass* ObjectBase            = UObject::StaticClass();

	TArray<const UClass*> SkipClasses = { DataAssetBase, ObjectBase };
	if (PrimaryDataAssetBase)
	{
		SkipClasses.Add(PrimaryDataAssetBase);
	}

	DAObj->SetArrayField(TEXT("properties"),
		FPropertySerializer::SerializeUserProperties(DataAsset, DataAsset->GetClass(), SkipClasses));

	Root->SetObjectField(TEXT("dataAsset"), DAObj);
	return Root;
}
