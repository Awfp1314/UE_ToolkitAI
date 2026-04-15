#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

class FScopedTransaction;
class UObject;

FString NormalizeAssetObjectPath(const FString& AssetPath);
UObject* ResolveAssetByPath(const FString& AssetPath);
bool DoesAssetExist(const FString& AssetPath);
void CleanupFailedCreateAsset(UObject*& Asset);

struct FAssetMutationDiagnostic
{
	FString Severity;
	FString Code;
	FString Message;
	FString Path;
};

struct FAssetMutationContext
{
	FString Operation;
	FString AssetPath;
	FString AssetClass;
	bool bValidateOnly = false;

	TArray<FAssetMutationDiagnostic> Diagnostics;
	TSet<FString> ChangedObjects;
	TSet<FString> DirtyPackages;
	TSharedPtr<FJsonObject> ValidationSummary;
	TSharedPtr<FJsonObject> CompileSummary;

	FAssetMutationContext(const FString& InOperation,
	                      const FString& InAssetPath,
	                      const FString& InAssetClass,
	                      bool bInValidateOnly);
	~FAssetMutationContext();

	void BeginTransaction(const FText& Description);
	void AddDiagnostic(const FString& Severity,
	                   const FString& Code,
	                   const FString& Message,
	                   const FString& Path = FString());
	void AddError(const FString& Code,
	              const FString& Message,
	              const FString& Path = FString());
	void AddWarning(const FString& Code,
	                const FString& Message,
	                const FString& Path = FString());
	void AddInfo(const FString& Code,
	             const FString& Message,
	             const FString& Path = FString());
	void TrackChangedObject(const UObject* Object);
	void TrackDirtyObject(const UObject* Object);
	void SetValidationSummary(bool bSuccess,
	                          const FString& Summary,
	                          const TArray<FString>& Errors = {});
	void SetCompileSummary(const TSharedPtr<FJsonObject>& InCompileSummary);
	TSharedPtr<FJsonObject> BuildResult(bool bSuccess) const;

	static TSharedPtr<FJsonObject> SaveAssets(const TArray<FString>& AssetPaths);

private:
	TUniquePtr<FScopedTransaction> Transaction;
};
