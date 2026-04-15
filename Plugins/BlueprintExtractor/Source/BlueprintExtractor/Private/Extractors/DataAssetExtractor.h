#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

class UDataAsset;

struct FDataAssetExtractor
{
	static TSharedPtr<FJsonObject> Extract(const UDataAsset* DataAsset);
};
