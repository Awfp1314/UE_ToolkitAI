#include "Authoring/AssetMutationHelpers.h"

#include "FileHelpers.h"
#include "ScopedTransaction.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "Misc/PackageName.h"
#include "Modules/ModuleManager.h"
#include "UObject/Package.h"
#include "UObject/UObjectIterator.h"
#include "UObject/UObjectGlobals.h"

namespace AssetMutationHelpersInternal
{

static TArray<TSharedPtr<FJsonValue>> ToJsonArray(const TSet<FString>& Values)
{
	TArray<FString> SortedValues = Values.Array();
	SortedValues.Sort();

	TArray<TSharedPtr<FJsonValue>> Result;
	for (const FString& Value : SortedValues)
	{
		Result.Add(MakeShared<FJsonValueString>(Value));
	}
	return Result;
}

static TArray<TSharedPtr<FJsonValue>> ToDiagnosticsArray(const TArray<FAssetMutationDiagnostic>& Diagnostics)
{
	TArray<TSharedPtr<FJsonValue>> Result;
	for (const FAssetMutationDiagnostic& Diagnostic : Diagnostics)
	{
		const TSharedPtr<FJsonObject> DiagnosticObject = MakeShared<FJsonObject>();
		DiagnosticObject->SetStringField(TEXT("severity"), Diagnostic.Severity);
		DiagnosticObject->SetStringField(TEXT("code"), Diagnostic.Code);
		DiagnosticObject->SetStringField(TEXT("message"), Diagnostic.Message);
		if (!Diagnostic.Path.IsEmpty())
		{
			DiagnosticObject->SetStringField(TEXT("path"), Diagnostic.Path);
		}
		Result.Add(MakeShared<FJsonValueObject>(DiagnosticObject));
	}
	return Result;
}

} // namespace AssetMutationHelpersInternal

FString NormalizeAssetObjectPath(const FString& AssetPath)
{
	if (AssetPath.IsEmpty())
	{
		return FString();
	}

	if (FPackageName::IsValidObjectPath(AssetPath))
	{
		return AssetPath;
	}

	if (!FPackageName::IsValidLongPackageName(AssetPath))
	{
		if (AssetPath.StartsWith(TEXT("/")) && !AssetPath.Contains(TEXT(".")))
		{
			int32 LastSlashIndex = INDEX_NONE;
			if (AssetPath.FindLastChar(TEXT('/'), LastSlashIndex) && LastSlashIndex + 1 < AssetPath.Len())
			{
				const FString AssetName = AssetPath.Mid(LastSlashIndex + 1);
				if (!AssetName.IsEmpty())
				{
					return FString::Printf(TEXT("%s.%s"), *AssetPath, *AssetName);
				}
			}
		}

		return AssetPath;
	}

	const FString AssetName = FPackageName::GetLongPackageAssetName(AssetPath);
	if (AssetName.IsEmpty())
	{
		return AssetPath;
	}

	return FString::Printf(TEXT("%s.%s"), *AssetPath, *AssetName);
}

static FString NormalizeAssetPackagePath(const FString& AssetPath)
{
	if (AssetPath.IsEmpty())
	{
		return FString();
	}

	if (FPackageName::IsValidObjectPath(AssetPath))
	{
		return FPackageName::ObjectPathToPackageName(AssetPath);
	}

	if (FPackageName::IsValidLongPackageName(AssetPath))
	{
		return AssetPath;
	}

	if (AssetPath.StartsWith(TEXT("/")) && AssetPath.Contains(TEXT(".")))
	{
		int32 LastSlashIndex = INDEX_NONE;
		int32 LastDotIndex = INDEX_NONE;
		if (AssetPath.FindLastChar(TEXT('/'), LastSlashIndex) && AssetPath.FindLastChar(TEXT('.'), LastDotIndex) && LastDotIndex > LastSlashIndex)
		{
			return AssetPath.Left(LastDotIndex);
		}
	}

	return FString();
}

