#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

class UUserDefinedStruct;

struct FUserDefinedStructExtractor
{
	static TSharedPtr<FJsonObject> Extract(const UUserDefinedStruct* UserDefinedStruct);
};
