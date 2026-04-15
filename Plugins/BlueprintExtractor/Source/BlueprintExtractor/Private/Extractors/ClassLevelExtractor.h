#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

class UBlueprint;

struct FClassLevelExtractor
{
	static TSharedPtr<FJsonObject> Extract(const UBlueprint* Blueprint);
};