UObject* ResolveAssetByPath(const FString& AssetPath)
{
	const FString ObjectPath = NormalizeAssetObjectPath(AssetPath);
	const FString PackagePath = NormalizeAssetPackagePath(AssetPath);
	if (ObjectPath.IsEmpty())
	{
		return nullptr;
	}

	if (UObject* ExistingAsset = StaticFindObject(UObject::StaticClass(), nullptr, *ObjectPath))
	{
		return ExistingAsset;
	}

	if (!PackagePath.IsEmpty())
	{
		const FString AssetName = FPackageName::GetLongPackageAssetName(PackagePath);
		if (UPackage* ExistingPackage = FindPackage(nullptr, *PackagePath))
		{
			if (!AssetName.IsEmpty())
			{
				if (UObject* ExistingPackageAsset = StaticFindObject(UObject::StaticClass(), ExistingPackage, *AssetName))
				{
					return ExistingPackageAsset;
				}
			}
		}

		if (!AssetName.IsEmpty())
		{
			for (TObjectIterator<UObject> It; It; ++It)
			{
				UObject* Candidate = *It;
				if (!Candidate || Candidate->HasAnyFlags(RF_ClassDefaultObject))
				{
					continue;
				}

				if (Candidate->GetPathName() == ObjectPath)
				{
					return Candidate;
				}

				if (UPackage* CandidatePackage = Candidate->GetOutermost())
				{
					if (CandidatePackage->GetName() == PackagePath && Candidate->GetName() == AssetName)
					{
						return Candidate;
					}
				}
			}
		}

		TArray<FAssetData> AssetDatas;
		FAssetRegistryModule& AssetRegistryModule = FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry"));
		AssetRegistryModule.Get().GetAssetsByPackageName(FName(*PackagePath), AssetDatas, true);
		if (AssetDatas.Num() > 0)
		{
			if (UObject* Asset = AssetDatas[0].GetAsset())
			{
				return Asset;
			}
		}
	}

	return nullptr;
}

bool DoesAssetExist(const FString& AssetPath)
{
	const FString ObjectPath = NormalizeAssetObjectPath(AssetPath);
	const FString PackagePath = NormalizeAssetPackagePath(AssetPath);
	if (ObjectPath.IsEmpty() || PackagePath.IsEmpty())
	{
		return false;
	}

	const FString AssetName = FPackageName::GetLongPackageAssetName(PackagePath);
	if (AssetName.IsEmpty())
	{
		return false;
	}

	if (UPackage* ExistingPackage = FindPackage(nullptr, *PackagePath))
	{
		if (UObject* ExistingAsset = StaticFindObject(UObject::StaticClass(), ExistingPackage, *AssetName))
		{
			return !ExistingAsset->IsA<UPackage>();
		}
	}

	if (UObject* ExistingAsset = StaticFindObject(UObject::StaticClass(), nullptr, *ObjectPath))
	{
		return !ExistingAsset->IsA<UPackage>();
	}

	TArray<FAssetData> AssetDatas;
	FAssetRegistryModule& AssetRegistryModule = FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry"));
	AssetRegistryModule.Get().GetAssetsByPackageName(FName(*PackagePath), AssetDatas, true);
	return AssetDatas.ContainsByPredicate([&AssetName](const FAssetData& AssetData)
	{
		return AssetData.AssetName == FName(*AssetName);
	});
}

void CleanupFailedCreateAsset(UObject*& Asset)
{
	if (!Asset)
	{
		return;
	}

	UPackage* Package = Asset->GetOutermost();
	const bool bIsInRealPackage = Package && Package != GetTransientPackage();

	if (bIsInRealPackage)
	{
		FAssetRegistryModule::AssetDeleted(Asset);
		Package->SetDirtyFlag(false);
	}

	Asset->ClearFlags(RF_Public | RF_Standalone);
	Asset->Rename(
		nullptr,
		GetTransientPackage(),
		REN_DontCreateRedirectors | REN_ForceNoResetLoaders | REN_NonTransactional);
	Asset->MarkAsGarbage();
	Asset = nullptr;

	if (bIsInRealPackage && Package)
	{
		Package->ClearFlags(RF_Standalone);
		Package->MarkAsGarbage();
	}
}

FAssetMutationContext::FAssetMutationContext(const FString& InOperation,
                                             const FString& InAssetPath,
                                             const FString& InAssetClass,
                                             const bool bInValidateOnly)
	: Operation(InOperation)
	, AssetPath(InAssetPath)
	, AssetClass(InAssetClass)
	, bValidateOnly(bInValidateOnly)
{
}

FAssetMutationContext::~FAssetMutationContext() = default;

void FAssetMutationContext::BeginTransaction(const FText& Description)
{
	if (!bValidateOnly && !Transaction.IsValid())
	{
		Transaction = MakeUnique<FScopedTransaction>(Description);
	}
}

void FAssetMutationContext::AddDiagnostic(const FString& Severity,
                                          const FString& Code,
                                          const FString& Message,
                                          const FString& Path)
{
	Diagnostics.Add({Severity, Code, Message, Path});
}

void FAssetMutationContext::AddError(const FString& Code,
                                     const FString& Message,
                                     const FString& Path)
{
	AddDiagnostic(TEXT("error"), Code, Message, Path);
}

void FAssetMutationContext::AddWarning(const FString& Code,
                                       const FString& Message,
                                       const FString& Path)
{
	AddDiagnostic(TEXT("warning"), Code, Message, Path);
}

void FAssetMutationContext::AddInfo(const FString& Code,
                                    const FString& Message,
                                    const FString& Path)
{
	AddDiagnostic(TEXT("info"), Code, Message, Path);
}

void FAssetMutationContext::TrackChangedObject(const UObject* Object)
{
	if (Object)
	{
		ChangedObjects.Add(Object->GetPathName());
	}
}

