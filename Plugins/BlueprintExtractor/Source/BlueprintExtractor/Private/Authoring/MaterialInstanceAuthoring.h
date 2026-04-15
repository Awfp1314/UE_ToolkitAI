#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

class UMaterialInstance;

struct FMaterialInstanceAuthoring
{
	static TSharedPtr<FJsonObject> Create(const FString& AssetPath,
	                                      const FString& ParentMaterialPath,
	                                      bool bValidateOnly);

	static TSharedPtr<FJsonObject> Modify(UMaterialInstance* MaterialInstance,
	                                      const TSharedPtr<FJsonObject>& PayloadJson,
	                                      bool bValidateOnly);
};
