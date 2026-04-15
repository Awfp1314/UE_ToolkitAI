#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

class UDataAsset;

struct FDataAssetAuthoring
{
	static TSharedPtr<FJsonObject> Create(const FString& AssetPath,
	                                      const FString& AssetClassPath,
	                                      const TSharedPtr<FJsonObject>& PropertiesJson,
	                                      bool bValidateOnly);

	static TSharedPtr<FJsonObject> Modify(UDataAsset* DataAsset,
	                                      const TSharedPtr<FJsonObject>& PropertiesJson,
	                                      bool bValidateOnly);
};