void FAssetMutationContext::TrackDirtyObject(const UObject* Object)
{
	if (!Object)
	{
		return;
	}

	TrackChangedObject(Object);

	if (const UPackage* Package = Object->GetOutermost())
	{
		DirtyPackages.Add(Package->GetName());
	}
}

void FAssetMutationContext::SetValidationSummary(const bool bSuccess,
                                                 const FString& Summary,
                                                 const TArray<FString>& Errors)
{
	ValidationSummary = MakeShared<FJsonObject>();
	ValidationSummary->SetBoolField(TEXT("success"), bSuccess);
	ValidationSummary->SetStringField(TEXT("summary"), Summary);

	TArray<TSharedPtr<FJsonValue>> ErrorValues;
	for (const FString& Error : Errors)
	{
		ErrorValues.Add(MakeShared<FJsonValueString>(Error));
	}
	ValidationSummary->SetArrayField(TEXT("errors"), ErrorValues);
}

void FAssetMutationContext::SetCompileSummary(const TSharedPtr<FJsonObject>& InCompileSummary)
{
	CompileSummary = InCompileSummary;
}

TSharedPtr<FJsonObject> FAssetMutationContext::BuildResult(const bool bSuccess) const
{
	using namespace AssetMutationHelpersInternal;

	const TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
	const FString ObjectPath = NormalizeAssetObjectPath(AssetPath);
	const FString PackagePath = NormalizeAssetPackagePath(AssetPath);
	Result->SetBoolField(TEXT("success"), bSuccess);
	Result->SetStringField(TEXT("operation"), Operation);
	Result->SetStringField(TEXT("assetPath"), AssetPath);
	if (!PackagePath.IsEmpty())
	{
		Result->SetStringField(TEXT("packagePath"), PackagePath);
	}
	if (!ObjectPath.IsEmpty())
	{
		Result->SetStringField(TEXT("objectPath"), ObjectPath);
	}
	Result->SetStringField(TEXT("assetClass"), AssetClass);
	Result->SetBoolField(TEXT("saved"), false);
	Result->SetBoolField(TEXT("validateOnly"), bValidateOnly);
	Result->SetArrayField(TEXT("changedObjects"), ToJsonArray(ChangedObjects));
	Result->SetArrayField(TEXT("dirtyPackages"), ToJsonArray(DirtyPackages));
	Result->SetArrayField(TEXT("diagnostics"), ToDiagnosticsArray(Diagnostics));

	// Synthesize a top-level message from diagnostics so the MCP layer
	// always has a human-readable summary even without parsing the array.
	if (!bSuccess)
	{
		FString Message;
		for (const FAssetMutationDiagnostic& Diag : Diagnostics)
		{
			if (Diag.Severity == TEXT("error") && !Diag.Message.IsEmpty())
			{
				if (!Message.IsEmpty())
				{
					Message += TEXT("; ");
				}
				Message += Diag.Message;
			}
		}
		if (Message.IsEmpty())
		{
			Message = FString::Printf(TEXT("%s failed for '%s' with no diagnostic details."),
				*Operation, *AssetPath);
		}
		Result->SetStringField(TEXT("message"), Message);
	}

	if (ValidationSummary.IsValid())
	{
		Result->SetObjectField(TEXT("validation"), ValidationSummary);
	}

	if (CompileSummary.IsValid())
	{
		Result->SetObjectField(TEXT("compile"), CompileSummary);
	}

	return Result;
}

TSharedPtr<FJsonObject> FAssetMutationContext::SaveAssets(const TArray<FString>& AssetPaths)
{
	FAssetMutationContext Context(TEXT("save_assets"), TEXT(""), TEXT("Package"), false);

	TArray<UPackage*> PackagesToSave;
	for (const FString& AssetPath : AssetPaths)
	{
		UObject* Asset = ResolveAssetByPath(AssetPath);
		if (!Asset)
		{
			Context.AddError(TEXT("asset_not_found"),
			                 FString::Printf(TEXT("Asset not found: %s"), *AssetPath),
			                 AssetPath);
			continue;
		}

		UPackage* Package = Asset->GetOutermost();
		if (!Package)
		{
			Context.AddError(TEXT("package_not_found"),
			                 FString::Printf(TEXT("Package not found for asset: %s"), *AssetPath),
			                 AssetPath);
			continue;
		}

		Context.TrackDirtyObject(Asset);
		PackagesToSave.AddUnique(Package);
	}

	bool bSaved = false;
	if (PackagesToSave.Num() > 0)
	{
		bSaved = UEditorLoadingAndSavingUtils::SavePackages(PackagesToSave, true);
		if (!bSaved)
		{
			Context.AddError(TEXT("save_failed"), TEXT("Failed to save one or more packages."));
		}
	}

	TSharedPtr<FJsonObject> Result = Context.BuildResult(bSaved && Context.Diagnostics.Num() == 0);
	Result->SetBoolField(TEXT("saved"), bSaved);
	return Result;
}
