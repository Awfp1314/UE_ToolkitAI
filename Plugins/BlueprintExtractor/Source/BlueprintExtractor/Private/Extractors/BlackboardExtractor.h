#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

class UBlackboardData;

struct FBlackboardExtractor
{
	static TSharedPtr<FJsonObject> Extract(const UBlackboardData* BlackboardData);
};
