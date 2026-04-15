#pragma once

#include "CoreMinimal.h"
#include "Templates/UniquePtr.h"

class FJsonObject;

class FBlueprintExtractorImportJobManager
{
public:
	FBlueprintExtractorImportJobManager();
	~FBlueprintExtractorImportJobManager();

	TSharedPtr<FJsonObject> EnqueueImportJob(const FString& Operation,
	                                        const FString& PayloadJson,
	                                        bool bValidateOnly);
	TSharedPtr<FJsonObject> EnqueueReimportJob(const FString& Operation,
	                                          const FString& PayloadJson,
	                                          bool bValidateOnly);
	TSharedPtr<FJsonObject> EnqueueTextureImportJob(const FString& Operation,
	                                                const FString& PayloadJson,
	                                                bool bValidateOnly);
	TSharedPtr<FJsonObject> EnqueueMeshImportJob(const FString& Operation,
	                                             const FString& PayloadJson,
	                                             bool bValidateOnly);
	TSharedPtr<FJsonObject> GetImportJob(const FString& JobId);
	TSharedPtr<FJsonObject> ListImportJobs(bool bIncludeCompleted);

private:
	struct FImpl;
	TUniquePtr<FImpl> Impl;
};
