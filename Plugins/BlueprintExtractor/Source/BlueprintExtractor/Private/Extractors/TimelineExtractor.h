#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"

class UBlueprint;

struct FTimelineExtractor
{
	static TArray<TSharedPtr<FJsonValue>> Extract(const UBlueprint* Blueprint);
};
