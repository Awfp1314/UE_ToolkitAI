#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

class UMaterialInstance;

struct FMaterialInstanceExtractor
{
	static TSharedPtr<FJsonObject> Extract(const UMaterialInstance* MaterialInstance);
};
